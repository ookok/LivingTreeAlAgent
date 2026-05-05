@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
title LivingTree Installer

set PORT=8888
set MODE=client
if "%1"=="--relay" set MODE=relay
if "%2"=="--relay" set MODE=relay

set INSTALL_DIR=%USERPROFILE%\livingtree
set GITHUB_URL=https://github.com/ookok/LivingTreeAlAgent.git
set GITEE_URL=https://gitee.com/ookok/LivingTreeAlAgent.git
set GITHUB_ZIP=https://github.com/ookok/LivingTreeAlAgent/archive/refs/heads/main.zip
set GITEE_ZIP=https://gitee.com/ookok/LivingTreeAlAgent/repository/archive/main.zip

echo.
echo ===========================================
echo   LivingTree Auto-Deploy (Windows)
echo   Mode: %MODE%
echo ===========================================
echo.

echo [1/7] Checking Python 3.14...
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
    echo   Downloading Python 3.14...
    powershell -c "$u='https://mirrors.huaweicloud.com/python/3.14.0/python-3.14.0-amd64.exe';$o='%TEMP%\python314.exe';(New-Object Net.WebClient).DownloadFile($u,$o)" 2>nul
    if exist "%TEMP%\python314.exe" (
        start /wait "" "%TEMP%\python314.exe" /quiet InstallAllUsers=0 Include_test=0
        del "%TEMP%\python314.exe" 2>nul
    )
    if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python314\python.exe
)
if "%PYTHON_CMD%"=="" (
    echo   ERROR: Python 3.14 required. https://www.python.org/downloads/
    pause
    exit /b 1
)
echo   OK

echo [2/7] Downloading project...
if exist "%INSTALL_DIR%\pyproject.toml" (
    cd /d "%INSTALL_DIR%" 2>nul
    git pull --ff-only origin main 2>nul
) else (
    where git >nul 2>&1 && git clone --depth 1 "%GITHUB_URL%" "%INSTALL_DIR%" 2>nul
    if not exist "%INSTALL_DIR%\pyproject.toml" (
        powershell -c "Invoke-WebRequest '%GITHUB_ZIP%' -OutFile '%TEMP%\lt.zip'" 2>nul
        powershell -c "Expand-Archive '%TEMP%\lt.zip' '%INSTALL_DIR%' -Force" 2>nul
        move "%INSTALL_DIR%\LivingTreeAlAgent-main\*" "%INSTALL_DIR%\" 2>nul
        rmdir /s /q "%INSTALL_DIR%\LivingTreeAlAgent-main" 2>nul
    )
)
if not exist "%INSTALL_DIR%\pyproject.toml" (
    echo   ERROR: Cannot download. Check network.
    pause & exit /b 1
)
cd /d "%INSTALL_DIR%"

echo [3/7] Virtual environment...
if not exist ".venv" "%PYTHON_CMD%" -m venv .venv
call .venv\Scripts\activate.bat >nul 2>&1

echo [4/7] Dependencies...
.venv\Scripts\python.exe -m pip install -e . --quiet 2>nul
.venv\Scripts\python.exe -m pip install aiohttp pyyaml pydantic loguru rich textual --quiet 2>nul

echo [5/7] Verifying...
.venv\Scripts\python.exe -c "from livingtree.tui.app import LivingTreeTuiApp; print('OK')" 2>nul || echo   WARNING

echo [6/7] Creating launcher...
echo @echo off > livingtree.bat
echo cd /d "%%~dp0" >> livingtree.bat
echo call .venv\Scripts\activate.bat >> livingtree.bat
echo if "%%1"=="relay" ( >> livingtree.bat
echo     python relay_server.py --port 8888 %%2 %%3 %%4 %%5 >> livingtree.bat
echo ) else ( >> livingtree.bat
echo     python -m livingtree tui %%* >> livingtree.bat
echo ) >> livingtree.bat

echo [7/7] Done
echo.
if "%MODE%"=="relay" (
    .venv\Scripts\python.exe relay_server.py --port 8888
) else (
    echo   Run: livingtree
    echo   or: cd %INSTALL_DIR% ^&^& python -m livingtree tui
)
pause
