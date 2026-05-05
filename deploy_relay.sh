#!/bin/bash
# LivingTree Relay Server — One-Click Deploy (Linux/macOS)
set -e

PORT="${1:-}"
if [ -z "$PORT" ]; then
    read -p "Enter port number (recommend 8100-8199): " PORT
fi
PORT="${PORT:-8100}"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   LivingTree Relay Server Deploy        ║"
echo "║   Port: $PORT                              ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Step 1: Check Python
echo "[1/5] Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found. Install Python 3.14+ first."
    exit 1
fi
python3 --version

# Step 2: Create venv
echo ""
echo "[2/5] Setting up virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "venv created."
else
    echo "venv already exists."
fi

# Step 3: Install dependencies
echo ""
echo "[3/5] Installing dependencies..."
source .venv/bin/activate
pip install -e . --quiet 2>/dev/null || true
pip install aiohttp pyyaml pydantic loguru --quiet 2>/dev/null || true
echo "Dependencies ready."

# Step 4: Verify
echo ""
echo "[4/5] Verifying installation..."
.venv/bin/python -c "from livingtree.integration.hub import IntegrationHub; print('OK')" 2>/dev/null || echo "WARNING: Import check failed."

# Step 5: Start server
echo ""
echo "[5/5] Starting relay server on port $PORT..."
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Server: http://0.0.0.0:$PORT           ║"
echo "║  Health: /health                         ║"
echo "║  Chat:   POST /chat                      ║"
echo "║  Status: GET  /status                     ║"
echo "║  Tasks:  POST /tasks                      ║"
echo "║                                          ║"
echo "║  Press Ctrl+C to stop                    ║"
echo "╚══════════════════════════════════════════╝"
echo ""

.venv/bin/python relay_server.py --port "$PORT" --host 0.0.0.0
