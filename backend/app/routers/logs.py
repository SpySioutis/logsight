"""Log explorer endpoints: server-side filtering, sorting, pagination."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LogEntry
from app.schemas import LogEntryOut, LogPage
from app.severity import SEVERITIES, normalize_severity

router = APIRouter(prefix="/logs", tags=["logs"])

MAX_PAGE_SIZE = 500
SORT_COLUMNS = {
    "timestamp": LogEntry.timestamp,
    "severity": LogEntry.severity,
    "source": LogEntry.source,
    "service": LogEntry.service,
}


def apply_filters(
    query,
    *,
    q: str | None,
    severities: list[str] | None,
    source: str | None,
    service: str | None,
    import_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
):
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(LogEntry.message.ilike(like), LogEntry.source.ilike(like), LogEntry.service.ilike(like))
        )
    if severities:
        # Normalize client-supplied severities; drop empties, never 500 on bad input.
        wanted = {normalize_severity(s) for s in severities if s}
        query = query.filter(LogEntry.severity.in_(sorted(wanted)))
    if source:
        query = query.filter(LogEntry.source.ilike(f"%{source}%"))
    if service:
        query = query.filter(LogEntry.service.ilike(f"%{service}%"))
    if import_id:
        query = query.filter(LogEntry.import_id == import_id)
    if date_from:
        query = query.filter(LogEntry.timestamp >= date_from)
    if date_to:
        query = query.filter(LogEntry.timestamp <= date_to)
    return query


@router.get("", response_model=LogPage)
def list_logs(
    q: str | None = Query(default=None, max_length=500),
    severity: list[str] | None = Query(default=None),
    source: str | None = Query(default=None, max_length=512),
    service: str | None = Query(default=None, max_length=256),
    import_id: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    sort: str = Query(default="timestamp"),
    direction: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> LogPage:
    if sort not in SORT_COLUMNS:
        raise HTTPException(status_code=400, detail=f"Invalid sort field. Use one of: {sorted(SORT_COLUMNS)}.")
    if direction not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="direction must be 'asc' or 'desc'.")
    if severity:
        unknown = [s for s in severity if normalize_severity(s) == "UNKNOWN" and s.strip().upper() != "UNKNOWN"]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown severity value(s): {unknown}. Valid: {list(SEVERITIES)}.",
            )

    query = apply_filters(
        db.query(LogEntry),
        q=q,
        severities=severity,
        source=source,
        service=service,
        import_id=import_id,
        date_from=date_from,
        date_to=date_to,
    )
    # NB: count the PK column so SQLAlchemy keeps the FROM clause
    # (bare func.count() would count a single FROM-less row).
    total = query.with_entities(func.count(LogEntry.id)).scalar() or 0

    column = SORT_COLUMNS[sort]
    ordered = query.order_by(column.asc() if direction == "asc" else column.desc(), LogEntry.id.desc())
    items = ordered.offset((page - 1) * page_size).limit(page_size).all()
    pages = max(1, (total + page_size - 1) // page_size)
    return LogPage(
        items=[LogEntryOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{entry_id}", response_model=LogEntryOut)
def get_log(entry_id: str, db: Session = Depends(get_db)) -> LogEntry:
    entry = db.get(LogEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Log entry not found.")
    return entry


@router.get("/meta/facets", response_model=dict)
def facets(db: Session = Depends(get_db)) -> dict:
    """Distinct values for filter dropdowns (capped for UI use)."""
    severities = [r[0] for r in db.query(LogEntry.severity).distinct().order_by(LogEntry.severity).all()]
    sources = [
        r[0]
        for r in db.query(LogEntry.source).filter(LogEntry.source.isnot(None)).distinct().order_by(LogEntry.source).limit(200).all()
    ]
    services = [
        r[0]
        for r in db.query(LogEntry.service).filter(LogEntry.service.isnot(None)).distinct().order_by(LogEntry.service).limit(200).all()
    ]
    return {"severities": severities, "sources": sources, "services": services}
