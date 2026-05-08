from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class L0Summary:
    record_count: int
    first_timestamp_utc: datetime | None
    last_timestamp_utc: datetime | None
    qc: dict[str, Any] = field(default_factory=dict)


def parse_l0(path: Path) -> L0Summary:
    """
    Extract a lightweight summary from a Pandonia L0 file.

    Placeholder implementation: counts non-blank, non-comment lines and treats
    the result as record_count. Replace with a real parser once the L0 record
    format is finalized — should populate first/last timestamps and QC fields
    (missing minutes, saturated records, dark count mean) as described in
    DESIGN.md §6.
    """
    record_count = 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("*"):
                continue
            record_count += 1

    return L0Summary(
        record_count=record_count,
        first_timestamp_utc=None,
        last_timestamp_utc=None,
        qc={},
    )
