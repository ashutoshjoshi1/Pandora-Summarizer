from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pandora_edge.config import HealthThresholds
from pandora_edge.health.rules import (
    AlignmentLabel,
    OnlineStatus,
    TrackerHealth,
    alignment_comment,
    alignment_label,
    online_status,
    score_label,
    tracker_health,
)


def test_online_when_l0_and_logs_present_and_recent() -> None:
    now = datetime.now(timezone.utc)
    status, reason = online_status(
        last_seen_utc=now - timedelta(hours=1),
        has_l0=True, has_partial_l0=False, has_logs=True,
        offline_hours_threshold=24, now_utc=now,
    )
    assert status == OnlineStatus.ONLINE
    assert reason is None


def test_offline_when_last_seen_exceeds_threshold() -> None:
    now = datetime.now(timezone.utc)
    status, reason = online_status(
        last_seen_utc=now - timedelta(hours=48),
        has_l0=True, has_partial_l0=False, has_logs=True,
        offline_hours_threshold=24, now_utc=now,
    )
    assert status == OnlineStatus.OFFLINE
    assert reason and "Last activity" in reason


def test_unknown_when_no_data() -> None:
    status, _ = online_status(
        last_seen_utc=None,
        has_l0=False, has_partial_l0=False, has_logs=False,
        offline_hours_threshold=24,
    )
    assert status == OnlineStatus.UNKNOWN


def test_alignment_label_uses_weighting_threshold() -> None:
    th = HealthThresholds()
    assert alignment_label(
        found=True, latest_weighting=600.0, bad_scan_count=0, thresholds=th,
    ) == AlignmentLabel.GOOD
    assert alignment_label(
        found=True, latest_weighting=400.0, bad_scan_count=1, thresholds=th,
    ) == AlignmentLabel.WARNING
    assert alignment_label(
        found=True, latest_weighting=400.0, bad_scan_count=5, thresholds=th,
    ) == AlignmentLabel.CRITICAL
    assert alignment_label(
        found=False, latest_weighting=None, bad_scan_count=0, thresholds=th,
    ) == AlignmentLabel.UNKNOWN


def test_alignment_comment_matches_spec() -> None:
    th = HealthThresholds(alignment_weighting_min_good=500)
    assert alignment_comment(latest_weighting=600.0, thresholds=th) == "Scans are good."
    assert "below 500" in alignment_comment(latest_weighting=300.0, thresholds=th)


def test_tracker_health_classification() -> None:
    th = HealthThresholds(tracker_reset_red=3)
    assert tracker_health(connected=True, reset_count=0, thresholds=th) == TrackerHealth.GOOD
    assert tracker_health(connected=True, reset_count=1, thresholds=th) == TrackerHealth.WARNING
    assert tracker_health(connected=True, reset_count=5, thresholds=th) == TrackerHealth.CRITICAL
    assert tracker_health(connected=False, reset_count=0, thresholds=th) == TrackerHealth.CRITICAL
    assert tracker_health(connected=None, reset_count=None, thresholds=th) == TrackerHealth.UNKNOWN


def test_score_label_thresholds() -> None:
    assert score_label(95) == "GREEN"
    assert score_label(80) == "YELLOW"
    assert score_label(40) == "RED"
    assert score_label(None) == "GRAY"
