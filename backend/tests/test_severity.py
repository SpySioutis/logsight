"""Severity normalization tests."""

from app.severity import SEVERITIES, is_error_like, is_warning_like, normalize_severity


def test_canonical_levels_preserved():
    for level in ("TRACE", "DEBUG", "INFO", "WARN", "WARNING", "ERROR", "FATAL", "CRITICAL", "UNKNOWN"):
        assert normalize_severity(level) == level
        assert normalize_severity(level.lower()) == level


def test_aliases_normalize():
    assert normalize_severity("warn") == "WARN"
    assert normalize_severity("warning") == "WARNING"
    assert normalize_severity("err") == "ERROR"
    assert normalize_severity("crit") == "CRITICAL"
    assert normalize_severity("information") == "INFO"
    assert normalize_severity("emerg") == "CRITICAL"


def test_numeric_levels():
    assert normalize_severity(10) == "DEBUG"
    assert normalize_severity(20) == "INFO"
    assert normalize_severity(30) == "WARNING"
    assert normalize_severity(40) == "ERROR"
    assert normalize_severity(50) == "CRITICAL"
    assert normalize_severity("30") == "WARNING"


def test_unknown_never_discarded():
    for bad in (None, "", "   ", "VERBOSE", "???", True, object()):
        assert normalize_severity(bad) == "UNKNOWN"
    assert "UNKNOWN" in SEVERITIES


def test_predicates():
    assert is_error_like("ERROR") and is_error_like("FATAL") and is_error_like("CRITICAL")
    assert not is_error_like("WARN") and not is_error_like("INFO")
    assert is_warning_like("WARN") and is_warning_like("WARNING")
    assert not is_warning_like("ERROR")
