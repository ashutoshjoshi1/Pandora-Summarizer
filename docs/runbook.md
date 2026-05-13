# Operations runbook

Day-to-day operation of `PandoraEdgeService` and the dashboard.

## Daily checks

1. Open the dashboard. The Fleet Overview lists every instrument with its
   latest `summary.json`.
2. Anything `RED` or `OFFLINE` deserves immediate attention. Anything `YELLOW`
   should be reviewed the same day.
3. Open the **Daily Report** for today's date and scan:
   - Units with critical errors.
   - Units missing L0 / status data.
   - Units with bad alignment.
   - Units with failed uploads.

If everything is `GREEN`, you're done.

## Common operator commands

```powershell
# Validate config after editing
pandora-edge validate-config --config C:\ProgramData\PandoraFleetMonitor\config.yaml

# Re-run for yesterday (will retry if previous run was PARTIAL/FAILED)
pandora-edge run --config <path>

# Run for a specific date
pandora-edge run --date 2026-05-10 --config <path>

# Dry run (no GCS upload)
pandora-edge run --date 2026-05-10 --config <path> --dry-run

# Backfill a range
pandora-edge backfill --start 2026-05-01 --end 2026-05-10 --config <path>
```

## Where everything lives

| Item                    | Default location                                      |
|-------------------------|-------------------------------------------------------|
| Config                  | `C:\ProgramData\PandoraFleetMonitor\config.yaml`      |
| Service account JSON    | `C:\ProgramData\PandoraFleetMonitor\sa.json`          |
| Local state             | `C:\ProgramData\PandoraFleetMonitor\state.db`         |
| Staging                 | `C:\ProgramData\PandoraFleetMonitor\staging\<id>\<date>\` |
| Local logs              | `C:\ProgramData\PandoraFleetMonitor\logs\`            |
| Scheduled task          | Task Scheduler → `PandoraEdgeService`                 |

## How an idempotent run works

1. The orchestrator looks up `(instrument_id, target_date)` in `state.db`.
2. If `status = COMPLETED`, the run is skipped.
3. Otherwise the attempt counter is incremented and the full pipeline runs.
4. Each step is wrapped in a safe-step harness; failures don't crash the run.
5. `summary.json` is **always** produced; failures appear in
   `service_status.errors`.

To force a re-run of a completed date:

```powershell
# remove only the run record (not the step / artifact history)
sqlite3 C:\ProgramData\PandoraFleetMonitor\state.db `
    "DELETE FROM daily_runs WHERE instrument_id='PandoraXXX' AND date_utc='YYYY-MM-DD';"

pandora-edge run --date YYYY-MM-DD --config <path>
```

## Healthy run fingerprint

A clean daily run looks like this in `pandora-edge.log`:

```
INFO pandora_edge.orchestrator :: run finished: Pandora024 2026-05-12
     status=COMPLETED attempt=1 score=95/GREEN
```

And in GCS:

```
gs://<bucket>/pandora-fleet-monitoring/Pandora024/2026-05-12/
    summary.json
    manifest.json
    data/l0/...
    data/partial_l0/...
    data/alignment/...
    data/logs/oslog/...
    data/logs/fslog/...
    data/logs/pslog/...
    data/figures/...
```

## Adding a new Pandora to the fleet

1. Bring the new computer online with Blick configured normally.
2. Copy this repo to `C:\ProgramData\PandoraFleetMonitor\app`.
3. Copy `config.example.yaml` → `config.yaml`. Edit:
   - `instrument.id` (e.g. `Pandora123`)
   - `instrument.display_name`
   - `instrument.location_name`
   - `instrument.timezone`
   - Path overrides if the Blick install is non-default.
4. Run `pandora-edge install-task`. The dashboard will pick up the new
   instrument automatically on the next daily run.

## Removing a Pandora from the fleet

1. Uninstall the task: `pandora-edge uninstall-task`.
2. Optionally archive `gs://<bucket>/pandora-fleet-monitoring/<id>/` to cold
   storage. The dashboard still lists historical dates as long as
   `summary.json` is present.

## Auditing what was uploaded

Every upload is recorded in `manifest.json` next to the corresponding
`summary.json`. Each row has `filename`, `artifact_type`, `size_bytes`,
`sha256`, `gcs_object`, and `uploaded_at_utc`. Use it to verify file integrity
without re-downloading the data files.
