from __future__ import annotations


def test_fleet_overview_renders(client) -> None:
    r = client.get("/fleet?date=2026-05-12")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Pandora024" in body
    assert "Pandora099" in body
    assert "Pandora200" in body
    assert "GREEN" in body
    assert "RED" in body


def test_fleet_filters_apply(client) -> None:
    r = client.get("/fleet?date=2026-05-12&health=RED")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Pandora200" in body
    assert "Pandora024" not in body


def test_instrument_detail_renders(client) -> None:
    r = client.get("/instrument/Pandora024")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Pandora024" in body
    assert "Scans are good" in body


def test_instrument_unknown_returns_404(client) -> None:
    r = client.get("/instrument/DoesNotExist")
    assert r.status_code == 404


def test_daily_report_renders(client) -> None:
    r = client.get("/reports/2026-05-12")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "GREEN" in body
    assert "Pandora200" in body  # Listed under failed upload / critical errors


def test_csv_export_returns_csv(client) -> None:
    r = client.get("/export/fleet.csv?date=2026-05-12")
    assert r.status_code == 200
    assert r.mimetype == "text/csv"
    body = r.get_data(as_text=True)
    lines = body.strip().splitlines()
    assert lines[0].startswith("instrument_id,target_date,health_label")
    assert any("Pandora024" in ln for ln in lines)


def test_csv_export_respects_filter(client) -> None:
    r = client.get("/export/fleet.csv?date=2026-05-12&health=RED")
    body = r.get_data(as_text=True)
    assert "Pandora200" in body
    assert "Pandora024" not in body
