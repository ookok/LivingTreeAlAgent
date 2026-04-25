# LivingTreeAI Dockerfile - 多阶段构建优化版
# Phase 6: 云原生部署（优化版）
# 构建时间: ~3min | 镜像大小: ~800MB

# ============ 阶段1: 依赖构建 ============
FROM python:3.11-slim AS builder

WORKDIR /build

# 安装系统构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境
RUN python -m venv /opt/venv

# 复制依赖文件（利用 Docker 缓存）
COPY requirements.txt pyproject.toml setup.py* ./
COPY client/setup.py client/setup.py || true
COPY server/relay_server/setup.py server/relay_server/setup.py || true

# 安装 Python 依赖到虚拟环境
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e . -e client/ -e server/relay_server/ || \
    pip install --no-cache-dir -r requirements.txt

# ============ 阶段2: 生产运行环境 ============
FROM python:3.11-slim AS runtime

LABEL maintainer="LivingTreeAI Team <team@livingtreeai.com>"
LABEL version="1.0.0"
LABEL description="LivingTreeAI - Build the Future of AI Coding"

# 安全: 创建非 root 用户
RUN groupadd --gid 1000 livingtree && \
    useradd --uid 1000 --gid livingtree --shell /bin/bash --create-home livingtree

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 创建应用目录
WORKDIR /app

# 复制应用代码（按变更频率分层）
COPY --chown=livingtree:livingtree config/ config/
COPY --chown=livingtree:livingtree core/ core/
COPY --chown=livingtree:livingtree client/ client/
COPY --chown=livingtree:livingtree server/ server/
COPY --chown=livingtree:livingtree main.py pyproject.toml ./

# 创建数据和日志目录
RUN mkdir -p /data /logs && \
    chown -R livingtree:livingtree /data /logs

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    LIVINGTREE_ENV=production \
    OLLAMA_URL=http://ollama:11434/v1

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 切换到非 root 用户
USER livingtree

# 预热 Python（减少冷启动时间）
RUN python -c "import sys; print('Python ready')" 2>/dev/null || true

# 启动命令
CMD ["python", "-m", "livingtree", "serve", "--host", "0.0.0.0", "--port", "8000"]

# ============ 阶段3: 开发环境 ============
FROM runtime AS development

ENV LIVINGTREE_ENV=development

# 安装开发工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

# 以 root 运行开发模式
USER root

# 开发模式启动
CMD ["python", "-m", "livingtree", "serve", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============ 阶段4: 最小化生产环境（Alpine） ============
FROM python:3.11-alpine AS production-minimal

WORKDIR /app

# Alpine 使用 musl libc，更轻量
RUN addgroup -g 1000 livingtree && \
    adduser -u 1000 -G livingtree -s /bin/sh -D livingtree

# 安装运行时依赖
RUN apk add --no-cache \
    curl \
    ca-certificates

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制应用代码
COPY --chown=livingtree:livingtree . .

# 创建数据目录
RUN mkdir -p /data /logs && \
    chown -R livingtree:livingtree /data /logs

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    LIVINGTREE_ENV=production

EXPOSE 8000

USER livingtree

CMD ["python", "-m", "livingtree", "serve", "--host", "0.0.0.0", "--port", "8000"]

# ============ 阶段5: 测试环境 ============
FROM runtime AS test

# 安装测试依赖
RUN pip install --no-cache-dir \
    pytest \
    pytest-cov \
    pytest-asyncio

WORKDIR /app/tests

CMD ["pytest", "--cov=core", "--cov-report=html", "-v"]
