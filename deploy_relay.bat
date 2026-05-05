@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title LivingTree Relay Server — One-Click Deploy

:: ═══ User-specified port ═══
set PORT=%1
if "%PORT%"=="" (
    set /p PORT="Enter port number (recommend 8100-8199): "
)
if "%PORT%"=="" set PORT=8100

echo.
echo ╔══════════════════════════════════════════╗
echo ║   LivingTree Relay Server Deploy        ║
echo ║   Port: %PORT%                              ║
echo ╚══════════════════════════════════════════╝
echo.

:: ═══ Step 1: Check Python 3.14 ═══
echo [1/5] Checking Python 3.14...
set PYTHON_CMD=
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    "%%i" -c "import sys; sys.exit(0 if sys.version_info>=(3,14) else 1)" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set PYTHON_CMD=%%i
        goto :found_python
    )
)

:: Check specific path
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe" (
    set PYTHON_CMD=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe
    goto :found_python
)

:: Auto-install Python 3.14
echo   Python 3.14 not found. Downloading...
powershell -c "Invoke-WebRequest -Uri 'https://mirrors.huaweicloud.com/python/3.14.0/python-3.14.0-amd64.exe' -OutFile '%TEMP%\python314.exe'" 2>nul
if exist "%TEMP%\python314.exe" (
    echo   Installing Python 3.14 (silent)...
    start /wait "" "%TEMP%\python314.exe" /quiet InstallAllUsers=0 Include_test=0
    del "%TEMP%\python314.exe" 2>nul
    if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe" (
        set PYTHON_CMD=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe
        goto :found_python
    )
)
echo   ERROR: Python 3.14 install failed. Install manually: https://www.python.org/downloads/
pause
exit /b 1

:found_python
echo   %PYTHON_CMD%
%PYTHON_CMD% --version

:: ═══ Step 2: Create venv ═══
echo.
echo [2/5] Setting up virtual environment...
if not exist ".venv" (
    %PYTHON_CMD% -m venv .venv
    echo venv created.
) else (
    echo venv already exists.
)

:: ═══ Step 3: Install dependencies ═══
echo.
echo [3/5] Installing dependencies...
call .venv\Scripts\activate.bat
%PYTHON_CMD% -m pip install -e . --quiet 2>nul
%PYTHON_CMD% -m pip install aiohttp pyyaml pydantic loguru --quiet 2>nul
echo Dependencies ready.

:: ═══ Step 4: Verify ═══
echo.
echo [4/5] Verifying installation...
.venv\Scripts\python.exe -c "from livingtree.integration.hub import IntegrationHub; print('OK')" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Import check failed. Server may not start correctly.
)

:: ═══ Step 5: Start server ═══
echo.
echo [5/5] Starting relay server on port %PORT%...
echo.
echo ╔══════════════════════════════════════════╗
echo ║  Server:  http://localhost:%PORT%           ║
echo ║  Admin:   http://localhost:%PORT%/admin      ║
echo ║  Chat:    POST /chat                          ║
echo ║  P2P:     POST /peers/register                ║
echo ║  WebSocket: ws://localhost:%PORT%/ws/relay     ║
echo ║                                              ║
echo ║  Press Ctrl+C to stop                        ║
echo ╚══════════════════════════════════════════╝
echo.

.venv\Scripts\python.exe relay_server.py --port %PORT% --host 0.0.0.0

echo.
echo Server stopped.
pause
