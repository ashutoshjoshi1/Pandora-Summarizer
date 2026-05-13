# Deployment guide

This guide covers a fresh deploy of `PandoraEdgeService` on a Pandora computer
and the read-only dashboard somewhere on your network.

## Edge service (per Pandora computer)

### Prerequisites

- Windows 10 or Windows Server 2019+
- Python 3.11+ installed (system-wide, e.g. `C:\Python311\`)
- A GCS service account JSON with `storage.objectAdmin` (or
  `storage.objectCreator`) on the target bucket
- Local administrator rights for the install

### One-time setup

```powershell
# 1. clone or extract the release into a writable location
git clone <repo> C:\ProgramData\PandoraFleetMonitor\app
cd C:\ProgramData\PandoraFleetMonitor\app

# 2. create a venv and install
C:\Python311\python.exe -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[windows]"

# 3. copy the example config and edit
Copy-Item config\config.example.yaml C:\ProgramData\PandoraFleetMonitor\config.yaml
notepad C:\ProgramData\PandoraFleetMonitor\config.yaml

# 4. drop the service-account JSON in ProgramData (NOT the repo)
#    referenced from gcs.service_account_json in config.yaml

# 5. validate the config
pandora-edge validate-config --config C:\ProgramData\PandoraFleetMonitor\config.yaml

# 6. dry-run once
pandora-edge run --config C:\ProgramData\PandoraFleetMonitor\config.yaml --dry-run

# 7. install the daily scheduled task (creates "PandoraEdgeService")
pandora-edge install-task --config C:\ProgramData\PandoraFleetMonitor\config.yaml
#    OR equivalently:
.\edge_service\pandora_edge\service\install.ps1 `
    -ConfigPath C:\ProgramData\PandoraFleetMonitor\config.yaml `
    -PythonExe   C:\ProgramData\PandoraFleetMonitor\app\.venv\Scripts\python.exe `
    -RunTime     06:00
```

The scheduled task runs daily at the time defined by `service.run_time_local`.
By default it runs at 06:00 local and processes the previous day's data
(`service.process_lookback_days = 1`).

### What `install.ps1` does

1. Creates a Windows Scheduled Task named `PandoraEdgeService`.
2. Action: `<python> -m pandora_edge run --config <config>`.
3. Trigger: daily at the configured time, runs as the local SYSTEM account.
4. Tightens the ACL on `sa.json` to `SYSTEM` + `Administrators` (read).

### Verification

```powershell
# 1. confirm the task is registered
schtasks /Query /TN PandoraEdgeService

# 2. force a manual run from the Task Scheduler ("Run") or from the CLI
pandora-edge run --config C:\ProgramData\PandoraFleetMonitor\config.yaml

# 3. inspect the local log
type C:\ProgramData\PandoraFleetMonitor\logs\pandora-edge.log

# 4. confirm the summary landed in GCS
gsutil ls gs://<bucket>/pandora-fleet-monitoring/<instrument_id>/<YYYY-MM-DD>/
```

### Uninstall

```powershell
pandora-edge uninstall-task
# or:
.\edge_service\pandora_edge\service\uninstall.ps1
```

### Backfill a date range

```powershell
pandora-edge backfill `
    --config C:\ProgramData\PandoraFleetMonitor\config.yaml `
    --start  2026-05-01 `
    --end    2026-05-12
```

Backfill is idempotent: dates already marked `COMPLETED` in `state.db` are
skipped.

## Dashboard

The dashboard is a Flask app that reads `summary.json` files from GCS. It does
not need to run on the Pandora computer — deploy it wherever your operations
team accesses it.

### One-time setup

```bash
git clone <repo>
cd Pandora-Summarizer
python -m venv .venv
source .venv/bin/activate
pip install -e .

# create a *separate* dashboard service account with `storage.objectViewer` only
export PANDORA_DASH_BUCKET=log_web
export PANDORA_DASH_PREFIX=pandora-fleet-monitoring
export PANDORA_DASH_SA_JSON=/etc/pandora-dashboard/dashboard-sa.json
export PANDORA_DASH_CACHE_SECONDS=60

python -m dashboard.app
```

By default the app listens on `127.0.0.1:8080`. Override with
`PANDORA_DASH_HOST` / `PANDORA_DASH_PORT`. For production use a real WSGI
server (gunicorn / waitress) and put the app behind your existing
authentication or VPN.

### Local development without GCS

Mirror the GCS layout under a local directory and point the dashboard at it:

```
PANDORA_DASH_FIXTURES_DIR=/path/to/summaries
# layout:
#   summaries/Pandora024/2026-05-12/summary.json
#   summaries/Pandora099/2026-05-12/summary.json
```

## GCS bucket setup

```bash
# bucket itself (uniform access recommended)
gsutil mb -p <project> -l us-central1 gs://log_web

# edge writer role
gcloud projects add-iam-policy-binding <project> \
    --member="serviceAccount:pandora-edge@<project>.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

# dashboard reader role (separate account!)
gcloud projects add-iam-policy-binding <project> \
    --member="serviceAccount:pandora-dashboard@<project>.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"
```

## Cutover from `pandora-summarizer` v0.1.x

If you have an older deploy that produced L1 files alongside summaries:

1. Stop the legacy task (`schtasks /Delete /TN PandoraSummarizer /F`).
2. Existing per-day folders in GCS remain readable; new folders use the v2.0
   layout (no `l1/`, no `l2*/`).
3. Install the new task as above. The new dashboard will read both layouts as
   long as `summary.json` is present.
