from __future__ import annotations

from datetime import date
from pathlib import Path

from pandora_summarizer.steps.locate_l0 import locate_l0


def test_returns_none_when_dir_missing(tmp_path: Path) -> None:
    assert locate_l0(tmp_path / "nope", date(2026, 5, 1)) is None


def test_finds_file_with_matching_date(tmp_path: Path) -> None:
    (tmp_path / "Pandora100s1_BoulderCO_20260501.txt").write_text("x")
    (tmp_path / "Pandora100s1_BoulderCO_20260430.txt").write_text("x")
    found = locate_l0(tmp_path, date(2026, 5, 1))
    assert found is not None and "20260501" in found.name


def test_returns_none_when_no_match(tmp_path: Path) -> None:
    (tmp_path / "Pandora100s1_BoulderCO_20260430.txt").write_text("x")
    assert locate_l0(tmp_path, date(2026, 5, 1)) is None


def test_picks_largest_when_multiple_match(tmp_path: Path) -> None:
    a = tmp_path / "a_20260501.txt"; a.write_text("a")
    b = tmp_path / "b_20260501.bak"; b.write_text("bb")
    found = locate_l0(tmp_path, date(2026, 5, 1))
    assert found == b
