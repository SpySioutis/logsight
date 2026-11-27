"""Parser tests: plain text, JSONL and structured JSON."""

import io

import pytest

from app.parsers import (
    append_continuation,
    is_continuation_line,
    iter_json_array,
    parse_csv_row,
    parse_json_line,
    parse_json_object,
    parse_plain_line,
    parse_syslog_line,
    parse_timestamp,
)


def test_plain_line_extracts_fields():
    entry = parse_plain_line("2024-05-01T12:34:56Z INFO [payments] order created id=42")
    assert entry.severity == "INFO"
    assert entry.timestamp is not None and entry.timestamp.year == 2024
    assert entry.message.startswith("2024-05-01")


def test_plain_line_unknown_level_kept():
    entry = parse_plain_line("2024-05-01 hello world without a level")
    assert entry.severity == "UNKNOWN"
    assert "hello world" in entry.message


def test_plain_line_service_source_kv():
    entry = parse_plain_line("ERROR service:api source:web-1 connection refused")
    assert entry.service == "api"
    assert entry.source == "web-1"
    assert entry.severity == "ERROR"


def test_plain_line_garbage_never_raises():
    entry = parse_plain_line("\x00\xff not really a log line {{{{")
    assert entry.severity == "UNKNOWN"
    assert entry.message


def test_timestamp_formats():
    assert parse_timestamp("2024-05-01 12:34:56,789 INFO x") is not None
    assert parse_timestamp("May  1 12:34:56 host app: msg") is not None
    assert parse_timestamp("no timestamp here") is None
    assert parse_timestamp("") is None


def test_syslog_timestamp_gets_plausible_year():
    from datetime import datetime, timezone

    parsed = parse_timestamp("May  1 12:34:56 host app: msg")
    assert parsed is not None
    current_year = datetime.now(timezone.utc).year
    assert parsed.year in (current_year, current_year - 1)
    assert parsed.year != 1900


def test_json_line_object():
    entry = parse_json_line(
        '{"timestamp": "2024-05-01T12:00:00Z", "level": "error", '
        '"service": "api", "msg": "boom 123", "user": "u1"}',
        1,
    )
    assert entry is not None
    assert entry.severity == "ERROR"
    assert entry.service == "api"
    assert entry.message == "boom 123"
    assert entry.attributes == {"user": "u1"}


def test_json_line_blank_is_none():
    assert parse_json_line("   \n", 3) is None


def test_json_line_invalid_raises_value_error():
    with pytest.raises(ValueError):
        parse_json_line("{not json", 9)


def test_json_object_numeric_level_and_epoch():
    entry = parse_json_object({"level": 40, "ts": 1714560000, "message": "bad"}, "{}")
    assert entry.severity == "ERROR"
    assert entry.timestamp is not None


def test_json_array_document():
    stream = io.StringIO('[{"level": "info", "message": "a"}, {"level": "error", "message": "b"}]')
    rows = list(iter_json_array(stream))
    assert len(rows) == 2
    assert rows[0][1] is not None and rows[0][1].severity == "INFO"
    assert rows[1][1] is not None and rows[1][1].severity == "ERROR"


def test_json_invalid_document_raises():
    with pytest.raises(ValueError):
        list(iter_json_array(io.StringIO("[1, 2")))


def test_plain_line_trace_request_kv():
    entry = parse_plain_line("INFO service:api trace_id:abc-1 request_id:req-7 all good")
    assert entry.trace_id == "abc-1"
    assert entry.request_id == "req-7"
    assert entry.service == "api"


def test_json_object_trace_request_excluded_from_attributes():
    entry = parse_json_object(
        {"level": "info", "message": "ok", "traceId": "t-1", "requestId": "r-2", "user": "u1"},
        "{}",
    )
    assert entry.trace_id == "t-1"
    assert entry.request_id == "r-2"
    assert entry.attributes == {"user": "u1"}


def test_syslog_rfc5424_parses_priority_and_ids():
    entry = parse_syslog_line(
        '<34>1 2024-05-01T10:00:00.000Z web-1 api - - [sd@1 trace_id="t-2"] login failed'
    )
    assert entry is not None
    assert entry.severity == "CRITICAL"  # 34 % 8 == 2 -> crit
    assert entry.service == "api"
    assert entry.source == "web-1"
    assert entry.trace_id == "t-2"
    assert entry.message == "login failed"


def test_syslog_invalid_returns_none():
    assert parse_syslog_line("not syslog at all") is None
    assert parse_syslog_line("<999>1 invalid") is None
    # Falls back to plain parsing without raising.
    entry = parse_plain_line("<999>1 INFO hello")
    assert entry.severity == "INFO"


def test_csv_row_maps_fields():
    entry = parse_csv_row(
        {
            "timestamp": "2024-05-01T10:00:00Z",
            "level": "40",
            "service": "api",
            "source": "web-1",
            "message": "bad",
            "trace_id": "t-3",
        },
        "raw",
    )
    assert entry.severity == "ERROR"
    assert entry.timestamp is not None
    assert entry.trace_id == "t-3"


def test_continuation_detection_and_join():
    assert is_continuation_line("\tat com.example.A.a(A.java:1)") is True
    assert is_continuation_line("Caused by: boom") is True
    assert is_continuation_line("Traceback (most recent call last):") is True
    assert is_continuation_line("2024-05-01 INFO fresh line") is False
    assert is_continuation_line("   ") is False

    entry = parse_plain_line("2024-05-01 ERROR boom")
    before = entry.fingerprint
    append_continuation(entry, "\tat com.example.A.a(A.java:1)")
    assert "at com.example" in entry.message
    assert entry.fingerprint != before


def test_iso_offsets_are_kept():
    from datetime import timedelta

    from app.parsers import parse_timestamp

    # The offset used to be dropped (stored as UTC, hours off) or, for
    # "+0200", the whole timestamp was lost.
    for text in ("2024-05-01T12:00:00+02:00 INFO x", "2024-05-01T12:00:00+0200 INFO x", "2024-05-01T12:00:00+02 x"):
        ts = parse_timestamp(text)
        assert ts is not None and ts.utcoffset() == timedelta(hours=2), text
    ts = parse_timestamp("2024-05-01T12:00:00.123-05:00 boom")
    assert ts is not None and ts.utcoffset() == timedelta(hours=-5)
    assert parse_timestamp("2024-05-01T12:00:00Z x").utcoffset() == timedelta(0)


def test_yearless_syslog_dates():
    from datetime import datetime, timezone

    from app.parsers import parse_timestamp

    leap = parse_timestamp("Feb 29 10:00:00 host app: x")
    assert leap is not None and leap.month == 2 and leap.day == 29
    assert leap <= datetime.now(timezone.utc)
    recent = parse_timestamp("Dec 31 23:59:59 host app: x")
    assert recent is not None and recent <= datetime.now(timezone.utc)
    assert recent.year >= datetime.now(timezone.utc).year - 1


def test_access_log_lines():
    from app.parsers import parse_plain_line

    e = parse_plain_line('127.0.0.1 - - [01/May/2024:12:00:00 +0200] "GET /api?x=1 HTTP/1.1" 503 512 "-" "curl/8"')
    assert e.timestamp is not None and e.timestamp.isoformat() == "2024-05-01T12:00:00+02:00"
    assert e.severity == "ERROR"
    assert e.attributes == {"http_method": "GET", "http_path": "/api?x=1", "http_status": 503}
    assert parse_plain_line('1.2.3.4 - - [01/May/2024:12:00:01 +0000] "POST /login HTTP/2.0" 401 0').severity == "WARNING"
    assert parse_plain_line('1.2.3.4 - - [01/May/2024:12:00:02 +0000] "GET / HTTP/1.1" 200 10').severity == "INFO"
    # An explicit level wins over the status code.
    assert parse_plain_line('INFO "GET /health HTTP/1.1" 503').severity == "INFO"


def test_slash_dated_and_epoch_string_timestamps():
    import json

    from app.parsers import parse_json_line, parse_plain_line

    assert parse_plain_line("2024/05/01 12:00:00 [error] 1#0: connect() failed").timestamp is not None
    for value, expected in (
        ("1714557600", "2024-05-01T10:00:00+00:00"),
        ("1714557600123", "2024-05-01T10:00:00.123000+00:00"),
        ("Wed, 01 May 2024 12:00:00 GMT", "2024-05-01T12:00:00+00:00"),
    ):
        entry = parse_json_line(json.dumps({"timestamp": value, "msg": "x"}), 1)
        assert entry is not None and entry.timestamp is not None
        assert entry.timestamp.isoformat() == expected, value


def test_access_log_level_only_outside_request():
    from app.parsers import parse_plain_line

    line = '1.2.3.4 - - [01/May/2024:12:00:00 +0000] "GET {path} HTTP/1.1" {status} 1 "https://x/WARN" "ua"'
    assert parse_plain_line(line.format(path="/api/error/report", status=200)).severity == "INFO"
    assert parse_plain_line(line.format(path="/debug", status=503)).severity == "ERROR"
    assert parse_plain_line(line.format(path="/?level=info", status=500)).severity == "ERROR"
    assert parse_plain_line(line.format(path="/", status=404)).severity == "WARNING"


def test_compact_numeric_dates_are_not_epochs():
    import json

    from app.parsers import parse_json_line

    def ts(value):
        return parse_json_line(json.dumps({"timestamp": value, "msg": "x"}), 1).timestamp

    assert ts("20240501123456").isoformat() == "2024-05-01T12:34:56+00:00"
    assert ts("202405011234").isoformat() == "2024-05-01T12:34:00+00:00"
    assert ts("1714557600").year == 2024
    assert ts("12345678901") is None  # 11 digits: neither a date nor an epoch unit
