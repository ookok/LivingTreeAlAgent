@echo off
chcp 65001 > nul 2>&1
set "ROOT=%~dp0"
cd /d "%ROOT%"

REM Try pythonw, fallback to python with minimized window
set "PY="
for /f "delims=" %%i in ('python -c "import sys; from pathlib import Path; p=Path(sys.executable).parent/'pythonw.exe'; print(p if p.exists() else sys.executable)" 2^>nul') do set "PY=%%i"
if not defined PY set "PY=python.exe"

start "" /B "%PY%" -c "from livingtree.tui.wt_bootstrap import main; main()" %* 2>nul
if errorlevel 1 (
    start "" /MIN python.exe -c "from livingtree.tui.wt_bootstrap import main; main()" %*
)
exit /b 0
