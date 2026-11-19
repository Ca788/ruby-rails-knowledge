#!/usr/bin/env python3
"""Comprehensive Automated Test Suite for ruby-rails-knowledge (Section 16)."""
from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from src.cli.commands import main as cli_main
from src.config import AppConfig, RetrievalLimits, SecurityLimits
from src.context.project_detector import ProjectContextDetector
from src.ingestion.corpus import get_all_corpus_documents
from src.ingestion.discovery import SourceCatalog
from src.ingestion.fetcher import (
    DocumentFetcher,
    SecurityViolationError,
    sanitize_filename,
    validate_url_security,
)
from src.ingestion.normalizer import DocumentNormalizer, compute_sha256
from src.ingestion.parser import SemanticDocumentParser
from src.ingestion.pipeline import IngestionPipeline
from src.models.entities import (
    ConceptEntity,
    KnowledgeChunk,
    RelationshipEntity,
    SourceConfig,
    validate_chunk_metadata,
)
from src.retrieval.graph_expansion import KnowledgeGraphExpander
from src.retrieval.lexical_search import RetrievalEngine
from src.storage.database import DatabaseManager
from src.storage.fts import build_fts5_match_expression, extract_technical_identifiers
from src.storage.repositories import KnowledgeRepository


def make_test_config(tmp_dir: Path) -> AppConfig:
    skill_root = SCRIPT_DIR.parent
    return AppConfig(
        skill_root=skill_root,
        data_dir=tmp_dir / "data",
        cache_dir=tmp_dir / "cache",
    )


class Test1IngestionAndSecurity(unittest.TestCase):
    """Tests for Ingestion: Download security, Parsing, Normalization, Deduplication, Hash, Versioning, Incremental Update, Source Failure."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = make_test_config(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_url_security_and_ssrf_protection(self):
        allowed = ["guides.rubyonrails.org", "docs.ruby-lang.org"]
        # Valid official HTTPS URL
        self.assertEqual(
            validate_url_security("https://guides.rubyonrails.org/v6.1/active_record_callbacks.html", allowed),
            "https://guides.rubyonrails.org/v6.1/active_record_callbacks.html",
        )
        # Block HTTP
        with self.assertRaises(SecurityViolationError):
            validate_url_security("http://guides.rubyonrails.org/v6.1/index.html", allowed)
        # Block loopback & private IPs (SSRF)
        for bad_url in [
            "https://127.0.0.1/admin",
            "https://localhost/secret",
            "https://169.254.169.254/latest/meta-data/",
            "https://10.0.0.1/internal",
            "https://192.168.1.1/config",
            "https://[::1]/loopback",
            "https://evil.example.com/exploit",
            "https://user:pass@guides.rubyonrails.org/v6.1/",
        ]:
            with self.assertRaises(SecurityViolationError, msg=f"Failed to block {bad_url}"):
                validate_url_security(bad_url, allowed)

    def test_filename_sanitization(self):
        self.assertEqual(sanitize_filename("../../etc/passwd\x00"), "etc_passwd")
        self.assertEqual(sanitize_filename("..."), "document")

    def test_malformed_html_and_semantic_parsing(self):
        parser = SemanticDocumentParser()
        malformed_html = """
        <html><body>
        <script>alert("xss")</script>
        <h1>Active Record Callbacks</h1>
        <p>Intro paragraph about lifecycle.
        <h2>Transaction Callbacks</h2>
        <p>Use <code>after_commit</code> and <code>after_rollback</code> for external jobs.
        <pre><code>after_commit :notify_user, on: :create</code></pre>
        <table><tr><th>Hook</th><th>Timing</th></tr><tr><td>after_save</td><td>Inside TX</td></tr></table>
        <div class="warning">DEPRECATED: Do not return false to halt callbacks.</div>
        """
        sections = parser.parse_to_sections(malformed_html, "Callbacks Guide", content_format="html")
        self.assertGreaterEqual(len(sections), 2)
        combined = "\n".join(s.content for s in sections)
        self.assertNotIn("alert", combined)
        self.assertIn("`after_commit`", combined)
        self.assertIn("```ruby", combined)
        self.assertIn("| Hook | Timing |", combined)

    def test_normalizer_stable_id_and_hash_deduplication(self):
        parser = SemanticDocumentParser()
        normalizer = DocumentNormalizer()
        md = "# Guide\n\n## After Commit\n\nRuns after transaction commit.\n"
        sections = parser.parse_to_sections(md, "Guide")
        doc1, chunks1 = normalizer.build_document_and_chunks(
            source_id="rails_guides",
            technology="rails",
            version="6.1",
            topic="callbacks",
            doc_title="Guide",
            doc_slug="guide",
            source_url="https://guides.rubyonrails.org/v6.1/active_record_callbacks.html",
            authority="official",
            raw_markdown=md,
            sections=sections,
            captured_at="2026-11-19T12:00:00Z",
        )
        doc2, chunks2 = normalizer.build_document_and_chunks(
            source_id="rails_guides",
            technology="rails",
            version="6.1",
            topic="callbacks",
            doc_title="Guide",
            doc_slug="guide",
            source_url="https://guides.rubyonrails.org/v6.1/active_record_callbacks.html",
            authority="official",
            raw_markdown=md,
            sections=sections,
            captured_at="2026-11-19T13:00:00Z",
        )
        self.assertEqual(doc1.id, doc2.id)
        self.assertEqual(doc1.current_hash, doc2.current_hash)
        self.assertEqual(chunks1[0].id, chunks2[0].id)
        self.assertEqual(chunks1[0].content_hash, chunks2[0].content_hash)

    def test_incremental_update_and_fault_isolation(self):
        pipeline = IngestionPipeline(self.cfg)
        sample_docs = get_all_corpus_documents()[:4]
        # 1. Initial ingest
        res1 = pipeline.run_ingestion(custom_documents=sample_docs)
        self.assertEqual(res1.status, "completed")
        self.assertEqual(res1.docs_added, 4)
        self.assertEqual(res1.docs_updated, 0)
        self.assertEqual(res1.docs_unchanged, 0)

        # 2. Idempotent re-run without changes -> all 4 unchanged
        res2 = pipeline.run_ingestion(custom_documents=sample_docs, run_type="update")
        self.assertEqual(res2.docs_added, 0)
        self.assertEqual(res2.docs_updated, 0)
        self.assertEqual(res2.docs_unchanged, 4)

        # 3. Modify 1 document and inject 1 failing document -> 1 updated, 3 unchanged, 1 failed, history preserved
        modified_docs = [dict(d) for d in sample_docs]
        modified_docs[0]["markdown"] = modified_docs[0]["markdown"] + "\n\n## Additional Updated Section\n\nNew technical note on `after_commit` ordering.\n"
        modified_docs.append({
            "source_id": "rails_guides",
            "technology": "rails",
            "version": "6.1",
            "topic": "callbacks",
            "doc_slug": "bad_doc",
            "title": "Bad URL Document",
            "source_url": "http://insecure.example.com/bad",  # Triggers SecurityViolationError
            "authority": "official",
            "markdown": "# Bad\n\n## Section\n\nContent",
        })
        res3 = pipeline.run_ingestion(custom_documents=modified_docs, run_type="update")
        self.assertEqual(res3.status, "partial_failure")
        self.assertEqual(res3.docs_updated, 1)
        self.assertEqual(res3.docs_unchanged, 3)
        self.assertEqual(res3.docs_failed, 1)

        # Verify historical revisions preserved in document_versions
        revs = pipeline.repo.get_document_versions("rails-6-1-rails_guides-active-record-active-record-callbacks")
        self.assertEqual(len(revs), 2)
        self.assertEqual(revs[0]["change_type"], "created")
        self.assertEqual(revs[1]["change_type"], "updated")
        self.assertEqual(revs[1]["previous_hash"], revs[0]["content_hash"])


class Test2StorageAndSchema(unittest.TestCase):
    """Tests for Storage: Referential integrity, Persistence, Migrations, FTS5, Indexes, Relationships."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = make_test_config(Path(self.tmp.name))
        self.pipeline = IngestionPipeline(self.cfg)
        self.pipeline.run_ingestion(custom_documents=get_all_corpus_documents()[:8])

    def tearDown(self):
        self.tmp.cleanup()

    def test_migrations_and_health_check(self):
        health = self.pipeline.db.check_health()
        self.assertTrue(health["healthy"])
        self.assertTrue(health["fts5_enabled"])
        self.assertEqual(health["schema_version"], 1)
        self.assertEqual(health["integrity_check"], "ok")
        self.assertEqual(health["foreign_key_violations"], 0)

    def test_referential_integrity_and_relationship_constraints(self):
        with self.pipeline.db.connect(readonly=False) as conn:
            # Foreign key violation must raise IntegrityError
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO documents (id, source_id, technology, version, topic, title, source_url, local_path, authority, current_hash, captured_at, updated_at) "
                    "VALUES ('d1', 'nonexistent_source', 'rails', '6.1', 't', 'T', 'https://guides.rubyonrails.org/', 'p', 'official', 'h', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
                )
            # Invalid relationship type must raise IntegrityError
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO relationships (id, source_concept_id, target_concept_id, relation_type, technology, version_scope, source_url) "
                    "VALUES ('bad_rel', 'rails:after_commit', 'rails:transactions', 'INVALID_REL', 'rails', 'all', 'https://guides.rubyonrails.org/')"
                )

    def test_backup_creation(self):
        bpath = self.pipeline.db.backup_database(label="unittest")
        self.assertIsNotNone(bpath)
        self.assertTrue(bpath.exists())
        self.assertGreater(bpath.stat().st_size, 1024)


class Test3RetrievalAndKnowledgeGraph(unittest.TestCase):
    """Tests for Retrieval: Exact match, Technical identifiers, Ranking, Version/Tech filters, Graph expansion, Limits, Empty results."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.cfg = make_test_config(Path(cls.tmp.name))
        cls.pipeline = IngestionPipeline(cls.cfg)
        cls.pipeline.run_ingestion()
        cls.engine = RetrievalEngine(cls.cfg)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_technical_identifiers_with_punctuation(self):
        for ident_query, expected_tech, expected_sub in [
            ("after_commit", "rails", "after_commit"),
            ("find_each", "rails", "find_each"),
            ("dependent: :destroy", "rails", "dependent: :destroy"),
            ("strict_loading", "rails", "strict_loading"),
            ("ActiveRecord::Relation", "rails", "ActiveRecord::Relation"),
            ("N+1", "rails", "N+1"),
            ("Enumerable#tally", "ruby", "tally"),
        ]:
            res = self.engine.search(ident_query, limit=3)
            self.assertGreater(len(res["results"]), 0, f"No results for technical identifier {ident_query}")
            top = res["results"][0]
            self.assertEqual(top["technology"], expected_tech)
            self.assertIn(expected_sub.lower(), (top["title"] + " " + top["content"]).lower())

    def test_version_filtering_and_isolation(self):
        res_61 = self.engine.search("after_commit", technology="rails", version="6.1", limit=5)
        self.assertGreater(len(res_61["results"]), 0)
        for r in res_61["results"]:
            self.assertEqual(r["version"], "6.1")
            self.assertEqual(r["version_status"], "eol")
        self.assertIn("End-of-Life", res_61["metadata"]["version_notice"] or "")

        res_72 = self.engine.search("after_all_transactions_commit", technology="rails", version="7.2", limit=3)
        self.assertGreater(len(res_72["results"]), 0)
        for r in res_72["results"]:
            self.assertEqual(r["version"], "7.2")
        self.assertIn("after_all_transactions_commit", res_72["results"][0]["content"])

    def test_unavailable_version_fallback_notice(self):
        # Rails 8.1 does not have dedicated static docs; must fall back to 8.0 with explicit notice
        res_81 = self.engine.search("after_commit", technology="rails", version="8.1", limit=2)
        self.assertEqual(res_81["filters"]["resolved_version"], "8.0")
        self.assertIsNotNone(res_81["metadata"]["version_notice"])
        self.assertIn("not available", res_81["metadata"]["version_notice"])
        self.assertIn("8.0", res_81["metadata"]["version_notice"])

    def test_edge_isolation_by_default(self):
        res_default = self.engine.search("after_commit", technology="rails", limit=10)
        for r in res_default["results"]:
            self.assertNotEqual(r["version"], "edge")

        res_edge = self.engine.search("after_commit", technology="rails", version="edge", limit=2)
        self.assertGreater(len(res_edge["results"]), 0)
        self.assertEqual(res_edge["results"][0]["version"], "edge")
        self.assertEqual(res_edge["results"][0]["authority"], "official_edge")

    def test_knowledge_graph_bounded_expansion(self):
        expander = KnowledgeGraphExpander(self.pipeline.db)
        g_res = expander.traverse("after_commit", technology="rails", max_depth=1, max_related=3)
        self.assertTrue(g_res["found"])
        self.assertLessEqual(len(g_res["related_concepts"]), 3)
        rel_types = {e["relation_type"] for e in g_res["edges"]}
        self.assertIn("RELATED_TO", rel_types)
        self.assertIn("PART_OF", rel_types)

    def test_retrieval_limits_and_empty_results(self):
        cfg_small = make_test_config(Path(self.tmp.name))
        cfg_small.retrieval_limits = RetrievalLimits(
            max_results=2,
            max_related_concepts=2,
            max_graph_depth=1,
            max_content_chars=400,
            max_estimated_tokens=250,
        )
        small_engine = RetrievalEngine(cfg_small)
        res = small_engine.search("after_commit", technology="rails", version="6.1")
        self.assertLessEqual(len(res["results"]), 2)
        for r in res["results"]:
            self.assertLessEqual(len(r["related_concepts"]), 2)
            self.assertLessEqual(len(r["content"]), 460)

        empty_res = self.engine.search("xyznonexistentquantumblockchainfluxcapacitor999")
        self.assertEqual(empty_res["metadata"]["total_results"], 0)
        self.assertEqual(empty_res["results"], [])


class Test4ProjectContextDetector(unittest.TestCase):
    """Tests for Project Context: Ruby version, Rails version, Dependencies, Missing files, Version conflicts."""

    def test_rails_61_project_context_detection(self):
        detector = ProjectContextDetector()
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / ".ruby-version").write_text("3.3.5\n", encoding="utf-8")
            (p / "Gemfile").write_text(
                "source 'https://rubygems.org'\nruby '3.3.5'\ngem 'rails', '~> 6.1.7'\ngem 'mysql2'\ngem 'sidekiq'\n",
                encoding="utf-8",
            )
            (p / "Gemfile.lock").write_text(
                "GEM\n  remote: https://rubygems.org/\n  specs:\n    rails (6.1.7.9)\n    activerecord (6.1.7.9)\n    mysql2 (0.5.6)\n    sidekiq (7.2.1)\n    minitest (5.25.1)\n\nRUBY VERSION\n   ruby 3.3.5p100\n",
                encoding="utf-8",
            )
            ctx = detector.detect(p)
            self.assertEqual(ctx.ruby_version, "3.3.5")
            self.assertEqual(ctx.rails_version, "6.1.7.9")
            self.assertEqual(ctx.rails_major_minor, "6.1")
            self.assertEqual(ctx.database, "mysql")
            self.assertEqual(ctx.orm, "active_record")
            self.assertIn("sidekiq", ctx.background_jobs)

    def test_priority_and_version_conflict_detection(self):
        detector = ProjectContextDetector()
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / ".ruby-version").write_text("3.2.2\n", encoding="utf-8")
            (p / "Gemfile").write_text(
                "source 'https://rubygems.org'\nruby '3.1.4'\ngem 'rails', '~> 7.0.0'\ngem 'pg'\ngem 'rspec-rails'\n",
                encoding="utf-8",
            )
            (p / "Gemfile.lock").write_text(
                "GEM\n  remote: https://rubygems.org/\n  specs:\n    rails (7.2.1)\n    pg (1.5.6)\n    rspec-rails (6.1.0)\n\nRUBY VERSION\n   ruby 3.3.5p100\n",
                encoding="utf-8",
            )
            ctx = detector.detect(p)
            # Priority 1 is Gemfile.lock
            self.assertEqual(ctx.ruby_version, "3.3.5")
            self.assertEqual(ctx.ruby_version_source, "Gemfile.lock")
            self.assertEqual(ctx.rails_version, "7.2.1")
            self.assertEqual(ctx.rails_major_minor, "7.2")
            self.assertEqual(ctx.database, "postgresql")
            self.assertEqual(ctx.test_framework, "rspec")
            # Conflicts between Gemfile.lock, .ruby-version, and Gemfile must be reported
            self.assertGreaterEqual(len(ctx.version_conflicts), 2)

    def test_missing_files_empty_directory(self):
        detector = ProjectContextDetector()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = detector.detect(Path(tmpdir))
            self.assertIsNone(ctx.ruby_version)
            self.assertIsNone(ctx.rails_version)
            self.assertEqual(ctx.detected_files, [])


class Test5CLIInterface(unittest.TestCase):
    """Tests for CLI: All commands, --help, valid JSON, Markdown, exit codes, controlled errors."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["RUBY_RAILS_KNOWLEDGE_DATA_DIR"] = str(Path(cls.tmp.name) / "data")
        os.environ["RUBY_RAILS_KNOWLEDGE_CACHE_DIR"] = str(Path(cls.tmp.name) / "cache")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main(["ingest"])
        assert code == 0

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("RUBY_RAILS_KNOWLEDGE_DATA_DIR", None)
        os.environ.pop("RUBY_RAILS_KNOWLEDGE_CACHE_DIR", None)
        cls.tmp.cleanup()

    def _run_cli(self, args: list[str]) -> tuple[int, str, str]:
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        try:
            with redirect_stdout(out_buf), redirect_stderr(err_buf):
                code = cli_main(args)
        except SystemExit as exc:
            code = int(exc.code) if exc.code is not None else 0
        return (code, out_buf.getvalue(), err_buf.getvalue())

    def test_all_commands_help(self):
        for cmd in [
            ["--help"],
            ["doctor", "--help"],
            ["status", "--help"],
            ["sources", "--help"],
            ["versions", "--help"],
            ["ingest", "--help"],
            ["update", "--help"],
            ["search", "--help"],
            ["graph", "--help"],
            ["context", "--help"],
            ["backup", "--help"],
            ["migrate", "--help"],
        ]:
            code, out, _ = self._run_cli(cmd)
            self.assertEqual(code, 0)
            self.assertIn("usage:", out)

    def test_all_commands_json_and_markdown(self):
        commands = [
            ["doctor"],
            ["status"],
            ["sources", "list"],
            ["versions", "list", "--technology", "rails"],
            ["update", "--source", "rails_guides", "--version", "6.1"],
            ["search", "after_commit", "--technology", "rails", "--version", "6.1"],
            ["graph", "active_record_callbacks"],
            ["context", "detect", "--project", "."],
            ["backup", "--label", "clitest"],
            ["migrate"],
        ]
        for cmd in commands:
            code, out, err = self._run_cli(cmd + ["--format", "json"])
            self.assertEqual(code, 0, f"Command {cmd} failed: {err}")
            parsed = json.loads(out)
            self.assertIsInstance(parsed, dict)
            # Ensure no sensitive host path leakage in search/context JSON outputs
            if cmd[0] in ("search", "context", "doctor", "status"):
                self.assertNotIn("/.local/share/", out)

        for md_cmd in [
            ["doctor", "--format", "markdown"],
            ["status", "--format", "markdown"],
            ["sources", "list", "--format", "markdown"],
            ["versions", "list", "--format", "markdown"],
            ["search", "find_each", "--format", "markdown"],
            ["graph", "after_commit", "--format", "markdown"],
            ["context", "detect", "--project", ".", "--format", "markdown"],
        ]:
            code, out, _ = self._run_cli(md_cmd)
            self.assertEqual(code, 0)
            self.assertIn("# ", out)

    def test_controlled_error_exit_code(self):
        code, _, err = self._run_cli(["ingest", "--source", "nonexistent_source_xyz"])
        self.assertEqual(code, 1)
        err_json = json.loads(err)
        self.assertEqual(err_json["error"], "ValueError")


if __name__ == "__main__":
    unittest.main(verbosity=2)
