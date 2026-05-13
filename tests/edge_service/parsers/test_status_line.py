from __future__ import annotations

from pandora_edge.parsers.status_line_parser import parse_status_line


def test_parses_typical_status_line() -> None:
    line = (
        "status: mode=SCHEDULE schedule=uv_sun.sked routine=SO last_routine=SU "
        "sun_search=SUCCESS rms=0.02 offset=0.01 fwhm=0.5 tracker_connected=true "
        "tracker_reset_count=2 warning_count=3 time=2026-05-12T12:00:00Z"
    )
    s = parse_status_line(line)
    assert s.mode == "SCHEDULE"
    assert s.current_schedule == "uv_sun.sked"
    assert s.current_routine == "SO"
    assert s.last_routine == "SU"
    assert s.sun_search_status == "SUCCESS"
    assert s.rms == 0.02
    assert s.offset == 0.01
    assert s.fwhm == 0.5
    assert s.tracker_connected is True
    assert s.tracker_reset_count == 2
    assert s.warning_count == 3
    assert s.timestamp_utc is not None
    assert s.timestamp_utc.isoformat().startswith("2026-05-12T12:00:00")


def test_unknown_tokens_preserved_in_extras() -> None:
    s = parse_status_line("foo=bar mode=ROUTINE custom_metric=12.5")
    assert s.mode == "ROUTINE"
    assert "foo" in s.extras
    assert s.extras["custom_metric"] == "12.5"


def test_invalid_input_returns_empty_fields() -> None:
    s = parse_status_line("totally not a status line")
    assert s.mode is None
    assert s.rms is None
    assert s.timestamp_utc is None


def test_boolean_parsing_handles_synonyms() -> None:
    assert parse_status_line("tracker_connected=connected").tracker_connected is True
    assert parse_status_line("tracker_connected=down").tracker_connected is False
    assert parse_status_line("tracker_connected=maybe").tracker_connected is None
