"""Parse a Blick status line.

Blick emits a status record (in L0/partial-L0/status files) containing whitespace-
or comma-separated tokens with keys for current mode, active schedule/routine,
last sun-search outcome, RMS/offset/FWHM, and tracker state.

The exact tokenization differs between Blick versions, so this parser is
tolerant: any token shaped like ``key=value``, ``key:value``, or whitespace-
separated ``key value`` pairs is captured into a dict, and a curated subset is
exposed on the StatusLine dataclass.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Keys we care about (lowercased before lookup).
_MODE_KEYS = ("mode", "current_mode", "operation_mode")
_SCHEDULE_KEYS = ("schedule", "current_schedule", "sked")
_ROUTINE_KEYS = ("routine", "current_routine")
_LAST_ROUTINE_KEYS = ("last_routine", "previous_routine")
_SUN_SEARCH_KEYS = ("sun_search", "sunsearch", "sun_search_status")
_RMS_KEYS = ("rms",)
_OFFSET_KEYS = ("offset",)
_FWHM_KEYS = ("fwhm",)
_AZ_KEYS = ("azimuth", "az", "pointing_azimuth")
_ZEN_KEYS = ("zenith", "zen", "pointing_zenith")
_TRACKER_RESET_KEYS = ("tracker_reset_count", "tracker_resets")
_TRACKER_CONNECTED_KEYS = ("tracker_connected", "tracker_status")
_WARN_COUNT_KEYS = ("warning_count", "warnings")
_FAILED_SUN_KEYS = ("failed_sun_search_count", "sun_search_fail_count")
_TIME_KEYS = ("time", "timestamp", "utc")

_KV_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*(.+)$")


def _tokenize(line: str) -> dict[str, str]:
    """Split a status line into key=value tokens.

    The `status:` (or `state:`, etc.) label prefix is ignored.
    Each remaining whitespace-separated token must look like `key=value`
    or `key:value`; tokens without separator are skipped.
    """
    out: dict[str, str] = {}
    for tok in line.replace(",", " ").split():
        m = _KV_RE.match(tok)
        if not m:
            continue
        k = m.group(1).lower()
        v = m.group(2)
        if v == "":  # bare label like `status:`
            continue
        out[k] = v
    return out


@dataclass(frozen=True)
class StatusLine:
    raw: str
    timestamp_utc: datetime | None = None
    mode: str | None = None
    current_schedule: str | None = None
    current_routine: str | None = None
    last_routine: str | None = None
    sun_search_status: str | None = None
    rms: float | None = None
    offset: float | None = None
    fwhm: float | None = None
    pointing_azimuth: float | None = None
    pointing_zenith: float | None = None
    tracker_reset_count: int | None = None
    tracker_connected: bool | None = None
    warning_count: int | None = None
    failed_sun_search_count: int | None = None
    extras: dict[str, str] = field(default_factory=dict)


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: str) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_bool(value: str) -> bool | None:
    v = value.strip().lower()
    if v in {"true", "1", "yes", "connected", "ok"}:
        return True
    if v in {"false", "0", "no", "disconnected", "down"}:
        return False
    return None


def _to_timestamp(value: str) -> datetime | None:
    # Accept ISO 8601 with or without timezone, or YYYYMMDD'T'HHMMSS.
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            continue
    return None


def _first_match(tokens: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for k in keys:
        if k in tokens:
            return tokens[k]
    return None


def parse_status_line(line: str) -> StatusLine:
    """Parse one status line into a StatusLine dataclass.

    Unknown tokens are preserved in `extras` so downstream consumers can read them.
    """
    tokens = _tokenize(line)

    timestamp = None
    ts_raw = _first_match(tokens, _TIME_KEYS)
    if ts_raw:
        timestamp = _to_timestamp(ts_raw)

    return StatusLine(
        raw=line.strip(),
        timestamp_utc=timestamp,
        mode=_first_match(tokens, _MODE_KEYS),
        current_schedule=_first_match(tokens, _SCHEDULE_KEYS),
        current_routine=_first_match(tokens, _ROUTINE_KEYS),
        last_routine=_first_match(tokens, _LAST_ROUTINE_KEYS),
        sun_search_status=_first_match(tokens, _SUN_SEARCH_KEYS),
        rms=_to_float(_first_match(tokens, _RMS_KEYS) or ""),
        offset=_to_float(_first_match(tokens, _OFFSET_KEYS) or ""),
        fwhm=_to_float(_first_match(tokens, _FWHM_KEYS) or ""),
        pointing_azimuth=_to_float(_first_match(tokens, _AZ_KEYS) or ""),
        pointing_zenith=_to_float(_first_match(tokens, _ZEN_KEYS) or ""),
        tracker_reset_count=_to_int(_first_match(tokens, _TRACKER_RESET_KEYS) or ""),
        tracker_connected=_to_bool(_first_match(tokens, _TRACKER_CONNECTED_KEYS) or ""),
        warning_count=_to_int(_first_match(tokens, _WARN_COUNT_KEYS) or ""),
        failed_sun_search_count=_to_int(_first_match(tokens, _FAILED_SUN_KEYS) or ""),
        extras={k: v for k, v in tokens.items() if k not in _KNOWN_KEYS},
    )


_KNOWN_KEYS: frozenset[str] = frozenset(
    _MODE_KEYS + _SCHEDULE_KEYS + _ROUTINE_KEYS + _LAST_ROUTINE_KEYS
    + _SUN_SEARCH_KEYS + _RMS_KEYS + _OFFSET_KEYS + _FWHM_KEYS
    + _AZ_KEYS + _ZEN_KEYS + _TRACKER_RESET_KEYS + _TRACKER_CONNECTED_KEYS
    + _WARN_COUNT_KEYS + _FAILED_SUN_KEYS + _TIME_KEYS
)
