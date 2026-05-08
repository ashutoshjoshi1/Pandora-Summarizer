from __future__ import annotations

from pathlib import Path

import pytest

from pandora_summarizer.config import load_config


def test_load_valid_config(tmp_config: Path) -> None:
    cfg = load_config(tmp_config)
    assert cfg.instrument.id == "Pan100"
    assert cfg.gcs.bucket == "test-bucket"
    assert cfg.retry.max_attempts == 3  # default


def test_invalid_instrument_id_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "config.yaml"
    bad.write_text(
        "instrument:\n"
        "  id: NotAPandora\n"
        "  timezone: UTC\n"
        "paths:\n"
        f"  l0_dir: {tmp_path}\n"
        f"  l1_out_dir: {tmp_path}\n"
        f"  alignment_dir: {tmp_path}\n"
        f"  blick_figures_dir: {tmp_path}\n"
        f"  blickp_exe: {tmp_path}/x\n"
        "gcs:\n  bucket: b\n"
        f"logging:\n  dir: {tmp_path}\n"
        f"state:\n  db_path: {tmp_path}/s.db\n"
    )
    with pytest.raises(Exception):
        load_config(bad)
