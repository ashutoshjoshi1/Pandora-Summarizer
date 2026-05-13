"""Argparse-based CLI entrypoint."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import Config
from .logging_setup import configure_logging
from .orchestrator import Orchestrator
from .service import install_task, uninstall_task
from .state import StateDB
from .version import __version__

log = logging.getLogger(__name__)


def _parse_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"invalid date {s!r}: {e}") from e


def _default_target_date(cfg: Config) -> date:
    return date.today() - timedelta(days=cfg.service.process_lookback_days)


def _load_cfg(path: str | None) -> Config:
    candidate = Path(path) if path else Path("config/config.yaml")
    return Config.load(candidate)


def cmd_run(args: argparse.Namespace) -> int:
    cfg = _load_cfg(args.config)
    configure_logging(cfg.logging.dir, cfg.logging.level,
                      cfg.logging.rotate_mb, cfg.logging.keep_files)
    target = args.date or _default_target_date(cfg)
    with StateDB(cfg.state.db_path) as db:
        orch = Orchestrator(cfg, db, dry_run=args.dry_run)
        status = orch.run_for(target)
    log.info("run finished with status=%s", status.value)
    return 0 if status.value in ("COMPLETED", "PARTIAL") else 1


def cmd_backfill(args: argparse.Namespace) -> int:
    cfg = _load_cfg(args.config)
    configure_logging(cfg.logging.dir, cfg.logging.level,
                      cfg.logging.rotate_mb, cfg.logging.keep_files)
    if args.end < args.start:
        log.error("--end must be >= --start")
        return 2

    exit_code = 0
    with StateDB(cfg.state.db_path) as db:
        orch = Orchestrator(cfg, db, dry_run=args.dry_run)
        cursor = args.start
        while cursor <= args.end:
            status = orch.run_for(cursor)
            log.info("backfill %s status=%s", cursor, status.value)
            if status.value == "FAILED":
                exit_code = 1
            cursor += timedelta(days=1)
    return exit_code


def cmd_validate_config(args: argparse.Namespace) -> int:
    try:
        cfg = _load_cfg(args.config)
    except Exception as e:  # noqa: BLE001 - top-level CLI handler
        print(f"INVALID: {e}", file=sys.stderr)
        return 2
    print(f"OK: config valid for instrument {cfg.instrument.id}")
    print(f"  bucket: {cfg.gcs.bucket}")
    print(f"  prefix: {cfg.gcs.prefix}/{cfg.instrument.id}/<YYYY-MM-DD>/")
    print(f"  state.db: {cfg.state.db_path}")
    print(f"  log dir: {cfg.logging.dir}")
    return 0


def cmd_install_task(args: argparse.Namespace) -> int:
    cfg = _load_cfg(args.config)
    rc = install_task(
        config_path=Path(args.config or "config/config.yaml").resolve(),
        run_time_hhmm=cfg.service.run_time_local,
    )
    return rc


def cmd_uninstall_task(_args: argparse.Namespace) -> int:
    return uninstall_task()


def build_parser() -> argparse.ArgumentParser:
    # Shared parent so --config works both before and after the subcommand,
    # e.g. `pandora-edge --config X run` and `pandora-edge run --config X`.
    # Use SUPPRESS so the subparser doesn't overwrite a value passed to the
    # top-level parser (and vice versa); we apply the real default after parsing.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", help="Path to config.yaml",
                        default=argparse.SUPPRESS)

    parser = argparse.ArgumentParser(prog="pandora-edge", parents=[common])
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", parents=[common],
                           help="Run the pipeline for one day")
    p_run.add_argument("--date", type=_parse_date,
                       help="Target date (YYYY-MM-DD); defaults to yesterday.")
    p_run.add_argument("--dry-run", action="store_true",
                       help="Process but do not upload to GCS.")
    p_run.set_defaults(func=cmd_run)

    p_bf = sub.add_parser("backfill", parents=[common],
                          help="Run the pipeline across a date range")
    p_bf.add_argument("--start", type=_parse_date, required=True)
    p_bf.add_argument("--end", type=_parse_date, required=True)
    p_bf.add_argument("--dry-run", action="store_true")
    p_bf.set_defaults(func=cmd_backfill)

    p_v = sub.add_parser("validate-config", parents=[common],
                         help="Validate the YAML config")
    p_v.set_defaults(func=cmd_validate_config)

    p_i = sub.add_parser("install-task", parents=[common],
                         help="Create the Windows scheduled task")
    p_i.set_defaults(func=cmd_install_task)

    p_u = sub.add_parser("uninstall-task", parents=[common],
                         help="Remove the Windows scheduled task")
    p_u.set_defaults(func=cmd_uninstall_task)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "config", None):
        args.config = "config/config.yaml"
    try:
        return int(args.func(args))
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
