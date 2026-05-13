"""Daily report routes."""
from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, render_template, request

from ..services.fleet_aggregator import aggregate_fleet
from ._helpers import reader

bp = Blueprint("reports", __name__)


@bp.get("/")
@bp.get("/<date_iso>")
def daily_report(date_iso: str | None = None) -> str:
    raw = date_iso or request.args.get("date")
    if raw:
        try:
            target = date.fromisoformat(raw)
        except ValueError:
            target = date.today() - timedelta(days=1)
    else:
        target = date.today() - timedelta(days=1)

    r = reader()
    snap = aggregate_fleet(r, target)
    return render_template("report.html", snap=snap, target_date=target.isoformat())
