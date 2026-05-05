#!/bin/bash
# LivingTree — One-Command Auto-Deploy (Linux/macOS)
# Usage: curl -fsSL https://raw.githubusercontent.com/.../install.sh | bash
#        bash install.sh --port 8100 --relay

set -e

GITHUB_REPO="https://github.com/ookok/LivingTreeAlAgent.git"
GITEE_REPO="https://gitee.com/ookok/LivingTreeAlAgent.git"
INSTALL_DIR="${HOME}/livingtree"
PYTHON_CMD=""
PORT="8100"
MODE="all"  # all | client | relay

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --port) PORT="$2"; shift 2 ;;
        --dir) INSTALL_DIR="$2"; shift 2 ;;
        --client) MODE="client"; shift ;;
        --relay) MODE="relay"; shift ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

echo "🌳 LivingTree Auto-Deploy"
echo "   Mode: $MODE | Port: $PORT | Dir: $INSTALL_DIR"

# Step 1: Find/Install Python 3.14
echo "[1/7] Python 3.14..."
if command -v python3.14 &>/dev/null; then
    PYTHON_CMD="python3.14"
elif python3 -c "import sys; sys.exit(0 if sys.version_info>= (3,14) else 1)" 2>/dev/null; then
    PYTHON_CMD="python3"
else
    echo "   Installing Python 3.14..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        curl -fsSL https://www.python.org/ftp/python/3.14.0/python-3.14.0-macos11.pkg -o /tmp/python314.pkg
        sudo installer -pkg /tmp/python314.pkg -target /
        PYTHON_CMD="python3.14"
    else
        sudo apt-get update -qq && sudo apt-get install -y -qq python3.14 python3.14-venv 2>/dev/null || true
        if ! command -v python3.14 &>/dev/null; then
            echo "   Please install Python 3.14 manually: https://www.python.org/downloads/"
            exit 1
        fi
        PYTHON_CMD="python3.14"
    fi
fi
echo "   $($PYTHON_CMD --version)"

# Step 2: Clone project (GitHub → Gitee fallback)
echo "[2/7] Downloading..."
if [ -d "$INSTALL_DIR" ]; then
    echo "   Directory exists — updating..."
    cd "$INSTALL_DIR"
    git pull --ff-only origin main 2>/dev/null || true
else
    git clone --depth 1 "$GITHUB_REPO" "$INSTALL_DIR" 2>/dev/null || \
    git clone --depth 1 "$GITEE_REPO" "$INSTALL_DIR" 2>/dev/null || {
        echo "   ERROR: Cannot clone from GitHub or Gitee. Check network."
        exit 1
    }
    cd "$INSTALL_DIR"
fi

# Step 3: Create venv
echo "[3/7] Virtual environment..."
if [ ! -d ".venv" ]; then
    $PYTHON_CMD -m venv .venv
fi
source .venv/bin/activate

# Step 4: Install deps
echo "[4/7] Dependencies..."
pip install -e . --quiet 2>/dev/null || true
pip install aiohttp pyyaml pydantic loguru rich textual --quiet 2>/dev/null || true

# Step 5: Verify
echo "[5/7] Verifying..."
.venv/bin/python -c "from livingtree.tui.app import LivingTreeTuiApp; print('   OK')" 2>/dev/null || echo "   WARNING: Import check failed"

# Step 6: Create launcher
echo "[6/7] Creating launcher..."
cat > "$INSTALL_DIR/livingtree.sh" << LAUNCHER
#!/bin/bash
cd "$INSTALL_DIR"
source .venv/bin/activate
if [ "\$1" = "relay" ]; then
    python relay_server.py --port "${PORT}" "\$@"
else
    python -m livingtree tui "\$@"
fi
LAUNCHER
chmod +x "$INSTALL_DIR/livingtree.sh"
ln -sf "$INSTALL_DIR/livingtree.sh" /usr/local/bin/livingtree 2>/dev/null || true

# Step 7: Start
echo "[7/7] Starting..."
echo ""
if [ "$MODE" = "relay" ]; then
    echo "Starting relay server on port $PORT..."
    python relay_server.py --port "$PORT"
else
    echo "Launch with: livingtree"
    echo "   or: cd $INSTALL_DIR && python -m livingtree tui"
fi
