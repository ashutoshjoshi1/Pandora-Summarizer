# Install PandoraEdgeService as a daily Windows Scheduled Task.
#
# Usage (from an elevated PowerShell):
#   .\install.ps1 -ConfigPath "C:\ProgramData\PandoraFleetMonitor\config.yaml" `
#                 -PythonExe   "C:\Python311\python.exe" `
#                 -RunTime     "06:00"
#
# This script is a thin wrapper around schtasks. The Python CLI
# `pandora-edge install-task` does the same thing programmatically.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigPath,

    [Parameter(Mandatory = $false)]
    [string]$PythonExe = "python",

    [Parameter(Mandatory = $false)]
    [string]$RunTime = "06:00",

    [Parameter(Mandatory = $false)]
    [string]$TaskName = "PandoraEdgeService"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Config not found: $ConfigPath"
}

$action = "`"$PythonExe`" -m pandora_edge run --config `"$ConfigPath`""

Write-Host "Creating scheduled task '$TaskName' to run daily at $RunTime"
Write-Host "Action: $action"

schtasks.exe /Create `
    /TN $TaskName `
    /SC DAILY `
    /ST $RunTime `
    /RL HIGHEST `
    /F `
    /TR $action

if ($LASTEXITCODE -ne 0) {
    throw "schtasks failed with exit code $LASTEXITCODE"
}

# Restrict ACL on the service account JSON if it is referenced from config.
$confDir = Split-Path -Parent $ConfigPath
$sa = Join-Path $confDir "sa.json"
if (Test-Path -LiteralPath $sa) {
    Write-Host "Restricting ACL on $sa to SYSTEM + Administrators."
    icacls.exe $sa /inheritance:r /grant:r "SYSTEM:F" "Administrators:F" | Out-Null
}

Write-Host "Done. Run 'schtasks /Query /TN $TaskName' to confirm."
