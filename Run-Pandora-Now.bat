@echo off
REM ============================================================
REM  Pandora Fleet Monitoring - run the service ONCE right now.
REM  Use this to test that the install worked, or to manually
REM  re-process a missed day. The daily Scheduled Task will still
REM  run on its own schedule.
REM ============================================================

setlocal

set CFG=C:\ProgramData\PandoraFleetMonitor\config.yaml
set CLI=C:\ProgramData\PandoraFleetMonitor\.venv\Scripts\pandora-edge.exe

if not exist "%CLI%" (
    echo.
    echo *** The service has not been installed yet on this computer.
    echo *** Double-click Run-Setup.bat first.
    echo.
    pause
    exit /b 1
)
if not exist "%CFG%" (
    echo.
    echo *** Config not found at %CFG%
    echo *** Double-click Run-Setup.bat to set it up.
    echo.
    pause
    exit /b 1
)

echo.
echo Running PandoraEdgeService right now...
echo Config: %CFG%
echo.

"%CLI%" run --config "%CFG%"
set RC=%ERRORLEVEL%

echo.
if %RC% EQU 0 (
    echo *** Run completed. Check the dashboard or GCS in a minute. ***
) else (
    echo *** Run finished with code %RC%. See the log:
    echo     C:\ProgramData\PandoraFleetMonitor\logs\pandora-edge.log
)
echo.
pause
endlocal
