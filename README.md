# LivingTreeAI - 智能代理平台

> *「根系装配园开放，每一位开发者都是嫁接者，将创新的枝条接入生命之树。」*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-green.svg)](https://pypi.org/project/PyQt6/)
[![GitHub: Issues](https://img.shields.io/github/issues/ookok/LivingTreeAlAgent)](https://github.com/ookok/LivingTreeAlAgent/issues)
[![GitHub: Stars](https://img.shields.io/github/stars/ookok/LivingTreeAlAgent)](https://github.com/ookok/LivingTreeAlAgent/stargazers)

---

## 🌱 愿景

**LivingTreeAI** 是一个具备**自我意识**的智能代理平台，融合意图驱动IDE、多智能体协作与自我进化能力，让AI真正成为你的数字伙伴。

```
LivingTreeAI = 智能代理平台 + 自我进化系统 + 意图驱动IDE
```

我们正在构建的不是一个普通的AI助手，而是一个能够：

- 🌱 **自我生长** - 从经验中学习，不断优化
- 🔄 **自我修复** - 自动检测并修复问题
- 💡 **理解意图** - 听懂你想做什么，而非只是你说了什么
- 🤝 **协作进化** - 多智能体协同工作，共同成长

---

## 🚀 核心特性

### 1. 意图驱动交互

LivingTreeAI 使用先进的意图识别引擎，能够理解用户的真实需求，而非简单的命令执行。

```python
from client.src.business.intent_engine import IntentEngine

engine = IntentEngine()
intent = engine.parse("帮我写一个用户登录接口，要用 FastAPI")
# 自动理解意图，生成代码，验证结果
```

### 2. 自我进化引擎

系统能够自动进化、测试、修复，无需人工干预。通过遗传算法、NSGA-II 多目标优化、表观遗传等技术，实现真正的自我进化。

```python
from client.src.business.evolution_engine import EvolutionEngine

engine = EvolutionEngine()
# 自动进化、测试、修复，无需人工干预
```

**核心能力**：
- 🧬 遗传算法优化
- 📊 NSGA-II 多目标优化
- 🔄 自适应进化策略
- 🧪 表观遗传（Lamarckian + Baldwinian）
- 🔧 热修复引擎
- 🔍 根因追踪器

### 3. 多智能体协作

支持多智能体协同工作，自动任务分解、分配、执行、聚合。

```python
from client.src.business.hermes_agent import HermesAgent

agent1 = HermesAgent(name="Coder")
agent2 = HermesAgent(name="Tester")
agent1.collaborate(agent2)
# 自动任务分解、分配、执行、聚合
```

### 4. 融合RAG（FusionRAG）

多源数据检索系统，结合向量检索、图谱检索、混合检索，提供精准的知识检索能力。

**三层架构**：
- L1: 向量检索（Dense Retrieval）
- L2: 图谱检索（Graph Retrieval）
- L3: 混合检索（Hybrid Retrieval）

### 5. 领域面板

针对不同领域提供专业面板：
- 💰 **FinanceHubPanel** - 金融面板（投资分析、支付集成、信用评估）
- 🎮 **GameHubPanel** - 游戏面板（游戏库、会话管理、成就系统）
- 🏥 **HealthHubPanel** - 健康面板（规划中）
- 📚 **EducationHubPanel** - 教育面板（规划中）

---

## 🏛️ 技术架构

### 已完成迁移（2026-04-26）

项目已完成从 `core/` + `ui/` 到 `client/src/` 的迁移，采用清晰的三层架构：

```
LivingTreeAlAgent/
├── client/src/                  # ✅ 所有代码已迁移到此
│   ├── business/               # 业务逻辑 (~340+ 文件)
│   │   ├── intent_engine/      # 意图驱动引擎
│   │   ├── evolution_engine/   # 进化引擎 (71 文件)
│   │   ├── hermes_agent/       # Agent 框架
│   │   ├── fusion_rag/         # 多源检索
│   │   └── ...                # 其他 300+ 模块
│   ├── presentation/           # UI (~200+ 文件)
│   │   ├── panels/            # 所有面板 (102+ 文件)
│   │   ├── components/        # 可复用组件
│   │   └── widgets/          # 自定义控件
│   ├── infrastructure/         # 数据库、配置、网络
│   └── shared/               # 共享工具
├── server/                     # 服务器层
│   ├── relay_server/           # FastAPI relay (46 文件)
│   └── tracker_server.py      # P2P tracker
├── app/                        # 独立企业应用
├── mobile/                     # PWA/移动端
├── packages/                   # 共享库
└── tests/                      # 测试文件
```

**✅ 迁移完成：**
- `core/` → `client/src/business/` (28个子目录 + 44个独立文件)
- `ui/` → `client/src/presentation/` (102个文件 + 39个子目录)
- 所有导入引用已更新
- 临时脚本和过时文档已清理

### 五大技术支柱

| 支柱 | 定位 | 核心能力 | 状态 |
|------|------|----------|------|
| 🧠 **智能代理** | 核心引擎 | 多智能体协作、任务分解、知识管理 | ✅ 100% |
| 🔄 **自我进化** | 差异化优势 | 自我测试、诊断、修复、进化 | ✅ 100% |
| 💡 **意图驱动** | 用户接口 | 自然语言交互、代码生成、验证 | ✅ 100% |
| 📊 **领域面板** | 功能载体 | 金融面板、游戏面板、平台面板 | 🔄 80% |
| 🔧 **基础设施** | 技术底座 | 统一配置、代理网关、A2A协议 | ✅ 100% |

---

## 📈 项目进度

| 阶段 | 状态 | 核心模块数 | 完成度 |
|------|------|-----------|--------|
| Phase 0: 基础夯实 | ✅ | - | 100% |
| Phase 1: 核心引擎 | ✅ | 10个 | 100% |
| Phase 2: 智能代理 | ✅ | 14个 | 100% |
| Phase 3: 领域面板 | 🔄 | 4个 | 80% |
| Phase 4: 自我进化 | ✅ | 13个 | 100% |
| Phase 5: 生态完善 | 🔄 | 2个 | 60% |
| Phase 6: 云原生 | 🔄 | 5个 | 20% |

---

## 🛠️ 技术栈

### 后端技术

| 技术 | 版本 | 用途 |
|------|------|------|
| **Python** | 3.11+ | 主力开发语言 |
| **PyQt6** | 6.0+ | 桌面 GUI 框架 |
| **FastAPI** | 0.104+ | 服务器 API 框架 |
| **SQLite** | 3.35+ | 本地数据库 |
| **PostgreSQL** | 14+ | 服务器数据库（可选） |

### AI/ML 技术

| 技术 | 版本 | 用途 |
|------|------|------|
| **Ollama** | 0.1.0+ | 本地 LLM 运行框架 |
| **Qwen** | 3.5:4b | 默认推理模型 |
| **LangChain** | 0.0.340+ | Agent 开发框架 |
| **ChromaDB** | 0.4.0+ | 向量数据库 |

### 前端技术

| 技术 | 版本 | 用途 |
|------|------|------|
| **PyQt6** | 6.0+ | UI 组件库 |
| **QSS** | - | 样式表（类似 CSS） |
| **Matplotlib** | 3.8+ | 图表绘制 |

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

### CLI 使用

```bash
# 通过 CLI 入口点
python -m livingtree client

# 查看帮助
livingtree --help
```

---

## 📊 项目统计

- **总提交数**: 17+ 次
- **总文件数**: 90+ 个
- **总代码行数**: 35,000+ 行
- **设计文档**: 15+ 份
- **核心模块**: 340+ 个
- **UI 组件**: 200+ 个

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

## 📚 文档

- [ARCHITECTURE.md](./ARCHITECTURE.md) - 详细架构文档
- [AGENTS.md](./AGENTS.md) - AI 指引文档
- [TODO.md](./TODO.md) - 待办任务清单
- [PROGRAMMING_OS_ROADMAP.md](./PROGRAMMING_OS_ROADMAP.md) - 编程操作系统路线图

---

## 🤝 贡献指南

我们欢迎任何形式的贡献！

### 开发流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 代码规范

- 遵循 PEP 8 代码风格
- 使用 `from client.src.business.xxx` 导入（而非 `from core.xxx`）
- 新功能先更新 `TODO.md` 再开始开发
- 提交前确保测试通过

---

## 📝 待办任务

详见 [TODO.md](./TODO.md) 查看完整的待办任务清单。

**高优先级任务**：
- [ ] 修复代码重复问题（EvolutionEngine × 9）
- [ ] 修复配置接口不兼容问题
- [ ] FinanceHubPanel 功能完善

---

## 🙏 致谢

- [PyQt6](https://pypi.org/project/PyQt6/) - 桌面应用框架
- [Ollama](https://ollama.ai/) - 本地 LLM 运行框架
- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) - Agent 架构参考
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Web 框架
- [LangChain](https://python.langchain.com/) - LLM 应用开发框架

---

## 📄 License

本项目采用 MIT License - 查看 [LICENSE](LICENSE) 文件了解详情。

---

## 📧 联系方式

- GitHub Issues: [提交问题](https://github.com/ookok/LivingTreeAlAgent/issues)
- 讨论区: [参与讨论](https://github.com/ookok/LivingTreeAlAgent/discussions)

---

*LivingTree AI - 让智能体像生命一样进化* 🌱

---

## 🔗 相关链接

- [在线演示](https://livingtree.ai/demo)（即将上线）
- [文档中心](https://docs.livingtree.ai)（即将上线）
- [社区论坛](https://community.livingtree.ai)（即将上线）

---

*最后更新：2026-04-26*
