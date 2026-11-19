#!/usr/bin/env python3
"""Global Installer for ruby-rails-knowledge Skill and Data Infrastructure."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BUILD_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def detect_surfaces(home: Path) -> list[tuple[str, Path]]:
    targets: list[tuple[str, Path]] = []
    # 1. Antigravity App & IDE (~/.gemini/config/skills/ruby-rails-knowledge)
    gemini_cfg = home / ".gemini" / "config"
    if gemini_cfg.exists() or (home / ".gemini" / "antigravity").exists():
        targets.append(("antigravity_app_ide", gemini_cfg / "skills" / "ruby-rails-knowledge"))

    # 2. Antigravity CLI (~/.gemini/antigravity-cli/skills/ruby-rails-knowledge)
    cli_cfg = home / ".gemini" / "antigravity-cli"
    if cli_cfg.exists():
        targets.append(("antigravity_cli", cli_cfg / "skills" / "ruby-rails-knowledge"))

    if not targets:
        targets.append(("antigravity_app_ide", gemini_cfg / "skills" / "ruby-rails-knowledge"))
    return targets


def copy_skill_tree(src_root: Path, dst_root: Path) -> None:
    if src_root.resolve() == dst_root.resolve():
        return
    dst_root.mkdir(parents=True, exist_ok=True)
    for item in ["SKILL.md", "README.md", "VERSION", ".gitignore", "config", "schemas", "references", "scripts"]:
        s = src_root / item
        d = dst_root / item
        if not s.exists():
            continue
        if s.is_dir():
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(
                s,
                d,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
            )
        else:
            shutil.copy2(s, d)

    for exe in ["ruby-rails-knowledge", "install.py", "run_tests.py", "run_benchmark.py"]:
        p = dst_root / "scripts" / exe
        if p.exists():
            os.chmod(p, 0o755)


def main() -> int:
    home = Path.home()
    targets = detect_surfaces(home)
    installed_paths: list[dict[str, str]] = []

    for surface_name, target_dir in targets:
        copy_skill_tree(BUILD_ROOT, target_dir)
        installed_paths.append({"surface": surface_name, "skill_dir": str(target_dir)})

    # Initialize global persistent data directory (~/.local/share/ruby-rails-knowledge)
    # and cache directory (~/.cache/ruby-rails-knowledge)
    primary_skill_dir = targets[0][1]
    primary_data_dir = home / ".local" / "share" / "ruby-rails-knowledge"
    primary_cache_dir = home / ".cache" / "ruby-rails-knowledge"

    from src.config import AppConfig
    from src.ingestion.pipeline import IngestionPipeline
    from src.storage.database import DatabaseManager

    cfg = AppConfig(
        skill_root=primary_skill_dir,
        data_dir=primary_data_dir,
        cache_dir=primary_cache_dir,
    )
    pipeline = IngestionPipeline(cfg)
    summary = pipeline.run_ingestion(run_type="ingest")
    health = DatabaseManager(cfg).check_health()

    report = {
        "installed_skills": installed_paths,
        "data_dir": str(primary_data_dir),
        "cache_dir": str(primary_cache_dir),
        "ingestion_summary": summary.to_dict(),
        "health": health,
    }
    print(json.dumps(report, indent=2))
    return 0 if health.get("healthy") else 1


if __name__ == "__main__":
    sys.exit(main())
