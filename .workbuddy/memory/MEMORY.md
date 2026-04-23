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
