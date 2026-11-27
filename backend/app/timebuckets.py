"""Time-bucket helpers shared by the dashboard timeline and log histogram.

Bucketing is portable: ``date_trunc`` on PostgreSQL, ``strftime`` on SQLite
(tests). Bucket keys are normalised to UTC datetimes so empty buckets can be
zero-filled, keeping chart x axes linear in time.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.models import LogEntry

# SQLite strftime patterns matching PostgreSQL date_trunc(<label>, ...).
SQLITE_PATTERNS = {
    "minute": "%Y-%m-%dT%H:%M:00",
    "hour": "%Y-%m-%dT%H:00:00",
    "day": "%Y-%m-%dT00:00:00",
    "month": "%Y-%m-01T00:00:00",
}


def trunc_expr(dialect: str, label: str):
    """SQL expression truncating ``LogEntry.timestamp`` to ``label``."""
    if dialect == "sqlite":
        return func.strftime(SQLITE_PATTERNS[label], LogEntry.timestamp)
    # Truncate in UTC explicitly: date_trunc on a timestamptz uses the
    # session TimeZone, which would misalign keys with the UTC zero-fill
    # grid (data rendered as zeros) whenever the DB timezone is not UTC.
    return func.date_trunc(label, func.timezone("UTC", LogEntry.timestamp))


def as_utc(value: object) -> datetime | None:
    """Bucket keys come back as datetimes (PostgreSQL) or text (SQLite)."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def truncate(value: datetime, label: str) -> datetime:
    """Python-side equivalent of ``date_trunc`` (UTC)."""
    value = as_utc(value) or value
    if label == "minute":
        return value.replace(second=0, microsecond=0)
    if label == "hour":
        return value.replace(minute=0, second=0, microsecond=0)
    if label == "day":
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def next_bucket(value: datetime, label: str) -> datetime:
    if label == "minute":
        return value + timedelta(minutes=1)
    if label == "hour":
        return value + timedelta(hours=1)
    if label == "day":
        return value + timedelta(days=1)
    return value.replace(year=value.year + (value.month == 12), month=value.month % 12 + 1)


def step_back(value: datetime, label: str, steps: int) -> datetime:
    """``value`` moved ``steps`` whole buckets into the past (not months)."""
    unit = {"minute": timedelta(minutes=1), "hour": timedelta(hours=1), "day": timedelta(days=1)}[label]
    return value - unit * steps


def zero_filled(
    counts: dict[datetime, tuple[int, int]], label: str, max_points: int
) -> list[tuple[datetime, int, int]]:
    """Every bucket from the first to the last key, missing ones as zeros."""
    if not counts:
        return []
    out: list[tuple[datetime, int, int]] = []
    cursor, end = min(counts), max(counts)
    while cursor <= end and len(out) < max_points:
        total, errors = counts.get(cursor, (0, 0))
        out.append((cursor, total, errors))
        cursor = next_bucket(cursor, label)
    return out
