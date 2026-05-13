from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from pandora_edge.state import (
    ArtifactRecord,
    DailyRunRecord,
    RunStatus,
    StateDB,
    StepLog,
    StepStatus,
)


def test_upsert_get_run_roundtrip(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "state.db")
    now = datetime.now(timezone.utc)
    db.upsert_run(DailyRunRecord(
        instrument_id="Pandora024", date_utc=date(2026, 5, 12),
        status=RunStatus.IN_PROGRESS, attempt=1,
        started_at_utc=now, finished_at_utc=None,
        gcs_prefix="prefix/Pandora024/2026-05-12",
        health_score=None, health_label=None,
    ))
    got = db.get_run("Pandora024", date(2026, 5, 12))
    assert got is not None
    assert got.status == RunStatus.IN_PROGRESS
    assert got.attempt == 1

    db.upsert_run(DailyRunRecord(
        instrument_id="Pandora024", date_utc=date(2026, 5, 12),
        status=RunStatus.COMPLETED, attempt=2,
        started_at_utc=now, finished_at_utc=now,
        gcs_prefix="prefix/Pandora024/2026-05-12",
        health_score=95, health_label="GREEN",
    ))
    got = db.get_run("Pandora024", date(2026, 5, 12))
    assert got is not None
    assert got.status == RunStatus.COMPLETED
    assert got.attempt == 2
    assert got.health_score == 95


def test_step_log_append_and_list(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "state.db")
    db.append_step(StepLog(
        instrument_id="P1", date_utc=date(2026, 5, 12), attempt=1,
        step_name="locate_files", status=StepStatus.OK,
        duration_ms=12, error_text=None,
    ))
    db.append_step(StepLog(
        instrument_id="P1", date_utc=date(2026, 5, 12), attempt=1,
        step_name="parse_logs", status=StepStatus.FAILED,
        duration_ms=5, error_text="boom",
    ))
    steps = db.list_steps("P1", date(2026, 5, 12), 1)
    assert [s.step_name for s in steps] == ["locate_files", "parse_logs"]
    assert steps[-1].status == StepStatus.FAILED


def test_artifact_upsert_is_idempotent(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "state.db")
    rec = ArtifactRecord(
        instrument_id="P1", date_utc=date(2026, 5, 12),
        kind="L0", filename="L0.txt", size_bytes=100, sha256=None,
        gcs_object_path="prefix/data/L0.txt",
    )
    db.upsert_artifact(rec)
    db.upsert_artifact(rec)  # should not duplicate
