"""Deterministic CLI interface for agents and developers."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import AppConfig, RetrievalLimits, SKILL_VERSION
from ..context.project_detector import ProjectContextDetector
from ..ingestion.discovery import SourceCatalog
from ..ingestion.pipeline import IngestionPipeline
from ..retrieval.graph_expansion import KnowledgeGraphExpander
from ..retrieval.lexical_search import RetrievalEngine
from ..storage.database import DatabaseManager
from ..storage.repositories import KnowledgeRepository


def _emit(payload: Dict[str, Any], fmt: str, markdown_renderer=None) -> None:
    if fmt == "markdown" and markdown_renderer is not None:
        sys.stdout.write(markdown_renderer(payload).rstrip() + "\n")
    else:
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _render_doctor_md(data: Dict[str, Any]) -> str:
    status_str = "HEALTHY" if data.get("healthy") else "UNHEALTHY"
    lines = [
        f"# ruby-rails-knowledge Doctor ({status_str})",
        "",
        f"- **Database Exists**: {data.get('db_exists')}",
        f"- **FTS5 Enabled**: {data.get('fts5_enabled')}",
        f"- **Schema Version**: {data.get('schema_version')}",
        f"- **Integrity Check**: {data.get('integrity_check')}",
        f"- **Foreign Key Violations**: {data.get('foreign_key_violations', 0)}",
        f"- **Registered Sources**: {data.get('registered_sources', 0)}",
        f"- **Indexed Chunks**: {data.get('knowledge_chunks', 0)}",
    ]
    return "\n".join(lines)


def _render_status_md(data: Dict[str, Any]) -> str:
    lines = [
        "# Knowledge Base Status",
        "",
        f"- **Sources**: {data['sources']}",
        f"- **Versions**: {data['versions']}",
        f"- **Documents**: {data['documents']} (Revisions: {data['document_revisions']})",
        f"- **Knowledge Chunks**: {data['knowledge_chunks']}",
        f"- **Indexed Technical Identifiers**: {data['indexed_identifiers']}",
        f"- **Knowledge Graph Concepts**: {data['concepts']} (Relationships: {data['relationships']})",
        f"- **Ingestion Runs**: {data['ingestion_runs']}",
        "",
        "## Coverage by Technology & Version",
        "| Technology | Version | Chunks |",
        "| --- | --- | --- |",
    ]
    for cov in data.get("coverage_by_version", []):
        lines.append(f"| {cov['technology']} | {cov['version']} | {cov['chunks']} |")
    return "\n".join(lines)


def _render_sources_md(data: Dict[str, Any]) -> str:
    lines = [
        "# Registered Knowledge Sources",
        "",
        "| ID | Technology | Authority | Type | Versioned | Docs | Chunks | Base URL |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s in data.get("sources", []):
        v_flag = "yes" if s.get("versioned") else "no"
        lines.append(
            f"| {s['id']} | {s['technology']} | {s['authority']} | {s['source_type']} | "
            f"{v_flag} | {s.get('document_count', 0)} | {s.get('chunk_count', 0)} | {s['base_url']} |"
        )
    return "\n".join(lines)


def _render_versions_md(data: Dict[str, Any]) -> str:
    lines = [
        "# Technology Version Matrix",
        "",
        "| Technology | Version | Lifecycle Status | Docs Available | Latest Stable | Docs | Chunks | Official URL |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for v in data.get("versions", []):
        avail = "yes" if v.get("docs_available") else "no"
        latest = "yes" if v.get("is_latest_stable") else "no"
        lines.append(
            f"| {v['technology']} | {v['version']} | {v['status']} | {avail} | {latest} | "
            f"{v.get('document_count', 0)} | {v.get('chunk_count', 0)} | {v.get('docs_url') or '-'} |"
        )
    return "\n".join(lines)


def _render_search_md(data: Dict[str, Any]) -> str:
    meta = data["metadata"]
    lines = [
        f"# Search Results for: {data['query']}",
        "",
        f"- **Total Results**: {meta['total_results']} | **Method**: {meta['retrieval_method']} | **Elapsed**: {meta['elapsed_ms']} ms",
        f"- **Estimated Tokens**: {meta.get('estimated_tokens', 0)} (vs {meta.get('full_docs_tokens', 0)} full-doc tokens; **{meta.get('token_savings_pct', 0)}% context saved**)",
    ]
    if meta.get("version_notice"):
        lines.append(f"\n> **Version Notice**: {meta['version_notice']}")
    lines.append("")

    if not data["results"]:
        lines.append("_No matching technical knowledge chunks found._")
        return "\n".join(lines)

    for idx, r in enumerate(data["results"], start=1):
        lines.append(f"## {idx}. {r['title']} [{r['technology']} {r['version']} | {r['authority']}]")
        lines.append(f"- **Section**: {r['source_section']}")
        lines.append(f"- **Source URL**: {r['source_url']}")
        if r.get("related_concepts"):
            lines.append(f"- **Related Concepts**: {', '.join(r['related_concepts'])}")
        if r.get("graph_relations"):
            rel_strs = [f"{g['source']} --[{g['relation_type']}]--> {g['target']}" for g in r["graph_relations"][:4]]
            lines.append(f"- **Graph Edges**: {'; '.join(rel_strs)}")
        lines.append("")
        lines.append(r["content"])
        lines.append("")
    return "\n".join(lines)


def _render_graph_md(data: Dict[str, Any]) -> str:
    lines = [
        f"# Knowledge Graph: {data['query_concept']}",
        "",
    ]
    if not data.get("found"):
        lines.append("_Concept not found in Knowledge Graph._")
        return "\n".join(lines)

    lines.append("## Relationships")
    for e in data.get("edges", []):
        lines.append(
            f"- **{e['source']}** --[{e['relation_type']}]--> **{e['target']}** "
            f"(scope: {e['version_scope']}) — {e.get('notes', '')} [{e['source_url']}]"
        )
    return "\n".join(lines)


def _render_context_md(data: Dict[str, Any]) -> str:
    lines = [
        "# Detected Project Context",
        "",
        f"- **Ruby Version**: {data.get('ruby_version') or 'not detected'} (source: {data.get('ruby_version_source') or '-'})",
        f"- **Rails Version**: {data.get('rails_version') or 'not detected'} (major.minor: {data.get('rails_major_minor') or '-'}, source: {data.get('rails_version_source') or '-'})",
        f"- **Database**: {data.get('database') or 'not detected'}",
        f"- **ORM**: {data.get('orm') or 'not detected'}",
        f"- **Test Framework**: {data.get('test_framework') or 'not detected'}",
        f"- **Background Jobs**: {', '.join(data.get('background_jobs') or []) or 'none'}",
        f"- **Detected Files**: {', '.join(data.get('detected_files') or []) or 'none'}",
    ]
    if data.get("version_conflicts"):
        lines.append("\n## Version Conflicts")
        for c in data["version_conflicts"]:
            lines.append(f"- {c}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ruby-rails-knowledge",
        description="Local, version-aware Ruby & Ruby on Rails technical knowledge base and retrieval CLI.",
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {SKILL_VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    # doctor
    p_doc = sub.add_parser("doctor", help="Verify database health, FTS5 availability, schema migrations, and sources.")
    p_doc.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format (default: json).")

    # status
    p_stat = sub.add_parser("status", help="Show knowledge base statistics and version coverage.")
    p_stat.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format (default: json).")

    # sources
    p_src = sub.add_parser("sources", help="Inspect registered official and ecosystem documentation sources.")
    p_src.add_argument("action", nargs="?", default="list", choices=["list"], help="Action to run (default: list).")
    p_src.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format (default: json).")

    # versions
    p_ver = sub.add_parser("versions", help="List supported Ruby and Rails versions and lifecycle status.")
    p_ver.add_argument("action", nargs="?", default="list", choices=["list"], help="Action to run (default: list).")
    p_ver.add_argument("--technology", choices=["ruby", "rails", "ecosystem", "security"], help="Filter by technology.")
    p_ver.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format (default: json).")

    # ingest
    p_ing = sub.add_parser("ingest", help="Ingest official documentation into the SQLite + FTS5 knowledge base.")
    p_ing.add_argument("--source", help="Filter ingestion by registered source ID (e.g. rails_guides, ruby_api).")
    p_ing.add_argument("--version", help="Filter ingestion by version (e.g. 6.1, 7.2, 8.0, 3.3).")
    p_ing.add_argument("--url", help="Optional live HTTPS URL from an allowed official domain to fetch and ingest.")
    p_ing.add_argument("--force", action="store_true", help="Force reprocessing even if content hash matches.")
    p_ing.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format (default: json).")

    # update
    p_upd = sub.add_parser("update", help="Incrementally update knowledge base while preserving historical revisions.")
    p_upd.add_argument("--source", help="Optional source ID filter.")
    p_upd.add_argument("--version", help="Optional version filter.")
    p_upd.add_argument("--url", help="Optional live HTTPS URL from an allowed official domain to check for updates.")
    p_upd.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format (default: json).")

    # search
    p_srch = sub.add_parser("search", help="Search technical knowledge using hybrid FTS5, identifier index, and graph.")
    p_srch.add_argument("query", help="Technical query, concept, Ruby method, class, or phrase.")
    p_srch.add_argument("--technology", choices=["ruby", "rails", "ecosystem", "security"], help="Filter by technology.")
    p_srch.add_argument("--version", help="Filter by technology version (e.g. 6.1, 7.2, 8.0, 3.3, edge).")
    p_srch.add_argument("--authority", choices=["official", "official_edge", "ecosystem_official", "community_standard", "security_standard"], help="Filter by source authority.")
    p_srch.add_argument("--topic", help="Filter by topic/category (e.g. active_record, callbacks, queries, enumerable).")
    p_srch.add_argument("--project", help="Automatically detect Ruby/Rails version from consumer project path.")
    p_srch.add_argument("--limit", type=int, default=5, help="Maximum number of chunks to return (default: 5).")
    p_srch.add_argument("--max-chars", type=int, default=2400, help="Maximum characters per chunk (default: 2400).")
    p_srch.add_argument("--max-tokens", type=int, default=1800, help="Maximum total estimated tokens (default: 1800).")
    p_srch.add_argument("--no-graph", action="store_true", help="Disable Knowledge Graph relationship expansion.")
    p_srch.add_argument("--graph-depth", type=int, default=2, help="Knowledge Graph expansion depth (default: 2).")
    p_srch.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format (default: json).")

    # graph
    p_grp = sub.add_parser("graph", help="Explore technical concept relationships in the Knowledge Graph.")
    p_grp.add_argument("concept", help="Concept identifier (e.g. after_commit, active_record_callbacks, includes).")
    p_grp.add_argument("--technology", choices=["ruby", "rails", "ecosystem", "security"], help="Filter by technology.")
    p_grp.add_argument("--depth", type=int, default=2, help="Maximum traversal depth (default: 2).")
    p_grp.add_argument("--max-related", type=int, default=8, help="Maximum related concepts to expand (default: 8).")
    p_grp.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format (default: json).")

    # context
    p_ctx = sub.add_parser("context", help="Detect Ruby, Rails, database, test framework, and job context of a project.")
    p_ctx.add_argument("action", nargs="?", default="detect", choices=["detect"], help="Action to run (default: detect).")
    p_ctx.add_argument("--project", default=".", help="Path to consumer Ruby/Rails project directory (default: .).")
    p_ctx.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format (default: json).")

    # backup
    p_bak = sub.add_parser("backup", help="Create a consistent SQLite database backup.")
    p_bak.add_argument("--label", default="manual", help="Backup label (default: manual).")
    p_bak.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format (default: json).")

    # migrate
    p_mig = sub.add_parser("migrate", help="Apply pending SQLite database schema migrations.")
    p_mig.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format (default: json).")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = AppConfig()

    try:
        if args.command == "doctor":
            db = DatabaseManager(cfg)
            health = db.check_health()
            cat = SourceCatalog(cfg.sources_config_path)
            health["skill_version"] = SKILL_VERSION
            health["registered_sources"] = len(cat.sources)
            if health["db_exists"] and health["healthy"]:
                repo = KnowledgeRepository(db)
                stats = repo.get_stats()
                health["knowledge_chunks"] = stats["knowledge_chunks"]
                health["documents"] = stats["documents"]
            else:
                health["knowledge_chunks"] = 0
                health["documents"] = 0
            _emit(health, args.format, _render_doctor_md)
            return 0 if health["healthy"] else 1

        if args.command == "status":
            db = DatabaseManager(cfg)
            repo = KnowledgeRepository(db)
            stats = repo.get_stats()
            stats["skill_version"] = SKILL_VERSION
            _emit(stats, args.format, _render_status_md)
            return 0

        if args.command == "sources":
            db = DatabaseManager(cfg)
            repo = KnowledgeRepository(db)
            sources = repo.list_sources()
            _emit({"sources": sources, "total": len(sources)}, args.format, _render_sources_md)
            return 0

        if args.command == "versions":
            db = DatabaseManager(cfg)
            repo = KnowledgeRepository(db)
            versions = repo.list_versions(technology=args.technology)
            _emit({"versions": versions, "total": len(versions)}, args.format, _render_versions_md)
            return 0

        if args.command in ("ingest", "update"):
            pipeline = IngestionPipeline(cfg)
            live_urls = [{"url": args.url, "source_id": args.source or "rails_guides", "version": args.version or "current"}] if args.url else None
            run_type = "ingest" if args.command == "ingest" else "update"
            force = getattr(args, "force", False)
            summary = pipeline.run_ingestion(
                source_filter=args.source,
                version_filter=args.version,
                run_type=run_type,
                live_urls=live_urls,
                force_reprocess=force,
            )
            payload = summary.to_dict()
            _emit(payload, args.format)
            return 0 if summary.status in ("completed", "partial_failure") else 1

        if args.command == "search":
            cfg.retrieval_limits = RetrievalLimits(
                max_results=max(1, args.limit),
                max_related_concepts=8,
                max_graph_depth=max(1, args.graph_depth),
                max_content_chars=max(200, args.max_chars),
                max_estimated_tokens=max(100, args.max_tokens),
            )
            tech = args.technology
            ver = args.version
            if args.project and not ver:
                ctx = ProjectContextDetector().detect(Path(args.project))
                if tech == "ruby" and ctx.ruby_version:
                    ver = ".".join(ctx.ruby_version.split(".")[:2])
                elif (tech in (None, "rails")) and ctx.rails_major_minor:
                    tech = tech or "rails"
                    ver = ctx.rails_major_minor
                elif ctx.ruby_version and not tech:
                    tech = "ruby"
                    ver = ".".join(ctx.ruby_version.split(".")[:2])

            engine = RetrievalEngine(cfg)
            res = engine.search(
                query=args.query,
                technology=tech,
                version=ver,
                authority=args.authority,
                topic=args.topic,
                limit=args.limit,
                expand_graph=not args.no_graph,
                graph_depth=args.graph_depth,
            )
            _emit(res, args.format, _render_search_md)
            return 0

        if args.command == "graph":
            db = DatabaseManager(cfg)
            expander = KnowledgeGraphExpander(db)
            res = expander.traverse(
                concept_query=args.concept,
                technology=args.technology,
                max_depth=args.depth,
                max_related=args.max_related,
            )
            _emit(res, args.format, _render_graph_md)
            return 0

        if args.command == "context":
            detector = ProjectContextDetector()
            ctx = detector.detect(Path(args.project))
            _emit(ctx.to_dict(), args.format, _render_context_md)
            return 0

        if args.command == "backup":
            db = DatabaseManager(cfg)
            bpath = db.backup_database(label=args.label)
            payload = {
                "status": "completed" if bpath else "skipped",
                "backup_filename": bpath.name if bpath else None,
            }
            _emit(payload, args.format)
            return 0

        if args.command == "migrate":
            db = DatabaseManager(cfg)
            db.backup_database(label="pre-migrate")
            res = db.initialize()
            _emit(res, args.format)
            return 0

        return 2
    except Exception as exc:
        err_payload = {
            "error": type(exc).__name__,
            "message": str(exc),
        }
        sys.stderr.write(json.dumps(err_payload) + "\n")
        return 1
