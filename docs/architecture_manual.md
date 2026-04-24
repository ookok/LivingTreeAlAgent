# LivingTree AI Agent - 架构手册

> 本手册详细介绍 LivingTree AI Agent 的系统架构、核心模块和设计模式。

---

## 目录

1. [系统概览](#1-系统概览)
2. [三层架构](#2-三层架构)
3. [核心模块](#3-核心模块)
4. [模型分层](#4-模型分层)
5. [数据流设计](#5-数据流设计)
6. [扩展机制](#6-扩展机制)

---

## 1. 系统概览

LivingTree AI Agent 是一个基于 PyQt6 的智能代理开发平台，核心特性：

- **多模型分层调用**：L0-L4 四层模型分工协作
- **技能进化系统**：技能自动固化、合并、分裂、遗忘
- **知识图谱**：实体关系管理与语义检索
- **数字分身**：AI 驱动的虚拟形象系统
- **P2P 存储**：去中心化的企业级存储方案

### 技术栈

| 层级 | 技术 |
|------|------|
| 桌面框架 | PyQt6 6.0+ |
| 编程语言 | Python 3.11+ |
| 本地 LLM | Ollama + GGUF 模型 |
| 数据库 | SQLite (会话/记忆) |
| 向量检索 | Chroma / FAISS |

---

## 2. 三层架构

项目采用三层架构设计，清晰的关注点分离：

```
┌─────────────────────────────────────────────────────────────┐
│                    client/src/                               │
├─────────────────────────────────────────────────────────────┤
│  presentation/          │ 表现层 (UI)                       │
│    ├── panels/          │   - 功能面板 (WorkspacePanel 等)   │
│    ├── components/      │   - 可复用组件                     │
│    └── widgets/         │   - 独立小部件                     │
├─────────────────────────────────────────────────────────────┤
│  business/              │ 业务逻辑层                         │
│    ├── hermes_agent/    │   - 代理框架                       │
│    ├── fusion_rag/      │   - 多源检索                       │
│    ├── knowledge_graph/  │   - 知识图谱                       │
│    ├── skill_evolution/ │   - 技能进化                       │
│    └── ...              │   - 其他业务模块                   │
├─────────────────────────────────────────────────────────────┤
│  infrastructure/        │ 基础设施层                         │
│    ├── database/        │   - 数据库 (v1-v14 迁移)           │
│    ├── config/          │   - 配置管理                       │
│    ├── model/          │   - 模型管理                       │
│    └── network/         │   - 网络通信                       │
└─────────────────────────────────────────────────────────────┘
```

### 架构原则

1. **单向依赖**：上层依赖下层，下层不关心上层
2. **接口隔离**：通过抽象接口解耦
3. **开闭原则**：对扩展开放，对修改关闭

---

## 3. 核心模块

### 3.1 Hermes Agent (`core/hermes_agent/`)

智能代理核心框架：

```
hermes_agent/
├── __init__.py          # 导出核心类
├── agent.py             # AIAgent 对话循环
├── ollama_client.py     # Ollama API 客户端
├── session_db.py        # SQLite 会话持久化
├── memory_manager.py    # 记忆管理
└── tools_*.py          # 工具集
```

**核心类**：

| 类 | 职责 |
|----|------|
| `HermesAgent` | 主代理类，管理对话循环 |
| `OllamaClient` | Ollama API 调用封装 |
| `SessionDB` | 会话持久化 |
| `MemoryManager` | 多级记忆管理 |

### 3.2 技能进化系统 (`core/skill_evolution/`)

技能生命周期管理：

```
skill_evolution/
├── agent_loop.py        # 技能进化 Agent
├── database.py          # 技能数据库
├── consolidator.py      # 技能固化器
└── merger.py            # 技能合并器
```

**技能状态**：

```
[活跃] ──→ [固化] ──→ [合并] ──→ [分裂] ──→ [遗忘]
           ↑                                     │
           └─────────────────────────────────────┘
                        (再激活)
```

### 3.3 知识图谱 (`core/knowledge_graph/`)

实体关系管理：

```
knowledge_graph/
├── graph_db.py          # 图数据库
├── entity_extractor.py  # 实体抽取
├── relation_detector.py # 关系检测
└── query_engine.py      # 查询引擎
```

### 3.4 Fusion RAG (`core/fusion_rag/`)

多源融合检索：

```
fusion_rag/
├── l4_executor.py       # L4 层执行器
├── deep_search.py       # 深度搜索
├── fusion_ranker.py     # 结果融合排序
└── query_rewriter.py   # 查询重写
```

---

## 4. 模型分层

项目采用 L0-L4 四层模型架构：

| 层级 | 模型 | 职责 | 延迟要求 |
|------|------|------|----------|
| **L0** | qwen2.5:0.5b | 意图分类、路由决策 | < 100ms |
| **L1** | qwen2.5:1.5b | 轻量推理、搜索 | < 500ms |
| **L3** | qwen3.5:4b | 深度推理、意图理解 | < 2s |
| **L4** | qwen3.5:9b | 深度生成、复杂任务 | < 5s |

### 模型配置

```python
# 远程 Ollama 服务
OLLAMA_BASE_URL = "http://www.mogoo.com.cn:8899/v1"

# 模型选择策略
MODEL_STRATEGY = {
    "routing": "L0",      # 路由决策
    "search": "L1",       # 轻量搜索
    "reasoning": "L3",    # 深度推理
    "generation": "L4",   # 复杂生成
}
```

---

## 5. 数据流设计

### 对话流程

```
用户输入
    │
    ▼
┌─────────┐
│  L0 路由 │ ───→ 意图分类
└─────────┘
    │
    ▼
┌─────────┐
│  技能匹配 │ ───→ 检索技能库
└─────────┘
    │
    ├─── (简单任务) ───→ ┌─────────┐
    │                    │  L1/L3  │ ───→ 直接响应
    │                    └─────────┘
    │
    └─── (复杂任务) ───→ ┌─────────┐
                         │  L4 生成 │ ───→ 深度处理
                         └─────────┘
                              │
                              ▼
                         ┌─────────┐
                         │ 知识图谱 │ ───→ 实体关系补充
                         └─────────┘
                              │
                              ▼
                         ┌─────────┐
                         │  记忆存储 │ ───→ 持久化
                         └─────────┘
```

### 记忆分层

```
┌──────────────────────────────────────────────┐
│                  工作记忆 (Working)            │
│         当前对话上下文 (Token 预算内)           │
├──────────────────────────────────────────────┤
│                  短期记忆 (Short-term)        │
│          近期交互记录 (最近 N 轮)              │
├──────────────────────────────────────────────┤
│                  长期记忆 (Long-term)          │
│          持久化知识 (向量数据库)              │
├──────────────────────────────────────────────┤
│                  知识图谱 (Knowledge)          │
│          结构化实体关系                      │
└──────────────────────────────────────────────┘
```

---

## 6. 扩展机制

### 6.1 工具扩展

注册新工具：

```python
from core.hermes_agent import ToolRegistry

registry = ToolRegistry()

@registry.register(
    name="my_tool",
    description="我的工具",
    category="utility"
)
async def my_tool(input: str) -> str:
    """工具实现"""
    return f"处理结果: {input}"
```

### 6.2 技能扩展

创建新技能：

```python
from core.skill_evolution import Skill

skill = Skill(
    name="我的技能",
    description="技能描述",
    trigger_patterns=["关键词1", "关键词2"],
    handler=my_handler,
    metadata={"version": "1.0.0"}
)
```

### 6.3 面板扩展

添加新的 UI 面板：

```python
from client.src.presentation.panels import QWidget

class MyPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 面板实现
```

---

## 附录

### A. 目录结构速查

```
LivingTreeAlAgent/
├── client/src/
│   ├── presentation/panels/    # 所有面板
│   ├── business/                # 业务逻辑
│   └── infrastructure/          # 基础设施
├── core/                        # 核心模块 (legacy)
├── server/relay_server/         # 中继服务
└── docs/                        # 文档
    ├── architecture_manual.md   # 本文档
    ├── developer_manual.md       # 开发手册
    └── operation_manual.md       # 操作手册
```

### B. 相关文档

- [开发手册](developer_manual.md) - 代码规范与开发指南
- [操作手册](operation_manual.md) - 日常使用指南

---

*最后更新：2026-04-24*
