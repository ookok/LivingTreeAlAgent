# 🌳 Hermes Desktop V2.0

> *「根系装配园开放，每一位开发者都是嫁接者，将创新的枝条接入生命之树。」*

一个基于 PyQt6 的桌面 AI 编程助手，集成了 GPT4All、NousHermes 和千问（Qwen）系列模型，支持本地 GGUF 模型加载与 MCP 协议扩展。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-green.svg)](https://pypi.org/project/PyQt6/)

---

## ✨ 核心功能

| 模块 | 说明 |
|------|------|
| 🔌 **MCP Server 管理器** | 一键部署和管理 MCP 协议服务器 |
| 🛠️ **Skill Market** | 技能市场，支持第三方扩展 |
| 🎭 **Digital Avatar** | 数字Avatar实时对话 |
| 💬 **LAN Chat** | 内网 P2P 加密通讯 |
| 💻 **Smart IDE** | AI 增强编程 + GitHub 项目集成 |
| 🎮 **Game Room** | 休闲游戏中心 |
| ⛓️ **Knowledge Blockchain** | 去中心化知识链 |
| 🔐 **Admin License System** | 管理员授权与序列号管理 |
| 💰 **Credit Economy System** | 积分经济生态 |
| 🏘️ **Universal Asset Ecosystem** | 通用资产交易生态 |
| 🎮 **Idle Grade System** | 挂机积分与等级系统 |
| 🏆 **Achievement System** | 全链路成就系统 |

---

## 🚀 快速开始

### 环境要求

- Windows 10+ / macOS 10.14+ / Ubuntu 18.04+
- Python 3.11+
- Git
- 至少 8GB RAM (推荐 16GB+)

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/ookok/LivingTreeAlAgent.git
cd hermes-desktop

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装 PyQt6
pip install PyQt6
```

### 启动方式

```bash
# 启动桌面客户端 (默认)
python main.py client

# 启动中继服务器
python main.py relay

# 启动追踪服务器
python main.py tracker

# 启动所有服务
python main.py all
```

---

## 📁 项目结构

```
hermes-desktop/
├── client/                    # 桌面客户端
│   └── src/
│       ├── presentation/      # UI层
│       ├── business/          # 业务逻辑层
│       └── infrastructure/    # 基础设施层
├── server/                    # 服务端
│   ├── relay_server/          # 中继服务器 (FastAPI)
│   └── tracker/               # 追踪服务器
├── core/                      # 核心业务模块
│   ├── fusion_rag/            # 多源融合检索
│   ├── intelligence_center/   # 全源情报中心
│   ├── credit_economy/       # 积分经济系统
│   ├── idle_grade_system/    # 挂机等级系统
│   ├── achievement_system/    # 全链路成就系统
│   └── admin_license_system/ # 管理员授权系统
├── ui/                        # PyQt6 UI 面板
├── docs/                      # 文档
└── main.py                    # 统一入口
```

---

## 🤖 本地模型支持

优先使用 **vLLM** 引擎加载本地模型，支持：

| 引擎 | 优先级 | 特点 |
|------|--------|------|
| **vLLM** | ⭐⭐⭐ | 高性能，张量并行 |
| **Nano-vLLM** | ⭐⭐ | 轻量级实现 |
| **Ollama** | ⭐ | 简单易用 |
| **llama-cpp-python** | - | 最广泛支持 |

### 模型加载配置

```python
from core.model_priority_loader import get_priority_loader

loader = get_priority_loader()
result = loader.load_model(
    model_path="models/your-model.gguf",
    backend_preference="vllm"
)
```

---

## 🎮 Smart IDE GitHub 集成

智能 IDE 支持直接从 GitHub 下载、编辑和推送项目：

```bash
# 克隆仓库
⬇️ git clone https://github.com/user/repo.git

# 拉取更新
🔄 git pull

# 推送更改
⬆️ git add . && git commit -m "更新" && git push
```

---

## 📊 会话统计

Hermes Agent 实时追踪会话指标：

| 指标 | 说明 |
|------|------|
| 🔧 工具调用 | 工具被调用的总次数 |
| 💬 过程消息 | 对话过程中的消息数量 |
| 🎯 调用技能 | 技能（Skill）被调用的次数 |
| 🔗 访问URL | 访问过的 URL 数量 |
| 📊 Token消耗 | prompt + completion tokens |
| ⏱️ 耗时 | 会话总耗时 |

---

## 🛠️ 开发指南

### 创建新模块

```python
# core/example_module/__init__.py
from .example import ExampleClass

__all__ = ["ExampleClass"]
```

```python
# core/example_module/example.py
class ExampleClass:
    def __init__(self):
        self.name = "Example Module"

    def process(self, data):
        return f"Processed: {data}"
```

### UI 面板模板

```python
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal

class ExamplePanel(QWidget):
    """示例面板"""

    data_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("示例面板"))
        self.setLayout(layout)
```

### API 开发

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/example", tags=["example"])

@router.post("/process")
async def process_example(request: ExampleRequest):
    return {"success": True, "result": "Processed"}
```

---

## 📖 文档

- [📚 开发手册](./docs/开发手册.md)
- [👤 用户手册](./docs/用户手册.md)
- [🏗️ 架构文档](./docs/ARCHITECTURE.md)
- [🔧 项目结构](./docs/PROJECT_STRUCTURE.md)

---

## 🧪 测试

```bash
# 运行测试
python -m pytest tests/

# 带覆盖率
python -m pytest tests/ --cov=core --cov-report=html
```

---

## 📝 提交规范

```
<type>(<scope>): <subject>

feat(core): 添加新功能
fix(ui): 修复界面bug
docs: 更新文档
refactor: 重构代码
test: 添加测试
```

---

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 致谢

- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) - Agent 架构参考
- [PyQt6](https://pypi.org/project/PyQt6/) - UI 框架
- [vLLM](https://github.com/vllm-project/vllm) - 高性能推理引擎
- [ModelScope](https://modelscope.cn/) - 魔搭社区模型支持

---

*Hermes Desktop - 让 AI 成为你的编程伙伴* 🌟

*最后更新: 2026-04-19*
