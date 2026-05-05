@echo off
cd /d "%~dp0"
if "%1"=="relay" (
    .venv\Scripts\python.exe relay_server.py --port 8888
) else (
    .venv\Scripts\python.exe -m livingtree tui
)
pause
