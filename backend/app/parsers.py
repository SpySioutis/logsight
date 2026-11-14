"""Streaming log parsers for plain text, JSON Lines and structured JSON.

Parsers yield ParsedEntry records line-by-line so large files are never
fully loaded into memory (except single-document JSON arrays, which are
bounded by the configured upload size limit and documented as such).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import IO, Any, Iterator

from app.grouping import fingerprint
from app.severity import normalize_severity

MAX_LINE_LENGTH = 64 * 1024  # truncate pathological single lines


@dataclass
class ParsedEntry:
    timestamp: datetime | None
    severity: str
    service: str | None
    source: str | None
    message: str
    raw: str
    attributes: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.fingerprint and self.message:
            self.fingerprint = fingerprint(self.message)


# --- timestamp handling -----------------------------------------------------

_TS_PATTERNS: list[tuple[re.Pattern[str], str | None]] = [
    # ISO-8601 with optional timezone: 2024-05-01T12:34:56.789Z / +02:00
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d:?\d{2}:?(?::?\d{2})?)?"), None),
    # 2024-05-01 12:34:56,789
    (re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:[.,]\d+)?"), "%Y-%m-%d %H:%M:%S"),
    # Syslog: May  1 12:34:56
    (re.compile(r"[A-Z][a-z]{2}\s+\d{1,2} \d{2}:\d{2}:\d{2}"), "%b %d %H:%M:%S"),
    # Epoch seconds / millis at line start.
    (re.compile(r"^\d{10}(?:\d{3})?(?=\s)"), "epoch"),
]


def _parse_iso(text: str) -> datetime | None:
    candidate = text.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_timestamp(text: str) -> datetime | None:
    """Extract the first recognizable timestamp from arbitrary text."""
    text = text.strip()
    if not text:
        return None
    for pattern, kind in _TS_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        raw = match.group(0)
        if kind is None:
            parsed = _parse_iso(raw)
            if parsed is not None:
                return parsed
        elif kind == "epoch":
            try:
                value = int(raw)
            except ValueError:
                continue
            if len(raw) > 10:
                value = value / 1000.0
            try:
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                continue
        else:
            for fmt in (kind, kind + ",%f", kind + ".%f"):
                try:
                    parsed = datetime.strptime(raw, fmt)
                except ValueError:
                    continue
                if kind.startswith("%b"):
                    # Syslog stamps carry no year: assume the most recent
                    # plausible one instead of strptime's default 1900.
                    now = datetime.now(timezone.utc)
                    try:
                        parsed = parsed.replace(year=now.year)
                        if parsed.replace(tzinfo=timezone.utc) > now:
                            parsed = parsed.replace(year=now.year - 1)
                    except ValueError:
                        pass  # e.g. Feb 29 on a non-leap year; keep parsed year
                return parsed.replace(tzinfo=timezone.utc)
    return None


# --- plain text --------------------------------------------------------------

_LEVEL_RE = re.compile(
    r"\b(?P<level>TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|ERR(?:OR)?|FATAL|CRITICAL|CRIT|ALERT|EMERG(?:ENCY)?)\b",
    re.IGNORECASE,
)
_KV_RE = re.compile(r"\b(?P<key>service|app|application|source|logger|host|component|module|request_id|trace_id)\s*[:=]\s*(?P<val>[^\s,;]+)")


def parse_plain_line(line: str) -> ParsedEntry:
    """Parse one plain-text log line; never raises on bad input."""
    raw = line if len(line) <= MAX_LINE_LENGTH else line[:MAX_LINE_LENGTH] + "…"
    text = line.strip()
    level_match = _LEVEL_RE.search(text)
    severity = normalize_severity(level_match.group("level")) if level_match else "UNKNOWN"
    timestamp = parse_timestamp(text)
    service: str | None = None
    source: str | None = None
    for kv in _KV_RE.finditer(text):
        key = kv.group("key").lower()
        val = kv.group("val").strip().strip("'\"")
        if key in ("service", "app", "application") and service is None:
            service = val
        elif key in ("source", "logger", "host", "component", "module") and source is None:
            source = val
    message = text
    return ParsedEntry(
        timestamp=timestamp,
        severity=severity,
        service=service,
        source=source,
        message=message,
        raw=raw,
        attributes={},
    )


# --- JSON / JSONL ------------------------------------------------------------

_TS_KEYS = ("timestamp", "@timestamp", "time", "ts", "datetime", "date")
_LEVEL_KEYS = ("level", "severity", "log_level", "loglevel", "priority")
_SERVICE_KEYS = ("service", "app", "application", "app_name")
_SOURCE_KEYS = ("source", "logger", "logger_name", "host", "hostname", "component", "module", "file")
_MESSAGE_KEYS = ("message", "msg", "log", "text", "error", "event")


def _first_present(obj: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in obj and obj[key] is not None:
            return obj[key]
    lowered = {str(k).lower(): v for k, v in obj.items()}
    for key in keys:
        if key in lowered and lowered[key] is not None:
            return lowered[key]
    return None


def _coerce_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 1e14:  # microseconds
            number /= 1e6
        elif number > 1e11:  # milliseconds
            number /= 1e3
        try:
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        parsed = _parse_iso(value)
        if parsed is not None:
            return parsed
        return parse_timestamp(value)
    return None


def parse_json_object(obj: dict[str, Any], raw: str) -> ParsedEntry:
    level = _first_present(obj, _LEVEL_KEYS)
    message_value = _first_present(obj, _MESSAGE_KEYS)
    if isinstance(message_value, (dict, list)):
        message = json.dumps(message_value)[:4000]
    else:
        message = str(message_value) if message_value is not None else raw.strip()
    known = set(_TS_KEYS) | set(_LEVEL_KEYS) | set(_SERVICE_KEYS) | set(_SOURCE_KEYS) | set(_MESSAGE_KEYS)
    attributes = {k: v for k, v in obj.items() if k not in known}
    service = _first_present(obj, _SERVICE_KEYS)
    source = _first_present(obj, _SOURCE_KEYS)
    return ParsedEntry(
        timestamp=_coerce_timestamp(_first_present(obj, _TS_KEYS)),
        severity=normalize_severity(level),
        service=str(service) if service is not None else None,
        source=str(source) if source is not None else None,
        message=message or raw.strip(),
        raw=raw if len(raw) <= MAX_LINE_LENGTH else raw[:MAX_LINE_LENGTH] + "…",
        attributes=attributes,
    )


def parse_json_line(line: str, lineno: int) -> ParsedEntry | None:
    """Parse one JSONL line; blank lines yield None, bad JSON raises ValueError."""
    if not line.strip():
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"line {lineno}: invalid JSON: {exc.msg}") from exc
    if isinstance(obj, dict):
        return parse_json_object(obj, line.rstrip("\n"))
    # A bare JSON scalar/array on a line is kept as a message-carrying entry.
    return ParsedEntry(
        timestamp=None,
        severity="UNKNOWN",
        service=None,
        source=None,
        message=line.strip(),
        raw=line.rstrip("\n"),
        attributes={},
    )


def iter_json_array(stream: IO[str]) -> Iterator[tuple[int, ParsedEntry | None]]:
    """Yield (lineno, entry) pairs from a single JSON array document."""
    try:
        data = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON document: {exc.msg}") from exc
    if isinstance(data, dict):
        yield 1, parse_json_object(data, json.dumps(data))
    elif isinstance(data, list):
        for lineno, item in enumerate(data, start=1):
            if isinstance(item, dict):
                yield lineno, parse_json_object(item, json.dumps(item))
            elif item is None or (isinstance(item, str) and not item.strip()):
                yield lineno, None
            else:
                text = item if isinstance(item, str) else json.dumps(item)
                yield lineno, ParsedEntry(
                    timestamp=None, severity="UNKNOWN", service=None,
                    source=None, message=text, raw=text, attributes={},
                )
    else:
        raise ValueError("JSON document must be an object or an array of objects")
