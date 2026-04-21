#!/bin/bash
# ============================================================================
# Hermes Desktop 客户端安装脚本 (Linux/macOS)
# ============================================================================
#
# 功能:
#   1. 检测系统环境 (Linux/macOS)
#   2. 下载最新版本的 Hermes Desktop
#   3. 自动安装依赖
#   4. 配置零配置更新系统
#   5. 启动客户端
#
# 使用方法:
#   chmod +x install.sh
#   ./install.sh [版本号]
#
# 示例:
#   ./install.sh 1.2.0
#   ./install.sh latest
#
# ============================================================================

set -e

# ============================================================================
# 配置常量
# ============================================================================
APP_NAME="HermesDesktop"
INSTALL_DIR="$HOME/.hermes-desktop"
CONFIG_DIR="$HOME/.config/hermes-desktop"
CACHE_DIR="$HOME/.cache/hermes-desktop"

# 中继服务器地址 (零配置引导节点)
RELAY_SERVERS="https://relay1.mogoo.com,https://relay2.mogoo.com,https://relay3.mogoo.com"
BOOT_SERVERS="boot1.mogoo.com,boot2.mogoo.com,boot3.mogoo.com"

# 默认版本
TARGET_VERSION="${1:-latest}"

# 日志文件
LOG_FILE="$INSTALL_DIR/logs/install.log"

# ============================================================================
# 颜色定义
# ============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# 日志函数
# ============================================================================
log() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "${BLUE}[INFO]${NC} $1"
    echo "$message" >> "$LOG_FILE"
}

log_warn() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $1"
    echo -e "${YELLOW}[WARN]${NC} $1"
    echo "$message" >> "$LOG_FILE"
}

log_error() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1"
    echo -e "${RED}[ERROR]${NC} $1"
    echo "$message" >> "$LOG_FILE"
}

# ============================================================================
# 检测环境
# ============================================================================
detect_environment() {
    log "检测系统环境..."

    # 检测操作系统
    case "$(uname -s)" in
        Linux*)     SYSTEM_OS="Linux" ;;
        Darwin*)    SYSTEM_OS="macOS" ;;
        *)          SYSTEM_OS="Unknown" ;;
    esac

    # 检测架构
    case "$(uname -m)" in
        x86_64)     SYSTEM_ARCH="x64" ;;
        arm64)      SYSTEM_ARCH="arm64" ;;
        aarch64)    SYSTEM_ARCH="arm64" ;;
        *)          SYSTEM_ARCH="x64" ;;
    esac

    # 检测内存
    TOTAL_MEM=$(free -h 2>/dev/null | grep Mem | awk '{print $2}' || sysctl -n hw.memsize 2>/dev/null | awk '{print $1/1024/1024/1024 "GB"}')
    log "系统: $SYSTEM_OS $SYSTEM_ARCH"
    log "内存: $TOTAL_MEM"

    # 检测网络
    if ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
        NETWORK_STATUS="online"
        log "网络: $NETWORK_STATUS"
    else
        NETWORK_STATUS="offline"
        log_warn "网络不可用"
    fi
}

# ============================================================================
# 创建目录结构
# ============================================================================
create_directories() {
    log "创建目录结构..."

    mkdir -p "$INSTALL_DIR"/{logs,updates,data,keys}
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$CACHE_DIR"

    log "目录结构创建完成"
}

# ============================================================================
# 检查依赖
# ============================================================================
check_dependencies() {
    log "检查依赖..."

    # 检测 Python
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        log_error "未安装 Python，请先安装 Python 3.10+"
        exit 1
    fi

    PYTHON_VERSION=$($PYTHON_CMD --version)
    log "Python 版本: $PYTHON_VERSION"

    # 检查 PyQt6
    if ! $PYTHON_CMD -c "import PyQt6" 2>/dev/null; then
        log_warn "PyQt6 未安装，将自动安装..."
        PYQT6_MISSING=1
    else
        log "PyQt6 已安装"
    fi

    log "依赖检查完成"
}

# ============================================================================
# 下载客户端
# ============================================================================
download_client() {
    log "下载 Hermes Desktop $TARGET_VERSION..."

    # 尝试从 P2P 网络发现版本
    discover_version

    # 确定下载 URL
    if [ "$TARGET_VERSION" == "latest" ]; then
        UPDATE_FILE="$CACHE_DIR/hermes-desktop-latest-$SYSTEM_ARCH.tar.gz"
    else
        UPDATE_FILE="$CACHE_DIR/hermes-desktop-$TARGET_VERSION-$SYSTEM_ARCH.tar.gz"
    fi

    # 构建下载 URL
    local base_urls=(
        "https://releases.mogoo.com/hermes-desktop"
        "https://mirror.mogoo.com/hermes-desktop"
        "https://cdn.mogoo.com/hermes-desktop"
    )

    local download_url=""
    for base_url in "${base_urls[@]}"; do
        local test_url="$base_url/$TARGET_VERSION/hermes-desktop-$TARGET_VERSION-$SYSTEM_ARCH.tar.gz"
        if curl -s -o /dev/null -w "%{http_code}" "$test_url" | grep -q "200"; then
            download_url="$test_url"
            break
        fi
    done

    if [ -z "$download_url" ]; then
        log_error "无法找到可用的下载源"
        exit 1
    fi

    log "下载地址: $download_url"

    # 下载
    curl -L -o "$UPDATE_FILE" "$download_url"

    if [ ! -f "$UPDATE_FILE" ]; then
        log_error "下载失败"
        exit 1
    fi

    # 验证签名
    verify_signature

    # 解压
    log "解压安装包..."
    tar -xzf "$UPDATE_FILE" -C "$INSTALL_DIR"

    log "客户端下载完成"
}

# ============================================================================
# P2P 版本发现
# ============================================================================
discover_version() {
    log "从 P2P 网络发现最新版本..."

    # 尝试连接引导节点
    for boot_node in $BOOT_SERVERS; do
        if ping -c 1 -W 2 "$boot_node" >/dev/null 2>&1; then
            log "连接引导节点: $boot_node"

            # 获取版本信息
            discovered=$(
                curl -s "https://$boot_node/api/version/latest" 2>/dev/null | \
                grep -o '"version":"[^"]*"' | cut -d'"' -f4
            )

            if [ -n "$discovered" ]; then
                log "发现版本: $discovered"
                TARGET_VERSION="$discovered"
                return 0
            fi
        fi
    done

    log_warn "P2P 发现失败，使用默认版本"
    TARGET_VERSION="latest"
    return 1
}

# ============================================================================
# 验证签名
# ============================================================================
verify_signature() {
    log "验证更新包签名..."

    local sig_file="${UPDATE_FILE}.sig"
    local pub_key="$INSTALL_DIR/keys/hermes-desktop.pub"

    # 下载签名
    curl -s -o "$sig_file" "${download_url}.sig"

    # 下载公钥 (首次安装)
    if [ ! -f "$pub_key" ]; then
        curl -s -o "$pub_key" "https://keys.mogoo.com/hermes-desktop.pub"
    fi

    # 验证
    if command -v gpg &> /dev/null; then
        gpg --verify "$sig_file" "$UPDATE_FILE"
    elif command -v openssl &> /dev/null; then
        openssl dgst -sha256 -verify "$pub_key" -signature "$sig_file" "$UPDATE_FILE"
    else
        log_warn "无法验证签名，跳过"
    fi

    log "签名验证完成"
}

# ============================================================================
# 安装依赖
# ============================================================================
install_dependencies() {
    log "安装 Python 依赖..."

    # 升级 pip
    $PYTHON_CMD -m pip install --upgrade pip

    # 安装 PyQt6
    if [ -n "$PYQT6_MISSING" ]; then
        $PYTHON_CMD -m pip install PyQt6
    fi

    # 安装其他依赖
    $PYTHON_CMD -m pip install requests charset-normalizer

    # 安装本地依赖
    if [ -f "$INSTALL_DIR/requirements.txt" ]; then
        $PYTHON_CMD -m pip install -r "$INSTALL_DIR/requirements.txt"
    fi

    log "依赖安装完成"
}

# ============================================================================
# 配置零配置更新系统
# ============================================================================
configure_zero_update() {
    log "配置零配置更新系统..."

    # 创建零配置更新配置
    local zero_config="$CONFIG_DIR/zero_update.json"

    cat > "$zero_config" << 'EOF'
{
    "enabled": true,
    "auto_update": true,
    "update_channel": "stable",
    "check_interval_hours": 24,
    "relay_servers": [
        "https://relay1.mogoo.com",
        "https://relay2.mogoo.com"
    ],
    "boot_nodes": [
        "boot1.mogoo.com",
        "boot2.mogoo.com",
        "boot3.mogoo.com"
    ],
    "auto_discovery": true,
    "ai_optimized": true,
    "network_adaptive": true,
    "notification_style": "smart",
    "habit_learning": true
}
EOF

    # 创建首次运行标记
    local first_run="$INSTALL_DIR/first_run.flag"
    cat > "$first_run" << EOF
{
    "install_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "version": "$TARGET_VERSION",
    "auto_update_enabled": true
}
EOF

    log "零配置更新系统配置完成"
}

# ============================================================================
# 启动客户端
# ============================================================================
launch_client() {
    log "启动 Hermes Desktop..."

    local launcher="$INSTALL_DIR/HermesDesktop"
    if [ -f "$INSTALL_DIR/HermesDesktop.py" ]; then
        nohup $PYTHON_CMD "$INSTALL_DIR/HermesDesktop.py" > /dev/null 2>&1 &
    elif [ -f "$launcher" ]; then
        nohup "$launcher" > /dev/null 2>&1 &
    else
        log_error "未找到启动程序"
        exit 1
    fi

    log "客户端已启动"
}

# ============================================================================
# 主安装流程
# ============================================================================
main() {
    echo ""
    echo "=============================================================="
    echo "  Hermes Desktop 客户端安装程序"
    echo "  版本: $TARGET_VERSION"
    echo "=============================================================="
    echo ""

    create_directories
    detect_environment
    check_dependencies
    download_client
    install_dependencies
    configure_zero_update
    launch_client

    echo ""
    echo "=============================================================="
    echo "  安装完成！"
    echo "=============================================================="
    echo ""
    echo "  安装目录: $INSTALL_DIR"
    echo "  配置目录: $CONFIG_DIR"
    echo "  日志文件: $LOG_FILE"
    echo ""
    echo "  提示: 客户端已启动，系统将自动检查更新"
    echo "=============================================================="
    echo ""
}

# ============================================================================
# 错误处理
# ============================================================================
error() {
    echo ""
    echo "=============================================================="
    echo -e "${RED}  安装失败！请查看日志: $LOG_FILE${NC}"
    echo "=============================================================="
    echo ""
    exit 1
}

trap error ERR

main "$@"