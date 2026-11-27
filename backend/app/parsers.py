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
from email.utils import parsedate_to_datetime
from typing import IO, Any, Iterator

from app.grouping import fingerprint
from app.severity import is_error_like, normalize_severity

MAX_LINE_LENGTH = 64 * 1024  # truncate pathological single lines
MAX_JOINED_LENGTH = 64 * 1024  # cap for multiline stacktrace-joined entries


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
    trace_id: str | None = None
    request_id: str | None = None

    def __post_init__(self) -> None:
        # Fingerprints are only consumed for error-like severities (error
        # groups, top errors), so skip the normalize + SHA-256 cost elsewhere.
        if not self.fingerprint and self.message and is_error_like(self.severity):
            self.fingerprint = fingerprint(self.message)


# --- timestamp handling -----------------------------------------------------

_TS_PATTERNS: list[tuple[re.Pattern[str], str | None]] = [
    # ISO-8601 with optional timezone: 2024-05-01T12:34:56.789Z / +02:00
    # (offset as +02:00, +0200 or +02; previously the offset was dropped).
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}(?::?\d{2})?\b)?"), None),
    # 2024-05-01 12:34:56,789
    (re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:[.,]\d+)?"), "%Y-%m-%d %H:%M:%S"),
    # Common/combined log format (nginx/Apache access): [01/May/2024:12:34:56 +0200]
    (re.compile(r"\d{2}/[A-Z][a-z]{2}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4}"), "%d/%b/%Y:%H:%M:%S %z"),
    # nginx error log / Go log package: 2024/05/01 12:34:56
    (re.compile(r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}(?:[.,]\d+)?"), "%Y/%m/%d %H:%M:%S"),
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


def _most_recent_year(parsed: datetime) -> datetime:
    """Syslog stamps carry no year: pick the latest one not in the future."""
    now = datetime.now(timezone.utc)
    for year in range(now.year, now.year - 8, -1):
        try:
            candidate = parsed.replace(year=year)
        except ValueError:
            continue  # Feb 29 in a non-leap year
        if candidate.replace(tzinfo=timezone.utc) <= now:
            return candidate
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
            yearless = kind.startswith("%b")
            for fmt in (kind, kind + ",%f", kind + ".%f"):
                try:
                    if yearless:
                        # Parse with an explicit leap year so "Feb 29" is
                        # valid (strptime's default 1900 is not a leap year).
                        parsed = datetime.strptime(f"2000 {raw}", f"%Y {fmt}")
                    else:
                        parsed = datetime.strptime(raw, fmt)
                except ValueError:
                    continue
                if yearless:
                    parsed = _most_recent_year(parsed)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


# --- plain text --------------------------------------------------------------

_LEVEL_RE = re.compile(
    r"\b(?P<level>TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|ERR(?:OR)?|FATAL|CRITICAL|CRIT|ALERT|EMERG(?:ENCY)?)\b",
    re.IGNORECASE,
)
_KV_RE = re.compile(
    r"\b(?P<key>service|app|application|source|logger|host|component|module"
    r"|request[-_]?id|requestid|trace[-_]?id|traceid|correlation[-_]?id|correlationid"
    r"|span[-_]?id|spanid)\s*[:=]\s*(?P<val>[^\s,;]+)"
)


# Common/combined access-log request + status: "GET /path HTTP/1.1" 503
_ACCESS_RE = re.compile(
    r'"(?P<method>GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|CONNECT|TRACE) (?P<path>\S+) HTTP/[\d.]+" (?P<status>[1-5]\d{2})\b'
)


def parse_plain_line(line: str) -> ParsedEntry:
    """Parse one plain-text log line; never raises on bad input."""
    syslog_entry = parse_syslog_line(line)
    if syslog_entry is not None:
        return syslog_entry
    raw = line if len(line) <= MAX_LINE_LENGTH else line[:MAX_LINE_LENGTH] + "…"
    text = line.strip()
    access = _ACCESS_RE.search(text)
    # In access logs, only look for a level *before* the quoted request:
    # words in the path, referrer or user agent ("/api/error/report",
    # "/debug") are not severities.
    level_match = _LEVEL_RE.search(text, 0, access.start() if access else len(text))
    severity = normalize_severity(level_match.group("level")) if level_match else "UNKNOWN"
    attributes: dict[str, Any] = {}
    if access is not None:
        status = int(access.group("status"))
        attributes = {
            "http_method": access.group("method"),
            "http_path": access.group("path")[:2048],
            "http_status": status,
        }
        if level_match is None:
            # Access logs carry no level: derive it from the status code.
            severity = "ERROR" if status >= 500 else "WARNING" if status >= 400 else "INFO"
    timestamp = parse_timestamp(text)
    service: str | None = None
    source: str | None = None
    trace_id: str | None = None
    request_id: str | None = None
    for kv in _KV_RE.finditer(text):
        key = re.sub(r"[-_]", "", kv.group("key").lower())
        val = kv.group("val").strip().strip("'\"")
        if key in ("service", "app", "application") and service is None:
            service = val
        elif key in ("source", "logger", "host", "component", "module") and source is None:
            source = val
        elif key in ("requestid", "spanid") and request_id is None:
            request_id = val
        elif key in ("traceid", "correlationid") and trace_id is None:
            trace_id = val
    message = text
    return ParsedEntry(
        timestamp=timestamp,
        severity=severity,
        service=service,
        source=source,
        message=message,
        raw=raw,
        attributes=attributes,
        trace_id=trace_id,
        request_id=request_id,
    )


# --- syslog (RFC 5424) ---------------------------------------------------------

_SYSLOG_RE = re.compile(
    r"^<(?P<pri>\d{1,3})>(?P<version>\d)\s+(?P<ts>\S+)\s+(?P<host>\S+)\s+"
    r"(?P<app>\S+)\s+(?P<proc>\S+)\s+(?P<msgid>\S+)\s+"
    r"(?P<sd>\[.*?\]|-)(?:\s+(?P<msg>.*))?$"
)
_SYSLOG_SD_PARAM = re.compile(r'(\w+)="([^"]*)"')
_SYSLOG_SEVERITY = {
    0: "CRITICAL",  # emerg
    1: "CRITICAL",  # alert
    2: "CRITICAL",  # crit
    3: "ERROR",  # err
    4: "WARNING",  # warning
    5: "INFO",  # notice
    6: "INFO",  # info
    7: "DEBUG",  # debug
}


def parse_syslog_line(line: str) -> ParsedEntry | None:
    """Parse one RFC 5424 syslog line; None when the line is not syslog."""
    text = line.strip()
    if not text.startswith("<"):
        return None
    match = _SYSLOG_RE.match(text)
    if not match:
        return None
    try:
        pri = int(match.group("pri"))
    except ValueError:
        return None
    if pri > 191:
        return None
    raw = line if len(line) <= MAX_LINE_LENGTH else line[:MAX_LINE_LENGTH] + "…"
    severity = _SYSLOG_SEVERITY.get(pri % 8, "UNKNOWN")
    ts_raw = match.group("ts")
    timestamp = None if ts_raw == "-" else (_parse_iso(ts_raw) or parse_timestamp(ts_raw))
    host = match.group("host")
    app = match.group("app")
    source = None if host == "-" else host
    service = None if app == "-" else app
    trace_id: str | None = None
    request_id: str | None = None
    attributes: dict[str, Any] = {}
    sd = match.group("sd")
    if sd != "-":
        for key, val in _SYSLOG_SD_PARAM.findall(sd):
            normalized = re.sub(r"[-_]", "", key.lower())
            if normalized in ("traceid", "correlationid") and trace_id is None:
                trace_id = val
            elif normalized in ("requestid", "spanid") and request_id is None:
                request_id = val
            else:
                attributes[key] = val
    msg = (match.group("msg") or "").strip()
    message = msg if msg else text
    return ParsedEntry(
        timestamp=timestamp,
        severity=severity,
        service=service,
        source=source,
        message=message,
        raw=raw,
        attributes=attributes,
        trace_id=trace_id,
        request_id=request_id,
    )


# --- multiline stacktraces -----------------------------------------------------

_CONTINUATION_PREFIXES = (
    "at ",
    "Caused by",
    "Suppressed:",
    "Traceback (most recent call last):",
    "Traceback",
    'File "',
    "File '",
    "...",
    "|",
    "+",
)


def is_continuation_line(line: str) -> bool:
    """True when a plaintext line continues the previous entry's stacktrace."""
    if not line.strip():
        return False
    stripped = line.strip()
    if stripped.startswith(_CONTINUATION_PREFIXES):
        return True
    if line[:1].isspace() and stripped.startswith(
        ("at ", "File ", "raise ", "Error", "Exception", "^")
    ):
        return True
    return False


def append_continuation(entry: ParsedEntry, line: str) -> None:
    """Append a continuation line to a pending entry, keeping caps + fingerprint."""
    text = line.rstrip("\n")
    entry.message = (entry.message + "\n" + text)[:MAX_JOINED_LENGTH]
    entry.raw = ((entry.raw or "") + "\n" + text)[:MAX_JOINED_LENGTH]
    if is_error_like(entry.severity):
        entry.fingerprint = fingerprint(entry.message)


# --- JSON / JSONL ------------------------------------------------------------

_TS_KEYS = ("timestamp", "@timestamp", "time", "ts", "datetime", "date")
_LEVEL_KEYS = ("level", "severity", "log_level", "loglevel", "priority")
_SERVICE_KEYS = ("service", "app", "application", "app_name")
_SOURCE_KEYS = ("source", "logger", "logger_name", "host", "hostname", "component", "module", "file")
_MESSAGE_KEYS = ("message", "msg", "log", "text", "error", "event")
_TRACE_KEYS = ("trace_id", "traceId", "traceID", "trace", "correlation_id", "correlationId")
_REQUEST_KEYS = ("request_id", "requestId", "requestID", "request", "span_id", "spanId")


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
        stripped = value.strip()
        if _NUMERIC.fullmatch(stripped):
            # Compact dates first ("20240501123456"), then epochs: CSV
            # delivers every value as text, so "1714557600" is an epoch.
            for fmt in _COMPACT_FORMATS.get(len(stripped), ()):
                try:
                    return datetime.strptime(stripped, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
            if len(stripped.split(".")[0]) not in (10, 13, 16):
                return None  # not seconds / ms / µs since the epoch
            return _coerce_timestamp(float(stripped))
        parsed = _parse_iso(stripped)
        if parsed is not None:
            return parsed
        parsed = parse_timestamp(stripped)
        if parsed is not None:
            return parsed
        try:  # RFC 2822 / HTTP dates: "Wed, 01 May 2024 12:00:00 GMT"
            parsed = parsedate_to_datetime(stripped)
        except (TypeError, ValueError, IndexError):
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


_NUMERIC = re.compile(r"\d{9,16}(?:\.\d+)?")
_COMPACT_FORMATS = {14: ("%Y%m%d%H%M%S",), 12: ("%Y%m%d%H%M",)}


def parse_json_object(obj: dict[str, Any], raw: str) -> ParsedEntry:
    level = _first_present(obj, _LEVEL_KEYS)
    message_value = _first_present(obj, _MESSAGE_KEYS)
    if isinstance(message_value, (dict, list)):
        message = json.dumps(message_value)[:4000]
    else:
        message = str(message_value) if message_value is not None else raw.strip()
    known = (
        set(_TS_KEYS)
        | set(_LEVEL_KEYS)
        | set(_SERVICE_KEYS)
        | set(_SOURCE_KEYS)
        | set(_MESSAGE_KEYS)
        | set(_TRACE_KEYS)
        | set(_REQUEST_KEYS)
    )
    lowered_known = {k.lower() for k in known}
    attributes = {k: v for k, v in obj.items() if k not in known and str(k).lower() not in lowered_known}
    service = _first_present(obj, _SERVICE_KEYS)
    source = _first_present(obj, _SOURCE_KEYS)
    trace_id = _first_present(obj, _TRACE_KEYS)
    request_id = _first_present(obj, _REQUEST_KEYS)
    return ParsedEntry(
        timestamp=_coerce_timestamp(_first_present(obj, _TS_KEYS)),
        severity=normalize_severity(level),
        service=str(service) if service is not None else None,
        source=str(source) if source is not None else None,
        message=message or raw.strip(),
        raw=raw if len(raw) <= MAX_LINE_LENGTH else raw[:MAX_LINE_LENGTH] + "…",
        attributes=attributes,
        trace_id=str(trace_id) if trace_id is not None else None,
        request_id=str(request_id) if request_id is not None else None,
    )


def parse_csv_row(row: dict[str, Any], raw: str) -> ParsedEntry:
    """Parse one CSV record via the JSON field mapping (headers are keys)."""
    cleaned = {k: v for k, v in row.items() if k and v not in (None, "")}
    return parse_json_object(cleaned, raw)


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
