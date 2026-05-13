"""Instrument detail routes."""
from __future__ import annotations

from datetime import date

from flask import Blueprint, abort, render_template

from ..services.summary_loader import load_summary
from ._helpers import reader

bp = Blueprint("instrument", __name__)


@bp.get("/<instrument_id>")
def detail(instrument_id: str) -> str:
    r = reader()
    dates = r.list_dates_for(instrument_id)
    if not dates:
        abort(404)

    latest_summary = load_summary(r.read(instrument_id, dates[0]))
    if latest_summary is None:
        abort(404)

    # Build a compact trend list (newest first, oldest last).
    trend = []
    for d in dates[:30]:
        rec = load_summary(r.read(instrument_id, d))
        if rec is None:
            continue
        trend.append({
            "date": d.isoformat(),
            "score": rec.health_score,
            "label": rec.health_label,
            "online": rec.online_status,
            "warnings": rec.warning_count,
            "errors": rec.error_count,
            "alignment": rec.alignment_health,
            "alignment_weighting": rec.alignment_weighting,
            "upload": rec.upload_status,
            "l0_status": rec.l0_status,
        })

    return render_template(
        "instrument.html",
        record=latest_summary,
        trend=trend,
        instrument_id=instrument_id,
        all_dates=[d.isoformat() for d in dates],
    )


@bp.get("/<instrument_id>/<date_iso>")
def detail_for_date(instrument_id: str, date_iso: str) -> str:
    try:
        d = date.fromisoformat(date_iso)
    except ValueError:
        abort(400)
    r = reader()
    rec = load_summary(r.read(instrument_id, d))
    if rec is None:
        abort(404)
    return render_template(
        "instrument.html",
        record=rec,
        trend=[],
        instrument_id=instrument_id,
        all_dates=[d.isoformat() for d in r.list_dates_for(instrument_id)],
    )
