# LogSight

[🇬🇧 Read in English](README.md)

Μια σύγχρονη, αυτο-φιλοξενούμενη (self-hosted) πλατφόρμα ανάλυσης logs για
αναζήτηση, φιλτράρισμα, παρακολούθηση και κατανόηση των logs εφαρμογών.

Εισάγετε αρχεία logs, περιηγηθείτε και επιθεωρήστε εγγραφές, αναζητήστε με
συνδυασμένα φίλτρα, παρακολουθήστε ομάδες σφαλμάτων και δείτε στατιστικά
dashboard — όλα υπολογισμένα από τα πραγματικά αποθηκευμένα δεδομένα σας.

## Γρήγορη εκκίνηση

Προαπαιτούμενα: Docker και Docker Compose v2.

```sh
./start.sh        # Linux
./start.command   # macOS (το διπλό κλικ δουλεύει επίσης)
start.bat         # Windows
```

Στη συνέχεια ανοίξτε το [http://localhost:8080](http://localhost:8080) στον browser.
Τεκμηρίωση API: [http://localhost:8000/api/docs](http://localhost:8000/api/docs).

Δείτε το [MANUAL.md](MANUAL.md) για χειροκίνητη εκκίνηση, παραμετροποίηση,
migrations, δοκιμές και αντιμετώπιση προβλημάτων.

## Δυνατότητες

- **Εισαγωγή logs** — απλό κείμενο (`.log`, `.txt`, συμπ. syslog RFC 5424 και
  πολυγραμμικά stacktraces), JSON Lines (`.jsonl`, `.ndjson`), δομημένο JSON
  (`.json`) και CSV (`.csv`)· γίνονται δεκτά gzip (`.gz`) και πακέτα (`.zip`)·
  ανάλυση με ροή (streaming), μαζική φόρτωση μέσω COPY (PostgreSQL),
  ζωντανό ποσοστό προόδου, όριο 1 GB (προεπιλογή, για
  πρωτογενές και αποσυμπιεσμένο μέγεθος), ανίχνευση
  διπλότυπων μέσω hash περιεχομένου, ιστορικό εισαγωγών.
- **Εξερεύνηση logs** — σελιδοποίηση από τον server, ταξινόμηση (συμπ.
  κατάταξης συνάφειας), αναζήτηση πλήρους κειμένου με τελεστές
  (`"ακριβής φράση"`, `-εξαίρεση`, `service:`, `source:`, `severity:`,
  `trace:`, `request:`), επισημασμένα αποσπάσματα, φίλτρα εύρους ημερομηνιών,
  σοβαρότητας, πηγής, υπηρεσίας, trace και request (συνδυαστικά), προβολή
  λεπτομερειών εγγραφής με αντιγραφή στο πρόχειρο και συνδέσμους trace.
- **Κανονικοποίηση σοβαρότητας** — TRACE / DEBUG / INFO / WARN / WARNING /
  ERROR / FATAL / CRITICAL / UNKNOWN. Τα συνώνυμα (`warn`, `err`, `crit`,
  αριθμητικά επίπεδα…) κανονικοποιούνται· οι άγνωστες τιμές γίνονται UNKNOWN
  και δεν απορρίπτονται ποτέ.
- **Dashboard** — σύνολα, σφάλματα, προειδοποιήσεις, κρίσιμα, logs στον χρόνο,
  κατανομή σοβαρότητας, πιο ενεργές πηγές, συχνότερα σφάλματα (χωρίς τις
  σιγασμένες ομάδες). Καταστάσεις κενού περιεχομένου όταν δεν έχουν εισαχθεί logs.
- **Ανάλυση σφαλμάτων** — ντετερμινιστική ομαδοποίηση με δακτυλικό αποτύπωμα
  (αποκρύπτονται IPs, UUIDs, αριθμοί, hex ids), μετρήσεις, πρώτη/τελευταία
  εμφάνιση, γραφική τάση ανά ομάδα, κύκλος ζωής (open/acknowledged/resolved/
  muted) με ανάθεση και σημείωση, πλοήγηση στις αντίστοιχες εγγραφές.
- **Συσχέτιση traces** — τα `trace_id` / `request_id` εξάγονται κατά την
  εισαγωγή· σελίδα επισκόπησης traces και χρονολόγιο-waterfall ανά trace
  ανάμεσα σε υπηρεσίες με διάρκεια, υπηρεσίες και σοβαρότητες.
- **Αποθηκευμένα φίλτρα** — δημιουργία, επεξεργασία, διαγραφή και
  επαναχρησιμοποίηση προεπιλογών αναζήτησης.
- **Σύγχρονο UI παρατηρησιμότητας** — SPA σε Vue 3 + TypeScript με σκοτεινό
  θέμα, πτυσσόμενη πλαϊνή πλοήγηση, πίνακα KPI, ομαλά γραφήματα,
  σκελετούς φόρτωσης και πλήρη υποστήριξη ανοιχτού θέματος.

## Τεχνολογίες

| Επίπεδο | Επιλογή |
|---|---|
| Frontend | Vue 3, TypeScript, Composition API, Vite, Pinia, Vue Router |
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, uv |
| Βάση δεδομένων | PostgreSQL 17 (versioned SQL migrations) |
| Υποδομή | Docker, Docker Compose |

## Δομή έργου

```text
logsight/
├── backend/               # Εφαρμογή FastAPI (διαχείριση με uv)
│   ├── app/               # config, database, models, schemas, severity,
│   │   │                  # parsers, grouping, search, import_service, migrate, main
│   │   └── routers/       # health, imports, logs, dashboard, errors, filters, traces
│   ├── migrations/        # versioned SQL (0001_initial … 0005_error_states)
│   └── tests/             # pytest: severity, parsers, grouping, search, API
├── frontend/              # SPA σε Vue 3 + TS (npm)
│   └── src/               # views, components, api client, stores, utils
├── samples/               # παραδείγματα αρχείων log για δοκιμές
├── compose.yaml           # υπηρεσίες db + backend + frontend
├── Dockerfile             # image του backend
├── start.sh / start.command / start.bat
├── MANUAL.md / AGENTS.md / README.md / README.el.md
└── .env.example
```

## Παραμετροποίηση

Αντιγράψτε το `.env.example` σε `.env` για να αλλάξετε τις προεπιλογές:

| Μεταβλητή | Προεπιλογή | Σημασία |
|---|---|---|
| `POSTGRES_USER / PASSWORD / DB` | `logsight` | διαπιστευτήρια βάσης |
| `BACKEND_PORT` | `8000` | θύρα του API στον host |
| `FRONTEND_PORT` | `8080` | θύρα του UI στον host |
| `MAX_UPLOAD_MB` | `1024` | μέγιστο μέγεθος αρχείου εισαγωγής σε megabytes (1 GB) |

Ποτέ μην κάνετε commit πραγματικό αρχείο `.env`.

## Επισκόπηση API

Βασική διαδρομή `/api`. Πλήρης αναφορά με σχήματα στο `/api/docs` (Swagger UI).

- `GET /api/health`
- `POST /api/imports/upload` · `GET /api/imports` · `GET /api/imports/{id}` · `DELETE /api/imports/{id}`
- `GET /api/logs` (q με τελεστές `"φράση" -εξαίρεση field:value`, severity[], source, service, import_id, trace_id, request_id, date_from, date_to, sort συμπ. `relevance`, direction, page, page_size) · `GET /api/logs/{id}` · `GET /api/logs/meta/facets`
- `GET /api/dashboard/summary|timeline|severity-distribution|top-sources|top-errors`
- `GET /api/errors/groups` (φίλτρο `status`) · `GET /api/errors/groups/{fingerprint}` · `PUT /api/errors/groups/{fingerprint}/state` · `GET /api/errors/groups/{fingerprint}/trend`
- `GET /api/traces` · `GET /api/traces/{id}`
- `GET|POST /api/filters` · `GET|PUT|DELETE /api/filters/{id}`

## Δοκιμές

```sh
cd backend && uv run pytest -q        # 54 δοκιμές: unit + API integration (SQLite)
cd frontend && npm test               # 12 δοκιμές vitest
```

Αναλυτικά στο MANUAL.md· εκεί περιγράφεται και η πλήρης validation με Docker.

## Γνωστοί περιορισμοί

- Οι εισαγωγές εκτελούνται συγχρονισμένα μέσα στο αίτημα upload (χωρίς
  background worker ακόμη)· τα πολύ μεγάλα αρχεία διαρκούν όσο το HTTP αίτημα.
  Η πρόοδος upload φαίνεται στο UI.
- Ένα αρχείο `.json` ως ενιαίο έγγραφο πρέπει να χωράει στο όριο μεγέθους
  upload (το `.jsonl` αναλύεται γραμμή-γραμμή). Το ίδιο όριο καλύπτει το
  αποσυμπιεσμένο περιεχόμενο `.gz` / `.zip`.
- Η αναζήτηση πλήρους κειμένου χρησιμοποιεί εκφραστικό (expression) GIN index
  με stemming + `ts_rank` στο PostgreSQL· η σουίτα δοκιμών την εξομοιώνει με
  `ILIKE` στο SQLite.
- Η ομαδοποίηση σφαλμάτων είναι ντετερμινιστική (fingerprint), όχι σημασιολογική.
- Χωρίς authentication/multi-user σε αυτή την έκδοση — χρησιμοποιήστε δικό σας
  έλεγχο πρόσβασης αν το εκθέσετε.

## Συντελεστές

**Muse Spark 1.3 High** — AI Coding Assistant & Implementation Contributor.

## Άδεια

MIT — δείτε το [LICENSE](LICENSE).
