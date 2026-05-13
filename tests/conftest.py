"""Shared pytest fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

# Make the edge_service/ package layout importable without `pip install -e .`.
ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "edge_service"
for p in (str(EDGE), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)
