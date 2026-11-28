"""Recompute stored error fingerprints after a grouping-rule change.

Usage (inside the backend container)::

    python -m app.refingerprint

Only rows that already have a fingerprint (error-like severities) are
touched. Rows are processed in id-ordered batches and committed per batch,
and re-running is idempotent. If it is interrupted, re-run it; lifecycle
state of groups whose rows were already rewritten before the interruption
is not carried over (re-set those groups' state in the UI).

Lifecycle state (``error_group_states``) is carried over to the new
fingerprint: when several old groups collapse into one new group, the most
recently updated state wins. Old state rows are kept (harmless: a state
without matching entries is never listed) so nothing is lost.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from sqlalchemy import bindparam, update
from sqlalchemy.orm import Session

from app.grouping import fingerprint
from app.models import ErrorGroupState, LogEntry

BATCH = 5000
_TABLE = LogEntry.__table__
_UPDATE = (
    update(_TABLE).where(_TABLE.c.id == bindparam("row_id")).values(fingerprint=bindparam("fp"))
)
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def refingerprint(db: Session, batch_size: int = BATCH) -> tuple[int, int]:
    """Return ``(rows_scanned, rows_changed)``."""
    mapping: dict[str, set[str]] = {}
    scanned = changed = 0
    last_id = ""
    while True:
        rows = (
            db.query(LogEntry.id, LogEntry.message, LogEntry.fingerprint)
            .filter(LogEntry.fingerprint.isnot(None))
            .filter(LogEntry.id > last_id)
            .order_by(LogEntry.id)
            .limit(batch_size)
            .all()
        )
        if not rows:
            break
        updates = []
        for row_id, message, old in rows:
            new = fingerprint(message)
            if new != old:
                updates.append({"row_id": row_id, "fp": new})
                mapping.setdefault(old, set()).add(new)
        if updates:
            db.execute(_UPDATE, updates)
        db.commit()
        scanned += len(rows)
        changed += len(updates)
        last_id = rows[-1][0]
    _carry_states(db, mapping)
    return scanned, changed


def _stamp(state: ErrorGroupState) -> datetime:
    value = state.updated_at
    if value is None:
        return _EPOCH
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _carry_states(db: Session, mapping: dict[str, set[str]]) -> None:
    if not mapping:
        return
    old_states = db.query(ErrorGroupState).filter(ErrorGroupState.fingerprint.in_(list(mapping))).all()
    best: dict[str, ErrorGroupState] = {}
    for state in old_states:
        # One old group can also split into several new ones: each gets it.
        for new in mapping[state.fingerprint]:
            current = best.get(new)
            if current is None or _stamp(state) > _stamp(current):
                best[new] = state
    for new, source in best.items():
        if db.get(ErrorGroupState, new) is not None:
            continue  # a state set on the new group already wins
        db.add(
            ErrorGroupState(
                fingerprint=new,
                status=source.status,
                assignee=source.assignee,
                note=source.note,
                updated_at=source.updated_at,
            )
        )
    db.commit()


if __name__ == "__main__":
    from app.database import SessionLocal

    with SessionLocal() as session:
        total, moved = refingerprint(session)
    print(f"scanned {total} fingerprinted entries, updated {moved}", file=sys.stdout)
