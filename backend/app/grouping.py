"""Deterministic error grouping via message fingerprinting.

Fingerprints normalize volatile tokens (numbers, hex ids, UUIDs, IPs,
timestamps, quoted strings) so recurring errors group together without
any external AI service.
"""

from __future__ import annotations

import hashlib
import re

# Applied to lower-cased text, before the generic number rules: in ISO
# timestamps the hour is glued to the "t" ("t10:00"), so \b-anchored number
# masks never see it and errors split into one group per hour of day.
_ISO_TS = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[t ]\d{2}:\d{2}(?::\d{2})?(?:[.,]\d+)?(?:z|[+-]\d{2}(?::?\d{2})?)?)?"
)
_SYSLOG_TS = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\b"
)
# Access logs "[01/may/2024:12:00:00 +0200]" and slash dates "2024/05/01 12:00:00".
_CLF_TS = re.compile(r"\d{2}/[a-z]{3}/\d{4}:\d{2}:\d{2}:\d{2}(?: [+-]\d{4})?")
_SLASH_TS = re.compile(r"\d{4}/\d{2}/\d{2}[ t]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?")
_TIME = re.compile(r"\b\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b")
_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
# Hex rules need at least one a-f letter: pure-digit tokens must become <n>
# regardless of length, otherwise "line 120" and "line 10020" split groups.
_HEX = re.compile(r"\b0x[0-9a-fA-F]+\b|\b(?=[0-9]*[a-fA-F])[0-9a-fA-F]{7,}\b")
_IP = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b")
_HEXLIKE = re.compile(r"\b(?=\d[0-9]*[a-fA-F])\d[0-9a-fA-F]{3,}\b")
_NUMBER = re.compile(r"\b\d+(?:\.\d+)+\b|\b\d+\b|(?<!\w)\d+(?=[a-zA-Z%])")
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
_WS = re.compile(r"\s+")


def normalize_message(message: str) -> str:
    """Reduce a log message to its stable shape for grouping."""
    text = message.strip().lower()
    text = _ISO_TS.sub("<ts>", text)
    text = _SYSLOG_TS.sub("<ts>", text)
    text = _CLF_TS.sub("<ts>", text)
    text = _SLASH_TS.sub("<ts>", text)
    text = _TIME.sub("<ts>", text)
    text = _UUID.sub("<uuid>", text)
    text = _IP.sub("<ip>", text)
    text = _HEX.sub("<hex>", text)
    text = _HEXLIKE.sub("<hex>", text)
    text = _NUMBER.sub("<n>", text)
    # Keep short quoted tokens (they often carry meaning), mask long ones.
    def _mask_quoted(match: re.Match[str]) -> str:
        return "<str>" if len(match.group(0)) > 24 else match.group(0)

    text = _QUOTED.sub(_mask_quoted, text)
    text = _WS.sub(" ", text).strip()
    return text[:500]


def fingerprint(message: str) -> str:
    """Return the stable hex fingerprint for a log message."""
    normalized = normalize_message(message)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]
