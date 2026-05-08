from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from google.cloud.storage import Bucket  # type: ignore

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadItem:
    local_path: Path
    object_path: str  # path within bucket, e.g. "Pan100/2026-05-01/data/foo.txt"


class GcsUploader:
    def __init__(
        self,
        bucket_name: str,
        service_account_json: Path | None,
        *,
        overwrite_existing: bool = True,
        dry_run: bool = False,
    ) -> None:
        self.bucket_name = bucket_name
        self.sa_json = service_account_json
        self.overwrite = overwrite_existing
        self.dry_run = dry_run
        self._bucket: Bucket | None = None

    def _bucket_lazy(self) -> Bucket:
        if self._bucket is not None:
            return self._bucket
        # Imported lazily so dry-run / tests don't require GCS credentials.
        from google.cloud import storage  # type: ignore

        if self.sa_json is not None:
            client = storage.Client.from_service_account_json(str(self.sa_json))
        else:
            client = storage.Client()
        self._bucket = client.bucket(self.bucket_name)
        return self._bucket

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(Exception),
    )
    def upload_one(self, item: UploadItem) -> int:
        if self.dry_run:
            log.info(
                "[dry-run] would upload %s -> gs://%s/%s",
                item.local_path, self.bucket_name, item.object_path,
            )
            return item.local_path.stat().st_size if item.local_path.exists() else 0

        bucket = self._bucket_lazy()
        blob = bucket.blob(item.object_path)
        if not self.overwrite and blob.exists():
            log.info("skip existing object: %s", item.object_path)
            return 0
        blob.upload_from_filename(str(item.local_path))
        return item.local_path.stat().st_size

    def upload_many(self, items: list[UploadItem]) -> tuple[int, int]:
        """Returns (uploaded_count, total_bytes). Raises on first hard failure
        after retries are exhausted; per-item retries are handled in upload_one."""
        total = 0
        count = 0
        for it in items:
            total += self.upload_one(it)
            count += 1
        return count, total
