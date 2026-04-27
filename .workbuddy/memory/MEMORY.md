# MEMORY.md - 长期记忆

## 用户模型配置（永久记住）

| 层级 | 模型 | 连接方式 | API Key | 用途 |
|------|------|----------|---------|------|
| **L0** | SmolLM2.gguf (models文件夹) → **fallback**: qwen3.5:2b | 本地 Ollama (http://localhost:11434) | 无 | 快速路由/意图分类 |
| **L3** | qwen3.5:4b | 本地 Ollama | 无 | 推理/意图理解 |
| **L4** | qwen3.6:latest | 本地 Ollama | 无 | 深度生成/思考模式 |

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

### HermesAgent KB 类型（重要区别）
| 组件 | KB 类型 | 路径 |
|------|---------|------|
| HermesAgent.knowledge_base | KnowledgeBaseVectorStore | core/knowledge_vector_db.py |
| ExpertTrainingPipeline.kb | KnowledgeBaseLayer | core/fusion_rag/knowledge_base.py |

### TTS 依赖状态
- pywin32: 未安装 → Windows SAPI 不可用
- edge-tts: 未安装 → edge-tts 不可用
- 朗读回退: 仅打印文本到控制台

## 硬件配置（2026-04-23 更新）

### GPU 配置
- **实际硬件**: 3x NVIDIA Tesla V100（SXM2）
  - GPU 0: Tesla V100-SXM2-16GB
  - GPU 1: Tesla V100-SXM2-32GB
  - GPU 2: Tesla V100-SXM2-16GB
  - **总 VRAM**: 64GB
- **层级**: `ultra`（自动识别）
- **GPU 检测**: `core/ai_capability_detector.py` → `_detect_gpu()`
  - 优先使用 `nvidia-smi`（最可靠）
  - 备用：pynvml → PowerShell Get-CimInstance → pygpu
  - **关键**：`core/knowledge_graph/` 是包目录（不是 `knowledge_graph.py`）

### 模型选举结果（ultra 层）
- **L0** (快速路由): `qwen3.5:2b`
- **L3** (意图理解): `qwen3.5:4b`
- **L4** (深度生成): `qwen3.6:35b-a3b`（思考模型，注意 `content=""` 问题）

## Ollama 模型自动加载（2026-04-23）

### auto-stop/auto-run 解决方案
- **问题**: Ollama 空闲时模型会被 stop（keep_alive 默认 5 分钟）
- **解决**: `OllamaClient.ensure_model_loaded()` + `get_loaded_models()`
- **机制**: chat() 前检查 `/api/ps`，模型未加载时发 `/api/generate` 触发重启
- **代码位置**: `core/ollama_client.py`

### Ollama 当前状态
- 已加载模型: `qwen2.5:1.5b`
- 可用模型: 11 个（qwen3.6:35b-a3b, gemma4:26b, deepseek-r1:70b 等）

## 意图分类机制（2026-04-23 新增）

### HermesAgent._classify_query_type() 三层路由
| 类型 | 特征 | 管道 |
|------|------|------|
| **dialogue** | 寒暄/情感/短句(≤12字) | L0模型，跳过KB/深度搜索 |
| **task** | 行动动词("帮我"/"写")/技术词 | KB搜索 + L3/L4模型 |
| **search** | 疑问词("是什么"/"为什么")/问号 | KB+深度搜索 + L4模型 |

### 分类优先级（2026-04-24 更新）
1. **搜索关键词** → search（优先判断，修复短句bug）
2. 疑问词开头 → search（除非有任务动词）
3. 行动动词 → task
4. 寒暄/情感/短句 → dialogue
5. 默认 → search

### Bug修复记录
- **2026-04-24**: "搜索 XXX" 等短句被错误分类为 dialogue
- **修复**: 增加搜索关键词（搜索/查找/查询/相关/资料）优先判断逻辑

### 关键坑
- `core/knowledge_graph/` 是**包目录**，导入 `core.knowledge_graph` 实际加载 `core/knowledge_graph/__init__.py`
- 正确添加方法到 `__init__.py`，不是 `knowledge_graph.py`（独立文件）
- Python `__pycache__` 会缓存旧代码，修改后需清理或重启进程

## 新增文件
- `core/model_election.py`: 硬件感知 L0/L3/L4 模型自动选举

## L0 意图识别升级（2026-04-24 新增）

### 架构：规则快速通道 + LLM 兜底
- `core/agent.py` → `L0IntentClassifier` 类
- **规则通道**（< 1ms）：frozenset 预编译词表 + 正则，80% 意图直接命中
- **LLM 兜底**（~2-5s）：规则未命中时调用 qwen2.5:1.5b 推断
- **反馈学习**：统计规则命中率，持续优化

### 分类类型（4类）
| 类型 | 特征 | 管道 |
|------|------|------|
| **dialogue** | 寒暄/情感/短句 | L0，跳过 KB/深度搜索 |
| **emotion_aware** | 情感词(好累/好烦) | L0 + 情绪感知 |
| **task** | 行动动词/技术词 | KB 搜索 + L3/L4 模型 |
| **search** | 疑问词/问号 | KB + 深度搜索 + L4 模型 |

### 关键代码位置
- `L0IntentClassifier`: `core/agent.py` 第 50-290 行
- `_classify_by_rules()`: frozenset 快速匹配
- `_classify_by_llm()`: LLM 兜底推断
- `classify()`: 主入口，规则优先 + LLM 兜底

## 情绪感知集成（2026-04-24 新增）

### EmotionalEncoder 已有的能力
- `core/living_tree_ai/neural_layer/emotional.py`
- **五维情感向量**: valence / arousal / dominance / intensity / duration
- **9 种情感类型**: JOY / SADNESS / ANGER / CALM / EXCITEMENT / FEAR / SURPRISE / DISGUST / NEUTRAL
- **情感共振计算**: 余弦相似度，0-1 范围
- **UI 效果映射**: 情感 → 颜色/动画/振动/背景

### HermesAgent 集成
- `send_message()` 中每次都调用 `EmotionVector.from_text_analysis()`
- 情绪状态注入 LLM 提示上下文
- **关心机制**: 用户连续负面情绪 → 主动表达关心

### 懒加载避免循环依赖
- `core/agent.py` → `_lazy_emotion_imports()` 函数
- 用 `importlib.util.spec_from_file_location` 直接加载 emotional.py
- 绕过 `living_tree_ai/__init__.py` 的问题导入链（task.py 不存在）

## 用户数字分身核心（2026-04-24 新增）

### UserDigitalTwin 类
- `core/agent.py` → `UserDigitalTwin` 类（第 290-490 行）
- **用户画像**: reply_style / language / preferred_model / max_response_length
- **学习积累**: intent_history / topic_history / tool_usage
- **情感记忆**: EmotionVector 追踪 + emotion_timeline（最近50条）
- **等级系统**: 每10次交互升1级

### 关键方法
| 方法 | 功能 |
|------|------|
| `record_interaction()` | 记录交互，更新情感和经验 |
| `should_express_care()` | 判断是否应表达关心 |
| `get_care_response()` | 生成关心语句 |
| `get_context_for_prompt()` | 生成 LLM 提示上下文 |
| `to_dict() / from_dict()` | 序列化/反序列化 |

### 全局管理器
- `get_user_digital_twin(user_id)`: 单例模式，全局注册表
- 数字分身在 `HermesAgent._init_model_client()` 中初始化

### 数字分身上下文注入
- `_build_enhanced_prompt()` 包含数字分身信息
- 注入内容: 情感状态 / 近期趋势 / 高频话题 / 关心建议 / 分身等级

## 模型选举缓存机制（2026-04-24 确认）

### `model_election.py` 已有缓存
- `_election_cache`: 模块级变量，同一进程只选举一次
- `get_elected_models(force_refresh=False)`: 首次调用时执行，之后返回缓存
- **无需每次调用**，同一 HermesAgent 实例共享缓存

### 循环导入解决
- `from __future__ import annotations` 避免类型注解求值问题
- 所有情绪相关类型用延迟导入或字符串注解

## 知识库创新模块（2026-04-24 新增）

### 核心文件
| 文件 | 功能 |
|------|------|
| `core/knowledge_innovation.py` | 5条创新功能实现 |
| `core/knowledge_hooks.py` | 知识库钩子集成器 |

### 5条创新功能

#### 1. 语义去重引擎 (SemanticDeduplicator)
- **原理**: 关键词哈希向量化 + 余弦相似度
- **阈值**: 0.85（超过判定重复）
- **优化**: 短文本快速哈希，长文本LLM向量化

#### 2. 知识价值评估系统 (KnowledgeValueScorer)
- **四维度评分**: 引用(30%) + 权威(20%) + 时效(20%) + 反馈(30%)
- **衰减因子**: 指数衰减，半衰期180天

#### 3. 主动学习触发器 (ActiveLearningTrigger)
- **FAQ生成**: 同一问题被问3次 → 生成FAQ
- **知识缺口**: 搜索无结果2次 → 标记缺口
- **用户纠正**: 记录纠正，更新知识库

#### 4. 知识图谱增强 (KnowledgeGraphEnhancer) - 中文优化
- **实体提取**: 人名/机构/地点/技术/概念
- **关系提取**: is_a/part_of/uses/requires/related_to
- **路径发现**: BFS查找实体间关系路径
- **中文优化**: 关系模式使用`[^，。；、\s]`精确匹配，避免过度捕获
- **停用词表**: 排除常见无意义词汇
- **置信度**: 动态调整，精确匹配+0.1~0.15

#### 5. 遗忘机制 + 强化复习 (ForgettingMechanism)
- **SM-2变体算法**: 记忆强度0-1，复习间隔倍增
- **状态**: ACTIVE → REVIEW_NEEDED → DECAYING → FORGOTTEN
- **每日衰减**: 0.001，不常用知识加速遗忘

### 钩子集成
```python
from core.knowledge_hooks import setup_knowledge_hooks, get_hook_manager

# 设置钩子
manager = setup_knowledge_hooks(agent)

# 手动触发
manager.on_deep_search_complete(query, results)
manager.on_session_end(session_id, messages)
```

### 核心模块
| 文件 | 功能 |
|------|------|
| `core/knowledge_auto_ingest.py` | 知识自动摄入、去重、质量评分、GC |
| `core/deep_search_kb_integration.py` | 深度搜索/会话与知识库集成 |

### 已有功能 vs 缺失功能

| 功能 | 状态 | 位置 |
|------|------|------|
| 知识库存储 | ✅ 已实现 | `KnowledgeBaseLayer` / `VectorDatabase` |
| 会话历史持久化 | ✅ 已实现 | `SessionDB` (FTS5全文搜索) |
| 文件清理策略 | ⚠️ 部分 | `CleanupManager` (仅文件，无KB) |
| 深度搜索结果→KB | ❌ 未实现 | 需要集成钩子 |
| 会话内容→KB | ❌ 未实现 | 需要自动提取 |
| KB智能清理 | ❌ 未实现 | 需要TTL/LRU/去重 |

### 新增模块

#### `KBAutoIngest` - 知识自动摄入器
- **来源类型**: DEEP_SEARCH / CONVERSATION / USER_FILE / EXPERT_TRAINING / MANUAL
- **去重**: MD5哈希 + 语义相似度（0.85阈值）
- **质量评分**: HIGH(3) / MEDIUM(2) / LOW(1) / GARBAGE(0)

#### `KnowledgeBaseGC` - 知识库垃圾回收
- **TTL策略**: 搜索结果30天 / 会话内容90天 / 用户文件1年 / 手动添加永不过期
- **LRU策略**: 访问次数<3且质量低 → 待删除
- **存储限制**: 最大10万条 / 500MB
- **清理比例**: 每次10%

#### `DeepSearchKBIntegration` - 深度搜索集成
- `ingest_search_results()`: 自动摄入搜索结果
- `ingest_deep_search_result()`: 摄入Wiki内容+来源URL
- `ingest_session()`: 提取问题+事实并存入KB
- `query_knowledge()`: 统一查询接口

#### `ConversationExtractor` - 会话内容提取
- **提取问题**: 问号结尾/疑问词开头
- **提取事实**: 陈述句/列表项
- **重要性评分**: 0-1分，基于关键词和长度

### 集成钩子使用
```python
from core.deep_search_kb_integration import get_ds_kb_integration

ds_kb = get_ds_kb_integration()
ds_kb.setup_hooks()  # 注册自动钩子

# 深度搜索完成后
ds_kb.ingest_search_results(query, results, source="deep_search")

# 会话结束后
ds_kb.ingest_session(session_id, messages)

# 定时GC
from core.knowledge_auto_ingest import get_kb_gc
gc = get_kb_gc()
gc.run_gc(dry_run=False)  # 执行清理
```

## 增强搜索系统（2026-04-25 新增）

### 核心文件
| 文件 | 功能 |
|------|------|
| `core/knowledge_vector_db_persistent.py` | 持久化知识库（ChromaDB）+ 错别字纠错 |
| `core/search_engine_monitor.py` | 搜索引擎健康检测与自动切换 |
| `core/enhanced_search.py` | 统一增强搜索接口 |

### ChineseTypoCorrector - 错别字纠错
- **原理**: 形近字 + 音近字 混淆表
- **关键映射**: `鹏 → 朋`（吉奥环鹏 → 吉奥环朋）
- **用户反馈**: 自动保存到 `~/.hermes-desktop/typo_feedback.json`
- **使用**:
```python
from core.knowledge_vector_db_persistent import ChineseTypoCorrector
corrector = ChineseTypoCorrector()
result = corrector.correct("吉奥环鹏")
print(result.corrected)  # "吉奥环朋"
print(result.corrections)  # [('鹏', '朋')]
```

### PersistentKnowledgeBase - ChromaDB 持久化
- **存储**: `~/.hermes-desktop/knowledge_db/`
- **功能**: 向量搜索、元数据过滤、自动去重
- **使用**:
```python
from core.knowledge_vector_db_persistent import PersistentKnowledgeBase
kb = PersistentKnowledgeBase()
kb.add(content="知识内容", source="搜索", query="关联查询")
results = kb.search_with_correction("吉奥环鹏")
```

### SearchEngineMonitor - 搜索引擎健康检测
- **检测引擎**: 360搜索、必应、搜狗、百度、DuckDuckGo
- **状态**: HEALTHY / DEGRADED / UNHEALTHY / UNKNOWN
- **自动排序**: 按响应时间和成功率排序
- **当前可用**: 360搜索（1.04s）> 必应（1.36s）> 搜狗（2.30s）

### EnhancedSearch - 统一搜索接口
```python
from core.enhanced_search import get_enhanced_search

search = get_enhanced_search()
results = await search.search("吉奥环鹏")
# 自动：纠错 → 知识库搜索 → 联网搜索 → 结果融合
```

### 已修复问题（2026-04-24）
1. **知识库搜索报错**: `KnowledgeBaseVectorStore` 添加 `search()` 方法
2. **深度搜索超时**: TierRouter 超时从 10s 增加到 30s
3. **web_search 降级**: 添加 `_web_search_fallback()` 方法
4. **错别字纠错**: 添加 `_fix_typo()` 方法（鹏→朋）
5. **知识库自动存储**: 添加 `_store_search_results_to_kb()` 方法

### 吉奥环朋企业信息（已存入知识库）
- **吉奥环朋科技（江苏）有限公司**: 2021年成立，注册资本5000万，南京市雨花台区
- **吉奥环朋科技（扬州）有限公司**: 2021年成立，注册资本12250万
- **业务**: 新兴能源技术研发、锂电池回收利用

## Agent 进度反馈系统（2026-04-25 新增）

### 核心文件
| 文件 | 功能 |
|------|------|
| `core/agent_progress.py` | 进度反馈系统（阶段化、百分比、流式 thinking） |
| `_test_agent_progress.py` | 进度系统测试脚本 |

### ProgressPhase 阶段定义
```
IDLE → INTENT_CLASSIFY → KNOWLEDGE_SEARCH → DEEP_SEARCH 
     → MODEL_ROUTE → LLM_GENERATING → COMPLETED
```

### 进度回调使用
```python
from core.agent_progress import AgentProgress, ProgressEmitter, ProgressPhase

# 方式1：直接使用发射器
def on_progress(prog: AgentProgress):
    print(f"[{prog.percent}%] {prog.message}")
    if prog.thinking:
        print(f"  Thinking: {prog.thinking}")

emitter = ProgressEmitter(on_progress)
emitter.start()
emitter.emit_phase(ProgressPhase.KNOWLEDGE_SEARCH, "搜索知识库...")
emitter.complete()

# 方式2：集成到 HermesAgent
agent = HermesAgent(config)
agent.callbacks.progress = on_progress
for chunk in agent.send_message("你好"):
    print(chunk.delta, end="")
```

### ChromaDB 懒加载优化
```python
# 旧：同步初始化（阻塞）
kb = PersistentKnowledgeBase(lazy=False)  # ~2-5秒

# 新：懒加载（毫秒级）
kb = PersistentKnowledgeBase(lazy=True)  # <10ms
# 首次使用时自动初始化
results = kb.search("query")
```

### 任务队列系统（已存在）
- `core/task_queue.py` - TaskQueue 类
- 支持并行任务、优先级、进度回调
- 测试通过：并行执行 3 个任务成功

## 模型能力检测系统（2026-04-25 新增）

### 核心文件
| 文件 | 功能 |
|------|------|
| `core/model_capabilities.py` | 模型能力检测（thinking + 多模态） |
| `_test_model_capabilities.py` | 能力检测测试脚本 |

### 能力类型
1. **Thinking 能力**
   - `NONE`: 不支持 thinking
   - `STREAMING`: 支持流式 thinking 输出
   - `FINAL_ONLY`: 仅最终返回 thinking

2. **多模态能力**
   - `TEXT_ONLY`: 仅文本
   - `VISION`: 支持图片
   - `AUDIO`: 支持音频
   - `VIDEO`: 支持视频
   - `FULL`: 全部支持

### 使用方式
```python
from core.model_capabilities import (
    get_capability_detector,
    MultimodalMessageFilter,
    ThinkingCapability,
    MultimodalCapability,
)

# 检测模型能力
detector = get_capability_detector()
caps = detector.detect("qwen3.6:35b-a3b")

print(caps.can_think())         # True
print(caps.can_stream_think())  # True
print(caps.supports_image())    # False

# 过滤不支持的多模态内容
filter = MultimodalMessageFilter(detector)
filtered, removed = filter.filter_messages(
    model_name="qwen2.5:1.5b",
    messages=[{"role": "user", "content": [{"type": "image_url", ...}]}]
)
# removed = ["图片 (image_url)"]
```

### HermesAgent 集成
```python
agent = HermesAgent(config)

# 获取当前模型能力
caps = agent.get_model_capabilities()
print(caps.get_capability_summary())

# 检查多模态支持
agent.check_multimodal_support("image")  # False

# 过滤多模态消息
filtered, removed = agent.filter_multimodal_message(messages)
```

### 模型能力映射表
| 模型 | Thinking | 多模态 | 说明 |
|------|----------|--------|------|
| qwen3.6:* | ✅ STREAMING | TEXT_ONLY | 思考模型 |
| qwen3.5:* | ✅ STREAMING | TEXT_ONLY | 思考模型 |
| deepseek-r1:* | ✅ STREAMING | TEXT_ONLY | 思考模型 |
| qwen2.5:* | ❌ | TEXT_ONLY | 普通模型 |
| llava:* | ❌ | VISION | 视觉模型 |
| qwen2.5-vl:* | ❌ | VISION | 视觉模型 |
| qwen2.5-omni:* | ❌ | FULL | 全能模型 |

### 流式 thinking 策略
- 模型支持 `can_stream_think()` → 启用 `reasoning_callback`，实时输出 thinking
- 模型不支持 thinking → 不传递回调，避免无效输出

## 任务分解系统（2026-04-25 新增）

### 核心文件
| 文件 | 功能 |
|------|------|
| `core/task_decomposer.py` | 任务分解核心模块 |
| `_test_task_decomposer.py` | 分解系统测试脚本 |

### 核心组件
1. **SubTask** - 子任务数据模型
2. **TaskDecomposition** - 分解结果容器
3. **TaskDecomposer** - 任务分解器（支持 LLM 智能分解和规则分解）
4. **SubTaskExecutor** - 子任务执行器（支持串行/并行/DAG）

### 执行策略
- `SEQUENTIAL`: 串行执行（按顺序）
- `PARALLEL`: 并行执行（同时）
- `DAG`: 依赖图执行（按依赖关系）

### 使用方式
```python
from core.task_decomposer import (
    TaskDecomposer,
    SubTaskExecutor,
    TaskDecompositionCallbacks,
)

# 分解任务
decomposer = TaskDecomposer()
decomp = decomposer.decompose("实现用户认证系统")

print(f"策略: {decomp.strategy.value}")
print(f"子任务: {len(decomp.subtasks)}")
for task in decomp.subtasks:
    print(f"  - {task.title}")

# 执行子任务
executor = SubTaskExecutor()
for state in executor.execute_stream(decomp):
    print(f"进度: {state.progress_percent:.0f}%")
```

### HermesAgent 集成
```python
# 自动任务分解（send_message 中）
agent = HermesAgent(config)

# 设置回调
callbacks = AgentCallbacks(
    task_decomposition=lambda d: print(f"分解完成: {d.total_tasks} 个子任务"),
    task_progress=lambda s: print(f"进度: {s.progress_percent:.0f}%"),
)

# 发送复杂任务自动触发分解
for chunk in agent.send_message("实现用户认证系统"):
    print(chunk.delta, end="")
```

### 触发条件
任务长度 >= 20 字 且 包含复杂动词：
- 实现、开发、构建、设计、架构
- 重构、优化、迁移、集成、部署
- 分析、调研、研究、比较、评估
- 修复、调试、排查、解决
- 搭建、配置、安装、设置

### UI 回调接口
```python
@dataclass
class AgentCallbacks:
    task_decomposition: Optional[Callable[[TaskDecomposition], None]] = None  # 分解完成
    task_progress: Optional[Callable[[TaskDecomposition], None]] = None      # 子任务进度
```

### 便捷方法
```python
agent.should_decompose_task(task)      # 判断是否需要分解
agent.decompose_task(task)            # 手动分解任务
agent.get_current_decomposition()      # 获取当前分解结果
agent.interrupt_task()                # 中断任务执行
agent.execute_decomposition(decomp)     # 手动执行分解

## 智能任务执行引擎（2026-04-25 新增）

### 核心文件
| 文件 | 功能 |
|------|------|
| `core/task_execution_engine.py` | 智能任务执行引擎 |
| `ui/task_tree_widget.py` | PyQt6 任务树可视化组件 |
| `ui/agent_chat_with_tasks.py` | Agent Chat + 任务分解集成示例 |

### 核心组件
1. **SmartDecomposer** - 智能分解器（LLM + 规则混合）
2. **SmartTaskExecutor** - 智能执行引擎
3. **TaskContext** - 任务上下文管理
4. **TaskNode** - 任务节点（支持树形结构）
5. **TaskTreeWidget** - PyQt6 可视化组件

### 智能触发条件
| 判断依据 | 示例 |
|----------|------|
| 高优先级动词 | 实现、开发、构建、设计、架构、搭建 |
| 复杂度模式 | "包括.*、.*包括" 多项目并列 |
| 任务长度 | > 100 字符 |
| LLM 辅助 | 可选的 LLM 判断 |

### 上下文管理
```python
context = TaskContext(original_task="用户原始任务")

# 共享变量
context.set_var("file_path", "/path/to/file")
context.get_var("file_path")  # -> "/path/to/file"

# 结果缓存
context.add_result("node_id", {"status": "success"})

# 错误记录
context.add_error("node_id", "错误信息", "traceback")
```

### 失败恢复机制
```python
# 重试策略（指数退避）
node.max_retries = 3  # 最多重试 3 次

# 跳过失败任务
executor.skip_failed(nodes)

# 重试失败任务
executor.retry_failed(nodes)

# 中断执行
executor.interrupt()
```

### 执行层数控制
```python
decomposer = SmartDecomposer(max_depth=3)  # 最大分解深度
executor = SmartTaskExecutor(max_depth=3)  # 最大执行深度
```

### PyQt6 UI 组件
```python
from ui.task_tree_widget import TaskTreeWidget

widget = TaskTreeWidget()
widget.set_nodes(task_nodes)
widget.set_title("任务分解")

# 连接信号
widget.task_selected.connect(lambda id, data: print(f"Selected: {id}"))
widget.retry_requested.connect(lambda id: retry(id))
widget.interrupt_requested.connect(interrupt)
```

### 执行策略
| 策略 | 说明 |
|------|------|
| SEQUENTIAL | 串行执行 |
| PARALLEL | 并行执行 |
| DAG | 依赖图执行 |

### 测试结果
```
[1] Intelligent Decomposition Test
  "写一个函数" -> False (50%)
  "实现用户认证系统" -> True (50%), parallel, depth=3
  "帮我搭建微服务架构" -> True (90%), depth=2
  "优化这个查询性能" -> False (50%)

[2] Execution Engine Test
  3/3 tasks completed, success_rate: 100%
```

```





