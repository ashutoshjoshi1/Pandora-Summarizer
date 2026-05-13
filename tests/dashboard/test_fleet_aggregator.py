from __future__ import annotations

from datetime import date
from pathlib import Path

from dashboard.services import LocalReader
from dashboard.services.fleet_aggregator import aggregate_fleet, latest_per_instrument


def test_aggregate_groups_records_by_date(fixtures_dir: Path) -> None:
    reader = LocalReader(root=fixtures_dir)
    snap = aggregate_fleet(reader, date(2026, 5, 12))
    assert snap.total == 3
    counts = snap.by_health_label
    assert counts == {"GREEN": 1, "YELLOW": 1, "RED": 1}
    assert len(snap.units_offline) == 1
    assert len(snap.units_with_critical_errors) == 1
    assert len(snap.units_with_failed_upload) == 1
    assert len(snap.units_with_missing_l0) == 1


def test_aggregate_omits_dates_without_summary(fixtures_dir: Path) -> None:
    reader = LocalReader(root=fixtures_dir)
    snap = aggregate_fleet(reader, date(2024, 1, 1))
    assert snap.total == 0


def test_latest_per_instrument_picks_freshest(fixtures_dir: Path) -> None:
    reader = LocalReader(root=fixtures_dir)
    snap = latest_per_instrument(reader)
    assert snap.total == 3
    # All records should be from the freshest available date for each unit.
    for rec in snap.records:
        assert rec.target_date == date(2026, 5, 12)
