@echo off
REM ============================================================
REM  Pandora Fleet Monitoring - one-click uninstaller.
REM  Removes the Scheduled Task. By default, leaves config, logs,
REM  and history alone in case you want to reinstall later.
REM ============================================================

setlocal

net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Requesting Administrator rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0teardown.ps1"
echo.
pause
endlocal
