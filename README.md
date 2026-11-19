# ruby-rails-knowledge (`v1.0.0`)

Global Agent Skill and local technical knowledge base for **Ruby** (`3.1`–`3.4`) and **Ruby on Rails** (`6.1`, `7.0`, `7.1`, `7.2`, `8.0`, `edge`), powered by **SQLite**, **FTS5**, a **Ruby/Rails Identifier Index**, and a relational **Knowledge Graph**.

- **Skill Version**: `1.0.0` (see [`VERSION`](./VERSION))
- **Zero External Credentials**: Runs 100% locally with Python standard library (`sqlite3`) and `PyYAML`. No API keys, tokens, or external servers required.
- **Consumer Project Safety**: Detects Ruby/Rails versions in read-only mode (`Gemfile.lock`, `.ruby-version`, `Gemfile`, `config/database.yml`) and never modifies consumer repositories.

---

## 1. Quick Installation

Clone this repository and run the installer:

\x60\x60\x60bash
python3 scripts/install.py
\x60\x60\x60

What the installer does:
1. Installs the Skill globally to `~/.gemini/config/skills/ruby-rails-knowledge/` (Antigravity App/IDE) and `~/.gemini/antigravity-cli/skills/ruby-rails-knowledge/` (if Antigravity CLI is installed).
2. Initializes the persistent SQLite database and documents outside the Skill folder at `~/.local/share/ruby-rails-knowledge/` (plus a sandbox cache mirror at `~/.cache/ruby-rails-knowledge/`).

---

## 2. How to Use (Simple Guide)

### A. Automatic Use by AI Agents
Once installed in `~/.gemini/config/skills/ruby-rails-knowledge/`, Antigravity automatically discovers [`SKILL.md`](./SKILL.md). When you ask a Ruby or Rails question in any project, the agent:
1. Detects your project's exact Ruby and Rails versions (`context detect --project .`).
2. Queries the exact section for that version (`search "<topic>" --project .`).
3. Expands related concepts in the Knowledge Graph and answers with official URLs.

### B. Direct CLI Commands

Set an alias or call `~/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge` directly:

\x60\x60\x60bash
# Check CLI version and database health
~/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge --version
~/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge doctor

# 1. Detect Ruby & Rails versions of the current project
~/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge context detect --project .

# 2. Search using the project's detected version automatically
~/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge search "after_commit" --project .

# 3. Search with explicit technology & version filters (JSON or Markdown output)
~/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge search "includes preload eager_load" \
  --technology rails \
  --version 6.1 \
  --format markdown

# 4. Explore concept relationships in the Knowledge Graph
~/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge graph "active_record_callbacks" --format markdown

# 5. List available sources and versions
~/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge sources list --format markdown
~/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge versions list --format markdown

# 6. Run incremental documentation updates
~/.gemini/config/skills/ruby-rails-knowledge/scripts/ruby-rails-knowledge update
\x60\x60\x60

---

## 3. Running Tests & Benchmarks

\x60\x60\x60bash
# Run automated test suite (20 unit & integration tests)
python3 scripts/run_tests.py

# Run retrieval quality & token-saving benchmark (12 multi-version queries)
python3 scripts/run_benchmark.py
\x60\x60\x60

---

## 4. Repository Structure

\x60\x60\x60text
ruby-rails-knowledge/
├── SKILL.md                  # Agent Skills specification entrypoint (v1.0.0)
├── README.md                 # Simple installation and usage guide
├── VERSION                   # Semantic version (1.0.0)
├── config/
│   └── sources.yml           # Verified official Ruby, Rails, Ecosystem & OWASP sources
├── references/               # Progressive disclosure reference guides
├── schemas/                  # SQLite DDL and JSON output schemas
└── scripts/
    ├── ruby-rails-knowledge  # Executable CLI
    ├── install.py            # Global Skill & XDG data installer
    ├── run_tests.py          # Automated test suite
    ├── run_benchmark.py      # Retrieval benchmark suite
    └── src/                  # Modular Python package (ingestion, storage, retrieval, context, cli)
\x60\x60\x60
