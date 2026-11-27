"""Log explorer endpoints: filtering, sorting, pagination, export, histogram, context."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, literal, select, text, tuple_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LogEntry
from app.schemas import LogContext, LogEntryOut, LogHistogram, LogPage, TimelinePoint
from app.search import (
    ParsedQuery,
    apply_field_filters,
    apply_ilike_search,
    contains_ci,
    highlight_snippet,
    parse_search_query,
)
from app.severity import SEVERITIES, normalize_severity
from app.timebuckets import as_utc, trunc_expr, zero_filled

router = APIRouter(prefix="/logs", tags=["logs"])

MAX_PAGE_SIZE = 500
MAX_EXPORT_ROWS = 100_000
EXPORT_CHUNK = 2_000
ERROR_SEVERITIES = ("ERROR", "FATAL", "CRITICAL")
MAX_HISTOGRAM_POINTS = 400
SORT_COLUMNS = {
    "timestamp": LogEntry.timestamp,
    "severity": LogEntry.severity,
    "source": LogEntry.source,
    "service": LogEntry.service,
}
SORT_FIELDS = (*SORT_COLUMNS, "relevance")

# Must stay identical to the expression in migrations/0008_search_split_tokens.sql
# so PostgreSQL matches the ix_log_entries_search GIN index. The translate()
# set must match search.FTS_SPLIT_CHARS.
_SEARCH_VECTOR_EXPR = (
    "to_tsvector('english', translate(coalesce(message, '') || ' ' || coalesce(service, '') || ' ' || "
    "coalesce(source, '') || ' ' || coalesce(trace_id, '') || ' ' || coalesce(request_id, ''), "
    "'/.@:', '    '))"
)


def apply_filters(
    query,
    *,
    parsed: ParsedQuery | None,
    severities: list[str] | None,
    source: str | None,
    service: str | None,
    import_id: str | None,
    trace_id: str | None,
    request_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    dialect: str = "sqlite",
    fingerprint: str | None = None,
):
    if parsed is not None and parsed.has_fts:
        if dialect == "postgresql" and parsed.websearch_text:
            # Match ids in an uncorrelated subquery so the expensive
            # to_tsvector() expression is evaluated once via the GIN bitmap.
            # The OFFSET 0 is load-bearing: without it PostgreSQL flattens
            # the IN-subquery into "timestamp index scan + per-row
            # to_tsvector()", which scans the whole table when matches are
            # rare. Do not remove it.
            match_ids = (
                select(LogEntry.id)
                .where(
                    text(
                        f"{_SEARCH_VECTOR_EXPR} @@ websearch_to_tsquery('english', :wsq)"
                    ).bindparams(wsq=parsed.websearch_text)
                )
                .offset(0)
            )
            query = query.filter(LogEntry.id.in_(match_ids))
        else:
            query = apply_ilike_search(query, parsed)
    if parsed is not None:
        query = apply_field_filters(query, parsed)
    if severities:
        # Normalize client-supplied severities; drop empties, never 500 on bad input.
        wanted = {normalize_severity(s) for s in severities if s}
        query = query.filter(LogEntry.severity.in_(sorted(wanted)))
    if source:
        query = query.filter(contains_ci(LogEntry.source, source))
    if service:
        query = query.filter(contains_ci(LogEntry.service, service))
    if import_id:
        query = query.filter(LogEntry.import_id == import_id)
    if trace_id:
        query = query.filter(LogEntry.trace_id == trace_id)
    if request_id:
        query = query.filter(LogEntry.request_id == request_id)
    if fingerprint:
        query = query.filter(LogEntry.fingerprint == fingerprint)
    if date_from:
        query = query.filter(LogEntry.timestamp >= date_from)
    if date_to:
        query = query.filter(LogEntry.timestamp <= date_to)
    return query


@dataclass
class LogFilters:
    """Explorer filter parameters shared by list, export and histogram."""

    q: str | None
    severity: list[str] | None
    source: str | None
    service: str | None
    import_id: str | None
    trace_id: str | None
    request_id: str | None
    date_from: datetime | None
    date_to: datetime | None
    fingerprint: str | None = None


def log_filters(
    q: str | None = Query(default=None, max_length=500),
    severity: list[str] | None = Query(default=None),
    source: str | None = Query(default=None, max_length=512),
    service: str | None = Query(default=None, max_length=256),
    import_id: str | None = Query(default=None),
    trace_id: str | None = Query(default=None, max_length=128),
    request_id: str | None = Query(default=None, max_length=128),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    fingerprint: str | None = Query(default=None, max_length=64),
) -> LogFilters:
    if severity:
        unknown = [s for s in severity if normalize_severity(s) == "UNKNOWN" and s.strip().upper() != "UNKNOWN"]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown severity value(s): {unknown}. Valid: {list(SEVERITIES)}.",
            )
    return LogFilters(q, severity, source, service, import_id, trace_id, request_id, date_from, date_to, fingerprint)


def _validate_sort(sort: str, direction: str) -> None:
    if sort not in SORT_FIELDS:
        raise HTTPException(status_code=400, detail=f"Invalid sort field. Use one of: {sorted(SORT_FIELDS)}.")
    if direction not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="direction must be 'asc' or 'desc'.")


def _filtered(db: Session, filters: LogFilters, base=None) -> tuple[object, ParsedQuery, str]:
    parsed = parse_search_query(filters.q)
    dialect = db.get_bind().dialect.name
    query = apply_filters(
        base if base is not None else db.query(LogEntry),
        parsed=parsed,
        severities=filters.severity,
        source=filters.source,
        service=filters.service,
        import_id=filters.import_id,
        trace_id=filters.trace_id,
        request_id=filters.request_id,
        date_from=filters.date_from,
        date_to=filters.date_to,
        dialect=dialect,
        fingerprint=filters.fingerprint,
    )
    return query, parsed, dialect


def _ordered(query, parsed: ParsedQuery, dialect: str, sort: str, direction: str):
    if sort == "relevance":
        if parsed.has_fts and dialect == "postgresql" and parsed.websearch_text:
            return query.order_by(
                text(
                    f"ts_rank({_SEARCH_VECTOR_EXPR}, websearch_to_tsquery('english', :wsq)) DESC"
                ).bindparams(wsq=parsed.websearch_text),
                LogEntry.id.desc(),
            )
        return query.order_by(LogEntry.timestamp.desc(), LogEntry.id.desc())
    column = SORT_COLUMNS[sort]
    return query.order_by(column.asc() if direction == "asc" else column.desc(), LogEntry.id.desc())


@router.get("", response_model=LogPage)
def list_logs(
    filters: LogFilters = Depends(log_filters),
    sort: str = Query(default="timestamp"),
    direction: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> LogPage:
    _validate_sort(sort, direction)
    query, parsed, dialect = _filtered(db, filters)
    # NB: count the PK column so SQLAlchemy keeps the FROM clause
    # (bare func.count() would count a single FROM-less row).
    total = query.with_entities(func.count(LogEntry.id)).scalar() or 0
    ordered = _ordered(query, parsed, dialect, sort, direction)
    items = ordered.offset((page - 1) * page_size).limit(page_size).all()
    pages = max(1, (total + page_size - 1) // page_size)
    results: list[LogEntryOut] = []
    for item in items:
        out = LogEntryOut.model_validate(item)
        if parsed.has_fts:
            out.snippet = highlight_snippet(item.message, parsed)
        results.append(out)
    return LogPage(
        items=results,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


_EXPORT_FIELDS = (
    "timestamp",
    "severity",
    "service",
    "source",
    "message",
    "trace_id",
    "request_id",
    "fingerprint",
    "import_id",
    "id",
)


def _csv_cell(value: str | None) -> str:
    """Neutralise spreadsheet formula injection in exported cells."""
    if value and value[0] in "=+-@\t\r":
        return "'" + value
    return value or ""


@router.get("/export")
def export_logs(
    filters: LogFilters = Depends(log_filters),
    format: str = Query(default="csv"),
    sort: str = Query(default="timestamp"),
    direction: str = Query(default="desc"),
    limit: int = Query(default=MAX_EXPORT_ROWS, ge=1, le=MAX_EXPORT_ROWS),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream every entry matching the explorer filters as CSV or JSONL.

    Same filters and ordering as ``GET /logs``; capped at ``MAX_EXPORT_ROWS``
    rows. Streamed from a server-side cursor so memory stays flat.
    """
    if format not in ("csv", "jsonl"):
        raise HTTPException(status_code=400, detail="format must be 'csv' or 'jsonl'.")
    _validate_sort(sort, direction)
    query, parsed, dialect = _filtered(db, filters)
    ordered = _ordered(query, parsed, dialect, sort, direction)

    def rows() -> Iterator[LogEntry]:
        # One query streamed through a server-side cursor (PostgreSQL) in
        # EXPORT_CHUNK batches: re-querying per chunk with OFFSET re-ran the
        # full-text match (and ts_rank) once per chunk. The get_db session
        # stays open until the response finishes (FastAPI >= 0.118 runs
        # yield-dependency teardown after the body is sent). The identity
        # map holds rows weakly, so memory stays flat without expunging
        # (expunge_all() mid-iteration would invalidate the cursor's map).
        yield from ordered.limit(limit).yield_per(EXPORT_CHUNK)

    def as_csv() -> Iterator[str]:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(_EXPORT_FIELDS)
        for entry in rows():
            writer.writerow(
                [
                    entry.timestamp.isoformat() if entry.timestamp else "",
                    entry.severity,
                    _csv_cell(entry.service),
                    _csv_cell(entry.source),
                    _csv_cell(entry.message),
                    _csv_cell(entry.trace_id),
                    _csv_cell(entry.request_id),
                    entry.fingerprint or "",
                    entry.import_id,
                    entry.id,
                ]
            )
            if buf.tell() > 64 * 1024:
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate()
        yield buf.getvalue()

    def as_jsonl() -> Iterator[str]:
        # Buffered like CSV: Starlette hops to a worker thread per yielded
        # chunk of a sync generator, so one yield per row is ~10x slower.
        parts: list[str] = []
        size = 0
        for entry in rows():
            record = {name: getattr(entry, name) for name in _EXPORT_FIELDS}
            record["timestamp"] = entry.timestamp.isoformat() if entry.timestamp else None
            record["attributes"] = entry.attributes or {}
            line = json.dumps(record, ensure_ascii=False) + "\n"
            parts.append(line)
            size += len(line)
            if size > 64 * 1024:
                yield "".join(parts)
                parts, size = [], 0
        yield "".join(parts)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    media = "text/csv" if format == "csv" else "application/x-ndjson"
    return StreamingResponse(
        as_csv() if format == "csv" else as_jsonl(),
        media_type=f"{media}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="logsight-export-{stamp}.{format}"'},
    )


# (bucket label, widest matched span it is used for); the last is open-ended.
_HISTOGRAM_BUCKETS = (
    ("minute", timedelta(hours=3)),
    ("hour", timedelta(days=7)),
    ("day", timedelta(days=365)),
    ("month", None),
)


@router.get("/histogram", response_model=LogHistogram)
def histogram(
    filters: LogFilters = Depends(log_filters),
    db: Session = Depends(get_db),
) -> LogHistogram:
    """Entry counts over time for the current explorer filters.

    The bucket size adapts to the matched time span (minute/hour/day/month)
    so the chart stays readable from a single burst to years of history.
    Empty buckets are zero-filled so the x axis is linear in time.
    """
    query, _parsed, dialect = _filtered(db, filters)
    first, last = query.with_entities(func.min(LogEntry.timestamp), func.max(LogEntry.timestamp)).one()
    first, last = as_utc(first), as_utc(last)
    if first is None or last is None:
        return LogHistogram(bucket="hour", points=[])
    label = next(name for name, widest in _HISTOGRAM_BUCKETS if widest is None or last - first <= widest)
    trunc = trunc_expr(dialect, label)
    rows = (
        query.with_entities(
            trunc.label("bucket"),
            func.count(LogEntry.id).label("total"),
            func.count(LogEntry.id).filter(LogEntry.severity.in_(ERROR_SEVERITIES)).label("errors"),
        )
        .filter(LogEntry.timestamp.isnot(None))
        .group_by(trunc)
        .all()
    )
    counts = {key: (r.total, r.errors) for r in rows if (key := as_utc(r.bucket)) is not None}
    return LogHistogram(
        bucket=label,
        points=[
            TimelinePoint(bucket=key.isoformat(), total=total, errors=errors)
            for key, total, errors in zero_filled(counts, label, MAX_HISTOGRAM_POINTS)
        ],
    )


@router.get("/{entry_id}", response_model=LogEntryOut)
def get_log(entry_id: str, db: Session = Depends(get_db)) -> LogEntry:
    entry = db.get(LogEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Log entry not found.")
    return entry


@router.get("/{entry_id}/context", response_model=LogContext)
def entry_context(
    entry_id: str,
    before: int = Query(default=10, ge=0, le=200),
    after: int = Query(default=10, ge=0, le=200),
    db: Session = Depends(get_db),
) -> LogContext:
    """Entries surrounding one entry in its original file (same import).

    Uses the per-import ``seq`` (file order). Rows imported before
    migration 0007 have no ``seq`` and fall back to (timestamp, id) order.
    """
    entry = db.get(LogEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Log entry not found.")
    same_import = db.query(LogEntry).filter(LogEntry.import_id == entry.import_id)
    if entry.seq is not None:
        prev_rows = (
            same_import.filter(LogEntry.seq < entry.seq).order_by(LogEntry.seq.desc()).limit(before).all()
        )
        next_rows = same_import.filter(LogEntry.seq > entry.seq).order_by(LogEntry.seq.asc()).limit(after).all()
    elif entry.timestamp is not None:
        key = tuple_(LogEntry.timestamp, LogEntry.id)
        anchor = tuple_(literal(entry.timestamp, LogEntry.timestamp.type), literal(entry.id))
        prev_rows = (
            same_import.filter(key < anchor)
            .order_by(LogEntry.timestamp.desc(), LogEntry.id.desc())
            .limit(before)
            .all()
        )
        next_rows = (
            same_import.filter(key > anchor)
            .order_by(LogEntry.timestamp.asc(), LogEntry.id.asc())
            .limit(after)
            .all()
        )
    else:
        prev_rows, next_rows = [], []
    return LogContext(
        entry=LogEntryOut.model_validate(entry),
        before=[LogEntryOut.model_validate(r) for r in reversed(prev_rows)],
        after=[LogEntryOut.model_validate(r) for r in next_rows],
    )


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
