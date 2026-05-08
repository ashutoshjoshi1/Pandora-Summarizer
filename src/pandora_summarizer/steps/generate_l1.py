from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


class L1GenerationError(RuntimeError):
    pass


def generate_l1(blickp_exe: Path, l0_path: Path, l1_out_dir: Path) -> Path:
    """
    Invoke BlickP to produce an L1 file from an L0 file.

    NOTE (DESIGN.md open question #1): the exact BlickP CLI is unconfirmed.
    The placeholder below assumes:
        BlickP.exe --l0 <path> --out <dir> --mode L1
    Replace once the actual invocation is known. The function should still
    return the resulting L1 file path or raise L1GenerationError.
    """
    if not blickp_exe.exists():
        raise L1GenerationError(f"BlickP executable not found: {blickp_exe}")
    if not l0_path.exists():
        raise L1GenerationError(f"L0 file not found: {l0_path}")
    l1_out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(blickp_exe),
        "--l0", str(l0_path),
        "--out", str(l1_out_dir),
        "--mode", "L1",
    ]
    log.info("invoking BlickP: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60 * 30, check=False
        )
    except FileNotFoundError as e:
        raise L1GenerationError(str(e)) from e

    if proc.returncode != 0:
        raise L1GenerationError(
            f"BlickP exited {proc.returncode}: {proc.stderr.strip()[:500]}"
        )

    # Heuristic: pick the newest file in l1_out_dir whose name contains the
    # L0 stem. Replace once we know BlickP's real output naming.
    stem = l0_path.stem
    candidates = [
        p for p in l1_out_dir.iterdir() if p.is_file() and stem in p.name
    ]
    if not candidates:
        raise L1GenerationError(
            f"BlickP succeeded but no L1 output found in {l1_out_dir}"
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)
