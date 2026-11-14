"""Parser tests: plain text, JSONL and structured JSON."""

import io

import pytest

from app.parsers import (
    iter_json_array,
    parse_json_line,
    parse_json_object,
    parse_plain_line,
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
