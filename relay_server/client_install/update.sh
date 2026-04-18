#!/bin/bash
# ============================================================================
# Hermes Desktop 客户端自动更新脚本 (Linux/macOS)
# ============================================================================
#
# 功能:
#   1. 后台检查更新
#   2. 智能下载 (P2P + 镜像)
#   3. 渐进式更新通知
#   4. 一键应用更新
#   5. 自动生成更新说明
#   6. 同步到博客和论坛
#
# 使用方法:
#   ./update.sh [选项]
#
#   选项:
#     --silent    - 静默模式，后台更新
#     --check     - 仅检查更新，不下载
#     --force     - 强制更新，即使已最新
#     --rollback  - 回滚到上一个版本
#
# 示例:
#   ./update.sh --silent
#   ./update.sh --check
#   ./update.sh --force
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
UPDATE_DIR="$INSTALL_DIR/updates"
LOG_FILE="$INSTALL_DIR/logs/update.log"

CURRENT_VERSION="unknown"
LATEST_VERSION="unknown"
UPDATE_MODE="silent"
FORCE_UPDATE=0

# 中继服务器
RELAY_SERVERS="https://relay1.mogoo.com,https://relay2.mogoo.com"
UPDATE_API="/api/v1/update"

# ============================================================================
# 颜色定义
# ============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

log_success() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] [SUCCESS] $1"
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    echo "$message" >> "$LOG_FILE"
}

# ============================================================================
# 解析命令行参数
# ============================================================================
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --silent)
                UPDATE_MODE="silent"
                shift
                ;;
            --check)
                UPDATE_MODE="check"
                shift
                ;;
            --force)
                FORCE_UPDATE=1
                UPDATE_MODE="silent"
                shift
                ;;
            --rollback)
                UPDATE_MODE="rollback"
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
}

# ============================================================================
# 主流程
# ============================================================================
main() {
    echo ""
    echo "=============================================================="
    echo "  Hermes Desktop 自动更新程序"
    echo "=============================================================="
    echo ""

    log "========== 开始更新流程 =========="
    log "更新模式: $UPDATE_MODE"

    # 创建目录
    create_directories

    # 读取当前版本
    read_current_version

    # 解析模式
    case $UPDATE_MODE in
        check)
            check_only
            ;;
        rollback)
            rollback_version
            ;;
        *)
            # 静默更新流程
            check_for_updates

            if [ "$HAS_UPDATE" != "1" ]; then
                log "已是最新版本: $CURRENT_VERSION"
                show_success
            else
                decide_update_strategy
                download_update
                apply_update
                generate_update_notes
                sync_to_blog_forum
                show_success
            fi
            ;;
    esac
}

# ============================================================================
# 创建目录
# ============================================================================
create_directories() {
    mkdir -p "$INSTALL_DIR"/{logs,updates,data,keys,backups}
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$CACHE_DIR"
}

# ============================================================================
# 读取当前版本
# ============================================================================
read_current_version() {
    log "读取当前版本信息..."

    local version_file="$INSTALL_DIR/version.ini"
    local config_file="$CONFIG_DIR/config.json"

    if [ -f "$version_file" ]; then
        CURRENT_VERSION=$(grep "version" "$version_file" | cut -d'=' -f2)
    elif [ -f "$config_file" ]; then
        CURRENT_VERSION=$(python3 -c "import json; print(json.load(open('$config_file'))['version'])" 2>/dev/null || echo "unknown")
    else
        CURRENT_VERSION="unknown"
    fi

    log "当前版本: $CURRENT_VERSION"
}

# ============================================================================
# 仅检查更新
# ============================================================================
check_only() {
    check_for_updates

    if [ "$HAS_UPDATE" == "1" ]; then
        echo ""
        echo "发现新版本: $LATEST_VERSION"
        echo "当前版本: $CURRENT_VERSION"
        echo "更新大小: $UPDATE_SIZE"
        echo ""
        echo "查看详情请访问: https://blog.mogoo.com/hermes-update"
    else
        echo ""
        echo "已是最新版本: $CURRENT_VERSION"
    fi
}

# ============================================================================
# 检查更新
# ============================================================================
check_for_updates() {
    log "检查更新..."

    # P2P 网络发现
    discover_latest_version_p2p

    if [ "$LATEST_VERSION" == "unknown" ]; then
        # 中心服务器查询
        query_center_server
    fi

    # 比较版本
    compare_versions
}

# ============================================================================
# P2P 网络发现最新版本
# ============================================================================
discover_latest_version_p2p() {
    log "P2P 网络发现最新版本..."

    for server in ${RELAY_SERVERS//,/ }; do
        if curl -s --connect-timeout 5 "$server$UPDATE_API/check?version=$CURRENT_VERSION" > temp_update.json 2>/dev/null; then
            LATEST_VERSION=$(grep -o '"latest_version":"[^"]*"' temp_update.json | cut -d'"' -f4)
            if [ -n "$LATEST_VERSION" ]; then
                log "P2P 发现版本: $LATEST_VERSION"
                rm -f temp_update.json
                return 0
            fi
        fi
    done

    LATEST_VERSION="unknown"
    return 1
}

# ============================================================================
# 查询中心服务器
# ============================================================================
query_center_server() {
    log "查询中心服务器..."

    local mirrors=(
        "https://releases.mogoo.com"
        "https://mirror.mogoo.com"
        "https://cdn.mogoo.com"
    )

    for mirror in "${mirrors[@]}"; do
        if version=$(curl -s --connect-timeout 5 "$mirror/api/version/latest" 2>/dev/null); then
            LATEST_VERSION=$(echo "$version" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
            if [ -n "$LATEST_VERSION" ]; then
                log "中心服务器发现版本: $LATEST_VERSION"
                return 0
            fi
        fi
    done

    LATEST_VERSION="unknown"
    return 1
}

# ============================================================================
# 比较版本
# ============================================================================
compare_versions() {
    log "比较版本: $CURRENT_VERSION vs $LATEST_VERSION..."

    if [ "$LATEST_VERSION" == "$CURRENT_VERSION" ] || [ "$LATEST_VERSION" == "unknown" ]; then
        HAS_UPDATE=0
        log "已是最新"
    else
        HAS_UPDATE=1
        log "发现新版本: $LATEST_VERSION"

        # 获取更新大小
        UPDATE_SIZE=$(curl -s "https://releases.mogoo.com/api/update/size?from=$CURRENT_VERSION&to=$LATEST_VERSION" 2>/dev/null || echo "未知")
    fi
}

# ============================================================================
# AI 决策更新策略
# ============================================================================
decide_update_strategy() {
    log "AI 决策更新策略..."

    # 分析网络环境
    analyze_network_environment

    # 分析时间段
    analyze_time_period

    # 分析用户习惯
    analyze_user_habits

    # 决定策略
    if [ "$USER_PREF_IMMEDIATE" == "1" ]; then
        STRATEGY="notify_and_apply"
        log "策略: 立即提示并应用 (用户偏好)"
    elif [ "$IS_WORKING_HOURS" == "1" ]; then
        STRATEGY="background_silent"
        log "策略: 工作时段静默"
    elif [ "$IS_MOBILE_NETWORK" == "1" ]; then
        STRATEGY="small_file_only"
        log "策略: 仅小文件 (移动网络)"
    else
        STRATEGY="smart_delayed"
        log "策略: 智能延迟更新"
    fi
}

# ============================================================================
# 分析网络环境
# ============================================================================
analyze_network_environment() {
    log "分析网络环境..."

    # 检测是否在中国大陆
    if ping -c 1 -W 2 cn.mogoo.com >/dev/null 2>&1; then
        IS_CHINA=1
        USE_MIRROR=1
        log "检测到中国大陆网络，使用镜像优先"
    else
        IS_CHINA=0
        USE_MIRROR=0
    fi

    # 检测网络质量
    if ping -c 3 -W 2 8.8.8.8 >/dev/null 2>&1; then
        NETWORK_QUALITY="good"
    else
        NETWORK_QUALITY="poor"
    fi
}

# ============================================================================
# 分析时间段
# ============================================================================
analyze_time_period() {
    log "分析时间段..."

    CURRENT_HOUR=$(date +%H)

    # 判断工作时间 (9:00-18:00)
    if [ "$CURRENT_HOUR" -ge 9 ] && [ "$CURRENT_HOUR" -lt 18 ]; then
        IS_WORKING_HOURS=1
    else
        IS_WORKING_HOURS=0
    fi

    log "当前小时: $CURRENT_HOUR, 工作时间: $IS_WORKING_HOURS"
}

# ============================================================================
# 分析用户习惯
# ============================================================================
analyze_user_habits() {
    log "分析用户习惯..."

    local prefs_file="$CONFIG_DIR/user_prefs.json"

    if [ -f "$prefs_file" ]; then
        if grep -q "immediate_update" "$prefs_file" 2>/dev/null; then
            USER_PREF_IMMEDIATE=1
        else
            USER_PREF_IMMEDIATE=0
        fi
    else
        USER_PREF_IMMEDIATE=0
    fi

    # 记录更新尝试
    local attempts_file="$INSTALL_DIR/update_attempts.txt"
    if [ -f "$attempts_file" ]; then
        UPDATE_ATTEMPTS=$(cat "$attempts_file")
        UPDATE_ATTEMPTS=$((UPDATE_ATTEMPTS + 1))
    else
        UPDATE_ATTEMPTS=1
    fi
    echo "$UPDATE_ATTEMPTS" > "$attempts_file"
}

# ============================================================================
# 下载更新
# ============================================================================
download_update() {
    log "下载更新包..."

    local update_file="$UPDATE_DIR/hermes-desktop-$LATEST_VERSION.tar.gz"
    local update_sig="$update_file.sig"

    # 多源下载 (P2P + 镜像)
    if ! download_from_p2p "$update_file"; then
        log "P2P 下载失败，尝试镜像..."
        download_from_mirror "$update_file"
    fi

    # 验证签名
    verify_update_signature "$update_file"

    # 记录下载信息
    record_download_info

    log "下载完成: $update_file"
}

# ============================================================================
# P2P 下载
# ============================================================================
download_from_p2p() {
    local update_file="$1"
    log "从 P2P 网络下载..."

    local p2p_url="https://relay1.mogoo.com$UPDATE_API/download/$LATEST_VERSION"

    if curl -L -o "$update_file" "$p2p_url" --connect-timeout 30 --max-time 3600; then
        return 0
    fi

    return 1
}

# ============================================================================
# 镜像下载
# ============================================================================
download_from_mirror() {
    local update_file="$1"
    log "从镜像下载..."

    local mirrors=(
        "https://mirror.mogoo.com/hermes-desktop"
        "https://cdn.mogoo.com/hermes-desktop"
        "https://releases.mogoo.com/hermes-desktop"
    )

    for mirror in "${mirrors[@]}"; do
        local mirror_url="$mirror/$LATEST_VERSION/hermes-desktop-$LATEST_VERSION-$(uname -m).tar.gz"
        log "尝试镜像: $mirror_url"

        if curl -L -o "$update_file" "$mirror_url" --connect-timeout 30 --max-time 3600; then
            return 0
        fi
    done

    return 1
}

# ============================================================================
# 验证更新签名
# ============================================================================
verify_update_signature() {
    local update_file="$1"
    log "验证更新签名..."

    local pub_key="$INSTALL_DIR/keys/hermes-desktop.pub"
    local sig_file="$update_file.sig"

    # 下载签名
    curl -s -o "$sig_file" "${p2p_url}.sig" 2>/dev/null

    # 下载公钥 (首次安装)
    if [ ! -f "$pub_key" ]; then
        curl -s -o "$pub_key" "https://keys.mogoo.com/hermes-desktop.pub"
    fi

    # 验证
    if command -v gpg &> /dev/null; then
        gpg --verify "$sig_file" "$update_file"
    elif command -v openssl &> /dev/null; then
        openssl dgst -sha256 -verify "$pub_key" -signature "$sig_file" "$update_file"
    else
        log_warn "无法验证签名"
    fi
}

# ============================================================================
# 记录下载信息
# ============================================================================
record_download_info() {
    local download_info="$UPDATE_DIR/download_info.json"

    cat > "$download_info" << EOF
{
    "version": "$LATEST_VERSION",
    "download_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "source": "p2p",
    "file_size": "$UPDATE_SIZE",
    "status": "downloaded"
}
EOF
}

# ============================================================================
# 应用更新
# ============================================================================
apply_update() {
    log "应用更新..."

    # 备份当前版本
    backup_current_version

    # 解压更新包
    log "解压更新包..."
    tar -xzf "$UPDATE_DIR/hermes-desktop-$LATEST_VERSION.tar.gz" -C "$INSTALL_DIR"

    # 更新版本文件
    local version_file="$INSTALL_DIR/version.ini"
    cat > "$version_file" << EOF
[Info]
version=$LATEST_VERSION
update_time=$(date)
EOF

    # 记录更新历史
    record_update_history

    # 发送内部通知
    send_internal_notification

    log "更新应用完成"
}

# ============================================================================
# 备份当前版本
# ============================================================================
backup_current_version() {
    log "备份当前版本..."

    local backup_dir="$INSTALL_DIR/backups"
    local backup_file="$backup_dir/hermes-desktop-backup-$CURRENT_VERSION.tar.gz"

    # 备份核心文件
    tar -czf "$backup_file" -C "$INSTALL_DIR" HermesDesktop.py *.py 2>/dev/null || true

    # 清理旧备份 (保留最近 3 个)
    cd "$backup_dir"
    ls -t *.tar.gz 2>/dev/null | tail -n +4 | xargs rm -f 2>/dev/null || true

    log "备份完成: $backup_file"
}

# ============================================================================
# 记录更新历史
# ============================================================================
record_update_history() {
    local history_file="$INSTALL_DIR/update_history.json"

    local new_record="{\"version\":\"$LATEST_VERSION\",\"time\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"from\":\"$CURRENT_VERSION\"}"

    if [ -f "$history_file" ]; then
        # 追加到现有历史
        local temp_file=$(mktemp)
        echo "[$new_record,$(cat "$history_file")]" > "$temp_file"
        mv "$temp_file" "$history_file"
    else
        echo "[$new_record]" > "$history_file"
    fi
}

# ============================================================================
# 发送内部通知邮件
# ============================================================================
send_internal_notification() {
    log "发送内部通知..."

    local email_api="https://internal.mogoo.com/api/notify"
    local email_content="{\"to\":\"devteam@mogoo.com\",\"subject\":\"Hermes Desktop 更新通知\",\"body\":\"版本: $CURRENT_VERSION -> $LATEST_VERSION\"}"

    curl -X POST -H "Content-Type: application/json" -d "$email_content" "$email_api" >/dev/null 2>&1 || true

    log "内部通知已发送"
}

# ============================================================================
# 生成更新说明
# ============================================================================
generate_update_notes() {
    log "生成更新说明..."

    local notes_file="$UPDATE_DIR/CHANGELOG-$LATEST_VERSION.md"

    # 从服务器获取更新内容
    curl -s "https://releases.mogoo.com/api/changelog/$LATEST_VERSION" > temp_changelog.json 2>/dev/null || echo "{}" > temp_changelog.json

    # 生成 Markdown 格式的更新说明
    cat > "$notes_file" << EOF
# Hermes Desktop v$LATEST_VERSION 更新说明

## 更新信息

| 项目 | 内容 |
| ---- | ---- |
| 当前版本 | $CURRENT_VERSION |
| 新版本 | $LATEST_VERSION |
| 更新大小 | $UPDATE_SIZE |
| 发布时间 | $(date) |
| 来源区域 | 自动检测 |

## 更新内容

$(cat temp_changelog.json)

## 内部备注

- 内部邮箱: devteam@mogoo.com
- 更新来源: P2P网络自动发现
- 同步时间: $(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

    rm -f temp_changelog.json

    log "更新说明已生成: $notes_file"
}

# ============================================================================
# 同步到博客和论坛
# ============================================================================
sync_to_blog_forum() {
    log "同步到博客和论坛..."

    # 同步到博客 (详细说明)
    sync_to_blog

    # 同步到论坛 (简要说明)
    sync_to_forum

    log "博客论坛同步完成"
}

# ============================================================================
# 同步到博客
# ============================================================================
sync_to_blog() {
    log "同步到博客..."

    local blog_api="https://blog.mogoo.com/api/posts"
    local notes_file="$UPDATE_DIR/CHANGELOG-$LATEST_VERSION.md"

    # 读取更新说明内容
    local content=$(cat "$notes_file" 2>/dev/null || echo "")

    local blog_content="{\"title\":\"Hermes Desktop v$LATEST_VERSION 更新说明\",\"content\":$(echo "$content" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))'),\"category\":\"product-update\",\"tags\":[\"hermes\",\"update\",\"v$LATEST_VERSION\"]}"

    # 发布博客文章
    if response=$(curl -X POST -H "Content-Type: application/json" -d "$blog_content" "$blog_api" 2>/dev/null); then
        BLOG_URL=$(echo "$response" | grep -o '"url":"[^"]*"' | cut -d'"' -f4 || echo "https://blog.mogoo.com/hermes-update/$LATEST_VERSION")
        log "博客已发布: $BLOG_URL"
    else
        BLOG_URL="https://blog.mogoo.com/hermes-update/$LATEST_VERSION"
    fi
}

# ============================================================================
# 同步到论坛
# ============================================================================
sync_to_forum() {
    log "同步到论坛..."

    local forum_api="https://forum.mogoo.com/api/topics"

    local forum_content="{\"title\":\"Hermes Desktop v$LATEST_VERSION 更新\",\"summary\":\"版本 $LATEST_VERSION 已发布，主要改进：...\",\"blog_url\":\"$BLOG_URL\",\"category\":\"update-announcements\"}"

    # 发布论坛主题
    if response=$(curl -X POST -H "Content-Type: application/json" -d "$forum_content" "$forum_api" 2>/dev/null); then
        FORUM_URL=$(echo "$response" | grep -o '"url":"[^"]*"' | cut -d'"' -f4 || echo "https://forum.mogoo.com/topic/hermes-$LATEST_VERSION")
        log "论坛主题已发布: $FORUM_URL"
    else
        FORUM_URL="https://forum.mogoo.com/topic/hermes-$LATEST_VERSION"
    fi
}

# ============================================================================
# 回滚版本
# ============================================================================
rollback_version() {
    log "开始回滚流程..."

    local backup_dir="$INSTALL_DIR/backups"

    # 列出可用备份
    log "可用的备份版本:"
    ls -lt "$backup_dir"/*.tar.gz 2>/dev/null || log_error "没有可用的备份"

    # 使用最新的备份
    local rollback_file=$(ls -t "$backup_dir"/*.tar.gz 2>/dev/null | head -1)

    if [ -z "$rollback_file" ]; then
        log_error "没有可用的备份"
        exit 1
    fi

    log "回滚到备份: $rollback_file"

    # 恢复备份
    tar -xzf "$rollback_file" -C "$INSTALL_DIR"

    # 记录回滚
    echo "{\"action\":\"rollback\",\"time\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" >> "$INSTALL_DIR/update_history.json"

    log "回滚完成"
}

# ============================================================================
# 显示成功信息
# ============================================================================
show_success() {
    echo ""
    echo "=============================================================="
    echo -e "${GREEN}  更新完成！${NC}"
    echo "=============================================================="
    echo ""
    echo "  新版本: $LATEST_VERSION"
    echo "  更新说明: $UPDATE_DIR/CHANGELOG-$LATEST_VERSION.md"
    echo "  博客文章: $BLOG_URL"
    echo "  论坛讨论: $FORUM_URL"
    echo ""
    echo "=============================================================="
    echo ""
}

# ============================================================================
# 错误处理
# ============================================================================
error() {
    echo ""
    echo "=============================================================="
    echo -e "${RED}  更新失败！请查看日志: $LOG_FILE${NC}"
    echo "=============================================================="
    echo ""
    echo "  可能的问题:"
    echo "  - 网络连接失败"
    echo "  - 下载的更新包损坏"
    echo "  - 签名验证失败"
    echo ""
    echo "  解决方法:"
    echo "  - 检查网络连接"
    echo "  - 使用 --force 参数强制重新下载"
    echo "  - 使用 --rollback 参数回滚到上一版本"
    echo ""
    echo "=============================================================="

    # 发送错误通知
    send_error_notification

    exit 1
}

trap error ERR

# ============================================================================
# 发送错误通知
# ============================================================================
send_error_notification() {
    local email_api="https://internal.mogoo.com/api/notify"
    local error_email="{\"to\":\"devteam@mogoo.com\",\"subject\":\"Hermes Desktop 更新失败\",\"body\":\"版本 $CURRENT_VERSION 更新失败，请检查日志\"}"

    curl -X POST -H "Content-Type: application/json" -d "$error_email" "$email_api" >/dev/null 2>&1 || true
}

# ============================================================================
# 入口
# ============================================================================
parse_args "$@"
main "$@"