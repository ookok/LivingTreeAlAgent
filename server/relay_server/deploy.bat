@echo off
REM =================================================================
REM Hermes Desktop Relay Server 部署脚本 (Windows)
REM =================================================================
REM 功能：
REM   - 自动安装 Docker Desktop
REM   - 拉取 Hermes Relay Server 镜像
REM   - 配置并启动所有服务
REM
REM 使用方法：
REM   deploy.bat your-server.com your@email.com
REM
REM 作者: Hermes Desktop AI Assistant
REM =================================================================

setlocal enabledelayedexpansion

set DOMAIN=%1
set EMAIL=%2
set RELAY_PORT=8081
set TURN_PORT=8082
set API_PORT=8080

echo ==================================================================
echo    Hermes Desktop Relay Server 部署脚本
echo ==================================================================
echo.

REM 检查参数
if "%DOMAIN%"=="" (
    echo 用法: deploy.bat domain email
    echo 示例: deploy.bat relay.example.com admin@example.com
    exit /b 1
)

if "%EMAIL%"=="" (
    echo 用法: deploy.bat domain email
    echo 示例: deploy.bat relay@example.com admin@example.com
    exit /b 1
)

echo [INFO] 开始部署 Hermes Relay Server...
echo [INFO] 域名: %DOMAIN%
echo [INFO] 邮箱: %EMAIL%
echo.

REM =================================================================
REM 1. 检查 Docker
REM =================================================================
echo [INFO] 检查 Docker...

where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Docker 未安装，正在安装...
    echo [INFO] 请下载并安装 Docker Desktop: https://docker.com/products/docker-desktop
    echo [INFO] 安装完成后，请重新运行此脚本
    exit /b 1
)

docker --version
echo [SUCCESS] Docker 已安装

REM =================================================================
REM 2. 检查 Docker 运行状态
REM =================================================================
echo.
echo [INFO] 检查 Docker 服务状态...

docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker 服务未运行
    echo [INFO] 请启动 Docker Desktop 并等待其完全启动
    echo [INFO] 然后重新运行此脚本
    exit /b 1
)

echo [SUCCESS] Docker 服务运行正常

REM =================================================================
REM 3. 创建部署目录
REM =================================================================
echo.
set DEPLOY_DIR=C:\hermes-relay
echo [INFO] 创建部署目录: %DEPLOY_DIR%

if not exist "%DEPLOY_DIR%" mkdir "%DEPLOY_DIR%"
cd /d %DEPLOY_DIR%

REM =================================================================
REM 4. 创建 docker-compose.yml
REM =================================================================
echo [INFO] 创建 docker-compose.yml...

(
echo version: '3.8'
echo.
echo services:
echo   relay-server:
echo     image: hermesdesktop/relay-server:latest
echo     container_name: hermes-relay
echo     restart: unless-stopped
echo     ports:
echo       - "%RELAY_PORT%:8081"
echo       - "%TURN_PORT%:8082"
echo       - "%API_PORT%:8080"
echo     environment:
echo       - DOMAIN=%DOMAIN%
echo       - RELAY_PORT=%RELAY_PORT%
echo       - TURN_PORT=%TURN_PORT%
echo       - API_PORT=%API_PORT%
echo       - TZ=Asia^/Shanghai
echo     volumes:
echo       - ./data:/app/data
echo       - ./logs:/app/logs
) > docker-compose.yml

REM =================================================================
REM 5. 创建 Nginx 配置
REM =================================================================
echo [INFO] 创建 Nginx 配置...

mkdir "%DEPLOY_DIR%\nginx" 2>nul
mkdir "%DEPLOY_DIR%\data" 2>nul
mkdir "%DEPLOY_DIR%\logs" 2>nul

(
echo events ^(^) ^(^)
echo     worker_connections 1024;
echo ^(^}
echo.
echo http ^(^>
echo     include /etc/nginx/mime.types;
echo     default_type application/octet-stream;
echo.
echo     log_format main '$remote_addr - $remote_user [$time_local] "$request" '
echo                     '$status $body_bytes_sent "$http_referer" '
echo                     '"$http_user_agent" "$http_x_forwarded_for"';
echo.
echo     access_log /var/log/nginx/access.log main;
echo     error_log /var/log/nginx/error.log warn;
echo.
echo     gzip on;
echo     gzip_vary on;
echo     gzip_min_length 1024;
echo.
echo     client_max_body_size 100M;
echo.
echo     proxy_set_header Host $host;
echo     proxy_set_header X-Real-IP $remote_addr;
echo     proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
echo     proxy_set_header X-Forwarded-Proto $scheme;
echo.
echo     server ^(^>
echo         listen 80;
echo         server_name %DOMAIN%;
echo.
echo         location /.well-known/acme-challenge/ ^(^>
echo             root /var/www/certbot;
echo         ^(^}
echo.
echo         location / ^(^>
echo             return 301 https://$host$request_uri;
echo         ^(^}
echo     ^(^}
echo.
echo     server ^(^>
echo         listen 443 ssl http2;
echo         server_name %DOMAIN%;
echo.
echo         # 自签名证书（生产环境请使用 Let's Encrypt^)
echo         ssl_certificate /etc/nginx/ssl/selfsigned.crt;
echo         ssl_certificate_key /etc/nginx/ssl/selfsigned.key;
echo.
echo         ssl_protocols TLSv1.2 TLSv1.3;
echo         ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
echo.
echo         location /ws ^(^>
echo             proxy_pass http://relay-server:8081;
echo             proxy_http_version 1.1;
echo             proxy_set_header Upgrade $http_upgrade;
echo             proxy_set_header Connection "upgrade";
echo             proxy_read_timeout 86400;
echo         ^(^}
echo.
echo         location /stun ^(^>
echo             proxy_pass http://relay-server:8082;
echo         ^(^}
echo.
echo         location /turn ^(^>
echo             proxy_pass http://relay-server:8082;
echo         ^(^}
echo.
echo         location /api/ ^(^>
echo             proxy_pass http://relay-server:8080/;
echo         ^(^}
echo.
echo         location /health ^(^>
echo             proxy_pass http://relay-server:8080/health;
echo         ^(^}
echo     ^(^>
echo ^(^}
) > nginx/nginx.conf

REM =================================================================
REM 6. 生成自签名证书（生产环境请使用 Let's Encrypt）
REM =================================================================
echo [INFO] 生成 SSL 证书...

openssl req -x509 -nodes -newkey rsa:2048 ^
    -keyout nginx/ssl/selfsigned.key ^
    -out nginx/ssl/selfsigned.crt ^
    -days 365 ^
    -subj "/CN=%DOMAIN%" 2>nul

if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] SSL 证书生成成功
) else (
    echo [WARNING] SSL 证书生成失败，将使用 HTTP
)

REM =================================================================
REM 7. 拉取并启动服务
REM =================================================================
echo.
echo [INFO] 拉取 Hermes Relay Server 镜像...
docker pull hermesdesktop/relay-server:latest

echo [INFO] 启动服务...
docker-compose up -d

REM =================================================================
REM 8. 验证部署
REM =================================================================
echo.
echo [INFO] 验证部署状态...
timeout /t 5 /nobreak >nul

docker ps | findstr hermes

REM 健康检查
curl -sf http://localhost:%API_PORT%/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] 服务健康检查通过
) else (
    echo [WARNING] 健康检查未通过，请检查日志: docker-compose logs
)

REM =================================================================
REM 9. 显示部署信息
REM =================================================================
echo.
echo ==================================================================
echo    Hermes Relay Server 部署完成!
echo ==================================================================
echo.
echo 服务地址:
echo   - P2P 信令: ws://%DOMAIN%:%RELAY_PORT%/ws
echo   - TURN STUN: stun://%DOMAIN%:%TURN_PORT%
echo   - API 网关: http://%DOMAIN%:%API_PORT%/api/
echo   - 健康检查: http://%DOMAIN%:%API_PORT%/health
echo.
echo 端口配置:
echo   - Relay Port: %RELAY_PORT%
echo   - TURN Port: %TURN_PORT%
echo   - API Port: %API_PORT%
echo.
echo 管理命令:
echo   - 查看日志: docker-compose logs -f
echo   - 重启服务: docker-compose restart
echo   - 停止服务: docker-compose down
echo   - 更新服务: docker-compose pull ^&^& docker-compose up -d
echo.
echo 配置文件位置: %DEPLOY_DIR%
echo ==================================================================
echo.
echo [SUCCESS] 部署完成!
echo [INFO] 请在 Hermes Desktop 客户端中配置此服务器地址

endlocal