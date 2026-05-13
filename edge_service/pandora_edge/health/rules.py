"""Categorical health labels derived from raw inputs + thresholds."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from ..config import HealthThresholds


class OnlineStatus(str, Enum):
    ONLINE = "ONLINE"
    PARTIAL = "PARTIAL"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


class AlignmentLabel(str, Enum):
    GOOD = "GOOD"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class TrackerHealth(str, Enum):
    GOOD = "GOOD"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


def online_status(
    *,
    last_seen_utc: datetime | None,
    has_l0: bool,
    has_partial_l0: bool,
    has_logs: bool,
    offline_hours_threshold: int,
    now_utc: datetime | None = None,
) -> tuple[OnlineStatus, str | None]:
    """Return (status, offline_reason). offline_reason is None when ONLINE."""
    if last_seen_utc is None and not (has_l0 or has_partial_l0 or has_logs):
        return OnlineStatus.UNKNOWN, "No data found for target date."

    now = now_utc or datetime.now(timezone.utc)
    hours_since = None
    if last_seen_utc is not None:
        if last_seen_utc.tzinfo is None:
            last_seen_utc = last_seen_utc.replace(tzinfo=timezone.utc)
        hours_since = (now - last_seen_utc).total_seconds() / 3600.0

    if hours_since is not None and hours_since > offline_hours_threshold:
        return OnlineStatus.OFFLINE, (
            f"Last activity {hours_since:.1f}h ago "
            f"(threshold {offline_hours_threshold}h)."
        )

    if has_l0 and has_logs:
        return OnlineStatus.ONLINE, None
    if has_l0 or has_partial_l0 or has_logs:
        return OnlineStatus.PARTIAL, "Some expected files missing."
    return OnlineStatus.OFFLINE, "No L0 / status / logs for target date."


def alignment_label(
    *,
    found: bool,
    latest_weighting: float | None,
    bad_scan_count: int,
    thresholds: HealthThresholds,
) -> AlignmentLabel:
    if not found:
        return AlignmentLabel.UNKNOWN
    if latest_weighting is None:
        return AlignmentLabel.WARNING
    if latest_weighting < thresholds.alignment_weighting_min_good:
        return (AlignmentLabel.CRITICAL if bad_scan_count > 2 else AlignmentLabel.WARNING)
    return AlignmentLabel.GOOD


def alignment_comment(
    *, latest_weighting: float | None, thresholds: HealthThresholds,
) -> str:
    if latest_weighting is None:
        return "No weighting factor recorded."
    if latest_weighting < thresholds.alignment_weighting_min_good:
        return (
            "Scans are not good. Weighting factor for this routine is below "
            f"{thresholds.alignment_weighting_min_good:g}. Check alignment."
        )
    return "Scans are good."


def tracker_health(
    *,
    connected: bool | None,
    reset_count: int | None,
    thresholds: HealthThresholds,
) -> TrackerHealth:
    if connected is False:
        return TrackerHealth.CRITICAL
    if reset_count is not None and reset_count >= thresholds.tracker_reset_red:
        return TrackerHealth.CRITICAL
    if reset_count is not None and reset_count > 0:
        return TrackerHealth.WARNING
    if connected is None and reset_count is None:
        return TrackerHealth.UNKNOWN
    return TrackerHealth.GOOD


def score_label(score: int | None) -> str:
    if score is None:
        return "GRAY"
    if score >= 85:
        return "GREEN"
    if score >= 60:
        return "YELLOW"
    return "RED"
