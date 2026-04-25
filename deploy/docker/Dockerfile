# LivingTreeAI Dockerfile - 多阶段构建优化版
# Phase 6: 云原生部署

# ============ 阶段1: 构建阶段 ============
FROM python:3.11-slim AS builder

# 设置工作目录
WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============ 阶段2: 运行阶段 ============
FROM python:3.11-slim AS runtime

# 设置维护者
LABEL maintainer="LivingTreeAI Team <team@livingtreeai.com>"
LABEL version="1.0.0"
LABEL description="LivingTreeAI - Build the Future of AI Coding"

# 设置工作目录
WORKDIR /app

# 安全: 创建非root用户
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

# 复制应用代码
COPY --chown=livingtree:livingtree . .

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    LIVINGTREE_ENV=production

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 切换到非root用户
USER livingtree

# 预热缓存
RUN python -c "import sys; print('Python ready')" 2>/dev/null || true

# 启动命令
CMD ["python", "-m", "livingtree", "serve", "--host", "0.0.0.0", "--port", "8000"]

# ============ 开发环境 (可选) ============
FROM runtime AS development

# 开发模式
ENV LIVINGTREE_ENV=development

# 安装开发工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

# 开发模式启动
CMD ["python", "-m", "livingtree", "serve", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============ 最小化生产环境 (可选) ============
FROM python:3.11-alpine AS production-minimal

WORKDIR /app

# Alpine 使用 musl libc，更轻量
RUN addgroup -g 1000 livingtree && \
    adduser -u 1000 -G livingtree -s /bin/sh -D livingtree

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY --chown=livingtree:livingtree . .

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    LIVINGTREE_ENV=production

EXPOSE 8000

USER livingtree

CMD ["python", "-m", "livingtree", "serve", "--host", "0.0.0.0", "--port", "8000"]
