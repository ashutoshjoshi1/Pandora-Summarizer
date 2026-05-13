"""Step: parse L0 + partial-L0/status files."""
from __future__ import annotations

from ..parsers import FileInventory, L0Info, parse_l0_files


def parse_l0_status(inventory: FileInventory) -> L0Info:
    return parse_l0_files(inventory.l0, inventory.partial_l0)
