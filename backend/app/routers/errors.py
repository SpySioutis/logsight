"""Error analysis: deterministic fingerprint groups over stored entries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LogEntry
from app.schemas import ErrorGroup, LogEntryOut, LogPage

router = APIRouter(prefix="/errors", tags=["errors"])

_ERROR_SEVERITIES = ("ERROR", "FATAL", "CRITICAL")


@router.get("/groups", response_model=list[ErrorGroup])
def error_groups(
    limit: int = Query(default=50, ge=1, le=200),
    severity: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ErrorGroup]:
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
    groups: list[ErrorGroup] = []
    for r in rows:
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
