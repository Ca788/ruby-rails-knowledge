"""SQLite database connection, backup, migration, and cache mirror management."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from ..config import SCHEMA_VERSION, AppConfig
from .migrations import MigrationManager


class DatabaseManager:
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self.migration_manager = MigrationManager(self.config.schema_sql_path)

    def _resolve_active_db_path(self, readonly: bool = False) -> Path:
        primary = self.config.db_path
        if readonly:
            if primary.exists() and os.access(primary, os.R_OK):
                return primary
            cache_db = self.config.cache_db_path
            if cache_db.exists() and os.access(cache_db, os.R_OK):
                return cache_db
        return primary

    def initialize(self) -> Dict[str, Any]:
        """Ensure directories exist, apply migrations, and write metadata."""
        self.config.ensure_directories()
        with self.connect(readonly=False) as conn:
            applied = self.migration_manager.migrate(conn)
            ver = self.migration_manager.current_version(conn)
        self._write_database_version_metadata(ver)
        self.sync_to_cache()
        return {"schema_version": ver, "applied_migrations": applied}

    @contextmanager
    def connect(self, readonly: bool = False) -> Iterator[sqlite3.Connection]:
        db_file = self._resolve_active_db_path(readonly=readonly)
        if not readonly:
            db_file.parent.mkdir(parents=True, exist_ok=True)

        if readonly and db_file.exists():
            # Open in read-only URI mode if parent directory is not writable
            parent_writable = os.access(db_file.parent, os.W_OK)
            if parent_writable:
                uri = f"file:{db_file.as_posix()}?mode=ro"
            else:
                uri = f"file:{db_file.as_posix()}?mode=ro&immutable=1"
            conn = sqlite3.connect(uri, uri=True)
        else:
            conn = sqlite3.connect(str(db_file))

        conn.row_factory = sqlite3.Row
        if not readonly:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = DELETE;")
            conn.execute("PRAGMA synchronous = NORMAL;")
        else:
            try:
                conn.execute("PRAGMA foreign_keys = ON;")
            except sqlite3.OperationalError:
                pass
        try:
            yield conn
        finally:
            conn.close()

    def backup_database(self, label: str = "manual") -> Optional[Path]:
        """Create a consistent SQLite backup in the cache backups directory."""
        src_db = self._resolve_active_db_path(readonly=True)
        if not src_db.exists():
            return None
        backup_dir = self.config.cache_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest_path = backup_dir / f"knowledge-{label}-{ts}.sqlite3"
        with sqlite3.connect(str(src_db)) as src_conn:
            with sqlite3.connect(str(dest_path)) as dst_conn:
                src_conn.backup(dst_conn)
        return dest_path

    def sync_to_cache(self) -> None:
        """Mirror database and manifests to ~/.cache/ruby-rails-knowledge/mirror for sandboxed queries."""
        primary_db = self.config.db_path
        cache_db = self.config.cache_db_path
        if not primary_db.exists():
            return
        try:
            if primary_db.resolve() == cache_db.resolve():
                return
            cache_db.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(primary_db)) as src_conn:
                with sqlite3.connect(str(cache_db)) as dst_conn:
                    src_conn.backup(dst_conn)
            for sub in ["manifests", "metadata"]:
                src_sub = self.config.data_dir / sub
                dst_sub = self.config.cache_dir / "mirror" / sub
                if src_sub.exists():
                    dst_sub.mkdir(parents=True, exist_ok=True)
                    for f in src_sub.glob("*.json"):
                        shutil.copy2(f, dst_sub / f.name)
        except OSError:
            pass

    def _write_database_version_metadata(self, version: int) -> None:
        meta_file = self.config.metadata_dir / "database-version.json"
        meta_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": version,
            "expected_schema_version": SCHEMA_VERSION,
            "engine": "sqlite3+fts5",
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        meta_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def check_health(self) -> Dict[str, Any]:
        """Verify SQLite integrity, FTS5 functionality, and foreign keys."""
        db_file = self._resolve_active_db_path(readonly=True)
        exists = db_file.exists()
        if not exists:
            return {
                "healthy": False,
                "db_exists": False,
                "fts5_enabled": True,
                "schema_version": 0,
                "integrity_check": "missing_database",
            }
        with self.connect(readonly=True) as conn:
            integrity = conn.execute("PRAGMA integrity_check;").fetchone()[0]
            fk_violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
            ver = self.migration_manager.current_version(conn)
            try:
                conn.execute("SELECT count(*) FROM knowledge_chunks_fts;").fetchone()
                fts_ok = True
            except sqlite3.Error:
                fts_ok = False
        return {
            "healthy": integrity == "ok" and len(fk_violations) == 0 and fts_ok and ver >= SCHEMA_VERSION,
            "db_exists": True,
            "fts5_enabled": fts_ok,
            "schema_version": ver,
            "integrity_check": integrity,
            "foreign_key_violations": len(fk_violations),
        }
