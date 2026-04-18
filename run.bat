@echo off
REM LivingTreeAI - 生命之树 AI 桌面应用
REM 生命之树苏醒，根系伸向远方，林间交易的风已经开始流动
REM
REM 用法:
REM   run.bat              - 启动桌面客户端
REM   run.bat client       - 启动桌面客户端
REM   run.bat relay        - 启动中继服务器
REM   run.bat tracker      - 启动追踪服务器
REM   run.bat all          - 启动所有服务
REM   run.bat deploy-web   - 生成 Web 管理界面
REM   run.bat install      - 安装中继服务(Windows)
REM   run.bat uninstall    - 卸载中继服务(Windows)

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   LivingTreeAI                              ║
echo  ║   生命之树 · Living Tree AI                  ║
echo  ╚══════════════════════════════════════════════╝
echo.

if "%1"=="" goto client
if "%1"=="client" goto client
if "%1"=="relay" goto relay
if "%1"=="tracker" goto tracker
if "%1"=="all" goto all
if "%1"=="deploy-web" goto deploy_web
if "%1"=="install" goto install
if "%1"=="uninstall" goto uninstall

:client
echo 🚀 启动桌面客户端...
python main.py client
goto end

:relay
echo 🌐 启动中继服务器...
python -m uvicorn server.relay_server.main:app --host 0.0.0.0 --port 8766
goto end

:tracker
echo 📊 启动追踪服务器...
python server/tracker/tracker_server.py
goto end

:all
echo 🚀 启动所有服务...
start "LivingTreeAI Relay" python -m uvicorn server.relay_server.main:app --host 0.0.0.0 --port 8766
start "LivingTreeAI Tracker" python server/tracker/tracker_server.py
echo 🌐 服务已启动
timeout /t 2 /nobreak >nul
python main.py client
goto end

:deploy_web
echo 🌐 生成 Web 管理界面...
python -m server.relay_server.web_dashboard
goto end

:install
echo 📦 安装 LivingTreeAI Relay Windows 服务...
echo 需要管理员权限...
nssm install LivingTreeRelay "python" "-m uvicorn server.relay_server.main:app --host 0.0.0.0 --port 8766"
nssm set LivingTreeRelay AppDirectory "%CD%"
nssm set LivingTreeRelay DisplayName "LivingTreeAI Relay Server"
nssm set LivingTreeRelay Description "LivingTreeAI 中继服务器"
sc config LivingTreeRelay start= auto
echo ✅ 服务安装完成，可使用 sc start LivingTreeRelay 启动
goto end

:uninstall
echo 🗑️ 卸载 LivingTreeAI Relay Windows 服务...
sc stop LivingTreeRelay 2>nul
sc delete LivingTreeRelay 2>nul
echo ✅ 服务已卸载
goto end

:end
pause