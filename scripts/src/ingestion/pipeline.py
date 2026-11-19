"""End-to-end ingestion and incremental update pipeline."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import uuid

from ..config import AppConfig
from ..models.entities import (
    ConceptEntity,
    IngestionRunSummary,
    RelationshipEntity,
)
from ..storage.database import DatabaseManager
from ..storage.repositories import KnowledgeRepository
from .corpus import get_all_corpus_documents, get_curated_concepts_and_relationships
from .discovery import SourceCatalog
from .fetcher import DocumentFetcher, SecurityViolationError
from .normalizer import DocumentNormalizer
from .parser import SemanticDocumentParser


class IngestionPipeline:
    """Orchestrates document discovery, fetching, parsing, normalization, storage, and incremental updates."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        fetcher: Optional[DocumentFetcher] = None,
    ):
        self.config = config or AppConfig()
        self.db = DatabaseManager(self.config)
        self.repo = KnowledgeRepository(self.db)
        self.catalog = SourceCatalog(self.config.sources_config_path)
        self.fetcher = fetcher or DocumentFetcher(
            allowed_domains=self.catalog.allowed_domains(),
            limits=self.config.security_limits,
        )
        self.parser = SemanticDocumentParser()
        self.normalizer = DocumentNormalizer()

    def bootstrap_catalog(self) -> None:
        """Ensure database schema is migrated and sources + version matrix are persisted."""
        self.db.initialize()
        self.repo.upsert_sources(list(self.catalog.sources.values()))
        self.repo.upsert_versions(self.catalog.versions)

    def run_ingestion(
        self,
        source_filter: Optional[str] = None,
        version_filter: Optional[str] = None,
        run_type: str = "ingest",
        custom_documents: Optional[List[Dict[str, Any]]] = None,
        live_urls: Optional[List[Dict[str, str]]] = None,
        force_reprocess: bool = False,
    ) -> IngestionRunSummary:
        """Execute an idempotent ingestion or incremental update run."""
        self.bootstrap_catalog()
        run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"
        started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if source_filter and source_filter not in self.catalog.sources:
            raise ValueError(f"Unknown source_id '{source_filter}'. Run 'sources list' to see registered sources.")

        norm_ver_filter: Optional[str] = None
        if version_filter:
            tech = self.catalog.sources[source_filter].technology if source_filter else "rails"
            norm_ver_filter = self.catalog.normalize_version_string(tech, version_filter)

        corpus_docs = custom_documents if custom_documents is not None else get_all_corpus_documents()

        # Filter documents by source_id and version
        selected_docs: List[Dict[str, Any]] = []
        for entry in corpus_docs:
            if source_filter and entry["source_id"] != source_filter:
                continue
            if norm_ver_filter and entry["version"] != norm_ver_filter and entry["version"] != version_filter:
                continue
            selected_docs.append(entry)

        # If live URLs are explicitly provided, fetch them through the secure fetcher
        errors: List[str] = []
        docs_checked = 0
        docs_added = 0
        docs_updated = 0
        docs_unchanged = 0
        docs_failed = 0
        chunks_indexed = 0

        if live_urls:
            for item in live_urls:
                docs_checked += 1
                url = item["url"]
                src_id = item.get("source_id", source_filter or "rails_guides")
                try:
                    if src_id not in self.catalog.sources:
                        raise ValueError(f"Unregistered source_id: {src_id}")
                    src_cfg = self.catalog.sources[src_id]
                    raw_text, final_url = self.fetcher.fetch_url(url)
                    selected_docs.append({
                        "source_id": src_id,
                        "technology": item.get("technology", src_cfg.technology),
                        "version": item.get("version", norm_ver_filter or "current"),
                        "topic": item.get("topic", "general"),
                        "doc_slug": item.get("doc_slug", "live_fetched_doc"),
                        "title": item.get("title", f"Fetched Document ({final_url})"),
                        "source_url": final_url,
                        "authority": src_cfg.authority,
                        "related_concepts": item.get("related_concepts", []),
                        "markdown": raw_text,
                        "_already_counted_check": True,
                    })
                except Exception as exc:
                    docs_failed += 1
                    errors.append(f"Failed fetching {url}: {exc}")

        graph_data = get_curated_concepts_and_relationships()
        curated_concepts = [
            ConceptEntity(
                id=c["id"],
                name=c["name"],
                technology=c["technology"],
                category=c["category"],
                description=c.get("description", ""),
            )
            for c in graph_data["concepts"]
        ]
        curated_relationships = [
            RelationshipEntity(
                id=f"rel-{r['source']}-{r['type']}-{r['target']}-{r['scope']}",
                source_concept_id=r["source"],
                target_concept_id=r["target"],
                relation_type=r["type"],
                technology=r["tech"],
                version_scope=r["scope"],
                source_url=r["url"],
                notes=r.get("notes", ""),
            )
            for r in graph_data["relationships"]
        ]

        graph_seeded = False
        for entry in selected_docs:
            if not entry.get("_already_counted_check"):
                docs_checked += 1
            try:
                src_id = entry["source_id"]
                if src_id not in self.catalog.sources:
                    raise ValueError(f"Source '{src_id}' is not registered in sources.yml")
                src_cfg = self.catalog.sources[src_id]
                if not src_cfg.enabled:
                    continue

                # Validate URL security on every document entry
                from .fetcher import validate_url_security
                validate_url_security(
                    entry["source_url"],
                    allowed_domains=self.catalog.allowed_domains(),
                    require_https=True,
                    resolve_dns=False,
                )

                sections = self.parser.parse_to_sections(
                    raw_content=entry["markdown"],
                    doc_title=entry["title"],
                    default_subtopic=entry["topic"],
                )
                if not sections:
                    raise ValueError(f"Document '{entry['title']}' produced 0 valid sections")

                doc_entity, chunks = self.normalizer.build_document_and_chunks(
                    source_id=src_id,
                    technology=entry["technology"],
                    version=str(entry["version"]),
                    topic=entry["topic"],
                    doc_title=entry["title"],
                    doc_slug=entry["doc_slug"],
                    source_url=entry["source_url"],
                    authority=entry.get("authority", src_cfg.authority),
                    raw_markdown=entry["markdown"],
                    sections=sections,
                    default_related_concepts=entry.get("related_concepts", []),
                    captured_at=entry.get("captured_at"),
                )

                change_type, num_chunks = self.repo.persist_document_and_chunks(
                    doc=doc_entity,
                    chunks=chunks,
                    concepts=curated_concepts if not graph_seeded else [],
                    relationships=curated_relationships if not graph_seeded else [],
                    force_reprocess=force_reprocess,
                )
                graph_seeded = True

                # Persist normalized markdown file on disk when created or updated
                if change_type in ("created", "updated"):
                    disk_path = self.config.data_dir / doc_entity.local_path
                    disk_path.parent.mkdir(parents=True, exist_ok=True)
                    disk_path.write_text(entry["markdown"].strip() + "\n", encoding="utf-8")

                if change_type == "created":
                    docs_added += 1
                    chunks_indexed += num_chunks
                elif change_type == "updated":
                    docs_updated += 1
                    chunks_indexed += num_chunks
                else:
                    docs_unchanged += 1
            except Exception as exc:
                docs_failed += 1
                errors.append(f"Error processing document '{entry.get('title', 'unknown')}': {exc}")

        completed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if docs_failed == 0:
            status = "completed"
        elif docs_added > 0 or docs_updated > 0 or docs_unchanged > 0:
            status = "partial_failure"
        else:
            status = "failed"

        summary = IngestionRunSummary(
            id=run_id,
            run_type=run_type,
            started_at=started_at,
            completed_at=completed_at,
            status=status,
            source_filter=source_filter,
            version_filter=norm_ver_filter or version_filter,
            docs_checked=docs_checked,
            docs_added=docs_added,
            docs_updated=docs_updated,
            docs_unchanged=docs_unchanged,
            docs_failed=docs_failed,
            chunks_indexed=chunks_indexed,
            errors=errors,
        )
        self.repo.record_ingestion_run(summary)
        return summary
