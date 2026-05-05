@echo off
cd /d "%~dp0"

:: Clear any external PYTHONPATH
set PYTHONPATH=

:: Verify correct venv
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv not found. Run install.bat first.
    pause
    exit /b 1
)

if "%1"=="relay" (
    .venv\Scripts\python.exe relay_server.py --port 8888
) else (
    .venv\Scripts\python.exe -m livingtree tui
)
pause
