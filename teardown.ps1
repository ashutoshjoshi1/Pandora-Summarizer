# Pandora Fleet Monitoring - one-shot uninstaller.
#
# Removes the scheduled task. By default, leaves config, logs, state.db, and
# uploaded data untouched. Pass -RemoveAll to wipe C:\ProgramData\PandoraFleetMonitor\.

[CmdletBinding()]
param(
    [string]$InstallRoot = "C:\ProgramData\PandoraFleetMonitor",
    [switch]$RemoveAll
)

$ErrorActionPreference = "Continue"

$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "FAILED: must run as Administrator." -ForegroundColor Red
    exit 1
}

Write-Host "Removing Scheduled Task 'PandoraEdgeService'..."
schtasks.exe /Delete /TN PandoraEdgeService /F
if ($LASTEXITCODE -eq 0) {
    Write-Host "    Task removed." -ForegroundColor Green
} else {
    Write-Host "    Task not present (already removed?)." -ForegroundColor Yellow
}

if ($RemoveAll) {
    if (Test-Path $InstallRoot) {
        Write-Host "Removing install root $InstallRoot ..."
        Remove-Item -Recurse -Force $InstallRoot
        Write-Host "    Removed." -ForegroundColor Green
    }
} else {
    Write-Host ""
    Write-Host "Leaving $InstallRoot in place (config, logs, state.db, staging)." -ForegroundColor Gray
    Write-Host "Pass -RemoveAll to wipe everything." -ForegroundColor Gray
}
