-- 0008_search_split_tokens: make words inside paths, URLs, e-mails and
-- hostnames searchable.
--
-- PostgreSQL's default text parser keeps "/api/checkout",
-- "user@example.com", "db.internal" and "10.0.0.5" as single tokens, so
-- searching "checkout" or "example" found nothing on PostgreSQL while the
-- SQLite ILIKE emulation (tests) did. The indexed text now has / . @ :
-- translated to spaces; app/search.py applies the same translation to
-- query terms (multi-part terms become phrases, so "10.0.0.5" still
-- matches exactly that address). The expression must stay identical to
-- _SEARCH_VECTOR_EXPR in app/routers/logs.py.
--
-- One-time GIN rebuild, like 0004 (~25 s per million rows measured on a
-- laptop; the API is unavailable meanwhile). Runs in one transaction: if
-- interrupted, the old index stays and the build retries on next boot.

SET LOCAL maintenance_work_mem = '256MB';
SET LOCAL max_parallel_maintenance_workers = '4';

DROP INDEX IF EXISTS ix_log_entries_search;

CREATE INDEX ix_log_entries_search
    ON log_entries USING gin (
        to_tsvector(
            'english',
            translate(
                coalesce(message, '') || ' ' ||
                coalesce(service, '') || ' ' ||
                coalesce(source, '') || ' ' ||
                coalesce(trace_id, '') || ' ' ||
                coalesce(request_id, ''),
                '/.@:',
                '    '
            )
        )
    );

-- Expression-index statistics are only gathered by ANALYZE; without them
-- the planner assumes a fixed selectivity for every search term (measured:
-- 2M-row semi-join planned as 10k-row nested loop, 15 s instead of 11 s).
-- Sampling-based, ~1 s on 2M rows; allowed inside the migration transaction.
ANALYZE log_entries;
