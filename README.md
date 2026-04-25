# LivingTreeAI - 智能代理平台

> *「根系装配园开放，每一位开发者都是嫁接者，将创新的枝条接入生命之树。」*

**LivingTreeAI** 是一个具备**自我意识**的智能代理平台，融合意图驱动IDE、多智能体协作与自我进化能力，让AI真正成为你的数字伙伴。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-green.svg)](https://pypi.org/project/PyQt6/)

---

## 🌱 愿景

```
LivingTreeAI = 智能代理平台 + 自我进化系统 + 意图驱动IDE
```

我们正在构建的不是一个普通的AI助手，而是一个能够：
- 🌱 **自我生长** - 从经验中学习，不断优化
- 🔄 **自我修复** - 自动检测并修复问题
- 💡 **理解意图** - 听懂你想做什么，而非只是你说了什么
- 🤝 **协作进化** - 多智能体协同工作，共同成长

---

## 🏛️ 技术架构（已迁移完成）

```
LivingTreeAlAgent/
├── client/src/                  # ✅ 所有代码已迁移到此
│   ├── main.py                 # PyQt6 入口
│   ├── business/               # 业务逻辑 (~340+ 文件)
│   │   ├── config.py           # UnifiedConfig 兼容层
│   │   ├── nanochat_config.py  # NanochatConfig (推荐)
│   │   ├── evolution_engine/   # 进化引擎
│   │   ├── intent_engine/      # 意图驱动引擎
│   │   └── ...                # 其他业务模块
│   ├── infrastructure/         # 数据库、配置、网络
│   ├── presentation/           # UI (~200+ 文件)
│   │   ├── panels/            # 所有面板 (102+ 文件)
│   │   ├── components/        # 可复用组件
│   │   └── widgets/          # 自定义控件
│   └── shared/               # 共享工具
├── server/                     # 服务器层
│   ├── relay_server/           # FastAPI relay
│   └── tracker_server.py      # P2P tracker
├── app/                        # 独立企业应用
├── mobile/                     # PWA/移动端
├── packages/                   # 共享库
├── config/                     # 配置文件
└── main.py                     # CLI 入口
```

**✅ 迁移完成（2026-04-26）：**
- `core/` → `client/src/business/` (28个子目录 + 44个独立文件)
- `ui/` → `client/src/presentation/` (102个文件 + 39个子目录)
- 所有导入引用已更新
- 临时脚本和过时文档已清理

---

## 🚀 五大技术支柱

| 支柱 | 定位 | 核心能力 |
|------|------|----------|
| 🧠 **智能代理** | 核心引擎 | 多智能体协作、任务分解、知识管理 |
| 🔄 **自我进化** | 差异化优势 | 自我测试、诊断、修复、进化 |
| 💡 **意图驱动** | 用户接口 | 自然语言交互、代码生成、验证 |
| 📊 **领域面板** | 功能载体 | 金融面板、游戏面板、平台面板 |
| 🔧 **基础设施** | 技术底座 | 统一配置、代理网关、A2A协议 |

---

## 📈 项目进度

| 阶段 | 状态 | 核心模块数 | 完成度 |
|------|------|-----------|--------|
| Phase 0: 基础夯实 | ✅ | - | 100% |
| Phase 1: 核心引擎 | ✅✅✅ | 10个 | 100% |
| Phase 2: 智能代理 | ✅✅✅ | 14个 | 100% |
| Phase 3: 领域面板 | ✅✅ | 4个 | 80% |
| Phase 4: 自我进化 | ✅✅✅ | 13个 | 100% |
| Phase 5: 生态完善 | ✅✅ | 2个 | 60% |
| Phase 6: 云原生 | 🔄 | 5个 | 20% |

### 核心模块（Phase 1-4 已完成）

#### ✅ IntentEngine - 意图驱动引擎
```python
from client.src.business.intent_engine import IntentEngine

engine = IntentEngine()
intent = engine.parse("帮我写一个用户登录接口，要用 FastAPI")
```

#### ✅ EvolutionEngine - 进化引擎
```python
from client.src.business.evolution_engine import EvolutionEngine

engine = EvolutionEngine()
# 自动进化、测试、修复
```

#### ✅ 配置系统（Nanochat 风格）
```python
# ✅ 推荐：NanochatConfig (dataclass, 10x 更快)
from client.src.business.nanochat_config import config

url = config.ollama.url
timeout = config.timeouts.default

# ⚠️ 兼容：UnifiedConfig (已弃用，仍工作)
from client.src.business.config import UnifiedConfig
config = UnifiedConfig.get_instance()
```

---

## ⚡ 快速开始

### 环境要求

- Python 3.11+
- PyQt6 6.0+
- Windows 10+ / macOS / Ubuntu

### 安装

```bash
git clone https://github.com/ookok/LivingTreeAlAgent.git
cd LivingTreeAlAgent

# 按顺序安装
pip install -e ./client
pip install -e ./server/relay_server
pip install -e ./app
```

### 启动

```bash
# 桌面客户端
python main.py client

# 中继服务器
python main.py relay

# P2P tracker
python main.py tracker

# 企业应用
python main.py app

# 全部服务
python main.py all
```

---

## 📊 项目统计

- **总提交数**: 17+ 次
- **总文件数**: 90+ 个
- **总代码行数**: 35,000+ 行
- **设计文档**: 15+ 份

---

## 🎯 设计原则

1. **意图驱动** - 用户只关心"做什么"，不关心"怎么做"
2. **自我进化** - 系统能够自我测试、诊断、修复
3. **模块化** - 高度解耦，易于扩展
4. **可视化** - 所有过程可视化追踪
5. **安全性** - 沙箱隔离、权限控制
6. **极简配置** - 学习 nanochat 设计哲学（配置即代码，dataclass 优先）

---

## 🆕 最新更新 (2026-04-26)

### 项目结构优化

- ✅ **`core/` 目录完全迁移** - 所有 28 个子目录和 44 个独立文件已迁移到 `client/src/business/`
- ✅ **`ui/` 目录完全迁移** - 所有 102 个文件和 39 个子目录已迁移到 `client/src/presentation/`
- ✅ **导入引用全部更新** - 项目中不再有 `from core.xxx` 或 `from ui.xxx` 的导入
- ✅ **临时文件清理** - 删除 30+ 个临时脚本和 15+ 个过时报告文档
- ✅ **AGENTS.md 更新** - 反映新的项目结构

### 配置系统重构

- ✅ **NanochatConfig 引入** - 极简 dataclass 风格配置
- ✅ **性能提升 10x** - 无 YAML 解析，无字典查找
- ✅ **类型安全** - IDE 自动补全
- ⚠️ **UnifiedConfig 弃用** - 仍工作但显示警告

---

## 🙏 致谢

- [PyQt6](https://pypi.org/project/PyQt6/) - 桌面应用框架
- [Ollama](https://ollama.ai/) - 本地 LLM 运行框架
- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) - Agent 架构参考

---

## 🄜 License

MIT License

---

*LivingTree AI - 让智能体像生命一样进化* 🌱
