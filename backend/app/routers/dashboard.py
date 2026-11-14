"""Dashboard statistics computed from stored data only."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Import, LogEntry
from app.schemas import DashboardSummary, SeverityBucket, SourceBucket, TimelinePoint, TopError

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_ERROR_SEVERITIES = ("ERROR", "FATAL", "CRITICAL")
_WARNING_SEVERITIES = ("WARN", "WARNING")


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db)) -> DashboardSummary:
    total = db.query(func.count(LogEntry.id)).scalar() or 0
    errors = db.query(func.count(LogEntry.id)).filter(LogEntry.severity.in_(_ERROR_SEVERITIES)).scalar() or 0
    warnings = db.query(func.count(LogEntry.id)).filter(LogEntry.severity.in_(_WARNING_SEVERITIES)).scalar() or 0
    info = db.query(func.count(LogEntry.id)).filter(LogEntry.severity == "INFO").scalar() or 0
    critical = db.query(func.count(LogEntry.id)).filter(LogEntry.severity == "CRITICAL").scalar() or 0
    sources = (
        db.query(func.count(func.distinct(LogEntry.source))).filter(LogEntry.source.isnot(None)).scalar() or 0
    )
    imports = db.query(func.count(Import.id)).scalar() or 0
    first_seen = db.query(func.min(LogEntry.timestamp)).scalar()
    last_seen = db.query(func.max(LogEntry.timestamp)).scalar()
    return DashboardSummary(
        total=total,
        errors=errors,
        warnings=warnings,
        info=info,
        critical=critical,
        sources=sources,
        imports=imports,
        first_seen=first_seen,
        last_seen=last_seen,
    )


@router.get("/timeline", response_model=list[TimelinePoint])
def timeline(
    bucket: str = Query(default="day"),
    limit: int = Query(default=60, ge=1, le=365),
    db: Session = Depends(get_db),
) -> list[TimelinePoint]:
    if bucket not in ("hour", "day"):
        bucket = "day"
    # Portable bucketing: date_trunc on PostgreSQL, strftime on SQLite (tests).
    if db.get_bind().dialect.name == "sqlite":
        pattern = "%Y-%m-%d %H:00" if bucket == "hour" else "%Y-%m-%d"
        trunc = func.strftime(pattern, LogEntry.timestamp)
    else:
        trunc = func.date_trunc(bucket, LogEntry.timestamp)
    rows = (
        db.query(
            trunc.label("bucket"),
            func.count(LogEntry.id).label("total"),
            func.count().filter(LogEntry.severity.in_(_ERROR_SEVERITIES)).label("errors"),
        )
        .filter(LogEntry.timestamp.isnot(None))
        .group_by(trunc)
        .order_by(trunc.desc())
        .limit(limit)
        .all()
    )
    points = [
        TimelinePoint(
            bucket=r.bucket.isoformat() if isinstance(r.bucket, datetime) else str(r.bucket),
            total=r.total,
            errors=r.errors,
        )
        for r in rows
    ]
    return list(reversed(points))


@router.get("/severity-distribution", response_model=list[SeverityBucket])
def severity_distribution(db: Session = Depends(get_db)) -> list[SeverityBucket]:
    rows = db.query(LogEntry.severity, func.count(LogEntry.id)).group_by(LogEntry.severity).all()
    return [SeverityBucket(severity=s, count=c) for s, c in sorted(rows)]


@router.get("/top-sources", response_model=list[SourceBucket])
def top_sources(limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db)) -> list[SourceBucket]:
    rows = (
        db.query(LogEntry.source, func.count(LogEntry.id).label("count"))
        .filter(LogEntry.source.isnot(None))
        .group_by(LogEntry.source)
        .order_by(func.count(LogEntry.id).desc())
        .limit(limit)
        .all()
    )
    return [SourceBucket(source=s or "(unknown)", count=c) for s, c in rows]


@router.get("/top-errors", response_model=list[TopError])
def top_errors(limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db)) -> list[TopError]:
    rows = (
        db.query(
            LogEntry.fingerprint,
            func.min(LogEntry.message).label("sample"),
            func.min(LogEntry.severity).label("severity"),
            func.count(LogEntry.id).label("count"),
            func.min(LogEntry.timestamp).label("first_seen"),
            func.max(LogEntry.timestamp).label("last_seen"),
        )
        .filter(LogEntry.severity.in_(_ERROR_SEVERITIES))
        .group_by(LogEntry.fingerprint)
        .order_by(func.count(LogEntry.id).desc())
        .limit(limit)
        .all()
    )
    return [
        TopError(
            fingerprint=r.fingerprint or "",
            sample=(r.sample or "")[:280],
            severity=r.severity,
            count=r.count,
            first_seen=r.first_seen,
            last_seen=r.last_seen,
        )
        for r in rows
    ]
