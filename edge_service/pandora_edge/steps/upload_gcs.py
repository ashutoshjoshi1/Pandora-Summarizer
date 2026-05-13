"""Step: upload a staged bundle to GCS."""
from __future__ import annotations

from ..config import Config
from ..gcs import GcsUploader, UploadItem, UploadResult
from .stage_bundle import StagedBundle


def upload_bundle(
    bundle: StagedBundle,
    cfg: Config,
    *,
    gcs_prefix: str,
    dry_run: bool = False,
) -> UploadResult:
    """Upload data files, then upload summary.json + manifest.json last.

    Summary/manifest are uploaded after data so their content can reflect the
    actual upload result.
    """
    uploader = GcsUploader(
        bucket_name=cfg.gcs.bucket,
        service_account_json=cfg.gcs.service_account_json,
        overwrite_existing=cfg.gcs.overwrite_existing,
        retry_attempts=cfg.service.retry_attempts,
        dry_run=dry_run,
    )

    data_result = uploader.upload_many(bundle.items)

    # Caller is expected to write summary.json + manifest.json AFTER this
    # function returns (to capture data_result inside summary), then call
    # finalize_upload to upload the two manifests.
    return data_result


def finalize_upload(
    bundle: StagedBundle,
    cfg: Config,
    *,
    gcs_prefix: str,
    data_result: UploadResult,
    dry_run: bool = False,
) -> UploadResult:
    """Upload summary.json + manifest.json after they have been written."""
    uploader = GcsUploader(
        bucket_name=cfg.gcs.bucket,
        service_account_json=cfg.gcs.service_account_json,
        overwrite_existing=cfg.gcs.overwrite_existing,
        retry_attempts=cfg.service.retry_attempts,
        dry_run=dry_run,
    )
    extras: list[UploadItem] = []
    if bundle.summary_path.exists():
        extras.append(UploadItem(
            local_path=bundle.summary_path,
            object_path=f"{gcs_prefix}/summary.json",
            content_type="application/json",
        ))
    if bundle.manifest_path.exists():
        extras.append(UploadItem(
            local_path=bundle.manifest_path,
            object_path=f"{gcs_prefix}/manifest.json",
            content_type="application/json",
        ))
    extra_result = uploader.upload_many(extras)
    # Merge into the data_result for a single summary.
    data_result.uploaded_objects_count += extra_result.uploaded_objects_count
    data_result.uploaded_bytes += extra_result.uploaded_bytes
    data_result.failed_uploads.extend(extra_result.failed_uploads)
    data_result.retry_count += extra_result.retry_count
    if extra_result.status == "FAILED" and data_result.status == "COMPLETED":
        data_result.status = "PARTIAL"
    elif extra_result.status == "PARTIAL" and data_result.status == "COMPLETED":
        data_result.status = "PARTIAL"
    return data_result
