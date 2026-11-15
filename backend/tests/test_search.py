"""Search query parser and snippet tests."""

from app.search import highlight_snippet, parse_search_query


def test_parse_terms_and_phrases():
    parsed = parse_search_query('connection "slow query" timeout')
    assert parsed.must_terms == ["connection", "timeout"]
    assert parsed.must_phrases == ["slow query"]
    assert parsed.has_fts is True


def test_parse_exclusions():
    parsed = parse_search_query('error -timeout -"known flake"')
    assert parsed.must_terms == ["error"]
    assert parsed.exclude_terms == ["timeout"]
    assert parsed.exclude_phrases == ["known flake"]


def test_parse_field_filters():
    parsed = parse_search_query("service:api source:web-1 severity:error trace:t-9 request:r-1 boom")
    assert parsed.field_filters == {
        "service": "api",
        "source": "web-1",
        "severity": "error",
        "trace_id": "t-9",
        "request_id": "r-1",
    }
    assert parsed.must_terms == ["boom"]


def test_parse_field_aliases_and_negation():
    parsed = parse_search_query("level:warn trace_id:abc -service:worker")
    assert parsed.field_filters == {"severity": "warn", "trace_id": "abc"}
    assert parsed.exclude_field_filters == {"service": ["worker"]}


def test_parse_empty_never_raises():
    assert parse_search_query(None).has_fts is False
    assert parse_search_query("   ").has_fts is False
    assert parse_search_query("service:").field_filters == {}


def test_websearch_text_roundtrip():
    parsed = parse_search_query('service:api "slow query" error -timeout')
    assert parsed.websearch_text == 'error "slow query" -timeout'


def test_snippet_marks_hits():
    parsed = parse_search_query("slow query")
    snippet = highlight_snippet("a slow query took 1200ms", parsed)
    assert "<mark>slow</mark>" in snippet
    assert "<mark>query</mark>" in snippet


def test_snippet_escapes_html():
    parsed = parse_search_query("boom")
    snippet = highlight_snippet("<b>boom</b> happened", parsed)
    assert "<b>" not in snippet
    assert "&lt;b&gt;<mark>boom</mark>&lt;/b&gt;" in snippet


def test_snippet_without_terms_truncates():
    parsed = parse_search_query("service:api")
    snippet = highlight_snippet("x" * 500, parsed, max_len=280)
    assert "<mark>" not in snippet
    assert snippet.endswith("…")
