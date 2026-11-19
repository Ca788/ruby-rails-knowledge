-- ruby-rails-knowledge SQLite Schema (v1)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    technology TEXT NOT NULL,
    authority TEXT NOT NULL,
    source_type TEXT NOT NULL,
    base_url TEXT NOT NULL,
    versioned INTEGER NOT NULL DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS versions (
    id TEXT PRIMARY KEY, -- e.g. 'rails:6.1', 'ruby:3.3'
    technology TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL, -- 'eol', 'security_maintenance', 'maintenance', 'stable', 'current_stable', 'edge', 'unavailable'
    docs_available INTEGER NOT NULL DEFAULT 1,
    is_latest_stable INTEGER NOT NULL DEFAULT 0,
    release_date TEXT,
    eol_date TEXT,
    docs_url TEXT,
    notes TEXT,
    UNIQUE(technology, version)
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    technology TEXT NOT NULL,
    version TEXT NOT NULL,
    topic TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    local_path TEXT NOT NULL,
    authority TEXT NOT NULL,
    current_hash TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_documents_tech_ver ON documents(technology, version);
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source_id);
CREATE INDEX IF NOT EXISTS idx_documents_topic ON documents(topic);

CREATE TABLE IF NOT EXISTS document_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    previous_hash TEXT,
    change_type TEXT NOT NULL, -- 'created', 'updated', 'unchanged', 'removed'
    captured_at TEXT NOT NULL,
    snapshot_path TEXT,
    summary TEXT,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    UNIQUE(document_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_doc_versions_doc ON document_versions(document_id);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    technology TEXT NOT NULL,
    version TEXT NOT NULL,
    topic TEXT NOT NULL,
    subtopic TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    normalized_identifiers TEXT NOT NULL DEFAULT '',
    authority TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_section TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    char_count INTEGER NOT NULL DEFAULT 0,
    estimated_tokens INTEGER NOT NULL DEFAULT 0,
    section_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_chunks_tech_ver ON knowledge_chunks(technology, version);
CREATE INDEX IF NOT EXISTS idx_chunks_topic ON knowledge_chunks(topic, subtopic);
CREATE INDEX IF NOT EXISTS idx_chunks_authority ON knowledge_chunks(authority);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON knowledge_chunks(document_id);

-- FTS5 Virtual Table for Lexical Search
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts USING fts5(
    chunk_id UNINDEXED,
    title,
    source_section,
    topic,
    subtopic,
    normalized_identifiers,
    content,
    tokenize='unicode61 tokenchars ''_:#?!'''
);

-- Auxiliary index for technical Ruby/Rails identifiers (exact & normalized lookup)
CREATE TABLE IF NOT EXISTS chunk_identifiers (
    chunk_id TEXT NOT NULL,
    identifier TEXT NOT NULL,
    normalized_identifier TEXT NOT NULL,
    identifier_type TEXT NOT NULL DEFAULT 'symbol', -- 'method', 'class', 'option', 'callback', 'concept'
    weight REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (chunk_id, identifier),
    FOREIGN KEY (chunk_id) REFERENCES knowledge_chunks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunk_identifiers_exact ON chunk_identifiers(identifier);
CREATE INDEX IF NOT EXISTS idx_chunk_identifiers_norm ON chunk_identifiers(normalized_identifier);

-- Knowledge Graph: Concepts
CREATE TABLE IF NOT EXISTS concepts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    technology TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    UNIQUE(technology, name)
);

CREATE INDEX IF NOT EXISTS idx_concepts_name ON concepts(name);
CREATE INDEX IF NOT EXISTS idx_concepts_tech ON concepts(technology);

-- Knowledge Graph: Chunk <-> Concept mapping
CREATE TABLE IF NOT EXISTS chunk_concepts (
    chunk_id TEXT NOT NULL,
    concept_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'primary', -- 'primary', 'mentioned'
    PRIMARY KEY (chunk_id, concept_id),
    FOREIGN KEY (chunk_id) REFERENCES knowledge_chunks(id) ON DELETE CASCADE,
    FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunk_concepts_concept ON chunk_concepts(concept_id);

-- Knowledge Graph: Directed Relationships between Concepts
CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    source_concept_id TEXT NOT NULL,
    target_concept_id TEXT NOT NULL,
    relation_type TEXT NOT NULL CHECK (
        relation_type IN (
            'RELATED_TO',
            'PART_OF',
            'ALTERNATIVE_TO',
            'DEPENDS_ON',
            'INTRODUCED_IN',
            'DEPRECATED_IN',
            'REPLACED_BY',
            'DOCUMENTED_IN'
        )
    ),
    technology TEXT NOT NULL,
    version_scope TEXT NOT NULL DEFAULT 'all',
    evidence_chunk_id TEXT,
    source_url TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (source_concept_id) REFERENCES concepts(id) ON DELETE CASCADE,
    FOREIGN KEY (target_concept_id) REFERENCES concepts(id) ON DELETE CASCADE,
    FOREIGN KEY (evidence_chunk_id) REFERENCES knowledge_chunks(id) ON DELETE SET NULL,
    UNIQUE(source_concept_id, target_concept_id, relation_type, version_scope)
);

CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_concept_id);
CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target_concept_id);
CREATE INDEX IF NOT EXISTS idx_rel_type ON relationships(relation_type);

-- Ingestion & Update Audit Log
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id TEXT PRIMARY KEY,
    run_type TEXT NOT NULL, -- 'ingest', 'update', 'seed'
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL, -- 'running', 'completed', 'partial_failure', 'failed'
    source_filter TEXT,
    version_filter TEXT,
    docs_checked INTEGER NOT NULL DEFAULT 0,
    docs_added INTEGER NOT NULL DEFAULT 0,
    docs_updated INTEGER NOT NULL DEFAULT 0,
    docs_unchanged INTEGER NOT NULL DEFAULT 0,
    docs_failed INTEGER NOT NULL DEFAULT 0,
    chunks_indexed INTEGER NOT NULL DEFAULT 0,
    error_log TEXT,
    summary_json TEXT
);
