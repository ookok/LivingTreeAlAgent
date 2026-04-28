# LivingTreeAlAgent 架构开发指南

**文档版本**: v1.0  
**创建日期**: 2026-04-28  
**状态**: 📋 **规划中** - 按阶段任务组织

---

## 文档结构

1. [一、项目现状](#一项目现状)
2. [二、架构概览](#二架构概览)
3. [三、阶段一：工具层基础设施](#三阶段一工具层基础设施)
4. [四、阶段二：工具模块改造](#四阶段二工具模块改造)
5. [五、阶段三：智能体集成](#五阶段三智能体集成)
6. [六、阶段四：新建缺失工具](#六阶段四新建缺失工具)
7. [七、阶段五：自我进化引擎](#七阶段五自我进化引擎)
8. [八、已实现模块清单](#八已实现模块清单)
9. [九、开发规范](#九开发规范)
10. [附录A：Docker部署](#附录adocker部署) ⏸️ **推迟**
11. [附录B：MCP集成](#附录bmcp集成) ⏸️ **推迟**

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

## 三、阶段一：工具层基础设施

**目标**: 搭建工具注册与调用框架  
**状态**: ✅ **已完成**  
**工时**: 1-2小时

### 3.1 已交付文件

```
client/src/business/tools/
├── __init__.py
├── tool_registry.py      # ✅ ToolRegistry单例类
├── base_tool.py          # ✅ BaseTool抽象基类
├── tool_definition.py    # ✅ ToolDefinition数据类
├── tool_result.py        # ✅ ToolResult数据类
└── registrar.py         # ✅ 统一注册入口
```

### 3.2 核心接口

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

### 3.3 使用示例

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

## 四、阶段二：工具模块改造

**目标**: 将18个已有模块封装为标准化工具  
**状态**: 🔄 **进行中**  
**工时**: 3-4小时

### 4.1 已完成改造

| 类别 | 工具 | 状态 |
|------|------|------|
| 文本处理 | TextCorrectionTool (错别字纠正) | ✅ |
| 自我进化 | ToolSelfRepairer (自我修复) | ✅ |
| 工具编排 | ToolChainOrchestrator | ✅ |
| 主动发现 | ProactiveDiscoveryAgent | ✅ |

### 4.2 待改造清单

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

### 4.3 改造模板

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

## 五、阶段三：智能体集成

**目标**: 让智能体通过ToolRegistry调用工具  
**状态**: ✅ **已完成**  
**工时**: 2-3小时

### 5.1 已集成模块

```
✅ BaseToolAgent基类 (client/src/business/hermes_agent/base_agents/base_agent.py)
✅ HermesAgent工具调用
✅ EIAgent工具调用
✅ 语义搜索发现
```

### 5.2 智能体工作流

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

## 六、阶段四：新建缺失工具

**目标**: 补齐P0/P1优先级工具  
**状态**: 📋 **规划中**  
**工时**: 按需

### 6.1 P0 - 立即开始

| 工具 | 功能 | 工时 | 依赖 |
|------|------|------|------|
| **MarkdownExporter** | HTML/DOCX → Markdown | 1天 | markdown库 |

### 6.2 P1 - 近期完成

| 工具 | 功能 | 工时 | 依赖 |
|------|------|------|------|
| **CGCS2000Converter** | 坐标转换(WGS84↔CGCS2000) | 3天 | pyproj |
| **ProgressiveUIRenderer** | 分步式地图生成向导 | 3天 | drawing_engine |
| **IntentionClarifier** | 用户意图澄清对话 | 2天 | hermes_agent |

### 6.3 P2 - 优化迭代

| 工具 | 功能 | 工时 | 状态 |
|------|------|------|------|
| **IncrementalFineTuner** | 增量微调管道 | 5天 | nanoGPT, peft |
| **AISectionGenerator** | AI增强章节生成 | 3天 | GlobalModelRouter |
| **TemplateEngine** | 文档模板引擎 | 2天 | MarkdownExporter |

---

## 七、阶段五：自我进化引擎

**目标**: 让系统具备自我进化能力  
**状态**: 🔄 **部分完成**  
**工时**: 3-5天

### 7.1 已实现组件

```
✅ ToolSelfRepairer (工具自我修复)
✅ HardVariantGenerator (难例变体生成)
✅ DualFlywheel (双数据飞轮)
✅ SelfReflectionEngine (自我反思)
```

### 7.2 待实现组件

| 组件 | 功能 | 状态 |
|------|------|------|
| **ToolMissingDetector** | 工具缺失检测 | 🔲 |
| **AutonomousToolCreator** | 自主工具创建 | 🔲 |
| **ActiveLearningLoop** | 主动学习循环 | 🔲 |
| **SafeAutonomousToolCreator** | 安全创建器(沙箱) | 🔲 |

### 7.3 进化流程

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

## 八、已实现模块清单

### 8.1 工具层 (client/src/business/tools/)

| 文件 | 功能 | 状态 |
|------|------|------|
| `tool_registry.py` | 工具注册中心 | ✅ |
| `base_tool.py` | 工具基类 | ✅ |
| `tool_definition.py` | 工具定义 | ✅ |
| `tool_result.py` | 工具结果 | ✅ |
| `registrar.py` | 统一注册 | ✅ |
| `text_correction_tool.py` | 错别字纠正 | ✅ |
| `mcp_tool_adapter.py` | MCP适配器 | ✅ |

### 8.2 EIA系统 (client/src/business/ei_agent/)

| 文件 | 功能 | 状态 |
|------|------|------|
| `workbench.py` | 工作流引擎 | ✅ |
| `calculation_engine.py` | AERMOD/Mike21 | ✅ |
| `compliance_checker.py` | 五合一审查 | ✅ |
| `collaborative_generator.py` | 人机协同 | ✅ |
| `document_parser.py` | 文档解析 | ✅ |
| `drawing_engine.py` | 绘图引擎 | ✅ |
| `export_manager.py` | 多格式导出 | ✅ |

### 8.3 LLM核心 (client/src/business/)

| 文件 | 功能 | 状态 |
|------|------|------|
| `global_model_router.py` | L0-L4分层 | ✅ |
| `llmcore/_nanogpt_src/` | nanoGPT源码 | ✅ |
| `expert_learning/` | 增量学习 | ✅ |
| `skill_evolution/` | 技能进化 | ✅ |

---

## 九、开发规范

### 9.1 代码位置

```
✅ 新代码 → client/src/business/ (逻辑) 或 client/src/presentation/ (UI)
❌ 旧代码 → core/ 或 ui/ (已删除)
```

### 9.2 LLM调用

```python
# ✅ 正确: 通过GlobalModelRouter
from client.src.business.global_model_router import GlobalModelRouter, ModelCapability
router = GlobalModelRouter()
result = router.call_model_sync(ModelCapability.REASONING, prompt)

# ❌ 错误: 直接调用Ollama
import requests
requests.post("http://localhost:11434/api/generate")
```

### 9.3 工具注册

```python
# 每个工具必须实现register()函数
def register():
    from client.src.business.tools import tool_registry
    tool_registry.register(YourTool())

# 在registrar.py中导入
from .web_crawler_tool import register as register_web_crawler
register_web_crawler()
```

### 9.4 单元测试

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
| v1.0 | 2026-04-28 | 初始版本，按阶段任务重新组织 |

---

**下一步**: 开始阶段四P0任务 - 实现MarkdownExporter
