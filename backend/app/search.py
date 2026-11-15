"""Full-text search query language and filtering helpers.

Supported ``q`` syntax (combinable, whitespace separated):

- ``word`` — must contain the word (stemmed on PostgreSQL).
- ``"exact phrase"`` — must contain the phrase.
- ``-word`` / ``-"phrase"`` — must not contain.
- ``service:api`` / ``source:web-1`` — field filters (substring match).
- ``severity:error`` / ``level:warn`` — exact severity match (normalized).
- ``trace:<id>`` / ``request:<id>`` — exact trace/request id match.
  (``trace_id:`` and ``request_id:`` spellings also work.)

On PostgreSQL the free-text part runs against an expression GIN index
(``ix_log_entries_search``, built by migration 0004) via
``websearch_to_tsquery`` with ``ts_rank`` ordering for ``sort=relevance``.
On SQLite (tests) the same query is emulated with ``ILIKE`` predicates so
behavior stays portable. Snippets are highlighted in Python on both.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from sqlalchemy import not_, or_
from sqlalchemy.orm import Query

from app.models import LogEntry
from app.severity import normalize_severity

_TOKEN = re.compile(r'(?P<neg>-)?(?:(?P<field>[A-Za-z_]+):)?(?P<value>"[^"]+"|\S+)')

_FIELD_ALIASES = {
    "service": "service",
    "source": "source",
    "severity": "severity",
    "level": "severity",
    "trace": "trace_id",
    "trace_id": "trace_id",
    "traceid": "trace_id",
    "request": "request_id",
    "request_id": "request_id",
    "requestid": "request_id",
}


@dataclass
class ParsedQuery:
    must_terms: list[str] = field(default_factory=list)
    must_phrases: list[str] = field(default_factory=list)
    exclude_terms: list[str] = field(default_factory=list)
    exclude_phrases: list[str] = field(default_factory=list)
    field_filters: dict[str, str] = field(default_factory=dict)
    exclude_field_filters: dict[str, list[str]] = field(default_factory=dict)

    @property
    def has_fts(self) -> bool:
        return bool(self.must_terms or self.must_phrases or self.exclude_terms or self.exclude_phrases)

    @property
    def websearch_text(self) -> str:
        """Free-text part rebuilt in websearch_to_tsquery syntax."""
        parts = list(self.must_terms)
        parts += [f'"{p}"' for p in self.must_phrases]
        parts += [f"-{t}" for t in self.exclude_terms]
        parts += [f'-"{p}"' for p in self.exclude_phrases]
        return " ".join(parts)[:500]


def _strip_quotes(value: str) -> tuple[str, bool]:
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1], True
    return value, False


def parse_search_query(raw: str | None) -> ParsedQuery:
    """Parse the ``q`` search string into structured clauses. Never raises."""
    parsed = ParsedQuery()
    if not raw or not raw.strip():
        return parsed
    for match in _TOKEN.finditer(raw.strip()[:2000]):
        negated = bool(match.group("neg"))
        field_name = (match.group("field") or "").lower()
        value, quoted = _strip_quotes(match.group("value"))
        value = value.strip()
        if not value:
            continue
        canonical = _FIELD_ALIASES.get(field_name) if field_name else None
        if canonical is not None:
            if negated:
                parsed.exclude_field_filters.setdefault(canonical, []).append(value)
            else:
                parsed.field_filters[canonical] = value
        elif quoted:
            (parsed.exclude_phrases if negated else parsed.must_phrases).append(value)
        else:
            (parsed.exclude_terms if negated else parsed.must_terms).append(value)
    return parsed


def _text_columns_contain(value: str):
    like = f"%{value}%"
    return or_(
        LogEntry.message.ilike(like),
        LogEntry.source.ilike(like),
        LogEntry.service.ilike(like),
    )


def apply_field_filters(query: Query, parsed: ParsedQuery) -> Query:
    for name, value in parsed.field_filters.items():
        if name == "service":
            query = query.filter(LogEntry.service.ilike(f"%{value}%"))
        elif name == "source":
            query = query.filter(LogEntry.source.ilike(f"%{value}%"))
        elif name == "severity":
            query = query.filter(LogEntry.severity == normalize_severity(value))
        elif name == "trace_id":
            query = query.filter(LogEntry.trace_id == value)
        elif name == "request_id":
            query = query.filter(LogEntry.request_id == value)
    for name, values in parsed.exclude_field_filters.items():
        for value in values:
            if name == "service":
                query = query.filter(not_(LogEntry.service.ilike(f"%{value}%")))
            elif name == "source":
                query = query.filter(not_(LogEntry.source.ilike(f"%{value}%")))
            elif name == "severity":
                query = query.filter(LogEntry.severity != normalize_severity(value))
            elif name == "trace_id":
                query = query.filter(or_(LogEntry.trace_id.is_(None), LogEntry.trace_id != value))
            elif name == "request_id":
                query = query.filter(or_(LogEntry.request_id.is_(None), LogEntry.request_id != value))
    return query


def apply_ilike_search(query: Query, parsed: ParsedQuery) -> Query:
    """Portable free-text emulation for SQLite (and PG fallback)."""
    for term in parsed.must_terms:
        query = query.filter(_text_columns_contain(term))
    for phrase in parsed.must_phrases:
        query = query.filter(_text_columns_contain(phrase))
    for term in parsed.exclude_terms:
        query = query.filter(not_(_text_columns_contain(term)))
    for phrase in parsed.exclude_phrases:
        query = query.filter(not_(_text_columns_contain(phrase)))
    return query


def highlight_snippet(message: str, parsed: ParsedQuery, max_len: int = 280) -> str:
    """Return an HTML-escaped window of ``message`` with ``<mark>`` hits.

    Only ``<mark>`` tags are ever emitted; everything else is escaped.
    """
    text = message or ""
    needles = sorted(set(parsed.must_phrases + parsed.must_terms), key=len, reverse=True)
    if not needles:
        clipped = text[:max_len]
        return html.escape(clipped) + ("…" if len(text) > max_len else "")
    lowered = text.lower()
    first = len(text)
    for needle in needles:
        pos = lowered.find(needle.lower())
        if pos != -1 and pos < first:
            first = pos
    if first == len(text):
        clipped = text[:max_len]
        return html.escape(clipped) + ("…" if len(text) > max_len else "")
    start = max(0, first - max_len // 3)
    end = min(len(text), start + max_len)
    start = max(0, end - max_len)
    window = text[start:end]
    escaped = html.escape(window)
    for needle in needles:
        escaped = re.sub(
            re.escape(html.escape(needle)), r"<mark>\g<0></mark>", escaped, flags=re.IGNORECASE
        )
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{escaped}{suffix}"
