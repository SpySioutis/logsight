# LogSight

[🇬🇷 Διαβάστε το στα Ελληνικά](README.el.md)

A modern, self-hosted log analysis platform for searching, filtering, monitoring and understanding application logs.

Import log files, browse and inspect entries, search with combined filters, track error groups, and review dashboard statistics — all computed from your real stored data.

## Quick start

Prerequisites: Docker and Docker Compose v2.

```sh
./start.sh        # Linux
./start.command   # macOS (double-click works too)
start.bat         # Windows
```

Then open [http://localhost:8080](http://localhost:8080) in a browser.
API docs: [http://localhost:8000/api/docs](http://localhost:8000/api/docs).

See [MANUAL.md](MANUAL.md) for manual startup, configuration, migrations, testing and troubleshooting.

## Features

- **Log import** — plain text (`.log`, `.txt`), JSON Lines (`.jsonl`, `.ndjson`) and structured JSON (`.json`); streaming parse, batch inserts, 100 MB default limit, progress display, duplicate detection by content hash, import history.
- **Log explorer** — server-side pagination, sorting, full-text search, date-range, severity, source and service filters (combinable), log details drawer with copy-to-clipboard.
- **Severity normalization** — TRACE / DEBUG / INFO / WARN / WARNING / ERROR / FATAL / CRITICAL / UNKNOWN. Aliases (`warn`, `err`, `crit`, numeric levels…) are normalized; unknown values become UNKNOWN and are never discarded.
- **Dashboard** — totals, errors, warnings, criticals, logs over time, severity distribution, most active sources, most frequent errors. Empty states when nothing is imported.
- **Error analysis** — deterministic fingerprint grouping (masks IPs, UUIDs, numbers, hex ids), counts, first/last occurrence, drill-down to matching entries.
- **Saved filters** — create, edit, delete and re-apply search presets.
- **Dark developer UI** — dense, minimal Vue 3 + TypeScript SPA (light theme optional in Settings).

## Technology stack

| Layer | Choice |
|---|---|
| Frontend | Vue 3, TypeScript, Composition API, Vite, Pinia, Vue Router |
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, uv |
| Database | PostgreSQL 17 (versioned SQL migrations) |
| Infra | Docker, Docker Compose |

## Project structure

```text
logsight/
├── backend/               # FastAPI app (uv-managed)
│   ├── app/               # config, database, models, schemas, severity,
│   │   │                  # parsers, grouping, import_service, migrate, main
│   │   └── routers/       # health, imports, logs, dashboard, errors, filters
│   ├── migrations/        # versioned SQL (0001_initial, 0002_trgm)
│   └── tests/             # pytest: severity, parsers, grouping, API
├── frontend/              # Vue 3 + TS SPA (npm)
│   └── src/               # views, components, api client, stores, utils
├── samples/               # example log files for manual testing
├── compose.yaml           # db + backend + frontend services
├── Dockerfile             # backend image
├── start.sh / start.command / start.bat
├── MANUAL.md / AGENTS.md / README.md
└── .env.example
```

## Configuration

Copy `.env.example` to `.env` to override defaults:

| Variable | Default | Meaning |
|---|---|---|
| `POSTGRES_USER / PASSWORD / DB` | `logsight` | database credentials |
| `BACKEND_PORT` | `8000` | host port for the API |
| `FRONTEND_PORT` | `8080` | host port for the UI |
| `MAX_UPLOAD_MB` | `100` | max import file size |

Never commit a real `.env` file.

## API overview

Base path `/api`. Full reference with schemas at `/api/docs` (Swagger UI).

- `GET /api/health`
- `POST /api/imports/upload` · `GET /api/imports` · `GET /api/imports/{id}` · `DELETE /api/imports/{id}`
- `GET /api/logs` (q, severity[], source, service, import_id, date_from, date_to, sort, direction, page, page_size) · `GET /api/logs/{id}` · `GET /api/logs/meta/facets`
- `GET /api/dashboard/summary|timeline|severity-distribution|top-sources|top-errors`
- `GET /api/errors/groups` · `GET /api/errors/groups/{fingerprint}`
- `GET|POST /api/filters` · `GET|PUT|DELETE /api/filters/{id}`

## Tests

```sh
cd backend && uv run pytest -q        # 29 tests: unit + API integration (SQLite)
cd frontend && npm test               # 9 vitest tests
```

Documented in MANUAL.md; a full Docker validation is described there too.

## Known limitations

- Imports are processed synchronously in the upload request (no background worker yet); very large files take as long as the HTTP request lasts. Upload progress is shown in the UI.
- A single-document `.json` file must fit within the upload size limit (it is parsed as one document; `.jsonl` streams line-by-line instead).
- Full-text search uses `ILIKE` + trigram index; no stemming or ranking.
- Error grouping is deterministic fingerprinting, not semantic clustering.
- No authentication/multi-user support in this version — run behind your own access control if exposed.

## Contributors

**Muse Spark 1.3 High** — AI Coding Assistant & Implementation Contributor.

## License

MIT — see [LICENSE](LICENSE).
