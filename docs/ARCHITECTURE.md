# LivingTree 系统架构手册

> v2.1 | 2026-05

---

## 1. 设计哲学

LivingTree 是一个**自主数字生命体**，不是传统的 LLM 包装器。

核心理念：
- **边缘智能优先**：能力向前端倾斜，Agent 自身就是模型，大模型仅是最强大脑
- **细胞 AI 网络**：世界由无数独立智能细胞组成，P2P 协作形成超级 AI
- **渐进脱离 LLM**：每一次 LLM 调用都是学习机会，知识向下层固化
- **经济范式驱动**：最小成本 × 最快速度 × 最高质量的三元优化

---

## 2. 系统分层

```
┌─────────────────────────────────────────────────────────┐
│  TUI 界面层  (Toad + Textual)                           │
│  ChatScreen · CodeScreen · KnowledgeScreen · Settings   │
├─────────────────────────────────────────────────────────┤
│  经济门控层  (Economy)                                   │
│  EconomicPolicy · ROIModel · ComplianceGate             │
├───────────┬───────────┬───────────┬────────────────────┤
│  TreeLLM  │ LifeEngine│ Knowledge │ Capability         │
│  路由引擎 │ 生命循环  │ RAG 2.0   │ 文档智能           │
├───────────┴───────────┴───────────┴────────────────────┤
│  执行层  (Execution)                                    │
│  PlanValidator · FitnessLandscape · DAG/ReAct          │
├─────────────────────────────────────────────────────────┤
│  集成层  (Integration)                                  │
│  Hub · P2P Node · Message Gateway · Self Updater        │
├─────────────────────────────────────────────────────────┤
│  存储层  (Infrastructure)                               │
│  SQLite FTS5 · Vector DB · Knowledge Graph · AsyncDisk  │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 核心子系统

### 3.1 LifeEngine — 生命循环

7 阶段管道：`perceive → cognize → plan → execute → reflect → evolve`

集成点：
- 执行前：EconomicOrchestrator 经济审查 + PlanValidator 验证
- 执行后：FitnessLandscape 轨迹记录 + SkillProgression 技能追踪
- 决策中：ReasoningChain 溯源记录

### 3.2 TreeLLM — 模型路由

RouteMoA 分层路由架构：
- Layer 1: Embedding 预筛选
- Layer 1.5: Foresight Gate 预测
- Layer 2: HolisticElection 5 维评分
- Layer 3: Self-Assessment 自评

支持 14+ Provider + models.dev 全量 (50+厂商) 动态同步。

### 3.3 Economic Engine — 经济引擎

| 策略 | 成本 | 速度 | 质量 | 日预算 | 场景 |
|------|------|------|------|--------|------|
| ECONOMY | 60% | 15% | 25% | ¥20 | 日常批处理 |
| BALANCED | 33% | 33% | 34% | ¥50 | 默认 |
| QUALITY | 15% | 15% | 70% | ¥100 | 环评/法律 |
| SPEED | 15% | 70% | 15% | ¥30 | 实时交互 |

AdaptiveEconomicScheduler 按时段/紧急度/ROI 自动切换。

### 3.4 Knowledge Layer — RAG 2.0

```
查询 → QueryDecomposer + HyDE
     → KnowledgeRouter (SSA 感知路由)
     → 多路并行 (FTS5 + Vector + Graph + Engram)
     → RRF 混合融合 (k=60)
     → Reranker 精排
     → AgenticRAG 迭代反射
     → HallucinationGuard 校验
```

### 3.5 Document Intelligence — 文档智能

三层文档处理栈：

| 层 | 模块 | 能力 |
|----|------|------|
| 读取 | DocumentIntelligence | Word/Excel/PPT 原生结构提取 |
| 理解 | DocumentUnderstanding | 5维语义分析（专家级） |
| 加速 | IncrementalDoc | 哈希 diff + 缓存复用（94% token节省） |

### 3.6 Intelligence Core — 智能核心

| 模块 | 功能 |
|------|------|
| AutonomousCore | 主动发现工作 → 分解 → 执行 → 审计 |
| ReasoningChain | 决策溯源：为什么/替代方案/验证 |
| SkillProgression | 8维技能成长追踪 |
| LocalIntelligence | 三层智能（缓存→本地→远程） |
| GradualAgent | 渐进式 RAG 升级（简单→复杂） |

---

## 4. 数据流

```
用户请求
  ├── LocalIntelligence (Tier 1 缓存命中? → 零LLM返回)
  ├── EconomicOrchestrator (ROI评估 → Go/NoGo)
  ├── TreeLLM routing (选择最优模型)
  ├── Knowledge RAG (检索增强)
  ├── LifeEngine execution (执行管道)
  └── 反馈到:
       ├── FitnessLandscape (轨迹记录)
       ├── SkillProgression (技能更新)
       └── ReasoningChain (决策验证)
```

---

## 5. 自主循环

```
LifeDaemon (每30分钟)
  ├── Self-check: GapDetector 检测知识缺口
  ├── Learn: AutonomousLearner 填补缺口
  ├── Evolve: Cell mutation + SelfEvolving
  ├── Train: 触发 Mitosis
  └── Proactive: AutonomousCore.cycle()
        ├── Discover (技能/项目/知识/优化)
        ├── Prioritize (紧急度×价值/成本)
        ├── Execute (自动分解执行)
        └── Audit (自我审查)
```

---

## 6. 部署架构

```
[用户设备]                    [服务器]
LivingTree Agent  ←──P2P──→  Relay Server
  ├── LocalIntelligence         ├── Node Registry
  ├── Local Model (可选)        ├── Message Gateway
  └── Knowledge Base            └── Health Monitor
       │
       ▼ (按需)
  [DeepSeek API]  [Qwen API]  [50+ models.dev providers]
```

---

## 7. 技术栈

| 层 | 技术 |
|----|------|
| UI | Toad (Textual 8.x) |
| LLM | LiteLLM → DeepSeek/Qwen/13+ providers |
| 知识库 | SQLite FTS5 + FAISS Vector + NetworkX Graph |
| 网络 | aiohttp + WebSocket P2P |
| 配置 | Pydantic + YAML + Fernet |
| 本地模型 | vLLM + Qwen3.5 series (可选) |
| 模型数据 | models.dev sync (50+厂商) |
