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
