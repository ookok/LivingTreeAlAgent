@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
title LivingTree Relay Server Deploy

set PORT=%1
if "%PORT%"=="" set /p PORT="Enter port (8888): "
if "%PORT%"=="" set PORT=8888

echo.
echo ===========================================
echo   LivingTree Relay Server Deploy
echo   Port: %PORT%
echo ===========================================
echo.

echo [1/5] Checking Python 3.14...
set PYTHON_CMD=
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python314\python.exe
)
if "%PYTHON_CMD%"=="" (
    for /f "tokens=*" %%i in ('where python 2^>nul') do (
        "%%i" -c "import sys; sys.exit(0 if sys.version_info>=(3,14) else 1)" >nul 2>&1
        if !ERRORLEVEL! EQU 0 set PYTHON_CMD=%%i
    )
)
if "%PYTHON_CMD%"=="" (
    echo   Python 3.14 not found. Downloading...
    powershell -c "$u='https://mirrors.huaweicloud.com/python/3.14.0/python-3.14.0-amd64.exe';$o='%TEMP%\python314.exe';(New-Object Net.WebClient).DownloadFile($u,$o)" 2>nul
    if exist "%TEMP%\python314.exe" (
        echo   Installing...
        start /wait "" "%TEMP%\python314.exe" /quiet InstallAllUsers=0 Include_test=0
        del "%TEMP%\python314.exe" 2>nul
    )
    if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
        set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python314\python.exe
    )
)
if "%PYTHON_CMD%"=="" (
    echo   ERROR: Cannot install Python 3.14. Get it from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo   OK: Python 3.14 found

echo.
echo [2/5] Virtual environment...
if not exist ".venv" (
    "%PYTHON_CMD%" -m venv .venv
    echo   venv created
) else (
    echo   venv exists
)

echo.
echo [3/5] Installing dependencies...
call .venv\Scripts\activate.bat >nul 2>&1
.venv\Scripts\python.exe -m pip install aiohttp pyyaml pydantic loguru --quiet 2>nul
echo   Done

echo.
echo [4/5] Verifying...
.venv\Scripts\python.exe -c "from relay_server import P2PRelayServer; print('OK')" 2>nul || echo   WARNING: import failed

echo.
echo [5/5] Starting relay server on port %PORT%...
echo.
echo   Server:  http://localhost:%PORT%
echo   Admin:   http://localhost:%PORT%/admin
echo   Chat:    POST http://localhost:%PORT%/chat
echo   P2P:     POST http://localhost:%PORT%/peers/register
echo   WS:      ws://localhost:%PORT%/ws/relay
echo.
echo   Press Ctrl+C to stop
echo.

.venv\Scripts\python.exe relay_server.py --port %PORT% --host 0.0.0.0

echo.
echo Server stopped.
pause
