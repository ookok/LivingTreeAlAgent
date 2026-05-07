@echo off
cd /d "%~dp0"
set PYTHONPATH=

set PYTHON_CMD=
if exist ".venv\Scripts\python.exe" (
    set PYTHON_CMD=.venv\Scripts\python.exe
)
if "%PYTHON_CMD%"=="" (
    for %%v in (313 312 311 310) do (
        if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" (
            set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe
        )
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

"%PYTHON_CMD%" -c "import pydantic" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    "%PYTHON_CMD%" -m pip install pydantic pyyaml loguru rich textual aiohttp pydantic-settings fastapi uvicorn --quiet 2>nul
)

if "%1"=="relay" (
    "%PYTHON_CMD%" relay_server.py --port 8888
) else (
    echo.
    echo   🌳 LivingTree AI Agent v2.1
    echo   Web UI: http://localhost:8100
    echo   API Docs: http://localhost:8100/docs
    echo.
    "%PYTHON_CMD%" -m livingtree
)
pause
