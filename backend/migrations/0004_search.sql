-- 0004_search: expression GIN index for ranked full-text search.
--
-- Deliberately NOT a stored tsvector column: backfilling a generated column
-- rewrites the whole heap (unbounded time/bloat on multi-million-row
-- tables), while an expression index is one bulk build with parallel
-- workers and zero heap changes. Queries in app/routers/logs.py call
-- to_tsvector() with the identical expression so the planner uses it.
-- The SQLAlchemy model needs no change, so tests keep running on SQLite
-- via the ILIKE emulation in app/search.py.

SET LOCAL maintenance_work_mem = '256MB';
SET LOCAL max_parallel_maintenance_workers = '4';

DROP INDEX IF EXISTS ix_log_entries_search_vector;

CREATE INDEX IF NOT EXISTS ix_log_entries_search
    ON log_entries USING gin (
        to_tsvector(
            'english',
            coalesce(message, '') || ' ' ||
            coalesce(service, '') || ' ' ||
            coalesce(source, '') || ' ' ||
            coalesce(trace_id, '') || ' ' ||
            coalesce(request_id, '')
        )
    );
