-- 0001_initial: core tables for imports, log entries and saved filters.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS imports (
    id VARCHAR(36) PRIMARY KEY,
    filename VARCHAR(1024) NOT NULL,
    file_size BIGINT NOT NULL DEFAULT 0,
    file_hash VARCHAR(64) NOT NULL,
    format VARCHAR(16) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'completed',
    total_lines BIGINT NOT NULL DEFAULT 0,
    parsed_count BIGINT NOT NULL DEFAULT 0,
    error_count BIGINT NOT NULL DEFAULT 0,
    duplicate_of VARCHAR(36),
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_imports_file_hash ON imports (file_hash);

CREATE TABLE IF NOT EXISTS log_entries (
    id VARCHAR(36) PRIMARY KEY,
    import_id VARCHAR(36) NOT NULL REFERENCES imports (id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ,
    severity VARCHAR(16) NOT NULL,
    service VARCHAR(256),
    source VARCHAR(512),
    message TEXT NOT NULL,
    raw TEXT,
    attributes JSONB,
    fingerprint VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_log_entries_import_id ON log_entries (import_id);
CREATE INDEX IF NOT EXISTS ix_log_entries_timestamp ON log_entries (timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_log_entries_severity ON log_entries (severity);
CREATE INDEX IF NOT EXISTS ix_log_entries_service ON log_entries (service);
CREATE INDEX IF NOT EXISTS ix_log_entries_source ON log_entries (source);
CREATE INDEX IF NOT EXISTS ix_log_entries_fingerprint ON log_entries (fingerprint);

CREATE TABLE IF NOT EXISTS saved_filters (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(256) NOT NULL UNIQUE,
    description TEXT,
    params JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
