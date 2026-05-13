from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from pandora_summarizer.state import (
    DailyRunRecord,
    RunStatus,
    StateDB,
    StepLog,
    StepStatus,
)


def test_run_upsert_and_fetch(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "s.db")
    rec = DailyRunRecord(
        instrument_id="Pan100",
        date_utc=date(2026, 5, 1),
        status=RunStatus.IN_PROGRESS,
        attempt=1,
        started_at_utc=datetime.now(timezone.utc),
        finished_at_utc=None,
        gcs_prefix="Pan100/2026-05-01",
    )
    db.upsert_run(rec)
    got = db.get_run("Pan100", date(2026, 5, 1))
    assert got is not None
    assert got.status == RunStatus.IN_PROGRESS
    assert got.attempt == 1

    rec_done = DailyRunRecord(**{**rec.__dict__, "status": RunStatus.COMPLETED, "attempt": 2})
    db.upsert_run(rec_done)
    got = db.get_run("Pan100", date(2026, 5, 1))
    assert got is not None
    assert got.status == RunStatus.COMPLETED
    assert got.attempt == 2


def test_step_log_append_and_query(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "s.db")
    d = date(2026, 5, 1)
    for name in ("locate_l0", "generate_l1"):
        db.append_step(StepLog(
            instrument_id="Pan100", date_utc=d, attempt=1,
            step_name=name, status=StepStatus.OK, duration_ms=10,
        ))
    rows = db.steps_for("Pan100", d, 1)
    assert [r.step_name for r in rows] == ["locate_l0", "generate_l1"]
