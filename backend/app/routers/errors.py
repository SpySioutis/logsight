"""Error analysis: deterministic fingerprint groups over stored entries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ErrorGroupState, LogEntry
from app.timebuckets import as_utc, step_back, trunc_expr, truncate, zero_filled
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
    query = (
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
    )
    if status is not None:
        # Filter by lifecycle state in SQL, *before* LIMIT: filtering the
        # top-N afterwards silently dropped matching groups outside it.
        # Missing state row means "open".
        stated = select(ErrorGroupState.fingerprint)
        if status == "open":
            query = query.filter(
                or_(
                    LogEntry.fingerprint.notin_(stated),
                    LogEntry.fingerprint.in_(stated.where(ErrorGroupState.status == "open")),
                )
            )
        else:
            query = query.filter(LogEntry.fingerprint.in_(stated.where(ErrorGroupState.status == status)))
    rows = (
        query.group_by(LogEntry.fingerprint)
        .order_by(func.count(LogEntry.id).desc(), LogEntry.fingerprint)
        .limit(limit)
        .all()
    )
    fingerprints = [r.fingerprint for r in rows if r.fingerprint]
    states = _states_map(db, fingerprints)
    # One query for all groups' sources instead of one per group.
    sources_by_fp: dict[str, list[str]] = {}
    if fingerprints:
        source_rows = (
            db.query(LogEntry.fingerprint, LogEntry.source)
            .filter(LogEntry.fingerprint.in_(fingerprints))
            .filter(LogEntry.source.isnot(None))
            .distinct()
            .order_by(LogEntry.fingerprint, LogEntry.source)
            .all()
        )
        for fp, src in source_rows:
            bucket = sources_by_fp.setdefault(fp, [])
            if len(bucket) < 10:
                bucket.append(src)
    groups: list[ErrorGroup] = []
    for r in rows:
        state = states.get(r.fingerprint or "")
        groups.append(
            ErrorGroup(
                fingerprint=r.fingerprint or "",
                sample=(r.sample or "")[:280],
                severity=r.severity,
                count=r.count,
                sources=sources_by_fp.get(r.fingerprint or "", []),
                first_seen=r.first_seen,
                last_seen=r.last_seen,
                status=state.status if state else "open",
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
    """Zero-filled occurrence counts for one group.

    The window ends at the newest stored entry overall (not the group's
    last occurrence), so trailing zeros show that an error stopped.
    """
    if bucket not in ("hour", "day"):
        bucket = "day"
    latest = as_utc(db.query(func.max(LogEntry.timestamp)).scalar())
    first = as_utc(
        db.query(func.min(LogEntry.timestamp)).filter(LogEntry.fingerprint == fingerprint).scalar()
    )
    if latest is None or first is None:
        return []
    end = truncate(latest, bucket)
    start = max(truncate(first, bucket), step_back(end, bucket, limit - 1))
    trunc = trunc_expr(db.get_bind().dialect.name, bucket)
    rows = (
        db.query(trunc.label("bucket"), func.count(LogEntry.id).label("count"))
        .filter(LogEntry.fingerprint == fingerprint)
        .filter(LogEntry.timestamp >= start)
        .group_by(trunc)
        .all()
    )
    counts = {key: (r.count, 0) for r in rows if (key := as_utc(r.bucket)) is not None}
    counts.setdefault(start, (0, 0))
    counts.setdefault(end, (0, 0))
    return [
        ErrorTrendPoint(bucket=key.isoformat(), count=count)
        for key, count, _ in zero_filled(counts, bucket, limit)
    ]
