# LivingTreeAlAgent 架构开发指南

**文档版本**: v2.0
**创建日期**: 2026-04-28
**更新日期**: 2026-04-28
**状态**: 📋 **规划中** - 按自我进化原则组织

---

## 文档结构

1. [一、项目现状](#一项目现状)
2. [二、架构概览](#二架构概览)
3. [三、极简设计理念](#三极简设计理念) ⭐ **核心原则**
4. [四、自我进化原则](#四自我进化原则) ⭐ **核心理念**
5. [五、开源项目借鉴清单](#五开源项目借鉴清单) ⭐ **高匹配度逐一分析**
6. [六、阶段任务规划](#六阶段任务规划)
7. [七、已实现模块清单](#七已实现模块清单)
8. [八、开发规范](#八开发规范)
9. [附录A：Docker部署](#附录adocker部署) ⏸️ **推迟**
10. [附录B：MCP集成](#附录bmcp集成) ⏸️ **推迟**

---

## 一、项目现状

### 1.1 已完成能力 (2026-04-28)

| 类别 | 能力 | 实现度 | 关键模块 |
|------|------|--------|----------|
| **LLM分层** | L0-L4分层推理 | 93% | `GlobalModelRouter`, `llmcore/` |
| **环评系统** | 35个核心模块 | 96% | `workbench.py`, `compliance_checker` |
| **文档引擎** | plugin_framework | 92% | `document_parser`, `intelligent_ocr` |
| **自我进化** | 双数据飞轮 | 85% | `SelfEvolutionEngine`, `ToolSelfRepairer` |
| **技能系统** | 220+专家角色 | 90% | `.livingtree/skills/` |
| **工具层** | 统一ToolRegistry | 80% | `tools/tool_registry.py` |
| **拼写检查** | 实时错别字纠正 | 100% | `SpellCheckTextEdit` |

### 1.2 待完成能力

| 优先级 | 能力 | 差距 | 预计工时 |
|--------|------|------|----------|
| **P0** | IntentClarifier意图澄清 | 18% | 2天 |
| **P0** | ProgressiveUIRenderer渐进渲染 | 18% | 3天 |
| **P1** | Vibe驱动技能构建 | 25% | 3天 |
| **P1** | 确定性执行保障 | 25% | 2天 |

---

## 二、架构概览

### 2.1 三层架构

```
┌─────────────────────────────────────────────────────────┐
│                   智能体层 (Agent Brain)                │
│  HermesAgent / EIAgent / SkillEvolutionAgent            │
│  职责: 思考决策、任务规划、工具选择                       │
└─────────────────────┬───────────────────────────────────┘
                      │ ToolRegistry.execute()
                      ↓
┌─────────────────────────────────────────────────────────┐
│              统一工具层 (ToolRegistry)                   │
│  BaseTool ← 抽象基类                                     │
│  ToolDefinition ← 工具定义                               │
│  职责: 统一注册、发现、调用接口                           │
└─────────────────────┬───────────────────────────────────┘
                      │ 实现
                      ↓
┌─────────────────────────────────────────────────────────┐
│                  工具实现层 (Implementations)              │
│  🌐 网络: WebCrawler, DeepSearch, TierRouter            │
│  📄 文档: DocumentParser, IntelligentOCR                │
│  💾 存储: VectorDB, KnowledgeGraph, Memory              │
│  📋 任务: TaskDecomposer, ExecutionEngine              │
│  🧠 进化: ExpertLearning, SkillEvolution                │
│  🗺️ 地理: AERMOD, Mike21, MapAPI                       │
└─────────────────────────────────────────────────────────┘
```

### 2.2 核心文件路径

```
client/src/business/
├── tools/                           # 统一工具层
│   ├── tool_registry.py             # ✅ 工具注册中心
│   ├── base_tool.py                 # ✅ 工具基类
│   └── ...
├── hermes_agent/                    # 智能体框架
├── self_evolution/                  # 自我进化
├── global_model_router.py           # ✅ LLM路由(L0-L4)
└── [18+工具模块]                   # 已封装/待封装
```

---

## 三、极简设计理念

> ⭐ **核心理念**: 极简不是功能少，而是每个功能都恰到好处

### 3.1 极简设计三角

```
┌─────────────────────────────────────────────────────────────┐
│                    极简设计三角                              │
│                                                             │
│           ┌──────────────┐                                 │
│           │   会话交互    │  ← 自然对话，减少界面摩擦        │
│           └──────┬───────┘                                 │
│                  │                                         │
│     ┌────────────┼────────────┐                            │
│     ↓            ↓            ↓                            │
│ ┌───────┐  ┌──────────┐  ┌──────────┐                    │
│ │需求澄清│  │渐进渲染UI │  │按需加载  │                    │
│ │避免猜测│  │先骨架后细节│  │沉默成本低│                    │
│ └───────┘  └──────────┘  └──────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 会话交互 (Conversational Interaction)

**目标**: 像聊天一样完成任务，减少界面点击

```python
# ✅ 好：自然对话驱动
class ConversationalAgent:
    async def process(self, user_message: str):
        intent = await self.understand(user_message)
        if intent.missing_fields:
            return await self.clarify(intent.missing_fields)
        return await self.execute_progressive(intent)
```

### 3.3 需求澄清 (Requirement Clarification)

**原则**: 宁可多问一次，也不要猜错

### 3.4 渐进式UI渲染 (Progressive Rendering)

```
时间线: T+0ms → 骨架 → T+100ms → 结构 → T+300ms → 内容 → T+500ms → 丰富
```

---

## 四、自我进化原则

> ⭐ **核心理念**: **系统不得预置逻辑和模板，一切都要遵循自我学习、自我进化的思路**

### 4.1 核心原则

```
┌─────────────────────────────────────────────────────────────┐
│                   自我进化三原则                             │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ❌ 禁止预置         │  ✅ 鼓励学习                   │   │
│  │  - 固定模板          │  - 从样本学习                  │   │
│  │  - 硬编码规则        │  - 动态知识图谱               │   │
│  │  - 不可变的流程      │  - 可演进的工作流             │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 预置 vs 学习的对比

| 预置模式 (❌) | 学习模式 (✅) |
|-------------|--------------|
| 预定义报告模板 | 从样本文档学习结构 |
| 硬编码的澄清问题 | 从交互中学习用户意图 |
| 固定的工作流 | 自适应任务编排 |
| 人工编写规则 | 强化学习自动优化 |
| 静态知识库 | 动态知识图谱 |

### 4.3 自我进化架构

```
┌─────────────────────────────────────────────────────────────┐
│                    自我进化循环                              │
│                                                             │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐            │
│   │   执行   │ ─→ │   反馈   │ ─→ │   学习   │            │
│   └──────────┘    └──────────┘    └──────────┘            │
│        ↑                                      │            │
│        └──────────────────────────────────────┘            │
│                                                             │
│   执行 → 记录结果 → 分析错误 → 生成变体 → 训练测试 → 优化    │
└─────────────────────────────────────────────────────────────┘
```

### 4.4 已实现的进化组件

| 组件 | 功能 | 状态 |
|------|------|------|
| **ToolSelfRepairer** | 工具执行失败自动修复 | ✅ |
| **HardVariantGenerator** | 从错误中生成更难变体 | ✅ |
| **DualFlywheel** | 推理+训练双数据飞轮 | ✅ |
| **SelfReflectionEngine** | 执行结果反思优化 | ✅ |

### 4.5 待实现的进化组件

| 组件 | 功能 | 优先级 |
|------|------|--------|
| **VibeSkillBuilder** | 自然语言学习生成技能 | P1 |
| **AdaptiveClarifier** | 从交互中学习澄清策略 | P1 |
| **WorkflowEvolver** | 从执行中学习工作流 | P2 |
| **TemplateLearner** | 从样本学习文档模板 | P2 |

---

## 五、开源项目借鉴清单

> ⭐ **高匹配度项目逐一分析，所有借鉴必须融入自我进化框架**

### 5.1 高匹配度项目汇总 (匹配度≥70%)

| 项目 | Stars | 匹配度 | 借鉴性 | 优先级 | 借鉴方式 |
|------|-------|--------|--------|--------|----------|
| **markitdown** | 118k | 75% | 90% | P0 | 学习通用解析模式 |
| **andrej-karpathy-skills** | 94.5k | 50% | 90% | P0 | 学习技能构建方法 |
| **agent-skills** | 24.7k | 75% | 85% | P0 | 学习工具-技能映射 |
| **DeepTutor** | 22.3k | 70% | 85% | P0 | 学习自适应教学 |
| **Multica** | 22.1k | 65% | 80% | P0 | 学习多模态能力 |
| **Rowboat** | 13.1k | 60% | 75% | P0 | 学习多Agent协作 |
| **ml-intern** | 7k+ | 65% | 80% | P0 | 学习工具学习 |
| **refly** | 7.3k | 55% | 80% | P1 | 学习Vibe驱动构建 |
| **cognee** | - | 80% | 90% | P0 | 学习记忆增强 |
| **claude-mem** | - | 75% | 85% | P0 | 学习三层搜索 |

### 5.2 系统级方案借鉴

| 方案 | 匹配度 | 借鉴价值 | 优先级 |
|------|--------|----------|--------|
| **AnyDoc通用文档引擎** | 92% | 通用引擎+领域插件模式 | P0 |
| **EIA报告系统** | 96% | 完整任务驱动工作流 | P0 |
| **渐进式UI范式** | 82% | 会话式+渐进渲染 | P0 |
| **内置LLM方案** | 93% | nanoGPT+增量学习 | P0 |

### 5.3 P0级核心借鉴 (立即执行)

#### 5.3.1 cognee记忆增强 (匹配度80%)

**核心借鉴**: remember/recall/forget/improve API

```python
# ❌ 预置模式: 固定记忆结构
memory = {
    "user_prefs": {...},
    "history": [...]
}

# ✅ 学习模式: 自动学习记忆结构
class CogneeMemoryAdapter:
    async def remember(self, text: str, session_id: str = None):
        # 1. 自动提取实体和关系
        entities = await self.extract_entities(text)
        relations = await self.extract_relations(entities)

        # 2. 存储到知识图谱 + 向量数据库
        await self.kg.add(entities, relations)
        await self.vector_db.upsert(text, entities)

    async def recall(self, query: str, session_id: str = None):
        # 1. 向量搜索
        vector_results = await self.vector_db.search(query)

        # 2. 知识图谱推理
        kg_results = await self.kg.query(query)

        # 3. 混合排序返回
        return self.hybrid_rank(vector_results, kg_results)
```

**落地模块**: `client/src/business/cognee_memory/`

#### 5.3.2 refly Vibe驱动技能构建 (匹配度55%, 借鉴性80%)

**核心借鉴**: 自然语言 → 自动生成技能

```python
# ❌ 预置模式: 手工编写SKILL.md
# ✅ 学习模式: 从描述中学习生成
class VibeSkillBuilder:
    async def build_from_description(self, user_description: str) -> Skill:
        # 1. 理解技能需求
        analysis = await self.analyze(user_description)

        # 2. 生成技能结构
        skill = await self.generate_skill_structure(analysis)

        # 3. 学习示例（如果有）
        if examples := analysis.get_examples():
            skill = await self.learn_from_examples(skill, examples)

        # 4. 验证并注册
        await self.validate(skill)
        return skill
```

**落地模块**: `client/src/business/skill_evolution/vibe_skill_builder.py`

#### 5.3.3 ProgressiveUIRenderer渐进渲染 (匹配度82%)

**核心借鉴**: 会话式+渐进式UI

```python
# ❌ 预置模式: 一次性渲染完整UI
# ✅ 学习模式: 渐进加载，随需渲染
class ProgressiveUIRenderer:
    async def render(self, task: Task) -> AsyncGenerator[UI, None]:
        # L1: 立即返回骨架
        yield self.render_skeleton(task)

        # L2: 加载核心数据
        core = await self.load_core(task)
        yield self.render_structure(core)

        # L3: 加载内容
        content = await self.load_content(core)
        yield self.render_content(content)

        # L4: 丰富交互 (按需)
        if self.user_interests(content):
            enriched = await self.load_enriched(content)
            yield self.render_enriched(enriched)
```

**落地模块**: `client/src/business/hermes_agent/progressive_ui_renderer.py`

#### 5.3.4 IntentClarifier意图澄清 (匹配度80%)

**核心借鉴**: 从交互中学习澄清策略

```python
# ❌ 预置模式: 固定的澄清问题列表
clarification_questions = [
    "请选择日期",
    "请选择范围",
]

# ✅ 学习模式: 自适应澄清
class AdaptiveClarifier:
    def __init__(self):
        self.learned_strategies = LearnedStrategies()

    async def clarify(self, intent: Intent) -> str:
        # 1. 分析缺失信息
        missing = intent.get_missing_fields()

        # 2. 学习最佳澄清策略
        strategy = await self.learned_strategies.get(missing)

        # 3. 生成自然语言澄清
        return self.generate_clarification(missing, strategy)

    async def learn_from_interaction(self, interaction: Interaction):
        # 4. 从交互中学习改进策略
        await self.learned_strategies.update(interaction)
```

**落地模块**: `client/src/business/hermes_agent/intent_clarifier.py`

#### 5.3.5 markitdown文档解析 (匹配度75%)

**核心借鉴**: 通用文档解析模式

```python
# ❌ 预置模式: 每个文档类型一个解析器
class EIAReportParser:
    def parse(self, doc): ...

class FeasibilityParser:
    def parse(self, doc): ...

# ✅ 学习模式: 通用解析器 + 自适应
class UniversalDocumentParser:
    def __init__(self):
        self.learned_patterns = LearnedPatterns()

    async def parse(self, doc: Document) -> ParsedResult:
        # 1. 检测文档类型
        doc_type = await self.detect_type(doc)

        # 2. 学习结构模式
        patterns = await self.learned_patterns.get(doc_type)
        if not patterns:
            patterns = await self.extract_patterns(doc)
            await self.learned_patterns.store(doc_type, patterns)

        # 3. 应用学习的模式解析
        return await self.apply_patterns(doc, patterns)
```

**落地模块**: `client/src/business/bilingual_doc/universal_parser.py`

### 5.4 P1级重要借鉴

#### 5.4.1 DeepTutor自适应学习

**核心借鉴**: 从反馈中学习最优策略

```python
class AdaptiveLearningLoop:
    async def learn(self, task: Task, result: Result):
        # 1. 评估结果质量
        quality = await self.evaluate(task, result)

        # 2. 记录学习样本
        await self.memory.add(task, result, quality)

        # 3. 如果质量低，生成变体
        if quality < threshold:
            variants = await self.generate_variants(task, result)
            await self.test(variants)

        # 4. 更新策略
        await self.policy.update(self.memory)
```

#### 5.4.2 Rowboat多Agent协作

**核心借鉴**: Agent团队协作模式

```python
class MultiAgentOrchestrator:
    async def orchestrate(self, task: Task) -> Result:
        # 1. 分解任务到子任务
        subtasks = await self.decompose(task)

        # 2. 分配给专业Agent
        agents = await self.assign_agents(subtasks)

        # 3. 并行执行
        results = await asyncio.gather(*[
            agent.execute(st) for agent, st in zip(agents, subtasks)
        ])

        # 4. 整合结果
        return await self.synthesize(results)
```

### 5.5 借鉴实施总览

| 阶段 | 借鉴项目 | 落地模块 | 工时 | 优先级 |
|------|---------|---------|------|--------|
| **A** | cognee记忆 | cognee_memory/ | 2天 | P0 |
| **A** | ProgressiveUI | progressive_ui_renderer.py | 3天 | P0 |
| **A** | IntentClarifier | intent_clarifier.py | 2天 | P0 |
| **B** | VibeSkillBuilder | vibe_skill_builder.py | 3天 | P1 |
| **B** | UniversalParser | universal_parser.py | 2天 | P1 |
| **C** | AdaptiveLearning | adaptive_learning_loop.py | 3天 | P2 |
| **C** | MultiAgentOrch | multi_agent_orchestrator.py | 2天 | P2 |

---

## 六、阶段任务规划

### 6.1 阶段A: 核心自我进化 (P0)

| 任务 | 功能 | 工时 | 依赖 |
|------|------|------|------|
| **IntentClarifier** | 自适应意图澄清 | 2天 | hermes_agent |
| **ProgressiveUIRenderer** | 渐进式UI渲染 | 3天 | presentation |
| **CogneeMemory** | 记忆增强学习 | 2天 | knowledge_graph |

### 6.2 阶段B: 技能与解析进化 (P1)

| 任务 | 功能 | 工时 | 依赖 |
|------|------|------|------|
| **VibeSkillBuilder** | Vibe驱动技能构建 | 3天 | skill_evolution |
| **UniversalParser** | 通用文档解析 | 2天 | bilingual_doc |

### 6.3 阶段C: 高级进化 (P2)

| 任务 | 功能 | 工时 | 依赖 |
|------|------|------|------|
| **AdaptiveLearning** | 自适应学习循环 | 3天 | self_evolution |
| **MultiAgentOrch** | 多Agent编排 | 2天 | hermes_agent |

---

## 七、已实现模块清单

### 7.1 工具层 (client/src/business/tools/)

| 文件 | 功能 | 状态 |
|------|------|------|
| `tool_registry.py` | 工具注册中心 | ✅ |
| `base_tool.py` | 工具基类 | ✅ |
| `mcp_tool_adapter.py` | MCP适配器 | ✅ |
| `text_correction_tool.py` | 错别字纠正 | ✅ |

### 7.2 自我进化 (client/src/business/self_evolution/)

| 文件 | 功能 | 状态 |
|------|------|------|
| `self_evolution_engine.py` | 进化引擎 | ✅ |
| `tool_self_repairer.py` | 工具自我修复 | ✅ |
| `hard_variant_generator.py` | 变体生成 | ✅ |
| `dual_flywheel/` | 双数据飞轮 | ✅ |

---

## 八、开发规范

### 8.1 代码位置

```
✅ 新代码 → client/src/business/ (逻辑) 或 client/src/presentation/ (UI)
❌ 旧代码 → core/ 或 ui/ (已删除)
```

### 8.2 自我进化检查清单

每个新模块必须检查：

- [ ] **学习优于预置**: 能否从样本/交互中学习，而非硬编码？
- [ ] **可演进**: 是否支持动态更新？
- [ ] **反馈闭环**: 执行结果能否反馈到学习？
- [ ] **无固定模板**: 是否避免预置模板？

### 8.3 LLM调用

```python
# ✅ 正确: 通过GlobalModelRouter
from client.src.business.global_model_router import GlobalModelRouter, ModelCapability
router = GlobalModelRouter()
result = router.call_model_sync(ModelCapability.REASONING, prompt)
```

---

## 附录A：Docker部署 ⏸️ **推迟**

---

## 附录B：MCP集成 ⏸️ **推迟**

---

## 变更日志

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v2.0 | 2026-04-28 | 重构为自我进化原则，新增开源项目借鉴清单 |
| v1.2 | 2026-04-28 | 新增极简设计理念章节 |
| v1.1 | 2026-04-28 | 新增参考借鉴章节 |
| v1.0 | 2026-04-28 | 初始版本，按阶段任务组织 |

---

**下一步**: 开始阶段A - 实现IntentClarifier + ProgressiveUIRenderer
