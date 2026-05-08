from __future__ import annotations

import re
from datetime import date
from pathlib import Path


# L0 filename convention is unconfirmed (see DESIGN.md open question #1).
# We accept any file whose name contains the date in YYYYMMDD form, which
# matches the typical Pandonia L0 pattern e.g. Pandora100s1_..._20260501.txt.
_DATE_RE = re.compile(r"(\d{8})")


def locate_l0(l0_dir: Path, target_date: date) -> Path | None:
    if not l0_dir.exists():
        return None

    stamp = target_date.strftime("%Y%m%d")
    candidates: list[Path] = []
    for p in l0_dir.iterdir():
        if not p.is_file():
            continue
        m = _DATE_RE.search(p.name)
        if m and m.group(1) == stamp:
            candidates.append(p)

    if not candidates:
        return None
    # If multiple match (e.g. .txt and .bak), prefer the largest.
    return max(candidates, key=lambda p: p.stat().st_size)
