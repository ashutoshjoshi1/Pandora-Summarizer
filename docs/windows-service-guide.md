# Pandora Summarizer — Windows Operations Guide

Complete instructions for installing and running Pandora Summarizer on a Pandora instrument PC.

> **Note on "service" vs "scheduled task"**: Pandora Summarizer is a once-per-day batch job. The recommended deployment is **Windows Task Scheduler** (Option A below) — it is simpler, easier to monitor, and matches the workload. A true Windows Service via NSSM (Option B) is supported for sites that have a standard requiring it. Pick one — do not run both.

---

## 1. Prerequisites

On every Pandora PC where the summarizer will run:

| Requirement | Notes |
|---|---|
| Windows 10 / 11 (64-bit) or Windows Server 2019+ | Confirmed environment for BlickP. |
| Python 3.11 or 3.12 (64-bit) | Install for **All Users** to `C:\Python311`. Tick "Add Python to PATH". |
| Local administrator access | Needed to install to `Program Files` and to register a scheduled task / service. |
| BlickP installed | Default location: `C:\Program Files\Blick\BlickP.exe`. |
| Outbound HTTPS to `storage.googleapis.com` | No inbound ports required. |
| GCP service-account JSON key | Scoped to **one** bucket with `roles/storage.objectCreator`. |

---

## 2. One-Time GCP Setup (do this once for the whole network)

1. Create the bucket: `gs://pgn-pandora-daily` (uniform bucket-level access).
2. Create a service account: `pandora-uploader@<project>.iam.gserviceaccount.com`.
3. Grant **only** `roles/storage.objectCreator` on that bucket. Do not grant project-wide roles.
4. Create a JSON key. This is the file each instrument PC will hold as `sa.json`.
5. (Optional) Set a 90-day key rotation reminder.

---

## 3. Install on a Pandora PC

All commands below run from an **elevated PowerShell** (right-click → Run as Administrator).

### 3.1 Lay down the package

```powershell
# 1. Create install dirs
$Install   = "C:\Program Files\PandoraSummarizer"
$DataRoot  = "C:\ProgramData\PandoraSummarizer"
New-Item -ItemType Directory -Force -Path $Install,$DataRoot,"$DataRoot\logs" | Out-Null

# 2. Copy the source tree to the install dir
#    (replace <SOURCE> with wherever you've staged the repo, e.g. a USB drive or share)
Copy-Item -Recurse -Force <SOURCE>\Pandora-Summarizer\* $Install

# 3. Create a venv inside the install dir and install the package
& "C:\Python311\python.exe" -m venv "$Install\.venv"
& "$Install\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "$Install\.venv\Scripts\pip.exe"   install "$Install"
```

### 3.2 Drop the service-account key

```powershell
# Copy the SA key from secure storage:
Copy-Item <SECURE_SHARE>\sa.json "$DataRoot\sa.json"

# Lock it down — only SYSTEM and Administrators can read it
icacls "$DataRoot\sa.json" /inheritance:r
icacls "$DataRoot\sa.json" /grant:r "SYSTEM:(R)" "Administrators:(R)"
```

### 3.3 Write the per-instrument config

`C:\ProgramData\PandoraSummarizer\config.yaml`:

```yaml
instrument:
  id: Pan100              # <-- change per host: Pan100, Pan175, ...
  timezone: America/Denver

paths:
  l0_dir:            D:\Pandora\L0
  l1_out_dir:        D:\Pandora\L1
  alignment_dir:     D:\Pandora\Alignment
  blick_figures_dir: C:\Program Files\Blick\Figures
  blickp_exe:        C:\Program Files\Blick\BlickP.exe

schedule:
  run_time_local: "02:00"
  process_lookback_days: 1

gcs:
  bucket: pgn-pandora-daily
  service_account_json: C:\ProgramData\PandoraSummarizer\sa.json
  overwrite_existing: true

retry:
  max_attempts: 3
  backoff_seconds: [30, 120, 600]

logging:
  dir: C:\ProgramData\PandoraSummarizer\logs
  level: INFO
  rotate_mb: 25
  keep_files: 14

state:
  db_path: C:\ProgramData\PandoraSummarizer\state.db
```

> The only fields that should differ across instruments are `instrument.id`, `instrument.timezone`, and the `paths.*` if a host is non-standard. Everything else should be identical across the network.

### 3.4 Smoke test before scheduling

```powershell
& "$Install\.venv\Scripts\pandora-summarizer.exe" run `
    --config "$DataRoot\config.yaml" `
    --date 2026-05-07 `
    --dry-run
```

Expect `done: COMPLETED`. If you see `PARTIAL` / `FAILED`, fix paths in `config.yaml` before continuing. See [Troubleshooting](#9-troubleshooting).

---

## 4. Option A — Task Scheduler (recommended)

### 4.1 Register the daily task

```powershell
.\installer\install.ps1
```

That script (kept simple, see `installer/install.ps1`) does:

```powershell
$action  = New-ScheduledTaskAction `
    -Execute "C:\Program Files\PandoraSummarizer\.venv\Scripts\pandora-summarizer.exe" `
    -Argument 'run --config "C:\ProgramData\PandoraSummarizer\config.yaml"'

$trigger = New-ScheduledTaskTrigger -Daily -At 2:00am

$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 30) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName "PandoraSummarizer-Daily" `
    -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Uploads yesterday's Pandora data products to GCS."
```

Why these flags:
- `SYSTEM` principal — runs without an interactive user; survives reboots and user logoffs.
- `StartWhenAvailable` — if the PC was off at 02:00 (power outage), runs as soon as it comes back.
- `RestartCount 3` — handles transient failures; the orchestrator's own retry handles network blips.
- `MultipleInstances IgnoreNew` — never overlap two runs of the same day.
- `ExecutionTimeLimit 4h` — hard ceiling; a healthy run is well under 5 minutes.

### 4.2 Verify

```powershell
Get-ScheduledTask -TaskName "PandoraSummarizer-Daily" | Format-List *
Get-ScheduledTaskInfo -TaskName "PandoraSummarizer-Daily"

# Force-run it now
Start-ScheduledTask -TaskName "PandoraSummarizer-Daily"

# After ~2 min, check status
& "$Install\.venv\Scripts\pandora-summarizer.exe" status `
    --config "C:\ProgramData\PandoraSummarizer\config.yaml"
```

---

## 5. Option B — Windows Service via NSSM (alternative)

Use only if your site requires "service" registration. NSSM wraps a CLI as a Windows Service and supplies its own scheduling.

### 5.1 Install NSSM

Download `nssm.exe` from <https://nssm.cc/release/nssm-2.24.zip>, unzip, copy `win64\nssm.exe` to `C:\Program Files\nssm\nssm.exe`. Verify SHA256 against the published value.

### 5.2 Register the service

```powershell
$nssm = "C:\Program Files\nssm\nssm.exe"
$exe  = "C:\Program Files\PandoraSummarizer\.venv\Scripts\pandora-summarizer.exe"

& $nssm install PandoraSummarizer $exe `
    "run --config C:\ProgramData\PandoraSummarizer\config.yaml"

& $nssm set PandoraSummarizer Start         SERVICE_DELAYED_AUTO_START
& $nssm set PandoraSummarizer ObjectName    LocalSystem
& $nssm set PandoraSummarizer AppStdout     "C:\ProgramData\PandoraSummarizer\logs\service.out.log"
& $nssm set PandoraSummarizer AppStderr     "C:\ProgramData\PandoraSummarizer\logs\service.err.log"
& $nssm set PandoraSummarizer AppRotateFiles 1
& $nssm set PandoraSummarizer AppRotateBytes 26214400          # 25 MB
& $nssm set PandoraSummarizer AppExit Default Restart
& $nssm set PandoraSummarizer AppRestartDelay 86400000         # 24h between runs

Start-Service PandoraSummarizer
```

> The CLI is a one-shot; NSSM keeps relaunching it once a day via `AppRestartDelay`. The service therefore "sleeps" most of the day. This is why Task Scheduler is simpler — you can see it.

### 5.3 Verify

```powershell
Get-Service PandoraSummarizer
Get-Content "C:\ProgramData\PandoraSummarizer\logs\service.out.log" -Tail 50
```

---

## 6. What gets uploaded

For run `D = 2026-05-07` on `Pan100`:

```
gs://pgn-pandora-daily/Pan100/2026-05-07/
├── data/
│   ├── Pandora100s1_<site>_20260507.txt        (L0)
│   ├── <L1 filename>                           (from BlickP)
│   ├── <alignment filename>
│   └── figures/
│       ├── fig_001.png
│       └── ...
└── summary.json
```

`summary.json` always uploads — even on partial failure — so operators can detect issues remotely without RDP'ing into the PC.

---

## 7. Day-2 Operations

### 7.1 Check yesterday's status

```powershell
& "C:\Program Files\PandoraSummarizer\.venv\Scripts\pandora-summarizer.exe" status `
    --config "C:\ProgramData\PandoraSummarizer\config.yaml"
```

### 7.2 Manually rerun a specific day

```powershell
& "C:\Program Files\PandoraSummarizer\.venv\Scripts\pandora-summarizer.exe" run `
    --config "C:\ProgramData\PandoraSummarizer\config.yaml" `
    --date 2026-05-03
```

Re-running is idempotent: GCS objects overwrite, `state.db` updates the row.

### 7.3 Rotate the GCS service-account key

1. Mint a new key in GCP Console.
2. Copy to `C:\ProgramData\PandoraSummarizer\sa.json` (overwrite).
3. Re-apply ACL: `icacls "$DataRoot\sa.json" /inheritance:r ; icacls "$DataRoot\sa.json" /grant:r "SYSTEM:(R)" "Administrators:(R)"`.
4. Smoke-test with `--dry-run`.
5. Disable the old key in GCP after one successful daily run.

### 7.4 Update to a new version

```powershell
Stop-ScheduledTask -TaskName "PandoraSummarizer-Daily"     # or Stop-Service for Option B
& "$Install\.venv\Scripts\pip.exe" install --upgrade <new wheel or path>
Start-ScheduledTask -TaskName "PandoraSummarizer-Daily"
```

`config.yaml`, `sa.json`, `state.db`, and `logs\` live under `ProgramData` and are not touched by upgrades.

### 7.5 Uninstall

```powershell
.\installer\uninstall.ps1
# Or manually:
Unregister-ScheduledTask -TaskName "PandoraSummarizer-Daily" -Confirm:$false
Remove-Item -Recurse -Force "C:\Program Files\PandoraSummarizer"
# Leave C:\ProgramData\PandoraSummarizer\ in place if you want to keep state/logs.
```

---

## 8. Logs and where to look

| Path | What it contains |
|---|---|
| `C:\ProgramData\PandoraSummarizer\logs\pandora_summarizer.log` | Structured JSON, one line per event. Rotates at 25 MB × 14 files. |
| `C:\ProgramData\PandoraSummarizer\state.db` | SQLite. Inspect with any sqlite tool. Tables: `daily_run`, `artifact`, `step_log`. |
| Task Scheduler → History tab | Trigger fires, exit codes. Enable history if disabled. |
| `gs://<bucket>/<Pan>/<date>/summary.json` | Authoritative remote view; `service_status.overall` is the headline. |

Quick state-DB query:

```powershell
sqlite3 "C:\ProgramData\PandoraSummarizer\state.db" `
    "SELECT date_utc, status, attempt FROM daily_run ORDER BY date_utc DESC LIMIT 14;"
```

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Status `PARTIAL`, step `locate_l0` failed | L0 file for that date not in `paths.l0_dir`, or filename doesn't contain `YYYYMMDD`. | Confirm acquisition wrote the file. Adjust `paths.l0_dir`. |
| Status `PARTIAL`, step `generate_l1` failed | BlickP CLI flags wrong (open question in DESIGN §13.1) or BlickP runtime error. | Inspect `pandora_summarizer.log` for the captured BlickP stderr. |
| Status `FAILED`, step `upload_gcs` failed | No outbound HTTPS, expired SA key, or bucket name typo. | `Test-NetConnection storage.googleapis.com -Port 443`; rotate key; re-check `gcs.bucket`. |
| Task scheduler shows `0x41301` (last run still running) | Previous run hung. | Kill any orphan `pandora-summarizer.exe`; re-run; investigate the slow step in logs. |
| Task scheduler shows `0x2` (file not found) | Path to `.exe` in the action is wrong. | `Get-ScheduledTask | Get-ScheduledTaskInfo`; reinstall with `installer\install.ps1`. |
| Run produces `summary.json` but no L1 | Expected when `--dry-run`, or when L0 is missing. | If neither applies, see `step_log.error_text` for the `generate_l1` row. |
| `summary.json` shows old `summarizer_version` | Upgrade missed this PC. | Re-run §7.4 on that host. |

### Re-run a failed day end-to-end

```powershell
& "C:\Program Files\PandoraSummarizer\.venv\Scripts\pandora-summarizer.exe" run `
    --config "C:\ProgramData\PandoraSummarizer\config.yaml" `
    --date 2026-05-03
```

A `COMPLETED` status overwrites the prior `FAILED` row in `state.db`.

---

## 10. Security Notes

- Run as `SYSTEM`; do not run as a named domain user.
- `sa.json` ACL: `SYSTEM:(R)` and `Administrators:(R)` only. No `Users` group.
- The service makes **outbound HTTPS only**. Block inbound to anything in `Program Files\PandoraSummarizer`.
- Key rotation cadence: every 90 days (§7.3).
- The installer should be code-signed before network-wide rollout (DESIGN §10).
- `summary.json` deliberately omits absolute filesystem paths; do not add them.

---

## 11. Per-Site Rollout Checklist

Before flipping a new site to scheduled mode:

- [ ] `instrument.id` correct in `config.yaml` (matches GCS prefix).
- [ ] `instrument.timezone` matches local time at site.
- [ ] All five `paths.*` resolve and are readable by `SYSTEM`.
- [ ] `sa.json` present and ACL'd.
- [ ] One successful `--dry-run` for yesterday.
- [ ] One successful real run for yesterday (look for the bundle in GCS).
- [ ] Scheduled task registered, next run time visible.
- [ ] `summary.json` for `D-1` shows `service_status.overall = "COMPLETED"`.
- [ ] Site added to the operator dashboard / alert list.
