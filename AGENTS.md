# AGENTS.md — LogSight contributor guide for AI coding agents

## Architecture

Three Docker Compose services (`compose.yaml` at repo root):

- `db` — PostgreSQL 17, persistent `pgdata` volume, `pg_isready` healthcheck.
- `backend` — built from root `Dockerfile` (uv + FastAPI on :8000). On boot it
  runs `python -m app.migrate` (versioned SQL in `backend/migrations/`) and
  then uvicorn. Health: `GET /api/health`.
- `frontend` — built from `frontend/Dockerfile` (node build → nginx serve on
  :80, `/api/` reverse-proxied to `backend:8000`, SPA fallback).

No background workers: imports are processed synchronously in the upload
request (streamed to temp file, parsed, bulk-loaded via PostgreSQL COPY in
5000-row batches; SQLite fallback uses executemany inserts).

## Directory structure

```text
backend/
  app/
    main.py            # FastAPI app, lifespan, router wiring under /api
    config.py          # pydantic-settings (DATABASE_URL, MAX_UPLOAD_MB)
    database.py        # engine + SessionLocal + get_db dependency
    models.py          # Import, LogEntry, SavedFilter, ErrorGroupState (ORM only; schema owned by migrations/)
    schemas.py         # Pydantic request/response models
    severity.py        # canonical levels + normalize_severity (never discards)
    parsers.py         # streaming plaintext (+syslog/multiline) / JSONL / JSON / CSV parsers
    grouping.py        # deterministic error fingerprinting (timestamps/IPs/ids masked)
    refingerprint.py   # `python -m app.refingerprint`: recompute stored fingerprints after rule changes
    timebuckets.py     # portable date_trunc/strftime bucketing + zero-filling for charts
    search.py          # q-language parser, ILIKE fallback, snippet highlighting
    import_service.py  # upload → temp file + hash → parse (+gzip/zip) → COPY bulk load + progress heartbeats
    migrate.py         # applies backend/migrations/*.sql once each; `--recover` (container boot only) fails interrupted imports
    routers/           # health, imports, logs, dashboard, errors, filters, traces
  migrations/0001_initial.sql … 0008_search_split_tokens.sql
  tests/               # pytest (SQLite override in conftest.py)
frontend/
  src/
    api/client.ts      # axios instance + types + toParams() / apiParams() / exportUrl()
    utils/             # severity.ts, format.ts, highlight.ts (+ vitest files)
    stores/settings.ts # Pinia: theme + page size (localStorage)
    components/        # AppIcon, SeverityBadge, StatusBadge, FilterBar, LogTable,
                       # LogDetails, Pagination, StatCard, TimeChart, TrendSpark,
                       # HistogramBars, EmptyState, PageHeader, TableSkeleton
    views/             # Dashboard, Explorer, Errors, Traces, Imports, SavedFilters, Settings, TraceView
    router/index.ts
samples/               # app.log, app.jsonl, structured.json, events.csv,
                       # syslog.log, trace.jsonl, access.log (manual testing)
```

## Technology stack (preferred stack — do not change without user approval)

Vue 3 + TypeScript + Vite + Pinia + Vue Router · Python + uv + FastAPI +
Pydantic v2 + SQLAlchemy 2 · PostgreSQL 17 · Docker/Compose. No other
framework, database or AI service may be introduced silently.

## Coding conventions

- Backend: type-annotated Python, module docstring per file, routers own
  HTTP concerns while `import_service.py` owns import logic; parsers must
  stream and never raise on bad line content (per-line `ValueError` only for
  malformed JSONL/JSON).
- Search: `q` goes through `search.py` (`parse_search_query`); PostgreSQL uses
  the `ix_log_entries_search` expression GIN index (identical expression in
  `routers/logs.py` and `migrations/0008_search_split_tokens.sql`; the index
  text has `/ . @ :` translated to spaces and `ParsedQuery.websearch_text`
  applies the same split, so words inside paths/e-mails/hosts/IPs match), SQLite uses the `ILIKE` emulation so tests stay
  portable. Snippets are HTML-escaped Python-side with `<mark>` hits only.
  Substring matches go through `search.contains_ci()` (escapes `%`/`_`,
  single bound `ILIKE` pattern) — never build `ilike(f"%{value}%")`.
  PG free-text matching runs in an `id IN (SELECT … OFFSET 0)` subquery — the
  OFFSET is load-bearing (blocks a catastrophic plan flattening); verify with
  EXPLAIN on a large table before touching it.
- Trace handling: `trace_id` / `request_id` are first-class indexed columns,
  extracted from JSON keys, plain `k=v` pairs, CSV headers and syslog
  structured data; `/api/traces/{id}` matches either column.
- Frontend: Composition API + `<script setup lang="ts">`, shared types from
  `api/client.ts`, dark-theme CSS variables in `assets/styles.css`; keep views
  dense, no decorative animation, no emoji.
- Severity handling: always go through `normalize_severity`; store canonical
  values; `UNKNOWN` is a valid stored value, never an error.
- Error grouping: deterministic `fingerprint()` in `grouping.py` only. No
  external AI/clustering APIs. Changing normalisation rules changes stored
  fingerprints: mention `python -m app.refingerprint` in the release notes.
- Time charts: bucket via `app/timebuckets.py` and zero-fill empty buckets so
  x axes stay linear in time (never return only non-empty buckets). Keep the
  newest buckets when capping, and ignore far-future timestamps (beyond
  now + 1 day) for chart ranges/windows (`latest_plausible()`): one
  mis-parsed date must not hide real data.
- Dates from the UI: `datetime-local` values are the user's local time.
  UI state and URLs keep that form; API calls go through `apiParams()`, which
  converts them to UTC ISO instants. Never send raw `datetime-local` values.
- CSS variables: never alias a custom property to itself
  (`--x: var(--x)` is a cycle and invalidates it app-wide).

## Dependency management

- Backend: `uv` with `backend/pyproject.toml` + committed `backend/uv.lock`.
  Add deps with `uv add`, then rebuild the image. Project-local env:
  `backend/.venv` (create with `uv sync`).
- Frontend: npm with `frontend/package.json`. `npm install` / `npm test` /
  `npm run build` (build runs `vue-tsc` typecheck first).

## Development commands

```sh
docker compose up --build          # full stack
docker compose up --build -d      # detached
docker compose logs -f backend
cd backend && uv sync && uv run pytest -q
cd backend && uv run uvicorn app.main:app --reload   # needs local Postgres + DATABASE_URL
cd frontend && npm install && npm run dev            # Vite proxies /api → :8000
cd frontend && npm test && npm run build
```

## Testing commands

- `cd backend && uv run pytest -q` — 68 tests. API tests use an isolated
  in-memory SQLite DB (`tests/conftest.py`); SQLite-only branches (e.g.
  `strftime` timeline bucketing, `ILIKE` search) exist solely to keep these
  tests portable.
- `cd frontend && npm test` — 17 vitest tests.

Never claim tests pass without running them in-session.

## Database conventions

- Schema is owned by `backend/migrations/*.sql`, applied by `app/migrate.py`
  via the `schema_migrations` table. New schema change = new numbered file;
  never edit an applied migration.
- `models.py` must stay compatible with both PostgreSQL (prod) and SQLite
  (tests): no postgres-only column/index constructs in models. Full-text
  search needs no model change (expression GIN index + raw SQL only).
- Counts must reference a table column
  (`with_entities(func.count(LogEntry.id))`) — bare `func.count()` drops the
  FROM clause and returns 1. Timeline bucketing branches on dialect
  (`date_trunc` vs `strftime`).
- `error_group_states.fingerprint` is a standalone PK (no FK to log entries);
  missing state means `open`. Muted fingerprints are excluded from
  `top-errors`, never from the groups list itself.
- FK `log_entries.import_id → imports.id ON DELETE CASCADE`; tests enable the
  SQLite FK pragma to exercise it.

## API conventions

- Routers mounted under `/api`; Swagger at `/api/docs`.
- Explorer filtering/sorting/pagination is server-side; validate `sort`
  (incl. `relevance`), `direction`, `severity` and error `status` with 400s,
  never 500s. Page cap: 500 rows. `sort=relevance` falls back to newest-first
  when there is no `q` or no tsvector (SQLite). `/logs`, `/logs/export` and
  `/logs/histogram` share the `log_filters` dependency — add new filters
  there so all three stay consistent. Export streams one query via
  `yield_per` (no OFFSET re-querying), capped at 100,000 rows, with CSV cells
  starting with `= + - @` prefixed by `'` (formula injection).
- Failed imports never keep partial rows (`_mark_failed()` deletes them);
  imports left `processing` by a crash are failed at boot.
- Upload: extension allowlist (`.log .txt .jsonl .ndjson .json .csv`, plus
  `.gz` / `.zip`) + `MAX_UPLOAD_MB` cap (413) applied to raw and decompressed
  bytes, content-hash duplicate detection (`status: "duplicate"`, no
  re-insert), per-line error counting without aborting the import.

## Security requirements

- Treat uploads as untrusted: stream, cap size, validate extension, never
  execute content, never reflect raw errors with secrets.
- Parameterized queries only (SQLAlchemy). No hardcoded credentials; `.env`
  stays out of Git. No auth in v1 — note exposure risk if publishing.

## Restrictions (need explicit user approval)

Changing frameworks/database, adding background workers or auth, replacing
deterministic grouping with AI/semantic clustering, editing applied
migrations, restructuring services. Keep docs (`README.md`, `README.el.md`,
`MANUAL.md`, `AGENTS.md`, `LLM.md`, `.env.example`) synchronized with every change.
