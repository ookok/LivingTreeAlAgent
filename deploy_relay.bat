@echo off
setlocal enabledelayedexpansion
title LivingTree Relay Server

set PORT=%1
if "%PORT%"=="" set /p PORT="Port (8888): "
if "%PORT%"=="" set PORT=8888

echo.
echo === LivingTree Relay Server ===
echo Port: %PORT%
echo.

set PYTHON_CMD=
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python314\python.exe
if "%PYTHON_CMD%"=="" (
    for /f "tokens=*" %%i in ('where python 2^>nul') do (
        "%%i" -c "import sys; sys.exit(0 if sys.version_info>=(3,14) else 1)" >nul 2>&1
        if !ERRORLEVEL! EQU 0 set PYTHON_CMD=%%i
    )
)
if "%PYTHON_CMD%"=="" (
    echo Python 3.14 not found.
    echo Downloading from mirror...
    powershell -Command "(New-Object Net.WebClient).DownloadFile('https://mirrors.huaweicloud.com/python/3.14.0/python-3.14.0-amd64.exe','%TEMP%\python314.exe')"
    if exist "%TEMP%\python314.exe" (
        start /wait "" "%TEMP%\python314.exe" /quiet InstallAllUsers=0 Include_test=0
        del "%TEMP%\python314.exe"
    )
    if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python314\python.exe
)
if "%PYTHON_CMD%"=="" (
    echo ERROR: Python 3.14 install failed.
    echo Manual: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo Python 3.14 OK

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
