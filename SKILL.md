---
name: ruby-rails-knowledge
version: "1.0.0"
description: >-
  Use this skill whenever answering technical questions, debugging, implementing features,
  or verifying version-specific behavior in Ruby or Ruby on Rails projects. Provides
  fast, version-aware CLI retrieval over official Ruby (3.1-3.4) and Ruby on Rails
  (6.1, 7.0, 7.1, 7.2, 8.0, edge) documentation, technical identifiers, and concept
  relationships without loading entire documentation files into context.
---

# Ruby & Ruby on Rails Knowledge Base (`ruby-rails-knowledge` — v1.0.0)

## 1. Objective

`ruby-rails-knowledge` is a local, version-aware technical knowledge base powered by SQLite, FTS5, an auxiliary Ruby identifier index, and a relational Knowledge Graph. It enables on-demand retrieval of targeted official Ruby and Ruby on Rails documentation excerpts with traceable source URLs and strict version isolation.

**Core rule**: Always invoke the CLI (`scripts/ruby-rails-knowledge`) as a black-box query tool. Do **not** read the internal Python implementation under `scripts/src/` during normal usage.

---

## 2. When to Consult This Skill

Activate and query this knowledge base whenever a task involves:
- Ruby language semantics, Object Model (`BasicObject`, `Module#ancestors`, `prepend`/`include`), `Enumerable`, exceptions, concurrency (`Thread`, `Fiber`, `Ractor`), or memory/GC/YJIT.
- Ruby on Rails APIs: Active Record, callbacks (`after_commit` vs `after_save`), transactions and savepoints (`requires_new: true`), associations (`dependent: :destroy`), querying (`includes` vs `preload` vs `eager_load`, `find_each`, `strict_loading`), connection pooling, Zeitwerk autoloading, Active Job, Active Support, Action Controller, routing, middleware, security, or deprecations.
- Verifying whether an API or behavior exists in a project's specific Ruby or Rails version (e.g., Rails 6.1 vs Rails 7.2/8.0).

---

## 3. Step 1 — Detect the Consumer Project Context

Before querying documentation for a repository, detect its Ruby and Rails versions (read-only, priority: `Gemfile.lock` > `.ruby-version` > `Gemfile` > `config/`):

\x60\x60\x60bash
~/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge context detect --project .
\x60\x60\x60

*(If using Antigravity CLI, replace `~/.gemini/config/skills/...` with `~/.gemini/antigravity-cli/skills/...` or invoke `./scripts/ruby-rails-knowledge` relative to this skill directory.)*

---

## 4. Step 2 — Search Technical Knowledge

Run targeted lexical + identifier queries using the `search` command:

\x60\x60\x60bash
# Automatically filter by the detected consumer project version
~/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge search "after_commit" --project .

# Or pass explicit technology and version filters
~/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge search "includes preload eager_load" \
  --technology rails \
  --version 6.1 \
  --limit 3
\x60\x60\x60

Punctuation-heavy Ruby/Rails identifiers (`after_commit`, `find_each`, `dependent: :destroy`, `strict_loading`, `ActiveRecord::Relation`, `N+1`) are indexed directly.

---

## 5. Step 3 — Apply Filters and Context Budgets

Use flags to constrain scope and protect your context window:
- `--technology {ruby,rails,ecosystem,security}`: Restrict to Ruby, Rails, complementary ecosystem (`rubocop`, `rspec`, `rubystyle`), or `security` (OWASP).
- `--version <X.Y|edge>`: Enforce strict version matching (`6.1`, `7.0`, `7.1`, `7.2`, `8.0`, `edge` for Rails; `3.1`, `3.2`, `3.3`, `3.4` for Ruby).
- `--authority {official,official_edge,ecosystem_official,community_standard,security_standard}`: Filter by authority class.
- `--topic <topic>`: Filter by domain topic (`active_record`, `callbacks`, `transactions`, `queries`, `associations`, `autoloading`, `enumerable`, `concurrency`, etc.).
- `--limit <K>`, `--max-chars <N>`, `--max-tokens <N>`: Bound excerpt count and token footprint.
- `--format {json,markdown}`: Use `json` (default) for structured parsing or `markdown` for human-readable output.

---

## 6. Step 4 — Explore Related Concepts in the Knowledge Graph

Search results include grounded `graph_relations`. To explore a concept's neighborhood (`RELATED_TO`, `PART_OF`, `ALTERNATIVE_TO`, `DEPENDS_ON`, `INTRODUCED_IN`, `DEPRECATED_IN`, `REPLACED_BY`, `DOCUMENTED_IN`) directly:

\x60\x60\x60bash
~/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge graph "active_record_callbacks" --depth 2 --max-related 8
\x60\x60\x60

---

## 7. How to Interpret Sources, Authorities, and Versions

1. **Authority Separation**: Never present community or ecosystem conventions (`community_standard`, `ecosystem_official`) as official Ruby or Rails core behavior (`official`).
2. **Version Fidelity**: Historical/EOL versions (such as Rails `6.1` or Ruby `3.1`) remain preserved for legacy repositories. Prefer compatibility with the consumer project's detected version over newer releases.
3. **Edge Isolation**: Documentation with `authority: official_edge` (`version: edge`) represents unreleased changes and is excluded from default queries unless `--version edge` is explicitly passed.

---

## 8. How to Present References

When answering the user using evidence from this skill, always cite:
- The **Technology and Version** (e.g., *Rails 6.1* or *Ruby 3.3*).
- The **Document Title and Section** (`title` / `source_section`).
- The **Original Official URL** (`source_url`) as a clickable link.

---

## 9. Operational Scripts & Progressive References

- **CLI Quick Reference & Output Schemas**: Read [references/cli-reference.md](./references/cli-reference.md)
- **Sources Catalog & Version Compatibility Matrix**: Read [references/sources-and-versions.md](./references/sources-and-versions.md)
- **Health Checks, Incremental Updates & Backups**: Read [references/operations-and-updates.md](./references/operations-and-updates.md)

---

## 10. Acting Under Insufficient Documentation or Version Fallback

- Check `metadata.version_notice` in the JSON response. If the requested version has no dedicated documentation (e.g. Rails `8.1`), the engine falls back to the nearest documented version and sets `version_notice`.
- **Never claim version compatibility without explicit evidence.** If a result comes from a fallback version or returns `total_results: 0`, explicitly state that limitation to the user.
