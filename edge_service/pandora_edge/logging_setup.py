"""Structured logging setup with rotation."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_dir: Path, level: str = "INFO", rotate_mb: int = 25,
                      keep_files: int = 14) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "pandora-edge.log"

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s :: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    root = logging.getLogger()
    root.setLevel(level.upper())
    # Clear any prior handlers (e.g. when re-invoked in tests).
    for h in list(root.handlers):
        root.removeHandler(h)

    fh = RotatingFileHandler(
        log_file, maxBytes=rotate_mb * 1024 * 1024, backupCount=keep_files, encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)
