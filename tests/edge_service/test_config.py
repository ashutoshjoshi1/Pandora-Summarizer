from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pandora_edge.config import Config


def test_loads_example_config_successfully() -> None:
    cfg = Config.load(Path("config/config.example.yaml"))
    assert cfg.instrument.id == "Pandora024"
    assert cfg.gcs.bucket == "log_web"
    assert cfg.gcs.prefix == "pandora-fleet-monitoring"
    assert cfg.health_thresholds.alignment_weighting_min_good == 500
    assert cfg.service.process_lookback_days == 1


def test_missing_file_raises_clearly(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Config.load(tmp_path / "does-not-exist.yaml")


def test_invalid_yaml_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("paths: not_a_dict\n")
    with pytest.raises(ValidationError):
        Config.load(bad)


def test_invalid_retry_attempts_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "instrument: {id: P, timezone: UTC}\n"
        "paths: {blick_root: /, l0_dir: /, alignment_dir: /, oslog_dir: /,\n"
        "       fslog_dir: /, pslog_dir: /, figures_dir: /}\n"
        "gcs: {bucket: x}\n"
        "service: {retry_attempts: 0}\n"
        "logging: {dir: /tmp}\n"
        "state: {db_path: /tmp/x.db}\n",
    )
    with pytest.raises(ValidationError):
        Config.load(bad)
