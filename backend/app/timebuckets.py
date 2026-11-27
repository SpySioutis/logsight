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
    """Next bucket start. Raises OverflowError past year 9999."""
    if label == "month" and value.year == 9999 and value.month == 12:
        raise OverflowError("date value out of range")
    if label == "minute":
        return value + timedelta(minutes=1)
    if label == "hour":
        return value + timedelta(hours=1)
    if label == "day":
        return value + timedelta(days=1)
    return value.replace(year=value.year + (value.month == 12), month=value.month % 12 + 1)


def step_back(value: datetime, label: str, steps: int) -> datetime:
    """``value`` moved ``steps`` whole buckets into the past (clamped at year 1)."""
    try:
        if label == "month":
            index = value.year * 12 + value.month - 1 - steps
            return value.replace(year=max(1, index // 12), month=index % 12 + 1)
        unit = {"minute": timedelta(minutes=1), "hour": timedelta(hours=1), "day": timedelta(days=1)}[label]
        return value - unit * steps
    except (OverflowError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)


def zero_filled(
    counts: dict[datetime, tuple[int, int]], label: str, max_points: int
) -> list[tuple[datetime, int, int]]:
    """Every bucket from the first to the last key, missing ones as zeros.

    When the range exceeds ``max_points`` the *newest* buckets are kept
    (an old outlier must not push the real, recent data out of the chart).
    """
    if not counts:
        return []
    end = max(counts)
    cursor = max(min(counts), step_back(end, label, max_points - 1))
    out: list[tuple[datetime, int, int]] = []
    while cursor <= end and len(out) < max_points:
        total, errors = counts.get(cursor, (0, 0))
        out.append((cursor, total, errors))
        try:
            cursor = next_bucket(cursor, label)
        except OverflowError:  # bucket at 9999-12-31: nothing after it
            break
    return out


def latest_plausible(db) -> datetime | None:
    """Newest entry timestamp that is not in the future (+1 day of skew).

    Windowed charts end here: a single mis-parsed far-future line (e.g. a
    "valid until 2099-01-01" date) must not move the window away from data.
    Falls back to the absolute newest when every entry is in the future.
    """
    horizon = datetime.now(timezone.utc) + timedelta(days=1)
    value = db.query(func.max(LogEntry.timestamp)).filter(LogEntry.timestamp <= horizon).scalar()
    if value is None:
        value = db.query(func.max(LogEntry.timestamp)).scalar()
    return as_utc(value)
