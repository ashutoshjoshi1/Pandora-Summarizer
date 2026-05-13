"""CSV export routes — mirror what's visible on the fleet page."""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from flask import Blueprint, Response, request

from ..services.fleet_aggregator import aggregate_fleet, latest_per_instrument
from ._helpers import filter_records, reader

bp = Blueprint("export", __name__)


_COLUMNS = [
    "instrument_id", "target_date", "health_label", "health_score",
    "online_status", "last_log_received_utc", "last_successful_measurement_utc",
    "current_schedule", "current_routine", "warning_count", "error_count",
    "tracker_health", "sun_search_status", "alignment_health",
    "alignment_weighting", "l0_status", "partial_l0_status",
    "upload_status", "upload_objects", "upload_bytes",
    "location_name", "timezone",
]


@bp.get("/fleet.csv")
def fleet_csv() -> Response:
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
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_COLUMNS)
    writer.writeheader()
    for rec in visible:
        writer.writerow({
            "instrument_id": rec.instrument_id,
            "target_date": rec.target_date.isoformat(),
            "health_label": rec.health_label,
            "health_score": rec.health_score,
            "online_status": rec.online_status,
            "last_log_received_utc": rec.last_log_received_utc or "",
            "last_successful_measurement_utc":
                rec.last_successful_measurement_utc or "",
            "current_schedule": rec.current_schedule or "",
            "current_routine": rec.current_routine or "",
            "warning_count": rec.warning_count,
            "error_count": rec.error_count,
            "tracker_health": rec.tracker_health,
            "sun_search_status": rec.sun_search_status or "",
            "alignment_health": rec.alignment_health,
            "alignment_weighting": rec.alignment_weighting or "",
            "l0_status": rec.l0_status,
            "partial_l0_status": rec.partial_l0_status,
            "upload_status": rec.upload_status,
            "upload_objects": rec.upload_objects,
            "upload_bytes": rec.upload_bytes,
            "location_name": rec.location_name or "",
            "timezone": rec.timezone or "",
        })
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                f"attachment; filename=pandora-fleet-{snap.target_date.isoformat()}.csv",
        },
    )
