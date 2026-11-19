# CLI Reference (`ruby-rails-knowledge`)

All commands support `--help` and `--format {json,markdown}` (default: `json`).

## Core Query Commands

### 1. Detect Project Context
\x60\x60\x60bash
ruby-rails-knowledge context detect --project .
\x60\x60\x60
Returns `ruby_version`, `rails_version`, `rails_major_minor`, `database`, `orm`, `test_framework`, `background_jobs`, `relevant_dependencies`, and `version_conflicts`.

### 2. Search Technical Knowledge
\x60\x60\x60bash
ruby-rails-knowledge search "<query>" \
  [--technology {ruby,rails,ecosystem,security}] \
  [--version <version>] \
  [--authority <authority>] \
  [--topic <topic>] \
  [--project <path>] \
  [--limit 5] \
  [--max-chars 2400] \
  [--max-tokens 1800] \
  [--no-graph] \
  [--graph-depth 2] \
  [--format {json,markdown}]
\x60\x60\x60

### 3. Traverse the Knowledge Graph
\x60\x60\x60bash
ruby-rails-knowledge graph "<concept>" \
  [--technology {ruby,rails,ecosystem,security}] \
  [--depth 2] \
  [--max-related 8] \
  [--format {json,markdown}]
\x60\x60\x60

## Administrative & Introspection Commands

- `ruby-rails-knowledge doctor`: Runs SQLite `integrity_check`, `foreign_key_check`, FTS5 verification, and schema migration checks.
- `ruby-rails-knowledge status`: Displays total sources, versions, documents, revisions, chunks, identifiers, concepts, and relationships.
- `ruby-rails-knowledge sources list`: Lists all registered sources and document counts.
- `ruby-rails-knowledge versions list [--technology ruby|rails]`: Lists the version lifecycle matrix.
- `ruby-rails-knowledge ingest [--source <id>] [--version <ver>] [--url <https_url>]`: Ingests documentation.
- `ruby-rails-knowledge update [--source <id>] [--version <ver>] [--url <https_url>]`: Runs incremental SHA-256 hash comparison and atomic updates while preserving `document_versions` history.
- `ruby-rails-knowledge backup [--label <name>]`: Creates an online SQLite backup in `~/.cache/ruby-rails-knowledge/backups/`.
- `ruby-rails-knowledge migrate`: Applies any pending SQLite schema migrations.
