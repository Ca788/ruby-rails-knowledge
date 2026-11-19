"""Typed domain entities and strict metadata validation."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


VALID_TECHNOLOGIES = {"ruby", "rails", "ecosystem", "security"}
VALID_AUTHORITIES = {
    "official",
    "official_edge",
    "ecosystem_official",
    "community_standard",
    "security_standard",
}
VALID_RELATION_TYPES = {
    "RELATED_TO",
    "PART_OF",
    "ALTERNATIVE_TO",
    "DEPENDS_ON",
    "INTRODUCED_IN",
    "DEPRECATED_IN",
    "REPLACED_BY",
    "DOCUMENTED_IN",
}
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
ISO8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


@dataclass
class SourceConfig:
    id: str
    technology: str
    authority: str
    source_type: str
    base_url: str
    versioned: bool = True
    enabled: bool = True
    supported_versions: List[str] = field(default_factory=list)
    url_template: Optional[str] = None
    description: str = ""

    def validate(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("Source id cannot be empty")
        if self.technology not in VALID_TECHNOLOGIES:
            raise ValueError(f"Invalid technology '{self.technology}' for source '{self.id}'")
        if self.authority not in VALID_AUTHORITIES:
            raise ValueError(f"Invalid authority '{self.authority}' for source '{self.id}'")
        if not self.base_url.startswith("https://"):
            raise ValueError(f"Source '{self.id}' base_url must use HTTPS: {self.base_url}")


@dataclass
class VersionInfo:
    technology: str
    version: str
    status: str  # 'eol', 'security_maintenance', 'maintenance', 'stable', 'current_stable', 'edge', 'unavailable'
    docs_available: bool = True
    is_latest_stable: bool = False
    release_date: Optional[str] = None
    eol_date: Optional[str] = None
    docs_url: Optional[str] = None
    notes: str = ""

    @property
    def id(self) -> str:
        return f"{self.technology}:{self.version}"


@dataclass
class DocumentEntity:
    id: str
    source_id: str
    technology: str
    version: str
    topic: str
    title: str
    source_url: str
    local_path: str
    authority: str
    current_hash: str
    captured_at: str
    updated_at: str
    status: str = "active"


@dataclass
class KnowledgeChunk:
    id: str
    document_id: str
    technology: str
    version: str
    topic: str
    subtopic: str
    title: str
    content: str
    authority: str
    source_id: str
    source_url: str
    source_section: str
    related_concepts: List[str]
    captured_at: str
    content_hash: str
    normalized_identifiers: str = ""
    identifiers: List[str] = field(default_factory=list)
    section_order: int = 0

    @property
    def char_count(self) -> int:
        return len(self.content)

    @property
    def estimated_tokens(self) -> int:
        # Rough deterministic token approximation (~4 chars per token)
        return max(1, (len(self.content) + 3) // 4)

    def to_metadata_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "technology": self.technology,
            "version": self.version,
            "topic": self.topic,
            "subtopic": self.subtopic,
            "title": self.title,
            "content": self.content,
            "authority": self.authority,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "source_section": self.source_section,
            "related_concepts": list(self.related_concepts),
            "captured_at": self.captured_at,
            "content_hash": self.content_hash,
        }


def validate_chunk_metadata(chunk: KnowledgeChunk) -> None:
    """Validate mandatory chunk metadata fields and types."""
    data = chunk.to_metadata_dict()
    required_str_fields = [
        "id",
        "technology",
        "version",
        "topic",
        "subtopic",
        "title",
        "content",
        "authority",
        "source_id",
        "source_url",
        "source_section",
        "captured_at",
        "content_hash",
    ]
    for f in required_str_fields:
        val = data.get(f)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"Chunk metadata missing or invalid required string field: {f}")

    if chunk.technology not in VALID_TECHNOLOGIES:
        raise ValueError(f"Invalid chunk technology: {chunk.technology}")
    if chunk.authority not in VALID_AUTHORITIES:
        raise ValueError(f"Invalid chunk authority: {chunk.authority}")
    if not chunk.source_url.startswith("https://"):
        raise ValueError(f"Chunk source_url must use HTTPS: {chunk.source_url}")
    if not SHA256_RE.match(chunk.content_hash):
        raise ValueError(f"Invalid SHA-256 content_hash: {chunk.content_hash}")
    if not ISO8601_RE.match(chunk.captured_at):
        raise ValueError(f"Invalid ISO-8601 captured_at timestamp: {chunk.captured_at}")
    if not isinstance(chunk.related_concepts, list):
        raise ValueError("related_concepts must be a list of strings")


@dataclass
class ConceptEntity:
    id: str
    name: str
    technology: str
    category: str
    description: str = ""


@dataclass
class RelationshipEntity:
    id: str
    source_concept_id: str
    target_concept_id: str
    relation_type: str
    technology: str
    version_scope: str = "all"
    evidence_chunk_id: Optional[str] = None
    source_url: str = ""
    notes: str = ""

    def validate(self) -> None:
        if self.relation_type not in VALID_RELATION_TYPES:
            raise ValueError(f"Invalid relationship type: {self.relation_type}")
        if not self.source_url.startswith("https://"):
            raise ValueError(f"Relationship must cite an HTTPS source_url: {self.source_url}")


@dataclass
class SearchResultItem:
    id: str
    title: str
    technology: str
    version: str
    version_status: str
    topic: str
    subtopic: str
    content: str
    source_id: str
    source_url: str
    source_section: str
    authority: str
    related_concepts: List[str]
    score: float
    graph_relations: List[Dict[str, Any]] = field(default_factory=list)
    captured_at: str = ""
    content_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "technology": self.technology,
            "version": self.version,
            "version_status": self.version_status,
            "topic": self.topic,
            "subtopic": self.subtopic,
            "content": self.content,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "source_section": self.source_section,
            "authority": self.authority,
            "related_concepts": self.related_concepts,
            "graph_relations": self.graph_relations,
            "score": round(self.score, 4),
        }


@dataclass
class ProjectContext:
    ruby_version: Optional[str] = None
    ruby_version_source: Optional[str] = None
    rails_version: Optional[str] = None
    rails_major_minor: Optional[str] = None
    rails_version_source: Optional[str] = None
    database: Optional[str] = None
    orm: Optional[str] = None
    test_framework: Optional[str] = None
    background_jobs: List[str] = field(default_factory=list)
    relevant_dependencies: Dict[str, str] = field(default_factory=dict)
    detected_files: List[str] = field(default_factory=list)
    version_conflicts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IngestionRunSummary:
    id: str
    run_type: str
    started_at: str
    completed_at: str
    status: str
    source_filter: Optional[str] = None
    version_filter: Optional[str] = None
    docs_checked: int = 0
    docs_added: int = 0
    docs_updated: int = 0
    docs_unchanged: int = 0
    docs_failed: int = 0
    chunks_indexed: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
