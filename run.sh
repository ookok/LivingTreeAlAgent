#!/bin/bash

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e ""
echo -e "${CYAN}██╗      █████╗ ██╗   ██╗███████╗██╗   ██╗██████╗ ${NC}"
echo -e "${CYAN}██║     ██╔══██╗██║   ██║██╔════╝╚██╗ ██╔╝██╔══██╗${NC}"
echo -e "${CYAN}██║     ███████║██║   ██║█████╗   ╚████╔╝ ██████╔╝${NC}"
echo -e "${CYAN}██║     ██╔══██║██║   ██║██╔══╝    ╚██╔╝  ██╔═══╝ ${NC}"
echo -e "${CYAN}███████╗██║  ██║╚██████╔╝███████╗   ██║   ██║     ${NC}"
echo -e "${CYAN}╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝   ╚═╝     ${NC}"
echo -e ""
echo -e "${CYAN}                    LivingTreeAI 一键启动器${NC}"
echo -e "${CYAN}============================================${NC}"
echo -e ""

PYTHON_REQUIRED_MAJOR="3"
PYTHON_REQUIRED_MINOR="11"

echo -e "${CYAN}[1/5] 检查 Python 环境...${NC}"
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo -e "${RED}❌ 未检测到 Python，请先安装 Python ${PYTHON_REQUIRED_MAJOR}.${PYTHON_REQUIRED_MINOR}+${NC}"
        echo -e "${YELLOW}📥 下载地址: https://www.python.org/downloads/${NC}"
        exit 1
    fi
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

PYTHON_VERSION=$(${PYTHON_CMD} --version 2>&1 | cut -d' ' -f2)
PYTHON_MAJOR=$(echo "${PYTHON_VERSION}" | cut -d'.' -f1)
PYTHON_MINOR=$(echo "${PYTHON_VERSION}" | cut -d'.' -f2)

if [[ "${PYTHON_MAJOR}" -lt "${PYTHON_REQUIRED_MAJOR}" ]]; then
    echo -e "${RED}❌ Python 版本过低，需要 ${PYTHON_REQUIRED_MAJOR}.${PYTHON_REQUIRED_MINOR}+${NC}"
    exit 1
fi

if [[ "${PYTHON_MAJOR}" -eq "${PYTHON_REQUIRED_MAJOR}" && "${PYTHON_MINOR}" -lt "${PYTHON_REQUIRED_MINOR}" ]]; then
    echo -e "${RED}❌ Python 版本过低，需要 ${PYTHON_REQUIRED_MAJOR}.${PYTHON_REQUIRED_MINOR}+${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python ${PYTHON_VERSION} 符合要求${NC}"

echo -e "${CYAN}[2/5] 检查 Git...${NC}"
if ! command -v git &> /dev/null; then
    echo -e "${YELLOW}⚠️  未检测到 Git，将跳过更新检测${NC}"
    HAS_GIT=0
else
    echo -e "${GREEN}✅ Git 已安装${NC}"
    HAS_GIT=1
fi

if [[ "${HAS_GIT}" -eq 1 ]]; then
    echo -e "${CYAN}[3/5] 检查更新...${NC}"
    git fetch --quiet
    UPDATES=$(git rev-list --count HEAD..origin/master 2>/dev/null || echo "0")
    if [[ "${UPDATES}" -gt 0 ]]; then
        echo -e "${YELLOW}📥 发现 ${UPDATES} 个更新${NC}"
        read -p "是否自动更新? (Y/N): " DO_UPDATE
        if [[ "${DO_UPDATE}" == "Y" || "${DO_UPDATE}" == "y" ]]; then
            echo -e "${CYAN}正在拉取更新...${NC}"
            git pull --quiet
            echo -e "${GREEN}✅ 更新完成${NC}"
        fi
    else
        echo -e "${GREEN}✅ 当前已是最新版本${NC}"
    fi
fi

echo -e "${CYAN}[4/5] 检查依赖...${NC}"
${PYTHON_CMD} -c "import sys; sys.path.insert(0, 'client/src'); from business.config import UnifiedConfig" 2>/dev/null || {
    echo -e "${YELLOW}📦 正在安装依赖...${NC}"
    pip install -e client/ -e server/relay_server/ -q || {
        echo -e "${YELLOW}⚠️  使用备用依赖安装...${NC}"
        pip install -r requirements.txt -q
    }
}
echo -e "${GREEN}✅ 依赖检查完成${NC}"

echo -e "${CYAN}[5/5] 启动 LivingTreeAI...${NC}"
echo -e ""
${PYTHON_CMD} main.py client

echo -e ""
echo -e "${GREEN}感谢使用 LivingTreeAI！${NC}"