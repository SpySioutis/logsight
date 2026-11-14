-- 0002_trgm: trigram index to keep full-text search fast on large tables.
-- Requires the pg_trgm extension.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

DROP INDEX IF EXISTS ix_log_entries_message_trgm;
CREATE INDEX IF NOT EXISTS ix_log_entries_message_trgm
    ON log_entries USING gin (message gin_trgm_ops);
