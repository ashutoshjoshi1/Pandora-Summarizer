"""Configuration loading + validation via Pydantic."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class Instrument(BaseModel):
    id: str
    display_name: str | None = None
    location_name: str | None = None
    timezone: str = "UTC"


class Paths(BaseModel):
    blick_root: Path
    l0_dir: Path
    tmp_dir: Path | None = None
    alignment_dir: Path
    oslog_dir: Path
    fslog_dir: Path
    pslog_dir: Path
    figures_dir: Path
    config_dir: Path | None = None
    operationfiles_dir: Path | None = None
    routines_dir: Path | None = None
    schedules_dir: Path | None = None


class Gcs(BaseModel):
    bucket: str
    prefix: str = "pandora-fleet-monitoring"
    service_account_json: Path | None = None
    overwrite_existing: bool = True


class Service(BaseModel):
    run_time_local: str = "06:00"
    process_lookback_days: int = 1
    retry_attempts: int = 3
    upload_l0_files: bool = True
    upload_partial_l0_files: bool = True
    upload_logs: bool = True
    upload_alignment_files: bool = True
    upload_figures: bool = True
    file_stability_seconds: int = 60

    @field_validator("retry_attempts")
    @classmethod
    def _positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("retry_attempts must be >= 1")
        return v


class HealthThresholds(BaseModel):
    offline_hours_threshold: int = 24
    warning_count_yellow: int = 5
    warning_count_red: int = 20
    error_count_yellow: int = 1
    error_count_red: int = 5
    alignment_weighting_min_good: float = 500.0
    failed_sun_search_red: int = 3
    tracker_reset_red: int = 3


class Logging(BaseModel):
    dir: Path
    level: str = "INFO"
    rotate_mb: int = 25
    keep_files: int = 14


class State(BaseModel):
    db_path: Path
    staging_dir: Path | None = None


class Config(BaseModel):
    instrument: Instrument
    paths: Paths
    gcs: Gcs
    service: Service = Field(default_factory=Service)
    health_thresholds: HealthThresholds = Field(default_factory=HealthThresholds)
    logging: Logging
    state: State

    @classmethod
    def load(cls, path: Path | str) -> "Config":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config not found: {p}")
        with p.open("r", encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f)
        if not isinstance(raw, dict):
            raise ValueError(f"Config root must be a mapping, got {type(raw).__name__}")
        return cls.model_validate(raw)
