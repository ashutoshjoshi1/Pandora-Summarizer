# Uninstall PandoraEdgeService scheduled task.
#
# Usage (elevated PowerShell):
#   .\uninstall.ps1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$TaskName = "PandoraEdgeService"
)

$ErrorActionPreference = "Stop"

schtasks.exe /Delete /TN $TaskName /F
if ($LASTEXITCODE -ne 0) {
    throw "schtasks delete failed with exit code $LASTEXITCODE"
}

Write-Host "Removed scheduled task '$TaskName'."
