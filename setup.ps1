# Pandora Fleet Monitoring - one-shot Windows installer.
#
# Copy this entire repo to the Pandora computer, then right-click this
# file -> "Run with PowerShell" (or run it from an elevated PowerShell).
#
# What this script does:
#   1. Verifies you have administrator rights and Python 3.11+.
#   2. Lays out a stable home under C:\ProgramData\PandoraFleetMonitor\.
#   3. Creates a Python virtualenv and installs the package.
#   4. Copies config.example.yaml -> config.yaml (only if it does not exist yet)
#      and opens it in Notepad so you can edit instrument id, paths, GCS bucket.
#   5. Verifies the GCS service-account JSON is in place and locks down its ACL.
#   6. Validates the config and runs a dry-run end-to-end test.
#   7. Backfills every day from -BackfillStart (default 2026-01-01) through
#      yesterday's local date. Days already completed in state.db are skipped,
#      so re-running setup.ps1 is cheap.
#   8. Registers the daily Scheduled Task ("PandoraEdgeService").
#   9. Prints a summary of what was created and how to verify it.
#
# This script is idempotent. You can rerun it after editing config.yaml.

[CmdletBinding()]
param(
    [string]$InstallRoot   = "C:\ProgramData\PandoraFleetMonitor",
    [string]$PythonExe     = "",     # empty = autodetect
    [string]$RunTime       = "",     # empty = read from config.yaml
    [string]$BackfillStart = "2026-01-01",
    [switch]$SkipDryRun,
    [switch]$SkipBackfill,
    [switch]$SkipTaskInstall
)

$ErrorActionPreference = "Stop"
$script:StepNumber = 0

function Step([string]$msg) {
    $script:StepNumber++
    Write-Host ""
    Write-Host "==[ $script:StepNumber. $msg ]==" -ForegroundColor Cyan
}

function Info([string]$msg) { Write-Host "    $msg" -ForegroundColor Gray }
function Ok([string]$msg)   { Write-Host "    OK: $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "    WARN: $msg" -ForegroundColor Yellow }
function Fail([string]$msg) {
    Write-Host ""
    Write-Host "    FAILED: $msg" -ForegroundColor Red
    Write-Host ""
    exit 1
}

# ---------------------------------------------------------------------------
Step "Verify admin rights"
$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Fail "This installer must be run from an elevated PowerShell. Right-click PowerShell -> Run as administrator, then re-run setup.ps1."
}
Ok "Running elevated as $($me.Identity.Name)"

# ---------------------------------------------------------------------------
Step "Locate Python 3.11+"
function Find-Python {
    param([string]$Preferred)
    $candidates = @()
    if ($Preferred) { $candidates += $Preferred }
    $candidates += @(
        "python",
        "py",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Program Files\Python313\python.exe",
        "C:\Program Files\Python312\python.exe",
        "C:\Program Files\Python311\python.exe"
    )
    foreach ($c in $candidates) {
        try {
            $resolved = (Get-Command $c -ErrorAction SilentlyContinue).Source
            if (-not $resolved) { $resolved = $c }
            if (-not (Test-Path $resolved) -and ($c -eq "python" -or $c -eq "py")) {
                # let `python --version` work via PATH
                $v = & $c --version 2>$null
            } else {
                $v = & $resolved --version 2>$null
            }
            if ($LASTEXITCODE -eq 0 -and $v -match "Python (\d+)\.(\d+)") {
                $maj = [int]$matches[1]; $min = [int]$matches[2]
                if ($maj -gt 3 -or ($maj -eq 3 -and $min -ge 11)) {
                    return @{ Path = $resolved; Version = $v }
                }
            }
        } catch { continue }
    }
    return $null
}
$py = Find-Python -Preferred $PythonExe
if (-not $py) {
    Fail "Could not find Python 3.11 or newer. Install it from https://www.python.org/downloads/ (check `Add python.exe to PATH'), then re-run setup.ps1. Or pass -PythonExe `"C:\path\to\python.exe`"."
}
Ok "Found $($py.Version) at $($py.Path)"

# ---------------------------------------------------------------------------
Step "Lay out install root at $InstallRoot"
$repoRoot   = (Get-Item $PSScriptRoot).FullName
$appDir     = Join-Path $InstallRoot "app"
$venvDir    = Join-Path $InstallRoot ".venv"
$logsDir    = Join-Path $InstallRoot "logs"
$stagingDir = Join-Path $InstallRoot "staging"
$configPath = Join-Path $InstallRoot "config.yaml"
$saJsonPath = Join-Path $InstallRoot "sa.json"
$dbPath     = Join-Path $InstallRoot "state.db"

New-Item -ItemType Directory -Force -Path $InstallRoot, $logsDir, $stagingDir | Out-Null
Ok "Created $InstallRoot, logs/, staging/"

# Copy the repo if we're running from somewhere else.
if ($repoRoot -ne $appDir) {
    Info "Copying repository from $repoRoot -> $appDir"
    if (Test-Path $appDir) {
        # Refresh in place - never delete the venv we may already have.
        $exclude = @(".venv", ".git", "__pycache__", ".pytest_cache", ".ruff_cache")
        robocopy $repoRoot $appDir /MIR /XD $exclude /NFL /NDL /NJH /NJS /NC /NS /R:1 /W:1 | Out-Null
    } else {
        robocopy $repoRoot $appDir /E /XD ".git" "__pycache__" ".pytest_cache" ".ruff_cache" /NFL /NDL /NJH /NJS /NC /NS /R:1 /W:1 | Out-Null
    }
    # robocopy exits with codes 0-7 for success; 8+ for failure.
    if ($LASTEXITCODE -ge 8) { Fail "robocopy failed with code $LASTEXITCODE" }
    Ok "Repo synced to $appDir"
} else {
    Ok "Already running from install location."
}

# ---------------------------------------------------------------------------
Step "Create / refresh Python virtualenv"
if (-not (Test-Path (Join-Path $venvDir "Scripts\python.exe"))) {
    Info "Creating new venv at $venvDir"
    & $py.Path -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { Fail "venv creation failed" }
} else {
    Ok "Venv already present at $venvDir"
}
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvPandora = Join-Path $venvDir "Scripts\pandora-edge.exe"

# ---------------------------------------------------------------------------
Step "Install pandora-fleet-monitor and dependencies"
& $venvPython -m pip install --upgrade pip wheel setuptools | Out-Null
& $venvPython -m pip install -e "$appDir[windows]"
if ($LASTEXITCODE -ne 0) { Fail "pip install failed. Check internet access from this machine." }
Ok "Package installed."

# ---------------------------------------------------------------------------
Step "Set up config.yaml"
if (-not (Test-Path $configPath)) {
    $src = Join-Path $appDir "config\config.example.yaml"
    if (-not (Test-Path $src)) { Fail "Missing $src" }
    Copy-Item $src $configPath
    Ok "Created $configPath from example. Opening Notepad - edit instrument id, paths, and GCS bucket."
    Start-Process notepad.exe -ArgumentList $configPath -Wait
} else {
    Info "$configPath already exists - leaving it alone."
    $reopen = Read-Host "Open it in Notepad to review? [y/N]"
    if ($reopen -match "^[Yy]") {
        Start-Process notepad.exe -ArgumentList $configPath -Wait
    }
}

# ---------------------------------------------------------------------------
Step "Verify GCS service-account JSON"
if (-not (Test-Path $saJsonPath)) {
    Warn "Expected service-account file not found:"
    Warn "    $saJsonPath"
    Write-Host ""
    Write-Host "    Download the service-account key from Google Cloud Console" -ForegroundColor Yellow
    Write-Host "    (IAM -> Service Accounts -> Keys -> Add key -> JSON)" -ForegroundColor Yellow
    Write-Host "    and save it to that exact path." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter once you have placed sa.json at $saJsonPath (or Ctrl+C to abort)"
    if (-not (Test-Path $saJsonPath)) {
        Fail "Still no sa.json at $saJsonPath. Place it there and re-run setup.ps1."
    }
}
Ok "Found sa.json. Tightening ACL to SYSTEM + Administrators."
& icacls.exe $saJsonPath /inheritance:r /grant:r "SYSTEM:F" "Administrators:F" | Out-Null

# ---------------------------------------------------------------------------
Step "Validate config"
& $venvPandora validate-config --config $configPath
if ($LASTEXITCODE -ne 0) { Fail "Config did not validate. Fix the issues shown above, then re-run setup.ps1." }
Ok "Config valid."

# ---------------------------------------------------------------------------
if (-not $SkipDryRun) {
    Step "Dry-run pipeline (no GCS upload)"
    & $venvPandora run --config $configPath --dry-run
    if ($LASTEXITCODE -ne 0) {
        Warn "Dry-run reported issues. This is often expected on a fresh install (Blick may not have written yesterday's files yet)."
        Warn "Inspect: $logsDir\pandora-edge.log"
    } else {
        Ok "Dry-run completed."
    }
}

# ---------------------------------------------------------------------------
if (-not $SkipBackfill) {
    Step "Backfill historical days from $BackfillStart through yesterday"
    # Sanity-check the start date.
    try { $startDate = [datetime]::ParseExact($BackfillStart, "yyyy-MM-dd", $null) }
    catch { Fail "Invalid -BackfillStart '$BackfillStart'. Use YYYY-MM-DD." }

    $endDate = (Get-Date).Date.AddDays(-1)
    if ($endDate -lt $startDate) {
        Warn "Yesterday ($($endDate.ToString('yyyy-MM-dd'))) is before $BackfillStart - nothing to backfill."
    } else {
        $endStr = $endDate.ToString("yyyy-MM-dd")
        Info "Range: $BackfillStart .. $endStr (already-completed days are skipped via state.db)."
        Info "This can take a while on a fresh install - leave the window open."
        & $venvPandora backfill --config $configPath --start $BackfillStart --end $endStr
        if ($LASTEXITCODE -ne 0) {
            Warn "Backfill exited with code $LASTEXITCODE. Some days failed - inspect:"
            Warn "    $logsDir\pandora-edge.log"
            Warn "Re-run setup.ps1 (or 'pandora-edge backfill ...') to retry; finished days are skipped."
        } else {
            Ok "Backfill complete through $endStr."
        }
    }
}

# ---------------------------------------------------------------------------
if (-not $SkipTaskInstall) {
    Step "Register daily Scheduled Task 'PandoraEdgeService'"
    # If -RunTime was not provided, read it from config.yaml (best effort).
    if (-not $RunTime) {
        $RunTime = "06:00"
        try {
            $cfg = Get-Content $configPath -Raw
            if ($cfg -match 'run_time_local:\s*"?(\d{2}:\d{2})"?') {
                $RunTime = $matches[1]
            }
        } catch {}
    }

    $action = "`"$venvPython`" -m pandora_edge run --config `"$configPath`""
    Info "Action: $action"
    Info "Daily at: $RunTime (local time)"

    schtasks.exe /Create `
        /TN PandoraEdgeService `
        /SC DAILY `
        /ST $RunTime `
        /RL HIGHEST `
        /F `
        /TR $action
    if ($LASTEXITCODE -ne 0) {
        Fail "schtasks failed to register the task. The most common cause is non-elevated PowerShell - confirm you opened PowerShell as Administrator."
    }
    Ok "Scheduled Task 'PandoraEdgeService' registered."
}

# ---------------------------------------------------------------------------
Step "Done. Summary"

$summary = @"

    Install root .... $InstallRoot
    Config .......... $configPath
    Service account.. $saJsonPath
    Local logs ...... $logsDir
    Staging ......... $stagingDir
    State DB ........ $dbPath
    Python (venv) ... $venvPython
    CLI ............. $venvPandora
    Scheduled task .. PandoraEdgeService (Task Scheduler)
    Backfill from ... $BackfillStart (override with -BackfillStart YYYY-MM-DD)

    Verify:
        schtasks /Query /TN PandoraEdgeService /V /FO LIST
        Get-Content '$logsDir\pandora-edge.log' -Tail 40

    Run on demand (won't wait for the daily trigger):
        & '$venvPandora' run --config '$configPath'

    Uninstall:
        & '$venvPandora' uninstall-task

"@
Write-Host $summary -ForegroundColor Green
