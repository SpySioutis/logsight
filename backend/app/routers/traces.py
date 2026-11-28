"""Trace correlation: follow one trace/request across services and time."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LogEntry
from app.schemas import LogEntryOut, TraceDetail, TraceSummary

router = APIRouter(prefix="/traces", tags=["traces"])

MAX_TRACE_ENTRIES = 500


def _trace_filter(trace_id: str):
    return or_(LogEntry.trace_id == trace_id, LogEntry.request_id == trace_id)


@router.get("", response_model=list[TraceSummary])
def list_traces(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[TraceSummary]:
    rows = (
        db.query(
            LogEntry.trace_id,
            func.count(LogEntry.id).label("count"),
            func.min(LogEntry.timestamp).label("first_seen"),
            func.max(LogEntry.timestamp).label("last_seen"),
        )
        .filter(LogEntry.trace_id.isnot(None))
        .group_by(LogEntry.trace_id)
        .order_by(func.max(LogEntry.timestamp).desc())
        .limit(limit)
        .all()
    )
    trace_ids = [r.trace_id for r in rows if r.trace_id]
    # Two batched queries for all traces instead of two per trace.
    services: dict[str, list[str]] = {}
    severities: dict[str, set[str]] = {}
    if trace_ids:
        for tid, service in (
            db.query(LogEntry.trace_id, LogEntry.service)
            .filter(LogEntry.trace_id.in_(trace_ids))
            .filter(LogEntry.service.isnot(None))
            .distinct()
            .order_by(LogEntry.trace_id, LogEntry.service)
            .all()
        ):
            bucket = services.setdefault(tid, [])
            if len(bucket) < 10:
                bucket.append(service)
        for tid, severity in (
            db.query(LogEntry.trace_id, LogEntry.severity)
            .filter(LogEntry.trace_id.in_(trace_ids))
            .distinct()
            .all()
        ):
            severities.setdefault(tid, set()).add(severity)
    return [
        TraceSummary(
            trace_id=r.trace_id or "",
            count=r.count,
            services=services.get(r.trace_id or "", []),
            severities=sorted(severities.get(r.trace_id or "", set())),
            first_seen=r.first_seen,
            last_seen=r.last_seen,
        )
        for r in rows
    ]


@router.get("/{trace_id}", response_model=TraceDetail)
def get_trace(
    trace_id: str = Path(max_length=128),
    db: Session = Depends(get_db),
) -> TraceDetail:
    base = db.query(LogEntry).filter(_trace_filter(trace_id))
    total = base.with_entities(func.count(LogEntry.id)).scalar() or 0
    if total == 0:
        raise HTTPException(status_code=404, detail="Trace not found.")
    entries = (
        base.order_by(LogEntry.timestamp.asc().nullslast(), LogEntry.id.asc())
        .limit(MAX_TRACE_ENTRIES)
        .all()
    )
    agg = (
        db.query(
            func.min(LogEntry.timestamp),
            func.max(LogEntry.timestamp),
        )
        .filter(_trace_filter(trace_id))
        .first()
    )
    first_seen, last_seen = (agg or (None, None))
    services = sorted(
        {
            s[0]
            for s in db.query(LogEntry.service)
            .filter(_trace_filter(trace_id))
            .filter(LogEntry.service.isnot(None))
            .distinct()
            .all()
        }
    )
    severities = sorted(
        {s[0] for s in db.query(LogEntry.severity).filter(_trace_filter(trace_id)).distinct().all()}
    )
    duration = None
    if first_seen is not None and last_seen is not None:
        duration = (last_seen - first_seen).total_seconds()
    return TraceDetail(
        trace_id=trace_id,
        count=total,
        services=services,
        severities=severities,
        first_seen=first_seen,
        last_seen=last_seen,
        duration_seconds=duration,
        entries=[LogEntryOut.model_validate(e) for e in entries],
    )
