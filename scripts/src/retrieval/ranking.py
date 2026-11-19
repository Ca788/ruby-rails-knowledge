"""Multi-signal relevance ranking for hybrid lexical and identifier retrieval."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from .query_normalizer import NormalizedQuery


AUTHORITY_WEIGHTS = {
    "official": 3.0,
    "ecosystem_official": 2.2,
    "security_standard": 2.2,
    "community_standard": 1.6,
    "official_edge": 1.0,
}


class RelevanceRanker:
    """Scores candidate chunks using exact identifier match, term coverage, title match, BM25, version, and authority."""

    def score_candidate(
        self,
        row: Dict[str, Any],
        norm_query: NormalizedQuery,
        requested_version: Optional[str] = None,
        requested_technology: Optional[str] = None,
        matched_identifier_weight: float = 0.0,
    ) -> float:
        score = 0.0
        title_low = (row.get("title") or "").lower()
        sec_low = (row.get("source_section") or "").lower()
        content_low = (row.get("content") or "").lower()
        norm_idents_low = (row.get("normalized_identifiers") or "").lower()
        topic_low = (row.get("topic") or "").lower()
        subtopic_low = (row.get("subtopic") or "").lower()

        # 1. FTS5 BM25 base score (SQLite bm25 returns negative numbers where more negative = better)
        raw_bm25 = float(row.get("bm25_score") or 0.0)
        if raw_bm25 < 0:
            score += min(25.0, abs(raw_bm25))

        # 2. Auxiliary technical identifier match weight
        score += matched_identifier_weight * 3.5

        # 3. Exact technical identifier matches in title, normalized_identifiers, and content
        matched_idents = 0
        for ident in norm_query.normalized_identifiers:
            ident_low = ident.lower()
            hit = False
            if ident_low in title_low or ident_low in subtopic_low:
                score += 10.0
                hit = True
            if ident_low in norm_idents_low.split():
                score += 6.0
                hit = True
            elif ident_low in content_low:
                score += 4.0
                hit = True
            if hit:
                matched_idents += 1

        # Multi-identifier coverage bonus (crucial for comparative queries like "after_save vs after_commit" or "includes, preload, eager_load")
        if len(norm_query.normalized_identifiers) >= 2 and matched_idents >= 2:
            score += matched_idents * 7.5

        # 4. Keyword coverage across title, section, topic, and content
        matched_kw = 0
        for kw in norm_query.keywords:
            kw_hit = False
            if kw in title_low:
                score += 5.5
                kw_hit = True
            elif kw in sec_low or kw in topic_low or kw in subtopic_low:
                score += 3.0
                kw_hit = True
            if kw in content_low:
                score += 1.8
                kw_hit = True
            if kw_hit:
                matched_kw += 1

        if len(norm_query.keywords) >= 2 and matched_kw >= 2:
            coverage_ratio = matched_kw / float(len(norm_query.keywords))
            score += coverage_ratio * 10.0

        # 5. Version compatibility and stability preference
        chunk_ver = str(row.get("version") or "")
        if requested_version:
            if chunk_ver == requested_version:
                score += 12.0
            else:
                score -= 5.0
        elif norm_query.inferred_versions:
            if chunk_ver in norm_query.inferred_versions:
                score += 9.0
        else:
            # When no version is specified, prefer current stable or requested project version over edge
            if chunk_ver in ("8.0", "7.2", "3.4", "3.3", "6.1"):
                score += 2.5
            if chunk_ver == "edge":
                score -= 6.0

        # 6. Technology alignment
        chunk_tech = row.get("technology") or ""
        target_tech = requested_technology or norm_query.inferred_technology
        if target_tech and chunk_tech == target_tech:
            score += 4.0

        # 7. Authority weight
        auth = row.get("authority") or "official"
        if requested_version == "edge" and auth == "official_edge":
            score += 4.0
        else:
            score += AUTHORITY_WEIGHTS.get(auth, 1.0)

        return score
