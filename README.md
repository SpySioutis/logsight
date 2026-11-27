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

- **Log import** — plain text (`.log`, `.txt`, incl. RFC 5424 syslog, nginx/Apache access and error logs, and multiline stacktraces), JSON Lines (`.jsonl`, `.ndjson`), structured JSON (`.json`) and CSV (`.csv`); gzip (`.gz`) and bundles (`.zip`) accepted; streaming parse, PostgreSQL COPY bulk load, 1 GB default limit (raw + decompressed), live progress percentage, duplicate detection by content hash, import history.
- **Log explorer** — server-side pagination, sorting (incl. relevance ranking), full-text search with operators (`"exact phrase"`, `-exclude`, `service:`, `source:`, `severity:`, `trace:`, `request:`), highlighted snippets, date-range, severity, source, service, trace and request filters (combinable, shareable via URL), a volume histogram of the current result set (click a bar to zoom into that period), CSV / JSONL export of all matching entries (up to 100,000), log details drawer with surrounding lines from the original file, copy-to-clipboard and trace links.
- **Severity normalization** — TRACE / DEBUG / INFO / WARN / WARNING / ERROR / FATAL / CRITICAL / UNKNOWN. Aliases (`warn`, `err`, `crit`, numeric levels…) are normalized; unknown values become UNKNOWN and are never discarded.
- **Dashboard** — totals, errors, warnings, criticals, logs over time, severity distribution, most active sources, most frequent errors (muted groups excluded). Empty states when nothing is imported.
- **Error analysis** — deterministic fingerprint grouping (masks timestamps, IPs, UUIDs, numbers, hex ids), counts, first/last occurrence, per-group trend sparkline, lifecycle status (open/acknowledged/resolved/muted) with assignee and note, drill-down to matching entries.
- **Trace correlation** — `trace_id` / `request_id` extracted at import; traces overview page plus a per-trace waterfall timeline across services with duration, services and severities.
- **Saved filters** — create, edit, delete and re-apply search presets.
- **Modern observability UI** — dark-first Vue 3 + TypeScript SPA with collapsible sidebar navigation, KPI dashboard, smooth charts, loading skeletons and full light-theme support.

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
│   │   │                  # parsers, grouping, search, import_service, migrate, main
│   │   └── routers/       # health, imports, logs, dashboard, errors, filters, traces
│   ├── migrations/        # versioned SQL (0001_initial … 0008_search_split_tokens)
│   └── tests/             # pytest: severity, parsers, grouping, search, API
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
| `MAX_UPLOAD_MB` | `1024` | max import file size in megabytes (1 GB) |

Never commit a real `.env` file.

## API overview

Base path `/api`. Full reference with schemas at `/api/docs` (Swagger UI).

- `GET /api/health`
- `POST /api/imports/upload` · `GET /api/imports` · `GET /api/imports/{id}` · `DELETE /api/imports/{id}`
- `GET /api/logs` (q with `"phrase" -exclude field:value` operators, severity[], source, service, import_id, trace_id, request_id, fingerprint, date_from, date_to, sort incl. `relevance`, direction, page, page_size) · `GET /api/logs/export` (same filters, `format=csv|jsonl`) · `GET /api/logs/histogram` (same filters) · `GET /api/logs/{id}` · `GET /api/logs/{id}/context` · `GET /api/logs/meta/facets`
- `GET /api/dashboard/summary|timeline|severity-distribution|top-sources|top-errors`
- `GET /api/errors/groups` (`status` filter) · `GET /api/errors/groups/{fingerprint}` · `PUT /api/errors/groups/{fingerprint}/state` · `GET /api/errors/groups/{fingerprint}/trend`
- `GET /api/traces` · `GET /api/traces/{id}`
- `GET|POST /api/filters` · `GET|PUT|DELETE /api/filters/{id}`

## Tests

```sh
cd backend && uv run pytest -q        # 68 tests: unit + API integration (SQLite)
cd frontend && npm test               # 17 vitest tests
```

Documented in MANUAL.md; a full Docker validation is described there too.

## Known limitations

- Imports are processed synchronously in the upload request (no background worker yet); very large files take as long as the HTTP request lasts. Upload progress is shown in the UI.
- A single-document `.json` file must fit within the upload size limit (it is parsed as one document; `.jsonl` streams line-by-line instead). The same limit caps decompressed `.gz` / `.zip` output.
- Full-text search uses an expression GIN index with stemming + `ts_rank` on PostgreSQL (words inside paths, e-mails, hostnames and IPs are indexed separately); the test suite emulates it with `ILIKE` on SQLite. A term that matches nearly every row is slow on multi-million-row tables.
- Error grouping is deterministic fingerprinting, not semantic clustering.
- No authentication/multi-user support in this version — run behind your own access control if exposed.

## Contributors

**Muse Spark 1.3 High** — AI Coding Assistant & Implementation Contributor.

## License

MIT — see [LICENSE](LICENSE).
