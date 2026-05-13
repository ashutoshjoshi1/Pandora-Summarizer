"""Step: locate Blick files for the target date."""
from __future__ import annotations

from datetime import date

from ..config import Config
from ..parsers import FileInventory, build_inventory


def locate_files(cfg: Config, target_date: date) -> FileInventory:
    return build_inventory(
        target_date=target_date,
        l0_dir=cfg.paths.l0_dir,
        tmp_dir=cfg.paths.tmp_dir,
        alignment_dir=cfg.paths.alignment_dir,
        figures_dir=cfg.paths.figures_dir,
        oslog_dir=cfg.paths.oslog_dir,
        fslog_dir=cfg.paths.fslog_dir,
        pslog_dir=cfg.paths.pslog_dir,
        stability_seconds=cfg.service.file_stability_seconds,
    )
