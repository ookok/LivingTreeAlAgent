#!/bin/bash
# LivingTreeAI Deploy Script
# Phase 6: 云原生部署脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助
show_help() {
    cat << EOF
LivingTreeAI Deploy Script

用法: ./deploy.sh [命令] [选项]

命令:
    build       构建 Docker 镜像
    start       启动服务
    stop        停止服务
    restart     重启服务
    logs        查看日志
    status      查看状态
    clean       清理资源
    test        运行测试
    benchmark   运行基准测试
    full        完整部署 (build + start)
    help        显示帮助

选项:
    -e, --env ENV         环境 (development/production)
    -p, --port PORT      端口号
    -v, --volume PATH    数据卷路径
    -d, --daemon         后台运行

示例:
    ./deploy.sh build
    ./deploy.sh start -e production
    ./deploy.sh full -e production -p 8080

EOF
}

# 环境变量
ENV="development"
PORT=8000
VOLUME="./data"
DAEMON=""

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        build|start|stop|restart|logs|status|clean|test|benchmark|full)
            COMMAND="$1"
            shift
            ;;
        -e|--env)
            ENV="$2"
            shift 2
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -v|--volume)
            VOLUME="$2"
            shift 2
            ;;
        -d|--daemon)
            DAEMON="-d"
            shift
            ;;
        help|--help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose 未安装"
        exit 1
    fi
    
    log_success "依赖检查完成"
}

# 构建镜像
build() {
    log_info "构建 Docker 镜像..."
    
    cd "$(dirname "$0")"
    
    docker build \
        -f docker/Dockerfile \
        -t livingtreeai:latest \
        -t livingtreeai:$ENV \
        ../../
    
    log_success "镜像构建完成"
}

# 启动服务
start() {
    log_info "启动 LivingTreeAI..."
    
    cd "$(dirname "$0")"
    
    # 创建数据目录
    mkdir -p "$VOLUME"
    
    # 设置环境变量
    export LIVINGTREE_ENV="$ENV"
    export SECRET_KEY="$(openssl rand -hex 32 2>/dev/null || echo 'dev-secret-key')"
    
    if [ -n "$DAEMON" ]; then
        docker-compose up -d
    else
        docker-compose up
    fi
    
    log_success "LivingTreeAI 已启动 (端口: $PORT)"
}

# 停止服务
stop() {
    log_info "停止 LivingTreeAI..."
    
    cd "$(dirname "$0")"
    docker-compose down
    
    log_success "LivingTreeAI 已停止"
}

# 重启服务
restart() {
    stop
    sleep 2
    start
}

# 查看日志
logs() {
    cd "$(dirname "$0")"
    docker-compose logs -f
}

# 查看状态
status() {
    cd "$(dirname "$0")"
    docker-compose ps
    
    echo ""
    log_info "容器状态:"
    docker ps --filter "name=livingtree" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# 清理资源
clean() {
    log_warn "清理 Docker 资源..."
    
    cd "$(dirname "$0")"
    
    docker-compose down -v --remove-orphans
    docker image prune -f
    
    log_success "清理完成"
}

# 运行测试
test() {
    log_info "运行测试..."
    
    cd "$(dirname "$0")/../.."
    
    if [ -f "pytest.ini" ] || [ -f "pyproject.toml" ]; then
        python -m pytest tests/ -v --tb=short
    else
        log_warn "未找到测试配置"
    fi
    
    log_success "测试完成"
}

# 运行基准测试
benchmark() {
    log_info "运行性能基准测试..."
    
    cd "$(dirname "$0")/../.."
    
    python -m core.performance.benchmark
    
    log_success "基准测试完成"
}

# 完整部署
full_deploy() {
    log_info "开始完整部署..."
    
    check_dependencies
    build
    clean
    start
    
    sleep 3
    status
    
    log_success "部署完成!"
    log_info "访问 http://localhost:$PORT"
}

# 主逻辑
case "$COMMAND" in
    build)
        check_dependencies
        build
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    logs)
        logs
        ;;
    status)
        status
        ;;
    clean)
        clean
        ;;
    test)
        test
        ;;
    benchmark)
        benchmark
        ;;
    full)
        full_deploy
        ;;
    *)
        log_error "请指定命令"
        show_help
        exit 1
        ;;
esac
