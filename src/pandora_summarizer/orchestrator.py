from __future__ import annotations

import logging
import shutil
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path

from .config import Config
from .gcs import GcsUploader, UploadItem
from .state import (
    ArtifactRecord,
    DailyRunRecord,
    RunStatus,
    StateDB,
    StepLog,
    StepStatus,
)
from .steps import (
    collect_alignment,
    collect_figures,
    generate_l1,
    locate_l0,
)
from .steps.build_summary import StepStatusEntry, build_summary, write_summary
from .steps.generate_l1 import L1GenerationError

log = logging.getLogger(__name__)


def _gcs_prefix(instrument_id: str, target_date: date) -> str:
    return f"{instrument_id}/{target_date.isoformat()}"


class Orchestrator:
    def __init__(self, cfg: Config, db: StateDB, *, dry_run: bool = False) -> None:
        self.cfg = cfg
        self.db = db
        self.dry_run = dry_run

    def run_for(self, target_date: date) -> RunStatus:
        instrument = self.cfg.instrument.id
        existing = self.db.get_run(instrument, target_date)
        if existing and existing.status == RunStatus.COMPLETED:
            log.info("run already completed for %s %s; nothing to do",
                     instrument, target_date)
            return RunStatus.COMPLETED

        attempt = (existing.attempt if existing else 0) + 1
        started = datetime.now(timezone.utc)
        prefix = _gcs_prefix(instrument, target_date)

        self.db.upsert_run(DailyRunRecord(
            instrument_id=instrument,
            date_utc=target_date,
            status=RunStatus.IN_PROGRESS,
            attempt=attempt,
            started_at_utc=started,
            finished_at_utc=None,
            gcs_prefix=prefix,
        ))

        steps_report: list[StepStatusEntry] = []
        any_failed = False

        # 1. Locate L0
        l0_path: Path | None = None
        with _timed() as t:
            try:
                l0_path = locate_l0(self.cfg.paths.l0_dir, target_date)
                status = StepStatus.OK if l0_path else StepStatus.FAILED
                err = None if l0_path else f"no L0 file found for {target_date}"
            except Exception as e:  # noqa: BLE001
                status, err = StepStatus.FAILED, str(e)
        any_failed |= status != StepStatus.OK
        self._log_step(instrument, target_date, attempt, "locate_l0", status, t.ms, err)
        steps_report.append(StepStatusEntry("locate_l0", status.value, t.ms, err))

        # 2. Generate L1
        l1_path: Path | None = None
        if l0_path is not None and not self.dry_run:
            with _timed() as t:
                try:
                    l1_path = generate_l1(
                        self.cfg.paths.blickp_exe, l0_path, self.cfg.paths.l1_out_dir,
                    )
                    status, err = StepStatus.OK, None
                except L1GenerationError as e:
                    status, err = StepStatus.FAILED, str(e)
            any_failed |= status != StepStatus.OK
            self._log_step(instrument, target_date, attempt, "generate_l1", status, t.ms, err)
            steps_report.append(StepStatusEntry("generate_l1", status.value, t.ms, err))
        else:
            reason = "dry-run" if self.dry_run else "L0 missing"
            steps_report.append(StepStatusEntry(
                "generate_l1", StepStatus.SKIPPED.value, 0, reason,
            ))

        # 3. Alignment
        with _timed() as t:
            alignment_path = collect_alignment(self.cfg.paths.alignment_dir, target_date)
            status = StepStatus.OK if alignment_path else StepStatus.SKIPPED
            err = None if alignment_path else "no alignment file found"
        self._log_step(instrument, target_date, attempt, "collect_alignment", status, t.ms, err)
        steps_report.append(StepStatusEntry("collect_alignment", status.value, t.ms, err))

        # 4. Figures
        with _timed() as t:
            figures = collect_figures(self.cfg.paths.blick_figures_dir, target_date)
            status = StepStatus.OK
            err = None
        self._log_step(instrument, target_date, attempt, "collect_figures", status, t.ms, err)
        steps_report.append(StepStatusEntry(
            "collect_figures", status.value, t.ms, None, extra={"count": len(figures)},
        ))

        # Decide overall status (before upload, so summary.json reflects it).
        overall = RunStatus.PARTIAL if any_failed else RunStatus.COMPLETED

        # 5. Stage + upload
        with tempfile.TemporaryDirectory(prefix="pandora-stage-") as staging_str:
            staging = Path(staging_str)
            data_dir = staging / "data"
            data_dir.mkdir(parents=True)
            figures_dir = data_dir / "figures"
            figures_dir.mkdir(parents=True)

            items: list[UploadItem] = []

            if l0_path and l0_path.exists():
                local = data_dir / l0_path.name
                shutil.copy2(l0_path, local)
                items.append(UploadItem(local, f"{prefix}/data/{l0_path.name}"))
                self._record_artifact(instrument, target_date, "L0", l0_path,
                                      f"{prefix}/data/{l0_path.name}")

            if l1_path and l1_path.exists():
                local = data_dir / l1_path.name
                shutil.copy2(l1_path, local)
                items.append(UploadItem(local, f"{prefix}/data/{l1_path.name}"))
                self._record_artifact(instrument, target_date, "L1", l1_path,
                                      f"{prefix}/data/{l1_path.name}")

            if alignment_path and alignment_path.exists():
                local = data_dir / alignment_path.name
                shutil.copy2(alignment_path, local)
                items.append(UploadItem(local, f"{prefix}/data/{alignment_path.name}"))
                self._record_artifact(instrument, target_date, "ALIGNMENT", alignment_path,
                                      f"{prefix}/data/{alignment_path.name}")

            for fig in figures:
                local = figures_dir / fig.name
                shutil.copy2(fig, local)
                items.append(UploadItem(local, f"{prefix}/data/figures/{fig.name}"))
                self._record_artifact(instrument, target_date, "FIGURE", fig,
                                      f"{prefix}/data/figures/{fig.name}")

            finished = datetime.now(timezone.utc)
            summary = build_summary(
                instrument_id=instrument,
                target_date=target_date,
                l0_path=l0_path,
                l1_path=l1_path,
                alignment_path=alignment_path,
                figures=figures,
                overall_status=overall.value,
                attempt=attempt,
                started_at=started,
                finished_at=finished,
                steps=steps_report,
            )
            summary_local = staging / "summary.json"
            write_summary(summary, summary_local)
            items.append(UploadItem(summary_local, f"{prefix}/summary.json"))

            uploader = GcsUploader(
                bucket_name=self.cfg.gcs.bucket,
                service_account_json=self.cfg.gcs.service_account_json,
                overwrite_existing=self.cfg.gcs.overwrite_existing,
                dry_run=self.dry_run,
            )

            with _timed() as t:
                try:
                    count, total_bytes = uploader.upload_many(items)
                    status, err = StepStatus.OK, None
                except Exception as e:  # noqa: BLE001
                    count, total_bytes = 0, 0
                    status, err = StepStatus.FAILED, str(e)
                    overall = RunStatus.FAILED
            self._log_step(instrument, target_date, attempt, "upload_gcs", status, t.ms, err)
            steps_report.append(StepStatusEntry(
                "upload_gcs", status.value, t.ms, err,
                extra={"objects_uploaded": count, "bytes_uploaded": total_bytes},
            ))

        finished = datetime.now(timezone.utc)
        self.db.upsert_run(DailyRunRecord(
            instrument_id=instrument,
            date_utc=target_date,
            status=overall,
            attempt=attempt,
            started_at_utc=started,
            finished_at_utc=finished,
            gcs_prefix=prefix,
        ))
        log.info("run finished: %s %s status=%s attempt=%d",
                 instrument, target_date, overall.value, attempt)
        return overall

    # -- helpers ------------------------------------------------------------

    def _log_step(
        self,
        instrument: str,
        target_date: date,
        attempt: int,
        name: str,
        status: StepStatus,
        duration_ms: int,
        error: str | None,
    ) -> None:
        self.db.append_step(StepLog(
            instrument_id=instrument,
            date_utc=target_date,
            attempt=attempt,
            step_name=name,
            status=status,
            duration_ms=duration_ms,
            error_text=error,
        ))

    def _record_artifact(
        self,
        instrument: str,
        target_date: date,
        kind: str,
        local: Path,
        gcs_path: str,
    ) -> None:
        self.db.upsert_artifact(ArtifactRecord(
            instrument_id=instrument,
            date_utc=target_date,
            kind=kind,
            filename=local.name,
            size_bytes=local.stat().st_size if local.exists() else 0,
            sha256=None,
            gcs_object_path=gcs_path,
        ))


class _timed:
    """Context manager that captures wall-clock duration in ms."""
    def __enter__(self) -> "_timed":
        self._t0 = time.perf_counter()
        self.ms = 0
        return self

    def __exit__(self, *_: object) -> None:
        self.ms = int((time.perf_counter() - self._t0) * 1000)
