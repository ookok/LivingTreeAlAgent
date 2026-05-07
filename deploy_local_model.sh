#!/bin/bash
# ============================================================
# LivingTree 本地模型一键部署脚本
# 部署 Qwen3.5-4B-Instruct via vLLM on Ubuntu 22.04+
#
# 用法:
#   chmod +x deploy_local_model.sh
#   ./deploy_local_model.sh              # 默认: Qwen3.5-4B, GPU自动检测
#   ./deploy_local_model.sh 8B           # 部署 Qwen3.5-8B
#   ./deploy_local_model.sh 4B cpu       # CPU模式 (慢)
#
# 部署后:
#   API端点: http://localhost:8000/v1
#   兼容 OpenAI SDK
# ============================================================
set -e

MODEL_SIZE="${1:-4B}"
DEVICE="${2:-auto}"
MODEL_ID=""
PORT=8000
MAX_MODEL_LEN=32768
GPU_MEMORY_UTILIZATION=0.90

# ── 模型选择 ──
case "$MODEL_SIZE" in
    0.6B|0.6b)
        MODEL_ID="Qwen/Qwen3.5-0.6B-Instruct"
        MAX_MODEL_LEN=32768
        ;;
    1.7B|1.7b)
        MODEL_ID="Qwen/Qwen3.5-1.7B-Instruct"
        MAX_MODEL_LEN=32768
        ;;
    4B|4b)
        MODEL_ID="Qwen/Qwen3.5-4B-Instruct"
        MAX_MODEL_LEN=32768
        ;;
    8B|8b)
        MODEL_ID="Qwen/Qwen3.5-8B-Instruct"
        MAX_MODEL_LEN=65536
        ;;
    14B|14b)
        MODEL_ID="Qwen/Qwen3.5-14B-Instruct"
        MAX_MODEL_LEN=65536
        ;;
    *)
        echo "不支持的模型大小: $MODEL_SIZE"
        echo "支持: 0.6B, 1.7B, 4B, 8B, 14B"
        exit 1
        ;;
esac

echo "============================================"
echo " LivingTree 本地模型部署"
echo "============================================"
echo " 模型: $MODEL_ID"
echo " 设备: $DEVICE"
echo " 端口: $PORT"
echo " 上下文: $MAX_MODEL_LEN tokens"
echo "============================================"

# ── 检查Python ──
if ! command -v python3 &> /dev/null; then
    echo "❌ 需要 Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓ Python $PYTHON_VERSION"

# ── 安装 vLLM ──
echo ""
echo "── 检查 vLLM ──"
if python3 -c "import vllm" 2>/dev/null; then
    echo "✓ vLLM 已安装"
else
    echo "安装 vLLM (可能需要几分钟)..."
    pip install vllm --upgrade
    echo "✓ vLLM 安装完成"
fi

# ── 检查 GPU ──
echo ""
echo "── 检查 GPU ──"
if [ "$DEVICE" = "cpu" ]; then
    echo "⚠  CPU 模式 (将非常慢)"
    GPU_FLAG=""
else
    if command -v nvidia-smi &> /dev/null; then
        GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
        echo "✓ 检测到 $GPU_COUNT GPU(s):"
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | while read line; do
            echo "    $line"
        done
        GPU_FLAG=""
    else
        echo "⚠  未检测到 NVIDIA GPU，将使用 CPU 模式"
        DEVICE="cpu"
        GPU_FLAG=""
    fi
fi

# ── 下载模型 ──
echo ""
echo "── 下载模型 ──"
# vLLM 首次启动时会自动下载模型，这里只是预热检查

# ── 启动 vLLM 服务 ──
echo ""
echo "── 启动 vLLM 服务 ──"
echo "   模型: $MODEL_ID"
echo "   端口: $PORT"
echo "   按 Ctrl+C 停止"
echo ""

python3 -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_ID" \
    --port "$PORT" \
    --max-model-len "$MAX_MODEL_LEN" \
    --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
    --trust-remote-code \
    --served-model-name "qwen3.5-local" \
    --host 0.0.0.0 \
    $GPU_FLAG

echo ""
echo "服务已停止。"
echo ""
echo "── 测试连接 ──"
echo "curl http://localhost:$PORT/v1/models"
echo ""
echo "── LivingTree 配置 ──"
echo "在 config.yaml 中添加:"
echo "  local_model:"
echo "    base_url: http://localhost:$PORT/v1"
echo "    model_name: qwen3.5-local"
