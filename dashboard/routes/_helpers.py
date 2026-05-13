"""Shared route helpers."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from flask import current_app, request

from ..services import SummaryReader


def reader() -> SummaryReader:
    r = current_app.config["SUMMARY_READER"]
    return r  # type: ignore[no-any-return]


def parse_date_arg(name: str = "date", default: date | None = None) -> date:
    raw = request.args.get(name)
    if not raw:
        if default is not None:
            return default
        return date.today()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return default or date.today()


def filter_records(records: list[Any]) -> list[Any]:
    """Apply ?filter=… query params common to fleet views."""
    health = request.args.get("health")
    online = request.args.get("online")
    location = request.args.get("location")
    alignment = request.args.get("alignment")
    upload = request.args.get("upload")
    instrument = request.args.get("instrument")
    out = records
    if health:
        out = [r for r in out if r.health_label.lower() == health.lower()]
    if online:
        out = [r for r in out if r.online_status.lower() == online.lower()]
    if location:
        out = [r for r in out if (r.location_name or "").lower() == location.lower()]
    if alignment:
        out = [r for r in out if r.alignment_health.lower() == alignment.lower()]
    if upload:
        out = [r for r in out if r.upload_status.lower() == upload.lower()]
    if instrument:
        out = [r for r in out if instrument.lower() in r.instrument_id.lower()]
    return out
