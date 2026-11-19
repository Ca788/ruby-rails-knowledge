from .database import DatabaseManager
from .fts import (
    build_fts5_match_expression,
    extract_technical_identifiers,
    normalize_identifier,
    normalize_text_for_fts,
)
from .migrations import MigrationManager
from .repositories import KnowledgeRepository

__all__ = [
    "DatabaseManager",
    "KnowledgeRepository",
    "MigrationManager",
    "build_fts5_match_expression",
    "extract_technical_identifiers",
    "normalize_identifier",
    "normalize_text_for_fts",
]
