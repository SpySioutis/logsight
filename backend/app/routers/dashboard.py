"""Dashboard statistics computed from stored data only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ErrorGroupState, Import, LogEntry
from app.timebuckets import latest_plausible, as_utc, step_back, trunc_expr, truncate, zero_filled
from app.schemas import DashboardSummary, SeverityBucket, SourceBucket, TimelinePoint, TopError

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_ERROR_SEVERITIES = ("ERROR", "FATAL", "CRITICAL")
_WARNING_SEVERITIES = ("WARN", "WARNING")


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db)) -> DashboardSummary:
    # Single-pass aggregation: one scan instead of one per counter.
    # (Previously 8 sequential full-table queries; ~30 s on a large table.)
    row = (
        db.query(
            func.count(LogEntry.id).label("total"),
            func.count(LogEntry.id).filter(LogEntry.severity.in_(_ERROR_SEVERITIES)).label("errors"),
            func.count(LogEntry.id).filter(LogEntry.severity.in_(_WARNING_SEVERITIES)).label("warnings"),
            func.count(LogEntry.id).filter(LogEntry.severity == "INFO").label("info"),
            func.count(LogEntry.id).filter(LogEntry.severity == "CRITICAL").label("critical"),
            func.min(LogEntry.timestamp).label("first_seen"),
            func.max(LogEntry.timestamp).label("last_seen"),
        ).one()
    )
    # count(DISTINCT source) inside the aggregate above sorts every row
    # (5.9 s on 2M rows); a DISTINCT subquery hash-aggregates (0.1 s).
    distinct_sources = (
        db.query(LogEntry.source).filter(LogEntry.source.isnot(None)).distinct().subquery()
    )
    sources = db.query(func.count()).select_from(distinct_sources).scalar() or 0
    imports = db.query(func.count(Import.id)).scalar() or 0
    return DashboardSummary(
        total=row.total or 0,
        errors=row.errors or 0,
        warnings=row.warnings or 0,
        info=row.info or 0,
        critical=row.critical or 0,
        sources=sources,
        imports=imports,
        first_seen=row.first_seen,
        last_seen=row.last_seen,
    )


@router.get("/timeline", response_model=list[TimelinePoint])
def timeline(
    bucket: str = Query(default="day"),
    limit: int = Query(default=60, ge=1, le=365),
    db: Session = Depends(get_db),
) -> list[TimelinePoint]:
    """The last ``limit`` calendar buckets ending at the newest entry.

    Empty buckets are zero-filled so the chart's x axis is linear in time
    (previously only non-empty buckets were returned, so bursts months apart
    were drawn as neighbours). The window never starts before the oldest
    entry, so short histories are not padded with leading zeros.
    """
    if bucket not in ("hour", "day"):
        bucket = "day"
    first = as_utc(db.query(func.min(LogEntry.timestamp)).scalar())
    last = latest_plausible(db)
    if first is None or last is None:
        return []
    end = truncate(last, bucket)
    start = max(truncate(first, bucket), step_back(end, bucket, limit - 1))
    trunc = trunc_expr(db.get_bind().dialect.name, bucket)
    rows = (
        db.query(
            trunc.label("bucket"),
            func.count(LogEntry.id).label("total"),
            func.count(LogEntry.id).filter(LogEntry.severity.in_(_ERROR_SEVERITIES)).label("errors"),
        )
        .filter(LogEntry.timestamp >= start)
        .group_by(trunc)
        .all()
    )
    counts = {key: (r.total, r.errors) for r in rows if (key := as_utc(r.bucket)) is not None and key <= end}
    counts.setdefault(start, (0, 0))
    counts.setdefault(end, (0, 0))
    return [
        TimelinePoint(bucket=key.isoformat(), total=total, errors=errors)
        for key, total, errors in zero_filled(counts, bucket, limit)
    ]


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
    muted = select(ErrorGroupState.fingerprint).where(ErrorGroupState.status == "muted")
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
        .filter(LogEntry.fingerprint.notin_(muted))
        .group_by(LogEntry.fingerprint)
        .order_by(func.count(LogEntry.id).desc())
        .limit(limit)
        .all()
    )
    states = {
        r.fingerprint: r.status
        for r in db.query(ErrorGroupState)
        .filter(ErrorGroupState.fingerprint.in_([r.fingerprint for r in rows if r.fingerprint]))
        .all()
    }
    return [
        TopError(
            fingerprint=r.fingerprint or "",
            sample=(r.sample or "")[:280],
            severity=r.severity,
            count=r.count,
            first_seen=r.first_seen,
            last_seen=r.last_seen,
            status=states.get(r.fingerprint or "", "open"),
        )
        for r in rows
    ]
