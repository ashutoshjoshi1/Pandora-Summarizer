"""Discover Blick output files for a target date with stability filtering."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class FileEntry:
    path: Path
    name: str
    size_bytes: int
    modified_utc: datetime
    sha256: str | None = None

    def relative_name(self) -> str:
        return self.name


@dataclass
class FileInventory:
    target_date: date
    l0: list[FileEntry] = field(default_factory=list)
    partial_l0: list[FileEntry] = field(default_factory=list)
    oslog: list[FileEntry] = field(default_factory=list)
    fslog: list[FileEntry] = field(default_factory=list)
    pslog: list[FileEntry] = field(default_factory=list)
    alignment: list[FileEntry] = field(default_factory=list)
    figures: list[FileEntry] = field(default_factory=list)
    skipped_unstable: list[Path] = field(default_factory=list)

    @property
    def all_logs(self) -> list[FileEntry]:
        return self.oslog + self.fslog + self.pslog

    def last_file_mtime_utc(self) -> datetime | None:
        candidates = (
            self.l0 + self.partial_l0 + self.alignment
            + self.oslog + self.fslog + self.pslog
        )
        if not candidates:
            return None
        return max(c.modified_utc for c in candidates)


def _sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _entry(path: Path, *, compute_sha: bool) -> FileEntry | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return FileEntry(
        path=path,
        name=path.name,
        size_bytes=st.st_size,
        modified_utc=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
        sha256=_sha256(path) if compute_sha else None,
    )


def _date_matches(name: str, target: date) -> bool:
    """Match if the date appears in any common format inside the filename.

    Accepts YYYYMMDD, YYYY-MM-DD, and YYMMDD substrings.
    """
    ymd = target.strftime("%Y%m%d")
    iso = target.isoformat()
    short = target.strftime("%y%m%d")
    return ymd in name or iso in name or short in name


def _is_stable(entry: FileEntry, stability_seconds: int, now_utc: float) -> bool:
    age = now_utc - entry.modified_utc.timestamp()
    return age >= stability_seconds


def _collect(
    directory: Path | None,
    target: date,
    *,
    patterns: tuple[str, ...],
    stability_seconds: int,
    skipped: list[Path],
    compute_sha: bool,
    now_utc: float,
    exclude_patterns: tuple[str, ...] = (),
) -> list[FileEntry]:
    if directory is None or not directory.exists():
        return []
    out: list[FileEntry] = []
    seen: set[Path] = set()
    for pat in patterns:
        for p in directory.glob(pat):
            if p in seen or not p.is_file():
                continue
            seen.add(p)
            if any(p.match(ex) for ex in exclude_patterns):
                continue
            if not _date_matches(p.name, target):
                continue
            entry = _entry(p, compute_sha=compute_sha)
            if entry is None:
                continue
            if not _is_stable(entry, stability_seconds, now_utc):
                skipped.append(p)
                continue
            out.append(entry)
    return sorted(out, key=lambda e: e.name)


def build_inventory(
    *,
    target_date: date,
    l0_dir: Path | None,
    tmp_dir: Path | None,
    alignment_dir: Path | None,
    figures_dir: Path | None,
    oslog_dir: Path | None,
    fslog_dir: Path | None,
    pslog_dir: Path | None,
    stability_seconds: int = 60,
    compute_sha: bool = True,
    now_utc: float | None = None,
) -> FileInventory:
    """Walk Blick directories and snapshot files belonging to target_date.

    Files actively being written (mtime within stability_seconds) are skipped
    and reported in `skipped_unstable`.
    """
    inv = FileInventory(target_date=target_date)
    now = now_utc if now_utc is not None else time.time()

    inv.l0 = _collect(
        l0_dir, target_date,
        patterns=("*.txt", "*.dat", "*.l0", "*.L0"),
        exclude_patterns=("*partial*", "*Partial*", "*PARTIAL*"),
        stability_seconds=stability_seconds,
        skipped=inv.skipped_unstable, compute_sha=compute_sha, now_utc=now,
    )
    # Partial L0 / status files may live under l0_dir or tmp_dir.
    partial_sources = [d for d in (l0_dir, tmp_dir) if d is not None]
    for src in partial_sources:
        inv.partial_l0.extend(
            _collect(
                src, target_date,
                patterns=("*partial*", "*status*", "*Status*"),
                stability_seconds=stability_seconds,
                skipped=inv.skipped_unstable, compute_sha=compute_sha, now_utc=now,
            )
        )
    inv.oslog = _collect(
        oslog_dir, target_date,
        patterns=("*.txt", "*.log"),
        stability_seconds=stability_seconds,
        skipped=inv.skipped_unstable, compute_sha=compute_sha, now_utc=now,
    )
    inv.fslog = _collect(
        fslog_dir, target_date,
        patterns=("*.txt", "*.log"),
        stability_seconds=stability_seconds,
        skipped=inv.skipped_unstable, compute_sha=compute_sha, now_utc=now,
    )
    inv.pslog = _collect(
        pslog_dir, target_date,
        patterns=("*.txt", "*.log"),
        stability_seconds=stability_seconds,
        skipped=inv.skipped_unstable, compute_sha=compute_sha, now_utc=now,
    )
    inv.alignment = _collect(
        alignment_dir, target_date,
        patterns=("*.txt", "*.dat", "*.align"),
        stability_seconds=stability_seconds,
        skipped=inv.skipped_unstable, compute_sha=compute_sha, now_utc=now,
    )
    inv.figures = _collect(
        figures_dir, target_date,
        patterns=("*.png", "*.jpg", "*.jpeg", "*.pdf", "*.svg"),
        stability_seconds=stability_seconds,
        skipped=inv.skipped_unstable, compute_sha=compute_sha, now_utc=now,
    )
    return inv
