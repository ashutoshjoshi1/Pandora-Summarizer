"""Parse Blick alignment files.

Alignment files contain scan records (typically tabular). Each record has at
least: scan type (FS, MS, etc.), weighting factor, RMS, and a timestamp.
Implementation is tolerant: we read header tokens, find columns by name, and
fall back to whitespace-positional parsing if the header is missing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .file_inventory_parser import FileEntry

_HEADER_HINTS = ("scan", "weight", "rms")


@dataclass(frozen=True)
class AlignmentScan:
    scan_type: str | None
    weighting_factor: float | None
    rms: float | None
    timestamp_utc: datetime | None
    raw: str


@dataclass
class AlignmentInfo:
    alignment_file_found: bool = False
    last_alignment_utc: datetime | None = None
    latest_scan_type: str | None = None
    latest_weighting_factor: float | None = None
    latest_rms: float | None = None
    scan_count: int = 0
    good_scan_count: int = 0
    bad_scan_count: int = 0
    scans: list[AlignmentScan] = field(default_factory=list)


_TS_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"
)
_NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
_SCAN_TYPE_RE = re.compile(r"\b(FS|MS|UC|SU|SO|SB|MU|MO|MB)\b")


def _parse_ts(raw: str) -> datetime | None:
    raw = raw.replace("Z", "+00:00").replace(" ", "T")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _split_columns(header: str) -> dict[str, int]:
    # Strip a leading comment marker so its position doesn't shift columns.
    cleaned = header.lstrip()
    if cleaned.startswith("#"):
        cleaned = cleaned[1:].lstrip()
    cols: dict[str, int] = {}
    for i, tok in enumerate(cleaned.lower().replace(",", " ").split()):
        cols[tok] = i
    return cols


def _find(cols: dict[str, int], *aliases: str) -> int | None:
    for a in aliases:
        if a in cols:
            return cols[a]
    return None


def _parse_data_row(
    row: str, cols: dict[str, int] | None,
) -> AlignmentScan | None:
    tokens = row.replace(",", " ").split()
    if not tokens:
        return None

    ts_match = _TS_RE.search(row)
    timestamp = _parse_ts(ts_match.group(1)) if ts_match else None

    scan_type: str | None = None
    weighting: float | None = None
    rms: float | None = None

    if cols:
        st_idx = _find(cols, "scan_type", "type", "scan")
        w_idx = _find(cols, "weighting_factor", "weight", "weighting", "wf")
        r_idx = _find(cols, "rms")
        if st_idx is not None and st_idx < len(tokens):
            scan_type = tokens[st_idx]
        if w_idx is not None and w_idx < len(tokens):
            try:
                weighting = float(tokens[w_idx])
            except ValueError:
                pass
        if r_idx is not None and r_idx < len(tokens):
            try:
                rms = float(tokens[r_idx])
            except ValueError:
                pass

    if scan_type is None:
        m = _SCAN_TYPE_RE.search(row)
        if m:
            scan_type = m.group(1)

    if weighting is None or rms is None:
        nums = [float(n) for n in _NUM_RE.findall(row)]
        if weighting is None and len(nums) >= 2:
            # Heuristic: the largest plausibly-bounded value is the weighting.
            big = [n for n in nums if n >= 1]
            if big:
                weighting = max(big)
        if rms is None and nums:
            small = [n for n in nums if 0 <= n < 1]
            if small:
                rms = small[0]

    if scan_type is None and weighting is None and rms is None and timestamp is None:
        return None

    return AlignmentScan(
        scan_type=scan_type,
        weighting_factor=weighting,
        rms=rms,
        timestamp_utc=timestamp,
        raw=row.strip()[:200],
    )


def _parse_one(path: Path, info: AlignmentInfo, min_good_weighting: float) -> None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            lines = [ln for ln in f if ln.strip()]
    except OSError:
        return

    cols: dict[str, int] | None = None
    for line in lines:
        lower = line.lower()
        if any(h in lower for h in _HEADER_HINTS) and not _TS_RE.search(line):
            cols = _split_columns(line)
            continue
        if line.strip().startswith("#"):
            continue
        scan = _parse_data_row(line, cols)
        if scan is None:
            continue
        info.scans.append(scan)
        info.scan_count += 1
        if scan.weighting_factor is not None:
            if scan.weighting_factor >= min_good_weighting:
                info.good_scan_count += 1
            else:
                info.bad_scan_count += 1
        if scan.timestamp_utc and (
            info.last_alignment_utc is None
            or scan.timestamp_utc > info.last_alignment_utc
        ):
            info.last_alignment_utc = scan.timestamp_utc
            info.latest_scan_type = scan.scan_type or info.latest_scan_type
            if scan.weighting_factor is not None:
                info.latest_weighting_factor = scan.weighting_factor
            if scan.rms is not None:
                info.latest_rms = scan.rms


def parse_alignment_files(
    entries: list[FileEntry], *, min_good_weighting: float = 500.0,
) -> AlignmentInfo:
    info = AlignmentInfo()
    info.alignment_file_found = bool(entries)
    for e in entries:
        _parse_one(e.path, info, min_good_weighting)

    # If no timestamp was found inside the files, fall back to file mtimes.
    if info.alignment_file_found and info.last_alignment_utc is None:
        info.last_alignment_utc = max(e.modified_utc for e in entries)

    # If we have scans but never landed on a "latest" — use the last appended.
    if info.scans and info.latest_weighting_factor is None:
        last_scan = info.scans[-1]
        info.latest_scan_type = info.latest_scan_type or last_scan.scan_type
        info.latest_weighting_factor = last_scan.weighting_factor
        info.latest_rms = last_scan.rms

    return info
