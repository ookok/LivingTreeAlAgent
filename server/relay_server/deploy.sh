#!/bin/bash
# =================================================================
# Hermes Desktop Relay Server 一键部署脚本
# =================================================================
# 功能：
#   - 自动安装 Docker 和 Docker Compose
#   - 拉取/构建 Hermes Relay Server 镜像
#   - 配置 HTTPS (Let's Encrypt)
#   - 启动所有服务 (信令/TURN/API网关)
#
# 使用方法：
#   curl -sSL https://your-domain.com/deploy.sh | bash -s -- \
#     --domain your-server.com \
#     --email your@email.com
#
# 作者: Hermes Desktop AI Assistant
# =================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# 默认配置
DOMAIN=""
EMAIL=""
RELAY_PORT=8081
TURN_PORT=8082
API_PORT=8080
HTTPS_PORT=8443

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --email)
            EMAIL="$2"
            shift 2
            ;;
        --relay-port)
            RELAY_PORT="$2"
            shift 2
            ;;
        --turn-port)
            TURN_PORT="$2"
            shift 2
            ;;
        --api-port)
            API_PORT="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            ;;
    esac
done

# 检查必填参数
if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 --domain your-server.com --email your@email.com"
    echo ""
    echo "Options:"
    echo "  --domain DOMAIN        你的服务器域名 (必填)"
    echo "  --email EMAIL          你的邮箱，用于 Let's Encrypt (必填)"
    echo "  --relay-port PORT      P2P信令端口，默认8081"
    echo "  --turn-port PORT       TURN中继端口，默认8082"
    echo "  --api-port PORT        API网关端口，默认8080"
    exit 1
fi

if [ -z "$EMAIL" ]; then
    echo "Usage: $0 --domain your-server.com --email your@email.com"
    exit 1
fi

log_info "开始部署 Hermes Relay Server..."
log_info "域名: $DOMAIN"
log_info "邮箱: $EMAIL"

# =================================================================
# 1. 检查系统环境
# =================================================================
log_info "检查系统环境..."

# 检查是否为root
if [ "$EUID" -ne 0 ]; then
    log_warning "建议使用 root 权限运行此脚本"
fi

# 检查操作系统
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    log_error "无法检测操作系统"
fi

log_success "操作系统: $OS"

# =================================================================
# 2. 安装 Docker (如果未安装)
# =================================================================
log_info "检查 Docker..."

if ! command -v docker &> /dev/null; then
    log_info "安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    log_success "Docker 安装完成"
else
    log_success "Docker 已安装: $(docker --version)"
fi

# 检查 Docker Compose
if ! command -v docker-compose &> /dev/null; then
    log_info "安装 Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    log_success "Docker Compose 安装完成"
else
    log_success "Docker Compose 已安装: $(docker-compose --version)"
fi

# =================================================================
# 3. 创建部署目录
# =================================================================
DEPLOY_DIR="/opt/hermes-relay"
log_info "创建部署目录: $DEPLOY_DIR"
mkdir -p $DEPLOY_DIR
cd $DEPLOY_DIR

# =================================================================
# 4. 创建 docker-compose.yml
# =================================================================
log_info "创建 docker-compose.yml..."
cat > $DEPLOY_DIR/docker-compose.yml << EOF
version: '3.8'

services:
  # P2P 信令服务器
  relay-server:
    image: hermesdesktop/relay-server:latest
    container_name: hermes-relay
    restart: unless-stopped
    ports:
      - "${RELAY_PORT}:8081"
      - "${TURN_PORT}:8082"
      - "${API_PORT}:8080"
    environment:
      - DOMAIN=${DOMAIN}
      - RELAY_PORT=${RELAY_PORT}
      - TURN_PORT=${TURN_PORT}
      - API_PORT=${API_PORT}
      - TZ=Asia/Shanghai
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    networks:
      - hermes-net

  # Nginx 反向代理 + HTTPS
  nginx:
    image: nginx:alpine
    container_name: hermes-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./data/certbot/conf:/etc/letsencrypt:ro
      - ./data/certbot/www:/var/www/certbot:ro
    depends_on:
      - relay-server
    networks:
      - hermes-net

  # Certbot (HTTPS证书)
  certbot:
    image: certbot/certbot
    container_name: hermes-certbot
    restart: unless-stopped
    volumes:
      - ./data/certbot/conf:/etc/letsencrypt:rw
      - ./data/certbot/www:/var/www/certbot:rw
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do sleep 6h && certbot renew; done'"

networks:
  hermes-net:
    driver: bridge
EOF

# 导出环境变量
export DOMAIN EMAIL RELAY_PORT TURN_PORT API_PORT

# =================================================================
# 5. 创建 Nginx 配置
# =================================================================
log_info "创建 Nginx 配置..."
mkdir -p $DEPLOY_DIR/nginx/ssl
mkdir -p $DEPLOY_DIR/data/certbot/conf
mkdir -p $DEPLOY_DIR/data/certbot/www

cat > $DEPLOY_DIR/nginx/nginx.conf << EOF
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # 日志格式
    log_format main '\$remote_addr - \$remote_user [\$time_local] "\$request" '
                    '\$status \$body_bytes_sent "\$http_referer" '
                    '"\$http_user_agent" "\$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log warn;

    # Gzip 压缩
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss;

    # 上传大小限制
    client_max_body_size 100M;

    # 代理设置
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;

    # P2P 信令服务
    server {
        listen 80;
        server_name $DOMAIN;

        # Let's Encrypt 验证
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 301 https://\$host\$request_uri;
        }
    }

    server {
        listen 443 ssl http2;
        server_name $DOMAIN;

        # SSL 证书
        ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

        # SSL 配置
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
        ssl_prefer_server_ciphers off;

        # P2P 信令 WebSocket
        location /ws {
            proxy_pass http://relay-server:8081;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_read_timeout 86400;
        }

        # TURN STUN
        location /stun {
            proxy_pass http://relay-server:8082;
            proxy_read_timeout 86400;
        }

        # TURN TURN (TCP)
        location /turn {
            proxy_pass http://relay-server:8082;
            proxy_read_timeout 86400;
        }

        # API 网关
        location /api/ {
            proxy_pass http://relay-server:8080/;
        }

        # 健康检查
        location /health {
            proxy_pass http://relay-server:8080/health;
            access_log off;
        }

        # 静态文件
        location / {
            root /usr/share/nginx/html;
            index index.html;
        }
    }
}
EOF

# =================================================================
# 6. 获取 SSL 证书
# =================================================================
log_info "获取 SSL 证书..."

# 创建 certbot 验证目录
mkdir -p $DEPLOY_DIR/data/certbot/www/.well-known/acme-challenge

# 临时启动 nginx 获取证书
docker run -d --name temp-nginx \
    -p 80:80 \
    -v $DEPLOY_DIR/data/certbot/www:/var/www/certbot \
    nginx:alpine

sleep 2

# 请求证书
certbot certonly --webroot \
    --webroot-path /var/www/certbot \
    --register-unsafely-without-email \
    --agree-tos \
    --domain $DOMAIN \
    --force-renewal || true

# 停止临时 nginx
docker stop temp-nginx || true
docker rm temp-nginx || true

# 检查证书是否生成
if [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    log_success "SSL 证书获取成功"
    # 复制证书到部署目录
    mkdir -p $DEPLOY_DIR/data/certbot/conf
    cp -r /etc/letsencrypt/live/$DOMAIN $DEPLOY_DIR/data/certbot/conf/
else
    log_warning "SSL 证书获取失败，将使用自签名证书"
    # 生成自签名证书
    openssl req -x509 -nodes -newkey rsa:2048 \
        -keyout $DEPLOY_DIR/nginx/ssl/selfsigned.key \
        -out $DEPLOY_DIR/nginx/ssl/selfsigned.crt \
        -days 365 \
        -subj "/CN=$DOMAIN"
fi

# =================================================================
# 7. 拉取并启动服务
# =================================================================
log_info "拉取 Hermes Relay Server 镜像..."
docker pull hermesdesktop/relay-server:latest || true

log_info "启动服务..."
cd $DEPLOY_DIR
docker-compose up -d

# =================================================================
# 8. 验证部署
# =================================================================
sleep 5

log_info "验证部署状态..."

# 检查容器状态
docker ps | grep hermes

# 健康检查
if curl -sf http://localhost:${API_PORT}/health > /dev/null; then
    log_success "服务健康检查通过"
else
    log_warning "健康检查未通过，请检查日志: docker-compose logs"
fi

# =================================================================
# 9. 显示部署信息
# =================================================================
echo ""
echo "=============================================="
echo "   Hermes Relay Server 部署完成!"
echo "=============================================="
echo ""
echo "服务地址:"
echo "  - P2P 信令: wss://$DOMAIN/ws"
echo "  - TURN STUN: stun://$DOMAIN:3478"
echo "  - API 网关: https://$DOMAIN/api/"
echo "  - 健康检查: https://$DOMAIN/health"
echo ""
echo "端口配置:"
echo "  - Relay Port: $RELAY_PORT"
echo "  - TURN Port: $TURN_PORT"
echo "  - API Port: $API_PORT"
echo ""
echo "管理命令:"
echo "  - 查看日志: docker-compose logs -f"
echo "  - 重启服务: docker-compose restart"
echo "  - 停止服务: docker-compose down"
echo "  - 更新服务: docker-compose pull && docker-compose up -d"
echo ""
echo "配置文件位置: $DEPLOY_DIR"
echo "=============================================="
echo ""

log_success "部署完成!"
log_info "请在 Hermes Desktop 客户端中配置此服务器地址"