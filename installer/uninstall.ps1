<#
.SYNOPSIS
    Removes the Pandora Summarizer scheduled task and (optionally) the install dir.

.DESCRIPTION
    By default, leaves C:\ProgramData\PandoraSummarizer untouched so state, logs,
    and config are preserved. Pass -RemoveData to wipe it as well.
#>

param(
    [string]$TaskName   = "PandoraSummarizer-Daily",
    [string]$InstallDir = "C:\Program Files\PandoraSummarizer",
    [string]$DataDir    = "C:\ProgramData\PandoraSummarizer",
    [switch]$RemoveData
)

$ErrorActionPreference = "Stop"

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task '$TaskName'."
} else {
    Write-Host "Scheduled task '$TaskName' not present."
}

if (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force $InstallDir
    Write-Host "Removed $InstallDir."
}

if ($RemoveData -and (Test-Path $DataDir)) {
    Remove-Item -Recurse -Force $DataDir
    Write-Host "Removed $DataDir (state, logs, config, sa.json)."
} elseif (Test-Path $DataDir) {
    Write-Host "Preserved $DataDir (use -RemoveData to wipe)."
}
