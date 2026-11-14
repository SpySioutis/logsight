"""Streaming import service: saves uploads to disk, parses, batch-inserts.

Strategy:
- The upload is streamed to a temp file while a SHA-256 hash is computed.
- Files are parsed line-by-line (plain text, JSONL) so memory stays flat.
- Rows are inserted in batches of 1,000 inside one transaction per batch.
- A file whose hash was imported before is recorded as a `duplicate`
  import that references the original; no rows are re-inserted.
- Supported extensions: .log, .txt (plain), .jsonl, .ndjson (JSON lines),
  .json (structured JSON object or array of objects).
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime, timezone

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
}


def detect_format(filename: str) -> str | None:
    lowered = filename.lower()
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
    }


def import_upload(db: Session, upload: UploadFile) -> tuple[Import, bool]:
    filename = upload.filename or "upload.log"
    fmt = detect_format(filename)
    if fmt is None:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Use .log, .txt, .jsonl, .ndjson or .json.",
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

        total_lines = 0
        parsed = 0
        errors = 0
        batch: list[dict] = []
        try:
            if fmt in ("plaintext", "jsonl"):
                with open(tmp_path, "r", encoding="utf-8", errors="replace") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        if not line.strip():
                            continue
                        total_lines += 1
                        try:
                            if fmt == "plaintext":
                                entry = parsers.parse_plain_line(line.rstrip("\n"))
                            else:
                                entry = parsers.parse_json_line(line, lineno)
                                if entry is None:
                                    continue
                        except ValueError:
                            errors += 1
                            continue
                        batch.append(_row(entry))
                        parsed += 1
                        if len(batch) >= CHUNK_ROWS:
                            _flush(db, record.id, batch)
                            batch = []
            else:  # structured JSON
                with open(tmp_path, "r", encoding="utf-8", errors="replace") as fh:
                    for lineno, entry in parsers.iter_json_array(fh):
                        if entry is None:
                            continue
                        total_lines += 1
                        batch.append(_row(entry))
                        parsed += 1
                        if len(batch) >= CHUNK_ROWS:
                            _flush(db, record.id, batch)
                            batch = []
            _flush(db, record.id, batch)
        except ValueError as exc:
            db.rollback()
            record.status = "failed"
            record.error_message = str(exc)
            record.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(record)
            return record, False

        record.status = "completed"
        record.total_lines = total_lines
        record.parsed_count = parsed
        record.error_count = errors
        record.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(record)
        return record, False
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
