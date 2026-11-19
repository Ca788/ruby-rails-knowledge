"""Query normalization, technical identifier extraction, and technology/version inference."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import List, Optional

from ..storage.fts import STOPWORDS, build_fts5_match_expression, N_PLUS_ONE_RE


RAILS_KEYWORDS = {
    "rails", "activerecord", "active_record", "activejob", "active_job",
    "activesupport", "active_support", "actioncontroller", "action_controller",
    "after_commit", "after_save", "after_rollback", "before_validation",
    "includes", "preload", "eager_load", "find_each", "in_batches",
    "strict_loading", "zeitwerk", "autoloading", "connection_pool",
    "connectionpool", "n_plus_one", "dependent", "belongs_to", "has_many",
    "savepoint", "requires_new", "after_all_transactions_commit", "deprecators",
}

RUBY_KEYWORDS = {
    "enumerable", "enumerator", "ractor", "fiber", "gvl", "yjit", "rjit",
    "basicobject", "eigenclass", "prepend", "tally", "flat_map", "filter_map",
    "each_with_object", "objectspace", "rgengc", "prism",
}

RAILS_VER_MENTION_RE = re.compile(r"\brails\s+v?(\d+\.\d+|edge)\b", re.IGNORECASE)
RUBY_VER_MENTION_RE = re.compile(r"\bruby\s+v?(\d+\.\d+)\b", re.IGNORECASE)


@dataclass
class NormalizedQuery:
    raw_query: str
    fts_expression: str
    raw_identifiers: List[str] = field(default_factory=list)
    normalized_identifiers: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    inferred_technology: Optional[str] = None
    inferred_versions: List[str] = field(default_factory=list)


class QueryNormalizer:
    def normalize(self, query: str) -> NormalizedQuery:
        q = (query or "").strip()
        fts_expr, raw_idents, norm_idents = build_fts5_match_expression(q)

        q_clean = N_PLUS_ONE_RE.sub(" n_plus_one ", q)
        words = [
            w.lstrip("#.:").lower()
            for w in re.findall(r"[A-Za-z0-9_#?!:]+", q_clean)
        ]
        keywords = list(dict.fromkeys(
            w for w in words if len(w) >= 2 and w not in STOPWORDS
        ))

        inferred_tech: Optional[str] = None
        token_set = set(keywords) | set(norm_idents) | {w.lower() for w in words}
        if token_set & RAILS_KEYWORDS:
            inferred_tech = "rails"
        elif token_set & RUBY_KEYWORDS:
            inferred_tech = "ruby"

        inferred_vers: List[str] = []
        for m in RAILS_VER_MENTION_RE.finditer(q):
            inferred_vers.append(m.group(1).lower())
            if not inferred_tech:
                inferred_tech = "rails"
        for m in RUBY_VER_MENTION_RE.finditer(q):
            inferred_vers.append(m.group(1).lower())
            if not inferred_tech:
                inferred_tech = "ruby"

        return NormalizedQuery(
            raw_query=q,
            fts_expression=fts_expr,
            raw_identifiers=raw_idents,
            normalized_identifiers=norm_idents,
            keywords=keywords,
            inferred_technology=inferred_tech,
            inferred_versions=list(dict.fromkeys(inferred_vers)),
        )
