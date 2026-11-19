"""Hybrid Lexical (FTS5 + Identifier Index) and Knowledge Graph Retrieval Engine."""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Set

from ..config import AppConfig, RetrievalLimits
from ..ingestion.discovery import SourceCatalog
from ..models.entities import SearchResultItem
from ..storage.database import DatabaseManager
from .evidence_selector import EvidenceSelector
from .graph_expansion import KnowledgeGraphExpander
from .query_normalizer import QueryNormalizer
from .ranking import RelevanceRanker


class RetrievalEngine:
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self.db = DatabaseManager(self.config)
        self.catalog = SourceCatalog(self.config.sources_config_path)
        self.normalizer = QueryNormalizer()
        self.ranker = RelevanceRanker()
        self.graph = KnowledgeGraphExpander(self.db)
        self.selector = EvidenceSelector(self.config.retrieval_limits)

    def search(
        self,
        query: str,
        technology: Optional[str] = None,
        version: Optional[str] = None,
        authority: Optional[str] = None,
        topic: Optional[str] = None,
        limit: Optional[int] = None,
        expand_graph: bool = True,
        graph_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        norm_q = self.normalizer.normalize(query)

        effective_tech = technology or (norm_q.inferred_technology if version else None)
        resolved_version: Optional[str] = None
        version_notice: Optional[str] = None

        if version:
            tech_for_ver = effective_tech or "rails"
            resolved_version, version_notice, _ = self.catalog.resolve_version_with_fallback(
                tech_for_ver, version
            )

        version_status_map: Dict[str, str] = {}
        for v in self.catalog.versions:
            version_status_map[f"{v.technology}:{v.version}"] = v.status

        candidates: Dict[str, Dict[str, Any]] = {}
        identifier_weights: Dict[str, float] = {}

        with self.db.connect(readonly=True) as conn:
            # 1. Auxiliary technical identifier exact & normalized lookup
            all_lookup_idents = list(dict.fromkeys(norm_q.raw_identifiers + norm_q.normalized_identifiers))
            if all_lookup_idents:
                placeholders = ",".join("?" for _ in all_lookup_idents)
                id_sql = f"""
                    SELECT ci.chunk_id, SUM(ci.weight) AS total_id_weight
                    FROM chunk_identifiers ci
                    WHERE ci.identifier IN ({placeholders})
                       OR ci.normalized_identifier IN ({placeholders})
                    GROUP BY ci.chunk_id
                """
                for r in conn.execute(id_sql, all_lookup_idents + all_lookup_idents).fetchall():
                    identifier_weights[r["chunk_id"]] = float(r["total_id_weight"])

            # 2. FTS5 Lexical Search
            if norm_q.fts_expression:
                fts_sql = """
                    SELECT c.*,
                           bm25(knowledge_chunks_fts, 0.0, 10.0, 5.0, 4.0, 4.0, 8.0, 1.0) AS bm25_score
                    FROM knowledge_chunks_fts
                    JOIN knowledge_chunks c ON c.id = knowledge_chunks_fts.chunk_id
                    WHERE knowledge_chunks_fts MATCH ?
                """
                params: List[Any] = [norm_q.fts_expression]
                fts_sql, params = self._apply_sql_filters(
                    fts_sql, params, technology, resolved_version, authority, topic
                )
                fts_sql += " ORDER BY bm25_score ASC LIMIT 40"
                for row in conn.execute(fts_sql, params).fetchall():
                    d = dict(row)
                    candidates[d["id"]] = d

            # 3. Also load chunks matched via auxiliary chunk_identifiers that might not be in FTS top 40
            missing_id_chunks = [cid for cid in identifier_weights if cid not in candidates]
            if missing_id_chunks:
                ph = ",".join("?" for _ in missing_id_chunks)
                id_chunk_sql = f"SELECT c.*, -5.0 AS bm25_score FROM knowledge_chunks c WHERE c.id IN ({ph})"
                id_params: List[Any] = list(missing_id_chunks)
                id_chunk_sql, id_params = self._apply_sql_filters(
                    id_chunk_sql, id_params, technology, resolved_version, authority, topic
                )
                for row in conn.execute(id_chunk_sql, id_params).fetchall():
                    d = dict(row)
                    candidates[d["id"]] = d

            # 4. Fetch related concepts & parent document token counts for candidates
            candidate_list = list(candidates.values())
            chunk_concepts_map: Dict[str, List[str]] = {}
            doc_full_chars: Dict[str, int] = {}

            if candidate_list:
                c_ids = [c["id"] for c in candidate_list]
                c_ph = ",".join("?" for _ in c_ids)
                cc_rows = conn.execute(
                    f"""
                    SELECT cc.chunk_id, con.name
                    FROM chunk_concepts cc
                    JOIN concepts con ON con.id = cc.concept_id
                    WHERE cc.chunk_id IN ({c_ph})
                    ORDER BY con.name
                    """,
                    c_ids,
                ).fetchall()
                for r in cc_rows:
                    chunk_concepts_map.setdefault(r["chunk_id"], []).append(r["name"])

                doc_ids = list({c["document_id"] for c in candidate_list})
                d_ph = ",".join("?" for _ in doc_ids)
                doc_rows = conn.execute(
                    f"""
                    SELECT document_id, SUM(char_count) AS total_doc_chars
                    FROM knowledge_chunks
                    WHERE document_id IN ({d_ph})
                    GROUP BY document_id
                    """,
                    doc_ids,
                ).fetchall()
                for r in doc_rows:
                    doc_full_chars[r["document_id"]] = int(r["total_doc_chars"] or 0)

        # Rank all candidates
        scored_items: List[SearchResultItem] = []
        seen_titles_in_version: Set[tuple[str, str, str]] = set()

        raw_scored = []
        for c in candidates.values():
            cid = c["id"]
            score = self.ranker.score_candidate(
                row=c,
                norm_query=norm_q,
                requested_version=resolved_version,
                requested_technology=technology,
                matched_identifier_weight=identifier_weights.get(cid, 0.0),
            )
            raw_scored.append((score, c))

        raw_scored.sort(key=lambda x: (-x[0], x[1]["section_order"]))

        # When no explicit version filter was passed, avoid duplicate identical sections across 5 minor versions
        # unless the query specifically asks to compare versions
        dedup_across_versions = (
            resolved_version is None and len(norm_q.inferred_versions) <= 1
        )
        seen_topic_title: Set[tuple[str, str]] = set()

        for score, c in raw_scored:
            if dedup_across_versions:
                # Normalize version suffix in title like "(Rails 8.0)" so we keep the best-ranked version first
                import re
                base_title = re.sub(r"\s*\((?:Rails|Ruby)\s+[^)]+\)", "", c["title"]).strip().lower()
                t_key = (c["technology"], base_title)
                if t_key in seen_topic_title:
                    continue
                seen_topic_title.add(t_key)

            cid = c["id"]
            v_key = f"{c['technology']}:{c['version']}"
            v_status = version_status_map.get(v_key, "stable")
            rel_concepts = chunk_concepts_map.get(cid, [])

            graph_rels: List[Dict[str, Any]] = []
            if expand_graph and rel_concepts:
                depth = graph_depth or self.config.retrieval_limits.max_graph_depth
                graph_rels = self.graph.expand_for_concepts(
                    rel_concepts,
                    technology=c["technology"],
                    max_depth=min(depth, 2),
                    max_related=self.config.retrieval_limits.max_related_concepts,
                )

            scored_items.append(
                SearchResultItem(
                    id=cid,
                    title=c["title"],
                    technology=c["technology"],
                    version=c["version"],
                    version_status=v_status,
                    topic=c["topic"],
                    subtopic=c["subtopic"],
                    content=c["content"],
                    source_id=c["source_id"],
                    source_url=c["source_url"],
                    source_section=c["source_section"],
                    authority=c["authority"],
                    related_concepts=rel_concepts,
                    score=score,
                    graph_relations=graph_rels,
                    captured_at=c["captured_at"],
                    content_hash=c["content_hash"],
                )
            )

        selected = self.selector.select_evidence(
            scored_items, max_results_override=limit or 0
        )

        # Compute measured token efficiency metrics vs full parent documents
        returned_chars = sum(len(item.content) for item in selected)
        returned_tokens = max(0, (returned_chars + 3) // 4) if selected else 0

        selected_doc_ids = {
            candidates[item.id]["document_id"]
            for item in selected
            if item.id in candidates
        }
        selected_versions = {(item.technology, item.version) for item in selected}
        candidate_doc_ids = {
            c["document_id"]
            for c in candidates.values()
            if not selected_versions or (c["technology"], c["version"]) in selected_versions
        }
        parent_docs_chars = sum(doc_full_chars.get(did, 0) for did in selected_doc_ids)
        full_docs_chars = sum(doc_full_chars.get(did, 0) for did in (candidate_doc_ids or selected_doc_ids))
        parent_docs_tokens = max(returned_tokens, (parent_docs_chars + 3) // 4)
        full_docs_tokens = max(parent_docs_tokens, (full_docs_chars + 3) // 4)
        savings_pct = (
            round((1.0 - (returned_tokens / float(full_docs_tokens))) * 100.0, 2)
            if full_docs_tokens > 0 and returned_tokens < full_docs_tokens
            else 0.0
        )

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        return {
            "query": query,
            "filters": {
                "technology": technology,
                "version": version,
                "resolved_version": resolved_version,
                "authority": authority,
                "topic": topic,
            },
            "results": [item.to_dict() for item in selected],
            "metadata": {
                "total_results": len(selected),
                "retrieval_method": "fts5+identifier_index+graph" if expand_graph else "fts5+identifier_index",
                "elapsed_ms": elapsed_ms,
                "version_notice": version_notice,
                "estimated_tokens": returned_tokens,
                "full_docs_tokens": full_docs_tokens,
                "token_savings_pct": savings_pct,
            },
        }

    @staticmethod
    def _apply_sql_filters(
        sql: str,
        params: List[Any],
        technology: Optional[str],
        resolved_version: Optional[str],
        authority: Optional[str],
        topic: Optional[str],
    ) -> tuple[str, List[Any]]:
        if technology:
            sql += " AND c.technology = ?"
            params.append(technology)
        if resolved_version:
            sql += " AND c.version = ?"
            params.append(resolved_version)
        elif resolved_version is None:
            # By default, never mix unreleased edge docs into general queries unless version=edge is requested
            sql += " AND c.version != 'edge'"
        if authority:
            sql += " AND c.authority = ?"
            params.append(authority)
        if topic:
            sql += " AND (c.topic = ? OR c.subtopic = ?)"
            params.extend([topic, topic])
        return (sql, params)
