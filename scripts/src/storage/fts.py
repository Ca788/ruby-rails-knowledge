"""FTS5 tokenization helper and auxiliary Ruby/Rails technical identifier indexing."""
from __future__ import annotations

import re
from typing import List, Optional, Set, Tuple


# Regex patterns for Ruby and Rails technical identifiers
NAMESPACE_RE = re.compile(r"\b([A-Z][A-Za-z0-9]*(?:::[A-Z][A-Za-z0-9]*)+(?:#[a-z_][a-z0-9_?!]*|\.[a-z_][a-z0-9_?!]*)?)")
KEYWORD_SYM_RE = re.compile(r"\b([a-z_][a-z0-9_]*:\s*:[a-z_][a-z0-9_]*)\b")
SNAKE_IDENT_RE = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+[?!]?)\b")
METHOD_BANG_Q_RE = re.compile(r"(?:^|[\s`\.#])([a-z_][a-z0-9_]*[?!])(?=$|[\s`\),\.])")
HASH_METHOD_RE = re.compile(r"(?:^|[\s`A-Za-z0-9])(#[a-z_][a-z0-9_?!]*)\b")
SYMBOL_RE = re.compile(r"(?:^|[\s`\(,])(:[a-z_][a-z0-9_]*)\b")
BACKTICK_RE = re.compile(r"`([^`\n]{2,60})`")
CAMEL_CLASS_RE = re.compile(r"\b(Enumerable|Comparable|Kernel|Object|BasicObject|Module|Class|Array|Hash|String|Symbol|Proc|Lambda|Method|Thread|Fiber|Ractor|Mutex|GC|ObjectSpace|Struct|Data|Regexp|Enumerator|Exception|StandardError|RuntimeError|ActiveRecord|ActiveJob|ActiveSupport|ActionController|ActionDispatch|ActionView|ActionMailer|ActionCable|ActiveModel|ActiveStorage|Zeitwerk|Sidekiq|RSpec|RuboCop)\b")
N_PLUS_ONE_RE = re.compile(r"\b(?:n\s*\+\s*1|n_plus_one)\b", re.IGNORECASE)

STOPWORDS = {
    "what", "is", "the", "difference", "between", "and", "or", "how", "does",
    "do", "work", "works", "in", "on", "of", "to", "for", "with", "a", "an",
    "are", "when", "why", "from", "by", "at", "be", "can", "used", "using",
    "rails", "ruby", "version", "changed", "regarding", "selected", "handle",
    "prevent", "methods", "documented",
}


def normalize_identifier(raw: str) -> str:
    """Normalize a Ruby/Rails identifier into a canonical searchable key."""
    s = raw.strip().strip("`").strip()
    if N_PLUS_ONE_RE.search(s):
        return "n_plus_one"
    # Normalize whitespace in keyword options like `dependent:   :destroy`
    s = re.sub(r":\s+:", ": :", s)
    s_low = s.lower()
    # Replace :: with __ and spaces/colons with _ for canonical matching
    canon = s_low.replace("::", "__")
    canon = re.sub(r"[:\s#\.]+", "_", canon)
    canon = canon.strip("_")
    return canon


def identifier_variants(raw: str) -> Set[str]:
    """Produce searchable lexical tokens for a technical identifier."""
    s = raw.strip().strip("`").strip()
    variants: Set[str] = set()
    if not s:
        return variants
    s_low = s.lower()
    variants.add(s_low)
    norm = normalize_identifier(s)
    if norm:
        variants.add(norm)
    if "::" in s_low:
        parts = [p for p in s_low.replace("#", "::").replace(".", "::").split("::") if p]
        variants.update(parts)
        variants.add("_".join(parts))
    if ": :" in s_low or ":" in s_low:
        cleaned = re.sub(r"[^a-z0-9_]+", "_", s_low).strip("_")
        if cleaned:
            variants.add(cleaned)
    if s_low.startswith("#") or s_low.startswith(".") or s_low.startswith(":"):
        variants.add(s_low.lstrip("#.:"))
    if s_low.endswith("?") or s_low.endswith("!"):
        variants.add(s_low[:-1])
    if N_PLUS_ONE_RE.search(s_low):
        variants.update(["n_plus_one", "n+1", "n1"])
    return {v for v in variants if len(v) >= 2}


def extract_technical_identifiers(
    text: str,
    title: str = "",
    extra_concepts: Optional[List[str]] = None,
) -> List[Tuple[str, str, str, float]]:
    """Extract technical identifiers from text and return (raw, normalized, type, weight)."""
    found: dict[str, Tuple[str, str, str, float]] = {}

    def _add(raw_val: str, id_type: str, weight: float) -> None:
        raw_clean = raw_val.strip().strip("`").strip()
        if not raw_clean or len(raw_clean) < 2 or len(raw_clean) > 80:
            return
        norm = normalize_identifier(raw_clean)
        if not norm or norm in STOPWORDS:
            return
        existing = found.get(raw_clean)
        if existing is None or existing[3] < weight:
            found[raw_clean] = (raw_clean, norm, id_type, weight)

    combined = f"{title}\n{text}"

    if N_PLUS_ONE_RE.search(combined):
        _add("N+1", "concept", 2.5)
        _add("n_plus_one", "concept", 2.5)

    for m in KEYWORD_SYM_RE.finditer(combined):
        val = re.sub(r":\s+:", ": :", m.group(1))
        _add(val, "option", 3.0)

    for m in NAMESPACE_RE.finditer(combined):
        _add(m.group(1), "class", 3.0)

    for m in CAMEL_CLASS_RE.finditer(combined):
        _add(m.group(1), "class", 2.2)

    for m in SNAKE_IDENT_RE.finditer(combined):
        token = m.group(1)
        w = 2.8 if token in title.lower() else 2.0
        _add(token, "method", w)

    for m in METHOD_BANG_Q_RE.finditer(combined):
        _add(m.group(1), "method", 2.2)

    for m in HASH_METHOD_RE.finditer(combined):
        _add(m.group(1), "method", 2.2)

    for m in SYMBOL_RE.finditer(combined):
        _add(m.group(1), "option", 1.6)

    for m in BACKTICK_RE.finditer(combined):
        snippet = m.group(1).strip()
        if " " not in snippet or KEYWORD_SYM_RE.fullmatch(snippet):
            _add(snippet, "symbol", 2.6)

    if extra_concepts:
        for c in extra_concepts:
            _add(c, "concept", 2.5)

    return list(found.values())


def normalize_text_for_fts(text: str, identifiers: List[Tuple[str, str, str, float]]) -> str:
    """Create the expanded normalized_identifiers string indexed in FTS5."""
    tokens: List[str] = []
    seen: Set[str] = set()
    for raw, norm, _, _ in identifiers:
        for v in [raw.lower(), norm] + sorted(identifier_variants(raw)):
            if v not in seen:
                seen.add(v)
                tokens.append(v)
    if N_PLUS_ONE_RE.search(text):
        for v in ["n_plus_one", "n1", "eager_loading"]:
            if v not in seen:
                seen.add(v)
                tokens.append(v)
    return " ".join(tokens)


def build_fts5_match_expression(query: str) -> Tuple[str, List[str], List[str]]:
    """Build a safe FTS5 MATCH expression and extract exact/normalized query identifiers.

    Returns:
        (fts_match_expr, raw_identifiers, normalized_identifiers)
    """
    q = query.strip()
    if not q:
        return ("", [], [])

    extracted = extract_technical_identifiers(q, title=q)
    raw_idents = [item[0] for item in extracted]
    norm_idents = list(dict.fromkeys(item[1] for item in extracted))

    # Also capture simple word tokens
    q_for_words = N_PLUS_ONE_RE.sub(" n_plus_one ", q)
    raw_words = re.findall(r"[A-Za-z0-9_#?!]+", q_for_words.lower())
    meaningful_words = [
        w.lstrip("#") for w in raw_words
        if len(w.lstrip("#")) >= 2 and w.lstrip("#") not in STOPWORDS
    ]
    if not meaningful_words and raw_words:
        meaningful_words = [w.lstrip("#") for w in raw_words if len(w.lstrip("#")) >= 2]

    fts_terms: List[str] = []
    seen_terms: Set[str] = set()

    for ident in norm_idents:
        clean_ident = re.sub(r"[^a-z0-9_?!]", "", ident.lower())
        if clean_ident and clean_ident not in seen_terms:
            seen_terms.add(clean_ident)
            fts_terms.append(f'"{clean_ident}"')

    for word in meaningful_words:
        clean_word = re.sub(r"[^a-z0-9_?!]", "", word.lower())
        if clean_word and clean_word not in seen_terms:
            seen_terms.add(clean_word)
            fts_terms.append(f'"{clean_word}"')
            # Add normalized form without trailing ? or !
            if clean_word.endswith("?") or clean_word.endswith("!"):
                stem = clean_word[:-1]
                if len(stem) >= 2 and stem not in seen_terms:
                    seen_terms.add(stem)
                    fts_terms.append(f'"{stem}"')

    if not fts_terms:
        return ("", raw_idents, norm_idents)

    # Use OR in FTS5 to recall candidate chunks and rank heavily by multi-term & exact matches
    fts_expr = " OR ".join(fts_terms)
    return (fts_expr, raw_idents, norm_idents)
