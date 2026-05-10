@echo off
setlocal enabledelayedexpansion
title LivingTree Relay Server

:: Fix DNS for cloud servers
netsh interface ip set dns "Ethernet" static 223.5.5.5 >nul 2>&1
netsh interface ip add dns "Ethernet" 114.114.114.114 index=2 >nul 2>&1
ipconfig /flushdns >nul 2>&1

set PORT=%1
if "%PORT%"=="" set /p PORT="Port (8899): "
if "%PORT%"=="" set PORT=8899

echo.
echo === LivingTree Relay Server ===
echo Port: %PORT%
echo.

set PYTHON_CMD=
for %%v in (313 312 311 310) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe
)
if "%PYTHON_CMD%"=="" (
    for /f "tokens=*" %%i in ('where python 2^>nul') do (
        "%%i" -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
        if !ERRORLEVEL! EQU 0 set PYTHON_CMD=%%i
    )
)
if "%PYTHON_CMD%"=="" (
    echo Python 3.10+ not found
    pause
    exit /b 1
)
echo Python OK

if not exist ".venv" (
    "%PYTHON_CMD%" -m venv .venv
    echo venv created.
)
call .venv\Scripts\activate.bat >nul
.venv\Scripts\python.exe -m pip install aiohttp pyyaml pydantic loguru --quiet
echo Dependencies OK.

echo Starting relay server on port %PORT%...
echo Admin: http://localhost:%PORT%/admin
echo Ctrl+C to stop
echo.

.venv\Scripts\python.exe relay_server.py --port %PORT% --host 0.0.0.0
pause
