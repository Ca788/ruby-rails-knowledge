"""Source catalog loader and version availability discovery."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml

from ..models.entities import SourceConfig, VersionInfo


class SourceCatalog:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._raw = self._load_yaml()
        self.sources: Dict[str, SourceConfig] = self._parse_sources()
        self.versions: List[VersionInfo] = self._parse_versions()

    def _load_yaml(self) -> dict:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Sources configuration not found: {self.config_path}")
        data = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        return data or {}

    def _parse_sources(self) -> Dict[str, SourceConfig]:
        out: Dict[str, SourceConfig] = {}
        for item in self._raw.get("sources", []):
            src = SourceConfig(
                id=item["id"],
                technology=item["technology"],
                authority=item["authority"],
                source_type=item["source_type"],
                base_url=item["base_url"],
                versioned=bool(item.get("versioned", True)),
                enabled=bool(item.get("enabled", True)),
                supported_versions=[str(v) for v in item.get("supported_versions", [])],
                url_template=item.get("url_template"),
                description=item.get("description", ""),
            )
            src.validate()
            out[src.id] = src
        return out

    def _parse_versions(self) -> List[VersionInfo]:
        out: List[VersionInfo] = []
        matrix = self._raw.get("version_matrix", {})
        for tech, ver_list in matrix.items():
            for item in ver_list:
                out.append(
                    VersionInfo(
                        technology=tech,
                        version=str(item["version"]),
                        status=item["status"],
                        docs_available=bool(item.get("docs_available", True)),
                        is_latest_stable=bool(item.get("is_latest_stable", False)),
                        release_date=item.get("release_date"),
                        eol_date=item.get("eol_date"),
                        docs_url=item.get("docs_url"),
                        notes=item.get("notes", ""),
                    )
                )
        # Also register standard unversioned ecosystem/security version entries
        out.append(
            VersionInfo(
                technology="ecosystem",
                version="current",
                status="current_stable",
                docs_available=True,
                is_latest_stable=True,
                docs_url="https://docs.rubocop.org/",
                notes="Complementary ecosystem documentation (RuboCop, Ruby Style Guide, RSpec).",
            )
        )
        out.append(
            VersionInfo(
                technology="security",
                version="current",
                status="current_stable",
                docs_available=True,
                is_latest_stable=True,
                docs_url="https://cheatsheetseries.owasp.org/",
                notes="OWASP Ruby on Rails Security Cheat Sheet.",
            )
        )
        return out

    def allowed_domains(self) -> List[str]:
        from urllib.parse import urlparse
        domains = {"cheatsheetseries.owasp.org"}
        for s in self.sources.values():
            parsed = urlparse(s.base_url)
            if parsed.hostname:
                domains.add(parsed.hostname.lower())
        return sorted(domains)

    def get_version_info(self, technology: str, version: str) -> Optional[VersionInfo]:
        norm_v = self.normalize_version_string(technology, version)
        for v in self.versions:
            if v.technology == technology and v.version == norm_v:
                return v
        return None

    @staticmethod
    def normalize_version_string(technology: str, version: str) -> str:
        v = version.strip().lower().lstrip("v")
        if v in ("latest", "stable", "current"):
            if technology == "rails":
                return "8.0"
            if technology == "ruby":
                return "3.4"
            return "current"
        if v == "edge":
            return "edge"
        parts = v.split(".")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"{parts[0]}.{parts[1]}"
        return v

    def resolve_version_with_fallback(
        self, technology: str, requested_version: str
    ) -> Tuple[str, Optional[str], Optional[VersionInfo]]:
        """Resolve requested version to an available documented version, or nearest version with explicit notice."""
        norm = self.normalize_version_string(technology, requested_version)
        available = [
            v for v in self.versions
            if v.technology == technology and v.docs_available and v.version != "edge"
        ]
        exact = next((v for v in self.versions if v.technology == technology and v.version == norm), None)
        if exact and exact.docs_available:
            notice = None
            if exact.status == "eol":
                notice = f"{technology.capitalize()} {norm} is End-of-Life (EOL); returning preserved historical documentation for {norm}."
            elif exact.status == "edge":
                notice = f"Returning unreleased Edge documentation for {technology.capitalize()}."
            return (norm, notice, exact)

        # Find nearest numeric major.minor version
        def _to_float(ver_str: str) -> Optional[float]:
            try:
                p = ver_str.split(".")
                return int(p[0]) + int(p[1]) / 10.0
            except (ValueError, IndexError):
                return None

        target_num = _to_float(norm)
        if target_num is not None and available:
            scored = []
            for cand in available:
                c_num = _to_float(cand.version)
                if c_num is not None:
                    scored.append((abs(c_num - target_num), c_num, cand))
            if scored:
                scored.sort(key=lambda x: (x[0], -x[1]))
                nearest = scored[0][2]
                reason = (
                    f"Dedicated documentation for {technology.capitalize()} {requested_version} (normalized: {norm}) "
                    f"is not available in the knowledge base. Showing nearest documented version {nearest.version} "
                    f"(compatibility with {requested_version} is not guaranteed without verification)."
                )
                return (nearest.version, reason, nearest)

        return (norm, f"No documentation found for {technology} version {requested_version}.", exact)
