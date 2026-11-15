-- 0006_dashboard_indexes: composite covering indexes for dashboard aggregates.
--
-- The dashboard summary/timeline/top-errors endpoints aggregate millions of
-- rows on every page load. Single-column indexes already exist, but two
-- access patterns had no efficient path:
-- - timeline groups by date_trunc(timestamp) and counts error severities, so
--   a (timestamp, severity) covering index lets PostgreSQL serve it as an
--   index-only scan without touching the wide heap (message/raw/attributes).
-- - top-errors filters severity IN (...) and groups by fingerprint, served
--   by a (severity, fingerprint) composite.
-- Plain CREATE INDEX (not CONCURRENTLY): migrate.py applies each file inside
-- a transaction, where CONCURRENTLY is forbidden. IF NOT EXISTS keeps
-- re-runs safe. Pure index build: no heap rewrite, no backfill.

SET LOCAL maintenance_work_mem = '256MB';

CREATE INDEX IF NOT EXISTS ix_log_entries_timestamp_severity
    ON log_entries (timestamp DESC, severity);

CREATE INDEX IF NOT EXISTS ix_log_entries_severity_fingerprint
    ON log_entries (severity, fingerprint);
