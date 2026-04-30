# 🏗️ LivingTreeAI 系统架构设计文档

> **版本**: v1.0.0  
> **状态**: 全面测试阶段  
> **最后更新**: 2026-04-30

---

## 📋 目录

1. [架构概述](#1-架构概述)
2. [核心架构原则](#2-核心架构原则)
3. [三层架构设计](#3-三层架构设计)
4. [核心模块详解](#4-核心模块详解)
5. [数据流与交互](#5-数据流与交互)
6. [数据库设计](#6-数据库设计)
7. [API 设计](#7-api-设计)
8. [部署架构](#8-部署架构)
9. [安全架构](#9-安全架构)

---

## 1. 架构概述

LivingTreeAI 采用**清晰的三层架构**设计，将业务逻辑、数据访问和用户界面分离，实现高内聚低耦合的软件设计目标。

### 1.1 架构风格

- **集成式单体应用 (Integrated Monolith)**: 所有核心功能集成在一个应用中，便于部署和维护
- **插件化架构**: 支持动态加载插件和技能扩展
- **事件驱动**: 通过事件总线实现模块间解耦
- **微内核架构**: 核心框架 + 可扩展插件

### 1.2 设计理念

```
┌─────────────────────────────────────────────────────────────┐
│                    用户层 (User Layer)                      │
├─────────────────────────────────────────────────────────────┤
│   Presentation Layer (表示层) - PyQt6 UI                   │
├─────────────────────────────────────────────────────────────┤
│   Business Layer (业务层) - Python 业务逻辑                 │
├─────────────────────────────────────────────────────────────┤
│   Infrastructure Layer (基础设施层) - DB/Network           │
├─────────────────────────────────────────────────────────────┤
│                      外部服务层                            │
│   Ollama │ PostgreSQL │ Redis │ P2P Network │ Web API      │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 核心架构原则

| 原则 | 说明 |
|-----|------|
| **单一职责** | 每个模块只负责一个功能领域 |
| **依赖倒置** | 高层模块不依赖低层模块，都依赖抽象 |
| **接口隔离** | 使用细粒度接口，避免不必要的依赖 |
| **开闭原则** | 对扩展开放，对修改关闭 |
| **里氏替换** | 子类可以替换父类而不影响功能 |
| **迪米特法则** | 每个模块只与直接朋友通信 |

---

## 3. 三层架构设计

### 3.1 Presentation Layer (表示层)

**职责**: UI 展示、用户交互、视图管理

**位置**: `client/src/presentation/`

**子模块**:

| 模块 | 职责 | 文件数 |
|-----|------|-------|
| `panels/` | 主面板组件 | ~102+ |
| `components/` | 可复用 UI 组件 | ~50+ |
| `widgets/` | 自定义 Qt 部件 | ~30+ |
| `dialogs/` | 对话框窗口 | ~20+ |
| `modules/` | 功能子模块 | ~10+ |

**核心组件**:

- **ChatWindow**: 聊天窗口组件
- **IDEPanel**: IDE 集成面板
- **SkillPanel**: 技能管理面板
- **ConfigPanel**: 配置面板
- **StatusBar**: 状态栏
- **NotificationCenter**: 通知中心

### 3.2 Business Layer (业务层)

**职责**: 业务逻辑处理、智能体管理、任务编排

**位置**: `client/src/business/`

**子模块**:

| 模块 | 职责 | 文件数 |
|-----|------|-------|
| `hermes_agent/` | 智能体框架 | ~50+ |
| `fusion_rag/` | 多源检索增强生成 | ~30+ |
| `knowledge_graph/` | 知识图谱 | ~20+ |
| `amphiloop/` | 双向调度引擎 | ~20+ |
| `optimization/` | PRISM 优化 | ~15+ |
| `enterprise/` | P2P 存储 | ~20+ |
| `digital_twin/` | 数字孪生 | ~15+ |
| `credit_economy/` | 信用经济 | ~15+ |
| `decommerce/` | 电子商务 | ~10+ |
| `living_tree_ai/` | 核心 AI 能力 | ~300+ |

**核心服务**:

| 服务 | 职责 | 文件 |
|-----|------|------|
| **AgentManager** | 智能体生命周期管理 | `agent_registry.py` |
| **ModelRouter** | LLM 模型路由 | `model_router.py` |
| **MemorySystem** | 记忆系统 | `memory_manager.py` |
| **SkillSystem** | 技能管理 | `skill_manager.py` |
| **TaskOrchestrator** | 任务编排 | `task_orchestrator.py` |
| **KnowledgeGraph** | 知识图谱管理 | `knowledge_graph.py` |
| **RAGEngine** | 检索增强生成 | `fusion_rag/` |
| **EventBus** | 事件总线 | `event_bus.py` |

### 3.3 Infrastructure Layer (基础设施层)

**职责**: 数据存储、网络通信、配置管理

**位置**: `client/src/infrastructure/`

**子模块**:

| 模块 | 职责 |
|-----|------|
| `database/` | 数据库管理与迁移 (v1-v14) |
| `config/` | 配置管理 |
| `network/` | 网络通信 |
| `model/` | 数据模型定义 |
| `storage/` | 文件存储 |

---

## 4. 核心模块详解

### 4.1 Agent Framework (智能体框架)

**架构**:

```
Agent Framework
├── AgentRegistry        # 智能体注册中心
├── AgentManager         # 智能体生命周期管理
├── AgentWorker          # 智能体执行器
├── AgentHub             # 智能体中心
├── AgentAdapter         # 智能体适配器
├── AgentProgress        # 智能体进度追踪
└── SkillsAdapter        # 技能适配器
```

**核心类**:

```python
class BaseAgent:
    def __init__(self, agent_id: str, config: dict):
        self.agent_id = agent_id
        self.config = config
        self.status = "idle"
    
    async def execute(self, task: Task) -> TaskResult:
        """执行任务"""
        pass
    
    async def learn(self, feedback: Feedback):
        """从反馈中学习"""
        pass
```

### 4.2 Model Router (模型路由)

**功能**: 根据任务类型和资源情况选择最优 LLM 模型

**路由策略**:

| 策略 | 说明 |
|-----|------|
| **性能优先** | 选择响应最快的模型 |
| **质量优先** | 选择质量最高的模型 |
| **成本优先** | 选择成本最低的模型 |
| **混合策略** | 综合考虑各项指标 |

**路由流程**:

```
任务请求 → 分析任务类型 → 评估可用模型 → 选择最优模型 → 执行任务 → 返回结果
```

### 4.3 Memory System (记忆系统)

**三层记忆架构**:

```
Memory System
├── ShortTermMemory    # 短期记忆 (当前会话)
├── MidTermMemory      # 中期记忆 (近期历史)
└── LongTermMemory     # 长期记忆 (持久化知识)
```

**记忆类型**:

| 类型 | 存储位置 | 保留时间 | 用途 |
|-----|---------|---------|------|
| 短期记忆 | 内存 | 会话期间 | 当前对话上下文 |
| 中期记忆 | SQLite | 7-30天 | 用户习惯学习 |
| 长期记忆 | PostgreSQL | 永久 | 知识库、技能、偏好 |

### 4.4 Skill System (技能系统)

**技能生命周期**:

```
技能注册 → 技能发现 → 技能匹配 → 技能执行 → 技能评估 → 技能进化
```

**技能分类**:

| 类别 | 说明 | 示例 |
|-----|------|------|
| **工具技能** | 调用外部工具 | 文件操作、浏览器自动化 |
| **知识技能** | 知识检索与问答 | RAG、知识库查询 |
| **创作技能** | 内容生成 | 写作、代码生成 |
| **分析技能** | 数据分析与处理 | 报表生成、趋势分析 |

**技能注册机制**:

```python
class SkillRegistry:
    def register(self, skill: BaseSkill):
        """注册技能"""
        pass
    
    def discover(self, query: str) -> List[SkillMatch]:
        """根据查询发现相关技能"""
        pass
    
    def match(self, intent: Intent) -> SkillMatch:
        """匹配最优技能"""
        pass
```

### 4.5 Task Orchestrator (任务编排)

**任务状态机**:

```
Pending → Queued → Processing → Completed/Failed → Archived
     ↓      ↓          ↓              ↓
   重试   取消      暂停/继续      重试/归档
```

**编排策略**:

| 策略 | 说明 |
|-----|------|
| **串行执行** | 任务按顺序执行 |
| **并行执行** | 任务同时执行 |
| **条件执行** | 根据条件决定执行路径 |
| **循环执行** | 重复执行直到条件满足 |

### 4.6 Fusion RAG (多源检索增强生成)

**检索流程**:

```
用户查询 → 查询分析 → 多源检索 → 结果融合 → LLM 生成 → 结果返回
            ↓               ↓
      意图识别      知识库/网页/文档
```

**检索源**:

| 源类型 | 说明 | 优先级 |
|-----|------|-------|
| **内部知识库** | 项目文档、代码注释 | 高 |
| **外部知识库** | 互联网搜索、文档库 | 中 |
| **用户记忆** | 历史对话、用户偏好 | 高 |
| **技能文档** | 技能描述、使用说明 | 中 |

### 4.7 Knowledge Graph (知识图谱)

**实体类型**:

| 实体 | 说明 | 属性 |
|-----|------|------|
| **Agent** | 智能体 | 名称、类型、能力 |
| **Skill** | 技能 | 名称、描述、参数 |
| **Knowledge** | 知识 | 内容、标签、来源 |
| **User** | 用户 | 偏好、历史、权限 |
| **Task** | 任务 | 状态、优先级、结果 |

**关系类型**:

| 关系 | 说明 | 示例 |
|-----|------|------|
| **has_skill** | 智能体拥有技能 | Agent → Skill |
| **knows** | 智能体知道知识 | Agent → Knowledge |
| **performed** | 用户执行任务 | User → Task |
| **uses** | 任务使用技能 | Task → Skill |

### 4.8 Event Bus (事件总线)

**事件类型**:

| 类别 | 事件 | 说明 |
|-----|------|------|
| **Agent Events** | `agent_created`, `agent_updated`, `agent_deleted` | 智能体生命周期 |
| **Task Events** | `task_created`, `task_updated`, `task_completed` | 任务状态变化 |
| **Skill Events** | `skill_registered`, `skill_updated`, `skill_executed` | 技能事件 |
| **System Events** | `system_started`, `system_shutdown`, `config_changed` | 系统事件 |

**事件订阅机制**:

```python
class EventBus:
    def subscribe(self, event_type: str, handler: Callable):
        """订阅事件"""
        pass
    
    def publish(self, event: Event):
        """发布事件"""
        pass
    
    def unsubscribe(self, event_type: str, handler: Callable):
        """取消订阅"""
        pass
```

---

## 5. 数据流与交互

### 5.1 核心数据流

**用户请求流程**:

```
[用户界面] → [事件总线] → [任务编排器] → [智能体管理器]
                                          ↓
                                   [模型路由器] → [LLM]
                                          ↓
                                   [技能系统] → [工具执行]
                                          ↓
                                   [记忆系统] → [知识检索]
                                          ↓
                                   [结果返回] → [用户界面]
```

### 5.2 模块交互图

```
┌────────────────────────────────────────────────────────────┐
│                     Presentation Layer                     │
│   [ChatWindow]  [IDEPanel]  [SkillPanel]  [ConfigPanel]   │
│         ↓            ↓            ↓            ↓          │
├────────────────────────────────────────────────────────────┤
│                        Event Bus                           │
│         ↓            ↓            ↓            ↓          │
├────────────────────────────────────────────────────────────┤
│                     Business Layer                         │
│   ┌───────────┐  ┌───────────┐  ┌───────────┐            │
│   │TaskOrch   │→│AgentMgr   │→│ModelRouter│            │
│   └───────────┘  └────┬──────┘  └────┬──────┘            │
│                       │              │                    │
│                       ↓              ↓                    │
│               ┌───────────┐  ┌───────────┐               │
│               │SkillSystem│  │MemorySystem│              │
│               └───────────┘  └───────────┘               │
│                       │              │                    │
├────────────────────────────────────────────────────────────┤
│                   Infrastructure Layer                     │
│           ┌─────────────┐  ┌─────────────┐                │
│           │  Database   │  │   Network   │                │
│           └─────────────┘  └─────────────┘                │
└────────────────────────────────────────────────────────────┘
```

---

## 6. 数据库设计

### 6.1 数据库架构

**数据库类型**: SQLite (默认) / PostgreSQL (生产环境)

**数据库迁移**: `client/src/infrastructure/database/` (v1-v14)

### 6.2 核心数据表

#### 6.2.1 agents 表

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | UUID | 主键 |
| `name` | VARCHAR | 智能体名称 |
| `type` | VARCHAR | 智能体类型 |
| `config` | JSON | 配置信息 |
| `status` | VARCHAR | 状态 |
| `created_at` | TIMESTAMP | 创建时间 |
| `updated_at` | TIMESTAMP | 更新时间 |

#### 6.2.2 skills 表

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | UUID | 主键 |
| `name` | VARCHAR | 技能名称 |
| `description` | TEXT | 技能描述 |
| `type` | VARCHAR | 技能类型 |
| `metadata` | JSON | 元数据 |
| `created_at` | TIMESTAMP | 创建时间 |

#### 6.2.3 tasks 表

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | UUID | 主键 |
| `agent_id` | UUID | 关联智能体 |
| `status` | VARCHAR | 任务状态 |
| `priority` | INTEGER | 优先级 |
| `input` | JSON | 输入数据 |
| `output` | JSON | 输出数据 |
| `error` | TEXT | 错误信息 |
| `created_at` | TIMESTAMP | 创建时间 |
| `completed_at` | TIMESTAMP | 完成时间 |

#### 6.2.4 memories 表

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | UUID | 主键 |
| `user_id` | UUID | 用户ID |
| `type` | VARCHAR | 记忆类型 (short/mid/long) |
| `content` | TEXT | 记忆内容 |
| `metadata` | JSON | 元数据 |
| `created_at` | TIMESTAMP | 创建时间 |
| `accessed_at` | TIMESTAMP | 访问时间 |

#### 6.2.5 knowledge_graph 表

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | UUID | 主键 |
| `entity_type` | VARCHAR | 实体类型 |
| `entity_id` | UUID | 实体ID |
| `relation` | VARCHAR | 关系类型 |
| `target_entity_type` | VARCHAR | 目标实体类型 |
| `target_entity_id` | UUID | 目标实体ID |
| `created_at` | TIMESTAMP | 创建时间 |

---

## 7. API 设计

### 7.1 REST API 端点

**基础路径**: `/api/v1/`

#### 7.1.1 智能体 API

| 端点 | 方法 | 说明 |
|-----|------|------|
| `/agents` | GET | 获取智能体列表 |
| `/agents/{id}` | GET | 获取单个智能体 |
| `/agents` | POST | 创建智能体 |
| `/agents/{id}` | PUT | 更新智能体 |
| `/agents/{id}` | DELETE | 删除智能体 |
| `/agents/{id}/execute` | POST | 执行智能体任务 |

#### 7.1.2 技能 API

| 端点 | 方法 | 说明 |
|-----|------|------|
| `/skills` | GET | 获取技能列表 |
| `/skills/{id}` | GET | 获取技能详情 |
| `/skills` | POST | 注册技能 |
| `/skills/{id}` | DELETE | 删除技能 |
| `/skills/search` | GET | 搜索技能 |

#### 7.1.3 任务 API

| 端点 | 方法 | 说明 |
|-----|------|------|
| `/tasks` | GET | 获取任务列表 |
| `/tasks/{id}` | GET | 获取任务详情 |
| `/tasks` | POST | 创建任务 |
| `/tasks/{id}` | PUT | 更新任务 |
| `/tasks/{id}` | DELETE | 删除任务 |
| `/tasks/{id}/cancel` | POST | 取消任务 |

#### 7.1.4 记忆 API

| 端点 | 方法 | 说明 |
|-----|------|------|
| `/memories` | GET | 获取记忆列表 |
| `/memories/{id}` | GET | 获取记忆详情 |
| `/memories` | POST | 创建记忆 |
| `/memories/{id}` | DELETE | 删除记忆 |
| `/memories/search` | GET | 搜索记忆 |

### 7.2 WebSocket API

**端点**: `/ws/v1/`

**消息类型**:

| 类型 | 说明 |
|-----|------|
| `task_update` | 任务状态更新 |
| `agent_status` | 智能体状态变化 |
| `system_event` | 系统事件 |
| `notification` | 通知消息 |

---

## 8. 部署架构

### 8.1 单机部署

```
┌─────────────────────────────────────────────┐
│           LivingTreeAI Desktop Client      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐    │
│  │  UI     │  │ Business│  │ Storage │    │
│  │ Layer   │  │  Layer  │  │ Layer   │    │
│  └────┬────┘  └────┬────┘  └────┬────┘    │
└───────┼────────────┼────────────┼──────────┘
        │            │            │
        ↓            ↓            ↓
┌─────────────────────────────────────────────┐
│              External Services              │
│   Ollama    │  PostgreSQL  │   Redis       │
└─────────────────────────────────────────────┘
```

### 8.2 分布式部署

```
                    ┌─────────────────┐
                    │   Load Balancer │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ↓                    ↓                    ↓
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   Relay       │    │   Relay       │    │   Relay       │
│   Server 1    │    │   Server 2    │    │   Server 3    │
└───────┬───────┘    └───────┬───────┘    └───────┬───────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ↓                    ↓                    ↓
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  PostgreSQL   │    │    Redis      │    │  P2P Network │
│   (Master)    │    │   Cluster     │    │   Tracker    │
└───────────────┘    └───────────────┘    └───────────────┘
```

### 8.3 Docker 部署

**容器组件**:

| 容器 | 镜像 | 端口 |
|-----|------|------|
| `livingtree` | `livingtreeai:latest` | 8000 |
| `postgres` | `postgres:15-alpine` | 5432 |
| `redis` | `redis:7-alpine` | 6379 |
| `nginx` | `nginx:alpine` | 80, 443 |

### 8.4 Kubernetes 部署

**资源配置**:

| 资源 | 配置 |
|-----|------|
| **Deployment** | 3 副本, RollingUpdate |
| **Service** | ClusterIP, 端口 8000 |
| **Ingress** | HTTPS, TLS 证书 |
| **HPA** | 基于 CPU/Memory, 2-10 副本 |
| **PVC** | 数据卷 10Gi, 日志卷 5Gi |

---

## 9. 安全架构

### 9.1 安全原则

| 原则 | 说明 |
|-----|------|
| **最小权限** | 每个模块只拥有必要的权限 |
| **数据加密** | 敏感数据加密存储和传输 |
| **输入验证** | 所有输入进行严格验证 |
| **审计日志** | 记录所有关键操作 |
| **安全隔离** | 进程隔离和沙箱执行 |

### 9.2 安全组件

| 组件 | 职责 |
|-----|------|
| **AuthSystem** | 用户认证和授权 |
| **SecurityPolicy** | 安全策略管理 |
| **EncryptedConfig** | 配置加密 |
| **SandboxRuntimes** | 沙箱运行时 |
| **ErrorLogger** | 安全审计日志 |

### 9.3 数据保护

**加密策略**:

| 数据类型 | 加密方式 |
|-----|------|
| **配置文件** | AES-256 |
| **数据库** | 字段级加密 |
| **网络传输** | TLS 1.3 |
| **API 通信** | JWT 令牌 |

---

## 📊 架构指标

| 指标 | 当前值 | 目标值 |
|-----|-------|-------|
| **模块数量** | ~340 (业务层) | 持续优化 |
| **代码行数** | ~100K+ | 持续优化 |
| **测试覆盖率** | 60% | 80%+ |
| **构建时间** | ~3min | <2min |
| **启动时间** | ~15s | <10s |
| **响应时间** | <500ms | <200ms |

---

## 🔮 未来演进

1. **微服务拆分**: 将核心服务拆分为独立微服务
2. **边缘部署**: 支持边缘计算节点部署
3. **AI 优化**: 引入更多 AI 驱动的优化
4. **多云支持**: 支持多云平台部署
5. **可观测性**: 增强监控和可观测性能力

---

**文档版本**: v1.0.0  
**最后更新**: 2026-04-30  
**维护团队**: LivingTreeAI Team