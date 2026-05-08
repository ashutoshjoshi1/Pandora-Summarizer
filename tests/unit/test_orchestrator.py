from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from pandora_summarizer.config import load_config
from pandora_summarizer.orchestrator import Orchestrator
from pandora_summarizer.state import RunStatus, StateDB


def _touch_with_mtime(p: Path, when: date) -> None:
    p.write_text("data")
    ts = __import__("datetime").datetime.combine(
        when, __import__("datetime").time(12, 0)
    ).timestamp()
    os.utime(p, (ts, ts))


def test_dry_run_partial_when_l0_missing(tmp_config: Path) -> None:
    cfg = load_config(tmp_config)
    db = StateDB(cfg.state.db_path)
    orch = Orchestrator(cfg, db, dry_run=True)
    status = orch.run_for(date(2026, 5, 1))
    # No L0 file, locate_l0 fails -> overall PARTIAL
    assert status == RunStatus.PARTIAL


def test_dry_run_completed_with_inputs(tmp_config: Path) -> None:
    cfg = load_config(tmp_config)
    target = date(2026, 5, 1)
    # Place an L0, an alignment, and a figure with the right mtime.
    l0 = cfg.paths.l0_dir / "Pandora100s1_X_20260501.txt"
    l0.write_text("# header\n1 2 3\n4 5 6\n")
    align = cfg.paths.alignment_dir / "alignment.dat"
    _touch_with_mtime(align, target)
    fig = cfg.paths.blick_figures_dir / "fig_001.png"
    _touch_with_mtime(fig, target)

    db = StateDB(cfg.state.db_path)
    orch = Orchestrator(cfg, db, dry_run=True)
    status = orch.run_for(target)
    assert status == RunStatus.COMPLETED

    rec = db.get_run("Pan100", target)
    assert rec is not None
    assert rec.status == RunStatus.COMPLETED
    assert rec.gcs_prefix == "Pan100/2026-05-01"

    steps = db.steps_for("Pan100", target, rec.attempt)
    names = [s.step_name for s in steps]
    assert "locate_l0" in names
    assert "collect_alignment" in names
    assert "collect_figures" in names
    assert "upload_gcs" in names
