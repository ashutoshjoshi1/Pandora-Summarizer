<#
.SYNOPSIS
    Registers the Pandora Summarizer as a Windows Service via NSSM.

.DESCRIPTION
    Use only when site policy mandates a Windows Service. For most deployments
    Task Scheduler (installer/install.ps1) is the better fit.
    Assumes nssm.exe is at $NssmPath and the package is installed at $InstallDir.
#>

param(
    [string]$ServiceName = "PandoraSummarizer",
    [string]$InstallDir  = "C:\Program Files\PandoraSummarizer",
    [string]$DataDir     = "C:\ProgramData\PandoraSummarizer",
    [string]$NssmPath    = "C:\Program Files\nssm\nssm.exe"
)

$ErrorActionPreference = "Stop"

$exe        = Join-Path $InstallDir ".venv\Scripts\pandora-summarizer.exe"
$configPath = Join-Path $DataDir "config.yaml"
$logsDir    = Join-Path $DataDir "logs"

if (-not (Test-Path $NssmPath))   { throw "Not found: $NssmPath — install NSSM first." }
if (-not (Test-Path $exe))        { throw "Not found: $exe — install the package first." }
if (-not (Test-Path $configPath)) { throw "Not found: $configPath." }

if (Get-Service $ServiceName -ErrorAction SilentlyContinue) {
    Stop-Service  $ServiceName -ErrorAction SilentlyContinue
    & $NssmPath remove $ServiceName confirm | Out-Null
}

& $NssmPath install $ServiceName $exe "run --config `"$configPath`"" | Out-Null

# A one-shot CLI restarted once per day.
& $NssmPath set $ServiceName Start          SERVICE_DELAYED_AUTO_START | Out-Null
& $NssmPath set $ServiceName ObjectName     LocalSystem               | Out-Null
& $NssmPath set $ServiceName AppStdout      (Join-Path $logsDir "service.out.log") | Out-Null
& $NssmPath set $ServiceName AppStderr      (Join-Path $logsDir "service.err.log") | Out-Null
& $NssmPath set $ServiceName AppRotateFiles 1                         | Out-Null
& $NssmPath set $ServiceName AppRotateBytes 26214400                  | Out-Null    # 25 MB
& $NssmPath set $ServiceName AppExit Default Restart                  | Out-Null
& $NssmPath set $ServiceName AppRestartDelay 86400000                 | Out-Null    # 24h

Start-Service $ServiceName
Write-Host "Service '$ServiceName' registered and started."
