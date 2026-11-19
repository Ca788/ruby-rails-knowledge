"""Database schema versioning and migration runner."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


class MigrationManager:
    """Manages SQLite schema migrations safely and idempotently."""

    def __init__(self, schema_sql_path: Path):
        self.schema_sql_path = schema_sql_path

    def get_migrations(self) -> List[Tuple[int, str, str]]:
        v1_sql = self.schema_sql_path.read_text(encoding="utf-8")
        # Future schema migrations can be appended here with version 2, 3, ...
        return [
            (1, "initial_knowledge_base_schema_v1", v1_sql),
        ]

    def current_version(self, conn: sqlite3.Connection) -> int:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        )
        if not cur.fetchone():
            return 0
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def applied_migrations(self, conn: sqlite3.Connection) -> List[Dict[str, object]]:
        if self.current_version(conn) == 0:
            return []
        rows = conn.execute(
            "SELECT version, name, applied_at FROM schema_migrations ORDER BY version ASC"
        ).fetchall()
        return [
            {"version": r[0], "name": r[1], "applied_at": r[2]}
            for r in rows
        ]

    def migrate(self, conn: sqlite3.Connection) -> List[int]:
        applied: List[int] = []
        current = self.current_version(conn)
        for version, name, sql_script in self.get_migrations():
            if version > current:
                conn.executescript(sql_script)
                now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                conn.execute(
                    "INSERT OR REPLACE INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, now),
                )
                conn.commit()
                applied.append(version)
        conn.execute("PRAGMA foreign_keys = ON;")
        return applied
