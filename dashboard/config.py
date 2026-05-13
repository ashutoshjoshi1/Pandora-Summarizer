"""Dashboard configuration loaded from environment variables.

The dashboard is intentionally read-only and config-light: bucket name,
prefix, optional service account, and an optional local fixtures directory
for development without GCS access.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DashboardConfig:
    bucket: str
    prefix: str
    service_account_json: Path | None
    fixtures_dir: Path | None       # local fallback for dev / tests
    cache_seconds: int

    @classmethod
    def from_env(cls) -> "DashboardConfig":
        sa = os.environ.get("PANDORA_DASH_SA_JSON")
        fx = os.environ.get("PANDORA_DASH_FIXTURES_DIR")
        return cls(
            bucket=os.environ.get("PANDORA_DASH_BUCKET", "log_web"),
            prefix=os.environ.get("PANDORA_DASH_PREFIX", "pandora-fleet-monitoring"),
            service_account_json=Path(sa) if sa else None,
            fixtures_dir=Path(fx) if fx else None,
            cache_seconds=int(os.environ.get("PANDORA_DASH_CACHE_SECONDS", "60")),
        )
