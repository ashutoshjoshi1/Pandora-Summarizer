from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from ..parsers.l0_parser import L0Summary, parse_l0
from ..version import __version__


@dataclass
class StepStatusEntry:
    name: str
    status: str
    duration_ms: int
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_block(path: Path | None, *, with_hash: bool = True) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"filename": None, "size_bytes": 0}
    block: dict[str, Any] = {
        "filename": path.name,
        "size_bytes": path.stat().st_size,
    }
    if with_hash:
        block["sha256"] = _sha256(path)
    return block


def build_summary(
    *,
    instrument_id: str,
    target_date: date,
    l0_path: Path | None,
    l1_path: Path | None,
    alignment_path: Path | None,
    figures: list[Path],
    overall_status: str,
    attempt: int,
    started_at: datetime,
    finished_at: datetime,
    steps: list[StepStatusEntry],
    blickp_version: str | None = None,
) -> dict[str, Any]:
    l0_summary: L0Summary | None = None
    if l0_path is not None and l0_path.exists():
        try:
            l0_summary = parse_l0(l0_path)
        except Exception as e:  # noqa: BLE001 — surfaced via service_status
            steps.append(
                StepStatusEntry(
                    name="parse_l0_summary", status="FAILED",
                    duration_ms=0, error=str(e),
                )
            )

    l0_block = _file_block(l0_path)
    if l0_summary is not None:
        l0_block.update(
            {
                "record_count": l0_summary.record_count,
                "first_timestamp_utc": (
                    l0_summary.first_timestamp_utc.isoformat()
                    if l0_summary.first_timestamp_utc else None
                ),
                "last_timestamp_utc": (
                    l0_summary.last_timestamp_utc.isoformat()
                    if l0_summary.last_timestamp_utc else None
                ),
                "qc": l0_summary.qc,
            }
        )

    return {
        "schema_version": "1.0",
        "instrument_id": instrument_id,
        "date_utc": target_date.isoformat(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": {
            "hostname": platform.node(),
            "os": f"{platform.system()} {platform.release()}",
            "summarizer_version": __version__,
            "blickp_version": blickp_version,
        },
        "l0": l0_block,
        "l1": {**_file_block(l1_path, with_hash=False), "generated": l1_path is not None},
        "alignment": _file_block(alignment_path, with_hash=False),
        "figures": {
            "count": len(figures),
            "total_bytes": sum(f.stat().st_size for f in figures if f.exists()),
        },
        "service_status": {
            "overall": overall_status,
            "attempt": attempt,
            "duration_seconds": int((finished_at - started_at).total_seconds()),
            "steps": [asdict(s) for s in steps],
            "errors": [s.error for s in steps if s.error],
        },
    }


def write_summary(summary: dict[str, Any], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return dest
