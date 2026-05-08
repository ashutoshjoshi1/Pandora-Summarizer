from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

_FIGURE_EXTS = {".png", ".jpg", ".jpeg", ".pdf", ".svg"}


def collect_figures(figures_dir: Path, target_date: date) -> list[Path]:
    """
    Collect figure files produced for `target_date`.

    Selection rule: any file under `figures_dir` (recursive) with a known
    extension whose mtime falls within target_date (instrument-local
    interpretation handled upstream — caller passes the right date).
    """
    if not figures_dir.exists():
        return []

    start = datetime.combine(target_date, time.min).timestamp()
    end = datetime.combine(target_date, time.max).timestamp()

    out: list[Path] = []
    for p in figures_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in _FIGURE_EXTS:
            continue
        m = p.stat().st_mtime
        if start <= m <= end:
            out.append(p)
    return sorted(out)
