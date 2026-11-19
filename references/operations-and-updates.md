# Operations, Data Directories & Incremental Updates

## Data and Cache Separation

- **Primary Data Directory**: `~/.local/share/ruby-rails-knowledge/` (configurable via `RUBY_RAILS_KNOWLEDGE_DATA_DIR`)
  - `database/knowledge.sqlite3`
  - `documents/{ruby,rails,ecosystem,security}/`
  - `manifests/{sources.json,versions.json}`
  - `metadata/{ingestion-history.json,database-version.json}`
- **Cache & Sandbox Mirror**: `~/.cache/ruby-rails-knowledge/` (configurable via `RUBY_RAILS_KNOWLEDGE_CACHE_DIR`)

## Manual & Externally Scheduled Incremental Updates

Updates are executed on-demand via:
\x60\x60\x60bash
~/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge update
\x60\x60\x60

If the user wishes to schedule periodic external updates via cron (e.g. weekly on Sundays at 03:00):
\x60\x60\x60cron
0 3 * * 0 $HOME/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge update >> $HOME/.cache/ruby-rails-knowledge/update.log 2>&1
\x60\x60\x60
