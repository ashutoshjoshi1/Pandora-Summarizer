"""State records for SQLite persistence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class RunStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class StepStatus(str, Enum):
    OK = "OK"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class DailyRunRecord:
    instrument_id: str
    date_utc: date
    status: RunStatus
    attempt: int
    started_at_utc: datetime
    finished_at_utc: datetime | None
    gcs_prefix: str
    health_score: int | None = None
    health_label: str | None = None


@dataclass(frozen=True)
class StepLog:
    instrument_id: str
    date_utc: date
    attempt: int
    step_name: str
    status: StepStatus
    duration_ms: int
    error_text: str | None


@dataclass(frozen=True)
class ArtifactRecord:
    instrument_id: str
    date_utc: date
    kind: str
    filename: str
    size_bytes: int
    sha256: str | None
    gcs_object_path: str
