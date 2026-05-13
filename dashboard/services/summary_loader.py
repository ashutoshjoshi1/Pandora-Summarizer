"""Flatten a raw summary.json dict into a UI-friendly record.

Defensive: any missing field falls back to None / "" / 0 so a partial
summary still renders in the dashboard.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


def _g(d: dict[str, Any] | None, *path: str, default: Any = None) -> Any:
    cur: Any = d or {}
    for p in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(p)
        if cur is None:
            return default
    return cur


@dataclass(frozen=True)
class SummaryRecord:
    instrument_id: str
    target_date: date
    generated_at_utc: str | None

    online_status: str
    health_label: str
    health_score: int

    location_name: str | None
    timezone: str | None
    display_name: str | None

    last_log_received_utc: str | None
    last_file_received_utc: str | None
    last_successful_measurement_utc: str | None
    current_schedule: str | None
    current_routine: str | None
    mode: str | None

    warning_count: int
    error_count: int
    tracker_health: str
    sun_search_status: str | None

    alignment_health: str
    alignment_weighting: float | None
    alignment_comment: str | None

    l0_status: str
    partial_l0_status: str

    upload_status: str
    upload_objects: int
    upload_bytes: int

    raw: dict[str, Any]


def load_summary(data: dict[str, Any] | None) -> SummaryRecord | None:
    if not data:
        return None
    iso = _g(data, "target_date")
    try:
        td = date.fromisoformat(iso) if iso else None
    except (TypeError, ValueError):
        td = None
    if td is None:
        return None
    return SummaryRecord(
        instrument_id=_g(data, "instrument_id", default="UNKNOWN"),
        target_date=td,
        generated_at_utc=_g(data, "generated_at_utc"),
        online_status=_g(data, "status", "online_status", default="UNKNOWN"),
        health_label=_g(data, "health", "daily_health_label", default="GRAY"),
        health_score=int(_g(data, "health", "daily_health_score", default=0)),
        location_name=_g(data, "host", "location_name"),
        timezone=_g(data, "host", "timezone"),
        display_name=_g(data, "host", "display_name"),
        last_log_received_utc=_g(data, "status", "last_log_received_utc"),
        last_file_received_utc=_g(data, "status", "last_file_received_utc"),
        last_successful_measurement_utc=_g(
            data, "operation", "last_successful_measurement_utc",
        ),
        current_schedule=_g(data, "operation", "current_schedule"),
        current_routine=_g(data, "operation", "current_routine"),
        mode=_g(data, "operation", "mode"),
        warning_count=int(_g(data, "logs", "total_warning_count", default=0)),
        error_count=int(_g(data, "logs", "total_error_count", default=0)),
        tracker_health=_g(data, "tracker", "tracker_health", default="UNKNOWN"),
        sun_search_status=_g(data, "sun_search", "sun_search_status"),
        alignment_health=_g(data, "alignment", "alignment_health", default="UNKNOWN"),
        alignment_weighting=_g(data, "alignment", "latest_weighting_factor"),
        alignment_comment=_g(data, "alignment", "alignment_comment"),
        l0_status=_g(data, "files", "l0", "status", default="UNKNOWN"),
        partial_l0_status=_g(data, "files", "partial_l0", "status", default="UNKNOWN"),
        upload_status=_g(data, "upload", "upload_status", default="UNKNOWN"),
        upload_objects=int(_g(data, "upload", "uploaded_objects_count", default=0)),
        upload_bytes=int(_g(data, "upload", "uploaded_bytes", default=0)),
        raw=data,
    )
