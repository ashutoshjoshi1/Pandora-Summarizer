"""Build a small fixtures tree of summary.json files for dashboard tests."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from dashboard.app import create_app
from dashboard.config import DashboardConfig


def _summary(instrument_id: str, target_date: date, *,
             health_score: int = 95, health_label: str = "GREEN",
             online: str = "ONLINE", warnings: int = 0, errors: int = 0,
             alignment: str = "GOOD", l0_status: str = "PRESENT",
             upload: str = "COMPLETED") -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "instrument_id": instrument_id,
        "target_date": target_date.isoformat(),
        "generated_at_utc": "2026-05-13T10:00:00Z",
        "host": {
            "hostname": f"{instrument_id}-PC", "os": "Windows 10",
            "service_version": "0.2.0", "blick_version": None,
            "display_name": instrument_id, "location_name": "GSFC",
            "timezone": "America/New_York",
        },
        "status": {
            "online_status": online,
            "last_seen_utc": "2026-05-12T23:00:00Z",
            "last_log_received_utc": "2026-05-12T23:00:00Z",
            "last_file_received_utc": "2026-05-12T22:55:00Z",
            "offline_reason": None,
            "missing_expected_files": [],
        },
        "operation": {
            "mode": "SCHEDULE", "current_schedule": "uv_sun.sked",
            "current_routine": "SO", "last_routine": "SO",
            "last_successful_measurement_utc": "2026-05-12T22:55:00Z",
            "measurement_count": 1200, "l0_file_count": 1,
            "partial_l0_file_count": 144, "routines_observed": ["SO"],
        },
        "logs": {
            "total_warning_count": warnings, "total_error_count": errors,
            "repeated_warnings": [], "critical_errors": [],
            "warning_summary": "ok", "error_summary": "ok",
        },
        "tracker": {
            "tracker_connected": True, "tracker_reset_count": 0,
            "last_tracker_reset_utc": None, "tracker_health": "GOOD",
        },
        "sun_search": {
            "last_sun_search_utc": "2026-05-12T16:10:00Z",
            "sun_search_status": "SUCCESS",
            "failed_sun_search_count": 0,
            "rms": 0.02, "offset": 0.01, "fwhm": 0.5,
        },
        "alignment": {
            "alignment_file_found": True,
            "last_alignment_utc": "2026-05-12T16:10:00Z",
            "latest_scan_type": "FS",
            "latest_weighting_factor": 1459.5, "latest_rms": 0.026,
            "scan_count": 10, "good_scan_count": 9, "bad_scan_count": 1,
            "alignment_health": alignment,
            "alignment_comment": "Scans are good.",
        },
        "files": {
            "l0": {"status": l0_status, "files": [], "total_bytes": 0},
            "partial_l0": {"status": "PRESENT", "files": [], "total_bytes": 0},
            "logs": {"status": "PRESENT", "oslog": {"status": "PRESENT", "files": [], "total_bytes": 0}, "fslog": {"status": "PRESENT", "files": [], "total_bytes": 0}, "pslog": {"status": "PRESENT", "files": [], "total_bytes": 0}},
            "alignment": {"status": "PRESENT", "files": [], "total_bytes": 0},
            "figures": {"status": "PRESENT", "files": [], "count": 0, "total_bytes": 0},
        },
        "upload": {
            "upload_status": upload,
            "gcs_prefix": f"pandora-fleet-monitoring/{instrument_id}/{target_date.isoformat()}/",
            "uploaded_objects_count": 15, "uploaded_bytes": 12345678,
            "failed_uploads": [], "retry_count": 0,
            "upload_started_at_utc": "2026-05-13T10:00:00Z",
            "upload_finished_at_utc": "2026-05-13T10:01:00Z",
        },
        "health": {
            "daily_health_score": health_score,
            "daily_health_label": health_label,
            "score_breakdown": {"base": 100},
            "summary": f"{instrument_id} OK",
        },
        "service_status": {
            "overall": "COMPLETED", "attempt": 1, "duration_seconds": 60,
            "steps": [], "errors": [],
        },
    }


@pytest.fixture
def fixtures_dir(tmp_path: Path) -> Path:
    """Three instruments x two days each."""
    root = tmp_path / "summaries"
    cases = [
        ("Pandora024", date(2026, 5, 12), {"health_score": 95, "health_label": "GREEN"}),
        ("Pandora024", date(2026, 5, 11), {"health_score": 92, "health_label": "GREEN"}),
        ("Pandora099", date(2026, 5, 12),
         {"health_score": 60, "health_label": "YELLOW",
          "warnings": 6, "alignment": "WARNING"}),
        ("Pandora099", date(2026, 5, 11), {"health_score": 70, "health_label": "YELLOW"}),
        ("Pandora200", date(2026, 5, 12),
         {"health_score": 20, "health_label": "RED",
          "online": "OFFLINE", "errors": 6, "upload": "FAILED",
          "l0_status": "MISSING"}),
    ]
    for instrument, d, kw in cases:
        target = root / instrument / d.isoformat()
        target.mkdir(parents=True)
        (target / "summary.json").write_text(json.dumps(_summary(instrument, d, **kw)))
    return root


@pytest.fixture
def app(fixtures_dir: Path):
    cfg = DashboardConfig(
        bucket="test-bucket",
        prefix="pandora-fleet-monitoring",
        service_account_json=None,
        fixtures_dir=fixtures_dir,
        cache_seconds=1,
    )
    app = create_app(cfg)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()
