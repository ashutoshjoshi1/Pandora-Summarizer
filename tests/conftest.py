from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest


@pytest.fixture()
def tmp_config(tmp_path: Path) -> Path:
    """Build a working config rooted at tmp_path with empty input dirs."""
    l0 = tmp_path / "l0"; l0.mkdir()
    l1 = tmp_path / "l1"; l1.mkdir()
    align = tmp_path / "alignment"; align.mkdir()
    figs = tmp_path / "figures"; figs.mkdir()
    blickp = tmp_path / "fake_blickp.exe"
    blickp.write_text("placeholder")
    logs = tmp_path / "logs"
    state_db = tmp_path / "state.db"

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(dedent(f"""
        instrument:
          id: Pan100
          timezone: UTC
        paths:
          l0_dir: {l0}
          l1_out_dir: {l1}
          alignment_dir: {align}
          blick_figures_dir: {figs}
          blickp_exe: {blickp}
        gcs:
          bucket: test-bucket
          overwrite_existing: true
        logging:
          dir: {logs}
          level: INFO
        state:
          db_path: {state_db}
    """).strip(), encoding="utf-8")
    return cfg_path
