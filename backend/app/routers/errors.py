"""Error analysis: deterministic fingerprint groups over stored entries."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ErrorGroupState, LogEntry
from app.schemas import ErrorGroup, ErrorGroupStateIn, ErrorGroupStateOut, ErrorTrendPoint, LogEntryOut, LogPage

router = APIRouter(prefix="/errors", tags=["errors"])

_ERROR_SEVERITIES = ("ERROR", "FATAL", "CRITICAL")
_STATUSES = ("open", "acknowledged", "resolved", "muted")


def _states_map(db: Session, fingerprints: list[str | None]) -> dict[str, ErrorGroupState]:
    wanted = [f for f in fingerprints if f]
    if not wanted:
        return {}
    rows = db.query(ErrorGroupState).filter(ErrorGroupState.fingerprint.in_(wanted)).all()
    return {r.fingerprint: r for r in rows}


@router.get("/groups", response_model=list[ErrorGroup])
def error_groups(
    limit: int = Query(default=50, ge=1, le=200),
    severity: list[str] | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ErrorGroup]:
    if status is not None and status not in _STATUSES:
        raise HTTPException(
            status_code=400, detail=f"Invalid status. Use one of: {list(_STATUSES)}."
        )
    severities = list(severity) if severity else list(_ERROR_SEVERITIES)
    rows = (
        db.query(
            LogEntry.fingerprint,
            func.min(LogEntry.message).label("sample"),
            func.min(LogEntry.severity).label("severity"),
            func.count(LogEntry.id).label("count"),
            func.min(LogEntry.timestamp).label("first_seen"),
            func.max(LogEntry.timestamp).label("last_seen"),
        )
        .filter(LogEntry.severity.in_(severities))
        .filter(LogEntry.fingerprint.isnot(None))
        .group_by(LogEntry.fingerprint)
        .order_by(func.count(LogEntry.id).desc())
        .limit(limit)
        .all()
    )
    states = _states_map(db, [r.fingerprint for r in rows])
    groups: list[ErrorGroup] = []
    for r in rows:
        state = states.get(r.fingerprint or "")
        effective_status = state.status if state else "open"
        if status is not None and effective_status != status:
            continue
        sources = [
            s[0]
            for s in (
                db.query(LogEntry.source)
                .filter(LogEntry.fingerprint == r.fingerprint)
                .filter(LogEntry.source.isnot(None))
                .distinct()
                .limit(10)
                .all()
            )
        ]
        groups.append(
            ErrorGroup(
                fingerprint=r.fingerprint or "",
                sample=(r.sample or "")[:280],
                severity=r.severity,
                count=r.count,
                sources=sources,
                first_seen=r.first_seen,
                last_seen=r.last_seen,
                status=effective_status,
                assignee=state.assignee if state else None,
                note=state.note if state else None,
            )
        )
    return groups


@router.get("/groups/{fingerprint}", response_model=LogPage)
def error_group_entries(
    fingerprint: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> LogPage:
    query = (
        db.query(LogEntry)
        .filter(LogEntry.fingerprint == fingerprint)
        .order_by(LogEntry.timestamp.desc(), LogEntry.id.desc())
    )
    # Count with a filter-only query: reusing `query` would carry its
    # ORDER BY into the aggregate, which PostgreSQL rejects.
    total = (
        db.query(func.count(LogEntry.id)).filter(LogEntry.fingerprint == fingerprint).scalar() or 0
    )
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    pages = max(1, (total + page_size - 1) // page_size)
    return LogPage(
        items=[LogEntryOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.put("/groups/{fingerprint}/state", response_model=ErrorGroupStateOut)
def set_group_state(
    fingerprint: str,
    payload: ErrorGroupStateIn,
    db: Session = Depends(get_db),
) -> ErrorGroupState:
    record = db.get(ErrorGroupState, fingerprint)
    assignee = payload.assignee.strip() if payload.assignee and payload.assignee.strip() else None
    note = payload.note.strip() if payload.note and payload.note.strip() else None
    if record is None:
        exists = db.query(LogEntry.id).filter(LogEntry.fingerprint == fingerprint).first()
        if exists is None:
            raise HTTPException(status_code=404, detail="Error group not found.")
        record = ErrorGroupState(
            fingerprint=fingerprint, status=payload.status, assignee=assignee, note=note
        )
        db.add(record)
    else:
        record.status = payload.status
        record.assignee = assignee
        record.note = note
    db.commit()
    db.refresh(record)
    return record


@router.get("/groups/{fingerprint}/trend", response_model=list[ErrorTrendPoint])
def group_trend(
    fingerprint: str,
    bucket: str = Query(default="day"),
    limit: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> list[ErrorTrendPoint]:
    if bucket not in ("hour", "day"):
        bucket = "day"
    if db.get_bind().dialect.name == "sqlite":
        pattern = "%Y-%m-%d %H:00" if bucket == "hour" else "%Y-%m-%d"
        trunc = func.strftime(pattern, LogEntry.timestamp)
    else:
        trunc = func.date_trunc(bucket, LogEntry.timestamp)
    rows = (
        db.query(trunc.label("bucket"), func.count(LogEntry.id).label("count"))
        .filter(LogEntry.fingerprint == fingerprint)
        .filter(LogEntry.timestamp.isnot(None))
        .group_by(trunc)
        .order_by(trunc.desc())
        .limit(limit)
        .all()
    )
    points = [
        ErrorTrendPoint(
            bucket=r.bucket.isoformat() if isinstance(r.bucket, datetime) else str(r.bucket),
            count=r.count,
        )
        for r in rows
    ]
    return list(reversed(points))
