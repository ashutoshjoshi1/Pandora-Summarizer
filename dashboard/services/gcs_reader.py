"""Pluggable read-only summary reader.

`SummaryReader` is a Protocol so dev / tests can use a `LocalReader`
backed by a directory of summary.json files; production uses `RemoteGcsReader`.

Layout matched by both readers:
    <root>/<instrument_id>/<YYYY-MM-DD>/summary.json
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol

log = logging.getLogger(__name__)


class SummaryReader(Protocol):
    def list_instruments(self) -> list[str]: ...
    def list_dates_for(self, instrument_id: str) -> list[date]: ...
    def read(self, instrument_id: str, target_date: date) -> dict[str, Any] | None: ...


def _iso_to_date(s: str) -> date | None:
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Local filesystem reader (dev, tests, offline triage).
# ---------------------------------------------------------------------------

@dataclass
class LocalReader:
    root: Path

    def list_instruments(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())

    def list_dates_for(self, instrument_id: str) -> list[date]:
        d = self.root / instrument_id
        if not d.exists():
            return []
        dates: list[date] = []
        for child in d.iterdir():
            dt = _iso_to_date(child.name)
            if dt is not None and (child / "summary.json").exists():
                dates.append(dt)
        return sorted(dates, reverse=True)

    def read(self, instrument_id: str, target_date: date) -> dict[str, Any] | None:
        path = self.root / instrument_id / target_date.isoformat() / "summary.json"
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            assert isinstance(data, dict)
            return data
        except (OSError, json.JSONDecodeError) as e:
            log.warning("failed to read %s: %s", path, e)
            return None


# ---------------------------------------------------------------------------
# GCS-backed reader with in-process TTL cache.
# ---------------------------------------------------------------------------

class RemoteGcsReader:
    def __init__(
        self,
        *,
        bucket_name: str,
        prefix: str,
        service_account_json: Path | None,
        cache_seconds: int = 60,
    ) -> None:
        self.bucket_name = bucket_name
        self.prefix = prefix.strip("/")
        self.service_account_json = service_account_json
        self.cache_seconds = cache_seconds
        self._cache: dict[str, tuple[float, Any]] = {}
        self._bucket: object | None = None

    def _bucket_handle(self) -> object:
        if self._bucket is not None:
            return self._bucket
        from google.cloud import storage  # type: ignore[import-not-found]
        if self.service_account_json and self.service_account_json.exists():
            client = storage.Client.from_service_account_json(
                str(self.service_account_json),
            )
        else:
            client = storage.Client()
        self._bucket = client.bucket(self.bucket_name)
        return self._bucket

    def _cached(self, key: str):
        hit = self._cache.get(key)
        if hit and (time.monotonic() - hit[0]) < self.cache_seconds:
            return hit[1]
        return None

    def _store(self, key: str, value: Any) -> Any:
        self._cache[key] = (time.monotonic(), value)
        return value

    def list_instruments(self) -> list[str]:
        cached = self._cached("__instruments__")
        if cached is not None:
            return cached
        bucket = self._bucket_handle()
        prefix = f"{self.prefix}/"
        # iterator with delimiter to enumerate "directories".
        it = bucket.client.list_blobs(  # type: ignore[attr-defined]
            self.bucket_name, prefix=prefix, delimiter="/",
        )
        list(it)  # force pagination
        instruments = sorted(
            p.rstrip("/").split("/")[-1] for p in it.prefixes
        )
        return self._store("__instruments__", instruments)

    def list_dates_for(self, instrument_id: str) -> list[date]:
        key = f"dates::{instrument_id}"
        cached = self._cached(key)
        if cached is not None:
            return cached
        bucket = self._bucket_handle()
        prefix = f"{self.prefix}/{instrument_id}/"
        it = bucket.client.list_blobs(  # type: ignore[attr-defined]
            self.bucket_name, prefix=prefix, delimiter="/",
        )
        list(it)
        dates: list[date] = []
        for p in it.prefixes:
            dt = _iso_to_date(p.rstrip("/").split("/")[-1])
            if dt is not None:
                dates.append(dt)
        dates.sort(reverse=True)
        return self._store(key, dates)

    def read(self, instrument_id: str, target_date: date) -> dict[str, Any] | None:
        key = f"summary::{instrument_id}::{target_date.isoformat()}"
        cached = self._cached(key)
        if cached is not None:
            return cached
        bucket = self._bucket_handle()
        object_path = (
            f"{self.prefix}/{instrument_id}/{target_date.isoformat()}/summary.json"
        )
        blob = bucket.blob(object_path)  # type: ignore[attr-defined]
        if not blob.exists():
            return self._store(key, None)
        try:
            data = json.loads(blob.download_as_text())
        except (json.JSONDecodeError, OSError) as e:
            log.warning("failed to read %s: %s", object_path, e)
            return self._store(key, None)
        return self._store(key, data)
