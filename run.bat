@echo off
cd /d "%~dp0"
set PYTHONPATH=

:: Use system Python — no venv needed for development
set PYTHON_CMD=
for %%v in (313 312 311 310) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" (
        set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe
    )
)
if "%PYTHON_CMD%"=="" (
    where python >nul 2>&1 && set PYTHON_CMD=python
)
if "%PYTHON_CMD%"=="" (
    echo ERROR: Python not found
    pause
    exit /b 1
)

if "%1"=="relay" (
    "%PYTHON_CMD%" relay_server.py --port 8888
) else if "%1"=="direct" (
    "%PYTHON_CMD%" -m livingtree tui --direct
) else (
    "%PYTHON_CMD%" -m livingtree tui
)
pause
