# LivingTree AI Agent — Production Docker Image
# Multi-stage build: builder → runner

# ── Stage 1: Builder ──
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build deps
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy project
COPY . .

# Install dependencies (skip optional heavy deps)
RUN pip install --no-cache-dir -e ".[ai,test]" 2>/dev/null || \
    pip install --no-cache-dir \
        fastapi>=0.104.0 \
        "uvicorn[standard]>=0.24.0" \
        aiohttp>=3.9.0 \
        pyyaml>=6.0 \
        pydantic>=2.0 \
        requests>=2.31.0 \
        loguru>=0.7.0 \
        jinja2>=3.0 \
        slowapi>=0.1.9

# ── Stage 2: Runner ──
FROM python:3.13-slim AS runner

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash livingtree && \
    mkdir -p /app/data /app/logs /app/config && \
    chown -R livingtree:livingtree /app

USER livingtree

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health')" || exit 1

EXPOSE 8080

# Entry point
ENTRYPOINT ["python", "-m", "livingtree"]
CMD ["server"]
