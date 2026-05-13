"""Step: parse oslog/fslog/pslog files."""
from __future__ import annotations

from ..parsers import FileInventory, LogRollup, parse_log_files


def parse_logs(inventory: FileInventory) -> LogRollup:
    return parse_log_files(
        oslog=inventory.oslog,
        fslog=inventory.fslog,
        pslog=inventory.pslog,
    )
