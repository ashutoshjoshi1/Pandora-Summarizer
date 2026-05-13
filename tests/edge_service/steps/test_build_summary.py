from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

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
from pandora_edge.gcs import UploadResult
from pandora_edge.parsers import AlignmentInfo, FileInventory, L0Info, LogRollup
from pandora_edge.steps.build_summary import SCHEMA_VERSION, build_summary


def _cfg(tmp_path: Path) -> Config:
    return Config(
        instrument=Instrument(id="P1", display_name="P1", timezone="UTC"),
        paths=Paths(
            blick_root=tmp_path, l0_dir=tmp_path,
            alignment_dir=tmp_path, oslog_dir=tmp_path,
            fslog_dir=tmp_path, pslog_dir=tmp_path,
            figures_dir=tmp_path,
        ),
        gcs=Gcs(bucket="b", prefix="pandora-fleet-monitoring"),
        service=Service(), health_thresholds=HealthThresholds(),
        logging=Logging(dir=tmp_path), state=State(db_path=tmp_path / "s.db"),
    )


def test_build_summary_has_all_required_sections(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    summary = build_summary(
        cfg=cfg, target_date=date(2026, 5, 12),
        inventory=FileInventory(target_date=date(2026, 5, 12)),
        l0=L0Info(), logs=LogRollup(), alignment=AlignmentInfo(),
        upload=UploadResult(status="COMPLETED"),
        upload_started_at_utc=None, upload_finished_at_utc=None,
        gcs_prefix="pandora-fleet-monitoring/P1/2026-05-12",
        attempt=1,
        started_at=datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 5, 13, 10, 2, tzinfo=timezone.utc),
        steps=[], service_errors=[],
    )
    assert summary["schema_version"] == SCHEMA_VERSION
    for section in (
        "host", "status", "operation", "logs", "tracker",
        "sun_search", "alignment", "files", "upload", "health",
        "service_status",
    ):
        assert section in summary, f"missing section {section}"
    assert summary["service_status"]["duration_seconds"] == 120
    assert summary["files"]["l0"]["status"] == "MISSING"
    # L1/L2 keys must never appear.
    flat = str(summary).lower()
    assert "l2fit" not in flat
    assert "/l1/" not in flat


def test_offline_when_no_data(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    summary = build_summary(
        cfg=cfg, target_date=date(2026, 5, 12),
        inventory=FileInventory(target_date=date(2026, 5, 12)),
        l0=L0Info(), logs=LogRollup(), alignment=AlignmentInfo(),
        upload=UploadResult(status="COMPLETED"),
        upload_started_at_utc=None, upload_finished_at_utc=None,
        gcs_prefix="x",
        attempt=1,
        started_at=datetime(2026, 5, 13, tzinfo=timezone.utc),
        finished_at=datetime(2026, 5, 13, tzinfo=timezone.utc),
        steps=[], service_errors=[],
    )
    assert summary["status"]["online_status"] in {"OFFLINE", "UNKNOWN"}
    assert summary["health"]["daily_health_label"] in {"GRAY", "RED"}
