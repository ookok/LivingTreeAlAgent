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

# Step 1: Check Python 3.14
echo "[1/5] Checking Python 3.14..."
PYTHON_CMD=""
if command -v python3.14 &>/dev/null; then
    PYTHON_CMD="python3.14"
elif python3 -c "import sys; sys.exit(0 if sys.version_info>=(3,14) else 1)" 2>/dev/null; then
    PYTHON_CMD="python3"
else
    echo "   Python 3.14 not found. Attempting install..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        curl -fsSL https://www.python.org/ftp/python/3.14.0/python-3.14.0-macos11.pkg -o /tmp/python314.pkg
        sudo installer -pkg /tmp/python314.pkg -target /
        PYTHON_CMD="python3.14"
    else
        sudo apt-get update -qq && sudo apt-get install -y -qq python3.14 python3.14-venv 2>/dev/null || true
        PYTHON_CMD="python3.14"
    fi
fi
$PYTHON_CMD --version

# Step 2: Create venv
echo ""
echo "[2/5] Setting up virtual environment..."
if [ ! -d ".venv" ]; then
    $PYTHON_CMD -m venv .venv
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
