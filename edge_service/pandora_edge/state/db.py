"""SQLite-backed persistence for runs, steps, and artifacts."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

from .models import ArtifactRecord, DailyRunRecord, RunStatus, StepLog, StepStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_runs (
    instrument_id    TEXT NOT NULL,
    date_utc         TEXT NOT NULL,
    status           TEXT NOT NULL,
    attempt          INTEGER NOT NULL,
    started_at_utc   TEXT NOT NULL,
    finished_at_utc  TEXT,
    gcs_prefix       TEXT NOT NULL,
    health_score     INTEGER,
    health_label     TEXT,
    PRIMARY KEY (instrument_id, date_utc)
);
CREATE TABLE IF NOT EXISTS step_logs (
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
CREATE INDEX IF NOT EXISTS idx_step_logs_run
    ON step_logs (instrument_id, date_utc, attempt);

CREATE TABLE IF NOT EXISTS artifacts (
    instrument_id    TEXT NOT NULL,
    date_utc         TEXT NOT NULL,
    kind             TEXT NOT NULL,
    filename         TEXT NOT NULL,
    size_bytes       INTEGER NOT NULL,
    sha256           TEXT,
    gcs_object_path  TEXT NOT NULL,
    PRIMARY KEY (instrument_id, date_utc, gcs_object_path)
);
"""


def _iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


def _parse_iso(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


class StateDB:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        self.close()

    # -- runs --------------------------------------------------------------

    def upsert_run(self, r: DailyRunRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO daily_runs (instrument_id, date_utc, status, attempt,
                                    started_at_utc, finished_at_utc, gcs_prefix,
                                    health_score, health_label)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(instrument_id, date_utc) DO UPDATE SET
                status=excluded.status,
                attempt=excluded.attempt,
                started_at_utc=excluded.started_at_utc,
                finished_at_utc=excluded.finished_at_utc,
                gcs_prefix=excluded.gcs_prefix,
                health_score=excluded.health_score,
                health_label=excluded.health_label
            """,
            (
                r.instrument_id, r.date_utc.isoformat(), r.status.value, r.attempt,
                r.started_at_utc.isoformat(), _iso(r.finished_at_utc), r.gcs_prefix,
                r.health_score, r.health_label,
            ),
        )
        self._conn.commit()

    def get_run(self, instrument_id: str, d: date) -> DailyRunRecord | None:
        row = self._conn.execute(
            "SELECT * FROM daily_runs WHERE instrument_id=? AND date_utc=?",
            (instrument_id, d.isoformat()),
        ).fetchone()
        if not row:
            return None
        finished = _parse_iso(row["finished_at_utc"])
        started = _parse_iso(row["started_at_utc"])
        assert started is not None  # started_at is NOT NULL in schema
        return DailyRunRecord(
            instrument_id=row["instrument_id"],
            date_utc=date.fromisoformat(row["date_utc"]),
            status=RunStatus(row["status"]),
            attempt=row["attempt"],
            started_at_utc=started,
            finished_at_utc=finished,
            gcs_prefix=row["gcs_prefix"],
            health_score=row["health_score"],
            health_label=row["health_label"],
        )

    # -- steps -------------------------------------------------------------

    def append_step(self, s: StepLog) -> None:
        self._conn.execute(
            """
            INSERT INTO step_logs (instrument_id, date_utc, attempt, step_name,
                                   status, duration_ms, error_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                s.instrument_id, s.date_utc.isoformat(), s.attempt, s.step_name,
                s.status.value, s.duration_ms, s.error_text,
            ),
        )
        self._conn.commit()

    def list_steps(self, instrument_id: str, d: date, attempt: int) -> list[StepLog]:
        rows = self._conn.execute(
            """
            SELECT * FROM step_logs
            WHERE instrument_id=? AND date_utc=? AND attempt=?
            ORDER BY id ASC
            """,
            (instrument_id, d.isoformat(), attempt),
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

    # -- artifacts ---------------------------------------------------------

    def upsert_artifact(self, a: ArtifactRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO artifacts (instrument_id, date_utc, kind, filename,
                                   size_bytes, sha256, gcs_object_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(instrument_id, date_utc, gcs_object_path) DO UPDATE SET
                kind=excluded.kind,
                filename=excluded.filename,
                size_bytes=excluded.size_bytes,
                sha256=excluded.sha256
            """,
            (
                a.instrument_id, a.date_utc.isoformat(), a.kind, a.filename,
                a.size_bytes, a.sha256, a.gcs_object_path,
            ),
        )
        self._conn.commit()
