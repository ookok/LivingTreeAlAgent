# 🌳 LivingTree AI Agent

> 🌳 数字生命体 — AI驱动的自我进化智能代理平台 | v2.0.0

**LivingTree** 是一个开源的数字生命体平台。它不是一个聊天框架，也不是一个 LLM 封装器——它是一个具备**认知、规划、执行、反思、进化**完整闭环的自治系统。

基于 **Python** + **Textual TUI** + **LiteLLM** 构建，通过 **Windows Terminal** 启动，提供接近原生 GUI 的终端体验。

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![Textual](https://img.shields.io/badge/Textual-8.2%2B-green)](https://textual.textualize.io)

---

## 概述

LivingTree 的核心是一个 **6 阶段数字生命管线**：

```
感知 → 认知 → 规划 → 执行 → 反思 → 进化
```

- **DeepSeek 双模型驱动**: flash (快速意图) + pro (深度推理+思考模式)
- **30 个内置工具**: 文件/代码/知识库/文档/地图/邮箱/模型计算/专家训练/技能
- **自进化**: 精英保留 + 思维交叉变异 + 基因组策略控制
- **Bi-temporal 知识库**: 时间点查询，"曾经为真≠当前为真"
- **16 层安全**: Merkle 审计链 + 路径防护 + SSRF + 提示注入扫描 + 密钥零化

---

## 快速开始

### 安装

```powershell
git clone https://github.com/ookok/LivingTreeAlAgent.git
cd LivingTreeAlAgent
pip install -r requirements.txt
```

### 配置 DeepSeek API Key

```powershell
python -c "from livingtree.config.secrets import SecretVault; v=SecretVault('config/secrets.enc'); v.set('deepseek_api_key','sk-your-key')"
```

### 启动

```powershell
# TUI 终端界面 (推荐)
python -m livingtree tui

# FastAPI 服务
python -m livingtree server

# 集成测试
python -m livingtree test
```

首次启动会自动检查 Windows Terminal，如未安装则自动下载。

---

## 核心架构

```
livingtree/
├── dna/              # 生命蓝图
│   ├── life_engine.py      # 6阶段管线引擎
│   ├── dual_consciousness.py # LiteLLM 双模型路由
│   ├── living_world.py     # 统一系统上下文
│   ├── genome.py           # 数字基因组
│   └── safety.py           # 16层安全防护
├── cell/             # 细胞AI
│   ├── cell_ai.py          # 可训练细胞
│   ├── distillation.py     # 知识蒸馏
│   ├── mitosis.py          # 细胞分裂
│   ├── phage.py            # 代码吞噬(AST)
│   └── swift_trainer.py    # MS-SWIFT训练
├── knowledge/        # 知识管理
│   ├── knowledge_base.py   # Bi-temporal知识库
│   ├── vector_store.py     # 向量存储
│   └── knowledge_graph.py  # 知识图谱
├── capability/       # 能力工厂
│   ├── tool_market.py      # 30个工具注册
│   ├── doc_engine.py       # 5类报告/176节
│   ├── code_engine.py      # 自注释代码生成
│   ├── ast_parser.py       # Tree-sitter AST
│   ├── code_graph.py       # 代码知识图
│   └── tianditu.py         # 天地图集成
├── execution/        # 任务编排
│   ├── task_planner.py     # 5领域模板
│   ├── orchestrator.py     # 17Agent调度
│   ├── thinking_evolution.py # 认知进化
│   ├── quality_checker.py  # 7阶段质量检查
│   ├── hitl.py             # 人机协同暂停
│   ├── checkpoint.py       # 断点续传
│   └── cost_aware.py       # 预算管控
├── network/          # P2P网络
├── integration/      # 系统集成中枢
├── api/              # FastAPI服务
├── config/           # 配置+加密保险库
├── observability/    # 日志/追踪/指标
├── tui/              # Textual终端界面
│   ├── screens/      # Chat/Code/Docs/Settings
│   └── widgets/      # 任务树/文件选择器/仪表盘
└── mcp/              # MCP协议服务(21工具)
```

---

## 功能矩阵

| 能力 | 说明 |
|------|------|
| **AI 对话** | DeepSeek 双模型, Markdown渲染, 流式输出, 思考模式 |
| **代码生成** | 自注释代码, AST解析, 调用链分析, 爆炸半径, 14语言语法高亮 |
| **知识管理** | Bi-temporal知识库, 时间点回溯, 向量搜索, 格式发现, 空白检测 |
| **文档生成** | 环评/应急预案/验收/可研报告, 共176节标准模板 |
| **细胞训练** | LoRA微调 + MS-SWIFT全流程 + 知识蒸馏 + 课程学习 |
| **P2P网络** | 节点发现(LAN/DHT), NAT穿透, 加密通道, 信誉系统 |
| **自进化** | 精英保留, 思维交叉变异, 基因组策略, 自我修复 |
| **安全防护** | Merkle审计链, 路径穿越, SSRF, 提示注入, 零化密钥 |
| **地图服务** | 天地图瓦片, 地理编码, 终端地图渲染 |
| **邮箱** | SMTP真实发送 (163.com) |
| **计算模型** | 高斯扩散, 噪声衰减, 河流稀释, Pasquill-Gifford参数 |

### 30 个内置工具

| 类别 | 工具 |
|------|------|
| **文件** | read_file, write_file, list_directory, search_files |
| **代码** | parse_ast, find_callers, find_callees, blast_radius, index_codebase, search_code, generate_code |
| **知识** | search_knowledge, add_knowledge, detect_gaps, discover_formats |
| **文档** | generate_report |
| **网络** | fetch_url |
| **系统** | get_status, list_cells |
| **地图** | lookup_location, geocode_reverse, static_map |
| **邮箱** | send_email |
| **训练** | distill_knowledge, curriculum_learning |
| **技能** | list_skills, create_skill |
| **模型** | gaussian_plume, noise_attenuation, water_dilution, dispersion_coeff |

---

## TUI 界面

```
┌──────────────────────────────────────────────────────┐
│  LivingTree AI Agent — www.livingtree-ai.com        │
├──────────────────────────────────────────────────────┤
│  Chat │ Code │ Docs │ Settings                       │
├─────────┬────────────────────────────────────────────┤
│ ⠋ Task  │  ### You                                  │
│ Pipeline│  帮我生成环评报告                           │
│         │                                            │
│ ● 感知  │  ### AI                                    │
│ ● 认知  │  **分析结果:**                              │
│ ◐ 规划  │  │章节    │状态  │                        │
│ ○ 执行  │  │总论    │完成  │                        │
│ ○ 反思  │  │工程…   │进行中│                        │
│ ○ 进化  │                                            │
│         ├────────────────────────────────────────────┤
│ tokens  │ [输入框]                         ▸ Send    │
│ ¥0.001  │                                            │
├─────────┴────────────────────────────────────────────┤
│ ^Q Quit │ www.livingtree-ai.com │ livingtreeai@163  │
└──────────────────────────────────────────────────────┘
```

**快捷键**: `Ctrl+1-4` 切换标签 | `Ctrl+P` 命令面板 | `Ctrl+D` 主题 | `Ctrl+Q` 退出

---

## API 端点

```
POST /api/chat              — AI 对话
GET  /api/health            — 健康检查
GET  /api/status            — 系统状态
GET  /api/tools             — 工具列表
GET  /api/skills            — 技能列表
GET  /api/metrics           — 指标
POST /api/report/generate   — 生成报告
POST /api/cell/train        — 训练细胞
POST /api/drill/train       — MS-SWIFT训练
GET  /api/hitl/pending      — 待审批
POST /api/hitl/approve      — 批准
GET  /api/cost/status       — 预算/成本
GET  /api/checkpoint/sessions — 检查点
WS   /ws                    — WebSocket
```

---

## 联系方式

- 🌐 官网: [www.livingtree-ai.com](https://www.livingtree-ai.com)
- 📧 邮箱: livingtreeai@163.com
- 🐙 GitHub: [ookok/LivingTreeAlAgent](https://github.com/ookok/LivingTreeAlAgent)

## 许可

MIT License — 详见 [LICENSE](LICENSE)
