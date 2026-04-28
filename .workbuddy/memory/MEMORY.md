# MEMORY.md - 长期记忆

## 用户偏好
- 回复语言：**中文**，结构化输出（emoji、表格、层级缩进）
- 执行风格：**直接执行**，不确认，一次性综合性任务
- 任务中断：发送"继续"催促

## 模型配置
- **L0** (路由): `qwen3.5:2b` / **L3** (推理): `qwen3.5:4b` / **L4** (生成): `qwen3.6:35b-a3b`
- **连接**: Ollama `http://localhost:11434`
- ⚠️ qwen3.6/qwen3.5:4b 是思考模型，`content=""`，答案在 `thinking` 字段
- 推荐压缩模型：`qwen2.5:1.5b`
- 可用: smollm2-test, gemma4:26b, qwen3.6:35b-a3b, qwen3.5:{0.8b,2b,4b,9b}, qwen2.5:{0.5b,1.5b}, deepseek-r1:70b

## 硬件
- 3x NVIDIA Tesla V100 (SXM2): 16GB + 32GB + 16GB = 64GB VRAM
- 层级：`ultra`

## 架构原则
### 分层
```
智能体层 (Brain) → 统一工具层 (ToolRegistry) → 工具实现层 (Implementations)
```
- **ToolRegistry**: 单例，语义搜索（Ollama embeddings + cosine）
- **BaseTool**: 抽象基类，execute(**kwargs) → ToolResult
- **ToolResult**: success, data, error, message, metadata
- 所有新代码在 `client/src/business/`（逻辑）或 `client/src/presentation/`（UI）

### LLM 调用规范 ⚠️
- **必须**通过 `GlobalModelRouter` (`client/src/business/global_model_router.py`)
- 支持 `call_model_sync()`，20+ 能力类型
- ❌ 禁止直接 `OllamaClient` 或直接调用 Ollama API

### 不要重复造轮子
- 优先复用已有组件：`fusion_rag/`, `knowledge_graph/`, `search/`, `hermes_agent/` 等
- 详见 AGENTS.md 的 QUICK LOOKUP 表

## 已实现工具模块（20+个）

### 按类别
| 类别 | 工具 | 路径 |
|------|------|------|
| 网络/搜索 | web_crawler, deep_search, tier_router, proxy_manager, content_extractor | `business/` 各子目录 |
| 文档 | document_parser, intelligent_ocr | `business/bilingual_doc/`, `business/intelligent_ocr/` |
| 存储/检索 | vector_database, knowledge_graph, intelligent_memory, kb_auto_ingest | `business/` |
| 任务 | task_decomposer, task_queue, task_execution_engine, agent_progress | `business/` |
| 学习/进化 | expert_learning, skill_evolution, experiment_loop | `business/` |
| 推理增强 | rys_engine, verifier_engine | `business/rys_engine.py`, `business/verifier_engine.py` |
| EIA | aermod_tool, mike21_tool | `business/tools/` |
| CLI工具 | cli_tool_discoverer, cli_tool_installer, cli_anything | `business/self_evolution/`, `business/` |

### 自我进化引擎（9 组件）
- 路径: `client/src/business/self_evolution/`
- 整合: `SelfEvolutionEngine`（safe_mode → SafeAutonomousToolCreator）
- 组件: ToolMissingDetector, AutonomousToolCreator, ActiveLearningLoop, SelfReflectionEngine, UserClarificationRequester, SafeAutonomousToolCreator, ProxySourceManager, CLIToolDiscoverer, ModelAutoDetectorAndUpgrader

## 意图分类（HermesAgent）
| 类型 | 特征 | 管道 |
|------|------|------|
| dialogue | 寒暄/情感/短句(≤12字) | L0 |
| task | 行动动词/技术词 | KB + L3/L4 |
| search | 疑问词/问号 | KB + 深度搜索 + L4 |

## 踩坑经验
- qwen3.6/qwen3.5:4b 思考模型 `content=""`，答案在 `thinking`
- Ollama 空闲时模型被 stop → `ensure_model_loaded()` + `/api/ps`
- `__pycache__` 缓存旧代码，修改后需清理
- Windows 用 `;` 不用 `&&`
- GlobalModelRouter 调用：禁止直连 Ollama，必须通过 `call_model_sync()`

## 外部技能集成
- **mattpocock/skills**: 21 个工程技能，`.workbuddy/skills/mattpocock/`
- **agency-agents-zh**: 199 个专家角色，`.workbuddy/skills/agency-agents-zh/`
- 总计 220 个技能，SkillsPanel 管理

## .livingtree/skills 专家角色
- **已有**: chemical-expert, emergency-management, environmental-engineering-expert, equipment-expert, mechanical-expert, production-process-expert, safety-expert（7个）
- **新增**: office-document-expert, wps-document-expert, linguistics-expert, writing-expert（4个）
- **总计**: 12 个专家角色，存放在 `.livingtree/skills/` 目录
- 格式: 每个角色一个目录，含 SKILL.md（YAML frontmatter + 核心能力 + 工作流程 + 常见问题 + 输出模板）

## 专家训练系统
- 路径: `client/src/business/expert_training/`
- 功能: 自主创建专家角色、知识发现集成(ai_scientist)、行业分类(GB/T 4754-2017)

## EIA 工具包（2026-04-27 完成）
- **aermod_tool**: 大气扩散模型（BaseTool，CLI subprocess + Gaussian plume）✅
- **mike21_tool**: 水动力模型（BaseTool，mikeio DFS 解析✅，统一 BaseTool 模式）
- **groundwater_tool**: 地下水模拟（FloPy + MODFLOW-6 + HJ 610-2016 解析法⭐）✅
- **water_network_tool**: 水网络模拟（PySWMM + WNTR + 暴雨强度⭐）✅
- **PRESET_CLI_TOOLS 扩展**: +6 个环评 CLI 工具（mf6/swmm5/mike21/hydrus/delft3d/map）
- **EIA_PACKAGE_PRESETS**: 12 个 Python 包（flopy/pyswmm/swmmio/wntr/mikeio 等）

## 新增功能模块（2026-04-28）

### 主动工具发现
- 路径: `client/src/business/hermes_agent/proactive_discovery_agent.py`
- 功能: HermesAgent 增强版，主动发现并安装缺失工具
- 核心类: `ProactiveDiscoveryAgent(BaseToolAgent)`
- 流程: 分析任务所需工具 → 检查 ToolRegistry → 缺失时调用 NaturalLanguageToolAdder 安装 → 刷新注册表 → 执行任务
- LLM 调用: 通过 GlobalModelRouter ✅

### 工具链自动编排
- 路径: `client/src/business/tool_chain_orchestrator.py`
- 功能: 基于 TaskDecomposer 的工具链自动编排系统
- 核心类: `ToolChainOrchestrator`, `ToolChainStep`, `ToolChainResult`
- 特性: 支持步骤依赖、并行执行、失败重试、步骤间数据传递
- LLM 调用: 通过 GlobalModelRouter ✅

### 工具自我修复
- 路径: `client/src/business/self_evolution/tool_self_repairer.py`
- 功能: 分析工具执行错误，自动修复
- 修复策略: INSTALL_DEPENDENCY / FIX_CODE / FIX_CONFIG / REINSTALL_TOOL / UPDATE_REGISTRY
- 核心类: `ToolSelfRepairer`, `RepairResult`
- SelfReflectionEngine 增强: 集成 ToolSelfRepairer，工具执行失败时自动触发修复
- `_call_llm()` 修复: 改用 GlobalModelRouter ✅

### TextCorrectionTool（增强）
- 路径: `client/src/business/tools/text_correction_tool.py`
- 功能: 上下文感知的错别字纠正工具（支持六类错别字）
- 核心类: `TextCorrectionTool(BaseTool)`
- 六类错别字: 同音、形近、语法、多字、少字、乱序 ⭐
- LLM 调用: 通过 GlobalModelRouter（`capability=ModelCapability.REASONING`, temperature=0.2）
- 自动注册: `auto_register()` 函数自动注册到 ToolRegistry
- 语法检查: ✅ 通过（2026-04-28 重写）

### SpellCheckTextEdit（重构）
- 路径: `client/src/presentation/components/spell_check_edit.py`
- 功能: 实时错别字检查输入框（真正异步）
- 核心类: `SpellCheckTextEdit(QTextEdit)`, `SpellCheckWorker(QThread)`
- 异步模型: QThread + signal/slot（非 threading.Thread）
- 线程清理: `_cleanup_worker()` → quit() + wait() + deleteLater()
- 集成位置: `ei_wizard_chat.py`, `ide/panel.py`
- 语法检查: ✅ 通过（2026-04-28 重写）

### CI/CD 配置（完善）
- 路径: `.github/workflows/ci.yml`
- 多平台矩阵: ubuntu-latest, windows-latest, macos-latest
- PyQt6 支持: 添加 `pip install PyQt6 PyQt6-Qt6`
- 新增任务: `text-correction-test`（专项测试六类错别字）
- YAML 语法: ✅ 通过验证
- 部署增强: 添加企业微信 Webhook 通知

### 双数据飞轮 MVP
- 路径: `client/src/business/self_evolution/`
- 灵感来源: 阿里 PAI AgenticQwen（双数据飞轮训练法）
- 实现文件:
  - `tool_self_repairer.py`（修改）：添加错题记录功能 → `failed_cases.json`
  - `hard_variant_generator.py`（新建）：推理飞轮，从错题生成更难变体 → `training_pool.json`
  - `train_with_variants.py`（新建）：使用变体测试工具选择准确率
  - `test_dual_flywheel.py`（新建）：集成测试脚本
- 工作流程: 工具修复失败 → 记录错题 → 生成变体 → 训练测试 → 提升准确率

### 文档Skill自动提炼系统
- 路径: `client/src/business/document_skill_extractor.py`, `semantic_skill_matcher.py`, `tools/document_skill_tool.py`, `presentation/components/document_skill_panel.py`
- 功能: 通用文档→Skill自动提炼，支持任意文体（通知/通报/专家意见等），通过语义分析（Embedding）自动匹配触发
- 核心类: `DocumentSkillExtractor`, `SemanticSkillMatcher`, `DocumentSkillTool`, `DocumentSkillPanel`
- 工作流程: 文档输入 → LLM语义分析（自动识别类型）→ 生成SKILL.md + embedding.json → 保存 → 下次语义匹配自动触发
- 匹配阈值: `SIMILARITY_THRESHOLD = 0.75`（余弦相似度）
- 语法检查: ✅ 4个文件全部通过

## GlobalModelRouter 调用规范（2026-04-27 修复）
- ⚠️ **禁止**直接调用 `localhost:11434` 或使用 `requests`/`aiohttp` 直连 Ollama
- ✅ **必须**通过 `GlobalModelRouter`（`client/src/business/global_model_router.py`）
- ✅ 使用 `call_model_sync(capability, prompt, ...)`
- 已修复：`ai_capability_registry.py` 改用 `OllamaClient`（内部走 ModelRouter）
- 全局搜索：`requests`/`aiohttp` 直连 Ollama = 0 个 ✅

## MCP ToolAdapter（2026-04-27 新增）
- 路径: `client/src/business/tools/mcp_tool_adapter.py`
- 功能: 将 MCP Server 工具适配为 BaseTool，自动注册到 ToolRegistry
- 支持连接方式: stdio（子进程 stdin/stdout）/ HTTP（POST JSON-RPC 2.0）
- 核心类: `MCPToolAdapter(BaseTool)`, `MCPToolDiscoverer`
- 配置: `~/.living.tree/mcp_servers.json`
- MCP 协议支持: `tools/list`（发现）✅, `tools/call`（执行）✅

## 包管理器自动安装机制（2026-04-27 新增）
- **PackageManagerInstaller**: `client/src/business/self_evolution/package_manager_installer.py`
- 支持: pip, npm, cargo, brew, winget, choco
- PRESET_CLI_TOOLS 扩展字段: `install_command`, `verify_command`, `post_install`
- 流程: 检测缺失 → 安装 → 验证 → 自动学习帮助文档 → 注册到 ToolRegistry

## 结构化帮助解析器（2026-04-27 新增）
- **StructuredHelpParser**: `client/src/business/self_evolution/structured_help_parser.py`
- 支持格式: argparse, optparse, --help 自由文本, clap(Rust), npm
- 输出: JSON Schema 参数定义 + 子命令映射

---

**最后更新**: 2026-04-28
