"""Daily health score: deterministic deductions from a 100 baseline."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import HealthThresholds
from .rules import AlignmentLabel, OnlineStatus, TrackerHealth, score_label


@dataclass(frozen=True)
class HealthInputs:
    online: OnlineStatus
    has_l0: bool
    has_partial_l0: bool
    warning_count: int
    error_count: int
    alignment: AlignmentLabel
    tracker: TrackerHealth
    tracker_reset_count: int | None
    failed_sun_search_count: int | None
    upload_status: str  # COMPLETED | PARTIAL | FAILED


@dataclass
class HealthScore:
    score: int
    label: str
    breakdown: dict[str, int] = field(default_factory=dict)
    summary: str = ""


def score_health(
    inputs: HealthInputs,
    thresholds: HealthThresholds,
    *,
    instrument_label: str = "Pandora",
) -> HealthScore:
    breakdown: dict[str, int] = {"base": 100}

    breakdown["offline_penalty"] = 40 if inputs.online == OnlineStatus.OFFLINE else 0

    if not inputs.has_l0 and not inputs.has_partial_l0:
        breakdown["missing_l0_penalty"] = 25
    else:
        breakdown["missing_l0_penalty"] = 0

    if inputs.warning_count >= thresholds.warning_count_red:
        breakdown["warnings_penalty"] = 20
    elif inputs.warning_count >= thresholds.warning_count_yellow:
        breakdown["warnings_penalty"] = 10
    else:
        breakdown["warnings_penalty"] = 0

    if inputs.error_count >= thresholds.error_count_red:
        breakdown["errors_penalty"] = 25
    elif inputs.error_count >= thresholds.error_count_yellow:
        breakdown["errors_penalty"] = 15
    else:
        breakdown["errors_penalty"] = 0

    breakdown["alignment_penalty"] = (
        15 if inputs.alignment == AlignmentLabel.CRITICAL
        else 5 if inputs.alignment == AlignmentLabel.WARNING
        else 0
    )

    breakdown["tracker_penalty"] = (
        10 if (
            inputs.tracker == TrackerHealth.CRITICAL
            or (inputs.tracker_reset_count or 0) >= thresholds.tracker_reset_red
        )
        else 0
    )

    breakdown["sun_search_penalty"] = (
        10 if (inputs.failed_sun_search_count or 0) >= thresholds.failed_sun_search_red
        else 0
    )

    if inputs.upload_status == "FAILED":
        breakdown["upload_penalty"] = 20
    elif inputs.upload_status == "PARTIAL":
        breakdown["upload_penalty"] = 10
    else:
        breakdown["upload_penalty"] = 0

    total_penalty = sum(v for k, v in breakdown.items() if k != "base")
    raw = breakdown["base"] - total_penalty
    score = max(0, min(100, raw))
    label = (
        "GRAY" if inputs.online == OnlineStatus.UNKNOWN
        else score_label(score)
    )

    summary = _summarize(instrument_label, inputs, score, label)
    return HealthScore(score=score, label=label, breakdown=breakdown, summary=summary)


def _summarize(label_name: str, i: HealthInputs, score: int, score_label_str: str) -> str:
    parts: list[str] = [f"{label_name} score {score} ({score_label_str})."]
    if i.online == OnlineStatus.OFFLINE:
        parts.append("Instrument appears offline.")
    elif i.online == OnlineStatus.PARTIAL:
        parts.append("Partial data received.")
    if i.error_count:
        parts.append(f"{i.error_count} error(s) in logs.")
    if i.warning_count:
        parts.append(f"{i.warning_count} warning(s) in logs.")
    if i.alignment == AlignmentLabel.CRITICAL:
        parts.append("Alignment is critical.")
    elif i.alignment == AlignmentLabel.GOOD:
        parts.append("Alignment is good.")
    if i.upload_status != "COMPLETED":
        parts.append(f"Upload {i.upload_status.lower()}.")
    if len(parts) == 1:
        parts.append("Operated normally.")
    return " ".join(parts)
