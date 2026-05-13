from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pandora_edge.parsers.file_inventory_parser import FileEntry
from pandora_edge.parsers.l0_parser import parse_l0_files


def _entry(p: Path) -> FileEntry:
    st = p.stat()
    return FileEntry(
        path=p, name=p.name, size_bytes=st.st_size,
        modified_utc=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
    )


def test_extracts_status_and_counts_measurements(tmp_path: Path) -> None:
    p = tmp_path / "Pandora_L0_20260512.txt"
    p.write_text(
        "# status: mode=SCHEDULE schedule=uv_sun.sked routine=SO "
        "tracker_connected=true rms=0.02 time=2026-05-12T12:00:00Z\n"
        "2026-05-12T12:00:00Z 123 456\n"
        "2026-05-12T12:01:00Z 124 457\n"
    )
    info = parse_l0_files([_entry(p)], partial_entries=[])
    assert info.l0_status == "PRESENT"
    assert info.l0_file_count == 1
    assert info.current_mode == "SCHEDULE"
    assert info.current_schedule == "uv_sun.sked"
    assert info.current_routine == "SO"
    assert info.tracker_connected is True
    assert info.measurement_count == 2
    assert "SO" in info.routines_observed


def test_status_partial_when_only_partial_files() -> None:
    info = parse_l0_files([], partial_entries=[])
    assert info.l0_status == "MISSING"


def test_partial_marks_l0_status_partial(tmp_path: Path) -> None:
    p = tmp_path / "Pandora_partial_20260512.txt"
    p.write_text(
        "# status: mode=SCHEDULE schedule=uv.sked routine=SO time=2026-05-12T23:50:00Z\n"
    )
    info = parse_l0_files([], partial_entries=[_entry(p)])
    assert info.l0_status == "PARTIAL"
    assert info.partial_l0_file_count == 1
    assert info.current_routine == "SO"
