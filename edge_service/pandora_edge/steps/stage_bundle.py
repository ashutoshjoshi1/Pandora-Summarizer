"""Stage Blick files into a deterministic local layout for upload.

Layout matches the spec exactly:
  <staging>/summary.json
  <staging>/manifest.json
  <staging>/data/l0/...
  <staging>/data/partial_l0/...
  <staging>/data/alignment/...
  <staging>/data/logs/oslog|fslog|pslog/...
  <staging>/data/figures/...
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import Config
from ..gcs import UploadItem
from ..parsers import FileEntry, FileInventory


@dataclass
class StagedBundle:
    staging_root: Path
    summary_path: Path
    manifest_path: Path
    items: list[UploadItem] = field(default_factory=list)
    data_manifest: list[dict[str, Any]] = field(default_factory=list)


def _copy(src: Path, dst: Path) -> int:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst.stat().st_size


def _stage_group(
    entries: list[FileEntry],
    sub_path: str,
    *,
    staging_root: Path,
    gcs_prefix: str,
    artifact_type: str,
    bundle: StagedBundle,
    now_iso: str,
) -> None:
    for e in entries:
        local = staging_root / "data" / sub_path / e.name
        size = _copy(e.path, local)
        gcs_object = f"{gcs_prefix}/data/{sub_path}/{e.name}"
        bundle.items.append(UploadItem(local_path=local, object_path=gcs_object))
        bundle.data_manifest.append({
            "filename": e.name,
            "artifact_type": artifact_type,
            "size_bytes": size,
            "sha256": e.sha256,
            "gcs_object": gcs_object,
            "uploaded_at_utc": now_iso,
        })


def stage_bundle(
    *,
    cfg: Config,
    staging_root: Path,
    inventory: FileInventory,
    gcs_prefix: str,
) -> StagedBundle:
    staging_root.mkdir(parents=True, exist_ok=True)
    bundle = StagedBundle(
        staging_root=staging_root,
        summary_path=staging_root / "summary.json",
        manifest_path=staging_root / "manifest.json",
    )
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if cfg.service.upload_l0_files:
        _stage_group(inventory.l0, "l0", staging_root=staging_root,
                     gcs_prefix=gcs_prefix, artifact_type="L0", bundle=bundle,
                     now_iso=now_iso)
    if cfg.service.upload_partial_l0_files:
        _stage_group(inventory.partial_l0, "partial_l0",
                     staging_root=staging_root, gcs_prefix=gcs_prefix,
                     artifact_type="PARTIAL_L0", bundle=bundle, now_iso=now_iso)
    if cfg.service.upload_alignment_files:
        _stage_group(inventory.alignment, "alignment",
                     staging_root=staging_root, gcs_prefix=gcs_prefix,
                     artifact_type="ALIGNMENT", bundle=bundle, now_iso=now_iso)
    if cfg.service.upload_logs:
        _stage_group(inventory.oslog, "logs/oslog", staging_root=staging_root,
                     gcs_prefix=gcs_prefix, artifact_type="OSLOG", bundle=bundle,
                     now_iso=now_iso)
        _stage_group(inventory.fslog, "logs/fslog", staging_root=staging_root,
                     gcs_prefix=gcs_prefix, artifact_type="FSLOG", bundle=bundle,
                     now_iso=now_iso)
        _stage_group(inventory.pslog, "logs/pslog", staging_root=staging_root,
                     gcs_prefix=gcs_prefix, artifact_type="PSLOG", bundle=bundle,
                     now_iso=now_iso)
    if cfg.service.upload_figures:
        _stage_group(inventory.figures, "figures", staging_root=staging_root,
                     gcs_prefix=gcs_prefix, artifact_type="FIGURE", bundle=bundle,
                     now_iso=now_iso)

    return bundle


def write_manifest(bundle: StagedBundle, *, instrument_id: str, target_date: str,
                   gcs_prefix: str) -> None:
    manifest = {
        "schema_version": "1.0",
        "instrument_id": instrument_id,
        "target_date": target_date,
        "gcs_prefix": gcs_prefix,
        "generated_at_utc": datetime.now(timezone.utc)
            .isoformat().replace("+00:00", "Z"),
        "object_count": len(bundle.data_manifest),
        "objects": bundle.data_manifest,
    }
    bundle.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with bundle.manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
