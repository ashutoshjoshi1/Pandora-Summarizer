from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pandora_edge.parsers.file_inventory_parser import FileEntry
from pandora_edge.parsers.log_parser import parse_log_files


def _entry(p: Path) -> FileEntry:
    st = p.stat()
    return FileEntry(
        path=p, name=p.name, size_bytes=st.st_size,
        modified_utc=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
    )


def test_counts_levels_and_groups_repeated_warnings(tmp_path: Path) -> None:
    os = tmp_path / "oslog.txt"
    os.write_text(
        "2026-05-12T10:00:00Z INFO startup\n"
        "2026-05-12T10:01:00Z WARNING tracker drift 12 mm\n"
        "2026-05-12T10:02:00Z WARNING tracker drift 15 mm\n"
        "2026-05-12T10:03:00Z WARNING tracker drift 18 mm\n"
        "2026-05-12T10:04:00Z ERROR comms timeout 0x7f\n"
        "2026-05-12T10:05:00Z CRITICAL fatal sensor failure\n"
    )
    roll = parse_log_files(oslog=[_entry(os)], fslog=[], pslog=[])
    assert roll.total_warning_count == 3
    assert roll.total_error_count == 2
    # All three "tracker drift" warnings group into one repeated entry.
    assert any(r["count"] == 3 for r in roll.repeated_warnings)
    assert roll.critical_errors  # CRITICAL captured
    assert roll.first_warning_utc is not None
    assert roll.last_error_utc is not None


def test_unparseable_lines_are_ignored(tmp_path: Path) -> None:
    p = tmp_path / "log.txt"
    p.write_text("garbage\n\n   no timestamp no level\n2026-05-12T01:00:00Z INFO hi\n")
    roll = parse_log_files(oslog=[_entry(p)], fslog=[], pslog=[])
    assert roll.total_warning_count == 0
    assert roll.total_error_count == 0


def test_missing_files_return_empty_rollup() -> None:
    roll = parse_log_files(oslog=[], fslog=[], pslog=[])
    assert roll.total_warning_count == 0
    assert "No warnings" in roll.warning_summary
