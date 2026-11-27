# LLM.md — LogSight project briefing for AI coding agents

> Read this file first when working on LogSight. It is the detailed,
> LLM-oriented companion to `AGENTS.md` (contributor rules), `README.md`
> (overview), and `MANUAL.md` (operations). If this file contradicts
> `AGENTS.md`, `AGENTS.md` wins.

## 1. What LogSight is

LogSight is a **self-hosted log analysis platform**. Users upload application
log files through a web UI; the backend parses them into structured rows in
PostgreSQL; the UI then offers search, filtering, dashboards, error grouping,
trace timelines, and saved filter presets. There is no log shipper, no
background worker, and no authentication — uploads are processed
synchronously inside the HTTP request.

Feature summary (v1 + search/traces/lifecycle release):

- **Import**: `.log`, `.txt` (plain text incl. RFC 5424 syslog and multiline
  stacktraces), `.jsonl`/`.ndjson`, `.json`, `.csv`; `.gz` single files and
  `.zip` bundles; duplicate detection by SHA-256 content hash.
- **Explorer**: server-side search with a query language (`"exact phrase"`,
  `-exclude`, `service:`/`source:`/`severity:`/`trace:`/`request:`), plus
  severity/source/service/trace/request/date filters, sorting (incl.
  relevance), pagination, highlighted `<mark>` snippets, result-set volume
  histogram (click a bar to zoom the date range), CSV/JSONL export of all
  matches (≤100k), entry drawer with surrounding lines in original file order.
- **Dashboard**: totals, severity distribution, logs-over-time (All =
  adaptive full history, Day/Hour = last 60 buckets, zero-filled), top sources,
  top errors (muted groups excluded).
- **Errors**: deterministic fingerprint grouping with open/acknowledged/
  resolved/muted lifecycle, assignee, note, per-group trend sparkline.
- **Traces**: `trace_id`/`request_id` extracted at import; timeline view per
  trace across services.
- **Saved filters**: named, reusable search presets (CRUD).

## 2. System architecture

Three Docker Compose services (`compose.yaml`, project name `logsight`):

| Service    | Image / build                                  | Port                    | Health                            |
|------------|------------------------------------------------|-------------------------|-----------------------------------|
| `db`       | `postgres:17.7`, volume `pgdata`               | internal `5432`         | `pg_isready`                      |
| `backend`  | root `Dockerfile` (uv + FastAPI, runs as uid 10001) | `${BACKEND_PORT:-8000}:8000` | `GET /api/health` (runs `SELECT 1`) |
| `frontend` | `frontend/Dockerfile` (node build → nginx)     | `${FRONTEND_PORT:-8080}:80`  | `depends_on backend healthy`      |

Request flow: browser → nginx `:80` → `/api/*` reverse-proxied to
`backend:8000`, everything else serves the SPA (`index.html` fallback, so
client-side routes like `/traces/:id` work on refresh).

Boot sequence (important): the backend container runs
`python -m app.migrate` **before** uvicorn. Migrations must fully apply or
the API never starts. `restart: unless-stopped` means a **failing migration
causes a crash loop** (container exits → Docker restarts it → migration
retries). Never write a migration that cannot complete; on a large table,
prefer index builds over heap rewrites (see §6).

Data flow for an upload:

```
browser --multipart--> POST /api/imports/upload
  -> import_service.import_upload():
     stream to temp file (1 MB chunks, MAX_UPLOAD_MB cap, SHA-256)
     -> duplicate check by hash -> parse (streaming) -> batch INSERT (1000 rows)
  -> { import record, duplicate: bool }
```

## 3. Repository layout

```text
logsight/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, CORS *, lifespan logging, router wiring
│   │   ├── config.py          # pydantic-settings: DATABASE_URL, MAX_UPLOAD_MB (+ property max_upload_bytes)
│   │   ├── database.py        # engine, Base, SessionLocal, get_db dependency
│   │   ├── models.py          # ORM ONLY: Import, LogEntry, SavedFilter, ErrorGroupState
│   │   ├── schemas.py         # Pydantic v2 request/response models
│   │   ├── severity.py        # canonical severities + normalize_severity() (never discards)
│   │   ├── grouping.py        # normalize_message() + fingerprint() (SHA-256, 32 hex chars)
│   │   ├── refingerprint.py   # maintenance: recompute stored fingerprints + carry lifecycle state
│   │   ├── timebuckets.py     # portable bucketing (date_trunc / strftime) + zero-fill helpers
│   │   ├── parsers.py         # streaming parsers -> ParsedEntry (never raise on line content)
│   │   ├── search.py          # q-language parser, SQLite ILIKE emulation, snippet highlighting
│   │   ├── import_service.py  # upload -> temp+hash -> decompress -> parse -> batch insert
│   │   ├── migrate.py         # versioned *.sql runner via schema_migrations table + interrupted-import recovery
│   │   └── routers/           # health, imports, logs, dashboard, errors, filters, traces
│   ├── migrations/            # 0001_initial … 0008_search_split_tokens (see §6)
│   ├── tests/                 # pytest, 68 tests, isolated in-memory SQLite per test
│   ├── pyproject.toml + uv.lock
│   └── .venv/                 # local env (gitignored), created by `uv sync`
├── frontend/
│   ├── src/
│   │   ├── api/client.ts      # axios instance, shared TS interfaces, toParams(), apiParams() (local→UTC dates), exportUrl()
│   │   ├── utils/             # severity.ts, format.ts, highlight.ts (+ *.test.ts; 17 vitest tests incl. api/client.test.ts)
│   │   ├── stores/settings.ts # Pinia: theme + pageSize + sidebar, persisted to localStorage
│   │   ├── assets/styles.css  # design system: dark-first tokens, light theme, all components
│   │   ├── components/        # AppIcon (inline Lucide set), SeverityBadge, StatusBadge,
│   │   │                      # FilterBar, LogTable, LogDetails, Pagination, StatCard,
│   │   │                      # TimeChart, HistogramBars, TrendSpark, EmptyState, PageHeader, TableSkeleton
│   │   ├── views/             # Dashboard, Explorer, Errors, Traces, Imports, SavedFilters,
│   │   │                      # Settings, TraceView
│   │   ├── router/index.ts    # /, /logs, /errors, /traces, /imports, /filters, /settings, /traces/:id
│   │   ├── App.vue            # shell: collapsible sidebar + topbar + <RouterView/>
│   │   └── main.ts            # app bootstrap (pinia, router)
│   ├── nginx.conf             # /api/ proxy + SPA fallback
│   └── package.json           # dev/build/test scripts (vue-tsc typecheck in build)
├── samples/                   # app.log, app.jsonl, structured.json, events.csv,
│                              # syslog.log, trace.jsonl, access.log (manual testing + curl validation)
├── compose.yaml, Dockerfile
├── start.sh / start.command / start.bat   # OS launchers (just run compose up --build)
├── README.md, README.el.md (Greek mirror — update BOTH), MANUAL.md,
│   AGENTS.md, LLM.md (this file), .env.example, LICENSE (MIT)
```

## 4. Backend guide

### 4.1 Module responsibilities

- **`main.py`**: creates `FastAPI(docs_url="/api/docs")`, permissive CORS,
  includes all routers with `prefix="/api"`. No business logic.
- **`config.py`**: `Settings` with `database_url` (default points at
  localhost for dev; compose injects the `db` host variant) and
  `max_upload_mb` (default 1024). Single global `settings` instance.
- **`database.py`**: sync SQLAlchemy 2 engine (`pool_pre_ping=True`),
  declarative `Base`, `get_db` generator dependency. Endpoints are `def`
  (sync), not `async def`.
- **`models.py`**: must compile on **both PostgreSQL and SQLite** — no
  postgres-only column types (JSON uses `JSON().with_variant(JSONB,
  "postgresql")`). Schema truth lives in `migrations/*.sql`, not here.
  Tables: `imports`, `log_entries` (Ü `trace_id`, `request_id` indexed),
  `saved_filters`, `error_group_states` (PK = fingerprint, no FK by design;
  missing row means `open`).
- **`schemas.py`**: response models mirror ORM + computed fields
  (`LogEntryOut.snippet`, `ErrorGroup.status/assignee/note`,
  `TraceDetail`, `ErrorTrendPoint`, `TopError.status`).
- **`severity.py`**: canonical set
  `TRACE DEBUG INFO WARN WARNING ERROR FATAL CRITICAL UNKNOWN`.
  `normalize_severity()` accepts aliases (`warn`, `err`, `crit`, `alert`,
  …), numeric levels (Python logging thresholds), numeric strings;
  anything else → `UNKNOWN`. **Never** raise or drop on unknown input.
- **`grouping.py`**: `normalize_message()` lowercases and masks volatile
  tokens (pure-digit tokens are always `<n>` whatever their length — hex
  masks require an a–f letter; `<ts>` for ISO / syslog / clock timestamps — applied first, since
  in `2024-05-01t10:00` the hour is glued to the `t` and escapes the
  `\b`-anchored number rules — then `<uuid> <ip> <hex> <n>`, long quoted
  strings) so recurring errors share one `fingerprint()` (SHA-256 hex,
  truncated to 32 chars). Plaintext messages keep the full line (timestamp
  and level included), so timestamp masking is essential.
  Deterministic only — no AI/clustering, ever, without user approval.
  Rule changes alter stored fingerprints → `python -m app.refingerprint`
  (batched, idempotent, carries `error_group_states` to the new key).
- **`timebuckets.py`**: `trunc_expr(dialect, label)` (`date_trunc(label,
  timezone('UTC', ts))` — explicit UTC, independent of the PG session
  TimeZone — / `strftime`), `as_utc()` key normalisation, `zero_filled()`. Every time
  chart (dashboard timeline, error trend, explorer histogram) returns
  zero-filled buckets so x axes are linear in time; capped ranges keep the
  newest buckets; `latest_plausible()` (newest timestamp ≤ now + 1 day)
  anchors Day/Hour windows and trends, and the histogram plots only up to
  that horizon when such data exists (far-future mis-parses stay listed,
  just not plotted). Bucket stepping is overflow-safe at year 9999.
- **`parsers.py`**: yields `ParsedEntry(timestamp, severity, service,
  source, message, raw, attributes, fingerprint, trace_id, request_id)`.
  - `parse_plain_line()`: never raises; tries RFC 5424 syslog first, then
    regex level + timestamp + `k=v` extraction (service/app, source/logger/
    host/…, trace/request/correlation/span ids).
  - Access logs (common/combined format): `"METHOD path HTTP/x" status`
    → attributes `http_method`/`http_path`/`http_status`; with no explicit
    level, severity comes from the status (5xx ERROR, 4xx WARNING, else
    INFO). An explicit level only counts *before* the quoted request and
    only as a standalone uppercase word (`_ACCESS_LEVEL_RE`), so paths,
    referrers, user agents, vhosts (`error.example.com`) and user names
    never become severities.
  - `parse_timestamp()`: also CLF `[01/May/2024:12:00:00 +0200]` and
    slash dates `2024/05/01 12:00:00` (nginx error log, Go). JSON/CSV
    values additionally accept numeric-string epochs (s/ms/µs) and RFC 2822
    (`Wed, 01 May 2024 12:00:00 GMT`). ISO 8601 keeps its UTC offset (`Z`, `+02:00`,
    `+0200`, `+02`; naive → UTC); year-less syslog stamps get the latest
    year that is not in the future (`Feb 29` handled via a leap year).
  - `parse_syslog_line()`: `<PRI>1 TS HOST APP PROC MSGID [SD] MSG`;
    severity from `PRI % 8`; trace/request ids from structured-data params.
    Returns `None` when the line is not syslog (caller falls back).
  - Multiline: `is_continuation_line()` (leading-whitespace `at …`,
    `File …`, `Caused by`, `...`, `Traceback…`) + `append_continuation()`
    (joins with `\n`, caps at 64 KB, recomputes fingerprint).
  - `parse_json_object()` / `parse_json_line()`: wide key-alias tables
    (incl. `traceId`, `requestId`, epoch/ms/us timestamps); blank line →
    `None`; malformed JSON → `ValueError` (counted, import continues).
  - `parse_csv_row()`: reuses the JSON field mapping (headers are keys).
  - `iter_json_array()`: single-document `.json` (object or array);
    malformed document → `ValueError` (fails the whole import → HTTP 422).
- **`search.py`**: `parse_search_query(q)` tokenizes
  `word`, `"phrase"`, `-negation`, `field:value` (fields: service, source,
  severity/level, trace/trace_id, request/request_id; negatable too).
  `websearch_text` rebuilds the free-text part for
  `websearch_to_tsquery`. `apply_ilike_search()` is the portable SQLite
  emulation. `highlight_snippet()` returns HTML-escaped text with only
  `<mark>` tags (max 280 chars, windowed on first hit).
- **`import_service.py`**: `detect_format()` (strips `.gz`; `.zip` is a
  bundle); streams upload to temp (raw cap 413); SHA-256 duplicate check
  (`status: "duplicate"`, references original, no re-insert); `.gz` →
  gunzip-to-temp with decompressed cap (zip-bomb guard);
  `.zip` → per-member format detection, skips dotfiles/dirs/unsupported,
  422 if no supported members; `_Parser` accumulates `ParsedEntry`s and
  flushes every 5000 rows via PostgreSQL `COPY FROM STDIN` (CSV buffer;
  `created_at` set explicitly per batch; `SET LOCAL synchronous_commit
  TO OFF` per bulk transaction; SQLite tests use the executemany
  fallback). Fingerprints are computed only for error-like severities
  (60% of parse CPU otherwise; `NULL` for the rest).
  `total_lines` counts physical lines,
  `parsed_count` logical entries (multiline joining reduces the latter).
  For live progress, the total-line estimate (fast newline count, committed
  upfront; 0 = unknown, e.g. single-doc JSON) and per-batch `parsed_count`
  heartbeats are committed during the parse, so polling `GET /imports`
  sees percent-complete while `status` is `"processing"`.
  Any failure mid-parse (`ValueError` → 422, decompressed-cap 413, or an
  unexpected error) goes through `_mark_failed()`: rollback, delete the
  rows already flushed for that import, `status: "failed"`. A failed
  import therefore never leaves partial data behind.
- **`migrate.py`**: applies `migrations/*.sql` in filename order inside
  one transaction per file, records versions in `schema_migrations`.
  Idempotent; safe to run every boot. With `--recover` (only passed by the
  Dockerfile CMD, never when run by hand against a live server), `recover()` calls
  `recover_interrupted_imports()`: any import still `processing` at boot
  (server crashed/restarted mid-upload) is marked `failed` and its partial
  rows removed. Safe because imports only run inside the single API
  process, which has not started yet.

### 4.2 Endpoint reference (all under `/api`)

| Method & path | Purpose | Key params / body |
|---|---|---|
| `GET /health` | liveness + `SELECT 1` DB check | — |
| `POST /imports/upload` | multipart upload → 201 (or 400/413/422) | `file`; errors: 400 type, 413 size, 422 parse failure |
| `GET /imports`, `GET /imports/{id}`, `DELETE /imports/{id}` | history / detail / delete (204, cascades to entries) | — |
| `GET /logs` | explorer page | `q`, `severity[]`, `source`, `service`, `import_id`, `trace_id`, `request_id`, `fingerprint` (exact, = one error group), `date_from/to`, `sort` (timestamp/severity/source/service/**relevance**), `direction`, `page`, `page_size` (≤500) |
| `GET /logs/export` | stream all matches as CSV or JSONL (attachment); one `yield_per` server-side-cursor query, ≤100k rows; CSV cells starting `= + - @` get a `'` prefix | same filters as `/logs` + `format` (csv/jsonl, 400 otherwise), `sort`, `direction`, `limit` |
| `GET /logs/histogram` | zero-filled counts (total + errors) over time for the filters; bucket adapts to span: ≤3 h minute, ≤7 d hour, ≤365 d day, else month (≤400 points) | same filters as `/logs` |
| `GET /logs/{id}` | single entry (404) | — |
| `GET /logs/{id}/context` | surrounding entries of the same import by `seq` (file order); pre-0007 rows (`seq` NULL) fall back to `(timestamp, id)` | `before`, `after` (0–200, default 10) |
| `GET /logs/meta/facets` | distinct severities/sources/services (capped 200) | — |
| `GET /dashboard/summary|timeline|severity-distribution|top-sources|top-errors` | stats from stored data only; `timeline` = last `limit` calendar buckets ending at the newest entry (never before the oldest), zero-filled | `bucket` hour/day, `limit` |
| `GET /errors/groups` | fingerprint groups + lifecycle state (status filtered in SQL before `limit`; sources batched in one query) | `limit`, `severity[]`, `status` (400 on invalid) |
| `GET /errors/groups/{fp}` | paged entries (count query has NO order-by — PG rejects it) | `page`, `page_size` |
| `PUT /errors/groups/{fp}/state` | upsert lifecycle state (404 if fp unknown) | `{status, assignee?, note?}`; bad status → 422 |
| `GET /errors/groups/{fp}/trend` | zero-filled per-bucket counts for sparkline; window ends at the newest entry overall (trailing zeros = error stopped) | `bucket`, `limit` |
| `GET /traces` | recent trace summaries | `limit` |
| `GET /traces/{id}` | timeline (matches `trace_id` OR `request_id`, 404) | entries capped at 500, asc order |
| `GET/POST /filters`, `GET/PUT/DELETE /filters/{id}` | saved filters (409 on name clash) | `{name, description?, params}` |

Validation philosophy: bad `sort`/`direction`/`severity`/`status` → 400
with a helpful message, never 500. Pydantic `Literal` mismatches → 422.

## 5. Frontend guide

- **Stack**: Vue 3 + TypeScript + Vite + Pinia + Vue Router, axios only.
  No UI framework; all styling is hand-written CSS in
  `assets/styles.css` (design tokens `--bg-*`, `--text-*`, `--accent`,
  `--danger`, `--warning`, `--success`, …). Dark-first premium theme,
  light via `data-theme="light"`. Icons are inline Lucide-style SVGs
  (`AppIcon.vue`, no extra dependency). No emoji.
- **Conventions**: `<script setup lang="ts">` everywhere; all shared
  types + `toParams()` in `api/client.ts`; axios `baseURL` is `/api`
  (nginx proxies) unless `VITE_API_BASE_URL` is set. `npm run build`
  runs `vue-tsc --noEmit` first — type errors fail the Docker build.
  Never `v-model` a `reactive()` root (replaces the object); mutate
  in place via `Object.assign` (see `Explorer.vue:onQueryUpdate`).
- **Views**:
  - `Dashboard.vue`: KPI stat cards + smooth `TimeChart` area chart
    (All/Day/Hour toggle; All uses `/logs/histogram`) + clickable severity/source/error breakdown
    panels; `EmptyState` when total is 0.
  - `Explorer.vue`: full-width search `FilterBar` (debounced 350 ms,
    syncs URL query) + active-filter chips + sort/per-page toolbar +
    `HistogramBars` (click = zoom date range; `date_to` is set 1 ms before
    the next bucket because the filter is inclusive) + CSV/JSONL export links +
    `LogTable` + `Pagination` + `LogDetails` drawer + save-filter box.
    Restores every filter plus `sort`/`direction`/`page`/`page_size` from
    the route (so reloads, shared links and saved filters keep ordering).
    API calls use `apiParams()` (dates → UTC); the URL keeps local dates.
  - `Errors.vue`: status segmented filter + groups table
    (severity/status badges) + detail panel with lifecycle editor,
    `TrendSpark`, entries table. "Open in Explorer" navigates with
    `?fingerprint=` (whole group), not a text search of the sample.
  - `Traces.vue` (`/traces`, sidebar entry): recent-trace list with
    jump-to-ID box; links to detail.
  - `Imports.vue`: drag-and-drop / multi-select upload (files queued and
    uploaded one at a time; files added while an upload runs join the queue, `timeout: 0` because the request stays open for
    the whole synchronous parse) with progress, import history with
    view/delete. Accept list must match the backend allowlist.
  - `TraceView.vue` (`/traces/:id`): KPI stats + service waterfall
    timeline with time axis + `LogDetails` drawer.
  - `SavedFilters.vue`: CRUD around `FilterBar`; `describe()` renders a
    human-readable criteria line — extend it when adding filter fields.
  - `Settings.vue`: theme + sidebar + page size (Pinia + localStorage),
    backend health, API docs link.
- **Components**: `LogTable` renders `entry.snippet` via `v-html` after
  `sanitizeSnippet()` (in `utils/highlight.ts`: strips every tag except
  `<mark>`), shows first line of multiline messages + `trace:` chip link;
  `LogDetails` drawer links trace/request ids to `/traces/:id` and shows
  "surrounding lines" (`/logs/{id}/context`); clicking one navigates
  inside the drawer (`current` ref), so every view using it gets this;
  funnel buttons filter by service/source/import/fingerprint (in-place via
  `@filter` when the Explorer passes `in-explorer`, otherwise they navigate
  to `/logs?<field>=…`);
  `TimeChart` is a dependency-free smooth SVG area chart with hover
  crosshair; `TrendSpark` is a dependency-free SVG area sparkline.
- **Tests**: 17 vitest tests (`client.test.ts`, `severity.test.ts`,
  `format.test.ts`, `highlight.test.ts`). Node ≥22 required
  (`nvm use 22` — system node may be ancient).

## 6. Database guide

Migrations (never edit an applied one; new change = new numbered file):

| File | Contents |
|---|---|
| `0001_initial.sql` | `schema_migrations`, `imports`, `log_entries`, `saved_filters` + indexes; FK `log_entries.import_id → imports.id ON DELETE CASCADE` |
| `0002_trgm.sql` | `pg_trgm` extension + trigram GIN index on `message` |
| `0003_traces.sql` | `trace_id`, `request_id` columns + btree indexes |
| `0004_search.sql` | expression GIN index `ix_log_entries_search` over `to_tsvector('english', message ‖ service ‖ source ‖ trace_id ‖ request_id)` |
| `0005_error_states.sql` | `error_group_states(fingerprint PK, status CHECK, assignee, note, updated_at)` |
| `0006_dashboard_indexes.sql` | composite covering indexes `ix_log_entries_timestamp_severity(timestamp DESC, severity)` (timeline index-only scans) + `ix_log_entries_severity_fingerprint(severity, fingerprint)` (top-errors). Index-only build, no heap rewrite |
| `0007_entry_seq.sql` | nullable `seq BIGINT` (metadata-only ADD COLUMN) + `ix_log_entries_import_seq(import_id, seq)`; importer numbers entries 1..n per import (continuing across zip members) |
| `0008_search_split_tokens.sql` | rebuilds `ix_log_entries_search` over `to_tsvector('english', translate(message ‖ service ‖ source ‖ trace_id ‖ request_id, '/.@:', '    '))` so path/e-mail/host/IP parts are words; ends with `ANALYZE log_entries` (expression stats). 2M rows: 48 s build |

Critical database rules (several were learned the hard way on a 5.8M-row,
7.6 GB production table — do not regress them):

1. **No stored tsvector, no backfill migrations.** A `SET search_vector`
   backfill rewrites the entire heap and took >20 min before being killed.
   The expression index is one parallel bulk build with zero heap changes.
2. **The query expression must be identical** to the index expression
   (see `_SEARCH_VECTOR_EXPR` in `routers/logs.py`, defined by migration
   0008, incl. the `translate(…, '/.@:', '    ')` split mirrored by
   `search.FTS_SPLIT_CHARS`) or PG silently ignores the index. Verify with `EXPLAIN` (expect `Bitmap Index Scan on
   ix_log_entries_search`).
3. **The `OFFSET 0` in the free-text id-subquery is load-bearing.** Without
   it the planner flattens `IN (SELECT…)` into "timestamp-index scan +
   per-row `to_tsvector()`", turning rare-term searches into full-table
   scans (minutes). With it: bitmap → hash → PK fetch → sort (~0.15 s).
4. **Counts reference a column**: `with_entities(func.count(LogEntry.id))`.
   Bare `func.count()` drops the FROM clause and returns 1.
5. **Count queries must not carry ORDER BY** (PG rejects `ORDER BY` in
   aggregates) — build a separate filter-only query for totals.
6. **Timeline/trend bucketing branches on dialect**: `date_trunc` on PG,
   `strftime` on SQLite. Same for search (tsquery vs ILIKE).
7. **Tests use SQLite** (`tests/conftest.py`, FK pragma enabled) and never
   run `migrations/` — so PG-only SQL (triggers, GIN, `CONCURRENTLY`-style
   constructs) has zero test coverage. Validate PG paths against the real
   container (see §8) whenever you touch them.
8. **Migration failure = crash loop** (`restart: unless-stopped` + migrate
   before uvicorn). A stuck migration also orphans server-side queries that
   survive container restarts — cancel via
   `SELECT pg_cancel_backend(pid)`. Monitor long index builds with
   `SELECT * FROM pg_stat_progress_create_index;`.
9. **Dashboard aggregates must be single-pass.** `/dashboard/summary` was 8
   sequential full-table queries (~30 s on a large table); it is now one
   `SELECT` with `COUNT … FILTER (WHERE …)` + `MIN/MAX`, plus the distinct
   source count as a separate `SELECT count(*) FROM (SELECT DISTINCT
   source …)`. Never put `COUNT(DISTINCT …)` back into the main aggregate:
   it forces a sort of every row (measured on 2M rows: 5.9 s inside the
   aggregate vs 0.16 s aggregate + 0.12 s hash-aggregated subquery). If the dashboard ever needs more,
   the next step is a pre-computed summary table — an architectural change
   needing approval, not more indexes.
10. **VACUUM matters more than indexes after bulk deletes.** A table with
    ~6M dead tuples (deleted imports, autovacuum behind) forces seq scans
    and defeats index-only plans. After mass deletes, run
    `VACUUM (ANALYZE) log_entries;` — regular VACUUM is online-safe;
    `VACUUM FULL`/backfills need approval (heap rewrite, long lock).

## 7. Conventions & rules (must-follow)

From `AGENTS.md`, condensed (read the original for full text):

- Type-annotated Python with a module docstring per file; routers own HTTP,
  `import_service.py` owns import logic.
- Parsers stream and never raise on line content (`ValueError` only for
  malformed JSONL lines / JSON documents / archives).
- All severity handling goes through `normalize_severity()`; `UNKNOWN` is
  data, never an error.
- Grouping is deterministic `fingerprint()` only.
- Uploads are untrusted: stream, cap (raw **and** decompressed bytes),
  allowlist extensions, parameterized queries only, never reflect secrets.
- New schema change = new numbered migration; `models.py` stays
  SQLite-compatible.
- Keep `README.md`, `README.el.md` (Greek mirror — update both),
  `MANUAL.md`, `AGENTS.md`, `LLM.md`, `.env.example` synchronized with
  every behavior/config change.
- Never claim tests pass without running them in-session.
- Needs explicit user approval: framework/DB changes, background workers,
  auth, AI/semantic grouping, editing applied migrations, restructuring
  services.

## 8. Commands

```sh
docker compose up --build                  # full stack (foreground)
docker compose up --build -d               # detached
docker compose logs -f backend             # API logs (watch migrations here)
docker compose exec backend python -m app.migrate   # manual migration run

cd backend && uv sync && uv run pytest -q  # 68 tests (uv-managed, .venv local)
cd backend && uv run uvicorn app.main:app --reload  # local API (needs PG + DATABASE_URL)

cd frontend && npm install && npm run dev  # Vite, /api proxied to :8000
cd frontend && npm test                    # 17 vitest tests (needs node ≥22)
cd frontend && npm run build               # typecheck + production bundle
```

Full-stack validation pattern (use unique markers, clean up after —
never `down -v` on a volume that may hold user data):

```sh
docker compose up --build -d
curl -s http://localhost:8000/api/health
curl -s -F "file=@samples/app.log" http://localhost:8000/api/imports/upload
curl -s "http://localhost:8000/api/logs?q=%22slow%20query%22&sort=relevance"
curl -s "http://localhost:8000/api/traces/<id>"
curl -s -X DELETE http://localhost:8000/api/imports/<id>   # cleanup
docker compose down                        # keeps pgdata volume
```

## 9. Known limitations & security

- Synchronous imports: very large files take as long as the HTTP request;
  no background worker (needs approval to add).
- Single-document `.json` must fit in memory; `.jsonl` streams instead.
- Trace detail caps at 500 entries.
- A search term matching nearly every row (e.g. `request` on a table where
  every line contains it) is slow on very large tables (~11 s for 2M
  matches): the planner then evaluates `to_tsvector()` per row. Rare and
  moderately common terms stay in the 10–250 ms range.
- No auth/multi-user: do not expose to untrusted networks without access
  control in front. No secrets in images; `.env` stays out of Git.
- `.env.example` documents all config (`POSTGRES_*`, `BACKEND_PORT`,
  `FRONTEND_PORT`, `MAX_UPLOAD_MB`, `VITE_API_BASE_URL`); no new env vars
  may be added without documenting them there.

## 10. Agent workflow for a typical change

1. Read this file + `AGENTS.md`, then inspect the real files (evidence
   before synthesis; check all candidate areas a bug report names).
2. Backend schema change? Add `migrations/NNNN_name.sql`, extend
   `models.py` (SQLite-safe) + `schemas.py`, then use it.
3. PG-only SQL? You must validate against the container — SQLite tests
   cannot cover it. Use `EXPLAIN` for anything touching 5M+ rows.
4. API change? Update `frontend/src/api/client.ts` types + `toParams()`,
   the consuming view/component, and `SavedFilters.describe()` if it adds
   a filter dimension.
5. Run `uv run pytest -q` and `npm test` + `npm run build` in-session.
6. Sync `README.md` + `README.el.md` + `MANUAL.md` + `AGENTS.md` (+ this
   file if architecture/conventions changed), add/adjust `samples/` if it
   aids manual testing, then commit with a descriptive message.
