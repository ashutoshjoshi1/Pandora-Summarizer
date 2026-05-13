"""Fleet overview routes."""
from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, render_template, request

from ..services.fleet_aggregator import aggregate_fleet, latest_per_instrument
from ._helpers import filter_records, reader

bp = Blueprint("fleet", __name__)


@bp.get("/")
@bp.get("/fleet")
def fleet_overview() -> str:
    r = reader()
    date_arg = request.args.get("date")
    if date_arg:
        try:
            target = date.fromisoformat(date_arg)
        except ValueError:
            target = date.today() - timedelta(days=1)
        snap = aggregate_fleet(r, target)
    else:
        snap = latest_per_instrument(r)

    visible = filter_records(snap.records)
    instruments = r.list_instruments()
    return render_template(
        "fleet.html",
        snap=snap,
        records=visible,
        instruments=instruments,
        active_date=snap.target_date.isoformat(),
        query=dict(request.args),
    )
