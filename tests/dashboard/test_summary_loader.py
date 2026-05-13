from __future__ import annotations

from datetime import date

from dashboard.services.summary_loader import load_summary


def test_loads_full_summary() -> None:
    data = {
        "schema_version": "2.0",
        "instrument_id": "Pandora024",
        "target_date": "2026-05-12",
        "generated_at_utc": "2026-05-13T10:00:00Z",
        "host": {"location_name": "GSFC", "timezone": "America/New_York",
                 "display_name": "P24"},
        "status": {"online_status": "ONLINE",
                   "last_log_received_utc": "x", "last_file_received_utc": "y"},
        "operation": {"mode": "SCHEDULE", "current_schedule": "s",
                      "current_routine": "SO",
                      "last_successful_measurement_utc": "z"},
        "logs": {"total_warning_count": 2, "total_error_count": 1},
        "tracker": {"tracker_health": "GOOD"},
        "sun_search": {"sun_search_status": "SUCCESS"},
        "alignment": {"alignment_health": "GOOD",
                      "latest_weighting_factor": 1459.5,
                      "alignment_comment": "Scans are good."},
        "files": {"l0": {"status": "PRESENT"},
                  "partial_l0": {"status": "PRESENT"}},
        "upload": {"upload_status": "COMPLETED",
                   "uploaded_objects_count": 5,
                   "uploaded_bytes": 1024},
        "health": {"daily_health_score": 95, "daily_health_label": "GREEN"},
    }
    rec = load_summary(data)
    assert rec is not None
    assert rec.instrument_id == "Pandora024"
    assert rec.target_date == date(2026, 5, 12)
    assert rec.health_score == 95
    assert rec.alignment_weighting == 1459.5
    assert rec.warning_count == 2
    assert rec.error_count == 1


def test_returns_none_for_empty_input() -> None:
    assert load_summary({}) is None
    assert load_summary(None) is None


def test_handles_partial_input_gracefully() -> None:
    rec = load_summary({"instrument_id": "P1", "target_date": "2026-05-12"})
    assert rec is not None
    assert rec.health_score == 0
    assert rec.health_label == "GRAY"
    assert rec.l0_status == "UNKNOWN"
