"""Step: build the canonical summary.json dict (schema version 2.0)."""
from __future__ import annotations

import json
import platform
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from ..config import Config, HealthThresholds
from ..gcs import UploadResult
from ..health import (
    HealthInputs,
    OnlineStatus,
    alignment_comment,
    alignment_label,
    online_status,
    score_health,
    tracker_health,
)
from ..parsers import (
    AlignmentInfo,
    FileEntry,
    FileInventory,
    L0Info,
    LogRollup,
)
from ..version import __version__

SCHEMA_VERSION = "2.0"


@dataclass(frozen=True)
class StepStatusEntry:
    name: str
    status: str
    duration_ms: int
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _isoz(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _entries_to_json(entries: list[FileEntry]) -> list[dict[str, Any]]:
    return [
        {
            "filename": e.name,
            "size_bytes": e.size_bytes,
            "sha256": e.sha256,
            "modified_utc": _isoz(e.modified_utc),
        }
        for e in entries
    ]


def _file_section(
    entries: list[FileEntry], *, expected: bool = True,
) -> dict[str, Any]:
    status = "PRESENT" if entries else ("MISSING" if expected else "UNKNOWN")
    return {
        "status": status,
        "files": _entries_to_json(entries),
        "total_bytes": sum(e.size_bytes for e in entries),
    }


def build_summary(
    *,
    cfg: Config,
    target_date: date,
    inventory: FileInventory,
    l0: L0Info,
    logs: LogRollup,
    alignment: AlignmentInfo,
    upload: UploadResult,
    upload_started_at_utc: datetime | None,
    upload_finished_at_utc: datetime | None,
    gcs_prefix: str,
    attempt: int,
    started_at: datetime,
    finished_at: datetime,
    steps: list[StepStatusEntry],
    service_errors: list[str],
    thresholds: HealthThresholds | None = None,
) -> dict[str, Any]:
    th = thresholds or cfg.health_thresholds

    # Online status
    last_seen = inventory.last_file_mtime_utc()
    if logs.last_log_line_utc and (last_seen is None or logs.last_log_line_utc > last_seen):
        last_seen = logs.last_log_line_utc

    status_value, offline_reason = online_status(
        last_seen_utc=last_seen,
        has_l0=bool(inventory.l0),
        has_partial_l0=bool(inventory.partial_l0),
        has_logs=bool(inventory.all_logs),
        offline_hours_threshold=th.offline_hours_threshold,
        now_utc=finished_at,
    )

    missing_expected: list[str] = []
    if not inventory.l0 and not inventory.partial_l0:
        missing_expected.append("L0_or_partial_L0")
    if not inventory.all_logs:
        missing_expected.append("logs")

    # Tracker / alignment categorical health
    al_label = alignment_label(
        found=alignment.alignment_file_found,
        latest_weighting=alignment.latest_weighting_factor,
        bad_scan_count=alignment.bad_scan_count,
        thresholds=th,
    )
    tr_label = tracker_health(
        connected=l0.tracker_connected,
        reset_count=l0.tracker_reset_count_from_status_line,
        thresholds=th,
    )

    # Score
    score = score_health(
        HealthInputs(
            online=status_value,
            has_l0=bool(inventory.l0),
            has_partial_l0=bool(inventory.partial_l0),
            warning_count=logs.total_warning_count,
            error_count=logs.total_error_count,
            alignment=al_label,
            tracker=tr_label,
            tracker_reset_count=l0.tracker_reset_count_from_status_line,
            failed_sun_search_count=l0.failed_sun_search_count,
            upload_status=upload.status,
        ),
        thresholds=th,
        instrument_label=cfg.instrument.display_name or cfg.instrument.id,
    )

    overall = (
        "FAILED" if upload.status == "FAILED" or any(s.status == "FAILED" for s in steps)
        else "PARTIAL" if (
            upload.status == "PARTIAL" or status_value == OnlineStatus.PARTIAL
            or missing_expected
        )
        else "COMPLETED"
    )

    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "instrument_id": cfg.instrument.id,
        "target_date": target_date.isoformat(),
        "generated_at_utc": _isoz(finished_at),
        "host": {
            "hostname": platform.node(),
            "os": f"{platform.system()} {platform.release()}",
            "service_version": __version__,
            "blick_version": None,
            "display_name": cfg.instrument.display_name,
            "location_name": cfg.instrument.location_name,
            "timezone": cfg.instrument.timezone,
        },
        "status": {
            "online_status": status_value.value,
            "last_seen_utc": _isoz(last_seen),
            "last_log_received_utc": _isoz(logs.last_log_line_utc),
            "last_file_received_utc": _isoz(inventory.last_file_mtime_utc()),
            "offline_reason": offline_reason,
            "missing_expected_files": missing_expected,
        },
        "operation": {
            "mode": l0.current_mode or "UNKNOWN",
            "current_schedule": l0.current_schedule,
            "current_routine": l0.current_routine,
            "last_routine": l0.last_routine,
            "last_started_schedule": l0.current_schedule,
            "last_started_routine": l0.current_routine,
            "last_successful_measurement_utc": _isoz(l0.last_successful_measurement_utc),
            "first_measurement_utc": _isoz(l0.first_measurement_utc),
            "measurement_count": l0.measurement_count,
            "l0_file_count": l0.l0_file_count,
            "partial_l0_file_count": l0.partial_l0_file_count,
            "routines_observed": l0.routines_observed,
            "l0_status": l0.l0_status,
        },
        "logs": {
            "total_warning_count": logs.total_warning_count,
            "total_error_count": logs.total_error_count,
            "repeated_warnings": logs.repeated_warnings,
            "critical_errors": logs.critical_errors,
            "warning_summary": logs.warning_summary,
            "error_summary": logs.error_summary,
            "first_warning_utc": _isoz(logs.first_warning_utc),
            "last_warning_utc": _isoz(logs.last_warning_utc),
            "first_error_utc": _isoz(logs.first_error_utc),
            "last_error_utc": _isoz(logs.last_error_utc),
        },
        "tracker": {
            "tracker_connected": l0.tracker_connected,
            "tracker_reset_count": l0.tracker_reset_count_from_status_line,
            "last_tracker_reset_utc": None,
            "tracker_health": tr_label.value,
        },
        "sun_search": {
            "last_sun_search_utc": _isoz(l0.last_successful_measurement_utc),
            "sun_search_status": l0.sun_search_status,
            "failed_sun_search_count": l0.failed_sun_search_count or 0,
            "rms": l0.rms,
            "offset": l0.offset,
            "fwhm": l0.fwhm,
            "pointing_azimuth": l0.pointing_azimuth,
            "pointing_zenith": l0.pointing_zenith,
        },
        "alignment": {
            "alignment_file_found": alignment.alignment_file_found,
            "last_alignment_utc": _isoz(alignment.last_alignment_utc),
            "latest_scan_type": alignment.latest_scan_type,
            "latest_weighting_factor": alignment.latest_weighting_factor,
            "latest_rms": alignment.latest_rms,
            "scan_count": alignment.scan_count,
            "good_scan_count": alignment.good_scan_count,
            "bad_scan_count": alignment.bad_scan_count,
            "alignment_health": al_label.value,
            "alignment_comment": alignment_comment(
                latest_weighting=alignment.latest_weighting_factor, thresholds=th,
            ),
        },
        "files": {
            "l0": _file_section(inventory.l0),
            "partial_l0": _file_section(inventory.partial_l0),
            "logs": {
                "status": "PRESENT" if inventory.all_logs else "MISSING",
                "oslog": _file_section(inventory.oslog),
                "fslog": _file_section(inventory.fslog),
                "pslog": _file_section(inventory.pslog),
            },
            "alignment": _file_section(inventory.alignment),
            "figures": {
                **_file_section(inventory.figures, expected=False),
                "count": len(inventory.figures),
            },
            "skipped_unstable": [p.name for p in inventory.skipped_unstable],
        },
        "upload": {
            "upload_status": upload.status,
            "gcs_prefix": gcs_prefix,
            "uploaded_objects_count": upload.uploaded_objects_count,
            "uploaded_bytes": upload.uploaded_bytes,
            "failed_uploads": upload.failed_uploads,
            "retry_count": upload.retry_count,
            "upload_started_at_utc": _isoz(upload_started_at_utc),
            "upload_finished_at_utc": _isoz(upload_finished_at_utc),
        },
        "health": {
            "daily_health_score": score.score,
            "daily_health_label": score.label,
            "score_breakdown": score.breakdown,
            "summary": score.summary,
        },
        "service_status": {
            "overall": overall,
            "attempt": attempt,
            "duration_seconds": int((finished_at - started_at).total_seconds()),
            "steps": [
                {
                    "name": s.name,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "error": s.error,
                    **({"extra": s.extra} if s.extra else {}),
                }
                for s in steps
            ],
            "errors": service_errors,
        },
    }
    return summary


def write_summary(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=False)
        f.write("\n")
