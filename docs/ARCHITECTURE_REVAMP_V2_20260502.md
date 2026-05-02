# LivingTree AI Agent — 1.0 版本架构重构升级方案

> **文档版本**: v2.0  
> **日期**: 2026-05-02  
> **目标**: 从任务链与数字生命体视角，彻底重构后端架构，保留前端Vue功能不变，清理冗余，夯实工程基座

---

## 目录

1. [现状诊断](#1-现状诊断)
2. [架构愿景：数字生命体的任务链模型](#2-架构愿景数字生命体的任务链模型)
3. [新架构设计](#3-新架构设计)
4. [模块整合方案](#4-模块整合方案)
5. [需删除的冗余代码清单](#5-需删除的冗余代码清单)
6. [创新设计融入](#6-创新设计融入)
7. [可观测性与错误监测](#7-可观测性与错误监测)
8. [分阶段实施路线图](#8-分阶段实施路线图)

---

## 1. 现状诊断

### 1.1 项目规模概览

| 维度 | 数据 |
|------|------|
| 总文件数 | ~3400+ |
| 业务模块文件 | ~340+ (`client/src/business/`) |
| 前端文件 | Vue (2套) + React (1套) = 3套前端 |
| 入口点 | `main.py`(根), `client/src/main.py`, `server/relay_server/main.py` 等6+个 |
| Python包 | client, server, app, packages, plugins, expert_system, learning_world, writing, mobile |
| 测试文件 | `tests/` 目录下 70+ 测试文件 |

### 1.2 核心问题：多重冗余

经过全量扫描，发现以下严重冗余问题：

#### 问题1：模型路由系统 — 9个模块互相重叠

```
model_router.py          - 基础模型路由器
model_routing.py         - 另一个模型路由逻辑
model_election.py        - 模型选举
model_switcher.py        - 模型切换器
model_manager.py         - 模型管理器
smart_ai_router.py       - 三层算力池路由（本地/边缘/云端）
linkmind_router.py       - LinkMind语义路由
model_priority_loader.py - 模型优先级加载器
global_model_router.py   - 全局模型路由器（可能已被删除）
+nanochat_config.py      - 也包含模型配置
+optimal_config.py       - 也包含模型配置
```

**诊断**: 至少4套模型路由逻辑并存，彼此之间没有统一的调度中心。`smart_ai_router.py` 是最完整的三层算力池方案，但 `HermesAgent` 并未使用它，而是用 `linkmind_router.py` + 自己的 `_init_model_client` 方法。

#### 问题2：记忆系统 — 5个模块各自为政

```
memory_manager.py        - 旧版记忆管理器
unified_memory.py        - 统一记忆接口（抽象层，定义规范）
memory/ (子目录)         - 新版记忆子系统（compat.py, mid_term.py, router.py）
cognee_memory.py         - Cognee知识图谱记忆集成
session_db.py            - 会话数据库（也算记忆存储）
```

**诊断**: `unified_memory.py` 定义了 `IMemorySystem` 抽象接口和 `MemoryRouter`，但实际没有任何模块实现了该接口。各记忆模块独立运行，没有统一查询入口。

#### 问题3：任务系统 — 6个模块功能重叠

```
task_decomposer.py       - 任务分解（含链式思考Chain-of-Thought）
task_planning.py         - 任务规划
task_router.py           - 多层递归任务分解器（TaskRouter + TaskNode）
task_queue.py            - 任务队列
enhanced_task.py         - 增强任务系统
decision_engine.py       - 决策支持系统（实际是金融投资决策系统，完全偏离）
```

**诊断**: `task_router.py` 是最完整的任务分解实现（支持3层递归、复杂度阈值），但 `task_decomposer.py` 也有Chain-of-Thought功能。两者功能重叠。`decision_engine.py` 是一个金融投资决策系统，与Agent决策无关，属于误放。

#### 问题4：插件系统 — 3套并存

```
plugin_manager.py        - 插件管理器 v1
plugin_system.py         - 插件系统 v2
plugin_framework/ (子目录) - 插件框架 v3
```

#### 问题5：技能系统 — 7个模块未串联

```
skill_clusterer.py       - 技能语义聚类（sentence-transformers + FAISS + DBSCAN）
skill_discovery.py       - 技能发现
skill_graph.py           - 技能图谱
skill_market.py          - 技能市场
skill_matcher.py         - 技能匹配
skill_updater.py         - 技能更新
skills_adapter.py        - 技能适配器
```

**诊断**: 这些技能模块在 `AgentHub` 中通过UI面板可以测试，但 `HermesAgent` 并未实际使用技能聚类结果，技能匹配未集成到Agent的任务执行流程。

#### 问题6：前端 — 3套并存

```
1. client/src/frontend/           - Vue 3 + Vite (环评智能工作台) ← 用户指定的保留前端
2. client/src/presentation/web_ui/ - Vue 3 (另一个Vue前端，含SoftwareManager/IDE等组件)
3. web/                           - React + TypeScript + Tailwind (ChatPage/KnowledgePage/SkillsPage/SettingsPage)
```

**诊断**: 用户明确要求保留Vue前端功能不变。应保留 `client/src/frontend/` 为主前端，清理其余两套。

#### 问题7：包级冗余

```
根目录散落的独立包：
- expert_system/         - 专家训练系统（未集成）
- learning_world/        - 学习世界（未集成）
- writing/               - 写作模块（可能已废弃）
- generated_clis/        - 生成的CLI工具（临时文件）
- libs/                  - 第三方库集成（opencode）
- plugins/               - 插件示例
- utils/                 - 工具脚本
```

### 1.3 架构层级现状

当前项目存在**两套并行的架构体系**：

| 体系 | 入口 | 核心类 | 状态 |
|------|------|--------|------|
| **Hermes Agent 体系** | `client/src/business/agent.py` | `HermesAgent` | **活跃** — 实际的对话循环、工具执行 |
| **Living System 体系** | `client/src/business/cell_framework/living_system.py` | `LivingSystem` | **半成品** — 定义了优美的生物隐喻，但未与实际任务执行打通 |
| **AgentHub 体系** | `client/src/business/agent_hub.py` | `AgentHub` (QWidget) | **孤立** — 是一个PyQt6监控面板，独立运行 |
| **SystemBrain 体系** | `client/src/business/system_brain.py` | `SystemBrain` | **活跃** — 管理轻量级模型下载和基础推理 |

### 1.4 当前工作流程（send_message）

以 `HermesAgent.send_message()` 为例，梳理当前任务执行流程：

```
用户输入
  │
  ├─ 1. 知识库搜索 (_search_knowledge_base)
  │     └─ KnowledgeBaseVectorStore + KnowledgeGraph
  │
  ├─ 2. 深度搜索 (_deep_search)
  │     └─ TierRouter (多源搜索)
  │
  ├─ 3. 模型路由 (_route_model)
  │     └─ LinkMindRouter
  │
  ├─ 4. 构建增强提示 (_build_enhanced_prompt)
  │     └─ 拼接知识库结果 + 搜索结果 + 已加载技能/专家
  │
  └─ 5. 对话循环 (while iteration < max_iterations)
        ├─ _build_messages → 历史消息
        ├─ _llm_chat → 流式调用LLM
        └─ _execute_tools → 工具执行
```

**问题**:
- 步骤1-4是**每次对话都执行**的同步阻塞逻辑，未做缓存或异步优化
- 工具发现(`discover_tools`)和技能匹配(`skill_matcher`)虽然有代码但**未在对话循环中使用**
- 缺乏执行前后的Hook机制，无法插入监控和自我反思

---

## 2. 架构愿景：数字生命体的任务链模型

### 2.1 核心理念

本项目是一个**数字生命体**，核心功能是：接收用户需求 → 理解意图 → 规划任务链 → 调度执行 → 反思学习 → 进化成长。

借鉴前沿理论，我们将系统设计为：

```
┌─────────────────────────────────────────────────────────────────────┐
│                     LIVING TREE — 数字生命体                          │
│                                                                      │
│   ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│   │ 感知层  │───→│ 认知层   │───→│ 规划层   │───→│ 执行层   │      │
│   │Perceive │    │Cognize   │    │ Plan     │    │ Execute  │      │
│   └─────────┘    └──────────┘    └──────────┘    └──────────┘      │
│        │              │               │               │             │
│        └──────────────┴───────┬───────┴───────────────┘             │
│                               ↓                                      │
│   ┌──────────────────────────────────────────────────────────┐     │
│   │                    反思与进化层                            │     │
│   │         Reflect → Learn → Evolve → Optimize              │     │
│   └──────────────────────────────────────────────────────────┘     │
│                               ↓                                      │
│   ┌──────────────────────────────────────────────────────────┐     │
│   │                    世界模型层                              │     │
│   │     World Model: Predict → Simulate → Verify             │     │
│   └──────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 任务链模型（TaskChain）

将 `HermesAgent.send_message()` 的线性流程重构为**任务链（TaskChain）**：

```
用户请求
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: 意图解析 (Intent Parsing)                               │
│   输入: 用户原始文本                                              │
│   输出: Intent { type, entities, complexity, priority }         │
│   涉及: 统一语义分析中心                                          │
├─────────────────────────────────────────────────────────────────┤
│ Step 2: 上下文装配 (Context Assembly)                            │
│   输入: Intent                                                   │
│   输出: Context { memory, knowledge, skills, tools }            │
│   涉及: 统一智能存储 + 统一技能匹配                               │
├─────────────────────────────────────────────────────────────────┤
│ Step 3: 任务规划 (Task Planning)                                 │
│   输入: Intent + Context                                         │
│   输出: TaskPlan { steps[], dependencies, fallbacks }           │
│   涉及: 统一任务规划器                                            │
├─────────────────────────────────────────────────────────────────┤
│ Step 4: 模型调度 (Model Dispatch)                                │
│   输入: TaskPlan                                                 │
│   输出: ModelBinding { model, backend, config }                 │
│   涉及: 统一模型调度中心                                          │
├─────────────────────────────────────────────────────────────────┤
│ Step 5: 执行循环 (Execution Loop)                                │
│   输入: TaskPlan + ModelBinding + Context                       │
│   输出: ExecutionResult { output, artifacts, metrics }         │
│   涉及: 统一工具执行器                                            │
├─────────────────────────────────────────────────────────────────┤
│ Step 6: 反思归档 (Reflection & Archive)                          │
│   输入: ExecutionResult                                          │
│   输出: LearningRecord { insights, improvements }              │
│   涉及: 自我进化引擎                                              │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 数字生命体的四大生命特征

对应生物学四大生命特征，我们设计系统的四大运行时特征：

| 生命特征 | 系统映射 | 实现 |
|----------|----------|------|
| **新陈代谢** | 任务处理流水线 | TaskChain Pipeline：持续的输入→处理→输出循环 |
| **应激性** | 事件驱动响应 | EventBus + Hook系统：系统事件触发自适应行为 |
| **生长繁殖** | 自进化与知识积累 | SelfEvolution：从历史中学习，优化策略和提示词 |
| **遗传变异** | 配置与技能继承 | SkillDNA：技能和配置可序列化、可迁移、可变异 |

---

## 3. 新架构设计

### 3.1 总体分层

```
livingtree/
├── core/                        # 核心引擎（无UI依赖）
│   ├── life_engine.py           # 生命引擎 — 总调度器
│   ├── intent/                  # 统一意图与语义分析中心
│   │   ├── parser.py            # 意图解析器
│   │   └── classifier.py        # 意图分类器
│   ├── context/                 # 上下文装配
│   │   ├── assembler.py         # 上下文装配器
│   │   └── compressor.py        # 上下文压缩器
│   ├── planning/                # 统一任务规划器
│   │   ├── decomposer.py        # 任务分解（整合Chain-of-Thought）
│   │   ├── task_node.py         # 任务节点数据结构
│   │   └── scheduler.py         # 任务调度（优先级、依赖）
│   ├── model/                   # 统一模型调度中心
│   │   ├── router.py            # 模型路由器（整合三层算力池）
│   │   ├── registry.py          # 模型注册表
│   │   └── client.py            # 统一模型客户端
│   ├── memory/                  # 统一智能存储
│   │   ├── store.py             # 统一存储接口
│   │   ├── vector_db.py         # 向量数据库
│   │   ├── graph_db.py          # 知识图谱
│   │   └── session.py           # 会话存储
│   ├── tools/                   # 统一工具系统
│   │   ├── registry.py          # 工具注册表（语义+关键词匹配）
│   │   ├── dispatcher.py        # 工具调度器
│   │   └── builtin/             # 内置工具
│   │       ├── file_tools.py
│   │       ├── terminal_tools.py
│   │       ├── web_tools.py
│   │       └── code_tools.py
│   ├── skills/                  # 统一技能系统
│   │   ├── loader.py            # 技能加载器
│   │   ├── matcher.py           # 技能匹配器（语义匹配）
│   │   └── repository.py        # 技能仓库
│   ├── plugins/                 # 统一插件系统
│   │   ├── manager.py           # 插件管理器
│   │   └── sandbox.py           # 插件沙箱
│   ├── evolution/               # 自进化引擎
│   │   ├── reflection.py        # 自我反思
│   │   ├── optimizer.py         # 策略优化
│   │   └── repairer.py          # 自动修复
│   ├── world_model/             # 世界模型（创新）
│   │   ├── predictor.py         # 状态预测
│   │   └── simulator.py         # 结果模拟
│   └── observability/           # 可观测性
│       ├── tracer.py            # 链路追踪
│       ├── metrics.py           # 指标收集
│       └── logger.py            # 结构化日志
│
├── adapters/                    # 适配器层（外部集成）
│   ├── mcp/                     # MCP协议适配
│   │   └── manager.py
│   ├── api/                     # API网关
│   │   └── gateway.py
│   └── providers/               # 第三方Provider
│       ├── ollama.py
│       ├── openai.py
│       └── vllm.py
│
├── infrastructure/              # 基础设施
│   ├── config.py                # 统一配置（整合NanochatConfig + OptimalConfig）
│   ├── database.py              # 数据库管理
│   ├── event_bus.py             # 事件总线
│   ├── websocket.py             # WebSocket服务
│   └── security.py              # 安全模块
│
├── server/                      # 服务层
│   ├── relay/                   # 中继服务（精简）
│   └── tracker/                 # P2P追踪器（精简）
│
└── frontend_bridge/             # 前端桥接层
    ├── channel.py               # QWebChannel桥接
    └── api.py                   # REST API
```

### 3.2 核心类关系

```
LifeEngine (总调度器 - 单例)
  │
  ├── IntentParser         # 意图解析
  ├── ContextAssembler     # 上下文装配
  ├── TaskPlanner          # 任务规划
  │     └── TaskNode[]     # 任务节点列表
  ├── ModelRouter          # 模型调度
  │     └── ModelRegistry  # 模型注册表
  ├── ExecutionLoop        # 执行循环
  │     ├── ToolDispatcher # 工具调度
  │     └── SkillMatcher   # 技能匹配
  ├── MemoryStore          # 统一存储
  │     ├── VectorDB
  │     ├── GraphDB
  │     └── SessionStore
  ├── EvolutionEngine      # 进化引擎
  │     ├── Reflector
  │     └── Optimizer
  ├── WorldModel           # 世界模型
  │     ├── Predictor
  │     └── Simulator
  └── ObservabilityHub     # 可观测中心
        ├── Tracer
        ├── MetricsCollector
        └── StructuredLogger
```

### 3.3 数据流（一图胜千言）

```
用户输入 "帮我写一份关于AI安全的报告"
  │
  ▼
LifeEngine.handle_request(request)
  │
  ├─ [1] IntentParser.parse("帮我写一份关于AI安全的报告")
  │     → Intent { type: WRITING, entities: [AI安全], complexity: 0.4 }
  │
  ├─ [2] ContextAssembler.assemble(intent)
  │     ├─ MemoryStore.search("AI安全")     → 3条历史记忆
  │     ├─ VectorDB.search("AI安全报告")    → 5条知识片段
  │     └─ SkillMatcher.match(intent)        → [writing_skill, research_skill]
  │     → Context { memories, knowledge, skills }
  │
  ├─ [3] TaskPlanner.plan(intent, context)
  │     ├─ Decomposer.decompose("写AI安全报告")
  │     │     → TaskNode("调研AI安全现状", depth=1)
  │     │     → TaskNode("整理关键风险点", depth=1)
  │     │     → TaskNode("撰写报告", depth=1)
  │     └─ Scheduler.schedule(tasks)
  │     → TaskPlan { steps: [...], estimated_tokens: 2000 }
  │
  ├─ [4] ModelRouter.route(task_plan)
  │     ├─ 复杂度 < 0.7 → 边缘模型 (qwen2.5:7b)
  │     └─ 成本预算允许 → 无云端调用
  │     → ModelBinding { model: "qwen2.5:7b", backend: OLLAMA }
  │
  ├─ [5] ExecutionLoop.run(task_plan, model, context)
  │     ├─ 对每个 TaskNode:
  │     │   ├─ build_prompt(task_node, context)
  │     │   ├─ llm_chat(prompt, model)
  │     │   ├─ if tool_call → ToolDispatcher.dispatch(...)
  │     │   └─ collect_result()
  │     └─ aggregate_results()
  │     → ExecutionResult { output: "报告内容...", tokens: 1500, duration: 3.2s }
  │
  └─ [6] EvolutionEngine.reflect(result)
        ├─ Reflector.analyze(result)        → 质量评分: 0.85
        ├─ Optimizer.suggest_improvements()  → 建议增加数据引用
        └─ MemoryStore.archive(result)       → 存入长期记忆
        → LearningRecord { insights: [...], score: 0.85 }
```

---

## 4. 模块整合方案

### 4.1 模型路由系统 → 整合为 `core/model/`

| 旧文件 | 处理方式 | 说明 |
|--------|----------|------|
| `smart_ai_router.py` | **保留核心逻辑** | 三层算力池（local/edge/cloud）设计最完整 |
| `model_router.py` | 合并到 `core/model/router.py` | 取其路由接口设计 |
| `model_routing.py` | 合并 | 路由算法逻辑 |
| `model_election.py` | 合并 | 选举策略 |
| `model_switcher.py` | 合并 | 动态切换逻辑 |
| `model_manager.py` | 转换为 `core/model/registry.py` | 模型发现和列表管理 |
| `linkmind_router.py` | 废弃 | 功能被smart_ai_router覆盖 |
| `model_priority_loader.py` | 合并 | 优先级加载逻辑 |
| `nanochat_config.py` | 合并到 `infrastructure/config.py` | 统一配置 |
| `optimal_config.py` | 合并到 `infrastructure/config.py` | 统一配置 |

### 4.2 记忆系统 → 整合为 `core/memory/`

| 旧文件 | 处理方式 | 说明 |
|--------|----------|------|
| `unified_memory.py` | **保留接口设计** | IMemorySystem + MemoryQuery + MemoryResult |
| `memory_manager.py` | 改造为实现类 | 实现IMemorySystem |
| `memory/` 子目录 | 合并 | compat.py/mid_term.py/router.py → store.py |
| `cognee_memory.py` | 改为可选插件 | 不强制依赖 |
| `session_db.py` | 合并到 `core/memory/session.py` | 精简 |
| `knowledge_graph.py` | 保留为 `core/memory/graph_db.py` | 作为Memory子系统 |
| `knowledge_vector_db.py` | 保留为 `core/memory/vector_db.py` | 原地重命名 |

### 4.3 任务系统 → 整合为 `core/planning/`

| 旧文件 | 处理方式 | 说明 |
|--------|----------|------|
| `task_router.py` | **保留核心** | TaskNode + TaskRouter 设计最完整 |
| `task_decomposer.py` | 合并Chain-of-Thought逻辑 | 取其CoT提示词生成 |
| `task_planning.py` | 转换为 `scheduler.py` | 取调度+优先级逻辑 |
| `task_queue.py` | 合并到scheduler | 队列管理 |
| `enhanced_task.py` | 废弃 | 功能被TaskRouter覆盖 |
| `decision_engine.py` | **完全删除** | 这是金融投资决策系统，与Agent无关 |

### 4.4 插件系统 → 整合为 `core/plugins/`

| 旧文件 | 处理方式 | 说明 |
|--------|----------|------|
| `plugin_framework/` | **保留为基座** | 目录结构最完整 |
| `plugin_manager.py` | 合并 | 取其管理接口 |
| `plugin_system.py` | 合并 | 取系统级能力 |

### 4.5 技能系统 → 整合为 `core/skills/`

| 旧文件 | 处理方式 | 说明 |
|--------|----------|------|
| `skill_matcher.py` | **保留核心** | 语义匹配是核心能力 |
| `skill_clusterer.py` | 合并 | 聚类能力作为matcher的增强 |
| `skill_discovery.py` | 合并到loader | 发现=自动加载 |
| `skill_graph.py` | 废弃 | 知识图谱已覆盖此功能 |
| `skill_market.py` | 废弃 | 未集成且非核心 |
| `skill_updater.py` | 合并到loader | 热更新能力 |
| `skills_adapter.py` | 废弃 | 统一入口已替代 |

### 4.6 前端 → 保留 `client/src/frontend/`

| 目录 | 处理方式 | 说明 |
|------|----------|------|
| `client/src/frontend/` | **保留不动** | 用户指定的Vue前端 |
| `client/src/presentation/web_ui/` | 删除 | 第二套Vue前端，冗余 |
| `web/` | 删除 | React前端，冗余 |
| `client/src/presentation/` | 精简 | 仅保留QWebChannel桥接逻辑 |
| `server/web/` | 删除 | 独立的Web服务器，冗余 |

### 4.7 包的整合

| 包/目录 | 处理方式 |
|----------|----------|
| `expert_system/` | 核心逻辑合并到 `core/skills/` |
| `learning_world/` | 核心逻辑合并到 `core/evolution/` |
| `writing/` | 核心逻辑合并到 `core/tools/builtin/` |
| `generated_clis/` | 删除（临时文件） |
| `libs/` | 评估后保留需要的，删除冗余 |
| `plugins/` | 移至 `core/plugins/` 的示例目录 |
| `utils/` | 合并到 `scripts/` |
| `packages/` | 保留 `living_tree_naming/`，`shared/` 合并到 core |
| `mobile/` | 保留但标记为 `experimental/` |
| `static/` | 保留 `ai-detector/` 等有用静态资源 |
| `locales/` | 保留国际化资源 |
| `localresources/` | 整理或删除 |

---

## 5. 需删除的冗余代码清单

### 5.1 可直接删除的文件/目录

| 路径 | 原因 |
|------|------|
| `client/src/presentation/web_ui/` | 第二套Vue前端，与保留的前端重复 |
| `web/` | React前端，与保留的前端重复 |
| `server/web/` | 独立Web服务器，冗余 |
| `client/src/business/decision_engine.py` | 金融投资决策系统，与Agent无关 |
| `client/src/business/cost_manager.py` | 功能被smart_ai_router的CostBudget覆盖 |
| `client/src/business/company_stamp.py` | 特定业务印章功能，非核心 |
| `client/src/business/pdf_stamp.py` | 特定业务印章功能，非核心 |
| `client/src/business/gov_data_query.py` | 特定业务查询，非核心 |
| `client/src/business/skill_market.py` | 未集成，市场功能非核心 |
| `client/src/business/skill_graph.py` | 被knowledge_graph覆盖 |
| `generated_clis/` | 临时生成的CLI工具 |
| `libs/opencode_integration/` | 如未集成则删除 |
| `root test_*.py` 文件 (~80个) | 散落在根目录的临时测试文件 |
| `client/src/business/wechat_tool.py` | 特定平台工具 |
| `client/src/business/wecom_tool.py` | 特定平台工具 |
| `client/src/business/mobile_adapter.py` | 移动端未上线，暂删 |
| `client/src/business/vheer_client.py` | 未知外部客户端 |
| `client/src/business/toonflow_client.py` | 未知外部客户端 |
| `client/src/business/toonflow_runner.py` | 未知外部客户端 |

### 5.2 需合并后删除的文件

| 文件 | 合并到 |
|------|--------|
| `model_routing.py` | → `core/model/router.py` |
| `model_election.py` | → `core/model/router.py` |
| `model_switcher.py` | → `core/model/router.py` |
| `linkmind_router.py` | → `core/model/router.py` |
| `model_priority_loader.py` | → `core/model/router.py` |
| `nanochat_config.py` | → `infrastructure/config.py` |
| `optimal_config.py` | → `infrastructure/config.py` |
| `plugin_system.py` | → `core/plugins/manager.py` |
| `plugin_manager.py` | → `core/plugins/manager.py` |
| `skill_discovery.py` | → `core/skills/loader.py` |
| `skill_updater.py` | → `core/skills/loader.py` |
| `skill_clusterer.py` | → `core/skills/matcher.py` |
| `skills_adapter.py` | → `core/skills/matcher.py` |
| `task_decomposer.py` | → `core/planning/decomposer.py` |
| `task_planning.py` | → `core/planning/scheduler.py` |
| `task_queue.py` | → `core/planning/scheduler.py` |
| `enhanced_task.py` | → `core/planning/`（取有用逻辑） |
| `memory_manager.py` | → `core/memory/store.py` |
| `memory/` | → `core/memory/` |

---

## 6. 创新设计融入

### 6.1 世界模型（World Model）— Next-State Prediction

借鉴前沿的"从预测下一个token转向预测世界下一状态"理念：

```python
# core/world_model/predictor.py

class StatePredictor:
    """
    世界模型预测器
    
    不预测文本，而是预测"执行某操作后世界的状态变化"
    例如：执行"删除文件X" → 预测：磁盘空间增加Y MB，文件X不可用
    """
    
    def predict_outcome(self, action: Action, current_state: WorldState) -> PredictedState:
        """
        在脑内预演行动后果
        
        Args:
            action: 待执行的操作
            current_state: 当前世界状态（文件系统、系统资源、用户上下文等）
        
        Returns:
            PredictedState with confidence intervals
        """
        pass
    
    def verify_prediction(self, predicted: PredictedState, actual: WorldState) -> float:
        """
        验证预测准确性，用于模型自我校正
        Returns: 预测误差分数
        """
        pass
```

### 6.2 Harness 架构 — 动态上下文压缩

将经验沉淀为代码，实现长时运行Token消耗骤降：

```python
# core/evolution/harness.py

class HarnessManager:
    """
    驾驭系统
    
    核心理念：
    1. 将重复出现的上下文模式压缩为可复用的"经验代码"
    2. 动态管理Agent的上下文窗口
    3. 将高频模式固化为系统级技能
    """
    
    def compress_pattern(self, pattern: ContextPattern) -> str:
        """将上下文模式压缩为可执行代码片段"""
        pass
    
    def apply_experience(self, task: Task) -> ContextInjection:
        """匹配并注入相关经验到当前任务的上下文"""
        pass
    
    def prune_context(self, messages: List[Message]) -> List[Message]:
        """智能裁剪上下文，保留关键信息"""
        pass
```

### 6.3 细胞AI架构 — 专业化细胞分工

保留并完善现有 `cell_framework/` 的设计：

```python
# core/life_engine.py

class LifeEngine:
    """
    生命引擎 — 细胞的中央调度
    
    五种核心细胞：
    - PerceptionCell: 感知用户输入和环境变化
    - ReasoningCell: 逻辑推理和决策
    - MemoryCell: 记忆存取和知识管理
    - LearningCell: 从经验中学习
    - ActionCell: 执行具体操作
    """
    
    def __init__(self):
        self.cells = {
            'perception': PerceptionCell(),
            'reasoning': ReasoningCell(),
            'memory': MemoryCell(),
            'learning': LearningCell(),
            'action': ActionCell(),
        }
    
    async def process(self, stimulus: Stimulus) -> Response:
        """
        细胞协作处理流程：
        Perception → Memory(检索) → Reasoning → Action → Memory(存储) → Learning
        """
        pass
```

### 6.4 智能体自进化 — 反思→学习→进化闭环

```python
# core/evolution/engine.py

class EvolutionEngine:
    """
    自进化引擎
    
    闭环:
    1. REFLECT: 分析最近N次任务执行的质量
    2. IDENTIFY: 识别可改进的模式
    3. EXPERIMENT: 生成改进方案（新的提示词、参数、策略）
    4. VALIDATE: A/B测试验证改进效果
    5. ADOPT: 将验证通过的改进固化为新基线
    """
    
    def reflect_on_batch(self, results: List[ExecutionResult]) -> ReflectionReport:
        """批量反思分析"""
        pass
    
    def propose_improvement(self, report: ReflectionReport) -> ImprovementProposal:
        """生成改进建议"""
        pass
    
    def validate_improvement(self, proposal: ImprovementProposal) -> ValidationResult:
        """验证改进效果"""
        pass
```

### 6.5 统一全模态感知

```python
# core/intent/parser.py

class MultimodalIntentParser:
    """
    统一多模态意图解析
    
    不区分文本/图像/语音，统一解析为结构化Intent
    """
    def parse(self, input: Union[str, Image, Audio]) -> Intent:
        pass
```

---

## 7. 可观测性与错误监测

### 7.1 结构化日志系统

```python
# core/observability/logger.py

class StructuredLogger:
    """
    结构化日志
    
    每条日志包含：
    - trace_id: 全链路追踪ID
    - span_id: 当前操作跨度ID
    - timestamp: 时间戳
    - level: INFO/WARN/ERROR/FATAL
    - module: 来源模块
    - action: 操作名称
    - input_summary: 输入摘要（脱敏后）
    - output_summary: 输出摘要
    - duration_ms: 耗时
    - tokens_used: Token消耗
    - error: 错误详情
    - metadata: 扩展字段
    """
    pass
```

### 7.2 链路追踪

```python
# core/observability/tracer.py

class RequestTracer:
    """
    分布式链路追踪
    
    追踪一个用户请求从进入到完成的全链路
    """
    def start_trace(self, request_id: str) -> TraceContext: ...
    def start_span(self, name: str, parent: Span = None) -> Span: ...
    def end_span(self, span: Span, result: Any = None): ...
    def end_trace(self, context: TraceContext): ...
```

### 7.3 健康监控

```python
# core/observability/metrics.py

class HealthMonitor:
    """
    系统健康监控
    
    指标维度：
    - 请求量 (QPS)
    - 成功率 / 失败率
    - P50/P95/P99 延迟
    - Token消耗速率
    - 内存/CPU/GPU使用率
    - 模型调用失败次数
    - 工具执行失败次数
    - 自我修复尝试次数及成功率
    """
    pass
```

### 7.4 错误分级与自动恢复

```python
class ErrorClassifier:
    """错误分级"""
    RETRYABLE = "retryable"       # 可重试（网络超时等）
    DEGRADABLE = "degradable"     # 可降级（换用备选模型）
    FATAL = "fatal"               # 致命错误（配置错误等）
    IGNORABLE = "ignorable"       # 可忽略（非关键警告）

class AutoRecovery:
    """自动恢复策略"""
    def handle(self, error: ClassifiedError) -> RecoveryAction:
        if error.level == RETRYABLE:
            return RetryAction(max_retries=3, backoff=exponential)
        elif error.level == DEGRADABLE:
            return DegradeAction(fallback_model="qwen2.5:0.5b")
        elif error.level == FATAL:
            return AlertAction(message="需人工干预")
```

---

## 8. 分阶段实施路线图

### 阶段0：清理准备（1-2天）

- [ ] 全量备份当前代码
- [ ] 删除明确冗余的目录/文件（见第5章清单）
- [ ] 删除根目录散落的80+临时 `test_*.py` 文件
- [ ] 整理 `tests/` 目录，仅保留有效的测试文件
- [ ] 确认 `client/src/frontend/` Vue前端完整可构建

### 阶段1：核心引擎搭建（3-5天）

- [ ] 创建新目录结构：`livingtree/core/`, `livingtree/adapters/`, `livingtree/infrastructure/`, `livingtree/server/`, `livingtree/frontend_bridge/`
- [ ] 实现 `infrastructure/config.py` — 统一配置（合并NanochatConfig + OptimalConfig + UnifiedConfig）
- [ ] 实现 `infrastructure/event_bus.py` — 事件总线
- [ ] 实现 `core/observability/` — 可观测性基础（logger, tracer, metrics）
- [ ] 实现 `core/life_engine.py` — 生命引擎骨架

### 阶段2：四大统一中心（5-7天）

**统一模型调度中心** (`core/model/`):
- [ ] 整合 `smart_ai_router.py` 三层算力池为核心
- [ ] 合并其他模型路由模块
- [ ] 实现 `ModelRouter.route()` 统一入口

**统一意图与语义分析中心** (`core/intent/`):
- [ ] 实现 `IntentParser` 和 `IntentClassifier`
- [ ] 支持多轮对话意图跟踪

**统一智能模块匹配** (`core/skills/`):
- [ ] 整合 `skill_matcher.py` 语义匹配
- [ ] 连接 `core/intent/` → `core/skills/` 自动匹配

**统一智能存储** (`core/memory/`):
- [ ] 基于 `unified_memory.py` 接口实现 `MemoryStore`
- [ ] 适配 `VectorDB` + `GraphDB` + `SessionStore`

### 阶段3：任务链实现（4-6天）

- [ ] 实现 `core/planning/` — TaskNode + Decomposer + Scheduler
- [ ] 实现 `core/context/` — ContextAssembler + Compressor
- [ ] 实现 `core/tools/` — 统一工具注册与调度
- [ ] 实现 `ExecutionLoop` — 对话循环+工具调用
- [ ] 打通完整任务链: Intent → Context → Plan → Model → Execute → Reflect

### 阶段4：自进化体系（3-4天）

- [ ] 实现 `core/evolution/engine.py` — 进化引擎
- [ ] 实现 `Reflector` + `Optimizer` + `Repairer`
- [ ] 实现 `HarnessManager` — 上下文压缩与经验固化
- [ ] 连接进化引擎到任务链的Reflect步骤

### 阶段5：创新层与前端桥接（3-5天）

- [ ] 实现 `core/world_model/` — 状态预测与模拟
- [ ] 实现 `adapters/mcp/` — MCP协议适配
- [ ] 实现 `adapters/api/gateway.py` — API网关
- [ ] 实现 `frontend_bridge/channel.py` — QWebChannel桥接（连接Vue前端）
- [ ] 实现 `frontend_bridge/api.py` — REST API

### 阶段6：集成验证与清理（2-3天）

- [ ] 将现有Vue前端连接到新后端 `frontend_bridge/`
- [ ] 端到端测试：用户输入 → 完整任务链 → 前端展示
- [ ] 可观测性验证：链路追踪、指标收集、日志
- [ ] 性能基准测试
- [ ] 清理旧 `client/src/business/` 中已被迁移的代码
- [ ] 更新 `AGENTS.md` 和 `README.md`

### 阶段7：服务层精简（2-3天）

- [ ] 精简 `server/relay_server/` 到 `livingtree/server/relay/`
- [ ] 精简 `server/tracker_server.py` 到 `livingtree/server/tracker/`
- [ ] 评估 `app/` 是否需要保留

---

## 附录A：模块迁移映射表

| 旧路径 | 新路径 | 状态 |
|--------|--------|------|
| `client/src/business/agent.py` → HermesAgent | `livingtree/core/life_engine.py` + `execution_loop.py` | 重构 |
| `client/src/business/smart_ai_router.py` | `livingtree/core/model/router.py` | 迁移+增强 |
| `client/src/business/unified_memory.py` | `livingtree/core/memory/store.py` | 保留接口 |
| `client/src/business/task_router.py` | `livingtree/core/planning/` | 迁移 |
| `client/src/business/skill_matcher.py` | `livingtree/core/skills/matcher.py` | 迁移 |
| `client/src/business/tools_registry.py` | `livingtree/core/tools/registry.py` | 迁移 |
| `client/src/business/self_evolution.py` | `livingtree/core/evolution/` | 迁移+增强 |
| `client/src/business/knowledge_graph.py` | `livingtree/core/memory/graph_db.py` | 迁移 |
| `client/src/business/plugin_framework/` | `livingtree/core/plugins/` | 迁移 |
| `client/src/business/mcp_manager.py` | `livingtree/adapters/mcp/manager.py` | 迁移 |
| `client/src/business/nanochat_config.py` | `livingtree/infrastructure/config.py` | 合并 |
| `client/src/business/cell_framework/` | `livingtree/core/` (分散到各cell) | 重构 |
| `client/src/frontend/` | 保留不动 | 保留 |
| `client/src/presentation/main_window.py` | `livingtree/frontend_bridge/` | 精简 |

---

## 附录B：保留的能力清单

重构后必须保留的现有能力：

| 能力 | 来源模块 | 保障方式 |
|------|----------|----------|
| 对话循环 + 流式输出 | `HermesAgent.send_message()` | 迁移到 `ExecutionLoop` |
| 工具注册与调度 | `ToolRegistry` + `ToolDispatcher` | 迁移到 `core/tools/` |
| 三层算力池路由 | `smart_ai_router.py` | 迁移到 `core/model/router.py` |
| 向量知识库搜索 | `KnowledgeBaseVectorStore` | 迁移到 `core/memory/vector_db.py` |
| 知识图谱 | `KnowledgeGraph` | 迁移到 `core/memory/graph_db.py` |
| 深度多源搜索 | `TierRouter` | 迁移到 `core/tools/builtin/web_tools.py` |
| 会话统计 | `SessionStats` + `SessionStatsTracker` | 迁移到 `core/observability/metrics.py` |
| Opik追踪 | `opik_tracer.py` | 迁移到 `core/observability/tracer.py` |
| 任务分解 | `TaskRouter` + `TaskNode` | 迁移到 `core/planning/` |
| 自进化引擎 | `SelfReflectionEngine` + `ToolSelfRepairer` | 迁移到 `core/evolution/` |
| 工具链编排 | `ToolChainOrchestrator` | 迁移到 `core/planning/scheduler.py` |
| 技能系统 | `skill_matcher.py` | 迁移到 `core/skills/` |
| MCP协议 | `mcp_manager.py` | 迁移到 `adapters/mcp/` |
| 插件框架 | `plugin_framework/` | 迁移到 `core/plugins/` |
| 系统大脑(模型管理) | `system_brain.py` | 迁移到 `core/model/registry.py` |
| 内容生成与动态UI | `web_channel_backend.py` | 迁移到 `frontend_bridge/` |

---

> **改造原则**
> 1. 前端Vue功能100%保持不变
> 2. 不考虑向下兼容 — 这是1.0版本，从未上线
> 3. 所有模块统一入口，消除重复
> 4. 可观测性一等公民 — 每个模块都有trace/log/metrics
> 5. 错误健壮 — 分级处理 + 自动降级 + 自我修复
> 6. 创新融入 — 世界模型 + Harness + 细胞AI + 自进化
