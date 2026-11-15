"""Streaming import service: saves uploads to disk, parses, batch-inserts.

Strategy:
- The upload is streamed to a temp file while a SHA-256 hash is computed.
- Files are parsed line-by-line (plain text, JSONL, CSV) so memory stays flat.
- Rows are inserted in batches of 1,000 inside one transaction per batch.
- A file whose hash was imported before is recorded as a `duplicate`
  import that references the original; no rows are re-inserted.
- Supported extensions: .log, .txt (plain, incl. RFC 5424 syslog and
  multiline stacktraces), .jsonl, .ndjson (JSON lines), .json (structured
  JSON object or array), .csv (header row required). Any of these may be
  gzip-compressed (.gz); .zip archives may bundle several supported files.
- Decompressed output is capped by the same upload size limit to stop
  zip-bomb style abuse.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from typing import IO, Iterable, Iterator

from fastapi import HTTPException, UploadFile
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app import parsers
from app.config import settings
from app.models import Import, LogEntry

CHUNK_ROWS = 1000

_FORMAT_BY_EXT: dict[str, str] = {
    ".log": "plaintext",
    ".txt": "plaintext",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".json": "json",
    ".csv": "csv",
}

_EXTENSIONS_HELP = ".log, .txt, .jsonl, .ndjson, .json, .csv (.gz or .zip accepted)"


def detect_format(filename: str) -> str | None:
    lowered = filename.lower()
    if lowered.endswith(".zip"):
        return "zip"
    if lowered.endswith(".gz"):
        lowered = lowered[: -len(".gz")]
    for ext, fmt in _FORMAT_BY_EXT.items():
        if lowered.endswith(ext):
            return fmt
    return None


def _member_format(name: str) -> str | None:
    lowered = name.lower()
    if lowered.endswith(".gz"):
        lowered = lowered[: -len(".gz")]
    for ext, fmt in _FORMAT_BY_EXT.items():
        if lowered.endswith(ext):
            return fmt
    return None


def _flush(db: Session, import_id: str, batch: list[dict]) -> int:
    if not batch:
        return 0
    db.execute(insert(LogEntry), [{**row, "import_id": import_id} for row in batch])
    db.commit()
    return len(batch)


def _row(entry: parsers.ParsedEntry) -> dict:
    return {
        "timestamp": entry.timestamp,
        "severity": entry.severity,
        "service": entry.service,
        "source": entry.source,
        "message": entry.message,
        "raw": entry.raw,
        "attributes": entry.attributes or {},
        "fingerprint": entry.fingerprint,
        "trace_id": entry.trace_id,
        "request_id": entry.request_id,
    }


class _Counter:
    def __init__(self, cap: int) -> None:
        self.total = 0
        self.cap = cap

    def add(self, amount: int) -> None:
        self.total += amount
        if self.total > self.cap:
            raise HTTPException(
                status_code=413,
                detail=f"Decompressed content exceeds the {settings.max_upload_mb} MB upload limit.",
            )


def _capped_lines(lines: Iterable[str], counter: _Counter) -> Iterator[str]:
    for line in lines:
        counter.add(len(line))
        yield line


def _gunzip_to_temp(src_path: str, cap: int) -> str:
    """Decompress a .gz file to a temp path, enforcing the size cap."""
    out = tempfile.NamedTemporaryFile(delete=False, suffix="-logsight-decompressed")
    total = 0
    try:
        with open(src_path, "rb") as fb:
            try:
                gz = gzip.GzipFile(fileobj=fb)
                while True:
                    chunk = gz.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > cap:
                        raise HTTPException(
                            status_code=413,
                            detail=(
                                "Decompressed content exceeds the "
                                f"{settings.max_upload_mb} MB upload limit."
                            ),
                        )
                    out.write(chunk)
            except HTTPException:
                raise
            except OSError as exc:
                raise ValueError(f"invalid gzip file: {exc}") from exc
    finally:
        out.close()
    return out.name


class _Parser:
    """Accumulates parsed entries and flushes them in batches."""

    def __init__(self, db: Session, import_id: str) -> None:
        self._db = db
        self._import_id = import_id
        self.batch: list[dict] = []
        self.total_lines = 0
        self.parsed = 0
        self.errors = 0

    def add(self, entry: parsers.ParsedEntry) -> None:
        self.batch.append(_row(entry))
        self.parsed += 1
        if len(self.batch) >= CHUNK_ROWS:
            _flush(self._db, self._import_id, self.batch)
            self.batch = []

    def flush(self) -> None:
        _flush(self._db, self._import_id, self.batch)
        self.batch = []

    def parse_plaintext(self, lines: Iterable[str]) -> None:
        pending: parsers.ParsedEntry | None = None

        def _emit() -> None:
            nonlocal pending
            if pending is not None:
                self.add(pending)
                pending = None

        for line in lines:
            if not line.strip():
                continue
            self.total_lines += 1
            if parsers.is_continuation_line(line) and pending is not None:
                parsers.append_continuation(pending, line.rstrip("\n"))
                continue
            _emit()
            pending = parsers.parse_plain_line(line.rstrip("\n"))
        _emit()

    def parse_jsonl(self, lines: Iterable[str]) -> None:
        lineno = 0
        for line in lines:
            lineno += 1
            if not line.strip():
                continue
            self.total_lines += 1
            try:
                entry = parsers.parse_json_line(line, lineno)
            except ValueError:
                self.errors += 1
                continue
            if entry is None:
                continue
            self.add(entry)

    def parse_json_doc(self, stream: IO[str], member: str = "") -> None:
        try:
            items = list(parsers.iter_json_array(stream))
        except ValueError as exc:
            if member:
                raise ValueError(f"{member}: {exc}") from exc
            raise
        for _lineno, entry in items:
            if entry is None:
                continue
            self.total_lines += 1
            self.add(entry)

    def parse_csv(self, lines: Iterable[str], member: str = "") -> None:
        reader = csv.DictReader(lines)
        if reader.fieldnames is None:
            return
        for row in reader:
            if row is None:
                continue
            values = {k: v for k, v in row.items() if k}
            if not any(v not in (None, "") for v in values.values()):
                continue
            self.total_lines += 1
            try:
                raw = json.dumps(values)
                entry = parsers.parse_csv_row(values, raw)
            except ValueError:
                self.errors += 1
                continue
            self.add(entry)


def _parse_file_object(
    parser: _Parser,
    fh: Iterable[str],
    fmt: str,
    counter: _Counter,
    member: str = "",
) -> None:
    if fmt == "plaintext":
        parser.parse_plaintext(_capped_lines(fh, counter))
    elif fmt == "jsonl":
        parser.parse_jsonl(_capped_lines(fh, counter))
    elif fmt == "csv":
        parser.parse_csv(_capped_lines(fh, counter), member)
    elif fmt == "json":
        # Single-document JSON needs random access for json.load: buffer it
        # (bounded by the same decompressed-size cap).
        text = "".join(_capped_lines(fh, counter))
        parser.parse_json_doc(io.StringIO(text), member)
    else:  # pragma: no cover - guarded by detect_format
        raise ValueError(f"unsupported format: {fmt}")


def _parse_zip(parser: _Parser, tmp_path: str, counter: _Counter) -> None:
    try:
        archive = zipfile.ZipFile(tmp_path)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"invalid zip archive: {exc}") from exc
    with archive:
        members = [
            info
            for info in archive.infolist()
            if not info.is_dir()
            and not info.filename.split("/")[-1].startswith(".")
            and _member_format(info.filename) is not None
        ]
        if not members:
            raise ValueError(
                "zip archive contains no supported log files "
                "(.log, .txt, .jsonl, .ndjson, .json, .csv)."
            )
        for info in members:
            fmt = _member_format(info.filename)
            assert fmt is not None
            try:
                raw = archive.open(info, "r")
            except (zipfile.BadZipFile, OSError) as exc:
                raise ValueError(f"{info.filename}: unreadable member: {exc}") from exc
            with raw:
                stream: IO[bytes] = raw
                if info.filename.lower().endswith(".gz"):
                    try:
                        stream = gzip.GzipFile(fileobj=raw)  # type: ignore[assignment]
                    except OSError as exc:
                        raise ValueError(f"{info.filename}: invalid gzip member: {exc}") from exc
                text_wrapper = io.TextIOWrapper(stream, encoding="utf-8", errors="replace")
                _parse_file_object(parser, text_wrapper, fmt, counter, info.filename)


def import_upload(db: Session, upload: UploadFile) -> tuple[Import, bool]:
    filename = upload.filename or "upload.log"
    fmt = detect_format(filename)
    if fmt is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Use {_EXTENSIONS_HELP}.",
        )
    is_gz = filename.lower().endswith(".gz") or (
        fmt != "zip" and filename.lower().endswith(".gz")
    )

    # Stream to disk with size cap + running hash (constant memory).
    digest = hashlib.sha256()
    size = 0
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix="-logsight-upload")
    try:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > settings.max_upload_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds the {settings.max_upload_mb} MB upload limit.",
                )
            digest.update(chunk)
            tmp.write(chunk)
    finally:
        tmp.close()
    tmp_path = tmp.name
    extra_temps: list[str] = []

    try:
        file_hash = digest.hexdigest()
        existing = db.query(Import).filter(Import.file_hash == file_hash).first()
        record = Import(
            filename=filename,
            file_size=size,
            file_hash=file_hash,
            format=fmt,
            status="processing",
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        if existing is not None and existing.status == "completed":
            record.status = "duplicate"
            record.duplicate_of = existing.id
            record.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(record)
            return record, True

        parser = _Parser(db, record.id)
        counter = _Counter(settings.max_upload_bytes)
        try:
            if fmt == "zip":
                _parse_zip(parser, tmp_path, counter)
            else:
                parse_path = tmp_path
                inner_fmt = fmt
                if is_gz:
                    parse_path = _gunzip_to_temp(tmp_path, settings.max_upload_bytes)
                    extra_temps.append(parse_path)
                with open(parse_path, "r", encoding="utf-8", errors="replace") as fh:
                    _parse_file_object(parser, fh, inner_fmt, counter)
            parser.flush()
        except ValueError as exc:
            db.rollback()
            record.status = "failed"
            record.error_message = str(exc)
            record.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(record)
            return record, False

        record.status = "completed"
        record.total_lines = parser.total_lines
        record.parsed_count = parser.parsed
        record.error_count = parser.errors
        record.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(record)
        return record, False
    finally:
        for path in [tmp_path, *extra_temps]:
            try:
                os.unlink(path)
            except OSError:
                pass
