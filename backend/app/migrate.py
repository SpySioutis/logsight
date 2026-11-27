"""Versioned SQL migration runner.

Applies every ``migrations/*.sql`` file in filename order exactly once,
recorded in the ``schema_migrations`` table. Safe to run on every boot:
already-applied versions are skipped inside a transaction.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

from app.database import engine

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def pending_versions() -> list[str]:
    files = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql"))
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
        )
        applied = {row[0] for row in conn.execute(text("SELECT version FROM schema_migrations"))}
    return [f for f in files if f not in applied]


def run() -> list[str]:
    applied: list[str] = []
    for version in pending_versions():
        sql = (MIGRATIONS_DIR / version).read_text(encoding="utf-8")
        with engine.begin() as conn:
            conn.execute(text(sql))
            conn.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:v) ON CONFLICT DO NOTHING"),
                {"v": version},
            )
        applied.append(version)
        print(f"applied migration {version}")
    if not applied:
        print("database is up to date")
    return applied


def recover() -> int:
    """Boot-time cleanup of imports interrupted by a crash or restart."""
    # Imported lazily: the migration runner must work before the ORM schema exists.
    from app.database import SessionLocal
    from app.import_service import recover_interrupted_imports

    with SessionLocal() as db:
        count = recover_interrupted_imports(db)
    if count:
        print(f"marked {count} interrupted import(s) as failed")
    return count


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001 - startup must show the real error
        print(f"migration failed: {exc}", file=sys.stderr)
        raise
    try:
        recover()
    except Exception as exc:  # noqa: BLE001 - never block startup on cleanup
        print(f"import recovery skipped: {exc}", file=sys.stderr)
