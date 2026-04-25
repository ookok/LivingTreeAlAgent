# LivingTreeAI - 智能代理平台

> *「根系装配园开放，每一位开发者都是嫁接者，将创新的枝条接入生命之树。」*

**LivingTreeAI** 是一个具备**自我意识**的智能代理平台，融合意图驱动IDE、多智能体协作与自我进化能力，让AI真正成为你的数字伙伴。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-green.svg)](https://pypi.org/project/PyQt6/)

---

## 🧭 愿景

```
LivingTreeAI = 智能代理平台 + 自我进化系统 + 意图驱动IDE
```

我们正在构建的不是一个普通的AI助手，而是一个能够：
- 🌱 **自我生长** - 从经验中学习，不断优化
- 🔄 **自我修复** - 自动检测并修复问题
- 🧠 **理解意图** - 听懂你想做什么，而非只是你说了什么
- 🤝 **协作进化** - 多智能体协同工作，共同成长

---

## 🏛️ 五大技术支柱

| 支柱 | 定位 | 核心能力 |
|------|------|----------|
| 🧠 **智能代理** | 核心引擎 | 多智能体协作、任务分解、知识管理 |
| 🔄 **自我进化** | 差异化优势 | 自我测试、诊断、修复、进化 |
| 💡 **意图驱动** | 用户接口 | 自然语言交互、代码生成、验证 |
| 📊 **领域面板** | 功能载体 | 金融面板、游戏面板、平台面板 |
| 🔧 **基础设施** | 技术底座 | 统一配置、代理网关、A2A协议 |

---

## 🚀 Phase 1：核心引擎（进行中）

**当前阶段**：构建 IntentEngine MVP 和统一配置系统

### 核心模块

#### 1. IntentEngine - 意图驱动引擎 ⭐ NEW

```python
from core.intent_engine import IntentParser, IntentClassifier, IntentExecutor

# 解析自然语言意图
parser = IntentParser()
intent = parser.parse("帮我写一个用户登录函数")

# 分类意图（优先级、复杂度）
classifier = IntentClassifier()
category = classifier.classify(intent)

# 执行意图
executor = IntentExecutor()
result = await executor.execute(intent, category)
```

| 组件 | 功能 | 状态 |
|------|------|------|
| `intent_parser.py` | 意图解析，12种意图类型 | ✅ MVP |
| `intent_classifier.py` | P0-P3优先级评估 | ✅ MVP |
| `intent_executor.py` | 异步执行引擎 | ✅ MVP |
| `intent_cache.py` | LRU+TTL缓存 | ✅ MVP |

#### 2. Evolution Engine - 进化引擎

| 组件 | 功能 | 状态 |
|------|------|------|
| 基因突变器 | 策略参数自动调优 | ✅ 核心完成 |
| 适者生存 | 优秀策略筛选 | ✅ 核心完成 |
| 交叉遗传 | 策略交叉组合 | 🔄 开发中 |
| 表观遗传 | 经验固化与传递 | 📋 规划中 |

#### 3. 自我意识系统

| 组件 | 功能 | 状态 |
|------|------|------|
| MirrorLauncher | 镜像测试启动器 | 🔄 开发中 |
| ComponentScanner | UI组件扫描器 | 📋 规划中 |
| AutoTester | 自动化测试引擎 | 📋 规划中 |
| HotFixEngine | 热修复引擎 | 📋 规划中 |

#### 4. 统一配置中心

```python
from core.config import get_unified_config, ServiceEndpoint

config = get_unified_config()

# 核心服务配置
model_url = config.model_service.url
relay_url = config.relay_service.url
```

| 配置项 | 说明 | 状态 |
|--------|------|------|
| 服务端点 | model/relay/knowledge | ✅ P0完成 |
| 超时配置 | default/long_running | ✅ P0完成 |
| 日志配置 | level/file/format | ✅ P0完成 |
| 重试配置 | max_retries/delay | 🔄 P1进行中 |
| 代理配置 | proxy_enabled/url | 📋 P2规划中 |

---

## 📊 演进路线图

```
Phase 0: 基础夯实     ✅ 已完成 (2026-04)
Phase 1: 核心引擎     🔄 当前 (8周)
Phase 2: 智能代理     📋 规划中 (8-16周)
Phase 3: 领域面板     📋 规划中 (16-24周)
Phase 4: 自我进化     📋 规划中 (24-32周)
Phase 5: 生态完善     📋 规划中 (32周后)
```

### Phase 1 任务清单

| 优先级 | 任务 | 周期 | 状态 |
|--------|------|------|------|
| P0 | IntentEngine MVP | 2周 | ✅ Day 1完成 |
| P0 | Evolution Engine核心 | 3周 | 🔄 进行中 |
| P0 | 自我意识系统核心 | 3周 | 📋 规划中 |
| P0 | 统一配置中心 | 2周 | ✅ Day 1完成 |
| P1 | PyQt6测试指挥官 | 2周 | 📋 规划中 |

---

## 🛠️ 技术架构

```
LivingTreeAlAgent/
├── client/src/                    # 桌面客户端 (PyQt6)
│   ├── presentation/              # 表现层 (UI面板)
│   ├── business/                  # 业务逻辑层
│   └── infrastructure/            # 基础设施层
├── core/                          # 核心引擎
│   ├── intent_engine/            # 💡 意图驱动 (NEW)
│   ├── evolution/                 # 🔄 进化引擎
│   ├── self_evolution/            # 🔄 自我进化
│   ├── agent/                     # 🧠 智能代理
│   ├── config/                    # 🔧 统一配置 (NEW)
│   └── ...
├── server/                        # 服务端
├── docs/                          # 设计文档 (63个)
└── main.py                        # 统一入口
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
pip install -e ./client
pip install -e ./server/relay_server
```

### 启动

```bash
# 桌面客户端
python main.py client

# 中继服务器
python main.py relay

# 全部服务
python main.py all
```

---

## 📈 设计文档

| 类别 | 数量 | 状态 |
|------|------|------|
| P0 核心文档 | 4个 | ✅ 完成 |
| P1 重要文档 | 12个 | ✅ 完成 |
| P2 增强文档 | 15个 | ✅ 完成 |
| 其他文档 | 32个 | ✅ 完成 |
| **总计** | **63个** | ✅ 全部完成 |

关键文档：
- [`docs/LIVING_TREE_AI_ROADMAP.md`](docs/LIVING_TREE_AI_ROADMAP.md) - 战略路线图
- [`docs/SELF_AWARENESS_SYSTEM_DESIGN.md`](docs/SELF_AWARENESS_SYSTEM_DESIGN.md) - 自我意识系统
- [`docs/UI_TEST_FIX_SYSTEM_DESIGN.md`](docs/UI_TEST_FIX_SYSTEM_DESIGN.md) - UI测试修复系统

---

## 🆕 最新更新 (2026-04-25)

### Phase 1 Day 1

- ✅ **IntentEngine MVP** - 意图驱动引擎核心模块发布
  - 意图解析器（12种意图类型）
  - 意图分类器（P0-P3优先级）
  - 异步执行引擎
  - LRU+TTL缓存机制

- ✅ **统一配置 P0** - 配置中心核心完成
  - ServiceEndpoint 服务端点
  - UnifiedConfig 统一配置类
  - 支持 YAML 加载/保存
  - 单例模式配置管理

---

## 🙏 致谢

- [PyQt6](https://pypi.org/project/PyQt6/) - 桌面应用框架
- [Ollama](https://ollama.ai/) - 本地 LLM 运行框架
- [ NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) - Agent 架构参考

---

## 📄 License

MIT License

---

*LivingTree AI - 让智能体像生命一样进化* 🌱
