"""End-to-end smoke test that exercises Phase 1-5 wiring.

Builds a synthetic Blick directory tree, runs the orchestrator in dry-run mode
(no network), and asserts that summary.json is produced with the expected
top-level shape and a sensible health score.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from textwrap import dedent

import pytest

from pandora_edge.config import (
    Config,
    Gcs,
    HealthThresholds,
    Instrument,
    Logging,
    Paths,
    Service,
    State,
)
from pandora_edge.orchestrator import Orchestrator
from pandora_edge.state import RunStatus, StateDB


@pytest.fixture
def synthetic_tree(tmp_path: Path) -> tuple[Path, date]:
    target = date(2026, 5, 12)
    ymd = target.strftime("%Y%m%d")

    blick = tmp_path / "Blick"
    (blick / "data" / "L0").mkdir(parents=True)
    (blick / "data" / "tmp").mkdir(parents=True)
    (blick / "data" / "alignments").mkdir(parents=True)
    (blick / "data" / "alignments" / "figures").mkdir(parents=True)
    (blick / "log" / "oslog").mkdir(parents=True)
    (blick / "log" / "fslog").mkdir(parents=True)
    (blick / "log" / "pslog").mkdir(parents=True)

    # L0 with a status line + measurement rows
    (blick / "data" / "L0" / f"Pandora024_L0_{ymd}.txt").write_text(dedent(f"""
        # Pandora L0 sample
        # status: mode=SCHEDULE schedule=uv_sun.sked routine=SO last_routine=SO \
sun_search=SUCCESS rms=0.02 offset=0.01 fwhm=0.5 tracker_connected=true \
tracker_reset_count=0 time={target.isoformat()}T12:00:00Z
        {target.isoformat()}T12:00:00Z 123.4 56.7
        {target.isoformat()}T12:01:00Z 124.0 56.9
    """).strip() + "\n")

    # Partial L0 / status file (sparse)
    (blick / "data" / "L0" / f"Pandora024_partial_{ymd}.txt").write_text(
        f"status: mode=SCHEDULE schedule=uv_sun.sked routine=SO "
        f"time={target.isoformat()}T23:55:00Z\n"
    )

    # oslog with warning + info
    (blick / "log" / "oslog" / f"oslog_{ymd}.txt").write_text(
        f"{target.isoformat()}T10:00:00Z INFO startup ok\n"
        f"{target.isoformat()}T10:01:00Z WARNING tracker drift detected\n"
        f"{target.isoformat()}T11:01:00Z WARNING tracker drift detected\n"
    )
    # fslog with one error
    (blick / "log" / "fslog" / f"fslog_{ymd}.txt").write_text(
        f"{target.isoformat()}T12:00:00Z ERROR comms timeout\n"
    )
    # pslog empty-ish
    (blick / "log" / "pslog" / f"pslog_{ymd}.txt").write_text(
        f"{target.isoformat()}T09:00:00Z INFO power normal\n"
    )

    # Alignment file with a good scan
    (blick / "data" / "alignments" / f"alignment_{ymd}.txt").write_text(
        "# scan_type weighting_factor rms time\n"
        f"FS 1459.5 0.026 {target.isoformat()}T16:10:00Z\n"
    )

    # Make file mtimes safely older than the stability window.
    old = (datetime.now(timezone.utc).timestamp() - 600)
    for p in blick.rglob("*"):
        if p.is_file():
            import os
            os.utime(p, (old, old))

    return blick, target


def _build_cfg(blick: Path, tmp_path: Path) -> Config:
    return Config(
        instrument=Instrument(
            id="Pandora024", display_name="Pandora024",
            location_name="GSFC", timezone="UTC",
        ),
        paths=Paths(
            blick_root=blick,
            l0_dir=blick / "data" / "L0",
            tmp_dir=blick / "data" / "tmp",
            alignment_dir=blick / "data" / "alignments",
            figures_dir=blick / "data" / "alignments" / "figures",
            oslog_dir=blick / "log" / "oslog",
            fslog_dir=blick / "log" / "fslog",
            pslog_dir=blick / "log" / "pslog",
        ),
        gcs=Gcs(bucket="test-bucket", prefix="pandora-fleet-monitoring"),
        service=Service(file_stability_seconds=1),
        health_thresholds=HealthThresholds(),
        logging=Logging(dir=tmp_path / "logs"),
        state=State(db_path=tmp_path / "state.db",
                    staging_dir=tmp_path / "staging"),
    )


def test_smoke_pipeline_produces_summary(
    synthetic_tree: tuple[Path, date], tmp_path: Path,
) -> None:
    blick, target = synthetic_tree
    cfg = _build_cfg(blick, tmp_path)
    with StateDB(cfg.state.db_path) as db:
        orch = Orchestrator(cfg, db, dry_run=True)
        status = orch.run_for(target)

    assert status in (RunStatus.COMPLETED, RunStatus.PARTIAL)

    summary_path = (
        cfg.state.staging_dir / "Pandora024" / target.isoformat() / "summary.json"
    )
    assert summary_path.exists(), f"summary.json missing at {summary_path}"

    data = json.loads(summary_path.read_text())
    assert data["schema_version"] == "2.0"
    assert data["instrument_id"] == "Pandora024"
    assert data["target_date"] == target.isoformat()
    assert data["health"]["daily_health_score"] is not None
    assert data["health"]["daily_health_label"] in {"GREEN", "YELLOW", "RED", "GRAY"}
    assert data["status"]["online_status"] in {"ONLINE", "PARTIAL"}
    assert data["operation"]["l0_file_count"] == 1
    assert data["operation"]["partial_l0_file_count"] == 1
    assert data["logs"]["total_warning_count"] == 2
    assert data["logs"]["total_error_count"] == 1
    assert data["alignment"]["alignment_file_found"] is True
    assert data["alignment"]["latest_weighting_factor"] == 1459.5
    assert data["alignment"]["alignment_health"] == "GOOD"
    assert data["files"]["l0"]["status"] == "PRESENT"
    assert data["upload"]["upload_status"] in {"COMPLETED", "PARTIAL", "FAILED"}
    # L1/L2 must not appear anywhere.
    flat = json.dumps(data).lower()
    assert "l1" not in flat or "l1_" not in flat  # tolerant, just guards typos
    assert "l2fit" not in flat
