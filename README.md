# 🌳 LivingTree AI Agent v2.1

> 工业级自主数字生命体 — 批量文档写作 · 项目开发 · 自我进化

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Toad](https://img.shields.io/badge/UI-Toad-blue)](https://github.com/batrachianai/toad)

---

## 快速开始

### 一键安装

**Linux/macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/ookok/LivingTreeAlAgent/main/install.sh | bash
```

**Windows (PowerShell):**
```powershell
powershell -c "irm https://raw.githubusercontent.com/ookok/LivingTreeAlAgent/main/install.ps1 | iex"
```

**Windows (CMD):**
```cmd
curl -fsSL https://raw.githubusercontent.com/ookok/LivingTreeAlAgent/main/install.bat -o install.bat && install.bat
```

### 启动

```bash
livingtree          # TUI 对话界面
livingtree relay    # 启动中继服务器
```

部署后系统自动完成：Python 环境检测、依赖安装、LLM 密钥加载、模型选举、知识库初始化。用户只需登录即可使用。

---

## 核心能力

| 能力 | 说明 |
|------|------|
| 🤖 **10+ LLM Provider** | DeepSeek/硅基流动/模力方舟/智谱/讯飞/阿里/小米等，免费优先 |
| 📝 **批量文档生成** | CSV 参数表 → 并行 LLM 生成 → DOCX/PDF 导出 |
| 🔍 **混合知识检索** | FTS5 全文 + 向量语义 + 知识图谱，4 路融合 |
| 🧠 **自主进化** | 每小时互联网学习，每天自动挖掘项目模板 |
| 🌐 **P2P 网络** | 节点能力共享，中继服务器内网穿透 |
| 🔧 **21 个内置工具** | 高斯烟羽/噪声衰减/代码图谱/AI 训练等 |
| 👤 **8 个专家角色** | 环评专家/全栈工程师/数据分析师/AI 研究员等 |
| 📋 **审批工作流** | draft→review→approve→publish 多级审批 |
| ⚖️ **法规合规检查** | GB3095/3096/3838/3840 自动审计 |

## 系统架构

```
┌──────────────────────────────────────────────────────────┐
│                    TUI (Toad)                             │
│  ┌──────────┬──────────┬──────────┬──────────────────┐   │
│  │ 对话面板  │ 代码面板  │ 知识库    │ 工具箱           │   │
│  │ ChatAgent│ CodeAgent│ KBAgent │ ToolsAgent       │   │
│  └────┬─────┴────┬─────┴────┬─────┴────────┬─────────┘   │
│       │          │          │              │              │
│  ┌────▼──────────▼──────────▼──────────────▼──────────┐  │
│  │              UnifiedRegistry                        │  │
│  │  21 tools · 12 roles · 4 KB stores → single source │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                  │
│  ┌──────────────────────▼───────────────────────────────┐  │
│  │                  LifeEngine                           │  │
│  │  perceive → cognize → plan → execute → reflect → evolve│  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                  │
│  ┌──────────────────────▼───────────────────────────────┐  │
│  │                  TreeLLM                              │  │
│  │  HolisticElection · CacheOptimizer · SkillRouter     │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                  │
│  ┌──────────────────────▼───────────────────────────────┐  │
│  │  DeepSeek · SiliconFlow · MoFang · Zhipu · Spark     │  │
│  │  LongCat · XiaoMi · Aliyun · DMXAPI · OpenCode-Serve │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## 项目结构

```
LivingTreeAlAgent/
├── relay_server.py          # P2P 中继服务器
├── install.sh/bat/ps1       # 一键部署脚本
├── deploy_relay.*           # 中继服务器部署
├── livingtree/
│   ├── tui/                 # Toad TUI 界面
│   │   ├── app.py           # App 主类
│   │   ├── screens/         # 各面板 Screen
│   │   ├── widgets/         # UI 组件
│   │   ├── td/              # Toad 源码 (165+ 文件)
│   │   ├── styles/          # CSS 主题
│   │   └── i18n.py          # 中英文翻译
│   ├── treellm/             # LLM 路由引擎
│   │   ├── core.py          # TreeLLM 主类
│   │   ├── providers.py     # 各 Provider 实现
│   │   ├── holistic_election.py  # 5 维评分选举
│   │   ├── structured_enforcer.py # JSON Schema 校验
│   │   ├── skill_router.py  # 全文本路由
│   │   └── model_registry.py # 模型自动发现
│   ├── dna/                 # 数字生命体
│   │   ├── dual_consciousness.py  # 双模型意识
│   │   ├── life_engine.py   # 6 阶段生命循环
│   │   ├── autonomous_learner.py  # 自主互联网学习
│   │   ├── prompt_optimizer.py    # 提示词优化
│   │   ├── tui_orchestrator.py    # LLM→TUI 路由
│   │   ├── skill_graph.py   # 技能关系图谱
│   │   └── unified_skill_system.py # 统一技能系统
│   ├── capability/          # 能力层
│   │   ├── industrial_doc_engine.py # 工业文档引擎
│   │   ├── document_processor.py   # 长文档处理
│   │   ├── unified_search.py       # 多引擎搜索
│   │   ├── web_reach.py     # 智能网页抓取
│   │   └── ddg_search.py    # DuckDuckGo 搜索
│   ├── knowledge/           # 知识层
│   │   ├── knowledge_base.py     # 主知识库
│   │   ├── document_kb.py        # 分块文档知识库
│   │   ├── intelligent_kb.py     # 智能检索+事实核查
│   │   ├── auto_knowledge_miner.py # 自动知识挖掘
│   │   ├── struct_mem.py    # 层次化记忆
│   │   └── session_search.py     # FTS5 会话搜索
│   ├── execution/           # 执行层
│   │   ├── real_pipeline.py      # 真实任务编排
│   │   ├── panel_agent.py        # 面板自愈 Agent
│   │   ├── auto_skill_resolver.py # 自动技能补全
│   │   ├── cron_scheduler.py     # 定时任务
│   │   └── task_guard.py         # 任务防护
│   ├── network/             # 网络层
│   │   ├── p2p_node.py     # P2P 节点
│   │   └── resilience.py   # 网络韧性
│   ├── config/              # 配置
│   │   ├── settings.py     # 全局配置
│   │   ├── secrets.py      # 加密密钥存储
│   │   └── system_config.py # 系统常量
│   ├── integration/         # 集成
│   │   ├── hub.py          # 集成中枢
│   │   ├── message_gateway.py   # 多平台消息网关
│   │   ├── pkg_manager.py       # 统一包管理
│   │   └── self_updater.py      # 自动更新
│   ├── core/                # 核心基础
│   │   ├── unified_registry.py  # 统一注册表
│   │   ├── async_disk.py        # 异步磁盘 I/O
│   │   └── task_guard.py        # 任务守护
│   └── observability/       # 可观测性
│       ├── error_interceptor.py  # 全局错误捕获
│       └── system_monitor.py     # 系统资源监控
└── docs/                    # 文档
```

## 技术栈

- **UI**: Toad (Textual 8.2.5) — 终端原生界面
- **LLM 路由**: TreeLLM (自研) — 10+ provider 多路复用
- **知识库**: SQLite FTS5 + 向量余弦 + NetworkX 图谱
- **网络**: aiohttp + WebSocket P2P 中继
- **配置**: Pydantic + YAML + Fernet 加密
- **持久化**: AsyncDisk 批量异步 + SQLite WAL

## 许可证

MIT License — 详见 [LICENSE](LICENSE)
