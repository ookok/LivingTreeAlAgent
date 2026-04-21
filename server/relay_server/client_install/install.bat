@echo off
REM ============================================================================
REM Hermes Desktop 客户端安装脚本
REM ============================================================================
REM 功能:
REM   1. 检测系统环境 (Windows/Linux/macOS)
REM   2. 下载最新版本的 Hermes Desktop
REM   3. 自动安装依赖
REM   4. 配置零配置更新系统
REM   5. 启动客户端
REM
REM 使用方法:
REM   Windows: install.bat [版本号]
REM   Linux/macOS: bash install.sh [版本号]
REM
REM 示例:
REM   install.bat 1.2.0
REM   bash install.sh latest
REM ============================================================================

setlocal enabledelayedexpansion

REM ============================================================================
REM 配置常量
REM ============================================================================
set "APP_NAME=HermesDesktop"
set "INSTALL_DIR=%USERPROFILE%\.hermes-desktop"
set "CONFIG_DIR=%APPDATA%\.hermes-desktop"
set "CACHE_DIR=%LOCALAPPDATA%\.hermes-desktop\cache"
set "LOG_FILE=%INSTALL_DIR%\logs\install.log"

REM 中继服务器地址 (零配置引导节点)
set "RELAY_SERVERS=https://relay1.mogoo.com,https://relay2.mogoo.com,https://relay3.mogoo.com"
set "BOOT_SERVERS=boot1.mogoo.com,boot2.mogoo.com,boot3.mogoo.com"

REM 默认版本
set "TARGET_VERSION=%~1"
if "%TARGET_VERSION%"=="" set "TARGET_VERSION=latest"

REM ============================================================================
REM 日志函数
REM ============================================================================
:log
echo [%date% %time%] %~1
echo [%date% %time%] %~1 >> "%LOG_FILE%"
goto :eof

REM ============================================================================
REM 主安装流程
REM ============================================================================
:main
echo.
echo ==============================================================
echo   Hermes Desktop 客户端安装程序
echo   版本: %TARGET_VERSION%
echo ==============================================================
echo.

REM 创建目录结构
call :create_directories

REM 检测系统环境
call :detect_environment

REM 检查依赖
call :check_dependencies

REM 下载客户端
call :download_client

REM 安装依赖
call :install_dependencies

REM 配置零配置更新系统
call :configure_zero_update

REM 启动客户端
call :launch_client

echo.
echo ==============================================================
echo   安装完成！
echo ==============================================================
echo.
echo   安装目录: %INSTALL_DIR%
echo   配置目录: %CONFIG_DIR%
echo   日志文件: %LOG_FILE%
echo.
echo   提示: 客户端已启动，系统将自动检查更新
echo ==============================================================

goto :end

REM ============================================================================
REM 创建目录结构
REM ============================================================================
:create_directories
call :log "创建目录结构..."

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
if not exist "%CACHE_DIR%" mkdir "%CACHE_DIR%"
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"
if not exist "%INSTALL_DIR%\updates" mkdir "%INSTALL_DIR%\updates"
if not exist "%INSTALL_DIR%\data" mkdir "%INSTALL_DIR%\data"
if not exist "%INSTALL_DIR%\keys" mkdir "%INSTALL_DIR%\keys"

call :log "目录结构创建完成"
goto :eof

REM ============================================================================
REM 检测系统环境
REM ============================================================================
:detect_environment
call :log "检测系统环境..."

REM 检测操作系统
if defined OS (
    set "SYSTEM_OS=Windows_NT"
) else (
    set "SYSTEM_OS=Unknown"
)

REM 检测架构
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    set "SYSTEM_ARCH=x64"
) else if "%PROCESSOR_ARCHITECTURE%"=="x86" (
    set "SYSTEM_ARCH=x86"
) else (
    set "SYSTEM_ARCH=x64"
)

REM 检测内存
systeminfo | findstr /C:"Total Physical Memory" > temp_mem.txt
set /p MEMORY_INFO=<temp_mem.txt
del temp_mem.txt

REM 检测网络
ping -n 1 8.8.8.8 >nul 2>&1
if errorlevel 1 (
    set "NETWORK_STATUS=offline"
    call :log "警告: 网络不可用"
) else (
    set "NETWORK_STATUS=online"
)

call :log "系统: %SYSTEM_OS% %SYSTEM_ARCH%"
call :log "内存: %MEMORY_INFO%"
call :log "网络: %NETWORK_STATUS%"
goto :eof

REM ============================================================================
REM 检查依赖
REM ============================================================================
:check_dependencies
call :log "检查依赖..."

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if errorlevel 1 (
        call :log "错误: 未安装 Python，请先安装 Python 3.10+"
        goto :error
    ) else (
        set "PYTHON_CMD=python3"
    )
) else (
    set "PYTHON_CMD=python"
)

REM 检查 PyQt6
%PYTHON_CMD% -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    call :log "提示: PyQt6 未安装，将自动安装..."
    set "PYQT6_MISSING=1"
) else (
    call :log "PyQt6 已安装"
)

call :log "依赖检查完成"
goto :eof

REM ============================================================================
REM 下载客户端
REM ============================================================================
:download_client
call :log "下载 Hermes Desktop %TARGET_VERSION%..."

REM 尝试从 P2P 网络发现最新版本
call :discover_version

REM 如果 P2P 失败，使用中心服务器
if not defined DISCOVERED_VERSION (
    call :download_from_server
) else (
    set "TARGET_VERSION=%DISCOVERED_VERSION%"
)

REM 下载更新包
set "UPDATE_URL=https://releases.mogoo.com/hermes-desktop/%TARGET_VERSION%/hermes-desktop-%TARGET_VERSION%-win64.zip"
set "UPDATE_FILE=%CACHE_DIR%\hermes-desktop-%TARGET_VERSION%-win64.zip"

call :log "下载地址: %UPDATE_URL%"

powershell -Command "Invoke-WebRequest -Uri '%UPDATE_URL%' -OutFile '%UPDATE_FILE%' -UseBasicParsing"

if not exist "%UPDATE_FILE%" (
    call :log "错误: 下载失败"
    goto :error
)

REM 验证签名
call :verify_signature

REM 解压
call :log "解压安装包..."
powershell -Command "Expand-Archive -Path '%UPDATE_FILE%' -DestinationPath '%INSTALL_DIR%' -Force"

call :log "客户端下载完成"
goto :eof

REM ============================================================================
REM 从 P2P 网络发现版本
REM ============================================================================
:discover_version
call :log "从 P2P 网络发现最新版本..."

REM 尝试连接引导节点
for %%S in (%BOOT_SERVERS%) do (
    ping -n 1 %%S >nul 2>&1
    if not errorlevel 1 (
        call :log "连接引导节点: %%S"
        
        REM 获取版本信息
        for /f "tokens=*" %%V in ('curl -s https://%%S/api/version/latest') do (
            set "DISCOVERED_VERSION=%%V"
            call :log "发现版本: %%V"
            goto :eof
        )
    )
)

REM P2P 发现失败，使用默认
call :log "P2P 发现失败，使用默认版本"
set "DISCOVERED_VERSION=latest"
goto :eof

REM ============================================================================
REM 从服务器下载
REM ============================================================================
:download_from_server
call :log "从中心服务器下载..."

REM 尝试多个镜像
set "MIRRORS=https://releases.mogoo.com,https://mirror.mogoo.com,https://cdn.mogoo.com"

for %%M in (%MIRRORS%) do (
    call :log "尝试镜像: %%M"
    
    set "TEST_URL=%%M/hermes-desktop/%TARGET_VERSION%/hermes-desktop-%TARGET_VERSION%-win64.zip"
    curl -s -o /dev/null -w "%%{http_code}" "!TEST_URL!"
    
    if errorlevel 200 (
        set "UPDATE_URL=!TEST_URL!"
        goto :eof
    )
)

goto :eof

REM ============================================================================
REM 验证签名
REM ============================================================================
:verify_signature
call :log "验证更新包签名..."

set "SIG_FILE=%UPDATE_FILE%.sig"
set "PUB_KEY=%INSTALL_DIR%\keys\hermes-desktop.pub"

REM 下载签名
curl -s -o "%SIG_FILE%" "%UPDATE_URL%.sig"

REM 下载公钥 (首次安装)
if not exist "%PUB_KEY%" (
    curl -s -o "%PUB_KEY%" "https://keys.mogoo.com/hermes-desktop.pub"
)

REM 验证 (需要 GPG 或 OpenSSL)
where gpg >nul 2>&1
if not errorlevel 1 (
    gpg --verify "%SIG_FILE%" "%UPDATE_FILE%"
) else (
    where openssl >nul 2>&1
    if not errorlevel 1 (
        openssl dgst -sha256 -verify "%PUB_KEY%" -signature "%SIG_FILE%" "%UPDATE_FILE%"
    ) else (
        call :log "警告: 无法验证签名，跳过"
    )
)

call :log "签名验证完成"
goto :eof

REM ============================================================================
REM 安装依赖
REM ============================================================================
:install_dependencies
call :log "安装 Python 依赖..."

REM 升级 pip
%PYTHON_CMD% -m pip install --upgrade pip

REM 安装 PyQt6
if defined PYQT6_MISSING (
    %PYTHON_CMD% -m pip install PyQt6
)

REM 安装其他依赖
%PYTHON_CMD% -m pip install requests charset-normalizer

REM 安装本地依赖
if exist "%INSTALL_DIR%\requirements.txt" (
    %PYTHON_CMD% -m pip install -r "%INSTALL_DIR%\requirements.txt"
)

call :log "依赖安装完成"
goto :eof

REM ============================================================================
REM 配置零配置更新系统
REM ============================================================================
:configure_zero_update
call :log "配置零配置更新系统..."

REM 创建零配置更新配置
set "ZERO_CONFIG=%CONFIG_DIR%\zero_update.json"

(
echo {
echo   "enabled": true,
echo   "auto_update": true,
echo   "update_channel": "stable",
echo   "check_interval_hours": 24,
echo   "relay_servers": ["https://relay1.mogoo.com", "https://relay2.mogoo.com"],
echo   "boot_nodes": ["boot1.mogoo.com", "boot2.mogoo.com", "boot3.mogoo.com"],
echo   "auto_discovery": true,
echo   "ai_optimized": true,
echo   "network_adaptive": true,
echo   "notification_style": "smart",
echo   "habit_learning": true
echo }
) > "%ZERO_CONFIG%"

REM 创建首次运行标记
set "FIRST_RUN=%INSTALL_DIR%\first_run.flag"
(
echo {
echo   "install_time": "%date% %time%",
echo   "version": "%TARGET_VERSION%",
echo   "auto_update_enabled": true
echo }
) > "%FIRST_RUN%"

call :log "零配置更新系统配置完成"
goto :eof

REM ============================================================================
REM 启动客户端
REM ============================================================================
:launch_client
call :log "启动 Hermes Desktop..."

set "LAUNCHER=%INSTALL_DIR%\HermesDesktop.exe"
if exist "%INSTALL_DIR%\HermesDesktop.exe" (
    start "" "%LAUNCHER%"
) else if exist "%INSTALL_DIR%\HermesDesktop.py" (
    %PYTHON_CMD% "%INSTALL_DIR%\HermesDesktop.py"
) else (
    call :log "错误: 未找到启动程序"
    goto :error
)

call :log "客户端已启动"
goto :eof

REM ============================================================================
REM 错误处理
REM ============================================================================
:error
echo.
echo ==============================================================
echo   安装失败！请查看日志: %LOG_FILE%
echo ==============================================================
echo.
pause
exit /b 1

REM ============================================================================
REM 结束
REM ============================================================================
:end
endlocal
pause