# LivingTreeAlAgent 架构开发指南

**文档版本**: v1.1  
**创建日期**: 2026-04-28  
**更新日期**: 2026-04-28  
**状态**: 📋 **规划中** - 按阶段任务组织

---

## 文档结构

1. [一、项目现状](#一项目现状)
2. [二、架构概览](#二架构概览)
3. [三、极简设计理念](#三极简设计理念) ⭐ **核心原则**
4. [四、参考借鉴](#四参考借鉴)
5. [五、阶段一：工具层基础设施](#五阶段一工具层基础设施)
6. [六、阶段二：工具模块改造](#六阶段二工具模块改造)
7. [七、阶段三：智能体集成](#七阶段三智能体集成)
8. [八、阶段四：新建缺失工具](#八阶段四新建缺失工具)
9. [九、阶段五：自我进化引擎](#九阶段五自我进化引擎)
10. [十、已实现模块清单](#十已实现模块清单)
11. [十一、开发规范](#十一开发规范)
12. [附录A：Docker部署](#附录adocker部署) ⏸️ **推迟**
13. [附录B：MCP集成](#附录bmcp集成) ⏸️ **推迟**

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
| **P0** | Markdown导出工具 | 18% | 1天 |
| **P1** | CGCS2000坐标转换器 | 18% | 3天 |
| **P1** | 意图澄清器 | 18% | 2天 |
| **P2** | 增量微调管道 | 25% | 5天 |

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
│   ├── tool_definition.py           # ✅ 工具定义
│   ├── tool_result.py               # ✅ 工具结果
│   └── registrar.py                 # ✅ 统一注册入口
│
├── hermes_agent/                    # 智能体框架
│   ├── agent.py                     # HermesAgent
│   ├── proactive_discovery_agent.py # ✅ 主动发现
│   └── tool_chain_orchestrator.py   # ✅ 工具链编排
│
├── self_evolution/                  # 自我进化
│   ├── self_evolution_engine.py     # ✅ 进化引擎
│   ├── tool_self_repairer.py        # ✅ 自我修复
│   ├── hard_variant_generator.py    # ✅ 变体生成
│   └── dual_flywheel/               # ✅ 双数据飞轮
│
├── global_model_router.py           # ✅ LLM路由(L0-L4)
├── llmcore/                         # ✅ nanoGPT源码
│
└── [18+工具模块]                   # 已封装/待封装
```

---

## 三、参考借鉴

> ⭐ **核心原则**: 不集成框架（太重），只借鉴设计哲学（轻量），用LivingTree现有架构实现（无缝融合）

---

## 四、参考借鉴

> ⭐ **核心原则**: 不集成框架（太重），只借鉴设计哲学（轻量），用LivingTree现有架构实现（无缝融合）

### 三大原则

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
│ │       │  │          │  │          │                    │
│ │避免猜测│  │先骨架后细节│  │沉默成本低│                    │
│ └───────┘  └──────────┘  └──────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

### 3.1.1 会话交互 (Conversational Interaction)

**目标**: 像聊天一样完成任务，减少界面点击

| 对比 | 传统UI | 会话交互 |
|------|--------|----------|
| 任务创建 | 填表单 → 点按钮 → 等待 | 说一句话 → 自动完成 |
| 参数配置 | 多级菜单 → 选项卡 | 渐进式提问 → 动态理解 |
| 结果展示 | 表格 → 图表 → 详情 | 关键信息 → "还需要什么？" |

**LivingTree实现**:
```python
# ✅ 好：自然对话驱动
class ConversationalAgent:
    async def process(self, user_message: str):
        # 1. 理解意图（可能需要澄清）
        intent = await self.understand(user_message)

        # 2. 缺失信息？主动询问
        if intent.missing_fields:
            return await self.clarify(intent.missing_fields)

        # 3. 执行 + 渐进展示
        return await self.execute_progressive(intent)
```

### 3.1.2 需求澄清 (Requirement Clarification)

**原则**: 宁可多问一次，也不要猜错

| 场景 | 不澄清 → 猜 | 澄清 → 确认 |
|------|------------|-------------|
| 时间 | "明天" → 假设24小时内 | "明天下午3点？" |
| 范围 | "环评报告" → 模板A | "要AERMOD还是Mike21？" |
| 精度 | "详细" → 最高精度 | "精确到小数点后几位？" |

**IntentClarifier模块** (P1优先级):
```python
class IntentClarifier:
    """需求澄清器 - 主动询问缺失信息"""

    def needs_clarification(self, intent: Intent) -> List[str]:
        """返回需要澄清的字段列表"""
        missing = []
        if not intent.time_constraint:
            missing.append("完成时间")
        if not intent.scope:
            missing.append("任务范围")
        if not intent.precision:
            missing.append("精度要求")
        return missing

    def generate_clarifying_question(self, missing_fields: List[str]) -> str:
        """生成自然语言的澄清问题"""
        # 示例："要什么时候完成？范围有多大？"
```

### 3.1.3 渐进式UI渲染 (Progressive Rendering)

**原则**: 先看到能看的，慢慢加载完整的

```
时间线:
─────────────────────────────────────────────────────────────►
│         │              │              │              │
T+0ms    T+100ms         T+300ms        T+500ms       T+1000ms
│         │              │              │              │
▼         ▼              ▼              ▼              ▼
┌───┐   ┌─────────┐   ┌───────────┐  ┌───────────┐  ┌───────────┐
│骨架│   │  标题   │   │  内容主体  │  │  图表    │  │  细节    │
│   │   │  + 日期  │   │           │  │         │  │  备注    │
│   │   │         │   │           │  │         │  │         │
└───┘   └─────────┘   └───────────┘  └───────────┘  └───────────┘
```

**实现模式**:

| 层级 | 渲染时机 | 内容 |
|------|---------|------|
| **L1 骨架** | 立即 (0ms) | 占位符、加载动画 |
| **L2 结构** | <100ms | 标题、时间、关键数据 |
| **L3 内容** | <500ms | 主体文本、列表 |
| **L4 丰富** | <1s | 图表、交互元素 |
| **L5 细节** | 随需 | 注释、帮助、扩展信息 |

```python
# ProgressiveRenderer 示例
class ProgressiveRenderer:
    async def render(self, data: Any) -> AsyncGenerator[str, None]:
        yield self.render_skeleton()           # L1: 骨架
        core = await self.load_core(data)
        yield self.render_structure(core)      # L2: 结构
        content = await self.load_content(core)
        yield self.render_content(content)     # L3: 内容
        if self.user_wants_details():
            enriched = await self.load_enriched(content)
            yield self.render_enriched(enriched)  # L4/L5: 丰富+细节
```

### 3.1.4 极简设计检查清单

开发新功能时检查：

- [ ] **会话优先**: 能否用一句话完成这个操作？
- [ ] **按需提问**: 是否只在必要时询问？
- [ ] **渐进展示**: 是否先展示关键信息？
- [ ] **沉默成本**: 用户不操作会怎样？最小代价是什么？
- [ ] **撤销友好**: 能否轻松回退？

---

## 四、参考借鉴

> ⭐ **核心原则**: 不集成框架（太重），只借鉴设计哲学（轻量），用LivingTree现有架构实现（无缝融合）

### 4.1 开源项目分析

| 项目 | 核心特性 | 匹配度 | LivingTree借鉴 |
|------|---------|--------|----------------|
| **claude-mem** | 三层搜索工作流、Chroma向量数据库、渐进式披露 | 75% | 记忆系统Token优化 |
| **cognee** | remember/recall/forget/improve API、知识图谱+向量混合 | 80% | 记忆增强机制 |
| **Ralph** | 外部持久化记忆、PRD驱动循环、反馈质量门禁 | 60% | Agent闭环设计 |
| **LinkMind** | 多模态API路由、生产级过滤器、模型故障转移 | 70% | 企业级中间件 |
| **Disco-RAG** | 块内话语树、块间修辞图、规划蓝图 | 65% | RAG结构化增强 |
| **Nano-vLLM** | 1200行轻量实现、前缀缓存、张量并行 | 45% | 本地推理优化 |
| **Vheer** | 免费图像视频生成、多模型集成 | 55% | 多模态内容生成 |

### 4.2 设计框架借鉴

| 框架 | 设计哲学 | 优先级 | 轻量实现 |
|------|---------|--------|----------|
| **OpenSpec** | Spec-First、先写规范再写代码 | P1 | RequirementSpecManager单文件 |
| **Superpowers** | TDD强制执行、工程纪律 | P2 | TDDEnforcement提示器 |
| **GSD** | 上下文buffer管理、防止长任务崩溃 | P1 | ContextBufferManager |
| **OMC** | 多Agent编排、并行执行 | P2 | MultiAgentOrchestration |
| **ECC** | Harness系统化优化、生产级可靠 | P2 | MemoryManager+SecurityChecker |
| **Trellis** | 项目记忆管理、多工具协作 | P1 | ProjectMemoryManager |

### 4.3 记忆系统增强方案 (借鉴 claude-mem + cognee)

```
当前状态                          目标状态
─────────────────────────────────────────────────────
SQLite纯存储              →       SQLite + Chroma向量
关键词匹配                →       语义向量搜索
手动调用API               →       remember/recall自动路由
无会话隔离                →       多会话/租户隔离
无遗忘机制                →       forget API
基础持续学习              →       improve反馈优化
```

**新增模块**: `client/src/business/cognee_memory/`

```python
class CogneeMemoryAdapter:
    async def remember(self, text: str, session_id: str = None):
        """存储到知识图谱 + 向量数据库"""

    async def recall(self, query: str, session_id: str = None):
        """自动路由查询，混合向量+图搜索"""

    async def forget(self, dataset: str):
        """删除数据"""

    async def improve(self, feedback: dict):
        """持续改进优化"""
```

### 4.4 Discourse-Aware RAG (借鉴 Disco-RAG)

**新增模块**: `client/src/business/disco_rag/`

| 功能 | 说明 | 状态 |
|------|------|------|
| 块内话语树 | 文档块内层级结构建模 | 🔲 |
| 块间修辞图 | 跨段落修辞关系图 | 🔲 |
| 规划蓝图 | 结构化生成引导 | 🔲 |

### 4.5 多模态集成 (借鉴 Vheer)

**功能**: 文生图、图生视频、文生视频

**集成方式**: 通过 `多模态内容生成` 技能（bundled）

### 4.6 企业级模型路由 (借鉴 LinkMind)

**已有**: GlobalModelRouter (L0-L4分层) ✅

**待增强**:
- 故障转移机制 (pass路由)
- 生产级过滤器 (敏感词/停用词)
- Token用量统计

### 4.7 借鉴实施计划

| 阶段 | 内容 | 优先级 | 工时 | 状态 |
|------|------|--------|------|------|
| **阶段A** | cognee记忆适配器 | P0 | 2天 | 🔲 |
| **阶段A** | ContextBufferManager | P0 | 1天 | 🔲 |
| **阶段B** | OpenSpec规范管理器 | P1 | 1天 | 🔲 |
| **阶段B** | Trellis项目记忆 | P1 | 2天 | 🔲 |
| **阶段C** | Disco-RAG话语感知 | P2 | 3天 | 🔲 |
| **阶段C** | MultiAgent编排 | P2 | 2天 | 🔲 |
| **阶段D** | LinkMind路由增强 | P2 | 1天 | 🔲 |

---

## 五、阶段一：工具层基础设施

**目标**: 搭建工具注册与调用框架
**状态**: ✅ **已完成**
**工时**: 1-2小时

### 5.1 已交付文件

```
client/src/business/tools/
├── __init__.py
├── tool_registry.py      # ✅ ToolRegistry单例类
├── base_tool.py          # ✅ BaseTool抽象基类
├── tool_definition.py    # ✅ ToolDefinition数据类
├── tool_result.py        # ✅ ToolResult数据类
└── registrar.py         # ✅ 统一注册入口
```

### 5.2 核心接口

```python
# ToolRegistry - 工具注册中心
class ToolRegistry:
    def register(tool_def: ToolDefinition) -> None
    def discover(query: str) -> List[ToolDefinition]  # 语义搜索
    async def execute(tool_name: str, **kwargs) -> ToolResult

# BaseTool - 工具基类
class BaseTool(ABC):
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult
    @property
    def name(self) -> str
    @property
    def description(self) -> str
    @property
    def category(self) -> str
```

### 5.3 使用示例

```python
from client.src.business.tools import tool_registry

# 注册工具
tool_registry.register(WebCrawlerTool())

# 发现工具
tools = tool_registry.discover("爬取网页内容")

# 执行工具
result = await tool_registry.execute("web_crawler", url="https://example.com")
```

---

## 六、阶段二：工具模块改造

**目标**: 将18个已有模块封装为标准化工具
**状态**: 🔄 **进行中**
**工时**: 3-4小时

### 6.1 已完成改造

| 类别 | 工具 | 状态 |
|------|------|------|
| 文本处理 | TextCorrectionTool (错别字纠正) | ✅ |
| 自我进化 | ToolSelfRepairer (自我修复) | ✅ |
| 工具编排 | ToolChainOrchestrator | ✅ |
| 主动发现 | ProactiveDiscoveryAgent | ✅ |

### 6.2 待改造清单

| 批次 | 工具 | 路径 | 状态 |
|------|------|------|------|
| **网络** | WebCrawler | `web_crawler/engine.py` | 🔲 |
| **网络** | DeepSearch | `deep_search_wiki/wiki_generator.py` | 🔲 |
| **网络** | TierRouter | `search/tier_router.py` | 🔲 |
| **网络** | ContentExtractor | `web_content_extractor/extractor.py` | 🔲 |
| **文档** | DocumentParser | `bilingual_doc/document_parser.py` | 🔲 |
| **文档** | IntelligentOCR | `intelligent_ocr/` | 🔲 |
| **存储** | VectorDB | `knowledge_vector_db.py` | 🔲 |
| **存储** | KnowledgeGraph | `knowledge_graph.py` | 🔲 |
| **存储** | IntelligentMemory | `intelligent_memory.py` | 🔲 |
| **任务** | TaskDecomposer | `task_decomposer.py` | 🔲 |
| **任务** | TaskExecutionEngine | `task_execution_engine.py` | 🔲 |
| **学习** | ExpertLearning | `expert_learning/` | 🔲 |
| **学习** | SkillEvolution | `skill_evolution/` | 🔲 |

### 6.3 改造模板

```python
# client/src/business/tools/[模块名]_tool.py
from client.src.business.tools.base_tool import BaseTool, ToolResult

class [ModuleName]Tool(BaseTool):
    """[模块描述]"""
    
    def __init__(self):
        self._impl = OriginalModule()
    
    @property
    def name(self) -> str:
        return "[tool_name]"
    
    @property
    def description(self) -> str:
        return "[工具功能描述]"
    
    @property
    def category(self) -> str:
        return "[category]"
    
    async def execute(self, **kwargs) -> ToolResult:
        try:
            result = self._impl.[method](**kwargs)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

def register():
    from client.src.business.tools import tool_registry
    tool_registry.register([ModuleName]Tool())
```

---

## 七、阶段三：智能体集成

**目标**: 让智能体通过ToolRegistry调用工具
**状态**: ✅ **已完成**
**工时**: 2-3小时

### 7.1 已集成模块

```
✅ BaseToolAgent基类 (client/src/business/hermes_agent/base_agents/base_agent.py)
✅ HermesAgent工具调用
✅ EIAgent工具调用
✅ 语义搜索发现
```

### 7.2 智能体工作流

```python
class HermesAgent:
    async def process_task(self, task: str):
        # 1. 理解任务
        analysis = await self.understand_task(task)
        
        # 2. 发现所需工具 (语义搜索)
        tools = await self.tool_registry.discover(analysis.needed_capabilities)
        
        # 3. 执行工具链
        results = {}
        for tool in tools:
            result = await self.tool_registry.execute(tool.name, **params)
            results[tool.name] = result
        
        # 4. 整合结果
        return await self.synthesize(results)
```

---

## 八、阶段四：新建缺失工具

**目标**: 补齐P0/P1优先级工具
**状态**: 📋 **规划中**
**工时**: 按需

### 8.1 P0 - 立即开始

| 工具 | 功能 | 工时 | 依赖 |
|------|------|------|------|
| **MarkdownExporter** | HTML/DOCX → Markdown | 1天 | markdown库 |

### 8.2 P1 - 近期完成

| 工具 | 功能 | 工时 | 依赖 |
|------|------|------|------|
| **CGCS2000Converter** | 坐标转换(WGS84↔CGCS2000) | 3天 | pyproj |
| **ProgressiveUIRenderer** | 分步式地图生成向导 | 3天 | drawing_engine |
| **IntentionClarifier** | 用户意图澄清对话 | 2天 | hermes_agent |

### 8.3 P2 - 优化迭代

| 工具 | 功能 | 工时 | 状态 |
|------|------|------|------|
| **IncrementalFineTuner** | 增量微调管道 | 5天 | nanoGPT, peft |
| **AISectionGenerator** | AI增强章节生成 | 3天 | GlobalModelRouter |
| **TemplateEngine** | 文档模板引擎 | 2天 | MarkdownExporter |

---

## 九、阶段五：自我进化引擎

**目标**: 让系统具备自我进化能力
**状态**: 🔄 **部分完成**
**工时**: 3-5天

### 9.1 已实现组件

```
✅ ToolSelfRepairer (工具自我修复)
✅ HardVariantGenerator (难例变体生成)
✅ DualFlywheel (双数据飞轮)
✅ SelfReflectionEngine (自我反思)
```

### 9.2 待实现组件

| 组件 | 功能 | 状态 |
|------|------|------|
| **ToolMissingDetector** | 工具缺失检测 | 🔲 |
| **AutonomousToolCreator** | 自主工具创建 | 🔲 |
| **ActiveLearningLoop** | 主动学习循环 | 🔲 |
| **SafeAutonomousToolCreator** | 安全创建器(沙箱) | 🔲 |

### 9.2 待实现组件

```
┌─────────────────────────────────────────────────────┐
│                    任务执行                           │
└─────────────────────┬───────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│              ToolMissingDetector                     │
│         检测所需工具是否可用                          │
└─────────────────────┬───────────────────────────────┘
                      ↓ (缺失)
┌─────────────────────────────────────────────────────┐
│           AutonomousToolCreator                      │
│         LLM生成工具代码                              │
└─────────────────────┬───────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│           SafeAutonomousToolCreator                  │
│         沙箱测试 + 代码审查                           │
└─────────────────────┬───────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│             ToolSelfRepairer                         │
│         执行失败时自动修复                             │
└─────────────────────┬───────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│            SelfReflectionEngine                      │
│         反思执行结果，更新策略                         │
└─────────────────────────────────────────────────────┘
```

---

## 十、已实现模块清单

### 10.1 工具层 (client/src/business/tools/)

| 文件 | 功能 | 状态 |
|------|------|------|
| `tool_registry.py` | 工具注册中心 | ✅ |
| `base_tool.py` | 工具基类 | ✅ |
| `tool_definition.py` | 工具定义 | ✅ |
| `tool_result.py` | 工具结果 | ✅ |
| `registrar.py` | 统一注册 | ✅ |
| `text_correction_tool.py` | 错别字纠正 | ✅ |
| `mcp_tool_adapter.py` | MCP适配器 | ✅ |

### 10.2 EIA系统 (client/src/business/ei_agent/)

| 文件 | 功能 | 状态 |
|------|------|------|
| `workbench.py` | 工作流引擎 | ✅ |
| `calculation_engine.py` | AERMOD/Mike21 | ✅ |
| `compliance_checker.py` | 五合一审查 | ✅ |
| `collaborative_generator.py` | 人机协同 | ✅ |
| `document_parser.py` | 文档解析 | ✅ |
| `drawing_engine.py` | 绘图引擎 | ✅ |
| `export_manager.py` | 多格式导出 | ✅ |

### 10.3 LLM核心 (client/src/business/)

| 文件 | 功能 | 状态 |
|------|------|------|
| `global_model_router.py` | L0-L4分层 | ✅ |
| `llmcore/_nanogpt_src/` | nanoGPT源码 | ✅ |
| `expert_learning/` | 增量学习 | ✅ |
| `skill_evolution/` | 技能进化 | ✅ |

---

## 十一、开发规范

### 11.1 代码位置

```
✅ 新代码 → client/src/business/ (逻辑) 或 client/src/presentation/ (UI)
❌ 旧代码 → core/ 或 ui/ (已删除)
```

### 11.2 LLM调用

```python
# ✅ 正确: 通过GlobalModelRouter
from client.src.business.global_model_router import GlobalModelRouter, ModelCapability
router = GlobalModelRouter()
result = router.call_model_sync(ModelCapability.REASONING, prompt)

# ❌ 错误: 直接调用Ollama
import requests
requests.post("http://localhost:11434/api/generate")
```

### 11.3 工具注册

```python
# 每个工具必须实现register()函数
def register():
    from client.src.business.tools import tool_registry
    tool_registry.register(YourTool())

# 在registrar.py中导入
from .web_crawler_tool import register as register_web_crawler
register_web_crawler()
```

### 11.4 单元测试

```python
# tests/test_tool_registry.py
import pytest
from client.src.business.tools import tool_registry

def test_register_and_discover():
    tool_registry.register(TestTool())
    tools = tool_registry.discover("测试查询")
    assert len(tools) > 0
```

---

## 附录A：Docker部署 ⏸️ **推迟**

> Docker和容器化部署将在核心功能稳定后进行。

**待办项**:
- [ ] Docker镜像构建
- [ ] docker-compose编排
- [ ] 环境变量配置
- [ ] 健康检查
- [ ] 日志收集

---

## 附录B：MCP集成 ⏸️ **推迟**

> MCP (Model Context Protocol) 集成将在工具层完善后进行。

**待办项**:
- [ ] MCP协议研究
- [ ] MCP服务器适配
- [ ] stdio/HTTP双模式
- [ ] 工具发现注册
- [ ] 性能测试

---

## 变更日志

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.2 | 2026-04-28 | 新增极简设计理念章节（会话交互+需求澄清+渐进渲染UI） |
| v1.1 | 2026-04-28 | 新增参考借鉴章节（开源项目分析+框架借鉴+实施计划） |
| v1.0 | 2026-04-28 | 初始版本，按阶段任务重新组织 |

---

**下一步**: 开始P1任务 - 实现IntentClarifier意图澄清器
