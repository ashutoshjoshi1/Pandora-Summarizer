"""Flask app factory for the Pandora Fleet dashboard."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from flask import Flask

from .config import DashboardConfig
from .routes import export, fleet, instrument, reports
from .services import LocalReader, RemoteGcsReader, SummaryReader

log = logging.getLogger(__name__)


def _build_reader(cfg: DashboardConfig) -> SummaryReader:
    if cfg.fixtures_dir is not None:
        log.info("Dashboard using LocalReader at %s", cfg.fixtures_dir)
        return LocalReader(root=cfg.fixtures_dir)
    log.info("Dashboard using RemoteGcsReader (bucket=%s prefix=%s)",
             cfg.bucket, cfg.prefix)
    return RemoteGcsReader(
        bucket_name=cfg.bucket,
        prefix=cfg.prefix,
        service_account_json=cfg.service_account_json,
        cache_seconds=cfg.cache_seconds,
    )


def create_app(cfg: DashboardConfig | None = None) -> Flask:
    cfg = cfg or DashboardConfig.from_env()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["DASH_CONFIG"] = cfg
    app.config["SUMMARY_READER"] = _build_reader(cfg)

    app.register_blueprint(fleet.bp)
    app.register_blueprint(instrument.bp, url_prefix="/instrument")
    app.register_blueprint(reports.bp, url_prefix="/reports")
    app.register_blueprint(export.bp, url_prefix="/export")

    @app.context_processor
    def inject_meta() -> dict[str, str]:
        return {
            "bucket_name": cfg.bucket,
            "bucket_prefix": cfg.prefix,
        }

    return app


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    # Ensure local sibling packages resolve when running `python -m dashboard.app`.
    here = Path(__file__).resolve().parent.parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    app = create_app()
    host = os.environ.get("PANDORA_DASH_HOST", "127.0.0.1")
    port = int(os.environ.get("PANDORA_DASH_PORT", "8080"))
    app.run(host=host, port=port, debug=bool(int(os.environ.get("FLASK_DEBUG", "0"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
