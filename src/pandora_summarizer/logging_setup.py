from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from .config import LoggingConfig


def configure_logging(cfg: LoggingConfig) -> None:
    cfg.dir.mkdir(parents=True, exist_ok=True)
    log_file = cfg.dir / "pandora_summarizer.log"

    handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=cfg.rotate_mb * 1024 * 1024,
        backupCount=cfg.keep_files,
        encoding="utf-8",
    )
    fmt = logging.Formatter(
        '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)r}'
    )
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(cfg.level)
    root.addHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s"))
    root.addHandler(console)
