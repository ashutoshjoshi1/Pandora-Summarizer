"""End-to-end orchestrator. Never raises out of run_for() — failures are
captured into summary.json's service_status.errors."""
from __future__ import annotations

import logging
import shutil
import tempfile
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator

from .config import Config
from .gcs import UploadResult
from .parsers import AlignmentInfo, FileInventory, L0Info, LogRollup
from .state import (
    DailyRunRecord,
    RunStatus,
    StateDB,
    StepLog,
    StepStatus,
)
from .steps import (
    build_summary,
    locate_files,
    parse_alignment,
    parse_l0_status,
    parse_logs,
    stage_bundle,
    upload_bundle,
    write_manifest,
    write_summary,
)
from .steps.build_summary import StepStatusEntry
from .steps.upload_gcs import finalize_upload

log = logging.getLogger(__name__)


@dataclass
class _Timer:
    ms: int = 0


@contextmanager
def _timed() -> Iterator[_Timer]:
    t = _Timer()
    t0 = time.perf_counter()
    try:
        yield t
    finally:
        t.ms = int((time.perf_counter() - t0) * 1000)


def _gcs_prefix(cfg: Config, target_date: date) -> str:
    base = cfg.gcs.prefix.strip("/")
    return f"{base}/{cfg.instrument.id}/{target_date.isoformat()}"


class Orchestrator:
    def __init__(self, cfg: Config, db: StateDB, *, dry_run: bool = False) -> None:
        self.cfg = cfg
        self.db = db
        self.dry_run = dry_run
        self._target_date: date = date.today()
        self._attempt: int = 0

    def run_for(self, target_date: date) -> RunStatus:
        instrument = self.cfg.instrument.id
        existing = self.db.get_run(instrument, target_date)
        if existing and existing.status == RunStatus.COMPLETED:
            log.info("run already completed for %s %s; nothing to do",
                     instrument, target_date)
            return RunStatus.COMPLETED

        attempt = (existing.attempt if existing else 0) + 1
        self._target_date = target_date
        self._attempt = attempt
        started = datetime.now(timezone.utc)
        prefix = _gcs_prefix(self.cfg, target_date)

        self.db.upsert_run(DailyRunRecord(
            instrument_id=instrument, date_utc=target_date,
            status=RunStatus.IN_PROGRESS, attempt=attempt,
            started_at_utc=started, finished_at_utc=None, gcs_prefix=prefix,
        ))

        steps: list[StepStatusEntry] = []
        errors: list[str] = []

        inventory = self._safe_step(
            "locate_files", steps, errors,
            lambda: locate_files(self.cfg, target_date),
            fallback=FileInventory(target_date=target_date),
        )
        l0_info = self._safe_step(
            "parse_l0_status", steps, errors,
            lambda: parse_l0_status(inventory),
            fallback=L0Info(),
        )
        log_info = self._safe_step(
            "parse_logs", steps, errors,
            lambda: parse_logs(inventory),
            fallback=LogRollup(),
        )
        alignment_info = self._safe_step(
            "parse_alignment", steps, errors,
            lambda: parse_alignment(inventory, self.cfg.health_thresholds),
            fallback=AlignmentInfo(),
        )

        upload_started: datetime | None = None
        upload_finished: datetime | None = None
        upload_result = UploadResult(status="FAILED")

        staging_base = self.cfg.state.staging_dir
        if staging_base is None:
            staging_ctx = tempfile.TemporaryDirectory(prefix="pandora-stage-")
            staging_root = Path(staging_ctx.name)
        else:
            staging_base.mkdir(parents=True, exist_ok=True)
            staging_root = staging_base / instrument / target_date.isoformat()
            if staging_root.exists():
                shutil.rmtree(staging_root, ignore_errors=True)
            staging_root.mkdir(parents=True, exist_ok=True)
            staging_ctx = None  # type: ignore[assignment]

        try:
            bundle = self._safe_step(
                "stage_bundle", steps, errors,
                lambda: stage_bundle(
                    cfg=self.cfg, staging_root=staging_root,
                    inventory=inventory, gcs_prefix=prefix,
                ),
                fallback=None,
            )

            if bundle is not None:
                upload_started = datetime.now(timezone.utc)
                upload_result = self._safe_step(
                    "upload_data", steps, errors,
                    lambda: upload_bundle(
                        bundle, self.cfg, gcs_prefix=prefix, dry_run=self.dry_run,
                    ),
                    fallback=UploadResult(status="FAILED"),
                )
                upload_finished = datetime.now(timezone.utc)

            finished = datetime.now(timezone.utc)
            summary = self._safe_step(
                "build_summary", steps, errors,
                lambda: build_summary(
                    cfg=self.cfg,
                    target_date=target_date,
                    inventory=inventory,
                    l0=l0_info,
                    logs=log_info,
                    alignment=alignment_info,
                    upload=upload_result,
                    upload_started_at_utc=upload_started,
                    upload_finished_at_utc=upload_finished,
                    gcs_prefix=prefix,
                    attempt=attempt,
                    started_at=started,
                    finished_at=finished,
                    steps=steps,
                    service_errors=errors,
                ),
                fallback={
                    "health": {"daily_health_score": 0, "daily_health_label": "GRAY"},
                    "service_status": {"overall": "FAILED"},
                },
            )

            if bundle is not None:
                self._safe_step(
                    "write_summary", steps, errors,
                    lambda: write_summary(summary, bundle.summary_path),
                    fallback=None,
                )
                self._safe_step(
                    "write_manifest", steps, errors,
                    lambda: write_manifest(
                        bundle, instrument_id=instrument,
                        target_date=target_date.isoformat(),
                        gcs_prefix=prefix,
                    ),
                    fallback=None,
                )
                upload_result = self._safe_step(
                    "upload_summary_manifest", steps, errors,
                    lambda: finalize_upload(
                        bundle, self.cfg, gcs_prefix=prefix,
                        data_result=upload_result, dry_run=self.dry_run,
                    ),
                    fallback=upload_result,
                )
        finally:
            if staging_ctx is not None:
                staging_ctx.cleanup()

        finished = datetime.now(timezone.utc)
        score = summary["health"]["daily_health_score"]
        label = summary["health"]["daily_health_label"]
        overall_str = summary["service_status"]["overall"]
        overall = RunStatus(overall_str) if overall_str in RunStatus.__members__ \
            else RunStatus.PARTIAL

        self.db.upsert_run(DailyRunRecord(
            instrument_id=instrument, date_utc=target_date,
            status=overall, attempt=attempt,
            started_at_utc=started, finished_at_utc=finished, gcs_prefix=prefix,
            health_score=score, health_label=label,
        ))
        log.info("run finished: %s %s status=%s attempt=%d score=%d/%s",
                 instrument, target_date, overall.value, attempt, score, label)
        return overall

    def _safe_step(
        self, name: str, steps: list[StepStatusEntry], errors: list[str],
        fn, *, fallback,
    ):
        with _timed() as t:
            try:
                result = fn()
                steps.append(StepStatusEntry(name=name, status=StepStatus.OK.value,
                                             duration_ms=t.ms))
                self._record_step(name, StepStatus.OK, t.ms, None)
                return result
            except Exception as e:  # noqa: BLE001 - intentional broad capture
                msg = f"{type(e).__name__}: {e}"
                tb = traceback.format_exc(limit=4)
                log.exception("step %s failed", name)
                errors.append(f"{name}: {msg}")
                steps.append(StepStatusEntry(name=name, status=StepStatus.FAILED.value,
                                             duration_ms=t.ms, error=msg,
                                             extra={"trace": tb[:1000]}))
                self._record_step(name, StepStatus.FAILED, t.ms, msg)
                return fallback

    def _record_step(self, name: str, status: StepStatus, duration_ms: int,
                     err: str | None) -> None:
        try:
            self.db.append_step(StepLog(
                instrument_id=self.cfg.instrument.id,
                date_utc=self._target_date,
                attempt=self._attempt,
                step_name=name, status=status, duration_ms=duration_ms,
                error_text=err,
            ))
        except Exception:  # noqa: BLE001 - state recording must never break the run
            log.warning("failed to persist step log %s", name)
