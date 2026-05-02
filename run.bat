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
    echo [X] 未检测到 Python，请先安装 Python %PYTHON_REQUIRED_MAJOR%.%PYTHON_REQUIRED_MINOR%+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%a in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%a"
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set "PYTHON_MAJOR=%%a"
    set "PYTHON_MINOR=%%b"
)

if %PYTHON_MAJOR% lss %PYTHON_REQUIRED_MAJOR% (
    echo [X] Python 版本过低，需要 %PYTHON_REQUIRED_MAJOR%.%PYTHON_REQUIRED_MINOR%+
    pause
    exit /b 1
)
if %PYTHON_MAJOR% equ %PYTHON_REQUIRED_MAJOR% if %PYTHON_MINOR% lss %PYTHON_REQUIRED_MINOR% (
    echo [X] Python 版本过低，需要 %PYTHON_REQUIRED_MAJOR%.%PYTHON_REQUIRED_MINOR%+
    pause
    exit /b 1
)

echo [OK] Python %PYTHON_VERSION% 符合要求

:check_deps
echo [2/5] 检查依赖...
python -c "from livingtree.infrastructure.config import get_config; get_config()" >nul 2>&1
if errorlevel 1 (
    echo 正在安装依赖...
    pip install -e client/ -q
    if errorlevel 1 (
        pip install -r requirements.txt -q
    )
)
echo [OK] 依赖检查完成

:menu
echo [3/5] 选择启动模式:
echo.
echo    [1] 桌面客户端 (PyQt6 GUI)
echo    [2] API 服务器   (FastAPI, http://localhost:8100)
echo    [3] 交互式对话   (命令行)
echo    [4] 集成测试
echo    [5] 退出
echo.
set /p "MODE=请输入选项 [1-5]: "

if "%MODE%"=="1" goto run_client
if "%MODE%"=="2" goto run_server
if "%MODE%"=="3" goto run_quick
if "%MODE%"=="4" goto run_test
if "%MODE%"=="5" goto exit
echo 无效选项，请重新选择
goto menu

:run_client
echo.
echo [4/5] 启动桌面客户端...
python main.py client
goto end

:run_server
echo.
echo [4/5] 启动 API 服务器 (http://localhost:8100)...
echo API 文档: http://localhost:8100/docs
echo.
python -m livingtree server
goto end

:run_quick
echo.
echo [4/5] 启动交互式对话模式...
echo 输入 quit 退出
echo.
python -m livingtree quick
goto end

:run_test
echo.
echo [4/5] 运行集成测试...
python -m livingtree test
goto end

:end
echo.
pause
goto exit

:exit
endlocal
echo.
echo 感谢使用 LivingTreeAI！
