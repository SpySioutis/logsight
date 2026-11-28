-- 0007_entry_seq: original file order of entries within an import.
--
-- Powers "surrounding lines" (GET /api/logs/{id}/context): timestamps tie
-- at second resolution and ids are random UUIDs, so neither preserves the
-- order lines had in the uploaded file.
-- ADD COLUMN without a default is metadata-only in PostgreSQL (no heap
-- rewrite). Rows imported before this migration keep seq NULL; the context
-- endpoint falls back to timestamp order for them. The btree build is over
-- two narrow columns, far cheaper than the 0004 GIN build.

SET LOCAL maintenance_work_mem = '256MB';

ALTER TABLE log_entries ADD COLUMN IF NOT EXISTS seq BIGINT;

CREATE INDEX IF NOT EXISTS ix_log_entries_import_seq ON log_entries (import_id, seq);
