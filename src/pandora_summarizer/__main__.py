from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .config import load_config
from .logging_setup import configure_logging
from .orchestrator import Orchestrator
from .state import StateDB
from .version import __version__


def _yesterday_in_tz(tz_name: str) -> date:
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        tz = timezone.utc
    return (datetime.now(tz) - timedelta(days=1)).date()


def _cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    configure_logging(cfg.logging)
    log = logging.getLogger("pandora_summarizer")

    target = (
        date.fromisoformat(args.date)
        if args.date else _yesterday_in_tz(cfg.instrument.timezone)
    )
    log.info("starting run for %s %s (dry_run=%s)",
             cfg.instrument.id, target, args.dry_run)

    db = StateDB(cfg.state.db_path)
    orch = Orchestrator(cfg, db, dry_run=args.dry_run)
    status = orch.run_for(target)
    log.info("done: %s", status.value)
    return 0 if status.value == "COMPLETED" else 2


def _cmd_status(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    db = StateDB(cfg.state.db_path)
    target = (
        date.fromisoformat(args.date)
        if args.date else _yesterday_in_tz(cfg.instrument.timezone)
    )
    run = db.get_run(cfg.instrument.id, target)
    if run is None:
        print(f"no run recorded for {cfg.instrument.id} {target}")
        return 1
    print(f"{cfg.instrument.id} {target}: {run.status.value} "
          f"(attempt={run.attempt}, prefix={run.gcs_prefix})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pandora-summarizer")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="execute a daily run")
    p_run.add_argument("--config", type=Path, required=True)
    p_run.add_argument("--date", type=str, default=None,
                       help="YYYY-MM-DD; defaults to yesterday in instrument tz")
    p_run.add_argument("--dry-run", action="store_true",
                       help="skip BlickP invocation and GCS upload")
    p_run.set_defaults(func=_cmd_run)

    p_st = sub.add_parser("status", help="show recorded status of a daily run")
    p_st.add_argument("--config", type=Path, required=True)
    p_st.add_argument("--date", type=str, default=None)
    p_st.set_defaults(func=_cmd_status)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
