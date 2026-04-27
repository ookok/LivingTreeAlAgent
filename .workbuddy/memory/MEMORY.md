# MEMORY.md - 长期记忆

## 用户偏好（永久记住）

- 回复语言：**中文**
- 输出格式：结构化（emoji、ASCII、层级缩进）
- 执行风格：**直接执行**，不确认，用户倾向一次性综合性任务
- 任务中断：用户发送"继续"指令催促执行

## 模型配置（永久记住）

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
- **模型**: `qwen3.6:latest` 或 `qwen3.5:9b`
- **连接**: 本地 Ollama (`http://localhost:11434`)
- **用途**: 深度生成、思考模式

### 通用配置
- **API Key**: 无（本地部署）
- **测试用途**: 优先使用此配置进行测试

⚠️ **踩坑**：qwen3.6:latest / qwen3.5:4b 是思考模型，API 返回 `content=""`，答案在 `thinking` 字段。
推荐压缩模型：`qwen2.5:1.5b`（非思考，干净中文输出，3-5s）

### Ollama 可用模型
```
smollm2-test:latest, gemma4:26b, qwen3.6:35b-a3b, qwen3.5:4b,
qwen3.5:2b, qwen3.6:latest, qwen3.5:9b, qwen3.5:0.8b,
qwen2.5:1.5b, qwen2.5:0.5b, deepseek-r1:70b
```

## 硬件配置

### GPU 配置
- **实际硬件**: 3x NVIDIA Tesla V100（SXM2）
  - GPU 0: Tesla V100-SXM2-16GB
  - GPU 1: Tesla V100-SXM2-32GB
  - GPU 2: Tesla V100-SXM2-16GB
  - **总 VRAM**: 64GB
- **层级**: `ultra`（自动识别）

### 模型选举结果（ultra 层）
- **L0** (快速路由): `qwen3.5:2b`
- **L3** (意图理解): `qwen3.5:4b`
- **L4** (深度生成): `qwen3.6:35b-a3b`（思考模型，注意 `content=""` 问题）

## 核心架构原则（永久记住）

### 不要重复造轮子
- 已有完整组件库，优先复用
- 新功能应该组合已有组件，而非重新实现
- 详见 `client/src/business/` 已有模块

### 架构分层（2026-04-27 新增）
```
智能体层 (Brain)
    ↓ 调用
统一工具层 (ToolRegistry)
    ↓ 路由
工具实现层 (Implementations)
```

- **智能体是大脑**：负责思考决策、任务规划、工具选择
- **工具是手脚眼睛耳朵**：负责执行具体任务
- **统一工具层**：所有工具通过 `ToolRegistry` 注册和调用

### 统一架构层方案（2026-04-27 新增）
- **ToolRegistry**：工具注册中心（单例模式）
- **BaseTool**：工具基类（所有工具继承此类）
- **ToolDefinition**：工具定义（名称、描述、处理函数、参数、返回值）
- **ToolResult**：工具执行结果（success, data, error）

详见：`docs/统一架构层改造方案.md`

### LLM 调用规范（2026-04-27 新增）⚠️ 重要
- **标准**：所有 LLM 调用必须通过 `GlobalModelRouter`
- **位置**：`client/src/business/global_model_router.py`
- **功能**：
  - 支持 20+ 种模型能力（chat, code_generation, reasoning, translation 等）
  - 支持策略路由（质量/速度/成本/隐私/均衡）
  - 支持三维评分（capability/cost/latency）
  - 支持缓存、负载均衡、历史成功率追踪
  - 支持 fallback 和 race 模式
  - 支持同步调用 `call_model_sync()`
- **已修改模块**：
  - ✅ `expert_training/expert_trainer.py` - 使用 `call_model_sync()` 替代 `OllamaClient`
  - ✅ `ai_scientist/base_engine.py` - 添加 `_call_llm()` 方法，使用 `GlobalModelRouter`
- **禁止**：
  - ❌ 禁止业务模块直接使用 `OllamaClient`（底层组件除外）
  - ❌ 禁止业务模块直接调用 Ollama API（必须通过路由器）
- **检查命令**：
  ```powershell
  # 查找可能违规的模块
  search_content -pattern "\.chat\(|OllamaClient" -type "py"
  ```

## 已有工具模块清单（2026-04-27 更新）

### 已实现的工具模块（20 个）

#### 网络与搜索工具（5 个）
1. **web_crawler** - 网页爬虫（`client/src/business/web_crawler/engine.py`）
2. **deep_search** - 深度搜索（`client/src/business/deep_search_wiki/wiki_generator.py`）
3. **tier_router** - 分层搜索路由（`client/src/business/search/tier_router.py`）
4. **proxy_manager** - 代理管理（`client/src/business/base_proxy_manager.py`）
5. **content_extractor** - 内容提取（`client/src/business/web_content_extractor/extractor.py`）

#### 文档处理工具（2 个 + 1 个需新建）
1. **document_parser** - 文档解析（`client/src/business/bilingual_doc/document_parser.py`）
2. **intelligent_ocr** - PDF OCR（`client/src/business/intelligent_ocr/ocr_engine.py`）
3. **markitdown_converter** - ❌ 需新建（P0 优先级）

#### 数据存储与检索工具（4 个）
1. **vector_database** - 向量数据库（`client/src/business/knowledge_vector_db.py`）
2. **knowledge_graph** - 知识图谱（`client/src/business/knowledge_graph.py`）
3. **intelligent_memory** - 智能记忆（`client/src/business/intelligent_memory.py`）
4. **kb_auto_ingest** - 知识自动摄入（`client/src/business/knowledge_auto_ingest.py`）

#### 任务与流程工具（4 个）
1. **task_decomposer** - 任务分解（`client/src/business/task_decomposer.py`）
2. **task_queue** - 任务队列（`client/src/business/task_queue.py`）
3. **task_execution_engine** - 任务执行引擎（`client/src/business/task_execution_engine.py`）
4. **agent_progress** - 进度反馈（`client/src/business/agent_progress.py`）

#### 学习与进化工具（3 个）
1. **expert_learning** - 专家学习（`client/src/business/expert_learning/learning_system.py`）
2. **skill_evolution** - 技能进化（`client/src/business/skill_evolution/evolution_engine.py`）
3. **experiment_loop** - 实验循环（`client/src/business/experiment_loop/evolution_loop.py`）

#### 推理增强工具（2 个）
1. **rys_engine** - RYS 层重复推理引擎（`client/src/business/rys_engine.py`）
   - 基于 dnhkng 的 RYS 研究：重复 Transformer 中间推理层提升性能
   - 不改权重、不微调，仅改变层执行路径
   - Qwen3-4B 重复第21层 → +11.9% 性能，延迟仅 +2.8%
   - 已集成到 GlobalModelRouter（`rys_config` 参数）
   - ⚠️ 当前 Ollama 不支持运行时层重复，需等 llama.cpp 合并 --repeat-layers
   - 参考：https://github.com/dnhkng/RYS
2. **verifier_engine** - LLM-as-a-Verifier 验证引擎（`client/src/business/verifier_engine.py`）
   - 基于 Stanford/Berkeley ICLR 2026 论文，OS级通用验证基础设施
   - 三维度验证：G(粒度) × K(重复验证) × C(标准分解)
   - Best-of-N 选择：循环赛机制选最优候选
   - 直接调用 Ollama /api/chat 的 logprobs 参数
   - VerifierRegistry：各模块注册评估标准
   - 已集成到 GlobalModelRouter（`verify` 参数）
   - 预置 4 套标准：universal(3) / ei_agent(7) / fusion_rag(3) / code_generation(3)
   - 参考：https://github.com/llm-as-a-verifier/llm-as-a-verifier

### 需新建工具模块（6 个）

| 工具名称 | 优先级 | 功能描述 |
|---------|-------|---------|
| **markitdown_converter** | P0 | HTML/PDF/DOCX → Markdown |
| **aermod_tool** | P1 | 大气扩散模型（基于已有部分实现） |
| **map_api_tool** | P1 | 地图 API（高德/天地图） |
| **elevation_tool** | P1 | 高程数据（SRTM/GTOPO30） |
| **distance_tool** | P1 | 距离计算（Haversine 公式） |
| **mike21_tool** | P2 | 水动力模型（Mike21 接口） |
| **cadnaa_tool** | P2 | 噪声模型（CadnaA 接口） |

## 意图分类机制

### HermesAgent._classify_query_type() 三层路由
| 类型 | 特征 | 管道 |
|------|------|------|
| **dialogue** | 寒暄/情感/短句(≤12字) | L0模型，跳过KB/深度搜索 |
| **emotion_aware** | 情感词(好累/好烦) | L0 + 情绪感知 |
| **task** | 行动动词/技术词 | KB 搜索 + L3/L4 模型 |
| **search** | 疑问词/问号 | KB + 深度搜索 + L4 模型 |

### 分类优先级
1. **搜索关键词** → search（优先判断，修复短句bug）
2. 疑问词开头 → search（除非有任务动词）
3. 行动动词 → task
4. 寒暄/情感/短句 → dialogue
5. 默认 → search

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

## 踩坑经验（永久记住）

### 知识图谱导入
- `core/knowledge_graph/` 是**包目录**，导入 `core.knowledge_graph` 实际加载 `core/knowledge_graph/__init__.py`
- 正确添加方法到 `__init__.py`，不是 `knowledge_graph.py`（独立文件）
- Python `__pycache__` 会缓存旧代码，修改后需清理或重启进程

### 模型思考能力
- qwen3.6:latest / qwen3.5:4b 是思考模型，API 返回 `content=""`，答案在 `thinking` 字段
- 推荐使用 `qwen2.5:1.5b` 作为压缩模型（非思考，干净中文输出，3-5s）

### Ollama 模型自动加载
- **问题**: Ollama 空闲时模型会被 stop（keep_alive 默认 5 分钟）
- **解决**: `OllamaClient.ensure_model_loaded()` + `get_loaded_models()`
- **机制**: chat() 前检查 `/api/ps`，模型未加载时发 `/api/generate` 触发重启

### 情绪感知集成
- `core/living_tree_ai/neural_layer/emotional.py` 已有完整实现
- 使用 `importlib.util.spec_from_file_location` 直接加载，绕过 `__init__.py` 的问题导入链

### 数字分身
- `core/agent.py` → `UserDigitalTwin` 类
- 在 `HermesAgent._init_model_client()` 中初始化
- 情绪状态注入 LLM 提示上下文

## 项目关键路径

- **统一缓存**: `unified_cache.py`（整合 L0/Search/L4 三层缓存 + 语义相似匹配）
- **深度搜索**: `core/fusion_rag/l4_executor.py` → `DeepSearchWikiSystem`
- **Skill 自进化**: `core/skill_evolution/agent_loop.py` → `SkillEvolutionAgent`

## 统一缓存增强

### 三级压缩策略（QueryCompressor）
- **≤300字**: Keyword 快缩（0延迟，提取关键词拼接）
- **300-500字**: LLM 语义压缩（qwen2.5:1.5b，保留意图+实体，0.5s）
- **>500字**: QueryChunker 分块（按句子/轮次切分，每块独立标准化）

## Skill 自动创建机制

**触发条件**（`SkillEvolutionAgent._try_consolidate()`）：
1. 任务成功完成（status=COMPLETED）
2. 执行步骤 ≥ 2 步
3. 无完全相同的已有技能（高阈值 0.6 查重）

**注意**：深度搜索链路（`HermesAgent` / `DeepSearchWikiSystem`）不触发 Skill 自动创建。
Skill 自进化只在 `SkillEvolutionAgent` 中生效。

## 外部技能集成（2026-04-27 新增）

### mattpocock/skills 集成
- **源仓库**: https://github.com/mattpocock/skills (24.9k stars, MIT License)
- **定位**: 面向专业工程师的 AI Agent 可复用技能集
- **本地克隆**: `.workbuddy/references/mattpocock-skills/`
- **适配输出**: `.workbuddy/skills/mattpocock/`
- **适配工具**: `client/src/business/skills_adapter.py`
- **已适配技能数**: 21 个
- **P0 已优化**: `tdd`（测试驱动开发）、`write-a-skill`（技能创建指南）
- **使用方式**: 技能已自动加载，触发词在 SKILL.md 的 description 字段中定义
- **集成说明**: `.workbuddy/skills/mattpocock/INTEGRATION.md`

### agency-agents-zh 集成（2026-04-27 新增）
- **源仓库**: https://github.com/agency-agents-zh/agency-agents-zh
- **定位**: 面向中文用户的 AI 专家角色库（211 个角色，18 个部门）
- **本地克隆**: `.workbuddy/references/agency-agents-zh/`
- **适配输出**: `.workbuddy/skills/agency-agents-zh/`
- **适配工具**: `client/src/business/agents_adapter.py`（新建）
- **已适配角色数**: 199 个（跳过 README 和策略文档）
- **目录结构**: 每个角色一个子目录，包含 SKILL.md（与 mattpocock 格式一致）
- **部门分类**: academic, design, engineering, finance, marketing, product, sales, specialized, strategy, support, testing 等

### 适配要点（两个库通用）
- 添加 YAML frontmatter（name, description, location 字段）
- 保留原始 Markdown 内容
- 添加 LivingTreeAlAgent 适配说明
- Shell 脚本标注 Windows 兼容性
- 生成与 mattpocock 一致的目录结构（`角色名/SKILL.md`）

### 高价值技能（优先级排序）
1. **tdd** - 测试驱动开发（红绿重构循环）
2. **write-a-skill** - 创建新技能指南
3.

## 专家训练系统（2026-04-27 新增）

### 核心功能
- **自主创建专家角色**：根据训练内容自动提取专家特征，生成 SKILL.md
- **知识发现集成**：集成 `ai_scientist` 模块，自动发现污染物关联、技术路线等知识
- **行业分类体系**：基于 GB/T 4754-2017 国民经济行业分类标准
- **自动整理专家**：按照行业和职业重新整理专家角色
- **智能体通知**：创建/更新后自动通知其他智能体
- **批量训练**：支持从目录批量导入训练文件

### 模块结构
```
client/src/business/expert_training/
├── __init__.py                  # 包初始化，导出核心类
├── industry_classification.py    # 行业分类体系（GB/T 4754-2017）
├── expert_trainer.py            # 专家训练核心模块（集成知识发现）
├── notification_system.py       # 智能体通知系统
├── industry_updater.py          # 行业分类自动更新
└── tools.py                    # 便捷工具函数
```

### ai_scientist 知识发现集成（2026-04-27）
- **集成位置**：`expert_trainer.py`
- **新增方法**：
  - `_discover_knowledge()`：调用 `ai_scientist.discover_knowledge()` 进行知识发现
  - `_extract_project_data()`：从训练内容中提取项目数据（工艺流程、排放信息）
- **修改方法**：
  - `train_from_content()`：在提取专家特征后，调用知识发现
  - `_generate_skill_md()`：在生成的 SKILL.md 中增加"知识发现"部分
- **工作流程**：
  1. 分析训练内容，提取专家特征
  2. 调用 `ai_scientist.discover_knowledge()` 发现相关知识
  3. 将发现的知识（污染物关联、技术路线等）写入 SKILL.md
  4. 生成更精准的专家角色

### 行业分类标准
- **标准**: GB/T 4754-2017《国民经济行业分类》
- **门类**: 20个（A-T）
- **大类**: 97个
- **数据来源**: 国家统计局 https://www.stats.gov.cn/sj/tjbz/gjtjjbz/
- **更新机制**: 定期从政府网站检查更新（默认24小时）

### 训练方式
1. **单个训练**：输入训练内容（文本、文档），自动生成专家角色
2. **批量训练**：从目录读取训练文件（支持 .txt, .md, .pdf, .docx, .csv, .json）
3. **自动分类**：根据训练内容自动匹配行业分类

### 通知系统
- **文件通知**（默认）：写入 `.livingtree/notifications/` 目录
- **消息总线**（可选）：通过消息队列发布通知
- **WebSocket推送**（可选）：实时推送给在线智能体
- **通知类型**：expert_created, expert_updated, expert_deleted, experts_reorganized

### UI 界面
- **面板位置**: `client/src/presentation/panels/expert_training_panel.py`
- **标签页**：
  1. 单个训练：输入训练内容，训练单个专家
  2. 批量训练：选择目录，批量训练专家
  3. 行业分类：查看行业分类体系树
  4. 专家整理：按行业重新整理专家
  5. 通知历史：查看通知历史记录

### 使用方式
```python
# 便捷函数
from client.src.business.expert_training.tools import (
    train_expert_from_text,
    batch_train_from_directory,
    reorganize_experts_by_industry
)

# 训练专家
result = train_expert_from_text("我是数据分析专家...", "数据分析专家")

# 批量训练
result = batch_train_from_directory("d:/training_data")

# 整理专家
report = reorganize_experts_by_industry()
```

### 文档
- **使用指南**: `docs/专家训练系统使用指南.md` **to-prd** - 生成产品需求文档
4. **improve-codebase-architecture** - 架构优化建议
5. **design-an-interface** - 并行生成接口设计方案

### 高价值专家角色（按部门）
- **engineering**: AI 工程师、后端架构师、前端开发、DevOps 自动化
- **marketing**: 增长经理、品牌守护者、内容策略师
- **product**: 产品经理、UX 架构师、用户体验研究员
- **finance**: 财务分析师、风险管理师、投资顾问
- **specialized**: MCP 构建者、会议助手、文档生成器

## 技能中心内置功能（2026-04-27 新增）

### SkillsPanel - 技能与专家角色管理面板
- **文件**: `client/src/presentation/panels/skills_panel.py`
- **注册**: `client/src/presentation/router/routes.py` → `tool_routes`
- **功能**: 浏览/搜索/启用/禁用技能，内置 220 个技能与专家角色
- **三个标签页**: 技能库（mattpocock + agency）| 专家角色（agency-agents-zh）| 已启用
- **激活持久化**: `~/.workbuddy/active_skills.json`

### 技能统计
| 来源 | 数量 | 说明 |
|------|------|------|
| mattpocock/skills | 21 个 | 工程技能（TDD、代码审查、架构设计等） |
| agency-agents-zh | 199 个 | 专家角色（AI工程师、产品经理、数据分析师等） |
| **总计** | **220 个** | 覆盖工程、设计、产品、市场、财务等领域 |

### 启用技能触发方式
- 在 SkillsPanel 中点击"✅ 启用技能"
- 对话中提及触发词自动加载对应 skill 的 SKILL.md 内容
- 已启用技能列表在 `~/.workbuddy/active_skills.json` 中管理

### 适配工具
- **skills_adapter.py**: mattpocock/skills 格式适配工具
- **agents_adapter.py**: agency-agents-zh 专家角色适配工具
- **输出目录**: `.workbuddy/skills/` (mattpocock/ + agency-agents-zh/)
- **格式**: 每个技能一个子目录，包含 SKILL.md

## 新增文件

- `client/src/business/skills_adapter.py`: mattpocock/skills 格式适配工具
- `core/model_election.py`: 硬件感知 L0/L3/L4 模型自动选举

---

**最后更新**: 2026-04-27
**更新内容**: 新增统一架构层设计方案、工具模块清单、待办任务清单、mattpocock/skills 集成记录
