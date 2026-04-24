# LivingTreeAI Agent 系统架构文档

> 生成时间: 2026-04-24
> 项目状态: 双代码库并行（Legacy + New）

---

## 1. 系统整体架构

### 1.1 架构概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          PyQt6 GUI (HomePage)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  Agent Chat │  │ 深度搜索Wiki │  │ 专家训练Pipeline│  │ 智能写作Smart │   │
│  │ (agent_chat)│  │(deep_search)│  │(expert_train)│  │  Writing    │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
│         │                │                │                │          │
│         └────────────────┼────────────────┼────────────────┘          │
│                          │                │                           │
│                    ┌─────▼─────────────────▼─────┐                     │
│                    │      HermesAgent (核心)      │                     │
│                    │  ┌──────────────────────┐   │                     │
│                    │  │ ToolRegistry + Dispatcher│   │                     │
│                    │  └──────────────────────┘   │                     │
│                    └───────────────┬──────────────┘                     │
│                                    │                                    │
│         ┌──────────────────────────┼──────────────────────────┐        │
│         │                          │                          │        │
│   ┌─────▼─────┐            ┌──────▼──────┐           ┌──────▼──────┐ │
│   │ L0 Router │            │  FusionRAG   │           │SkillEvolution│ │
│   │(意图分类)  │            │ (多源检索)   │           │ (技能自进化) │ │
│   └─────┬─────┘            └──────┬──────┘           └──────┬──────┘ │
│         │                          │                          │        │
│         └──────────────────────────┼──────────────────────────┘        │
│                                    │                                    │
│   ┌────────────────────────────────┼────────────────────────────────┐  │
│   │                    Unified Cache (三级缓存)                       │  │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │  │
│   │  │L0 Cache  │  │ L1 Mem   │  │ L2 SQLite│  │ L3 Semantic  │  │  │
│   │  │(LRU)     │  │(热度加权) │  │  (WAL)   │  │  (FAISS)     │  │  │
│   │  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │  │
│   └────────────────────────────────────────────────────────────────┘  │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                          Ollama (本地 LLM)                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ SmolLM2  │  │ qwen3.5  │  │ qwen3.6  │  │ qwen2.5  │              │
│  │ (意图分类)│  │ (推理)   │  │ (深度生成)│  │ (压缩)   │              │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 双代码库策略

| 层级 | Legacy (core/ + ui/) | New (client/src/) | 状态 |
|------|---------------------|-------------------|------|
| **业务逻辑** | `core/` (~243 dirs, ~300+ modules) | `client/src/business/` | 共存迁移中 |
| **展示层** | `ui/` (PyQt6) | `client/src/presentation/` | 共存迁移中 |
| **基础设施** | 分散在 core/ | `client/src/infrastructure/` | 新建 |

---

## 2. 已实现核心模块清单

### 2.1 Agent 核心系统

| 模块 | 文件路径 | 功能描述 | 状态 |
|------|---------|---------|------|
| **HermesAgent** | `core/agent.py` | Agent 主类，消息处理，工具调用 | ✅ 已实现 |
| **OllamaClient** | `core/ollama_client.py` | 本地 LLM 调用封装 | ✅ 已实现 |
| **ToolRegistry** | `core/tools_registry.py` | 工具注册与分发 | ✅ 已实现 |
| **SessionDB** | `core/session_db.py` | 会话持久化 (SQLite) | ✅ 已实现 |
| **MemoryManager** | `core/memory_manager.py` | 记忆管理 | ✅ 已实现 |

### 2.2 意图分类与路由

| 模块 | 文件路径 | 功能描述 | 状态 |
|------|---------|---------|------|
| **QueryIntentClassifier** | `core/fusion_rag/intent_classifier.py` | 查询意图分类 (factual/conversational/procedural/creative) | ✅ 已实现 |
| **IntelligentRouter** | `core/fusion_rag/intelligent_router.py` | 动态路由决策，权重调整 | ✅ 已实现 |
| **L4AwareRouter** | `core/fusion_rag/l4_aware_router.py` | L4 层感知路由 | ✅ 已实现 |
| **L4RelayExecutor** | `core/fusion_rag/l4_executor.py` | L4 执行器，Relay 网关集成 | ✅ 已实现 |

### 2.3 深度搜索系统

| 模块 | 文件路径 | 功能描述 | 状态 |
|------|---------|---------|------|
| **DeepSearchWikiSystem** | `core/deep_search_wiki/wiki_generator.py` | Wiki 风格深度搜索生成 | ✅ 已实现 |
| **SmartSearchEngine** | `core/deep_search_wiki/search_engine.py` | 多源搜索聚合 | ✅ 已实现 |
| **CredibilityEvaluator** | `core/deep_search_wiki/credibility.py` | 来源可信度评估 | ✅ 已实现 |
| **WikiModels** | `core/deep_search_wiki/models.py` | Wiki 数据结构定义 | ✅ 已实现 |

### 2.4 RAG 与知识库

| 模块 | 文件路径 | 功能描述 | 状态 |
|------|---------|---------|------|
| **KnowledgeBaseLayer** | `core/fusion_rag/knowledge_base.py` | 深度文档检索，混合索引 (向量+BM25) | ✅ 已实现 |
| **KnowledgeBaseVectorStore** | `core/knowledge_vector_db.py` | 向量数据库，支持 Chroma/FAISS | ✅ 已实现 |
| **FusionEngine** | `core/fusion_rag/fusion_engine.py` | 多源结果融合 | ✅ 已实现 |
| **ExactCacheLayer** | `core/fusion_rag/exact_cache.py` | L4 精确缓存 (LRU+SimHash) | ✅ 已实现 |
| **WriteBackCache** | `core/fusion_rag/write_back_cache.py` | 异步回填缓存 | ✅ 已实现 |

### 2.5 任务执行系统

| 模块 | 文件路径 | 功能描述 | 状态 |
|------|---------|---------|------|
| **SmartTaskExecutor** | `core/task_execution_engine.py` | 智能任务执行引擎，支持分解/重试/回滚 | ✅ 已实现 |
| **SmartDecomposer** | `core/task_execution_engine.py` | 任务分解器 (LLM+规则混合) | ✅ 已实现 |
| **TaskContext** | `core/task_execution_engine.py` | 任务上下文管理 | ✅ 已实现 |
| **TaskDecomposer** | `core/task_decomposer.py` | 任务分解工具 | ✅ 已实现 |

### 2.6 记忆与上下文

| 模块 | 文件路径 | 功能描述 | 状态 |
|------|---------|---------|------|
| **MemoryPalace** | `core/memory_palace/models.py` | 记忆宫殿 (Palace/Hall/Room/Drawer 分层) | ✅ 已实现 |
| **MemoryCompression** | `core/memory_palace/models.py` | AAAK 记忆压缩 | ✅ 已实现 |
| **ConversationalClarifier** | `core/conversational_clarifier.py` | 主动需求引导，需求澄清 | ✅ 已实现 |
| **IdeaClarifier** | `core/idea_clarifier.py` | 头脑风暴，需求清晰化 | ✅ 已实现 |
| **ContextPreprocessor** | `core/context_preprocessor.py` | 上下文预处理 | ✅ 已实现 |

### 2.7 技能自进化系统

| 模块 | 文件路径 | 功能描述 | 状态 |
|------|---------|---------|------|
| **SkillEvolutionAgent** | `core/skill_evolution/agent_loop.py` | 技能自进化 Agent 循环 | ✅ 已实现 |
| **EvolutionDatabase** | `core/skill_evolution/database.py` | L0-L4 分层记忆存储 | ✅ 已实现 |
| **TaskSkill** | `core/skill_evolution/models.py` | 技能数据结构 | ✅ 已实现 |
| **UnifiedToolHandler** | `core/skill_evolution/atom_tools.py` | 原子工具处理 | ✅ 已实现 |
| **AmphiLoop** | `core/amphiloop/` | 双向调度引擎 | ✅ 已实现 |

### 2.8 统一缓存系统

| 模块 | 文件路径 | 功能描述 | 状态 |
|------|---------|---------|------|
| **UnifiedCache** | `unified_cache.py` | 三级缓存统一接入层 | ✅ 已实现 |
| **QueryNormalizer** | `unified_cache.py` | Query 标准化与压缩 | ✅ 已实现 |
| **QueryCompressor** | `unified_cache.py` | 三级压缩策略 (关键词/语义/分块) | ✅ 已实现 |
| **CacheManager** | `client/src/business/tier_model/cache_manager.py` | L1/L2/L3 三级缓存 | ✅ 已实现 |

### 2.9 智能写作系统

| 模块 | 文件路径 | 功能描述 | 状态 |
|------|---------|---------|------|
| **AIEnhancedGeneration** | `core/smart_writing/ai_enhanced_generation.py` | AI 增强内容生成 | ✅ 新增 |
| **ProjectGeneration** | `core/smart_writing/project_generation.py` | 项目生成 | ✅ 新增 |

---

## 3. 核心模块详细说明

### 3.1 L0-L4 分层选举架构

```
用户 Query
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│  L0: 意图分类 + 快速路由 (SmolLM2.gguf / qwen3.5:2b)         │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ QueryIntentClassifier → 4 类意图                         │ │
│  │ • factual (事实查询)                                     │ │
│  │ • conversational (对话类)                                │ │
│  │ • procedural (流程/代码类)                              │ │
│  │ • creative (创意类)                                     │ │
│  └─────────────────────────────────────────────────────────┘ │
│    │                                                        │
│    │ 基于意图选择路由策略                                      │
│    ▼                                                        │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ L1-L2: 检索层 (Cache + Knowledge Base)                  │ │
│  │ • ExactCache → SessionCache → KnowledgeBase → Database   │ │
│  └─────────────────────────────────────────────────────────┘ │
│    │                                                        │
│    │ 未命中或需要深度生成                                      │
│    ▼                                                        │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ L3: 推理层 (qwen3.5:4b)                                 │ │
│  │ • 意图理解 + 上下文整合                                    │ │
│  └─────────────────────────────────────────────────────────┘ │
│    │                                                        │
│    │ 需要深度生成                                            │
│    ▼                                                        │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ L4: 深度生成层 (qwen3.5:9b / qwen3.6:35b-a3b)           │ │
│  │ • Wiki 风格深度搜索                                      │ │
│  │ • 流式输出                                               │ │
│  └─────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

### 3.2 记忆宫殿 (Memory Palace)

```
Palace (宫殿) ─ 用户完整档案
  │
  ├── Hall (大厅) ─ 业务板块
  │     │
  │     ├── Room (房间) ─ 会话线程
  │     │     │
  │     │     └── Drawer (抽屉) ─ 关键事实
  │     │           │
  │     │           ├── order_number (订单号)
  │     │           ├── preference (偏好)
  │     │           └── commitment (承诺)
  │     │
  │     └── MemoryEntry (记忆条目)
  │           │
  │           ├── access_count (访问计数)
  │           ├── compressed (压缩标记)
  │           └── tags (标签)
  │
  └── PalaceProfile
        │
        ├── user_id
        ├── halls[]
        └── preferences{}
```

### 3.3 统一缓存架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Query Normalizer                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 1. 截断超长 query (200字)                              │  │
│  │ 2. 提取核心关键词 (语义压缩)                            │  │
│  │ 3. 归一化数字/标点                                    │  │
│  │ 4. 生成多种 cache key                                 │  │
│  └───────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  L0 Cache    │   │ Search Cache │   │ L4 Response  │
│  (smolllm2)  │   │  (tier_model)│   │   (exact)   │
├──────────────┤   ├──────────────┤   ├──────────────┤
│ Memory LRU   │   │ L1 Memory   │   │ ExactCache   │
│ 100条/24h   │   │ (热度加权)   │   │ LRU+SimHash  │
├──────────────┤   ├──────────────┤   ├──────────────┤
│ query hash   │   │ L2 SQLite   │   │ BloomFilter  │
│ → route      │   │ WAL 24h     │   │ 7天 TTL      │
├──────────────┤   ├──────────────┤   ├──────────────┤
│              │   │ L3 Semantic │   │ WriteBack    │
│              │   │ FAISS 0.85  │   │ 异步回填     │
└──────────────┘   └──────────────┘   └──────────────┘
```

### 3.4 技能自进化流程

```
[遇到新任务]
      │
      ▼
┌─────────────────┐
│ 搜索相似技能 (L3) │
└────────┬────────┘
         │
    ┌────┴────┐
    │ 有相似?  │
    └────┬────┘
   Yes   │   No
    │    │    │
    ▼    │    ▼
[复用技能] │ [自主摸索]
    │    │    │
    │    │    ├─→ LLM 推理
    │    │    ├─→ 工具执行
    │    │    └─→ 经验写入
    │    │
    │    └─────────────────────────────┐
    │                                  │
    ▼                                  ▼
[执行完成?] ──────────────────────→ [固化判断]
    │                                  │
    │ Yes                              │ 成功≥2次
    │                                  ▼
    │                           [固化为 Skill]
    │                                  │
    │                                  ▼
    │                           [写入 L3 层]
    │                                  │
    └──────────────────────────────────┘
                    │
                    ▼
              [技能成熟度]
              • seed → growing → matured
              • 成功率跟踪
              • 使用次数统计
```

---

## 4. 模块依赖关系图

```
HermesAgent
├── ToolRegistry + Dispatcher
│   ├── file/terminal/writing/ollama 工具集
│   └── knowledge 工具集 (需额外注册)
├── SessionDB
├── MemoryManager
└── ┌─────────────────────────────────────────────────┐
    │              FusionRAG (多源检索)                 │
    │  ┌───────────┐  ┌───────────┐  ┌───────────┐     │
    │  │ IntentCls │→ │IntellRouter│→ │L4AwareRouter│    │
    │  └───────────┘  └───────────┘  └───────────┘     │
    │        │            │              │              │
    │        ▼            ▼              ▼              │
    │  ┌─────────────────────────────────────────┐    │
    │  │         KnowledgeBaseLayer              │    │
    │  │  (向量+BM25 混合检索, Ollama 嵌入)       │    │
    │  └─────────────────────────────────────────┘    │
    │        │                                      │
    │        ▼                                      │
    │  ┌───────────┐  ┌───────────┐                 │
    │  │FusionEngine│  │DeepSearch │                 │
    │  │(结果融合)  │  │WikiSystem │                 │
    │  └───────────┘  └───────────┘                 │
    └─────────────────────────────────────────────────┘
    │
    ├── UnifiedCache (三级缓存)
    │     ├── L0 Cache (smolllm2/router)
    │     ├── Search Cache (L1/L2/L3)
    │     └── L4 Response Cache
    │
    ├── SkillEvolutionAgent
    │     ├── EvolutionDatabase (L0-L4 分层记忆)
    │     ├── AmphiLoop (双向调度)
    │     └── UnifiedToolHandler
    │
    ├── SmartTaskExecutor
    │     ├── SmartDecomposer (LLM+规则)
    │     └── TaskContext
    │
    └── MemoryPalace
          ├── Palace/Hall/Room/Drawer
          └── MemoryCompression (AAAK)
```

---

## 5. 复用建议与重构思路

### 5.1 已实现功能 → 新功能映射表

| 新功能需求 | 优先复用模块 | 复用方式 |
|-----------|-------------|---------|
| **深度搜索** | `DeepSearchWikiSystem` | 直接调用 `generate_wiki(topic)` |
| **多源检索** | `KnowledgeBaseLayer` + `FusionEngine` | 组合使用 |
| **意图分类** | `QueryIntentClassifier` | 直接调用 `classify(query)` |
| **智能路由** | `IntelligentRouter` | 传入 intent 获取路由决策 |
| **任务分解** | `SmartDecomposer` | 调用 `should_decompose()` 判断 + `decompose()` 执行 |
| **记忆存储** | `MemoryPalace` | 使用 `store_fact()` / `recall_user_context()` |
| **需求澄清** | `ConversationalClarifier` | 监听用户消息，`should_prompt()` 判断 |
| **技能固化** | `SkillEvolutionAgent` | `execute_task()` 自动触发 `_try_consolidate()` |
| **结果缓存** | `UnifiedCache` | 统一查询入口，自动多级命中 |
| **会话持久化** | `SessionDB` | SQLite WAL 模式 |
| **向量检索** | `KnowledgeBaseVectorStore` | 支持 Chroma/FAISS |
| **任务执行** | `SmartTaskExecutor` | 支持重试/回滚/DAG |

### 5.2 重构建议

#### 建议 1: 统一入口整合

**现状**: 各模块分散调用，缺乏统一入口
**建议**: 在 `HermesAgent` 中整合 FusionRAG 调用链

```python
# 建议的调用方式
class HermesAgent:
    def chat(self, query):
        # 1. 意图分类 (L0)
        intent = self.intent_classifier.classify(query)

        # 2. 智能路由 (L1-L2)
        route = self.router.route(query, intent)

        # 3. 多源检索 (KB + Cache)
        results = self.fusion.search(query, route)

        # 4. 结果融合
        fused = self.fusion_engine.fuse(results)

        # 5. LLM 生成或直接返回
        if route.needs_llm:
            return self.llm.generate(fused, ...)
        return fused
```

#### 建议 2: 技能系统与任务执行解耦

**现状**: `SkillEvolutionAgent` 内部包含完整执行循环
**建议**: 提取通用执行引擎，技能系统专注固化逻辑

```
SmartTaskExecutor (通用任务执行)
      │
      ├── 串行/并行/DAG 执行
      ├── 失败重试 + 回滚
      ├── 检查点保存
      │
      ▼
SkillEvolutionAgent (技能专用)
      │
      ├── 技能搜索
      ├── 固化判断
      └── 写入 L3
```

#### 建议 3: 缓存层统一封装

**现状**: `unified_cache.py` 已实现但可能未被充分利用
**建议**: 所有 Agent 统一通过 `UnifiedCache` 访问

```python
# 统一缓存使用
result = unified_cache.get_or_compute(
    query=query,
    compute_fn=lambda: llm.generate(query),
    layers=["exact_cache", "session_cache", "knowledge_base"]
)
```

#### 建议 4: 记忆系统与上下文融合

**现状**: `MemoryPalace` 与 `ConversationHistory` 分离
**建议**: 统一上下文管理器

```python
class UnifiedContext:
    """整合记忆宫殿 + 会话历史 + 实时上下文"""

    def __init__(self):
        self.palace = MemoryPalace()
        self.session = SessionDB()
        self.clarifier = ConversationalClarifier()

    def get_context(self, user_id: str) -> dict:
        """获取完整上下文用于 LLM"""
        return {
            "user_profile": self.palace.recall_user_context(user_id),
            "recent_history": self.session.get_recent(user_id, limit=10),
            "pending_clarifications": self.clarifier.get_pending()
        }
```

### 5.3 避免重复造轮子

| 需求场景 | 现有解决方案 | 说明 |
|---------|-------------|------|
| 需要搜索 → | `KnowledgeBaseLayer.search()` | 向量+BM25 混合 |
| 需要 Wiki 风格 → | `DeepSearchWikiSystem.generate()` | 章节模板+来源聚合 |
| 需要任务分解 → | `SmartDecomposer.should_decompose()` | LLM+规则混合 |
| 需要需求澄清 → | `ConversationalClarifier` | 主动引导 |
| 需要记忆 → | `MemoryPalace` | 分层存储 |
| 需要技能 → | `SkillEvolutionAgent.execute_task()` | 自进化 |
| 需要缓存 → | `UnifiedCache` | 三级缓存 |
| 需要会话 → | `SessionDB` | SQLite WAL |

---

## 6. 附录

### 6.1 关键配置

| 配置项 | 默认值 | 说明 |
|-------|-------|------|
| Ollama 地址 | `http://localhost:11434` | 本地 LLM |
| 嵌入模型 | `nomic-embed-text` / `qwen2.5:1.5b` | 向量化 |
| L0 模型 | `SmolLM2.gguf` | 意图分类 |
| L3 模型 | `qwen3.5:4b` | 推理 |
| L4 模型 | `qwen3.5:9b` | 深度生成 |
| 压缩模型 | `qwen2.5:1.5b` | Query 压缩 |

### 6.2 文件路径速查

```
核心模块:  core/
├── agent.py                    # HermesAgent
├── ollama_client.py            # Ollama 调用
├── session_db.py               # 会话数据库
├── memory_manager.py           # 记忆管理
├── tools_registry.py           # 工具注册
├── task_execution_engine.py     # 任务执行
├── conversational_clarifier.py  # 需求澄清
├── unified_cache.py             # 统一缓存

├── fusion_rag/
│   ├── l4_executor.py          # L4 执行器
│   ├── intent_classifier.py    # 意图分类
│   ├── intelligent_router.py    # 智能路由
│   ├── knowledge_base.py       # 知识库层
│   └── fusion_engine.py        # 结果融合

├── deep_search_wiki/
│   ├── wiki_generator.py       # Wiki 生成
│   ├── search_engine.py        # 搜索引擎
│   └── credibility.py          # 可信度评估

├── memory_palace/
│   └── models.py               # 记忆宫殿

├── skill_evolution/
│   ├── agent_loop.py          # 技能进化
│   ├── models.py              # 数据模型
│   └── database.py            # 进化数据库

└── amphiloop/
    └── ...                     # 双向调度
```
