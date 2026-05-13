@echo off
REM ============================================================
REM  Pandora Fleet Monitoring - one-click installer
REM  Double-click this file. It will ask for admin rights and
REM  then walk through the install.
REM ============================================================

setlocal

REM Step 1: Make sure we are running as Administrator. If not,
REM relaunch ourselves elevated.
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Requesting Administrator rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

REM Step 2: Hand off to the PowerShell installer with the right
REM execution policy so script-blocking does not derail us.
cd /d "%~dp0"
echo.
echo Running setup.ps1 ...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
set RC=%ERRORLEVEL%

echo.
if %RC% NEQ 0 (
    echo.
    echo *** Installer exited with code %RC%. Scroll up to see what went wrong. ***
    echo.
) else (
    echo *** Installer finished. ***
)
echo.
pause
endlocal
