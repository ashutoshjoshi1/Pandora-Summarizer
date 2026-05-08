from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from .models import ArtifactRecord, DailyRunRecord, RunStatus, StepLog, StepStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_run (
    instrument_id     TEXT NOT NULL,
    date_utc          TEXT NOT NULL,
    status            TEXT NOT NULL,
    attempt           INTEGER NOT NULL DEFAULT 0,
    started_at_utc    TEXT,
    finished_at_utc   TEXT,
    gcs_prefix        TEXT,
    PRIMARY KEY (instrument_id, date_utc)
);

CREATE TABLE IF NOT EXISTS artifact (
    instrument_id    TEXT NOT NULL,
    date_utc         TEXT NOT NULL,
    kind             TEXT NOT NULL,
    filename         TEXT NOT NULL,
    size_bytes       INTEGER NOT NULL,
    sha256           TEXT,
    gcs_object_path  TEXT,
    PRIMARY KEY (instrument_id, date_utc, kind, filename)
);

CREATE TABLE IF NOT EXISTS step_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id    TEXT NOT NULL,
    date_utc         TEXT NOT NULL,
    attempt          INTEGER NOT NULL,
    step_name        TEXT NOT NULL,
    status           TEXT NOT NULL,
    duration_ms      INTEGER NOT NULL,
    error_text       TEXT,
    created_at_utc   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_step_log_run
    ON step_log(instrument_id, date_utc, attempt);
"""


class StateDB:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- daily_run ---------------------------------------------------------

    def upsert_run(self, run: DailyRunRecord) -> None:
        with self._connect() as c:
            c.execute(
                """
                INSERT INTO daily_run
                    (instrument_id, date_utc, status, attempt,
                     started_at_utc, finished_at_utc, gcs_prefix)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(instrument_id, date_utc) DO UPDATE SET
                    status          = excluded.status,
                    attempt         = excluded.attempt,
                    started_at_utc  = excluded.started_at_utc,
                    finished_at_utc = excluded.finished_at_utc,
                    gcs_prefix      = excluded.gcs_prefix
                """,
                (
                    run.instrument_id,
                    run.date_utc.isoformat(),
                    run.status.value,
                    run.attempt,
                    run.started_at_utc.isoformat() if run.started_at_utc else None,
                    run.finished_at_utc.isoformat() if run.finished_at_utc else None,
                    run.gcs_prefix,
                ),
            )

    def get_run(self, instrument_id: str, date_utc: date) -> DailyRunRecord | None:
        with self._connect() as c:
            row = c.execute(
                "SELECT * FROM daily_run WHERE instrument_id = ? AND date_utc = ?",
                (instrument_id, date_utc.isoformat()),
            ).fetchone()
        if row is None:
            return None
        return DailyRunRecord(
            instrument_id=row["instrument_id"],
            date_utc=date.fromisoformat(row["date_utc"]),
            status=RunStatus(row["status"]),
            attempt=row["attempt"],
            started_at_utc=datetime.fromisoformat(row["started_at_utc"])
            if row["started_at_utc"]
            else None,
            finished_at_utc=datetime.fromisoformat(row["finished_at_utc"])
            if row["finished_at_utc"]
            else None,
            gcs_prefix=row["gcs_prefix"],
        )

    # --- artifacts ---------------------------------------------------------

    def upsert_artifact(self, art: ArtifactRecord) -> None:
        with self._connect() as c:
            c.execute(
                """
                INSERT INTO artifact
                    (instrument_id, date_utc, kind, filename,
                     size_bytes, sha256, gcs_object_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(instrument_id, date_utc, kind, filename) DO UPDATE SET
                    size_bytes      = excluded.size_bytes,
                    sha256          = excluded.sha256,
                    gcs_object_path = excluded.gcs_object_path
                """,
                (
                    art.instrument_id,
                    art.date_utc.isoformat(),
                    art.kind,
                    art.filename,
                    art.size_bytes,
                    art.sha256,
                    art.gcs_object_path,
                ),
            )

    # --- step log ----------------------------------------------------------

    def append_step(self, step: StepLog) -> None:
        with self._connect() as c:
            c.execute(
                """
                INSERT INTO step_log
                    (instrument_id, date_utc, attempt, step_name,
                     status, duration_ms, error_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step.instrument_id,
                    step.date_utc.isoformat(),
                    step.attempt,
                    step.step_name,
                    step.status.value,
                    step.duration_ms,
                    step.error_text,
                ),
            )

    def steps_for(
        self, instrument_id: str, date_utc: date, attempt: int
    ) -> list[StepLog]:
        with self._connect() as c:
            rows = c.execute(
                """
                SELECT instrument_id, date_utc, attempt, step_name,
                       status, duration_ms, error_text
                FROM step_log
                WHERE instrument_id = ? AND date_utc = ? AND attempt = ?
                ORDER BY id ASC
                """,
                (instrument_id, date_utc.isoformat(), attempt),
            ).fetchall()
        return [
            StepLog(
                instrument_id=r["instrument_id"],
                date_utc=date.fromisoformat(r["date_utc"]),
                attempt=r["attempt"],
                step_name=r["step_name"],
                status=StepStatus(r["status"]),
                duration_ms=r["duration_ms"],
                error_text=r["error_text"],
            )
            for r in rows
        ]
