#!/usr/bin/env bash
# One-click installer — LivingTree AI Agent (Linux / macOS)
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/ookok/LivingTreeAlAgent/main/install.sh)

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

INSTALL_DIR="$HOME/livingtree"
VENV_DIR="$INSTALL_DIR/.venv"
REPO_URL="https://github.com/ookok/LivingTreeAlAgent.git"
REPO_GITEE="https://gitee.com/ookok/LivingTreeAlAgent.git"
PORT=8100

echo -e "${GREEN}"
cat << "EOF"
╔══════════════════════════════════════════════╗
║   🌳 生命之树 · LivingTree AI Agent          ║
║       One-Click Linux/macOS Installer        ║
╚══════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# ── Check Python ──

PYTHON=""
for cmd in python3 python; do
    if command -v $cmd &> /dev/null; then
        PYTHON=$(command -v $cmd)
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}❌ Python not found. Installing...${NC}"
    if command -v apt &> /dev/null; then
        sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
    elif command -v brew &> /dev/null; then
        brew install python3 git
    elif command -v yum &> /dev/null; then
        sudo yum install -y python3 python3-pip git
    else
        echo -e "${RED}Please install Python 3.10+ and git manually${NC}"
        exit 1
    fi
    PYTHON=$(command -v python3 || command -v python)
fi

PYVER=$($PYTHON --version 2>&1)
echo -e "${GREEN}✅ $PYVER${NC}"

# ── Clone / Update ──

if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${CYAN}📥 Updating repository...${NC}"
    cd "$INSTALL_DIR"
    git pull origin main 2>/dev/null || true
else
    echo -e "${CYAN}📥 Cloning repository...${NC}"
    rm -rf "$INSTALL_DIR"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" 2>/dev/null || \
    git clone --depth 1 "$REPO_GITEE" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# ── Setup venv ──

if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo -e "${CYAN}📦 Creating virtual environment...${NC}"
    $PYTHON -m venv "$VENV_DIR"
fi

PIP="$VENV_DIR/bin/pip"
PY="$VENV_DIR/bin/python"

echo -e "${CYAN}📦 Installing dependencies...${NC}"
$PIP install --upgrade pip -q
$PIP install -r requirements.txt -q

# ── Optional tools ──

echo -e "${CYAN}📦 Installing optional tools...${NC}"
$PIP install edge-tts -q 2>/dev/null || true
$PIP install numpy -q 2>/dev/null || true

# ── Check GPU ──

if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}✅ GPU detected (NVIDIA)${NC}"
fi

# ── Check Node.js ──

if command -v node &> /dev/null; then
    echo -e "${GREEN}✅ Node.js detected (npm MCP mode available)${NC}"
else
    echo -e "${YELLOW}💡 Install Node.js for Chrome automation${NC}"
fi

# ── Create CLI symlink ──

CLI_LINK="/usr/local/bin/livingtree"
if [ -w "/usr/local/bin" ] || [ "$(id -u)" = "0" ]; then
    cat > "$CLI_LINK" << CLISCRIPT
#!/usr/bin/env bash
cd "$INSTALL_DIR"
exec "$PY" -m livingtree "\$@"
CLISCRIPT
    chmod +x "$CLI_LINK" 2>/dev/null || sudo chmod +x "$CLI_LINK" 2>/dev/null || true
    echo -e "${GREEN}✅ CLI installed: livingtree${NC}"
fi

# ── Done ──

echo -e "${GREEN}"
cat << EOF

✅ Installation complete!

Start LivingTree:
  cd $INSTALL_DIR
  $PY -m livingtree

Or: livingtree start    (if CLI symlink created)

Web UI: http://localhost:$PORT/tree/living

CLI Management (CowAgent style):
  livingtree start              # background daemon
  livingtree stop               # stop service
  livingtree restart            # restart service
  livingtree status             # service status
  livingtree logs 50            # last 50 log lines
  livingtree skill hub          # browse skills
  livingtree skill install X    # install skill

EOF
echo -e "${NC}"

# ── Auto-start ──

read -p "Auto-start LivingTree now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}🚀 Starting LivingTree...${NC}"
    nohup $PY -m livingtree start &>/dev/null &
    sleep 2
    if command -v xdg-open &> /dev/null; then
        xdg-open "http://localhost:$PORT/tree/living" &
    elif command -v open &> /dev/null; then
        open "http://localhost:$PORT/tree/living" &
    fi
fi
