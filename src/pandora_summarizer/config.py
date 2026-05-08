from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class InstrumentConfig(BaseModel):
    id: str = Field(..., pattern=r"^Pan\d+[a-zA-Z0-9_-]*$")
    timezone: str = "UTC"


class PathsConfig(BaseModel):
    l0_dir: Path
    l1_out_dir: Path
    alignment_dir: Path
    blick_figures_dir: Path
    blickp_exe: Path


class ScheduleConfig(BaseModel):
    run_time_local: str = "02:00"
    process_lookback_days: int = 1


class GcsConfig(BaseModel):
    bucket: str
    service_account_json: Path | None = None
    overwrite_existing: bool = True


class RetryConfig(BaseModel):
    max_attempts: int = 3
    backoff_seconds: list[int] = [30, 120, 600]

    @field_validator("backoff_seconds")
    @classmethod
    def _non_empty(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("backoff_seconds must not be empty")
        return v


class LoggingConfig(BaseModel):
    dir: Path
    level: str = "INFO"
    rotate_mb: int = 25
    keep_files: int = 14


class StateConfig(BaseModel):
    db_path: Path


class Config(BaseModel):
    instrument: InstrumentConfig
    paths: PathsConfig
    schedule: ScheduleConfig = ScheduleConfig()
    gcs: GcsConfig
    retry: RetryConfig = RetryConfig()
    logging: LoggingConfig
    state: StateConfig


def load_config(path: str | Path) -> Config:
    text = Path(path).read_text(encoding="utf-8")
    raw: dict[str, Any] = yaml.safe_load(text) or {}
    return Config.model_validate(raw)
