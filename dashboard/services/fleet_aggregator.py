"""Aggregate per-instrument SummaryRecords into fleet-level views."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from .gcs_reader import SummaryReader
from .summary_loader import SummaryRecord, load_summary


@dataclass
class FleetSnapshot:
    target_date: date
    records: list[SummaryRecord] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.records)

    @property
    def by_health_label(self) -> dict[str, int]:
        return dict(Counter(r.health_label for r in self.records))

    @property
    def by_online_status(self) -> dict[str, int]:
        return dict(Counter(r.online_status for r in self.records))

    @property
    def units_with_critical_errors(self) -> list[SummaryRecord]:
        return [r for r in self.records if r.error_count > 0]

    @property
    def units_with_missing_l0(self) -> list[SummaryRecord]:
        return [r for r in self.records if r.l0_status != "PRESENT"]

    @property
    def units_with_bad_alignment(self) -> list[SummaryRecord]:
        return [r for r in self.records
                if r.alignment_health in ("CRITICAL", "WARNING")]

    @property
    def units_with_failed_upload(self) -> list[SummaryRecord]:
        return [r for r in self.records if r.upload_status != "COMPLETED"]

    @property
    def units_offline(self) -> list[SummaryRecord]:
        return [r for r in self.records if r.online_status == "OFFLINE"]

    @property
    def units_online(self) -> list[SummaryRecord]:
        return [r for r in self.records if r.online_status == "ONLINE"]


def aggregate_fleet(
    reader: SummaryReader, target_date: date,
) -> FleetSnapshot:
    snapshot = FleetSnapshot(target_date=target_date)
    for instrument in reader.list_instruments():
        raw = reader.read(instrument, target_date)
        rec = load_summary(raw)
        if rec is None:
            continue
        snapshot.records.append(rec)
    snapshot.records.sort(key=lambda r: (r.health_score, r.instrument_id))
    return snapshot


def latest_per_instrument(reader: SummaryReader) -> FleetSnapshot:
    """Build a snapshot using the most recent date available per instrument."""
    snapshot_records: list[SummaryRecord] = []
    latest: date | None = None
    for instrument in reader.list_instruments():
        dates = reader.list_dates_for(instrument)
        if not dates:
            continue
        d = dates[0]
        if latest is None or d > latest:
            latest = d
        rec = load_summary(reader.read(instrument, d))
        if rec is not None:
            snapshot_records.append(rec)
    snap = FleetSnapshot(target_date=latest or date.today())
    snap.records = sorted(snapshot_records, key=lambda r: r.instrument_id)
    return snap
