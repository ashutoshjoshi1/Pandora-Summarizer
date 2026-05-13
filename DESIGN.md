# Pandora Fleet Monitoring Platform — Design Document

**Version:** 2.0
**Status:** Implemented (Phase 1–9)

---

## 1. Goal

Operate a fleet of Pandora spectral measurement instruments by producing a
deterministic daily `summary.json` per instrument and surfacing fleet health
through a read-only web dashboard. All processing is local to each Pandora
computer; Google Cloud Storage is a passive storage layer.

### 1.1 Non-goals

- Real-time streaming of measurements.
- L1, L2Fit, or L2 generation, parsing, upload, or display.
- Centralized control plane. The dashboard is read-only.
- Sub-daily summarization (the unit of work is one day per instrument).

## 2. Three layers

```
┌─────────────────────┐     ┌────────────────────┐    ┌──────────────────┐
│  Edge service       │ ──► │  GCS (passive)     │ ◄─ │  Web dashboard   │
│  PandoraEdgeService │     │  summary.json +    │    │  Flask, read-    │
│  (Windows, daily)   │     │  manifest +        │    │  only            │
└─────────────────────┘     │  data/{l0, …}      │    └──────────────────┘
                            └────────────────────┘
```

### 2.1 Edge service responsibilities

1. Discover Blick files for a target date.
2. Parse L0 / partial-L0 status, oslog / fslog / pslog, alignment files.
3. Compute online status, alignment health, tracker health, warning / error
   rollups, and a 0–100 daily health score.
4. Stage a deterministic bundle in a local staging directory.
5. Upload `data/...` to GCS, then upload `summary.json` and `manifest.json`
   (so `summary.upload` reflects the actual outcome).
6. Persist run state in a local SQLite database so retries are idempotent.

### 2.2 GCS responsibilities

Only storage. No Cloud Functions, no triggers, no compute.

Object layout:

```
gs://<bucket>/<prefix>/<instrument_id>/<YYYY-MM-DD>/
    summary.json
    manifest.json
    data/
        l0/           — original Blick L0 files (configurable)
        partial_l0/   — partial / status files
        alignment/    — alignment scan files
        logs/
            oslog/, fslog/, pslog/
        figures/      — diagnostic figures (configurable)
```

There are no `l1/`, `l2fit/`, or `l2/` paths.

### 2.3 Dashboard responsibilities

- List instruments and dates from GCS object listings.
- Read each `summary.json` into a `SummaryRecord`.
- Aggregate records into fleet-level snapshots.
- Render: fleet overview, instrument detail, daily report, CSV export.
- Never compute raw metrics from Blick files; only consume `summary.json`.

## 3. Edge pipeline

Implemented in `edge_service/pandora_edge/orchestrator.py`.

```
locate_files
    └─ FileInventory (l0, partial_l0, oslog, fslog, pslog, alignment, figures,
                      skipped_unstable)
parse_l0_status     → L0Info
parse_logs          → LogRollup
parse_alignment     → AlignmentInfo
stage_bundle        → staged files under <staging>/data/...
upload_data         → GCS upload (data only)
build_summary       → summary.json dict (schema v2.0)
write_summary       → <staging>/summary.json
write_manifest      → <staging>/manifest.json
upload_summary_manifest
```

Every step is wrapped in `_safe_step`. A step failure is recorded in
`service_status.errors` and surfaced as a `FAILED` step entry, but the run
continues and a `summary.json` is always produced (possibly with `GRAY` health
and `service_status.overall == "FAILED"`).

## 4. summary.json schema v2.0

See `docs/examples/summary.json` for a complete sample. Top-level sections:

- `host` — hostname, OS, service version, instrument display name + location.
- `status` — online status, `last_seen_utc`, `last_log_received_utc`,
  `last_file_received_utc`, offline reason, list of missing expected files.
- `operation` — mode, schedule, routine, measurement count, L0 file counts,
  routines observed.
- `logs` — total warning / error counts, top-10 repeated warnings,
  critical errors, first / last observation timestamps.
- `tracker` — connected flag, reset count, categorical health.
- `sun_search` — last sun-search time, status, RMS / offset / FWHM,
  pointing azimuth / zenith.
- `alignment` — file presence, latest scan type / weighting factor / RMS,
  good / bad scan counts, categorical health, comment per spec.
- `files` — per-artifact-type presence, names, sizes, SHA-256, modified UTC,
  and a `skipped_unstable` list (files still being written by Blick).
- `upload` — status (COMPLETED / PARTIAL / FAILED), object count, bytes,
  failed uploads, retry count, GCS prefix.
- `health` — `daily_health_score`, `daily_health_label`, score breakdown,
  human-readable summary.
- `service_status` — overall status, attempt, duration seconds, per-step
  entries, and `errors` (a list of human-readable error strings).

## 5. Health scoring

Deductions from a 100 baseline (see `edge_service/pandora_edge/health/scoring.py`):

| Trigger                                               | Penalty |
|-------------------------------------------------------|---------|
| Offline                                               | 40      |
| No L0 and no partial L0                               | 25      |
| Warnings ≥ red threshold                              | 20      |
| Warnings ≥ yellow threshold                           | 10      |
| Errors ≥ red threshold                                | 25      |
| Errors ≥ yellow threshold                             | 15      |
| Alignment CRITICAL                                    | 15      |
| Alignment WARNING                                     | 5       |
| Tracker CRITICAL or reset count ≥ threshold           | 10      |
| Failed sun search count ≥ threshold                   | 10      |
| Upload FAILED                                         | 20      |
| Upload PARTIAL                                        | 10      |

Clamped to [0, 100]. Labels:

- `GREEN`  85–100
- `YELLOW` 60–84
- `RED`    0–59
- `GRAY`   online status is UNKNOWN (no usable data)

## 6. Idempotency & reliability

- SQLite `state.db` records the (instrument, date) status. If a previous run
  completed, the orchestrator skips re-execution.
- A previous `PARTIAL` or `FAILED` run increments the attempt counter and
  retries the full pipeline.
- File-stability gate: any file whose mtime is within
  `service.file_stability_seconds` (default 60s) is skipped to avoid reading
  files Blick is actively writing. Skipped paths are surfaced in
  `summary.files.skipped_unstable`.
- GCS uploads retry with exponential backoff (tenacity).
- Local files are never deleted.

## 7. Security

- Service account JSON lives in `ProgramData\PandoraFleetMonitor\` and is ACL'd
  to `SYSTEM` + `Administrators` by `install.ps1`.
- The repo `.gitignore` excludes `sa.json`, `service-account*.json`,
  `credentials.json`, `state.db*`, and `config/config.yaml`.
- `summary.json` does not embed full Windows paths — only filenames and
  artifact types.
- Dashboard expects a read-only GCS service account (`storage.objectViewer`)
  separate from the edge writer.

## 8. Dashboard

Flask app factory at `dashboard/app.py`.

- `services/gcs_reader.py` — `SummaryReader` Protocol with `LocalReader` (dev)
  and `RemoteGcsReader` (production, with TTL cache).
- `services/summary_loader.py` — flattens a raw `summary.json` into a
  `SummaryRecord` dataclass, tolerant of missing fields.
- `services/fleet_aggregator.py` — builds `FleetSnapshot` and computes derived
  views (units with errors, missing L0, bad alignment, failed upload).
- `routes/fleet.py` — fleet overview + filters.
- `routes/instrument.py` — per-instrument detail with 30-day trend.
- `routes/reports.py` — daily report (counts + categorized lists).
- `routes/export.py` — CSV export mirroring the visible fleet table.

## 9. Repository layout

See `README.md`.

## 10. Out of scope

- L1 / L2Fit / L2 generation, parsing, upload, display.
- Real-time alerting (Slack / PagerDuty etc.).
- Multi-tenant dashboards with auth — the dashboard is intended for internal
  read-only deployment behind existing network controls.

## 11. Future work

- Optional Pub/Sub notification on summary upload to power alerting without
  adding cloud-side parsing.
- Long-term trend storage outside per-day summaries (the dashboard currently
  derives trends from the per-day files directly).
