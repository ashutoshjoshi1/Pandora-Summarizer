from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path

from pandora_edge.parsers.file_inventory_parser import build_inventory


def _make(path: Path, content: str = "x", age_seconds: float = 600) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    old = time.time() - age_seconds
    os.utime(path, (old, old))
    return path


def test_finds_dated_files_and_groups_them(tmp_path: Path) -> None:
    target = date(2026, 5, 12)
    ymd = "20260512"
    _make(tmp_path / "L0" / f"L0_{ymd}.txt")
    _make(tmp_path / "L0" / f"partial_{ymd}.txt")
    _make(tmp_path / "oslog" / f"os_{ymd}.txt")
    _make(tmp_path / "align" / f"align_{ymd}.txt")
    _make(tmp_path / "figs" / f"plot_{ymd}.png")
    _make(tmp_path / "L0" / "L0_20260513.txt")  # different date — should be ignored

    inv = build_inventory(
        target_date=target,
        l0_dir=tmp_path / "L0", tmp_dir=None,
        alignment_dir=tmp_path / "align", figures_dir=tmp_path / "figs",
        oslog_dir=tmp_path / "oslog",
        fslog_dir=tmp_path / "fslog",
        pslog_dir=tmp_path / "pslog",
        stability_seconds=1,
    )
    assert len(inv.l0) == 1
    assert len(inv.partial_l0) == 1
    assert len(inv.oslog) == 1
    assert len(inv.alignment) == 1
    assert len(inv.figures) == 1


def test_stability_window_skips_recent_files(tmp_path: Path) -> None:
    target = date(2026, 5, 12)
    fresh = _make(tmp_path / "L0" / "L0_20260512.txt", age_seconds=0.0)
    inv = build_inventory(
        target_date=target,
        l0_dir=tmp_path / "L0", tmp_dir=None,
        alignment_dir=None, figures_dir=None,
        oslog_dir=None, fslog_dir=None, pslog_dir=None,
        stability_seconds=120,
    )
    assert fresh in inv.skipped_unstable
    assert inv.l0 == []


def test_missing_directories_do_not_raise(tmp_path: Path) -> None:
    target = date(2026, 5, 12)
    inv = build_inventory(
        target_date=target,
        l0_dir=tmp_path / "missing", tmp_dir=None,
        alignment_dir=tmp_path / "also-missing",
        figures_dir=None,
        oslog_dir=None, fslog_dir=None, pslog_dir=None,
        stability_seconds=1,
    )
    assert inv.l0 == []
    assert inv.alignment == []
