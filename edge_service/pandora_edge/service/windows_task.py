"""Thin wrappers around Windows `schtasks` for install / uninstall.

We deliberately avoid pywin32 here so the basic install path works in stock
Python. The full PowerShell installer lives at service/install.ps1 (Phase 6).
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

TASK_NAME = "PandoraEdgeService"


def _schtasks_available() -> str | None:
    return shutil.which("schtasks")


def install_task(
    *, config_path: Path, run_time_hhmm: str = "06:00",
    task_name: str = TASK_NAME,
) -> int:
    """Create a Windows Scheduled Task that runs `pandora-edge run` daily."""
    schtasks = _schtasks_available()
    if not schtasks:
        log.error("schtasks.exe not found - are you on Windows?")
        return 1

    python_exe = sys.executable
    # Use `-m pandora_edge run` so the entrypoint works regardless of script shims.
    tr = (
        f'"{python_exe}" -m pandora_edge run --config "{config_path}"'
    )
    cmd = [
        schtasks, "/Create", "/TN", task_name,
        "/SC", "DAILY", "/ST", run_time_hhmm,
        "/RL", "HIGHEST",
        "/F",  # overwrite if already exists
        "/TR", tr,
    ]
    log.info("creating scheduled task: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
    if proc.returncode != 0:
        log.error("schtasks failed: %s", proc.stderr.strip())
    else:
        log.info("scheduled task %s created", task_name)
    return proc.returncode


def uninstall_task(*, task_name: str = TASK_NAME) -> int:
    schtasks = _schtasks_available()
    if not schtasks:
        log.error("schtasks.exe not found - are you on Windows?")
        return 1
    cmd = [schtasks, "/Delete", "/TN", task_name, "/F"]
    proc = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
    if proc.returncode != 0:
        log.error("schtasks delete failed: %s", proc.stderr.strip())
    else:
        log.info("scheduled task %s removed", task_name)
    return proc.returncode
