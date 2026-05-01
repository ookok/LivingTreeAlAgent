# 🏗️ LivingTreeAlAgent 完整架构可视化文档

> **版本**: v2.0 | **日期**: 2026-05-01 | **状态**: ✅ 完整重构

---

## 📚 目录

1. [整体架构概览](#-整体架构概览)
2. [三层架构详解](#-三层架构详解)
3. [业务层核心模块](#-业务层核心模块)
4. [核心创新系统](#-核心创新系统)
5. [数据流与交互](#-数据流与交互)
6. [快速开发指南](#-快速开发指南)

---

## 🌐 整体架构概览

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         LivingTreeAlAgent 完整系统                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                        🖥️ 客户端 (Client)                                │  │
│  ├─────────────────────────────────────────────────────────────────────────┤  │
│  │  ┌───────────────────────────────────────────────────────────────────┐  │  │
│  │  │  🎨 表现层 (Presentation Layer)          PyQt6 / Vue3             │  │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────┐ │  │  │
│  │  │  │  Panels  │ │Components│ │ Widgets  │ │ Dialogs  │ │Modules│ │  │  │
│  │  │  │(102+文件) │ │(可复用UI) │ │(自定义控件)│ │(对话框) │ │(子模块)│ │  │  │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └───────┘ │  │  │
│  │  └───────────────────────────────────────────────────────────────────┘  │  │
│  │                              ↓ (事件总线)                                │  │
│  │  ┌───────────────────────────────────────────────────────────────────┐  │  │
│  │  │  🧠 业务层 (Business Layer)               Python / ~340+模块      │  │  │
│  │  │  ┌─────────────────────────────────────────────────────────────┐│  │  │
│  │  │  │  🎯 核心引擎组                                               ││  │  │
│  │  │  │  ├─ AmphiLoop (双向循环调度)                               ││  │  │
│  │  │  │  ├─ FusionRAG (多源融合检索)                               ││  │  │
│  │  │  │  ├─ EvoRAG (知识图谱自进化)                               ││  │  │
│  │  │  │  ├─ HermesAgent (智能体框架)                              ││  │  │
│  │  │  │  └─ FaultTolerance (容错系统)                            ││  │  │
│  │  │  └─────────────────────────────────────────────────────────────┘│  │  │
│  │  │  ┌─────────────────────────────────────────────────────────────┐│  │  │
│  │  │  │  🌐 分布式系统                                              ││  │  │
│  │  │  │  ├─ DeCommerce (去中心化电商)                              ││  │  │
│  │  │  │  ├─ CreditNetwork (信用网络)                              ││  │  │
│  │  │  │  ├─ P2P Network (P2P网络)                                  ││  │  │
│  │  │  │  ├─ RelayChain (中继链)                                    ││  │  │
│  │  │  │  └─ KnowledgeBlockchain (知识区块链)                      ││  │  │
│  │  │  └─────────────────────────────────────────────────────────────┘│  │  │
│  │  │  ┌─────────────────────────────────────────────────────────────┐│  │  │
│  │  │  │  🤖 智能模块                                              ││  │  │
│  │  │  │  ├─ DigitalTwin (数字孪生)                                ││  │  │
│  │  │  │  ├─ LivingTreeAI (生命树AI)                                ││  │  │
│  │  │  │  ├─ MultiAgent (多智能体协作)                             ││  │  │
│  │  │  │  ├─ ExpertTraining (专家训练系统)                         ││  │  │
│  │  │  │  └─ EvolutionEngine (进化引擎)                           ││  │  │
│  │  │  └─────────────────────────────────────────────────────────────┘│  │  │
│  │  │  ┌─────────────────────────────────────────────────────────────┐│  │  │
│  │  │  │  📦 基础设施组件                                          ││  │  │
│  │  │  │  ├─ ModelRouter (模型路由)                                ││  │  │
│  │  │  │  ├─ MemorySystem (记忆系统)                              ││  │  │
│  │  │  │  ├─ SkillSystem (技能系统)                               ││  │  │
│  │  │  │  ├─ KnowledgeGraph (知识图谱)                            ││  │  │
│  │  │  │  ├─ TaskOrchestrator (任务编排器)                       ││  │  │
│  │  │  │  ├─ EventBus (事件总线)                                 ││  │  │
│  │  │  │  └─ Shared (共享组件)                                    ││  │  │
│  │  │  └─────────────────────────────────────────────────────────────┘│  │  │
│  │  └───────────────────────────────────────────────────────────────────┘  │  │
│  │                              ↓ (接口层)                                  │  │
│  │  ┌───────────────────────────────────────────────────────────────────┐  │  │
│  │  │  🏗️ 基础设施层 (Infrastructure Layer)  数据库 / 网络 / 配置      │  │  │
│  │  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │  │  │
│  │  │  │  Database    │ │  Network     │ │  Config      │              │  │  │
│  │  │  │  (v1-v14迁移) │ │  (P2P/WebRTC) │ │  (Nanochat)  │              │  │  │
│  │  │  └──────────────┘ └──────────────┘ └──────────────┘              │  │  │
│  │  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │  │  │
│  │  │  │  Storage     │ │  Model       │ │  Security    │              │  │  │
│  │  │  └──────────────┘ └──────────────┘ └──────────────┘              │  │  │
│  │  └───────────────────────────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                    🌐 服务端 (Server)                                    │  │
│  ├─────────────────────────────────────────────────────────────────────────┤  │
│  │  ┌───────────────────────┐ ┌───────────────────────┐ ┌────────────────┐ │  │
│  │  │  RelayServer          │ │  TrackerServer        │ │  AppServer    │ │  │
│  │  │  (FastAPI / 中继服务) │ │  (P2P节点追踪)       │ │  (企业应用)   │ │  │
│  │  └───────────────────────┘ └───────────────────────┘ └────────────────┘ │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                  🔗 外部集成 (External Integrations)                      │  │
│  ├─────────────────────────────────────────────────────────────────────────┤  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │  │
│  │  │  Ollama  │ │OpenAI API│ │  GitHub  │ │ Browser  │ │  WebRTC  │     │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘     │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ 三层架构详解

### 1️⃣ 表现层 (Presentation Layer)

**位置**: `client/src/presentation/`

#### 📂 目录结构
```
presentation/
├── panels/              # 主面板 (102+文件)
│   ├── chat_panel.py
│   ├── ide_panel.py
│   ├── skill_panel.py
│   ├── config_panel.py
│   └── ...
├── components/          # 可复用UI组件
│   ├── cards.py
│   ├── gauges.py
│   ├── spinners.py
│   └── ...
├── widgets/            # 自定义Qt控件
├── dialogs/            # 对话框窗口
├── modules/            # 功能子模块
│   ├── a2ui/
│   ├── connector/
│   ├── forum/
│   ├── intelligence/
│   └── ...
└── frontend/           # Web前端 (Vue3)
    └── src/
        ├── components/
        ├── pages/
        └── stores/
```

#### 🎨 核心UI组件
| 组件 | 功能 | 状态 |
|------|------|------|
| ChatWindow | 聊天窗口 | ✅ |
| IDEPanel | IDE集成 | ✅ |
| SkillPanel | 技能管理 | ✅ |
| ConfigPanel | 配置管理 | ✅ |
| StatusBar | 状态栏 | ✅ |
| NotificationCenter | 通知中心 | ✅ |

---

### 2️⃣ 业务层 (Business Layer)

**位置**: `client/src/business/`

#### 📦 模块分类（12大分类）

| 分类 | 模块列表 | 核心功能 |
|------|---------|---------|
| **🎯 核心引擎** | `amphiloop/`, `fusion_rag/`, `llm_wiki/`, `fault_tolerance/` | 调度、检索、容错 |
| **🤖 智能体** | `hermes_agent/`, `agent_skills/`, `agent_workflow/`, `multi_agent/` | 智能体框架 |
| **🌐 分布式** | `decommerce/`, `p2p_*/`, `relay_chain/`, `credit_economy/` | 去中心化系统 |
| **💭 记忆知识** | `memory/`, `knowledge_graph/`, `knowledge_blockchain/`, `gbrain_memory/` | 记忆与知识 |
| **👥 数字孪生** | `digital_twin/`, `enterprise_os/`, `eia_system/` | 数字孪生体系 |
| **🌳 生命树** | `living_tree_ai/`, `living_tree/`, `evolving_community/` | 生命树AI |
| **📝 写作办公** | `smart_writing/`, `office_automation/`, `md_to_doc/` | 办公自动化 |
| **🔧 工具技能** | `tools/`, `skill_evolution/`, `skill_market/` | 工具技能系统 |
| **⚙️ 基础服务** | `model_router/`, `task_orchestrator/`, `event_bus/` | 基础设施服务 |
| **🎓 学习训练** | `learning/`, `expert_training/`, `skill_distillation/` | 学习训练系统 |
| **🚀 进化自举** | `evolution_engine/`, `self_evolution/`, `self_evolving/` | 进化引擎 |
| **📦 其他** | `provider/`, `plugin_system/`, `sandbox/`, `security/` | 通用模块 |

#### 🎯 核心引擎详细说明

##### 🌀 AmphiLoop (双向循环调度)
**位置**: `client/src/business/amphiloop/`

**核心特性**:
- ✅ 双向调度系统
- ✅ 检查点持久化
- ✅ 容错回滚机制
- ✅ 动态终止判定
- ✅ 学习优化建议

**关键文件**:
```
amphiloop/
├── __init__.py
├── amphiloop_engine.py      # 主引擎 (969行)
├── checkpoint_manager.py    # 检查点管理
└── models.py                # 数据模型
```

**使用示例**:
```python
from client.src.business.amphiloop import AmphiLoopEngine

# 初始化引擎
engine = AmphiLoopEngine()

# 创建任务
task = engine.create_task("my_task", {"data": "..."})

# 执行并监控
result = engine.execute(task)

# 获取优化建议
suggestions = engine.get_optimization_suggestions("my_task")
```

##### 🔍 FusionRAG (多源融合检索)
**位置**: `client/src/business/fusion_rag/`

**核心特性**:
- ✅ 四层混合检索 (精确缓存 → 会话缓存 → 知识库 → 数据库)
- ✅ L4感知智能路由
- ✅ 意图分类与查询转换
- ✅ 多源结果融合 (RRF算法)
- ✅ 小模型优化器
- ✅ 向量存储与重排序

**关键文件** (30+文件):
```
fusion_rag/
├── __init__.py
├── engine.py                # 主引擎
├── intent_classifier.py     # 意图分类
├── query_transformer.py     # 查询转换
├── reranker.py             # 结果重排序
├── knowledge_router.py      # 知识路由
├── fusion_engine.py        # 融合引擎
├── l4_executor.py          # L4执行器
├── vector_store.py         # 向量存储
├── exact_cache.py          # 精确缓存
├── session_cache.py        # 会话缓存
└── small_model_optimizer.py # 小模型优化
```

**架构图**:
```
用户查询
    ↓
意图分类
    ↓
智能路由
    ↓
┌─────────────────────────────────────────┐
│  Layer 1: ExactCache (毫秒级)          │
├─────────────────────────────────────────┤
│  Layer 2: SessionCache (上下文感知)    │
├─────────────────────────────────────────┤
│  Layer 3: KnowledgeBase (深度检索)     │
├─────────────────────────────────────────┤
│  Layer 4: Database (结构化数据)       │
└─────────────────────────────────────────┘
    ↓
结果融合 (RRF算法)
    ↓
小模型优化 (可选)
    ↓
返回用户
```

##### 🌱 EvoRAG (知识图谱自进化)
**位置**: `client/src/business/llm_wiki/`

**核心特性** (来自arXiv最新研究):
- ✅ 反馈驱动反向传播
- ✅ 知识图谱自进化
- ✅ 混合优先级检索
- ✅ 关系融合与抑制
- ✅ 动态恢复机制

**关键文件**:
```
llm_wiki/
├── __init__.py
├── feedback_manager.py       # 反馈管理
├── kg_self_evolver.py       # 知识图谱自进化
├── hybrid_retriever.py      # 混合检索
├── knowledge_graph_integrator_v4.py
├── models.py
└── wiki_core.py
```

**核心算法**:
```
混合优先级公式:
P(t) = (1-α)·Sr(t) + α·Sc(t)
其中:
- Sr(t): 语义相似度
- Sc(t): 贡献分数
- α: 权重系数 (0-1)

知识图谱进化步骤:
1. 计算阈值 (τ_high, τ_low)
2. 识别高贡献起始三元组
3. BFS搜索高质量路径
4. 创建捷径边 (关系融合)
5. 抑制低质量三元组
6. 动态恢复机制
```

##### 🛡️ FaultTolerance (容错系统)
**位置**: `client/src/business/fault_tolerance/`

**核心特性**:
- ✅ 五层恢复策略
- ✅ 检查点管理
- ✅ 节点故障处理
- ✅ 网络分区处理
- ✅ 恢复记录与统计

**五层恢复策略**:
```
Layer 1: 快速重试 (毫秒级)
  └─ 同一节点立即重试

Layer 2: 转移重试 (秒级)
  └─ 转移到不同节点

Layer 3: 降级重试
  └─ 降低任务要求重试

Layer 4: 检查点恢复
  └─ 从最新检查点恢复

Layer 5: 人工干预
  └─ 通知用户处理
```

**关键文件**:
```
fault_tolerance/
├── __init__.py
├── checkpoint_manager.py   # 检查点管理 (466行)
├── recovery_manager.py     # 恢复管理 (530行)
├── distributed_scheduler.py # 分布式调度
├── fault_detector.py       # 故障检测
└── models.py               # 数据模型
```

---

### 3️⃣ 基础设施层 (Infrastructure Layer)

**位置**: `client/src/infrastructure/`

#### 📂 目录结构
```
infrastructure/
├── database/              # 数据库管理
│   ├── migrations.py      # 迁移脚本 (v1-v14)
│   └── models.py
├── config/               # 配置管理
│   ├── config_manager.py
│   └── nanochat_config.py
├── network/              # 网络通信
│   ├── p2p_network.py
│   └── webrtc_adapter.py
├── model/               # 数据模型
├── storage/             # 文件存储
└── security/            # 安全模块
```

---

## 🌐 核心创新系统

### 1️⃣ DeCommerce (去中心化电商)
**位置**: `client/src/business/decommerce/`

**架构**:
```
                    [Cloud Tracker]
                    (商品目录/信令)
                          ↓
        ┌─────────────────┼─────────────────┐
        ↓                 ↓                 ↓
  [Seller Node]    [Seller Node]    [Buyer Client]
  (PC端卖家)       (手机卖家)       (PC端买家)
        ↓                 ↓                 ↓
  ┌─────────────────────────────────────────┐
  │         P2P WebRTC 连接                │
  │  (视频/AI/DataChannel)                 │
  └─────────────────────────────────────────┘
```

**核心功能**:
- ✅ 去中心化订单协议 (密码学保证)
- ✅ P2P WebRTC 通信
- ✅ 分层穿透网络 (Super Relay → Edge Relay → P2P)
- ✅ 四种原生服务类型:
  1. Remote Live View (远程实景直播)
  2. AI Computing (AI计算服务)
  3. Remote Assist (远程代操作)
  4. Knowledge Consult (知识咨询)

**关键文件**:
```
decommerce/
├── __init__.py
├── models.py               # 数据模型
├── seller_node.py         # 卖家节点
├── buyer_client.py        # 买家客户端
├── decentralized_order.py # 去中心化订单 (762行)
├── edge_relay_network.py  # 边缘中继网络 (546行)
├── audit_trail.py         # 审计追踪
├── crdt_order.py          # CRDT订单
├── payment_guard.py       # 支付守卫
└── services/             # 服务处理器
```

---

### 2️⃣ 数字孪生体系 (Digital Twin)

**子系统**:
1. **企业数字孪生** (`enterprise_os/`)
2. **用户数字孪生** (`digital_twin/`)
3. **EIA数字孪生** (`living_tree_ai/eia_system/`)

#### 🏢 企业数字孪生
**位置**: `client/src/business/living_tree_ai/enterprise_os/`

**八维架构**:
```
EnterpriseDigitalTwin
├── Identity (身份维度)
│   ├─ 统一社会信用代码
│   ├─ 公司名称
│   └─ 资质证书
├── Physical (物理资产)
├── Personnel (人员信息)
├── Business (业务流程)
├── Assets (资产信息)
├── Compliance (合规义务)
├── OperationalData (运营数据)
└── Risks (风险信息)
```

**关键文件**:
```
enterprise_os/
├── __init__.py
├── enterprise_digital_twin.py  # 数字孪生核心 (365行)
├── enterprise_os_controller.py # 控制器 (581行)
└── models.py
```

---

### 3️⃣ 知识区块链 (Knowledge Blockchain)
**位置**: `client/src/business/knowledge_blockchain/`

**代币经济体系**:
| 代币 | 用途 | 分配比例 |
|------|------|---------|
| KNC | 知识创造 | 30% |
| RPC | 知识验证 | 20% |
| CNC | 知识传播 | 15% |
| LNC | 知识学习 | 15% |
| GNC | 生态治理 | 10% |
| 系统预留 | - | 10% |

**激励机制**:
- 知识创建激励
- 知识验证激励
- 知识传播激励
- 知识学习激励
- 教学激励

---

### 4️⃣ 长任务管理系统 (Long Task)
**位置**: `client/src/business/long_task/`

**核心能力**:
- ✅ 流式处理 (超长文本处理)
- ✅ 智能去重 (内容和语义级去重)
- ✅ 进程隔离 (进程级隔离 + 看门狗)
- ✅ 断点恢复 (检查点机制)

**关键文件**:
```
long_task/
├── __init__.py
├── stream_processor.py      # 流式处理
├── smart_deduplication.py  # 智能去重
├── process_isolation.py    # 进程隔离
└── integration.py          # 集成层 (482行)
```

---

## 🔄 数据流与交互

### 完整请求流程
```
用户输入
    ↓
[Presentation Layer]
    │ UI事件
    ↓
[Event Bus] 事件总线
    ↓
[Task Orchestrator] 任务编排器
    ↓
┌─────────────────────────────────────────┐
│  智能路由决策                          │
├─────────────────────────────────────────┤
│  ├─ ModelRouter → LLM模型             │
│  ├─ SkillSystem → 工具执行           │
│  ├─ MemorySystem → 知识检索          │
│  ├─ FusionRAG → 多源检索            │
│  └─ AgentSystem → 智能体协作         │
└─────────────────────────────────────────┘
    ↓
[Result Aggregation] 结果聚合
    ↓
[UI更新] → 用户
```

### 模块交互图
```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │  Chat    │ │  IDE     │ │  Skill   │ │  Config  │     │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘     │
└───────┼─────────────┼─────────────┼─────────────┼───────────┘
        ↓             ↓             ↓             ↓
┌─────────────────────────────────────────────────────────────┐
│                      Event Bus                              │
└───────┬─────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────┐
│                    Business Layer                           │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Task Orchestrator                                   │ │
│  └───────────────────────────────────────────────────────┘ │
│                          ↓                                  │
│  ┌──────────────────┐ ┌──────────────────┐ ┌─────────────┐ │
│  │  Agent Manager  │ │  Model Router    │ │ Memory Sys  │ │
│  └──────────────────┘ └──────────────────┘ └─────────────┘ │
│                          ↓                                  │
│  ┌──────────────────┐ ┌──────────────────┐ ┌─────────────┐ │
│  │  Skill System   │ │  FusionRAG       │ │ Knowledge   │ │
│  └──────────────────┘ └──────────────────┘ └─────────────┘ │
└───────┬─────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────┐
│                Infrastructure Layer                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │  Database    │ │  Network     │ │  Config      │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开发指南

### 📁 创建新业务模块

**标准结构**:
```
client/src/business/my_new_module/
├── __init__.py          # 模块入口
├── models.py            # 数据模型
├── manager.py           # 管理器
├── core.py              # 核心逻辑
└── utils.py             # 工具函数
```

**`__init__.py` 模板**:
```python
"""
我的新模块
功能描述: 这里写模块功能
"""

from .manager import MyNewManager
from .models import MyDataModel

__all__ = ['MyNewManager', 'MyDataModel']
```

**导入路径**:
```python
# ✅ 正确
from client.src.business.my_new_module import MyNewManager

# ❌ 错误 (已废弃)
from core.my_new_module import MyNewManager
```

---

### 🎨 创建新UI面板

**位置**: `client/src/presentation/panels/`

**模板**:
```python
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

class MyNewPanel(QWidget):
    """我的新面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("新面板"))
        
        btn = QPushButton("点击我")
        btn.clicked.connect(self._on_click)
        layout.addWidget(btn)
    
    def _on_click(self):
        pass
```

---

### 📊 数据库迁移

**位置**: `client/src/infrastructure/database/migrations.py`

**添加新版本**:
```python
@register_migration(15, "add_my_feature", "添加我的功能")
def migrate_v15(conn):
    """添加新表"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS my_table (
            id TEXT PRIMARY KEY,
            name TEXT,
            data JSON,
            created_at REAL DEFAULT (julianday('now'))
        )
    """)
```

---

### 🔧 配置管理

**新系统**: `nanochat_config.py` (推荐)
```python
from client.src.business.nanochat_config import config

url = config.ollama.url
timeout = config.timeouts.default
```

**兼容系统**: `config.py` (保留)
```python
from client.src.business.config import UnifiedConfig

config = UnifiedConfig.get_instance()
url = config.get("endpoints.ollama.url")
```

---

## 📈 项目统计

| 指标 | 数值 |
|------|------|
| 总文件数 | ~3400+ |
| 业务模块数 | ~340+ |
| 代码行数 | ~100K+ |
| UI面板数 | 102+ |
| 数据库版本 | v1-v14 |
| 核心系统数 | 12+ |

---

## 📚 相关文档

- [ARCHITECTURE.md](ARCHITECTURE.md) - 原始架构文档
- [AGENTS.md](AGENTS.md) - 智能体系统文档
- [LLM_Wiki_集成分析报告.md](LLM_Wiki_集成分析报告.md) - EvoRAG集成报告
- [docs/](docs/) - 更多文档

---

## 🎯 总结

LivingTreeAlAgent 是一个**AI原生的分布式操作系统级平台**，具有以下特点:

1. ✅ **清晰的三层架构** - 表示层/业务层/基础设施层
2. ✅ **丰富的创新系统** - AmphiLoop/FusionRAG/EvoRAG/DigitalTwin
3. ✅ **完整的分布式体系** - DeCommerce/P2P/区块链
4. ✅ **强大的容错能力** - 五层恢复策略/检查点机制
5. ✅ **丰富的模块生态** - 340+业务模块/102+UI面板

**开发原则**:
- 📍 所有新代码 → `client/src/business/` 或 `client/src/presentation/`
- 📍 使用新的导入路径 → `from client.src.business.xxx import yyy`
- 📍 使用NanochatConfig配置系统
- 📍 遵循现有代码风格和架构模式

---

**文档维护**: LivingTreeAlAgent Team  
**最后更新**: 2026-05-01
