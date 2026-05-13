"""Aggregate L0 and partial-L0/status files into operational metrics.

Strategy:
- Scan headers / metadata lines for status-line tokens.
- Count data rows for `measurement_count`.
- Track first/last measurement timestamps where available.
- Track distinct routines observed.

L0 files vary in format across Blick versions, so this parser only consumes
lines that look like status records and is tolerant of everything else.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .file_inventory_parser import FileEntry
from .status_line_parser import StatusLine, parse_status_line


@dataclass
class L0Info:
    l0_status: str = "UNKNOWN"            # PRESENT | MISSING | PARTIAL | UNKNOWN
    l0_file_count: int = 0
    partial_l0_file_count: int = 0
    first_measurement_utc: datetime | None = None
    last_successful_measurement_utc: datetime | None = None
    measurement_count: int = 0
    current_mode: str | None = None
    current_schedule: str | None = None
    current_routine: str | None = None
    last_routine: str | None = None
    routines_observed: list[str] = field(default_factory=list)
    warning_count_from_status_line: int | None = None
    tracker_reset_count_from_status_line: int | None = None
    sun_search_status: str | None = None
    rms: float | None = None
    offset: float | None = None
    fwhm: float | None = None
    pointing_azimuth: float | None = None
    pointing_zenith: float | None = None
    tracker_connected: bool | None = None
    failed_sun_search_count: int | None = None
    last_status_line: StatusLine | None = None


_STATUS_HINTS = ("status", "mode", "routine", "schedule", "rms", "tracker")


def _looks_like_status(line: str) -> bool:
    lower = line.lower()
    return any(h in lower for h in _STATUS_HINTS) and ("=" in line or ":" in line)


def _looks_like_data_row(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    # A data row typically starts with a numeric / timestamp token.
    head = stripped.split()[0] if stripped.split() else ""
    return any(ch.isdigit() for ch in head)


def _merge(info: L0Info, s: StatusLine) -> None:
    if s.mode and not info.current_mode:
        info.current_mode = s.mode
    info.current_mode = s.mode or info.current_mode
    info.current_schedule = s.current_schedule or info.current_schedule
    info.current_routine = s.current_routine or info.current_routine
    info.last_routine = s.last_routine or info.last_routine
    info.sun_search_status = s.sun_search_status or info.sun_search_status
    info.rms = s.rms if s.rms is not None else info.rms
    info.offset = s.offset if s.offset is not None else info.offset
    info.fwhm = s.fwhm if s.fwhm is not None else info.fwhm
    info.pointing_azimuth = (
        s.pointing_azimuth if s.pointing_azimuth is not None else info.pointing_azimuth
    )
    info.pointing_zenith = (
        s.pointing_zenith if s.pointing_zenith is not None else info.pointing_zenith
    )
    if s.tracker_reset_count is not None:
        info.tracker_reset_count_from_status_line = s.tracker_reset_count
    if s.tracker_connected is not None:
        info.tracker_connected = s.tracker_connected
    if s.warning_count is not None:
        info.warning_count_from_status_line = s.warning_count
    if s.failed_sun_search_count is not None:
        info.failed_sun_search_count = s.failed_sun_search_count
    if s.current_routine and s.current_routine not in info.routines_observed:
        info.routines_observed.append(s.current_routine)
    if s.timestamp_utc:
        if not info.first_measurement_utc or s.timestamp_utc < info.first_measurement_utc:
            info.first_measurement_utc = s.timestamp_utc
        if (not info.last_successful_measurement_utc
                or s.timestamp_utc > info.last_successful_measurement_utc):
            info.last_successful_measurement_utc = s.timestamp_utc
    info.last_status_line = s


def _parse_one(path: Path, info: L0Info) -> None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if _looks_like_status(line):
                    _merge(info, parse_status_line(line))
                elif _looks_like_data_row(line):
                    info.measurement_count += 1
    except OSError:
        return


def parse_l0_files(
    l0_entries: list[FileEntry],
    partial_entries: list[FileEntry],
) -> L0Info:
    info = L0Info()
    info.l0_file_count = len(l0_entries)
    info.partial_l0_file_count = len(partial_entries)

    for e in l0_entries:
        _parse_one(e.path, info)
    for e in partial_entries:
        _parse_one(e.path, info)

    if l0_entries:
        info.l0_status = "PRESENT"
    elif partial_entries:
        info.l0_status = "PARTIAL"
    else:
        info.l0_status = "MISSING"

    return info
