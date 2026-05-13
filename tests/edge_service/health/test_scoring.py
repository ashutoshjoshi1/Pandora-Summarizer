from __future__ import annotations

from pandora_edge.config import HealthThresholds
from pandora_edge.health.rules import AlignmentLabel, OnlineStatus, TrackerHealth
from pandora_edge.health.scoring import HealthInputs, score_health


def _inputs(**overrides) -> HealthInputs:
    base = dict(
        online=OnlineStatus.ONLINE,
        has_l0=True, has_partial_l0=False,
        warning_count=0, error_count=0,
        alignment=AlignmentLabel.GOOD,
        tracker=TrackerHealth.GOOD,
        tracker_reset_count=0,
        failed_sun_search_count=0,
        upload_status="COMPLETED",
    )
    base.update(overrides)
    return HealthInputs(**base)


def test_green_when_everything_nominal() -> None:
    s = score_health(_inputs(), HealthThresholds())
    assert s.score == 100
    assert s.label == "GREEN"
    assert s.breakdown["base"] == 100


def test_offline_drops_score_significantly() -> None:
    s = score_health(_inputs(online=OnlineStatus.OFFLINE), HealthThresholds())
    assert s.score <= 60
    assert s.breakdown["offline_penalty"] == 40


def test_red_thresholds_compound() -> None:
    s = score_health(
        _inputs(
            warning_count=25, error_count=10,
            alignment=AlignmentLabel.CRITICAL,
            tracker=TrackerHealth.CRITICAL,
            tracker_reset_count=5, failed_sun_search_count=4,
            upload_status="FAILED",
        ),
        HealthThresholds(),
    )
    assert s.score == 0  # clamped
    assert s.label == "RED"


def test_unknown_online_yields_gray() -> None:
    s = score_health(_inputs(online=OnlineStatus.UNKNOWN, has_l0=False),
                     HealthThresholds())
    assert s.label == "GRAY"


def test_summary_text_mentions_observations() -> None:
    s = score_health(
        _inputs(warning_count=3, error_count=1, alignment=AlignmentLabel.CRITICAL),
        HealthThresholds(),
        instrument_label="Pandora007",
    )
    assert "Pandora007" in s.summary
    assert "warning" in s.summary.lower()
    assert "error" in s.summary.lower()
