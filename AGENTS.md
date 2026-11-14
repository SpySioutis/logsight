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
request (streamed to temp file, parsed, batch-inserted with 1000-row commits).

## Directory structure

```text
backend/
  app/
    main.py            # FastAPI app, lifespan, router wiring under /api
    config.py          # pydantic-settings (DATABASE_URL, MAX_UPLOAD_MB)
    database.py        # engine + SessionLocal + get_db dependency
    models.py          # Import, LogEntry, SavedFilter (ORM only; schema owned by migrations/)
    schemas.py         # Pydantic request/response models
    severity.py        # canonical levels + normalize_severity (never discards)
    parsers.py         # streaming plaintext / JSONL / JSON parsers
    grouping.py        # deterministic error fingerprinting
    import_service.py  # upload → temp file + hash → parse → batch insert
    migrate.py         # applies backend/migrations/*.sql once each
    routers/           # health, imports, logs, dashboard, errors, filters
  migrations/0001_initial.sql, 0002_trgm.sql
  tests/               # pytest (SQLite override in conftest.py)
frontend/
  src/
    api/client.ts      # axios instance + types + toParams()
    utils/             # severity.ts, format.ts (+ vitest files)
    stores/settings.ts # Pinia: theme + page size (localStorage)
    components/        # SeverityBadge, FilterBar, LogTable, LogDetails,
                       # Pagination, StatCard, TimeChart, EmptyState
    views/             # Dashboard, Explorer, Errors, Imports, SavedFilters, Settings
    router/index.ts
samples/               # app.log, app.jsonl, structured.json (manual testing)
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
- Frontend: Composition API + `<script setup lang="ts">`, shared types from
  `api/client.ts`, dark-theme CSS variables in `assets/styles.css`; keep views
  dense, no decorative animation, no emoji.
- Severity handling: always go through `normalize_severity`; store canonical
  values; `UNKNOWN` is a valid stored value, never an error.
- Error grouping: deterministic `fingerprint()` in `grouping.py` only. No
  external AI/clustering APIs.

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

- `cd backend && uv run pytest -q` — 29 tests. API tests use an isolated
  in-memory SQLite DB (`tests/conftest.py`); SQLite-only branches (e.g.
  `strftime` timeline bucketing) exist solely to keep these tests portable.
- `cd frontend && npm test` — 9 vitest tests.

Never claim tests pass without running them in-session.

## Database conventions

- Schema is owned by `backend/migrations/*.sql`, applied by `app/migrate.py`
  via the `schema_migrations` table. New schema change = new numbered file;
  never edit an applied migration.
- `models.py` must stay compatible with both PostgreSQL (prod) and SQLite
  (tests): no postgres-only column/index constructs in models.
- Counts must reference a table column
  (`with_entities(func.count(LogEntry.id))`) — bare `func.count()` drops the
  FROM clause and returns 1. Timeline bucketing branches on dialect
  (`date_trunc` vs `strftime`).
- FK `log_entries.import_id → imports.id ON DELETE CASCADE`; tests enable the
  SQLite FK pragma to exercise it.

## API conventions

- Routers mounted under `/api`; Swagger at `/api/docs`.
- Explorer filtering/sorting/pagination is server-side; validate `sort`,
  `direction` and `severity` with 400s, never 500s. Page cap: 500 rows.
- Upload: extension allowlist + `MAX_UPLOAD_MB` cap (413), content-hash
  duplicate detection (`status: "duplicate"`, no re-insert), per-line error
  counting without aborting the import.

## Security requirements

- Treat uploads as untrusted: stream, cap size, validate extension, never
  execute content, never reflect raw errors with secrets.
- Parameterized queries only (SQLAlchemy). No hardcoded credentials; `.env`
  stays out of Git. No auth in v1 — note exposure risk if publishing.

## Restrictions (need explicit user approval)

Changing frameworks/database, adding background workers or auth, replacing
deterministic grouping with AI/semantic clustering, editing applied
migrations, restructuring services. Keep docs (`README.md`, `MANUAL.md`,
`AGENTS.md`, `.env.example`) synchronized with every change.
