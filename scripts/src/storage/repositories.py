"""SQLite Repositories for atomic persistence, FTS5 indexing, and Knowledge Graph."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..models.entities import (
    ConceptEntity,
    DocumentEntity,
    IngestionRunSummary,
    KnowledgeChunk,
    RelationshipEntity,
    SourceConfig,
    VersionInfo,
    validate_chunk_metadata,
)
from .database import DatabaseManager
from .fts import extract_technical_identifiers, normalize_identifier, normalize_text_for_fts


class KnowledgeRepository:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def upsert_sources(self, sources: List[SourceConfig]) -> int:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.db.connect(readonly=False) as conn:
            for s in sources:
                s.validate()
                conn.execute(
                    """
                    INSERT INTO sources (id, technology, authority, source_type, base_url, versioned, enabled, description, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        technology=excluded.technology,
                        authority=excluded.authority,
                        source_type=excluded.source_type,
                        base_url=excluded.base_url,
                        versioned=excluded.versioned,
                        enabled=excluded.enabled,
                        description=excluded.description,
                        updated_at=excluded.updated_at
                    """,
                    (
                        s.id,
                        s.technology,
                        s.authority,
                        s.source_type,
                        s.base_url,
                        1 if s.versioned else 0,
                        1 if s.enabled else 0,
                        s.description,
                        now,
                    ),
                )
            conn.commit()
        self._write_sources_manifest(sources)
        return len(sources)

    def upsert_versions(self, versions: List[VersionInfo]) -> int:
        with self.db.connect(readonly=False) as conn:
            for v in versions:
                conn.execute(
                    """
                    INSERT INTO versions (id, technology, version, status, docs_available, is_latest_stable, release_date, eol_date, docs_url, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        status=excluded.status,
                        docs_available=excluded.docs_available,
                        is_latest_stable=excluded.is_latest_stable,
                        release_date=excluded.release_date,
                        eol_date=excluded.eol_date,
                        docs_url=excluded.docs_url,
                        notes=excluded.notes
                    """,
                    (
                        v.id,
                        v.technology,
                        v.version,
                        v.status,
                        1 if v.docs_available else 0,
                        1 if v.is_latest_stable else 0,
                        v.release_date,
                        v.eol_date,
                        v.docs_url,
                        v.notes,
                    ),
                )
            conn.commit()
        self._write_versions_manifest(versions)
        return len(versions)

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect(readonly=True) as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
            return dict(row) if row else None

    def get_document_versions(self, doc_id: str) -> List[Dict[str, Any]]:
        with self.db.connect(readonly=True) as conn:
            rows = conn.execute(
                "SELECT * FROM document_versions WHERE document_id = ? ORDER BY version_number ASC",
                (doc_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def persist_document_and_chunks(
        self,
        doc: DocumentEntity,
        chunks: List[KnowledgeChunk],
        concepts: List[ConceptEntity],
        relationships: List[RelationshipEntity],
        force_reprocess: bool = False,
    ) -> Tuple[str, int]:
        """Atomically persist a document, its historical revision, semantic chunks, FTS5 entries, and concepts.

        Returns:
            (change_type: 'created' | 'updated' | 'unchanged', chunks_persisted_count)
        """
        for chunk in chunks:
            validate_chunk_metadata(chunk)
        for rel in relationships:
            rel.validate()

        with self.db.connect(readonly=False) as conn:
            existing = conn.execute(
                "SELECT current_hash, status FROM documents WHERE id = ?",
                (doc.id,),
            ).fetchone()

            if existing and existing["current_hash"] == doc.current_hash and not force_reprocess:
                return ("unchanged", 0)

            prev_hash = existing["current_hash"] if existing else None
            change_type = "updated" if existing else "created"

            max_ver_row = conn.execute(
                "SELECT COALESCE(MAX(version_number), 0) AS max_v FROM document_versions WHERE document_id = ?",
                (doc.id,),
            ).fetchone()
            next_ver_num = int(max_ver_row["max_v"]) + 1

            conn.execute(
                """
                INSERT INTO documents (id, source_id, technology, version, topic, title, source_url, local_path, authority, current_hash, captured_at, updated_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_id=excluded.source_id,
                    technology=excluded.technology,
                    version=excluded.version,
                    topic=excluded.topic,
                    title=excluded.title,
                    source_url=excluded.source_url,
                    local_path=excluded.local_path,
                    authority=excluded.authority,
                    current_hash=excluded.current_hash,
                    updated_at=excluded.updated_at,
                    status=excluded.status
                """,
                (
                    doc.id,
                    doc.source_id,
                    doc.technology,
                    doc.version,
                    doc.topic,
                    doc.title,
                    doc.source_url,
                    doc.local_path,
                    doc.authority,
                    doc.current_hash,
                    doc.captured_at,
                    doc.updated_at,
                    doc.status,
                ),
            )

            # Record immutable revision in document_versions
            conn.execute(
                """
                INSERT INTO document_versions (document_id, version_number, content_hash, previous_hash, change_type, captured_at, snapshot_path, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.id,
                    next_ver_num,
                    doc.current_hash,
                    prev_hash,
                    change_type,
                    doc.updated_at,
                    doc.local_path,
                    f"{change_type} ({len(chunks)} chunks)",
                ),
            )

            # Remove old FTS rows & chunks for this document before inserting updated chunks
            old_chunk_rows = conn.execute(
                "SELECT id FROM knowledge_chunks WHERE document_id = ?",
                (doc.id,),
            ).fetchall()
            for r in old_chunk_rows:
                conn.execute("DELETE FROM knowledge_chunks_fts WHERE chunk_id = ?", (r["id"],))
            conn.execute("DELETE FROM knowledge_chunks WHERE document_id = ?", (doc.id,))

            # Upsert concepts first so foreign keys in chunk_concepts and relationships resolve
            for c in concepts:
                conn.execute(
                    """
                    INSERT INTO concepts (id, name, technology, category, description)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        description=CASE WHEN excluded.description != '' THEN excluded.description ELSE concepts.description END
                    """,
                    (c.id, c.name, c.technology, c.category, c.description),
                )

            # Insert chunks, FTS5 rows, technical identifiers, and chunk_concepts
            for idx, chunk in enumerate(chunks):
                extracted_idents = extract_technical_identifiers(
                    chunk.content,
                    title=chunk.title,
                    extra_concepts=chunk.related_concepts + chunk.identifiers,
                )
                norm_ident_str = normalize_text_for_fts(chunk.content, extracted_idents)
                chunk.normalized_identifiers = norm_ident_str

                conn.execute(
                    """
                    INSERT INTO knowledge_chunks (
                        id, document_id, technology, version, topic, subtopic, title, content,
                        normalized_identifiers, authority, source_id, source_url, source_section,
                        captured_at, content_hash, char_count, estimated_tokens, section_order
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.id,
                        doc.id,
                        chunk.technology,
                        chunk.version,
                        chunk.topic,
                        chunk.subtopic,
                        chunk.title,
                        chunk.content,
                        chunk.normalized_identifiers,
                        chunk.authority,
                        chunk.source_id,
                        chunk.source_url,
                        chunk.source_section,
                        chunk.captured_at,
                        chunk.content_hash,
                        chunk.char_count,
                        chunk.estimated_tokens,
                        idx,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO knowledge_chunks_fts (
                        chunk_id, title, source_section, topic, subtopic, normalized_identifiers, content
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.id,
                        chunk.title,
                        chunk.source_section,
                        chunk.topic,
                        chunk.subtopic,
                        chunk.normalized_identifiers,
                        chunk.content,
                    ),
                )

                for raw_id, norm_id, id_type, weight in extracted_idents:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO chunk_identifiers (
                            chunk_id, identifier, normalized_identifier, identifier_type, weight
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (chunk.id, raw_id, norm_id, id_type, weight),
                    )

                # Ensure every related concept on the chunk exists and is linked
                for concept_name in chunk.related_concepts:
                    c_norm = normalize_identifier(concept_name)
                    if not c_norm:
                        continue
                    c_id = f"{chunk.technology}:{c_norm}"
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO concepts (id, name, technology, category, description)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (c_id, c_norm, chunk.technology, chunk.topic, f"Concept {c_norm} in {chunk.technology}"),
                    )
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO chunk_concepts (chunk_id, concept_id, role)
                        VALUES (?, ?, 'related')
                        """,
                        (chunk.id, c_id),
                    )

            # Upsert relationships
            for rel in relationships:
                conn.execute(
                    """
                    INSERT INTO relationships (
                        id, source_concept_id, target_concept_id, relation_type,
                        technology, version_scope, evidence_chunk_id, source_url, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_concept_id, target_concept_id, relation_type, version_scope) DO UPDATE SET
                        evidence_chunk_id=excluded.evidence_chunk_id,
                        source_url=excluded.source_url,
                        notes=excluded.notes
                    """,
                    (
                        rel.id,
                        rel.source_concept_id,
                        rel.target_concept_id,
                        rel.relation_type,
                        rel.technology,
                        rel.version_scope,
                        rel.evidence_chunk_id,
                        rel.source_url,
                        rel.notes,
                    ),
                )

            conn.commit()
        return (change_type, len(chunks))

    def record_ingestion_run(self, summary: IngestionRunSummary) -> None:
        with self.db.connect(readonly=False) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO ingestion_runs (
                    id, run_type, started_at, completed_at, status, source_filter, version_filter,
                    docs_checked, docs_added, docs_updated, docs_unchanged, docs_failed,
                    chunks_indexed, error_log, summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.id,
                    summary.run_type,
                    summary.started_at,
                    summary.completed_at,
                    summary.status,
                    summary.source_filter,
                    summary.version_filter,
                    summary.docs_checked,
                    summary.docs_added,
                    summary.docs_updated,
                    summary.docs_unchanged,
                    summary.docs_failed,
                    summary.chunks_indexed,
                    "\n".join(summary.errors),
                    json.dumps(summary.to_dict()),
                ),
            )
            conn.commit()
        self._append_ingestion_history(summary)
        self.db.sync_to_cache()

    def list_sources(self) -> List[Dict[str, Any]]:
        with self.db.connect(readonly=True) as conn:
            rows = conn.execute(
                """
                SELECT s.*, COUNT(DISTINCT d.id) AS document_count, COUNT(c.id) AS chunk_count
                FROM sources s
                LEFT JOIN documents d ON d.source_id = s.id AND d.status = 'active'
                LEFT JOIN knowledge_chunks c ON c.document_id = d.id
                GROUP BY s.id
                ORDER BY s.technology, s.id
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def list_versions(self, technology: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.db.connect(readonly=True) as conn:
            sql = """
                SELECT v.*, COUNT(DISTINCT d.id) AS document_count, COUNT(c.id) AS chunk_count
                FROM versions v
                LEFT JOIN documents d ON d.technology = v.technology AND d.version = v.version AND d.status = 'active'
                LEFT JOIN knowledge_chunks c ON c.document_id = d.id
            """
            params: List[Any] = []
            if technology:
                sql += " WHERE v.technology = ?"
                params.append(technology)
            sql += " GROUP BY v.id ORDER BY v.technology, v.version"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_stats(self) -> Dict[str, Any]:
        with self.db.connect(readonly=True) as conn:
            sources_cnt = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
            versions_cnt = conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0]
            docs_cnt = conn.execute("SELECT COUNT(*) FROM documents WHERE status='active'").fetchone()[0]
            revs_cnt = conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0]
            chunks_cnt = conn.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()[0]
            idents_cnt = conn.execute("SELECT COUNT(*) FROM chunk_identifiers").fetchone()[0]
            concepts_cnt = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
            rels_cnt = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
            runs_cnt = conn.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0]
            last_run = conn.execute(
                "SELECT id, run_type, completed_at, status, docs_added, docs_updated, docs_unchanged FROM ingestion_runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            by_tech = conn.execute(
                "SELECT technology, version, COUNT(*) AS chunks FROM knowledge_chunks GROUP BY technology, version ORDER BY technology, version"
            ).fetchall()

        return {
            "sources": sources_cnt,
            "versions": versions_cnt,
            "documents": docs_cnt,
            "document_revisions": revs_cnt,
            "knowledge_chunks": chunks_cnt,
            "indexed_identifiers": idents_cnt,
            "concepts": concepts_cnt,
            "relationships": rels_cnt,
            "ingestion_runs": runs_cnt,
            "last_run": dict(last_run) if last_run else None,
            "coverage_by_version": [dict(r) for r in by_tech],
        }

    def _write_sources_manifest(self, sources: List[SourceConfig]) -> None:
        manifest_path = self.db.config.manifests_dir / "sources.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sources": [
                {
                    "id": s.id,
                    "technology": s.technology,
                    "authority": s.authority,
                    "source_type": s.source_type,
                    "base_url": s.base_url,
                    "versioned": s.versioned,
                    "enabled": s.enabled,
                    "supported_versions": s.supported_versions,
                }
                for s in sources
            ],
        }
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _write_versions_manifest(self, versions: List[VersionInfo]) -> None:
        manifest_path = self.db.config.manifests_dir / "versions.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "versions": [
                {
                    "id": v.id,
                    "technology": v.technology,
                    "version": v.version,
                    "status": v.status,
                    "docs_available": v.docs_available,
                    "is_latest_stable": v.is_latest_stable,
                    "release_date": v.release_date,
                    "eol_date": v.eol_date,
                    "docs_url": v.docs_url,
                    "notes": v.notes,
                }
                for v in versions
            ],
        }
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _append_ingestion_history(self, summary: IngestionRunSummary) -> None:
        hist_path = self.db.config.metadata_dir / "ingestion-history.json"
        hist_path.parent.mkdir(parents=True, exist_ok=True)
        history: List[Dict[str, Any]] = []
        if hist_path.exists():
            try:
                history = json.loads(hist_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                history = []
        history.append(summary.to_dict())
        hist_path.write_text(json.dumps(history[-100:], indent=2), encoding="utf-8")
