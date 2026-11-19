"""Configuration, configurable XDG directory resolution, and retrieval limits."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


SKILL_NAME = "ruby-rails-knowledge"
SKILL_VERSION = "1.0.0"
SCHEMA_VERSION = 1


def _resolve_skill_root() -> Path:
    env_root = os.environ.get("RUBY_RAILS_KNOWLEDGE_SKILL_DIR")
    if env_root:
        return Path(env_root).expanduser().resolve()
    # Relative to scripts/src/config.py -> scripts/src -> scripts -> skill_root
    return Path(__file__).resolve().parent.parent.parent


def _is_writable_or_creatable(target: Path) -> bool:
    try:
        curr = target
        while not curr.exists() and curr.parent != curr:
            curr = curr.parent
        return os.access(curr, os.W_OK)
    except OSError:
        return False


def resolve_data_dir(prefer_writable: bool = False) -> Path:
    """Resolve the persistent global data directory.

    Priority:
    1. RUBY_RAILS_KNOWLEDGE_DATA_DIR environment variable.
    2. $XDG_DATA_HOME/ruby-rails-knowledge or ~/.local/share/ruby-rails-knowledge
       (if accessible or writable).
    3. Fallback to ~/.cache/ruby-rails-knowledge/data when running inside a
       restricted container/sandbox where ~/.local/share is not mounted.
    """
    env_dir = os.environ.get("RUBY_RAILS_KNOWLEDGE_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser()

    xdg_data = os.environ.get("XDG_DATA_HOME")
    base_data = Path(xdg_data).expanduser() if xdg_data else (Path.home() / ".local" / "share")
    primary = base_data / SKILL_NAME

    db_file = primary / "database" / "knowledge.sqlite3"
    if not prefer_writable and db_file.exists() and os.access(db_file, os.R_OK):
        return primary
    if _is_writable_or_creatable(primary):
        return primary

    # Sandbox fallback to cache mirror
    cache_fallback = resolve_cache_dir() / "mirror"
    return cache_fallback


def resolve_cache_dir() -> Path:
    """Resolve the reconstructible cache directory."""
    env_cache = os.environ.get("RUBY_RAILS_KNOWLEDGE_CACHE_DIR")
    if env_cache:
        return Path(env_cache).expanduser()
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    base_cache = Path(xdg_cache).expanduser() if xdg_cache else (Path.home() / ".cache")
    return base_cache / SKILL_NAME


def detect_antigravity_skill_targets() -> Dict[str, Path]:
    """Detect official Antigravity App/IDE and CLI global skill installation paths."""
    home = Path.home()
    return {
        "app_ide": home / ".gemini" / "config" / "skills" / SKILL_NAME,
        "cli": home / ".gemini" / "antigravity-cli" / "skills" / SKILL_NAME,
    }


@dataclass
class RetrievalLimits:
    max_results: int = 5
    max_related_concepts: int = 8
    max_graph_depth: int = 2
    max_content_chars: int = 2400
    max_estimated_tokens: int = 1800


@dataclass
class SecurityLimits:
    connect_timeout_sec: float = 8.0
    read_timeout_sec: float = 12.0
    max_download_bytes: int = 5 * 1024 * 1024  # 5 MB
    require_https: bool = True
    max_redirects: int = 3


@dataclass
class AppConfig:
    skill_root: Path = field(default_factory=_resolve_skill_root)
    data_dir: Path = field(default_factory=resolve_data_dir)
    cache_dir: Path = field(default_factory=resolve_cache_dir)
    retrieval_limits: RetrievalLimits = field(default_factory=RetrievalLimits)
    security_limits: SecurityLimits = field(default_factory=SecurityLimits)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "database" / "knowledge.sqlite3"

    @property
    def cache_db_path(self) -> Path:
        return self.cache_dir / "mirror" / "database" / "knowledge.sqlite3"

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"

    @property
    def manifests_dir(self) -> Path:
        return self.data_dir / "manifests"

    @property
    def metadata_dir(self) -> Path:
        return self.data_dir / "metadata"

    @property
    def sources_config_path(self) -> Path:
        return self.skill_root / "config" / "sources.yml"

    @property
    def schema_sql_path(self) -> Path:
        return self.skill_root / "schemas" / "schema.sql"

    def ensure_directories(self) -> None:
        for d in [
            self.data_dir / "database",
            self.documents_dir / "ruby",
            self.documents_dir / "rails",
            self.documents_dir / "ecosystem",
            self.documents_dir / "security",
            self.manifests_dir,
            self.metadata_dir,
            self.cache_dir / "mirror" / "database",
            self.cache_dir / "backups",
        ]:
            d.mkdir(parents=True, exist_ok=True)
