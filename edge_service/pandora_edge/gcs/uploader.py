"""GCS uploader with retry, dry-run, and per-file failure tracking."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    pass  # google-cloud-storage imported lazily inside _client()

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadItem:
    local_path: Path
    object_path: str  # full object path relative to bucket root
    content_type: str | None = None


@dataclass
class UploadResult:
    status: str = "COMPLETED"   # COMPLETED | PARTIAL | FAILED
    uploaded_objects_count: int = 0
    uploaded_bytes: int = 0
    failed_uploads: list[dict[str, str]] = field(default_factory=list)
    retry_count: int = 0


class GcsUploader:
    def __init__(
        self,
        *,
        bucket_name: str,
        service_account_json: Path | None,
        overwrite_existing: bool = True,
        retry_attempts: int = 3,
        dry_run: bool = False,
    ) -> None:
        self.bucket_name = bucket_name
        self.service_account_json = service_account_json
        self.overwrite_existing = overwrite_existing
        self.retry_attempts = retry_attempts
        self.dry_run = dry_run
        self._bucket: object | None = None  # lazy

    def _bucket_handle(self) -> object:
        if self._bucket is not None:
            return self._bucket
        # Imported lazily so tests / dry-runs don't require google-cloud-storage.
        from google.cloud import storage  # type: ignore[import-not-found]

        if self.service_account_json and Path(self.service_account_json).exists():
            client = storage.Client.from_service_account_json(str(self.service_account_json))
        else:
            client = storage.Client()
        self._bucket = client.bucket(self.bucket_name)
        return self._bucket

    def _upload_one(self, item: UploadItem) -> int:
        if self.dry_run:
            log.info("DRY-RUN upload %s -> gs://%s/%s",
                     item.local_path, self.bucket_name, item.object_path)
            return item.local_path.stat().st_size if item.local_path.exists() else 0

        bucket = self._bucket_handle()
        blob = bucket.blob(item.object_path)  # type: ignore[attr-defined]
        if blob.exists() and not self.overwrite_existing:
            log.info("skipping existing object %s", item.object_path)
            return 0
        blob.upload_from_filename(
            str(item.local_path),
            content_type=item.content_type,
        )
        return item.local_path.stat().st_size

    def upload_many(self, items: list[UploadItem]) -> UploadResult:
        result = UploadResult()
        for item in items:
            try:
                size = self._with_retry(item, result)
                result.uploaded_objects_count += 1
                result.uploaded_bytes += size
            except Exception as e:  # noqa: BLE001 - we surface error per-item
                log.error("upload failed for %s: %s", item.object_path, e)
                result.failed_uploads.append({
                    "object_path": item.object_path,
                    "error": str(e)[:300],
                })

        if result.failed_uploads and result.uploaded_objects_count == 0:
            result.status = "FAILED"
        elif result.failed_uploads:
            result.status = "PARTIAL"
        return result

    def _with_retry(self, item: UploadItem, result: UploadResult) -> int:
        attempts = 0

        def _do() -> int:
            nonlocal attempts
            attempts += 1
            return self._upload_one(item)

        try:
            for attempt in Retrying(
                stop=stop_after_attempt(self.retry_attempts),
                wait=wait_exponential(multiplier=2, min=2, max=30),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
                    size = _do()
            result.retry_count += max(attempts - 1, 0)
            return size
        except RetryError as e:  # pragma: no cover - tenacity reraise=True path
            raise e
