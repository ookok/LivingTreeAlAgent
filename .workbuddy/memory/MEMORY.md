# MEMORY.md - 长期记忆

## Programming OS 范式革命（2026-04-24）

### 核心理念转变

用户提出：**从"带AI的编辑器"到"意图处理器"的范式革命**

| 传统 IDE | AI-IDE |
|----------|---------|
| 程序员手写每一行代码 | 程序员表达意图，AI 生成优化代码 |
| 键盘输入 → 编辑器 → 文件系统 | 意图 → 意图处理器 → 验证 → 版本控制 |
| 用户关心"怎么写" | 用户只关心"做什么" |

### 必须抛弃的 6 个传统组件

1. **文件浏览器** → 功能模块视图（用户只关心功能，不关心文件路径）
2. **代码编辑器** → 意图工作台（编辑器降级为预览窗口）
3. **命令行终端** → 自然语言执行
4. **Git 手动操作** → 变更容器（一键应用/撤销）
5. **测试运行** → 质量管道（自动运行，质量报告）
6. **配置文件** → 自动检测 + 意图配置

### MVP 定义（2-3周）

```
核心功能：
- 意图输入（自然语言）
- 意图理解（IntentEngine）
- 代码生成（模板）
- 代码预览（diff）
- 一键应用
- 质量报告

验证目标：
- 10 个测试意图中 7 个能直接生成可用代码
- 用户满意度 > 80%
```

### 新增核心模块设计

| 模块 | 位置 | 说明 |
|------|------|------|
| Intent Engine | `core/intent_engine/` | 完整意图理解，不只是分类 |
| VFS | `core/virtual_fs/` | 草稿区+快照+签入 |
| Permission Engine | `core/permission_engine/` | L1-L5 权限分级 |

### 自动驾驶愿景

```
L1: 代码补全、语法检查 ← 现状
L2: 生成简单函数、修复错误
L3: 明确场景完全接管 ← 我们的目标
L4: 处理复杂任务，人类偶尔干预
L5: 描述需求，完成设计到部署全过程
```

### 陷阱提醒

1. ❌ 不要兼容传统流程 → ✅ 强制纯 AI 驱动
2. ❌ 不要提供太多选项 → ✅ 自动选择最优
3. ❌ 不要暴露技术复杂性 → ✅ 透明在背后
4. ❌ 不要一步到位 → ✅ MVP 优先

### 大型工程性能优化（上下文经济学）

**核心矛盾**: 无限增长的上下文 vs 有限计算/内存

**核心策略**: 从"全知全能"转向"按需加载"

| 优化技术 | 说明 |
|----------|------|
| Context Triage | 意图类型 → 上下文策略 |
| Symbol Index | O(1) 符号查找，替代全文 grep |
| VFS 惰性加载 | 仅加载"脏"区域 |
| 意图预热 | 根据历史意图预加载索引 |
| 增量上下文 | 上下文累加，非重置 |
| 边缘缓存 | 高频意图结果缓存 |

**本地网关架构**:
```
[IDE Plugin] → [Local Gateway] → [LLM API]
             (索引/缓存/路由)
```

**核心原则**: "足够好"而非"完美"
- 等待30秒的AI → 被用户抛弃
- 3秒响应的AI → 用户体验更佳

### 意图保持型压缩（2026-04-24 新增）

**核心理念**: 不是"压缩"，而是"信息密度革命"。用 1% 的 Token 传递 99% 的意图。

| 技术 | 原理 | 压缩比 |
|------|------|--------|
| 代码签名化 | 保留函数签名+目的+依赖，丢弃实现细节 | 10:1 |
| 分层上下文金字塔 | L1-L5 按需加载，简单任务用高层摘要 | 5:1-50:1 |
| 意图编码 | 将自然语言编码为结构化查询 | 减少50%上下文需求 |
| 语义分块 | AST分析 + 重要性打分，优先保留关键节点 | 3:1-10:1 |

**Token价值评估体系**:
- 📈 高价值：接口定义、依赖关系、意图信息
- 📊 中等价值：核心逻辑、错误处理
- 📉 低价值：样板代码、重复模式
- 💨 零价值：注释空白、调试代码

**Token预算制度**:
- 简单任务：512 tokens
- 中等任务：2048 tokens
- 复杂任务：8192 tokens
- 深度分析：16384 tokens

**预处理管道**: 意图分析 → 上下文选择 → 代码压缩 → 意图编码 → LLM API → 后处理

### 推理式编程助手（2026-04-24 新增）

**核心设计**：推理引擎 + 可视化轨迹 + Git工作流三大支柱

| 组件 | 功能 | 特点 |
|------|------|------|
| 任务分解器 | OpenCode风格，递归分解任务 | 考虑依赖、产出、难点 |
| 推导链追踪 | 记录每个推理步骤 | alternatives + decision + reason |
| Git管理器 | 智能提交分组 | 推导过程存储在commit body |
| 时间旅行 | 回到任意决策点 | Git作为记忆系统 |

**多模型协作**：
- CodeAnalyzerModel：代码分析
- TaskPlannerModel：任务规划
- CoderModel：代码生成
- VerifierModel：验证

**MVP第一周**：
1. 基础IDE插件框架
2. 硬编码任务分解
3. 基础推导显示
4. 手动Git提交

### 端到端体验优化（2026-04-24 新增）

**核心洞察**：本地部署的"慢"不是因为模型弱，而是交互充满"摩擦"

| 摩擦类型 | 说明 | 解决方案 |
|---------|------|---------|
| 上下文切换 | 在IDE、终端、聊天窗口来回切换 | 上下文自动注入 |
| 等待摩擦 | 提问→等待→验证循环 | 预测性预加载 + 分层模型 |
| 执行摩擦 | 模型只能"说"，不能"做" | 工具调用 + 沙箱执行 |

**五大优化领域**：
1. **上下文感知**：项目级上下文注入、活跃文件感知
2. **延迟优化**：预测性预加载、渐进式输出、离线优先
3. **工具集成**：Function Calling、沙箱代码执行、调试器集成
4. **反馈循环**：偏好学习、质量评分、知识库RAG
5. **多模态**：图片理解、语音输入、插件生态

**目标**：从"需要伺候的聊天对象" → "能自主工作的副驾驶"

---

## Expert Learning 模块修复（2026-04-24）

### 缓存层 API 修复
`core/expert_learning/expert_guided_system.py` 修复：

1. **缓存调用修复**：`cache.get()` → `cache.get_l4()`
   - UnifiedCache 使用分层 API: `get_l0_route`/`set_l0_route`, `get_search`/`set_search`, `get_l4`/`set_l4`
   - 返回值是 `CacheHit` 对象，需用 `.data` 获取实际数据

2. **OllamaClient 修复**：
   - 不能直接传 `base_url` 参数，需用 `OllamaConfig(base_url=...)`
   - `chat()` 返回生成器，需用 `chat_sync()` 获取完整响应

3. **缓存填充逻辑**：专家不可用时也需缓存本地结果

### B) HermesAgent 深度集成（2026-04-24）

`core/agent_chat.py` 集成 ExpertLearning：

- `_init_expert_learning()`: 初始化专家学习系统
- `get_learning_stats()`: 获取学习统计（cache_hit_rate, corrections 等）
- 自动启用：enable_enhancement=True 时自动初始化

### C) 思维链蒸馏器（创新功能，2026-04-24）

`core/expert_learning/chain_of_thought_distiller.py` - 创新功能：

**核心功能**：
- 记录专家/本地模型的推理过程
- 提取思维链模板（因果/类比/演绎/归纳等）
- 相似问题自动匹配模板
- 提供推理提示注入

**模板结构**：
```python
ChainTemplate:
  - id: 模板ID
  - query_pattern: 问题关键词
  - query_type: 推理类型
  - reasoning_steps: 推理步骤列表
  - pattern: 模式摘要
  - usage_count: 使用次数
  - success_rate: 成功率
```

**使用方式**：
```python
distiller = ChainOfThoughtDistiller()

# 记录推理
distiller.record_reasoning(
    query="为什么天空是蓝色的",
    expert_reasoning="1. 识别光学问题 2. 瑞利散射...",
    local_reasoning="因为太阳光...",
    expert_answer="因为瑞利散射...",
    local_answer="因为太阳光..."
)

# 获取相似模板
template = distiller.get_template("为什么海水是蓝色")
hint = distiller.get_prompt_hint("为什么天空是蓝色")
```

## 用户模型配置（永久记住）

| 层级 | 模型 | 连接方式 | API Key | 用途 |
|------|------|----------|---------|------|
| **L0** | qwen2.5:0.5b | 远程 Ollama (http://www.mogoo.com.cn:8899/v1) | 无 | 快速路由/意图分类 |
| **L1** | qwen2.5:1.5b | 远程 Ollama | 无 | 轻量推理/搜索 |
| **L3** | qwen3.5:4b | 远程 Ollama | 无 | 推理/意图理解 |
| **L4** | qwen3.5:9b | 远程 Ollama | 无 | 深度生成/思考模式 |

> 远程服务: http://www.mogoo.com.cn:8899/v1（无 API Key）
> 测试通过: 2026-04-24

> ⚠️ 踩坑：qwen3.6:latest / qwen3.5:4b 是思考模型，API 返回 `content=""`，答案在 `thinking` 字段。
> 推荐压缩模型：`qwen2.5:1.5b`（非思考，干净中文输出，3-5s）

## 项目关键路径

- **统一缓存**: `unified_cache.py`（整合 L0/Search/L4 三层缓存 + 语义相似匹配）
- **深度搜索**: `core/fusion_rag/l4_executor.py` → `DeepSearchWikiSystem`
- **Skill 自进化**: `core/skill_evolution/agent_loop.py` → `SkillEvolutionAgent`

## 统一缓存增强（2026-04-23）

### 三级压缩策略（QueryCompressor）
- **≤300字**: Keyword 快缩（0延迟，提取关键词拼接）
- **300-500字**: LLM 语义压缩（qwen2.5:1.5b，保留意图+实体，0.5s）
- **>500字**: QueryChunker 分块（按句子/轮次切分，每块独立标准化）

### 关键代码位置
- `QueryCompressor` 类: `unified_cache.py` 增强1.5区域
- `QueryChunker` 类: 同上，按句子/轮次分块
- `QueryNormalizer.normalize()`: 集成压缩器，替换粗暴截断
- `_COMPRESS_MODELS` 列表: `QueryCompressor` 类头部

### Ollama 可用模型
```
smollm2-test:latest, gemma4:26b, qwen3.6:35b-a3b, qwen3.5:4b,
qwen3.5:2b, qwen3.6:latest, qwen3.5:9b, qwen3.5:0.8b,
qwen2.5:1.5b, qwen2.5:0.5b, deepseek-r1:70b
```

## Agent Chat 通用增强模块 (2026-04-24)

`core/agent_chat_enhancer.py` - 通用意图识别 + Query压缩 + 上下文管理

### 核心组件

| 组件 | 功能 |
|------|------|
| `ChatIntentClassifier` | 通用意图分类（16种意图，覆盖对话/推理/任务/创作/知识） |
| `QueryCompressor` | Query压缩（三档策略：轻/中/强） |
| `ChatContextManager` | 上下文管理（消息历史/Token控制/连续追问检测） |
| `EnhancedAgentChat` | 增强版 AgentChat 封装 |

### 通用意图类型（16种）

**对话类**: `GREETING`, `CHITCHAT`, `QUESTION`
**推理类**: `REASONING`, `MATHEMATICS`, `ANALYSIS`
**任务类**: `CODE_GENERATION`, `CODE_REVIEW`, `DEBUGGING`, `FILE_OPERATION`, `TASK_EXECUTION`
**创作类**: `WRITING`, `TRANSLATION`, `SUMMARIZATION`, `CREATIVE`
**知识类**: `KNOWLEDGE_QUERY`, `SEARCH`

### 模型选择建议

| 场景 | 模型 | 意图 |
|------|------|------|
| 代码生成 | L4 | `code_generation` |
| 代码审查/调试 | L3 | `code_review`, `debugging`, `reasoning` |
| 创作/摘要 | L3 | `writing`, `summarization`, `creative` |
| 翻译/搜索/闲聊 | L1 | `translation`, `search`, `chitchat` |
| 问候/计算 | L0 | `greeting`, `mathematics` |

### 使用示例

```python
from core.agent_chat_enhancer import enhance_agent_chat

chat = enhance_agent_chat(base_chat)
chat.set_intent_callback(lambda i: print(f"意图: {i.intent.value}"))

# 自动意图识别 + Query压缩 + 上下文管理
response = chat.chat("帮我调试这个bug")
```

### 测试结果

意图识别准确率: **100%**（19/19测试用例通过）

## Skill 自动创建机制

**触发条件**（`SkillEvolutionAgent._try_consolidate()`）：
1. 任务成功完成（status=COMPLETED）
2. 执行步骤 ≥ 2 步
3. 无完全相同的已有技能（高阈值 0.6 查重）

**创建流程**：
```
execute_task() → _run_autonomous_loop() → _finish_task()
→ _try_consolidate() → TaskSkill → 写入 L3 (SkillEvolutionDatabase)
```

**注意**：深度搜索链路（`HermesAgent` / `DeepSearchWikiSystem`）不触发 Skill 自动创建。
Skill 自进化只在 `SkillEvolutionAgent` 中生效。

## IntentEngine - 意图引擎核心模块（2026-04-24 新建）

`core/intent_engine/` - 实现"意图处理器"范式的核心

### 模块结构

| 文件 | 功能 |
|------|------|
| `intent_types.py` | 意图类型定义（IntentType 枚举、Intent 数据类） |
| `intent_parser.py` | 意图解析器（动作提取、目标提取、意图分类） |
| `tech_stack_detector.py` | 技术栈检测（语言/框架/数据库/工具/云服务） |
| `constraint_extractor.py` | 约束条件提取（性能/安全/格式/质量约束） |
| `composite_detector.py` | 复合意图检测（并列/顺序任务分解） |
| `intent_engine.py` | 主入口（整合各组件，提供统一 API） |

### 意图类型（30+ 种）

- **代码生成**: CODE_GENERATION, API_DESIGN, DATABASE_DESIGN, UI_GENERATION
- **代码修改**: CODE_MODIFICATION, CODE_REFACTOR, CODE_OPTIMIZATION
- **调试修复**: DEBUGGING, BUG_FIX, ERROR_RESOLUTION
- **代码理解**: CODE_UNDERSTANDING, CODE_EXPLANATION, CODE_REVIEW
- **测试验证**: TEST_GENERATION, SECURITY_CHECK, PERFORMANCE_ANALYSIS
- **运维部署**: DEPLOYMENT, CONFIGURATION, ENVIRONMENT_SETUP

### 使用方式

```python
from core.intent_engine import IntentEngine

engine = IntentEngine()
intent = engine.parse("帮我写一个用户登录接口，要用 FastAPI")

# 解析结果
print(intent.intent_type)   # api_design
print(intent.tech_stack)    # ['fastapi', 'python']
print(intent.action)        # 编写
print(intent.target)        # 用户登录接口
print(intent.constraints)   # [认证方式: jwt]
print(intent.confidence)   # 0.63
print(engine.suggest_model(intent))  # qwen3.5:9b
```

### 集成到 AgentChat

`core/agent_chat_enhancer.py` 中已集成 IntentEngine：

```python
chat = enhance_agent_chat(base_chat)
intent = chat.analyze_code_intent("帮我写一个用户登录接口")
```

---

## 用户偏好

- 回复语言：**中文**
- 输出格式：结构化（emoji、ASCII、层级缩进）
- 执行风格：**直接执行**，不确认，用户倾向一次性综合性任务
- 任务中断：用户发送"继续"指令催促执行

## 模型配置（永久记住，2026-04-23 更新）

### L0 模型（快速路由/意图分类）
- **首选**: `SmolLM2.gguf`（models 文件夹）
- **Fallback**: `qwen3.5:2b` → `qwen2.5:1.5b`
- **连接**: 本地 Ollama (`http://localhost:11434`)
- **用途**: 快速路由、意图分类

### L3 模型（推理/意图理解）
- **模型**: `qwen3.5:4b`
- **连接**: 本地 Ollama (`http://localhost:11434`)
- **用途**: 推理、意图理解

### L4 模型（深度生成/思考模式）
- **模型**: `qwen3.5:9b`
- **连接**: 本地 Ollama (`http://localhost:11434`)
- **用途**: 深度生成、思考模式

### 通用配置
- **API Key**: 无（本地部署）
- **测试用途**: 优先使用此配置进行测试

## L0-L4 组件复用（重要原则）

### 已有完整组件库，不要重复造轮子

| 功能 | 已有模块 | 路径 |
|------|---------|------|
| **意图分类** | `QueryIntentClassifier` | `core/fusion_rag/intent_classifier.py` |
| **智能路由** | `IntelligentRouter` | `core/fusion_rag/intelligent_router.py` |
| **结果融合** | `ResultFusion` | `core/search/result_fusion.py` |
| **L4感知路由** | `L4AwareRouter` | `core/fusion_rag/l4_aware_router.py` |
| **知识库** | `KnowledgeBaseLayer` | `core/fusion_rag/knowledge_base.py` |
| **向量存储** | `VectorDatabase` | `core/knowledge_vector_db.py` |
| **PageIndex** | `PageIndexBuilder` | `core/page_index/index_builder.py` |
| **LLM Wiki** | `LLMWikiGenerator` | `core/deep_search_wiki/wiki_generator.py` |

### 正确做法
1. **复用优先**：新功能应该组合已有组件，而非重新实现
2. **路由器 = 组合器**：只需调用已有模块，不需要重新写分类/融合
3. **测试文件**：`test_unified_router.py` 验证了 L0→L1-L2→L4 调用链

## Agent Chat 单一入口架构（2026-04-23）

### HermesAgent 工具注册机制
- HermesAgent._register_tools() 注册: file/terminal/writing/ollama 工具集
- 知识库工具需额外注册: `ToolRegistry.register(name, desc, schema, handler, "knowledge")`
- 工具调用链路: HermesAgent.send_message() → LLM 解析意图 → dispatcher.dispatch() → 工具执行

### 工具注册示例（2026-04-23 实测通过）
```python
from core.tools_registry import ToolRegistry

def read_aloud_handler(ctx, file_path="", max_chars=3000):
    content = read_file_text(file_path)
    speak_win(content[:max_chars])
    return {"success": True}

ToolRegistry.register(
    name="read_aloud",
    description="TTS朗读文件",
    parameters={"type":"object","properties":{"file_path":{"type":"string"},"max_chars":{"type":"integer"}},"required":["file_path"]},
    handler=read_aloud_handler,
    toolset="knowledge"
)
```

### SessionDB 事务错误修复
- 根因: 线程本地连接嵌套事务
- 修复: `agent.session_db._local.conn = None` → 重建会话
- 隔离测试: 使用独立 db 路径避免锁冲突
- 残留锁清理: `PRAGMA wal_checkpoint(TRUNCATE)` + 删除 -wal/-shm

## 智能学习系统六大模块（2026-04-24）

在 `core/expert_learning/` 下创建了完整的智能学习系统：

### 1. 离线自学习循环 `offline_learning_loop.py`
- **永不掉线机制**：4层降级策略（精确匹配→模式匹配→模板→紧急响应）
- **知识碎片管理**：基于哈希的精确匹配 + 关键词索引
- **自我进化**：成功率追踪、相似知识合并、低置信度清理
- **关键类**：`OfflineLearningLoop`, `KnowledgeFragment`

### 2. 知识一致性验证 `knowledge_consistency.py`
- **多模型并行推理**：支持异步并发调用
- **一致性检测**：Jaccard相似度 + 关键事实提取对比
- **投票决策**：多数投票 + 相似度投票
- **关键类**：`KnowledgeConsistencyVerifier`, `ConsensusLevel`

### 3. 自动模型选择 `auto_model_selector.py`
- **意图分类**：16种任务类型自动识别
- **复杂度评估**：长度/结构/领域/任务复杂度
- **动态选择**：基于擅长领域、历史表现、延迟、成本综合评分
- **关键类**：`AutoModelSelector`, `TaskType`, `IntentClassifier`

### 4. 成本优化引擎 `cost_optimizer.py`
- **预算管理**：日/周/月三级预算
- **智能切换**：FREE_ONLY/FREE_PREFERRED/BALANCED/QUALITY_FIRST 四种模式
- **节省追踪**：与假设全付费对比计算节省
- **关键类**：`CostOptimizer`, `CostMode`

### 5. 多模型对比 `multi_model_comparison.py`
- **并行推理**：同时调用多个模型
- **多维评估**：准确性/连贯性/简洁性/创意性/事实性
- **差异分析**：长度/结构/关键词差异检测
- **关键类**：`MultiModelComparison`, `ComparisonMetric`

### 6. 性能监控 `enhanced_performance_monitor.py`
- **实时监控**：延迟/质量/错误率/吞吐量
- **异常检测**：延迟过高/质量低/错误率飙升
- **趋势分析**：metric趋势（上升/下降/稳定）
- **关键类**：`EnhancedPerformanceMonitor`, `MetricType`

### 统一入口 `intelligent_learning_system.py`
- `IntelligentLearningSystem` 整合所有模块
- 单例模式全局访问
- 核心方法：`process()`, `learn()`, `get_status()`, `get_optimization_tips()`

### 使用示例
```python
from core.expert_learning import get_intelligent_learning_system

system = get_intelligent_learning_system({'daily_budget': 5.0})

# 注册模型
system.register_model('qwen_9b', 'qwen3.5:9b', client, {'strengths': ['reasoning']})

# 处理请求（自动选择最优策略）
result = system.process('解释量子计算原理')
print(result.content)

# 获取系统状态
status = system.get_status()
print(f"健康度: {status.system_health}")
```

### HermesAgent KB 类型（重要区别）
| 组件 | KB 类型 | 路径 |
|------|---------|------|
| HermesAgent.knowledge_base | KnowledgeBaseVectorStore | core/knowledge_vector_db.py |
| ExpertTrainingPipeline.kb | KnowledgeBaseLayer | core/fusion_rag/knowledge_base.py |

### TTS 依赖状态
- pywin32: 未安装 → Windows SAPI 不可用
- edge-tts: 未安装 → edge-tts 不可用
- 朗读回退: 仅打印文本到控制台

## 重构进度（2026-04-24）

### 已完成重构

| # | 重构项 | 文件 | 状态 | 说明 |
|---|--------|------|------|------|
| **R1** | 统一入口整合 | `core/unified_pipeline.py` | ✅ | 7步流水线，复用FusionRAG组件 |
| **R2** | 任务执行解耦 | `core/unified_task_executor.py` | ✅ | 串行/并行/DAG执行策略 |
| **R3** | 上下文统一管理 | `core/unified_context.py` | ✅ | 整合MemoryPalace/SessionDB |
| **R4** | 智能写作工作流 | `core/smart_writing/unified_workflow.py` | ✅ | 8阶段流水线 |
| **R5** | UI面板重构 | `ui/smart_writing_panel.py` | ✅ | 业务逻辑分离 |

### R4 SmartWritingWorkflow 架构

**8阶段流水线**：
```
需求澄清 → 知识检索 → 深度搜索 → 内容生成 → AI审核 → 分身辩论 → 虚拟会议 → 最终修订
```

**复用组件**：
- `AIEnhancedGeneration` - AI审核 + 分身辩论
- `ProjectGeneration` - 项目文档生成
- `WikiGenerator` - 深度搜索
- `KnowledgeBaseLayer` - 知识检索

### R4-1 智能写作增强模块（2026-04-24 增强版）

| 模块 | 文件 | 功能 |
|------|------|------|
| **计算模型库** | `core/smart_writing/calculation_models.py` | 通过CLI调用EIA引擎，NPV/IRR/排放量/LEC等20+计算 |
| **数据采集管道** | `core/smart_writing/data_collector.py` | 国家统计局/环境部/气象局/高德地图等政府+第三方API |
| **意图分类器** | `core/smart_writing/intent_classifier.py` | 动态识别文档类型，不固定枚举，多维度分类 |
| **交互式澄清** | `core/smart_writing/interactive_clarifier.py` | 引导式访谈、自动补全、与进化引擎集成 |
| **多模态生成** | `core/smart_writing/multimodal_generator.py` | 表格、图表、甘特图、流程图、公式生成 |
| **自进化引擎** | `core/smart_writing/self_evolution.py` | 经验积累/专家反馈/新类型识别/知识库集成 |

**集成系统**：
- `SkillEvolutionAgent` - 技能自进化
- `ExpertPanel` - 专家反馈
- `KnowledgeBaseVectorStore` - 知识存储
- `WikiGenerator` - 深度搜索
- `CLIAnything` + `EIA CalculationEngine` - 外部计算

**使用方式**：
```python
from core.smart_writing.self_evolution import get_evolution_engine
from core.smart_writing.intent_classifier import quick_classify

# 自进化引擎
engine = get_evolution_engine()
engine.learn_from_generation(requirement, doc_type, content, quality_score)
refs = engine.get_reference_documents(requirement, doc_type)
metrics = engine.get_metrics()

# 动态识别文档类型
result = quick_classify("上传的文件内容...")  # 不固定类型
```

### R5 SmartWritingPanel 架构

**UI分离原则**：
- UI层 (`SmartWritingPanel`): 负责展示和用户交互
- 业务层 (`SmartWritingWorkflow`): 负责核心逻辑
- 工作线程 (`WritingWorker`): 异步执行

### 已知问题
- `core/agent.py` 引用不存在的 `core.agent_progress` 模块
- 测试需绕过 `core/__init__.py` 直接加载模块
