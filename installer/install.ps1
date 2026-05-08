<#
.SYNOPSIS
    Registers the Pandora Summarizer daily scheduled task.

.DESCRIPTION
    Idempotent: re-running this script replaces the existing task definition.
    Run from an elevated PowerShell. Assumes the package has already been
    installed at $InstallDir and config.yaml exists at $ConfigPath.
    See docs/windows-service-guide.md.
#>

param(
    [string]$TaskName   = "PandoraSummarizer-Daily",
    [string]$InstallDir = "C:\Program Files\PandoraSummarizer",
    [string]$ConfigPath = "C:\ProgramData\PandoraSummarizer\config.yaml",
    [string]$RunAt      = "02:00"
)

$ErrorActionPreference = "Stop"

$exe = Join-Path $InstallDir ".venv\Scripts\pandora-summarizer.exe"
if (-not (Test-Path $exe))        { throw "Not found: $exe — install the package first." }
if (-not (Test-Path $ConfigPath)) { throw "Not found: $ConfigPath — create config first." }

$action = New-ScheduledTaskAction `
    -Execute $exe `
    -Argument "run --config `"$ConfigPath`""

$trigger = New-ScheduledTaskTrigger -Daily -At $RunAt

$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 30) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4) `
    -MultipleInstances IgnoreNew

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName    $TaskName `
    -Action      $action `
    -Trigger     $trigger `
    -Principal   $principal `
    -Settings    $settings `
    -Description "Uploads yesterday's Pandora data products to GCS." | Out-Null

Write-Host "Registered scheduled task '$TaskName' to run daily at $RunAt as SYSTEM."
