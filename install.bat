@echo off
setlocal enabledelayedexpansion
title LivingTree — One-Command Auto-Deploy (Windows)
:: Usage: powershell -c "irm https://...install.ps1 | iex"
::        install.bat --port 8100 --relay

set PORT=%1
if "%PORT%"=="" set PORT=8100
if "%PORT:~0,2%"=="--" set PORT=8100

set MODE=client
if "%2"=="--relay" set MODE=relay
if "%1"=="--relay" set MODE=relay

set INSTALL_DIR=%USERPROFILE%\livingtree
set GITHUB_URL=https://github.com/ookok/LivingTreeAlAgent.git
set GITEE_URL=https://gitee.com/ookok/LivingTreeAlAgent.git

echo.
echo ╔══════════════════════════════════════════╗
echo ║  LivingTree Auto-Deploy (Windows)       ║
echo ║  Mode: %MODE%  Port: %PORT%               ║
echo ╚══════════════════════════════════════════╝
echo.

:: [1/7] Check Python
echo [1/7] Checking Python...
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   Python not found. Downloading Python 3.14...
    powershell -c "Invoke-WebRequest -Uri 'https://mirrors.huaweicloud.com/python/3.14.0/python-3.14.0-amd64.exe' -OutFile '%TEMP%\python314.exe'" 2>nul
    if exist "%TEMP%\python314.exe" (
        start /wait "" "%TEMP%\python314.exe" /quiet InstallAllUsers=0 Include_test=0
        echo   Python 3.14 installed. Please re-run this script.
        exit /b 0
    )
)
python --version

:: [2/7] Clone/Update project
echo [2/7] Downloading project...
if exist "%INSTALL_DIR%" (
    echo   Directory exists — updating...
    cd /d "%INSTALL_DIR%"
    git pull --ff-only origin main 2>nul
) else (
    git clone --depth 1 "%GITHUB_URL%" "%INSTALL_DIR%" 2>nul || (
        echo   GitHub failed, trying Gitee mirror...
        git clone --depth 1 "%GITEE_URL%" "%INSTALL_DIR%" 2>nul || (
            echo   ERROR: Cannot clone. Check network or install git.
            pause
            exit /b 1
        )
    )
)
cd /d "%INSTALL_DIR%"

:: [3/7] Venv
echo [3/7] Virtual environment...
if not exist ".venv" python -m venv .venv
call .venv\Scripts\activate.bat

:: [4/7] Dependencies
echo [4/7] Installing dependencies...
pip install -e . --quiet 2>nul
pip install aiohttp pyyaml pydantic loguru rich textual --quiet 2>nul
echo   Dependencies ready.

:: [5/7] Verify
echo [5/7] Verifying...
.venv\Scripts\python.exe -c "from livingtree.tui.app import LivingTreeTuiApp; print('   OK')" 2>nul || echo   WARNING: Import check failed

:: [6/7] Launcher
echo [6/7] Creating launcher...
echo @echo off > livingtree.bat
echo cd /d "%%~dp0" >> livingtree.bat
echo call .venv\Scripts\activate.bat >> livingtree.bat
echo if "%%1"=="relay" ( >> livingtree.bat
echo     python relay_server.py --port %PORT% %%2 %%3 %%4 %%5 >> livingtree.bat
echo ) else ( >> livingtree.bat
echo     python -m livingtree tui %%* >> livingtree.bat
echo ) >> livingtree.bat

:: Add to PATH
setx PATH "%INSTALL_DIR%;%PATH%" >nul 2>&1

:: [7/7] Start
echo [7/7] Done^^!
echo.
if "%MODE%"=="relay" (
    echo Starting relay server on port %PORT%...
    echo.
    .venv\Scripts\python.exe relay_server.py --port %PORT%
) else (
    echo ╔══════════════════════════════════════════╗
    echo ║  LivingTree installed successfully!      ║
    echo ║                                          ║
    echo ║  Launch TUI:    livingtree                ║
    echo ║  Relay server:  livingtree relay          ║
    echo ║  Update:        git pull                  ║
    echo ╚══════════════════════════════════════════╝
    echo.
    pause
)
