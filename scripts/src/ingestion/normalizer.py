"""Document and section normalizer, stable ID builder, and SHA-256 content hashing."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import List, Optional, Tuple

from ..models.entities import DocumentEntity, KnowledgeChunk
from .fetcher import sanitize_filename
from .parser import ExtractedSection


SLUG_RE = re.compile(r"[^a-z0-9]+")
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore\s+(?:all\s+)?previous\s+instructions"),
    re.compile(r"(?i)system\s+prompt\s*:"),
    re.compile(r"(?i)you\s+are\s+now\s+an?\s+"),
]


def compute_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_slug(text: str) -> str:
    s = SLUG_RE.sub("-", text.lower()).strip("-")
    return s[:64] if s else "section"


def make_stable_document_id(technology: str, version: str, source_id: str, topic: str, doc_slug: str) -> str:
    v_slug = make_slug(version)
    t_slug = make_slug(topic)
    d_slug = make_slug(doc_slug)
    return f"{technology}-{v_slug}-{source_id}-{t_slug}-{d_slug}"


def make_stable_chunk_id(doc_id: str, section_title: str, ordinal: int = 0) -> str:
    sec_slug = make_slug(section_title)
    if ordinal > 0:
        return f"{doc_id}--{sec_slug}-{ordinal}"
    return f"{doc_id}--{sec_slug}"


def sanitize_untrusted_content(text: str) -> str:
    """Ensure external documentation is treated strictly as passive technical data."""
    cleaned = text.replace("\x00", "")
    for pat in PROMPT_INJECTION_PATTERNS:
        cleaned = pat.sub("[redacted-untrusted-directive]", cleaned)
    return cleaned.strip()


class DocumentNormalizer:
    """Normalizes extracted sections into validated DocumentEntity and KnowledgeChunk objects."""

    def build_document_and_chunks(
        self,
        source_id: str,
        technology: str,
        version: str,
        topic: str,
        doc_title: str,
        doc_slug: str,
        source_url: str,
        authority: str,
        raw_markdown: str,
        sections: List[ExtractedSection],
        default_related_concepts: Optional[List[str]] = None,
        captured_at: Optional[str] = None,
    ) -> Tuple[DocumentEntity, List[KnowledgeChunk]]:
        ts = captured_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        clean_full = sanitize_untrusted_content(raw_markdown)
        doc_hash = compute_sha256(clean_full)
        doc_id = make_stable_document_id(technology, version, source_id, topic, doc_slug)
        safe_fname = sanitize_filename(f"{doc_id}.md")
        rel_local_path = f"documents/{technology}/{safe_fname}"

        doc_entity = DocumentEntity(
            id=doc_id,
            source_id=source_id,
            technology=technology,
            version=version,
            topic=topic,
            title=doc_title,
            source_url=source_url,
            local_path=rel_local_path,
            authority=authority,
            current_hash=doc_hash,
            captured_at=ts,
            updated_at=ts,
            status="active",
        )

        chunks: List[KnowledgeChunk] = []
        seen_chunk_ids: dict[str, int] = {}

        for idx, sec in enumerate(sections):
            clean_sec = sanitize_untrusted_content(sec.content)
            if len(clean_sec) < 15:
                continue
            base_cid = make_stable_chunk_id(doc_id, sec.title, 0)
            count = seen_chunk_ids.get(base_cid, 0)
            seen_chunk_ids[base_cid] = count + 1
            chunk_id = make_stable_chunk_id(doc_id, sec.title, count)

            rel_concepts = list(
                dict.fromkeys((sec.related_concepts or []) + (default_related_concepts or []))
            )
            sec_url = f"{source_url}#{sec.anchor}" if sec.anchor and "#" not in source_url else source_url
            c_hash = compute_sha256(clean_sec)

            chunks.append(
                KnowledgeChunk(
                    id=chunk_id,
                    document_id=doc_id,
                    technology=technology,
                    version=version,
                    topic=topic,
                    subtopic=sec.subtopic or topic,
                    title=sec.title,
                    content=clean_sec,
                    authority=authority,
                    source_id=source_id,
                    source_url=sec_url,
                    source_section=sec.source_section,
                    related_concepts=rel_concepts,
                    captured_at=ts,
                    content_hash=c_hash,
                    section_order=idx,
                )
            )

        return (doc_entity, chunks)
