@echo off
REM ============================================================================
REM Hermes Desktop 客户端自动更新脚本
REM ============================================================================
REM 功能:
REM   1. 后台检查更新
REM   2. 智能下载 (P2P + 镜像)
REM   3. 渐进式更新通知
REM   4. 一键应用更新
REM   5. 自动生成更新说明
REM   6. 同步到博客和论坛
REM
REM 使用方法:
REM   update.bat [选项]
REM
REM   选项:
REM     /silent    - 静默模式，后台更新
REM     /check     - 仅检查更新，不下载
REM     /force     - 强制更新，即使已最新
REM     /rollback  - 回滚到上一个版本
REM
REM 示例:
REM   update.bat /silent
REM   update.bat /check
REM   update.bat /force
REM ============================================================================

setlocal enabledelayedexpansion

REM ============================================================================
REM 配置常量
REM ============================================================================
set "APP_NAME=HermesDesktop"
set "INSTALL_DIR=%USERPROFILE%\.hermes-desktop"
set "CONFIG_DIR=%APPDATA%\.hermes-desktop"
set "CACHE_DIR=%LOCALAPPDATA%\.hermes-desktop\cache"
set "UPDATE_DIR=%INSTALL_DIR%\updates"
set "LOG_FILE=%INSTALL_DIR%\logs\update.log"

set "CURRENT_VERSION=unknown"
set "LATEST_VERSION=unknown"
set "UPDATE_MODE=silent"
set "FORCE_UPDATE=0"

REM 中继服务器
set "RELAY_SERVERS=https://relay1.mogoo.com,https://relay2.mogoo.com"
set "UPDATE_API=/api/v1/update"

REM ============================================================================
REM 日志函数
REM ============================================================================
:log
echo [%date% %time%] %~1
echo [%date% %time%] %~1 >> "%LOG_FILE%"
goto :eof

REM ============================================================================
REM 解析命令行参数
REM ============================================================================
:parse_args
if "%~1"=="" goto :main

if /i "%~1"=="/silent" (
    set "UPDATE_MODE=silent"
    shift
    goto :parse_args
)

if /i "%~1"=="/check" (
    set "UPDATE_MODE=check"
    shift
    goto :parse_args
)

if /i "%~1"=="/force" (
    set "FORCE_UPDATE=1"
    set "UPDATE_MODE=silent"
    shift
    goto :parse_args
)

if /i "%~1"=="/rollback" (
    set "UPDATE_MODE=rollback"
    shift
    goto :parse_args
)

shift
goto :parse_args

REM ============================================================================
REM 主流程
REM ============================================================================
:main
call :log "========== 开始更新流程 =========="
call :log "更新模式: %UPDATE_MODE%"

REM 读取当前版本
call :read_current_version

REM 解析模式
if "%UPDATE_MODE%"=="check" goto :check_only
if "%UPDATE_MODE%"=="rollback" goto :rollback_version

REM 静默更新流程
call :check_for_updates
if errorlevel 1 (
    call :log "检查更新失败"
    goto :error
)

call :decide_update_strategy

if "%HAS_UPDATE%"=="0" (
    call :log "已是最新版本: %CURRENT_VERSION%"
    goto :success
)

call :download_update
if errorlevel 1 (
    call :log "下载更新失败"
    goto :error
)

call :apply_update
if errorlevel 1 (
    call :log "应用更新失败"
    goto :error
)

call :generate_update_notes

call :sync_to_blog_forum

goto :success

REM ============================================================================
REM 读取当前版本
REM ============================================================================
:read_current_version
call :log "读取当前版本信息..."

set "VERSION_FILE=%INSTALL_DIR%\version.ini"
if exist "%VERSION_FILE%" (
    for /f "tokens=2 delims==" %%a in ('findstr "version" "%VERSION_FILE%"') do (
        set "CURRENT_VERSION=%%a"
    )
) else (
    REM 尝试从 Python 获取
    python -c "import json; print(json.load(open('%CONFIG_DIR%\config.json'))['version'])" > temp_ver.txt 2>nul
    set /p CURRENT_VERSION=<temp_ver.txt
    del temp_ver.txt 2>nul
)

call :log "当前版本: %CURRENT_VERSION%"
goto :eof

REM ============================================================================
REM 仅检查更新
REM ============================================================================
:check_only
call :check_for_updates

if "%HAS_UPDATE%"=="1" (
    echo.
    echo 发现新版本: %LATEST_VERSION%
    echo 当前版本: %CURRENT_VERSION%
    echo 更新大小: %UPDATE_SIZE%
    echo.
    echo 查看详情请访问: https://blog.mogoo.com/hermes-update
) else (
    echo.
    echo 已是最新版本: %CURRENT_VERSION%
)

goto :end

REM ============================================================================
REM 检查更新
REM ============================================================================
:check_for_updates
call :log "检查更新..."

REM P2P 网络发现
call :discover_latest_version_p2p

if "%LATEST_VERSION%"=="unknown" (
    REM 中心服务器查询
    call :query_center_server
)

REM 比较版本
call :compare_versions

goto :eof

REM ============================================================================
REM P2P 网络发现最新版本
REM ============================================================================
:discover_latest_version_p2p
call :log "P2P 网络发现最新版本..."

REM 尝试连接种子节点
for %%S in (%RELAY_SERVERS%) do (
    curl -s "https://%%S%UPDATE_API%/check?version=%CURRENT_VERSION%" > temp_update.json 2>nul

    if exist temp_update.json (
        for /f "tokens=*" %%v in ('findstr "latest_version" temp_update.json') do (
            set "LATEST_VERSION=%%v"
        )
        del temp_update.json
        goto :eof
    )
)

set "LATEST_VERSION=unknown"
goto :eof

REM ============================================================================
REM 查询中心服务器
REM ============================================================================
:query_center_server
call :log "查询中心服务器..."

for %%M in (releases.mogoo.com mirror.mogoo.com cdn.mogoo.com) do (
    curl -s "https://%%M/api/version/latest" > temp_ver.json 2>nul

    if exist temp_ver.json (
        set /p LATEST_VERSION=<temp_ver.json
        del temp_ver.json
        goto :eof
    )
)

set "LATEST_VERSION=unknown"
goto :eof

REM ============================================================================
REM 比较版本
REM ============================================================================
:compare_versions
call :log "比较版本: %CURRENT_VERSION% vs %LATEST_VERSION%..."

REM 简单版本比较 (实际应该用语义版本比较)
if "%LATEST_VERSION%"=="%CURRENT_VERSION%" (
    set "HAS_UPDATE=0"
    call :log "已是最新"
) else if "%LATEST_VERSION%"=="unknown" (
    set "HAS_UPDATE=0"
    call :log "无法获取最新版本"
) else (
    set "HAS_UPDATE=1"
    call :log "发现新版本: %LATEST_VERSION%"
)

REM 获取更新大小
if "%HAS_UPDATE%"=="1" (
    curl -s "https://releases.mogoo.com/api/update/size?from=%CURRENT_VERSION%&to=%LATEST_VERSION%" > temp_size.txt 2>nul
    set /p UPDATE_SIZE=<temp_size.txt
    if not defined UPDATE_SIZE set "UPDATE_SIZE=未知"
)

goto :eof

REM ============================================================================
REM AI 决策更新策略
REM ============================================================================
:decide_update_strategy
call :log "AI 决策更新策略..."

REM 分析网络环境
call :analyze_network_environment

REM 分析时间段
call :analyze_time_period

REM 分析用户习惯
call :analyze_user_habits

REM 决定策略
if "%USER_PREF_IMMEDIATE%"=="1" (
    set "STRATEGY=notify_and_apply"
    call :log "策略: 立即提示并应用 (用户偏好)"
) else if "%IS_WORKING_HOURS%"=="1" (
    set "STRATEGY=background_silent"
    call :log "策略: 工作时段静默"
) else if "%IS_MOBILE_NETWORK%"=="1" (
    set "STRATEGY=small_file_only"
    call :log "策略: 仅小文件 (移动网络)"
) else (
    set "STRATEGY=smart_delayed"
    call :log "策略: 智能延迟更新"
)

goto :eof

REM ============================================================================
REM 分析网络环境
REM ============================================================================
:analyze_network_environment
call :log "分析网络环境..."

REM 检测是否在中国大陆
ping -n 1 cn.mogoo.com >nul 2>&1
if not errorlevel 1 (
    set "IS_CHINA=1"
    set "USE_MIRROR=1"
    call :log "检测到中国大陆网络，使用镜像优先"
) else (
    set "IS_CHINA=0"
    set "USE_MIRROR=0"
)

REM 检测网络质量
ping -n 3 8.8.8.8 >nul 2>&1
if errorlevel 1 (
    set "NETWORK_QUALITY=poor"
) else (
    set "NETWORK_QUALITY=good"
)

REM 检测是否移动网络 (通过网关判断)
ipconfig | findstr "Mobile" >nul 2>&1
if not errorlevel 1 (
    set "IS_MOBILE_NETWORK=1"
) else (
    set "IS_MOBILE_NETWORK=0"
)

goto :eof

REM ============================================================================
REM 分析时间段
REM ============================================================================
:analyze_time_period
call :log "分析时间段..."

REM 获取当前小时
for /f "tokens=1-2 delims=: " %%a in ('time /t') do (
    set "CURRENT_HOUR=%%a"
)

REM 判断工作时间 (9:00-18:00)
if %CURRENT_HOUR% GEQ 9 (
    if %CURRENT_HOUR% LSS 18 (
        set "IS_WORKING_HOURS=1"
    ) else (
        set "IS_WORKING_HOURS=0"
    )
) else (
    set "IS_WORKING_HOURS=0"
)

call :log "当前小时: %CURRENT_HOUR%, 工作时间: %IS_WORKING_HOURS%"
goto :eof

REM ============================================================================
REM 分析用户习惯
REM ============================================================================
:analyze_user_habits
call :log "分析用户习惯..."

set "USER_PREFS_FILE=%CONFIG_DIR%\user_prefs.json"

if exist "%USER_PREFS_FILE%" (
    findstr "immediate_update" "%USER_PREFS_FILE%" >nul 2>&1
    if not errorlevel 1 (
        set "USER_PREF_IMMEDIATE=1"
    ) else (
        set "USER_PREF_IMMEDIATE=0"
    )
) else (
    set "USER_PREF_IMMEDIATE=0"
)

REM 记录更新尝试次数
set "UPDATE_ATTEMPTS_FILE=%INSTALL_DIR%\update_attempts.txt"
if exist "%UPDATE_ATTEMPTS_FILE%" (
    set /p UPDATE_ATTEMPTS=<"%UPDATE_ATTEMPTS_FILE%"
    set /a UPDATE_ATTEMPTS+=1
) else (
    set "UPDATE_ATTEMPTS=1"
)
echo !UPDATE_ATTEMPTS! > "%UPDATE_ATTEMPTS_FILE%"

goto :eof

REM ============================================================================
REM 下载更新
REM ============================================================================
:download_update
call :log "下载更新包..."

set "UPDATE_FILE=%UPDATE_DIR%\hermes-desktop-%LATEST_VERSION%.zip"
set "UPDATE_SIG=%UPDATE_FILE%.sig"

REM 创建更新目录
if not exist "%UPDATE_DIR%" mkdir "%UPDATE_DIR%"

REM 多源下载 (P2P + 镜像)
call :download_from_p2p
if errorlevel 1 (
    call :log "P2P 下载失败，尝试镜像..."
    call :download_from_mirror
)

REM 验证签名
call :verify_update_signature

REM 记录下载信息
call :record_download_info

call :log "下载完成: %UPDATE_FILE%"
goto :eof

REM ============================================================================
REM P2P 下载
REM ============================================================================
:download_from_p2p
call :log "从 P2P 网络下载..."

REM 查询可用节点
curl -s "https://relay1.mogoo.com%UPDATE_API%/peers?version=%LATEST_VERSION%" > temp_peers.json

REM 从 P2P 网络下载分片
set "P2P_DOWNLOAD_URL=https://relay1.mogoo.com%UPDATE_API%/download/%LATEST_VERSION%"

curl -L -o "%UPDATE_FILE%" "%P2P_DOWNLOAD_URL%"
if errorlevel 1 exit /b 1

exit /b 0

REM ============================================================================
REM 镜像下载
REM ============================================================================
:download_from_mirror
call :log "从镜像下载..."

set "MIRRORS=https://mirror.mogoo.com,https://cdn.mogoo.com,https://releases.mogoo.com"

for %%M in (!MIRRORS!) do (
    set "MIRROR_URL=%%M/hermes-desktop/!LATEST_VERSION!/hermes-desktop-!LATEST_VERSION!-win64.zip"

    curl -L -o "%UPDATE_FILE%" "!MIRROR_URL!"
    if not errorlevel 1 exit /b 0
)

exit /b 1

REM ============================================================================
REM 验证更新签名
REM ============================================================================
:verify_update_signature
call :log "验证更新签名..."

set "PUB_KEY=%INSTALL_DIR%\keys\hermes-desktop.pub"

REM 下载签名
curl -s -o "%UPDATE_SIG%" "%P2P_DOWNLOAD_URL%.sig"

REM 验证 (使用 OpenSSL 或 GPG)
where openssl >nul 2>&1
if not errorlevel 1 (
    openssl dgst -sha256 -verify "%PUB_KEY%" -signature "%UPDATE_SIG%" "%UPDATE_FILE%"
) else (
    call :log "警告: 无法验证签名"
)

goto :eof

REM ============================================================================
REM 记录下载信息
REM ============================================================================
:record_download_info
call :log "记录下载信息..."

set "DOWNLOAD_INFO=%UPDATE_DIR%\download_info.json"

(
echo {
echo   "version": "%LATEST_VERSION%",
echo   "download_time": "%date% %time%",
echo   "source": "p2p",
echo   "file_size": "%UPDATE_SIZE%",
echo   "status": "downloaded"
echo }
) > "%DOWNLOAD_INFO%"

goto :eof

REM ============================================================================
REM 应用更新
REM ============================================================================
:apply_update
call :log "应用更新..."

REM 备份当前版本
call :backup_current_version

REM 解压更新包
powershell -Command "Expand-Archive -Path '%UPDATE_FILE%' -DestinationPath '%INSTALL_DIR%' -Force"

REM 更新版本文件
set "VERSION_FILE=%INSTALL_DIR%\version.ini"
(
echo [Info]
echo version=%LATEST_VERSION%
echo update_time=%date% %time%
) > "%VERSION_FILE%"

REM 记录更新历史
call :record_update_history

REM 发送内部通知
call :send_internal_notification

call :log "更新应用完成"
goto :eof

REM ============================================================================
REM 备份当前版本
REM ============================================================================
:backup_current_version
call :log "备份当前版本..."

set "BACKUP_DIR=%INSTALL_DIR%\backups"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

set "BACKUP_FILE=%BACKUP_DIR%\hermes-desktop-backup-%CURRENT_VERSION%.zip"

REM 备份核心文件
powershell -Command "Compress-Archive -Path '%INSTALL_DIR%\*.py','%INSTALL_DIR%\*.dll' -DestinationPath '%BACKUP_FILE%'"

REM 保留最近 3 个备份
call :cleanup_old_backups

call :log "备份完成: %BACKUP_FILE%"
goto :eof

REM ============================================================================
REM 清理旧备份
REM ============================================================================
:cleanup_old_backups
call :log "清理旧备份..."

set "BACKUP_COUNT=0"
for /f "tokens=*" %%f in ('dir /b /o-d "%BACKUP_DIR%\*.zip" 2^>nul') do (
    set /a BACKUP_COUNT+=1
    if !BACKUP_COUNT! GTR 3 (
        del "%BACKUP_DIR%\%%f"
        call :log "删除旧备份: %%f"
    )
)

goto :eof

REM ============================================================================
REM 记录更新历史
REM ============================================================================
:record_update_history
call :log "记录更新历史..."

set "HISTORY_FILE=%INSTALL_DIR%\update_history.json"

REM 读取现有历史
if exist "%HISTORY_FILE%" (
    set /p HISTORY=<"%HISTORY_FILE%"
) else (
    set "HISTORY=[]"
)

REM 添加新记录
set "NEW_RECORD={\"version\":\"%LATEST_VERSION%\",\"time\":\"%date% %time%\",\"from\":\"%CURRENT_VERSION%\"}"

REM 追加到历史 (简化处理)
echo [%NEW_RECORD%,!HISTORY!] > "%HISTORY_FILE%"

goto :eof

REM ============================================================================
REM 发送内部通知邮件
REM ============================================================================
:send_internal_notification
call :log "发送内部通知..."

REM 使用内部邮件 API
set "EMAIL_API=https://internal.mogoo.com/api/notify"
set "EMAIL_CONTENT={\"to\":\"devteam@mogoo.com\",\"subject\":\"Hermes Desktop 更新通知\",\"body\":\"版本: %CURRENT_VERSION% -> %LATEST_VERSION%\"}"

curl -X POST -H "Content-Type: application/json" -d "%EMAIL_CONTENT%" "%EMAIL_API%" >nul 2>&1

call :log "内部通知已发送"
goto :eof

REM ============================================================================
REM 生成更新说明
REM ============================================================================
:generate_update_notes
call :log "生成更新说明..."

set "NOTES_FILE=%INSTALL_DIR%\updates\CHANGELOG-%LATEST_VERSION%.md"

REM 从服务器获取更新内容
curl -s "https://releases.mogoo.com/api/changelog/%LATEST_VERSION%" > temp_changelog.json

REM 生成 Markdown 格式的更新说明
(
echo # Hermes Desktop v%LATEST_VERSION% 更新说明
echo.
echo ## 更新信息
echo.
echo ^| 项目 ^| 内容 ^|
echo ^| ----^| ---- ^|
echo ^| 当前版本 ^| %CURRENT_VERSION% ^|
echo ^| 新版本 ^| %LATEST_VERSION% ^|
echo ^| 更新大小 ^| %UPDATE_SIZE% ^|
echo ^| 发布时间 ^| %date% ^|
echo ^| 来源区域 ^| 自动检测 ^|
echo.
echo ## 更新内容
echo.
) > "%NOTES_FILE%"

REM 获取并追加更新内容
REM (实际应该解析 JSON 并格式化)
type temp_changelog.json >> "%NOTES_FILE%" 2>nul

REM 添加内部邮箱信息
(
echo.
echo ## 内部备注
echo.
echo - 内部邮箱: devteam^mogoo.com
echo - 更新来源: P2P网络自动发现
echo - 同步时间: %date% %time%
) >> "%NOTES_FILE%"

del temp_changelog.json 2>nul

call :log "更新说明已生成: %NOTES_FILE%"
goto :eof

REM ============================================================================
REM 同步到博客和论坛
REM ============================================================================
:sync_to_blog_forum
call :log "同步到博客和论坛..."

REM 同步到博客 (详细说明)
call :sync_to_blog

REM 同步到论坛 (简要说明)
call :sync_to_forum

call :log "博客论坛同步完成"
goto :eof

REM ============================================================================
REM 同步到博客
REM ============================================================================
:sync_to_blog
call :log "同步到博客..."

set "BLOG_API=https://blog.mogoo.com/api/posts"
set "BLOG_CONTENT={\"title\":\"Hermes Desktop v%LATEST_VERSION% 更新说明\",\"content_file\":\"%NOTES_FILE%\",\"category\":\"product-update\",\"tags\":[\"hermes\",\"update\",\"v%LATEST_VERSION%\"]}"

REM 发布博客文章
curl -X POST -H "Content-Type: application/json" -d "%BLOG_CONTENT%" "%BLOG_API%" > temp_blog_resp.json 2>nul

REM 获取博客地址
set "BLOG_URL=https://blog.mogoo.com/hermes-update/%LATEST_VERSION%"

call :log "博客已发布: %BLOG_URL%"
goto :eof

REM ============================================================================
REM 同步到论坛
REM ============================================================================
:sync_to_forum
call :log "同步到论坛..."

set "FORUM_API=https://forum.mogoo.com/api/topics"
set "FORUM_CONTENT={\"title\":\"Hermes Desktop v%LATEST_VERSION% 更新\",\"summary\":\"版本 %LATEST_VERSION% 已发布，主要改进：...\",\"blog_url\":\"%BLOG_URL%\",\"category\":\"update-announcements\"}"

REM 发布论坛主题
curl -X POST -H "Content-Type: application/json" -d "%FORUM_CONTENT%" "%FORUM_API%" > temp_forum_resp.json 2>nul

REM 获取论坛地址
set "FORUM_URL=https://forum.mogoo.com/topic/hermes-%LATEST_VERSION%"

call :log "论坛主题已发布: %FORUM_URL%"
goto :eof

REM ============================================================================
REM 回滚版本
REM ============================================================================
:rollback_version
call :log "开始回滚流程..."

REM 列出可用备份
call :list_available_backups

REM 使用最新的备份
for /f "tokens=*" %%f in ('dir /b /o-d "%BACKUP_DIR%\*.zip" 2^>nul') do (
    set "ROLLBACK_FILE=%BACKUP_DIR%\%%f"
    goto :do_rollback
)

call :log "错误: 没有可用的备份"
goto :error

:do_rollback
call :log "回滚到备份: %ROLLBACK_FILE%"

REM 恢复备份
powershell -Command "Expand-Archive -Path '%ROLLBACK_FILE%' -DestinationPath '%INSTALL_DIR%' -Force"

REM 记录回滚
set "ROLLBACK_RECORD=%INSTALL_DIR%\update_history.json"
echo {"action":"rollback","to":"%CURRENT_VERSION%","time":"%date% %time%"} >> "%ROLLBACK_RECORD%"

call :log "回滚完成"
goto :success

REM ============================================================================
REM 列出可用备份
REM ============================================================================
:list_available_backups
call :log "可用的备份版本:"

dir /b /o-d "%BACKUP_DIR%\*.zip" 2>nul
goto :eof

REM ============================================================================
REM 成功完成
REM ============================================================================
:success
call :log "========== 更新流程完成 =========="
echo.
echo ==============================================================
echo   更新完成！
echo ==============================================================
echo.
echo   新版本: %LATEST_VERSION%
echo   更新说明: %NOTES_FILE%
echo   博客文章: %BLOG_URL%
echo   论坛讨论: %FORUM_URL%
echo.
echo ==============================================================
goto :end

REM ============================================================================
REM 错误处理
REM ============================================================================
:error
call :log "========== 更新失败 =========="
echo.
echo ==============================================================
echo   更新失败！请查看日志: %LOG_FILE%
echo ==============================================================
echo.
echo   可能的问题:
echo   - 网络连接失败
echo   - 下载的更新包损坏
echo   - 签名验证失败
echo.
echo   解决方法:
echo   - 检查网络连接
echo   - 使用 /force 参数强制重新下载
echo   - 使用 /rollback 参数回滚到上一版本
echo ==============================================================

REM 发送错误通知
call :send_error_notification

goto :end

REM ============================================================================
REM 发送错误通知
REM ============================================================================
:send_error_notification
call :log "发送错误通知..."

set "ERROR_EMAIL={\"to\":\"devteam@mogoo.com\",\"subject\":\"Hermes Desktop 更新失败\",\"body\":\"版本 %CURRENT_VERSION% 更新失败，请检查日志\"}"
curl -X POST -H "Content-Type: application/json" -d "%ERROR_EMAIL%" "%EMAIL_API%" >nul 2>&1

goto :eof

REM ============================================================================
REM 结束
REM ============================================================================
:end
endlocal
pause