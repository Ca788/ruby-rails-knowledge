"""Read-only consumer project context detector (Gemfile.lock, .ruby-version, Gemfile, config/)."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

from ..models.entities import ProjectContext


LOCK_SPEC_RE = re.compile(r"^\s{4}([A-Za-z0-9_-]+)\s+\(([0-9][A-Za-z0-9._-]*)\)", re.MULTILINE)
LOCK_RUBY_RE = re.compile(r"RUBY VERSION\s+ruby\s+([0-9]+\.[0-9]+\.[0-9]+)", re.MULTILINE)
GEMFILE_RUBY_RE = re.compile(r'^\s*ruby\s+["\']([^"\']+)["\']', re.MULTILINE)
GEMFILE_GEM_RE = re.compile(
    r'^\s*gem\s+["\']([A-Za-z0-9_-]+)["\'](?:\s*,\s*["\']([^"\']+)["\'])?',
    re.MULTILINE,
)
DB_ADAPTER_RE = re.compile(r"^\s*adapter:\s*([A-Za-z0-9_]+)", re.MULTILINE)

DB_GEM_MAP = {
    "pg": "postgresql",
    "mysql2": "mysql",
    "trilogy": "mysql",
    "sqlite3": "sqlite3",
    "activerecord-oracle_enhanced-adapter": "oracle",
    "tiny_tds": "sqlserver",
}

BG_JOB_GEMS = [
    "sidekiq",
    "solid_queue",
    "good_job",
    "delayed_job",
    "delayed_job_active_record",
    "resque",
    "que",
    "shoryuken",
]

NOTABLE_GEMS = [
    "rails",
    "activerecord",
    "activejob",
    "activesupport",
    "actionpack",
    "zeitwerk",
    "pg",
    "mysql2",
    "sqlite3",
    "trilogy",
    "sidekiq",
    "solid_queue",
    "good_job",
    "rspec-rails",
    "rspec",
    "minitest",
    "mocha",
    "factory_bot_rails",
    "rubocop",
    "rubocop-rails",
    "devise",
    "pundit",
    "after_commit_everywhere",
    "graphql",
    "alba",
    "jbuilder",
    "sunspot_rails",
]


class ProjectContextDetector:
    """Detects Ruby, Rails, DB, ORM, Test Framework, Background Jobs, and Dependencies without modifying files."""

    def detect(self, project_dir: Path) -> ProjectContext:
        root = Path(project_dir).resolve()
        ctx = ProjectContext()
        if not root.exists() or not root.is_dir():
            return ctx

        lock_specs: Dict[str, str] = {}
        lock_ruby: Optional[str] = None
        dot_ruby: Optional[str] = None
        gemfile_ruby: Optional[str] = None
        gemfile_gems: Dict[str, str] = {}

        # 1. Gemfile.lock (Priority 1)
        lock_path = root / "Gemfile.lock"
        if lock_path.is_file():
            ctx.detected_files.append("Gemfile.lock")
            lock_text = lock_path.read_text(encoding="utf-8", errors="replace")
            lock_specs, lock_ruby = self._parse_gemfile_lock(lock_text)

        # 2. .ruby-version (Priority 2)
        rv_path = root / ".ruby-version"
        if rv_path.is_file():
            ctx.detected_files.append(".ruby-version")
            raw_rv = rv_path.read_text(encoding="utf-8", errors="replace").strip()
            if raw_rv:
                dot_ruby = re.sub(r"^ruby-", "", raw_rv.splitlines()[0].strip())

        # 3. Gemfile (Priority 3)
        gemfile_path = root / "Gemfile"
        if gemfile_path.is_file():
            ctx.detected_files.append("Gemfile")
            gf_text = gemfile_path.read_text(encoding="utf-8", errors="replace")
            gemfile_gems, gemfile_ruby = self._parse_gemfile(gf_text)

        # 4. Complementary configurations (config/database.yml, config/application.rb, test/ vs spec/)
        db_yml_path = root / "config" / "database.yml"
        db_yml_adapter: Optional[str] = None
        if db_yml_path.is_file():
            ctx.detected_files.append("config/database.yml")
            db_text = db_yml_path.read_text(encoding="utf-8", errors="replace")
            m = DB_ADAPTER_RE.search(db_text)
            if m:
                raw_adapter = m.group(1).lower()
                if "mysql" in raw_adapter or "trilogy" in raw_adapter:
                    db_yml_adapter = "mysql"
                elif "postgres" in raw_adapter or "postgis" in raw_adapter:
                    db_yml_adapter = "postgresql"
                elif "sqlite" in raw_adapter:
                    db_yml_adapter = "sqlite3"
                else:
                    db_yml_adapter = raw_adapter

        app_rb_path = root / "config" / "application.rb"
        if app_rb_path.is_file():
            ctx.detected_files.append("config/application.rb")

        # Resolve Ruby version according to strict priority: 1. Gemfile.lock, 2. .ruby-version, 3. Gemfile
        if lock_ruby:
            ctx.ruby_version = lock_ruby
            ctx.ruby_version_source = "Gemfile.lock"
        elif dot_ruby:
            ctx.ruby_version = dot_ruby
            ctx.ruby_version_source = ".ruby-version"
        elif gemfile_ruby:
            ctx.ruby_version = self._clean_version_constraint(gemfile_ruby)
            ctx.ruby_version_source = "Gemfile"

        # Check Ruby version conflicts across sources
        distinct_rubies = {}
        if lock_ruby:
            distinct_rubies["Gemfile.lock"] = lock_ruby
        if dot_ruby:
            distinct_rubies[".ruby-version"] = dot_ruby
        if gemfile_ruby:
            cleaned_gf_ruby = self._clean_version_constraint(gemfile_ruby)
            if re.match(r"^\d+\.\d+", cleaned_gf_ruby):
                distinct_rubies["Gemfile"] = cleaned_gf_ruby

        if len(set(distinct_rubies.values())) > 1:
            parts = [f"{src}={ver}" for src, ver in distinct_rubies.items()]
            ctx.version_conflicts.append(f"Ruby version mismatch across files: {', '.join(parts)}")

        # Resolve Rails version according to priority: 1. Gemfile.lock, 2. Gemfile
        lock_rails = lock_specs.get("rails") or lock_specs.get("activerecord") or lock_specs.get("activesupport")
        gf_rails = gemfile_gems.get("rails")

        if lock_rails:
            ctx.rails_version = lock_rails
            ctx.rails_version_source = "Gemfile.lock"
        elif gf_rails:
            ctx.rails_version = self._clean_version_constraint(gf_rails)
            ctx.rails_version_source = "Gemfile"

        if ctx.rails_version:
            v_parts = ctx.rails_version.split(".")
            if len(v_parts) >= 2 and v_parts[0].isdigit() and v_parts[1].isdigit():
                ctx.rails_major_minor = f"{v_parts[0]}.{v_parts[1]}"

        if lock_rails and gf_rails:
            gf_mm = self._extract_major_minor(gf_rails)
            lock_mm = self._extract_major_minor(lock_rails)
            if gf_mm and lock_mm and gf_mm != lock_mm:
                ctx.version_conflicts.append(
                    f"Rails version conflict: Gemfile.lock has {lock_rails} ({lock_mm}) vs Gemfile constraint '{gf_rails}' ({gf_mm})"
                )

        # Merge effective gems map (lockfile takes precedence over Gemfile)
        all_gems: Dict[str, str] = dict(gemfile_gems)
        all_gems.update(lock_specs)

        # Database detection
        for gem_name, db_type in DB_GEM_MAP.items():
            if gem_name in all_gems:
                ctx.database = db_type
                break
        if not ctx.database and db_yml_adapter:
            ctx.database = db_yml_adapter

        # ORM detection
        if "activerecord" in all_gems or "rails" in all_gems:
            ctx.orm = "active_record"
        elif "mongoid" in all_gems:
            ctx.orm = "mongoid"
        elif "sequel" in all_gems:
            ctx.orm = "sequel"
        elif "rom" in all_gems:
            ctx.orm = "rom"

        # Test framework detection
        if "rspec-rails" in all_gems or "rspec" in all_gems or "rspec-core" in all_gems:
            ctx.test_framework = "rspec"
        elif "minitest" in all_gems or (root / "test" / "test_helper.rb").is_file():
            ctx.test_framework = "minitest"

        # Background jobs detection
        for bg in BG_JOB_GEMS:
            if bg in all_gems:
                norm_bg = "delayed_job" if bg.startswith("delayed_job") else bg
                if norm_bg not in ctx.background_jobs:
                    ctx.background_jobs.append(norm_bg)

        # Notable dependencies
        for g in NOTABLE_GEMS:
            if g in all_gems:
                ctx.relevant_dependencies[g] = all_gems[g]

        return ctx

    @staticmethod
    def _parse_gemfile_lock(text: str) -> Tuple[Dict[str, str], Optional[str]]:
        specs: Dict[str, str] = {}
        for m in LOCK_SPEC_RE.finditer(text):
            gem_name, ver = m.group(1), m.group(2)
            if gem_name not in specs:
                specs[gem_name] = ver
        ruby_ver: Optional[str] = None
        rm = LOCK_RUBY_RE.search(text)
        if rm:
            ruby_ver = rm.group(1)
        return (specs, ruby_ver)

    @staticmethod
    def _parse_gemfile(text: str) -> Tuple[Dict[str, str], Optional[str]]:
        gems: Dict[str, str] = {}
        ruby_ver: Optional[str] = None
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if ruby_ver is None:
                rm = GEMFILE_RUBY_RE.match(line)
                if rm:
                    ruby_ver = rm.group(1).strip()
                    continue
            gm = GEMFILE_GEM_RE.match(line)
            if gm:
                gname = gm.group(1)
                gver = (gm.group(2) or "unspecified").strip()
                gems[gname] = gver
        return (gems, ruby_ver)

    @staticmethod
    def _clean_version_constraint(constraint: str) -> str:
        c = re.sub(r"^[~><=\s]+", "", constraint.strip())
        return c.split(",")[0].strip()

    @staticmethod
    def _extract_major_minor(ver_str: str) -> Optional[str]:
        m = re.search(r"(\d+)\.(\d+)", ver_str)
        if m:
            return f"{m.group(1)}.{m.group(2)}"
        return None
