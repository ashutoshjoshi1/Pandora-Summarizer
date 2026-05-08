from __future__ import annotations

from datetime import date
from pathlib import Path


def collect_alignment(alignment_dir: Path, target_date: date) -> Path | None:
    """
    Find the alignment file applicable for `target_date`.

    DESIGN.md open question #4: alignment cadence. For now we pick the most
    recent alignment file with mtime <= end-of-target-date. Adjust once cadence
    is confirmed (daily file vs. only-when-changed).
    """
    if not alignment_dir.exists():
        return None

    cutoff = (
        date(target_date.year, target_date.month, target_date.day)
    )  # date object; comparison via mtime done below
    end_of_day = (
        __import__("datetime").datetime.combine(
            cutoff, __import__("datetime").time(23, 59, 59)
        ).timestamp()
    )

    candidates = [p for p in alignment_dir.iterdir() if p.is_file()]
    eligible = [p for p in candidates if p.stat().st_mtime <= end_of_day]
    if not eligible:
        return None
    return max(eligible, key=lambda p: p.stat().st_mtime)
