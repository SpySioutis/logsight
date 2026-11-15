"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ImportOut(BaseModel):
    id: str
    filename: str
    file_size: int
    file_hash: str
    format: str
    status: str
    total_lines: int
    parsed_count: int
    error_count: int
    duplicate_of: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class ImportCreateOut(ImportOut):
    duplicate: bool = False


class LogEntryOut(BaseModel):
    id: str
    import_id: str
    timestamp: datetime | None
    severity: str
    service: str | None
    source: str | None
    message: str
    raw: str | None
    attributes: dict[str, Any] | None
    fingerprint: str | None
    trace_id: str | None = None
    request_id: str | None = None
    snippet: str | None = None

    model_config = {"from_attributes": True}


class LogPage(BaseModel):
    items: list[LogEntryOut]
    total: int
    page: int
    page_size: int
    pages: int


SortField = Literal["timestamp", "severity", "source", "service", "relevance"]
SortDir = Literal["asc", "desc"]


class DashboardSummary(BaseModel):
    total: int
    errors: int
    warnings: int
    info: int
    critical: int
    sources: int
    imports: int
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class TimelinePoint(BaseModel):
    bucket: str
    total: int
    errors: int


class SeverityBucket(BaseModel):
    severity: str
    count: int


class SourceBucket(BaseModel):
    source: str
    count: int


class TopError(BaseModel):
    fingerprint: str
    sample: str
    severity: str
    count: int
    first_seen: datetime | None
    last_seen: datetime | None
    status: str = "open"


class ErrorGroup(BaseModel):
    fingerprint: str
    sample: str
    severity: str
    count: int
    sources: list[str]
    first_seen: datetime | None
    last_seen: datetime | None
    status: str = "open"
    assignee: str | None = None
    note: str | None = None


ErrorGroupStatus = Literal["open", "acknowledged", "resolved", "muted"]


class ErrorGroupStateOut(BaseModel):
    fingerprint: str
    status: str
    assignee: str | None = None
    note: str | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ErrorGroupStateIn(BaseModel):
    status: ErrorGroupStatus
    assignee: str | None = Field(default=None, max_length=256)
    note: str | None = Field(default=None, max_length=2000)


class ErrorTrendPoint(BaseModel):
    bucket: str
    count: int


class TraceSummary(BaseModel):
    trace_id: str
    count: int
    services: list[str]
    severities: list[str]
    first_seen: datetime | None
    last_seen: datetime | None


class TraceDetail(BaseModel):
    trace_id: str
    count: int
    services: list[str]
    severities: list[str]
    first_seen: datetime | None
    last_seen: datetime | None
    duration_seconds: float | None = None
    entries: list[LogEntryOut]


class SavedFilterIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class SavedFilterOut(BaseModel):
    id: str
    name: str
    description: str | None
    params: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
