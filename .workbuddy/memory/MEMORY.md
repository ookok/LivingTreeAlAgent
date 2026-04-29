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

## 架构原则
### 分层
```
智能体层 (Brain) → 统一工具层 (ToolRegistry) → 工具实现层 (Implementations)
```
- **ToolRegistry**: 单例，语义搜索
- **BaseTool**: 抽象基类，`execute(**kwargs) -> AgentCallResult`
- **ToolResult**: success, data, error, message, metadata
- 所有新代码在 `client/src/business/`（逻辑）或 `client/src/presentation/`（UI）

### LLM 调用规范 ⚠️
- **必须**通过 `GlobalModelRouter` (`client/src/business/global_model_router.py`)
- 支持 `call_model_sync(capability, prompt, ...)`，20+ 能力类型
- ❌ 禁止直接 `OllamaClient` 或直接调用 Ollama API

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

## 自我进化引擎（v1-v3）
- **路径**: `client/src/business/self_evolution/`
- **v1 (9组件)**: ToolMissingDetector, AutonomousToolCreator, ActiveLearningLoop, SelfReflectionEngine, UserClarificationRequester, SafeAutonomousToolCreator, ProxySourceManager, CLIToolDiscoverer, ModelAutoDetectorAndUpgrader
- **v2 (管线)**: Scanner → Ingestion → Planner → Executor → Orchestrator
- **v3 (CodeTool)**: OpenCode + Serena 集成（自动写/测/修/发布）
  - ~~`serena_adapter.py`~~: MCP 客户端（已废弃）
  - `serena_direct.py`: **直接集成模式**（方案 A）✅
  - `libs/serena-core/`: **Serena 核心子模块**（进程内调用、零序列化）
  - `code_tool.py`: BaseTool 子类，注册到 ToolRegistry
  - 安全: dry-run, backup, syntax verify, approve callback, rollback

## Serena 直接集成（方案 A）
- **路径**: `libs/serena-core/`（独立 git 仓库）
- **优势**: 延迟低（<1ms）、零序列化、进程内调用
- **组件**: serena_agent.py, ast_engine.py, symbol_resolver.py, code_modifier.py
- **已废弃**: MCP JSON-RPC 协议（方案 B）

## PyQt6 UI 自动化测试框架 (v1.1)
- **路径**: `client/tests/ui_automation/`
- **test_base.py**: TestCase, TestRunner, wait_for, screenshot_on_failure
- **component_tester.py**: ComponentTester, assert_*, simulate_*
- **business_logic_tester.py**: 消息渲染、流式输出、工具调用、流水线测试
- **opencode_ide_tester.py**: OpenCode IDE 专用测试套件
- **run_ui_tests.py**: 测试运行器 CLI
- **resource_locator.py**: **localresources 文件自动查找**（关键词/扩展名/内容匹配）
- **auto_test_generator.py**: **自动代码分析 + 测试生成**（分析业务逻辑，生成测试代码）
- **demo_auto_test.py**: 自动测试生成示例

### 自动测试生成功能
- **CodeAnalyzer**: 分析类结构（方法/信号/属性）
- **TestCodeGenerator**: 根据分析结果生成 pytest/unittest/qtest 代码
- **ResourceLocator**: 从 localresources 查找测试数据文件
- **generate_opencode_ide_tests()**: 一键生成 OpenCode IDE 完整测试套件

## EIA 工具包
- **aermod_tool**: 大气扩散模型 ✅
- **mike21_tool**: 水动力模型 ✅
- **groundwater_tool**: 地下水模拟 ✅
- **water_network_tool**: 水网络模拟 ✅

## 外部技能集成
- **mattpocock/skills**: 21 个工程技能
- **agency-agents-zh**: 199 个专家角色
- **总计**: 220 个技能，SkillsPanel 管理

## 专家角色系统
- **.livingtree/skills/**: 12 个专家角色（SKILL.md 格式）
- **expert_training/**: 自主创建专家角色、知识发现、行业分类

## EvoRAG 集成
- 反馈驱动反向传播 + 知识图谱自进化 + 混合优先级检索
- V4 集成器: `client/src/business/llm_wiki/knowledge_graph_integrator_v4.py`

## EigenFlux 增强 A2A 通信层
### 核心理念
- **信号广播**: Agent 广播 KNOWLEDGE/NEED/CAPABILITY
- **智能匹配**: 网络只传递相关信号，减少信息过载
- **去中心化**: 无需中心注册表，Agent 可自发现
- **开放标准**: 任何 Agent 可加入，不同框架可互操作

### 核心文件
| 文件 | 功能 |
|------|------|
| `a2a_protocol/eigenflux.py` | SignalBus、匹配引擎、适配器 |
| `a2a_protocol/eigenflux_integration.py` | A2A 集成示例 LivingTreeEigenFluxGateway |
| `a2a_protocol/EIGENFLUX_DESIGN.md` | 完整设计文档 |

### 核心组件
- **SignalBus**: 信号总线，负责广播与智能路由
- **SignalMatchEngine**: 匹配引擎（Semantic/Keyword/Capability/Interest）
- **AgentSignalAdapter**: Agent 信号适配器
- **A2AEigenFluxBridge**: A2A 与 EigenFlux 桥接器

### 信号类型
- `KNOWLEDGE`: 我知道什么（触发 Interest 匹配）
- `NEED`: 我需要什么（触发 Capability 匹配）
- `CAPABILITY`: 我能做什么（触发 Need 匹配）
- `TASK`: 有任务要处理

## PyDracula UI 框架集成
### 概述
- 基于 [Wanderson-Magalhaes/Modern_GUI_PyDracula_PySide6_or_PyQt6](https://github.com/Wanderson-Magalhaes/Modern_GUI_PyDracula_PySide6_or_PyQt6)
- 默认亮色主题（PyDracula_Light）
- 支持深色主题切换

### 核心文件
| 文件 | 功能 |
|------|------|
| `ui/__init__.py` | 包入口 |
| `ui/main_window.py` | MainWindow 主窗口类 |
| `ui/theme_manager.py` | ThemeManager 主题管理器（单例模式）|
| `ui/modules/ui_settings.py` | UI 设置常量 |
| `ui/modules/ui_functions.py` | UI 工具函数 |
| `ui/themes/py_dracula_light.qss` | 亮色主题 |
| `ui/themes/py_dracula_dark.qss` | 深色主题 |

### 主题切换 API
```python
from ui.theme_manager import get_theme_manager

tm = get_theme_manager()
tm.set_theme(is_light=True)   # 亮色主题
tm.set_theme(is_light=False)  # 深色主题
tm.toggle_theme()             # 切换主题
```

### 启动方式
```bash
python ui/ui_run.py              # 亮色主题（默认）
python ui/ui_run.py --dark       # 深色主题
```

### 依赖
- PySide6>=6.5.0 或 PyQt6>=6.5.0

---
**最后更新**: 2026-04-29
