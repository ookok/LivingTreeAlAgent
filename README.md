# LivingTreeAlAgent - 自我进化智能代理平台

> *「根系装配园开放，每一位开发者都是嫁接者，将创新的枝条接入生命之树。」*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-green.svg)](https://pypi.org/project/PyQt6/)

---

## 核心理念

LivingTreeAlAgent 是一个具备**自我进化**能力的智能代理平台，遵循**极简设计**原则：

```
会话交互 → 需求澄清 → 渐进渲染UI
```

### 三大设计原则

| 原则 | 说明 | 实践 |
|------|------|------|
| **会话优先** | 自然语言驱动一切交互 | 用户说意图，系统理解并执行 |
| **需求澄清** | 不猜，多问，直到确定 | IntentClarifier 主动澄清模糊需求 |
| **渐进渲染** | 先给轮廓，逐步完善 | ProgressiveUIRenderer 按需加载 |

### 自我进化三禁止

```
┌─────────────────────────────────────────────────────┐
│  ❌ 禁止预置          ✅ 鼓励学习                    │
│  - 固定模板           - 从样本学习                   │
│  - 硬编码规则         - 动态知识图谱                 │
│  - 不可变流程         - 可演进工作流                 │
└─────────────────────────────────────────────────────┘
```

---

## 核心特性

### 1. LLM分层推理 (L0-L4)

```
L0: 路由判断 → L3: 深度推理 → L4: 生成优化
```

| 模型 | 用途 | 特点 |
|------|------|------|
| qwen3.5:2b | L0路由 | 快速响应 |
| qwen3.5:4b | L3推理 | 深度思考 |
| qwen3.6:35b | L4生成 | 高质量输出 |

### 2. 环评EIA专业系统 (96%匹配)

35个核心模块，覆盖环境影响评价全流程：
- 📊 工作台 / 合规检查 / 报告生成
- 🌫️ AERMOD大气扩散 / 💧 Mike21水动力
- 🌍 地下水模拟 / 🌧️ 暴雨排水

### 3. 统一工具层

```
ToolRegistry (语义搜索) ← BaseTool (抽象基类) ← 20+工具实现
```

| 类别 | 工具 |
|------|------|
| 🌐 网络 | WebCrawler, DeepSearch, TierRouter |
| 📄 文档 | DocumentParser, IntelligentOCR |
| 💾 存储 | VectorDB, KnowledgeGraph, Memory |
| 📋 任务 | TaskDecomposer, ExecutionEngine |

### 4. 技能系统

220+专家角色，涵盖工程、法律、金融等20+领域：

```python
# 使用技能
/skill chemical-expert    # 化工专家
/skill EIA-wizard         # 环评向导
/skill legal-consultant   # 法律顾问
```

### 5. 自我进化引擎

- 🔍 **ToolSelfRepairer**: 自动修复工具执行错误
- 📚 **HardVariantGenerator**: 从错题生成更难变体
- 🧪 **ExperimentLoop**: 双数据飞轮训练

---

## 技术架构

```
LivingTreeAlAgent/
├── client/src/                    # 核心代码
│   ├── business/                  # 业务逻辑 (~340+ 文件)
│   │   ├── hermes_agent/         # Agent框架
│   │   ├── tools/                # 统一工具层
│   │   ├── self_evolution/       # 自我进化
│   │   ├── global_model_router.py # LLM路由
│   │   └── eia_workbench/        # 环评系统
│   └── presentation/             # PyQt6 UI (~200+ 文件)
├── docs/                          # 核心文档
│   ├── LIVINGTREE_ARCHITECTURE_GUIDE.md  # 架构指南
│   └── LIVINGTREE_DEVELOPMENT_GUIDE.md   # 开发指南
└── server/                       # FastAPI服务器
```

---

## 快速开始

### 环境要求

- Python 3.11+
- PyQt6 6.0+
- Ollama (本地LLM)

### 安装

```bash
git clone https://github.com/ookok/LivingTreeAlAgent.git
cd LivingTreeAlAgent
pip install -e ./client
```

### 启动

```bash
python main.py client
```

---

## 开源项目借鉴

高匹配度项目逐一借鉴：

| 项目 | 匹配度 | 借鉴价值 |
|------|--------|----------|
| EIA报告系统 | 96% | 任务驱动工作流 |
| 内置LLM方案 | 93% | nanoGPT+增量学习 |
| AnyDoc通用文档 | 92% | 通用引擎+领域插件 |
| 渐进式UI范式 | 82% | 会话式+渐进渲染 |
| cognee记忆 | 80% | remember/recall/forget/improve |

---

## 文档导航

| 文档 | 用途 |
|------|------|
| [架构指南](./docs/LIVINGTREE_ARCHITECTURE_GUIDE.md) | 核心架构、自我进化、开源借鉴 |
| [开发指南](./docs/LIVINGTREE_DEVELOPMENT_GUIDE.md) | 功能开发规范 |
| [工具开发指南](./docs/统一工具层开发指南.md) | BaseTool/ToolRegistry规范 |
| [归档文档](./docs/_archive/) | 历史文档、详细分析 |

---

## License

MIT License

---

*LivingTree AI - 让智能体像生命一样进化* 🌱
