"""Canonical severity levels and normalization.

Accepted levels: TRACE, DEBUG, INFO, WARN, WARNING, ERROR, FATAL, CRITICAL, UNKNOWN.
Equivalent values are normalized (e.g. "warn" -> WARN, "err" -> ERROR).
Anything unrecognized becomes UNKNOWN and is never discarded.
"""

from __future__ import annotations

TRACE = "TRACE"
DEBUG = "DEBUG"
INFO = "INFO"
WARN = "WARN"
WARNING = "WARNING"
ERROR = "ERROR"
FATAL = "FATAL"
CRITICAL = "CRITICAL"
UNKNOWN = "UNKNOWN"

#: All severity values accepted by the API and stored in the database.
SEVERITIES: tuple[str, ...] = (
    TRACE,
    DEBUG,
    INFO,
    WARN,
    WARNING,
    ERROR,
    FATAL,
    CRITICAL,
    UNKNOWN,
)

#: Lowercase alias -> canonical severity.
_ALIASES: dict[str, str] = {
    "trace": TRACE,
    "trc": TRACE,
    "debug": DEBUG,
    "dbg": DEBUG,
    "info": INFO,
    "information": INFO,
    "notice": INFO,
    "note": INFO,
    "warn": WARN,
    "warning": WARNING,
    "error": ERROR,
    "err": ERROR,
    "eror": ERROR,
    "fatal": FATAL,
    "critical": CRITICAL,
    "crit": CRITICAL,
    "critial": CRITICAL,
    "alert": CRITICAL,
    "emergency": CRITICAL,
    "emerg": CRITICAL,
    "unknown": UNKNOWN,
    "none": UNKNOWN,
    "": UNKNOWN,
}

#: Python logging style numeric levels -> canonical severity.
_NUMERIC: list[tuple[int, str]] = [
    (50, CRITICAL),
    (40, ERROR),
    (30, WARNING),
    (20, INFO),
    (10, DEBUG),
]


def normalize_severity(value: object) -> str:
    """Normalize any raw severity value to a canonical severity string."""
    if value is None:
        return UNKNOWN
    if isinstance(value, bool):
        return UNKNOWN
    if isinstance(value, (int, float)):
        level = int(value)
        for threshold, name in _NUMERIC:
            if level >= threshold:
                return name
        return TRACE if level >= 0 else UNKNOWN
    text = str(value).strip()
    if not text:
        return UNKNOWN
    lowered = text.lower()
    if lowered in _ALIASES:
        return _ALIASES[lowered]
    # Numeric strings such as "30" or "ERROR: ..." prefixes.
    if lowered.isdigit():
        return normalize_severity(int(lowered))
    return UNKNOWN


def is_error_like(severity: str) -> bool:
    return severity in (ERROR, FATAL, CRITICAL)


def is_warning_like(severity: str) -> bool:
    return severity in (WARN, WARNING)
