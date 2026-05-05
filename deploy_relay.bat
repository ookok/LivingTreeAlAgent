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

:: ═══ Step 1: Check Python ═══
echo [1/5] Checking Python...
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found. Install Python 3.14+ first.
    pause
    exit /b 1
)
python --version

:: ═══ Step 2: Create venv ═══
echo.
echo [2/5] Setting up virtual environment...
if not exist ".venv" (
    python -m venv .venv
    echo venv created.
) else (
    echo venv already exists.
)

:: ═══ Step 3: Install dependencies ═══
echo.
echo [3/5] Installing dependencies...
call .venv\Scripts\activate.bat
pip install -e . --quiet 2>nul
pip install aiohttp pyyaml pydantic loguru --quiet 2>nul
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
