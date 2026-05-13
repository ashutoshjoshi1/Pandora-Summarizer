from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pandora_edge.parsers.alignment_parser import parse_alignment_files
from pandora_edge.parsers.file_inventory_parser import FileEntry


def _entry(p: Path) -> FileEntry:
    st = p.stat()
    return FileEntry(
        path=p, name=p.name, size_bytes=st.st_size,
        modified_utc=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
    )


def test_parses_good_scan(tmp_path: Path) -> None:
    f = tmp_path / "alignment_20260512.txt"
    f.write_text(
        "# scan_type weighting_factor rms time\n"
        "FS 1459.5 0.026 2026-05-12T16:10:00Z\n"
        "FS 1500.0 0.020 2026-05-12T17:00:00Z\n"
    )
    info = parse_alignment_files([_entry(f)], min_good_weighting=500)
    assert info.alignment_file_found is True
    assert info.scan_count == 2
    assert info.good_scan_count == 2
    assert info.bad_scan_count == 0
    assert info.latest_weighting_factor == 1500.0
    assert info.latest_scan_type == "FS"


def test_marks_bad_scans_below_threshold(tmp_path: Path) -> None:
    f = tmp_path / "alignment_20260512.txt"
    f.write_text(
        "# scan_type weighting_factor rms time\n"
        "FS 200.0 0.05 2026-05-12T17:00:00Z\n"
    )
    info = parse_alignment_files([_entry(f)], min_good_weighting=500)
    assert info.bad_scan_count == 1
    assert info.good_scan_count == 0


def test_no_files_returns_empty_info() -> None:
    info = parse_alignment_files([], min_good_weighting=500)
    assert info.alignment_file_found is False
    assert info.scan_count == 0
