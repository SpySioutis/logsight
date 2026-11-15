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

- **Εισαγωγή logs** — απλό κείμενο (`.log`, `.txt`), JSON Lines (`.jsonl`, `.ndjson`)
  και δομημένο JSON (`.json`)· ανάλυση με ροή (streaming), μαζικές εισαγωγές,
  όριο 1 GB (προεπιλογή), ένδειξη προόδου, ανίχνευση διπλότυπων μέσω hash
  περιεχομένου, ιστορικό εισαγωγών.
- **Εξερεύνηση logs** — σελιδοποίηση από τον server, ταξινόμηση, αναζήτηση
  πλήρους κειμένου, φίλτρα εύρους ημερομηνιών, σοβαρότητας, πηγής και υπηρεσίας
  (συνδυαστικά), προβολή λεπτομερειών εγγραφής με αντιγραφή στο πρόχειρο.
- **Κανονικοποίηση σοβαρότητας** — TRACE / DEBUG / INFO / WARN / WARNING /
  ERROR / FATAL / CRITICAL / UNKNOWN. Τα συνώνυμα (`warn`, `err`, `crit`,
  αριθμητικά επίπεδα…) κανονικοποιούνται· οι άγνωστες τιμές γίνονται UNKNOWN
  και δεν απορρίπτονται ποτέ.
- **Dashboard** — σύνολα, σφάλματα, προειδοποιήσεις, κρίσιμα, logs στον χρόνο,
  κατανομή σοβαρότητας, πιο ενεργές πηγές, συχνότερα σφάλματα. Καταστάσεις
  κενού περιεχομένου όταν δεν έχουν εισαχθεί logs.
- **Ανάλυση σφαλμάτων** — ντετερμινιστική ομαδοποίηση με δακτυλικό αποτύπωμα
  (αποκρύπτονται IPs, UUIDs, αριθμοί, hex ids), μετρήσεις, πρώτη/τελευταία
  εμφάνιση, πλοήγηση στις αντίστοιχες εγγραφές.
- **Αποθηκευμένα φίλτρα** — δημιουργία, επεξεργασία, διαγραφή και
  επαναχρησιμοποίηση προεπιλογών αναζήτησης.
- **Σκοτεινό UI για προγραμματιστές** — πυκνό, μινιμαλιστικό SPA σε Vue 3 +
  TypeScript (προαιρετικό ανοιχτό θέμα στις Ρυθμίσεις).

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
│   │   │                  # parsers, grouping, import_service, migrate, main
│   │   └── routers/       # health, imports, logs, dashboard, errors, filters
│   ├── migrations/        # versioned SQL (0001_initial, 0002_trgm)
│   └── tests/             # pytest: severity, parsers, grouping, API
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
- `GET /api/logs` (q, severity[], source, service, import_id, date_from, date_to, sort, direction, page, page_size) · `GET /api/logs/{id}` · `GET /api/logs/meta/facets`
- `GET /api/dashboard/summary|timeline|severity-distribution|top-sources|top-errors`
- `GET /api/errors/groups` · `GET /api/errors/groups/{fingerprint}`
- `GET|POST /api/filters` · `GET|PUT|DELETE /api/filters/{id}`

## Δοκιμές

```sh
cd backend && uv run pytest -q        # 29 δοκιμές: unit + API integration (SQLite)
cd frontend && npm test               # 9 δοκιμές vitest
```

Αναλυτικά στο MANUAL.md· εκεί περιγράφεται και η πλήρης validation με Docker.

## Γνωστοί περιορισμοί

- Οι εισαγωγές εκτελούνται συγχρονισμένα μέσα στο αίτημα upload (χωρίς
  background worker ακόμη)· τα πολύ μεγάλα αρχεία διαρκούν όσο το HTTP αίτημα.
  Η πρόοδος upload φαίνεται στο UI.
- Ένα αρχείο `.json` ως ενιαίο έγγραφο πρέπει να χωράει στο όριο μεγέθους
  upload (το `.jsonl` αναλύεται γραμμή-γραμμή).
- Η αναζήτηση πλήρους κειμένου χρησιμοποιεί `ILIKE` + trigram index· χωρίς
  stemming ή κατάταξη.
- Η ομαδοποίηση σφαλμάτων είναι ντετερμινιστική (fingerprint), όχι σημασιολογική.
- Χωρίς authentication/multi-user σε αυτή την έκδοση — χρησιμοποιήστε δικό σας
  έλεγχο πρόσβασης αν το εκθέσετε.

## Συντελεστές

**Muse Spark 1.3 High** — AI Coding Assistant & Implementation Contributor.

## Άδεια

MIT — δείτε το [LICENSE](LICENSE).
