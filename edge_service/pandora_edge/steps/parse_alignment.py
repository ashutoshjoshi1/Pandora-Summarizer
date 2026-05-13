"""Step: parse alignment files."""
from __future__ import annotations

from ..config import HealthThresholds
from ..parsers import AlignmentInfo, FileInventory, parse_alignment_files


def parse_alignment(
    inventory: FileInventory, thresholds: HealthThresholds,
) -> AlignmentInfo:
    return parse_alignment_files(
        inventory.alignment,
        min_good_weighting=thresholds.alignment_weighting_min_good,
    )
