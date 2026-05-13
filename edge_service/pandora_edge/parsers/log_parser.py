"""Parse Blick oslog / fslog / pslog files and roll up warning/error counts."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .file_inventory_parser import FileEntry

# Common Blick log line shapes:
#   2026-05-12T10:00:00Z INFO message...
#   [2026-05-12 10:00:00] WARNING message
#   2026/05/12 10:00:00.123 ERROR ...
_TS_PATTERNS = [
    re.compile(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"),
    re.compile(r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?)"),
]
_LEVEL_RE = re.compile(r"\b(INFO|WARN|WARNING|ERROR|CRIT|CRITICAL|DEBUG|TRACE)\b", re.IGNORECASE)


@dataclass(frozen=True)
class LogEntry:
    timestamp_utc: datetime | None
    level: str
    message: str
    source_file: str


@dataclass
class LogRollup:
    total_warning_count: int = 0
    total_error_count: int = 0
    critical_errors: list[str] = field(default_factory=list)
    repeated_warnings: list[dict[str, int | str]] = field(default_factory=list)
    first_warning_utc: datetime | None = None
    last_warning_utc: datetime | None = None
    first_error_utc: datetime | None = None
    last_error_utc: datetime | None = None
    warning_summary: str = ""
    error_summary: str = ""
    last_log_line_utc: datetime | None = None


def _parse_timestamp(raw: str) -> datetime | None:
    raw = raw.replace("/", "-").replace("Z", "+00:00")
    if " " in raw and "T" not in raw:
        raw = raw.replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _extract(line: str, source_file: str) -> LogEntry | None:
    ts: datetime | None = None
    for pat in _TS_PATTERNS:
        m = pat.search(line)
        if m:
            ts = _parse_timestamp(m.group(1))
            break

    level_match = _LEVEL_RE.search(line)
    if not level_match:
        return None
    level = level_match.group(1).upper()
    if level == "WARN":
        level = "WARNING"
    if level == "CRIT":
        level = "CRITICAL"

    # Message: everything after the level token.
    msg = line[level_match.end():].strip(" :-\t\n")
    return LogEntry(timestamp_utc=ts, level=level, message=msg, source_file=source_file)


def _normalize_message(msg: str) -> str:
    """Strip volatile bits (numbers, hex addresses) so identical events group."""
    msg = re.sub(r"\b\d+(\.\d+)?\b", "<n>", msg)
    msg = re.sub(r"0x[0-9a-fA-F]+", "<hex>", msg)
    return msg[:160].strip()


def _iter_entries(files: list[FileEntry]) -> list[LogEntry]:
    entries: list[LogEntry] = []
    for f in files:
        try:
            with f.path.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    e = _extract(line, f.name)
                    if e is not None:
                        entries.append(e)
        except OSError:
            continue
    return entries


def parse_log_files(
    *,
    oslog: list[FileEntry],
    fslog: list[FileEntry],
    pslog: list[FileEntry],
    repeated_top_n: int = 10,
) -> LogRollup:
    entries = _iter_entries(oslog) + _iter_entries(fslog) + _iter_entries(pslog)

    rollup = LogRollup()
    warn_msgs: Counter[str] = Counter()

    for e in entries:
        if e.level == "WARNING":
            rollup.total_warning_count += 1
            warn_msgs[_normalize_message(e.message)] += 1
            if e.timestamp_utc:
                if (not rollup.first_warning_utc
                        or e.timestamp_utc < rollup.first_warning_utc):
                    rollup.first_warning_utc = e.timestamp_utc
                if (not rollup.last_warning_utc
                        or e.timestamp_utc > rollup.last_warning_utc):
                    rollup.last_warning_utc = e.timestamp_utc
        elif e.level in ("ERROR", "CRITICAL"):
            rollup.total_error_count += 1
            if e.level == "CRITICAL" or "critical" in e.message.lower():
                if e.message not in rollup.critical_errors:
                    rollup.critical_errors.append(e.message[:200])
            if e.timestamp_utc:
                if (not rollup.first_error_utc
                        or e.timestamp_utc < rollup.first_error_utc):
                    rollup.first_error_utc = e.timestamp_utc
                if (not rollup.last_error_utc
                        or e.timestamp_utc > rollup.last_error_utc):
                    rollup.last_error_utc = e.timestamp_utc
        if e.timestamp_utc:
            if not rollup.last_log_line_utc or e.timestamp_utc > rollup.last_log_line_utc:
                rollup.last_log_line_utc = e.timestamp_utc

    rollup.repeated_warnings = [
        {"message": msg, "count": count}
        for msg, count in warn_msgs.most_common(repeated_top_n)
        if count > 1
    ]
    rollup.warning_summary = (
        f"{rollup.total_warning_count} warnings across {len(set(warn_msgs))} unique messages."
        if rollup.total_warning_count
        else "No warnings observed."
    )
    rollup.error_summary = (
        f"{rollup.total_error_count} errors observed."
        if rollup.total_error_count
        else "No critical errors found."
    )
    return rollup
