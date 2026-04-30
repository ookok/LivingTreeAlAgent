@echo off
chcp 65001 >nul
title LivingTreeAI Launcher

echo.
echo ██╗      █████╗ ██╗   ██╗███████╗██╗   ██╗██████╗ 
echo ██║     ██╔══██╗██║   ██║██╔════╝╚██╗ ██╔╝██╔══██╗
echo ██║     ███████║██║   ██║█████╗   ╚████╔╝ ██████╔╝
echo ██║     ██╔══██║██║   ██║██╔══╝    ╚██╔╝  ██╔═══╝ 
echo ███████╗██║  ██║╚██████╔╝███████╗   ██║   ██║     
echo ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝   ╚═╝     
echo.
echo                    LivingTreeAI 一键启动器
echo ================================================

setlocal enabledelayedexpansion

set "PYTHON_REQUIRED_MAJOR=3"
set "PYTHON_REQUIRED_MINOR=11"

:check_python
echo [1/5] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 Python，请先安装 Python %PYTHON_REQUIRED_MAJOR%.%PYTHON_REQUIRED_MINOR%+
    echo 📥 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%a in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%a"
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set "PYTHON_MAJOR=%%a"
    set "PYTHON_MINOR=%%b"
)

if %PYTHON_MAJOR% lss %PYTHON_REQUIRED_MAJOR% (
    echo ❌ Python 版本过低，需要 %PYTHON_REQUIRED_MAJOR%.%PYTHON_REQUIRED_MINOR%+
    pause
    exit /b 1
)
if %PYTHON_MAJOR% equ %PYTHON_REQUIRED_MAJOR% if %PYTHON_MINOR% lss %PYTHON_REQUIRED_MINOR% (
    echo ❌ Python 版本过低，需要 %PYTHON_REQUIRED_MAJOR%.%PYTHON_REQUIRED_MINOR%+
    pause
    exit /b 1
)

echo ✅ Python %PYTHON_VERSION% 符合要求

:check_git
echo [2/5] 检查 Git...
git --version >nul 2>&1
if errorlevel 1 (
    echo ⚠️  未检测到 Git，将跳过更新检测
    set "HAS_GIT=0"
) else (
    echo ✅ Git 已安装
    set "HAS_GIT=1"
)

:check_updates
if %HAS_GIT% equ 1 (
    echo [3/5] 检查更新...
    git fetch --quiet
    for /f %%a in ('git rev-list --count HEAD..origin/master 2^>nul') do set "UPDATES=%%a"
    if !UPDATES! gtr 0 (
        echo 📥 发现 !UPDATES! 个更新
        set /p "DO_UPDATE=是否自动更新? (Y/N): "
        if /i "!DO_UPDATE!"=="Y" (
            echo 正在拉取更新...
            git pull --quiet
            echo ✅ 更新完成
        )
    ) else (
        echo ✅ 当前已是最新版本
    )
)

:install_deps
echo [4/5] 检查依赖...
python -c "import sys; sys.path.insert(0, 'client/src'); from business.config import UnifiedConfig" >nul 2>&1
if errorlevel 1 (
    echo 📦 正在安装依赖...
    pip install -e client/ -e server/relay_server/ -q
    if errorlevel 1 (
        echo ⚠️  使用备用依赖安装...
        pip install -r requirements.txt -q
    )
)
echo ✅ 依赖检查完成

:run_client
echo [5/5] 启动 LivingTreeAI...
echo.
python main.py client

:exit
endlocal
echo.
echo 感谢使用 LivingTreeAI！
pause