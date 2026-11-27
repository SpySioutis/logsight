# LogSight Manual

## 1. Project overview

LogSight is a self-hosted log analysis platform. You upload application log
files (plain text incl. syslog, JSON Lines, structured JSON or CSV, optionally
gzip-compressed or bundled in a zip archive) and then browse, search,
filter and analyze them through a web UI backed by a FastAPI API and
PostgreSQL 17. Three Docker services (`db`, `backend`, `frontend`) are
orchestrated with Docker Compose.

## 2. Prerequisites

- Docker Engine 24+ with Docker Compose v2 (`docker compose version` must work).
- 4 GB free RAM recommended; ~2 GB disk for images on first build.
- Ports `8080` (UI) and `8000` (API) free, or override via `.env`.

Check:

```sh
docker --version
docker compose version
```

## 3. Required software

Only Docker + Compose are required to run LogSight. For local development
(without Docker) you additionally need Python 3.12+, `uv`, Node 22+ and npm —
see §13.

## 4. Installation

```sh
git clone <repository-url> logsight
cd logsight
```

No other installation step is needed: images build from the repository.

## 5. Environment configuration

1. Copy the example file: `cp .env.example .env`
2. Adjust values (all optional; defaults work out of the box):

| Variable | Default | Meaning |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `logsight` | DB credentials (compose injects matching `DATABASE_URL` into the backend; the checked-in `DATABASE_URL` default is only for local dev) |
| `BACKEND_PORT` | `8000` | host port publishing the API |
| `FRONTEND_PORT` | `8080` | host port publishing the UI |
| `MAX_UPLOAD_MB` | `1024` | maximum import file size in megabytes (1 GB) |

3. Never commit `.env`. It is covered by `.gitignore`.

## 6. Database initialization

PostgreSQL 17 runs in the `db` service with data persisted in the `pgdata`
Docker volume. Schema is created by versioned SQL migrations, not by the ORM:

- `backend/migrations/0001_initial.sql` — tables + indexes.
- `backend/migrations/0002_trgm.sql` — `pg_trgm` extension + message trigram index.
- `backend/migrations/0003_traces.sql` — `trace_id` / `request_id` columns + indexes.
- `backend/migrations/0004_search.sql` — expression GIN index
  `ix_log_entries_search` for ranked full-text search (no heap changes).
- `backend/migrations/0005_error_states.sql` — `error_group_states` lifecycle table.
- `backend/migrations/0006_dashboard_indexes.sql` — composite covering indexes
  for dashboard aggregates.
- `backend/migrations/0008_search_split_tokens.sql` — rebuilds
  `ix_log_entries_search` so words inside paths, URLs, e-mails, hostnames
  and IPs are searchable (`checkout` now finds `/api/checkout`), then runs
  `ANALYZE` so the planner has statistics for the index expression.
- `backend/migrations/0007_entry_seq.sql` — nullable `seq` column (original
  file order per import, metadata-only `ADD COLUMN`) + `(import_id, seq)`
  index for the "surrounding lines" view. Entries imported earlier keep
  `seq` NULL and fall back to timestamp order.

Migrations run automatically every time the backend container starts
(`python -m app.migrate` before uvicorn); already-applied files are recorded
in `schema_migrations` and skipped. To apply them manually against a running
stack, see §11.

The container's boot step (`python -m app.migrate --recover`) also cleans up
imports interrupted by a crash or restart (running `python -m app.migrate`
by hand never does this, so it is safe against a live server):
anything still in `processing` is marked `failed` (with an explanatory
message) and its partially loaded rows are removed. A failed import never
leaves partial data behind — simply upload the file again.

Note: `0004_search.sql` and `0008_search_split_tokens.sql` build a GIN index
over all stored rows (0008 measured ~25 s per million rows on a laptop). On tables
with millions of entries this one-time build can take several minutes, during
which the backend stays unhealthy and the API is unavailable. Let it finish;
interrupting it only rolls back and retries on the next boot. Progress is
visible in Postgres via `SELECT * FROM pg_stat_progress_create_index;`.

## 7. Docker setup

Services (`compose.yaml`):

| Service | Image / build | Ports | Health |
|---|---|---|---|
| `db` | `postgres:17`, volume `pgdata` | internal 5432 | `pg_isready` |
| `backend` | `Dockerfile` (uv + FastAPI) | `${BACKEND_PORT:-8000}:8000` | `GET /api/health` |
| `frontend` | `frontend/Dockerfile` (nginx + static SPA, proxies `/api/` → backend) | `${FRONTEND_PORT:-8080}:80` | depends on backend |

## 8. Automatic startup

Use the script for your OS (works from any directory; scripts resolve the
project root themselves):

- Linux: `./start.sh`
- macOS: `./start.command` (double-click in Finder, or run in Terminal)
- Windows: `start.bat` (double-click, or run in a console)

Each script checks Docker and Compose availability, prints a clear error if
missing, then runs `docker compose up --build` and propagates its exit code.

After startup:

- UI: http://localhost:8080 (or your `FRONTEND_PORT`)
- API docs: http://localhost:8000/api/docs (or your `BACKEND_PORT`)

## 9. Manual startup

```sh
cd /path/to/logsight
docker compose up --build          # foreground; Ctrl-C stops
# or detached:
docker compose up --build -d
```

## 10. How to stop the application

- Foreground: `Ctrl-C`.
- Detached: `docker compose down` (keeps the `pgdata` volume).
- Full reset including data: `docker compose down -v` (deletes all imported logs).

## 11. How to inspect logs

```sh
docker compose logs -f backend     # API logs
docker compose logs -f frontend    # nginx access/error logs
docker compose logs -f db          # postgres logs
docker compose ps                  # service health overview
```

Manual migration run (backend container already built):

```sh
docker compose exec backend python -m app.migrate
```

## 12. How to run tests

Backend (68 tests: severity, parsers, grouping, search + API integration on isolated SQLite):

```sh
cd backend
uv sync
uv run pytest -q
```

Frontend (17 vitest tests: severity/format/highlight utils, API param builder, date conversion, export URL):

```sh
cd frontend
npm install
npm test
npm run build   # also typechecks (vue-tsc) and produces dist/
```

Full-stack validation with Docker:

```sh
docker compose up --build -d
curl -s http://localhost:8000/api/health
# upload a sample and query it:
curl -s -F "file=@samples/app.log" http://localhost:8000/api/imports/upload
curl -s "http://localhost:8000/api/dashboard/summary"
docker compose down
```

## 13. Development workflow

- Backend without Docker: `cd backend && uv sync && uv run uvicorn app.main:app --reload`,
  with Postgres reachable and `DATABASE_URL` exported
  (default expects `postgresql+psycopg://logsight:logsight@localhost:5432/logsight`).
- Frontend without Docker: `cd frontend && npm install && npm run dev`
  (Vite proxies `/api` → `http://localhost:8000`).
- Keep `MANUAL.md`, `AGENTS.md`, `README.md` and `.env.example` in sync with
  every behavior/config change.

## 14. Backup and restoration

```sh
docker compose exec db pg_dump -U logsight logsight > logsight-backup.sql
cat logsight-backup.sql | docker compose exec -T db psql -U logsight -d logsight
```

## 14a. Upgrading: re-fingerprinting stored errors

Error groups are keyed by a deterministic fingerprint of the message. When
the normalisation rules change (e.g. timestamps inside messages are now
masked, so one error no longer splits into a group per hour of day), rows
imported before the upgrade keep their old fingerprints and will not merge
with newly imported ones. Recompute them once:

```sh
docker compose exec backend python -m app.refingerprint
```

It only touches rows that have a fingerprint (error-like severities), works
in batches of 5,000 committed one by one, is idempotent, and carries each
group's lifecycle state (status / assignee / note) over to the new
fingerprint. Roughly 3,000 rows/s; the API stays available while it runs.

## 15. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `docker: command not found` | Install Docker Desktop (macOS/Windows) or docker engine (Linux). |
| `permission denied` on the Docker socket (Linux) | Add your user to the `docker` group, then log out/in. |
| Port already in use | Set `FRONTEND_PORT` / `BACKEND_PORT` in `.env`. |
| Backend unhealthy / DB connection refused on first boot | Wait for the `db` healthcheck; check `docker compose logs db`. Migrations run before the API accepts traffic. |
| `413 File exceeds the limit` on upload | Increase `MAX_UPLOAD_MB`, rebuild backend (`docker compose up --build backend`). The same cap applies to decompressed `.gz` / `.zip` output. |
| `400 Unsupported file type` | Use `.log`, `.txt`, `.jsonl`, `.ndjson`, `.json`, `.csv`, `.gz` or `.zip`. |
| `422` on a `.zip` upload | The archive holds no supported log files, or a member is corrupt — check the `detail` message. |
| Blank dashboard | No logs imported yet — upload a file in Imports (try `samples/app.log`). |
| Same error split into many groups after upgrading | Data imported before the timestamp-aware fingerprint rules: run `docker compose exec backend python -m app.refingerprint` once (see §14a). |
| Import shows `failed` with "interrupted" | The server restarted mid-upload; the partial rows were removed at boot. Upload the file again. |
| Frontend `Could not load…` errors | Backend unreachable: `curl http://localhost:8000/api/health`; check `docker compose ps`. |

## 16. Security notes

- Imported files are untrusted input: they are streamed to disk, parsed with
  size caps, never executed, and errors are isolated per line.
- Upload size, extension allowlist, and Pydantic input validation are enforced.
  Decompressed `.gz` / `.zip` output is capped by the same size limit.
- All queries use SQLAlchemy parameter binding. No secrets are baked into
  images; credentials come from environment. Keep `.env` out of Git.
- This version has no authentication: do not expose it to untrusted networks
  without your own access control in front of it.
