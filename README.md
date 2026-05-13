# Pandora Fleet Monitoring Platform

Edge-heavy monitoring for a fleet of Pandora spectral measurement instruments.

- **Edge service** runs on each Pandora computer (Windows). It reads Blick L0,
  partial-L0/status files, oslog / fslog / pslog, alignment files, and figures
  **locally**, builds a daily `summary.json` with online status, warning /
  error rollups, alignment health, tracker health, and a 0–100 health score,
  then uploads to Google Cloud Storage.
- **GCS** is a passive storage layer. No cloud compute.
- **Dashboard** (Flask + Jinja, read-only) reads `summary.json` files from GCS
  and renders fleet overview, per-instrument detail, and daily reports.

L1, L2Fit, and L2 files are **not** part of this workflow and are not produced,
parsed, uploaded, or displayed anywhere.

## Repo layout

```
config/config.example.yaml                Edge config (copy to config.yaml).
edge_service/pandora_edge/                The edge service package.
  cli.py                                  pandora-edge CLI.
  orchestrator.py                         Never-crash pipeline.
  config.py                               Pydantic schema.
  parsers/                                L0, status-line, log, alignment, file inventory.
  health/                                 Rules + scoring.
  steps/                                  Pipeline steps.
  gcs/uploader.py                         GCS uploader with retry.
  service/                                Windows install / uninstall scripts.
dashboard/                                Flask app reading summaries from GCS.
  app.py
  config.py
  services/                               gcs_reader, summary_loader, fleet_aggregator.
  routes/                                 fleet / instrument / reports / export.
  templates/, static/
tests/                                    Unit + dashboard tests.
docs/                                     Runbook, troubleshooting, deployment.
```

## Quick start

### On a Pandora computer (field install)

The complete, non-technical walkthrough for someone visiting a Pandora
computer with a USB stick is **[`INSTALL-ON-PANDORA.md`](INSTALL-ON-PANDORA.md)**.
A one-page printable checklist is **[`FIELD-CHECKLIST.txt`](FIELD-CHECKLIST.txt)**.

Short version:

1. Copy this entire folder onto the Pandora computer.
2. Install Python 3.11+ from python.org (tick "Add python.exe to PATH").
3. Drop the GCS service-account key at
   `C:\ProgramData\PandoraFleetMonitor\sa.json`.
4. Double-click **`Run-Setup.bat`** and accept the UAC prompt.
5. Edit `config.yaml` when Notepad opens, save, close.
6. Double-click **`Run-Pandora-Now.bat`** to test.

For on-demand runs after install, double-click `Run-Pandora-Now.bat`. To
uninstall, double-click `Run-Uninstall.bat`.

### Manual / dev install

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"

cp config/config.example.yaml config/config.yaml
edit config/config.yaml

pandora-edge validate-config --config config/config.yaml
pandora-edge run --config config/config.yaml --dry-run
pandora-edge run --config config/config.yaml
pandora-edge install-task --config config/config.yaml
```

See [`docs/deployment.md`](docs/deployment.md) for the full deployment
reference and [`docs/runbook.md`](docs/runbook.md) for daily operations.

## CLI

```
pandora-edge run --date YYYY-MM-DD [--dry-run]
pandora-edge backfill --start YYYY-MM-DD --end YYYY-MM-DD [--dry-run]
pandora-edge validate-config
pandora-edge install-task
pandora-edge uninstall-task
```

If `--date` is omitted, the target date is `today - process_lookback_days`
(default: yesterday).

## GCS layout

```
gs://<bucket>/pandora-fleet-monitoring/<instrument_id>/<YYYY-MM-DD>/
  summary.json
  manifest.json
  data/
    l0/...
    partial_l0/...
    alignment/...
    logs/
      oslog/...
      fslog/...
      pslog/...
    figures/...
```

There are no `l1/`, `l2fit/`, or `l2/` folders by design.

## Dashboard

```bash
# environment-driven configuration
set PANDORA_DASH_BUCKET=log_web
set PANDORA_DASH_PREFIX=pandora-fleet-monitoring
set PANDORA_DASH_SA_JSON=C:\ProgramData\PandoraFleetMonitor\dashboard-sa.json

python -m dashboard.app
# or:
pandora-dashboard
```

For local development without GCS, point the dashboard at a directory of
fixtures with the same layout:

```bash
set PANDORA_DASH_FIXTURES_DIR=C:\dev\summaries
```

See [`docs/runbook.md`](docs/runbook.md) and the example summary at
[`docs/examples/summary.json`](docs/examples/summary.json).

## Tests

```bash
pytest -q                                          # full suite
pytest tests/edge_service/test_smoke.py            # full pipeline smoke test
pytest tests/dashboard                             # dashboard only
pytest --cov=edge_service --cov=dashboard          # coverage
```

## License

Internal / not released. See repository owner.
