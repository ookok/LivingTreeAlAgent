#!/bin/bash
# =================================================================
# LivingTreeAI Relay Server - Linux 一键部署脚本
# =================================================================
# GitHub: https://github.com/your-repo/living-tree-ai
# =================================================================
# 用法:
#   ./deploy.sh              # 前台运行
#   ./deploy.sh install      # 安装 systemd 服务
#   ./deploy.sh uninstall    # 卸载 systemd 服务
#   ./deploy.sh restart      # 重启服务
#   ./deploy.sh stop         # 停止服务
#   ./deploy.sh status       # 查看服务状态
# =================================================================

set -e

# ========== 项目配置 ==========
GITHUB_REPO="https://github.com/your-repo/living-tree-ai"
APP_VERSION="2.0.0"

# ========== 配置 ==========
APP_NAME="livingtree-relay"
APP_USER="${APP_USER:-$(whoami)}"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-8766}"
HOST="${HOST:-0.0.0.0}"
VENV_DIR="${VENV_DIR:-.venv}"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
LOG_DIR="/var/log/${APP_NAME}"
DATA_DIR="${HOME}/.livingtree-ai/relay_server"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ========== 前置检查 ==========
check_requirements() {
    log_info "检查系统环境..."

    # 检查 Python
    if ! command -v $PYTHON_BIN &> /dev/null; then
        log_error "Python3 未安装，请先安装: sudo apt install python3 python3-venv"
        exit 1
    fi
    PYTHON_VERSION=$($PYTHON_BIN -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    log_info "Python 版本: $PYTHON_VERSION"

    # 检查 pip
    if ! $PYTHON_BIN -m pip --version &> /dev/null; then
        log_warn "pip 未安装，正在安装..."
        $PYTHON_BIN -m ensurepip --default-pip || true
    fi

    log_info "环境检查完成 ✓"
}

# ========== 虚拟环境 ==========
setup_venv() {
    log_info "配置虚拟环境..."

    if [ ! -d "$VENV_DIR" ]; then
        log_info "创建虚拟环境..."
        $PYTHON_BIN -m venv "$VENV_DIR"
    fi

    # 激活虚拟环境
    source "${VENV_DIR}/bin/activate"

    # 升级 pip
    pip install --upgrade pip -q

    # 安装依赖
    log_info "安装依赖..."
    pip install -r server/relay_server/requirements-server.txt -q

    log_info "虚拟环境配置完成 ✓"
}

# ========== 目录准备 ==========
prepare_dirs() {
    log_info "准备数据目录..."

    mkdir -p "${DATA_DIR}/raw"
    mkdir -p "${DATA_DIR}/agg"
    mkdir -p "${DATA_DIR}/web"
    mkdir -p "${DATA_DIR}/backup"
    mkdir -p "${LOG_DIR}"

    # 写入初始配置
    if [ ! -f "${DATA_DIR}/config.json" ]; then
        cat > "${DATA_DIR}/config.json" << EOF
{
    "server": {
        "host": "${HOST}",
        "port": ${PORT},
        "relay_enabled": true,
        "max_clients": 100
    },
    "relay": {
        "dispatch_params": true,
        "collect_stats": true,
        "offline_mode": false
    },
    "security": {
        "allow_external_clients": true,
        "rate_limit_per_minute": 60
    }
}
EOF
        log_info "配置文件已创建: ${DATA_DIR}/config.json"
    fi

    log_info "目录准备完成 ✓"
}

# ========== 服务管理 ==========
create_systemd_service() {
    log_info "创建 systemd 服务..."

    SERVICE_CONTENT="[Unit]
Description=Hermes Desktop Relay Server
After=network.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment=\"PATH=${APP_DIR}/${VENV_DIR}/bin\"
ExecStart=${APP_DIR}/${VENV_DIR}/bin/python -m uvicorn server.relay_server.main:app --host ${HOST} --port ${PORT}
Restart=always
RestartSec=10
StandardOutput=append:${LOG_DIR}/stdout.log
StandardError=append:${LOG_DIR}/stderr.log

[Install]
WantedBy=multi-user.target
"

    echo "${SERVICE_CONTENT}" | sudo tee "${SERVICE_FILE}" > /dev/null
    sudo systemctl daemon-reload

    log_info "systemd 服务已创建: ${SERVICE_FILE}"
    log_info "可用命令: sudo systemctl start ${APP_NAME}"
    log_info "           sudo systemctl enable ${APP_NAME}"
}

remove_systemd_service() {
    log_info "移除 systemd 服务..."

    if [ -f "${SERVICE_FILE}" ]; then
        sudo systemctl stop "${APP_NAME}" 2>/dev/null || true
        sudo systemctl disable "${APP_NAME}" 2>/dev/null || true
        sudo rm -f "${SERVICE_FILE}"
        sudo systemctl daemon-reload
        log_info "systemd 服务已移除"
    else
        log_warn "服务未安装"
    fi
}

start_service() {
    if [ -f "${SERVICE_FILE}" ]; then
        sudo systemctl start "${APP_NAME}"
        sudo systemctl status "${APP_NAME}" --no-pager
    else
        log_warn "服务未安装，使用前台模式启动..."
        start_foreground
    fi
}

stop_service() {
    if [ -f "${SERVICE_FILE}" ]; then
        sudo systemctl stop "${APP_NAME}"
        log_info "服务已停止"
    else
        log_warn "服务未安装"
    fi
}

restart_service() {
    if [ -f "${SERVICE_FILE}" ]; then
        sudo systemctl restart "${APP_NAME}"
        log_info "服务已重启"
    else
        log_warn "服务未安装"
    fi
}

show_status() {
    if [ -f "${SERVICE_FILE}" ]; then
        sudo systemctl status "${APP_NAME}" --no-pager
    else
        log_warn "服务未安装"
        log_info "前台运行方式: ./deploy.sh"
    fi
}

start_foreground() {
    source "${VENV_DIR}/bin/activate"
    cd "${APP_DIR}"
    python -m uvicorn server.relay_server.main:app --host "${HOST}" --port "${PORT}" --reload
}

# ========== Web 界面部署 ==========
deploy_web_interface() {
    log_info "部署 Web 管理界面..."

    source "${VENV_DIR}/bin/activate"

    # 生成 Web 界面
    python -c "
import sys
sys.path.insert(0, '.')
from server.relay_server.web_dashboard import save_dashboard
save_dashboard()
print('Web 界面已生成')
"

    log_info "Web 管理界面: http://localhost:${PORT}/web"
    log_info "API 端点: http://localhost:${PORT}/api"
}

# ========== 一键安装 ==========
install() {
    log_info "开始安装 Hermes Relay Server..."
    echo ""

    check_requirements
    setup_venv
    prepare_dirs
    deploy_web_interface
    create_systemd_service

    echo ""
    log_info "═══════════════════════════════════════════════"
    log_info "  安装完成！"
    log_info "═══════════════════════════════════════════════"
    log_info ""
    log_info "  启动服务:   sudo systemctl start ${APP_NAME}"
    log_info "  开机自启:   sudo systemctl enable ${APP_NAME}"
    log_info "  查看状态:   sudo systemctl status ${APP_NAME}"
    log_info "  查看日志:   tail -f ${LOG_DIR}/stdout.log"
    log_info "  Web 管理:   http://<服务器IP>:${PORT}/web"
    log_info ""
    log_info "  或直接前台运行: ./deploy.sh"
    log_info ""
}

# ========== 卸载 ==========
uninstall() {
    log_warn "即将卸载 Hermes Relay Server..."
    remove_systemd_service
    log_info "卸载完成（数据目录保留在 ${DATA_DIR}）"
}

# ========== 主入口 ==========
case "${1:-}" in
    install)
        install
        ;;
    uninstall|remove)
        uninstall
        ;;
    restart)
        restart_service
        ;;
    stop)
        stop_service
        ;;
    status)
        show_status
        ;;
    start)
        start_service
        ;;
    web)
        deploy_web_interface
        ;;
    "")
        check_requirements
        setup_venv
        prepare_dirs
        deploy_web_interface
        log_info ""
        log_info "═══════════════════════════════════════════════"
        log_info "  启动前台运行模式..."
        log_info "═══════════════════════════════════════════════"
        start_foreground
        ;;
    *)
        echo "用法: $0 {install|uninstall|start|stop|restart|status|web}"
        echo ""
        echo "  无参数     - 前台运行"
        echo "  install    - 安装 systemd 服务"
        echo "  uninstall  - 卸载服务"
        echo "  start      - 启动服务"
        echo "  stop       - 停止服务"
        echo "  restart    - 重启服务"
        echo "  status     - 查看状态"
        echo "  web        - 仅部署 Web 界面"
        exit 1
        ;;
esac
