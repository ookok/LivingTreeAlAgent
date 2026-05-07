# 🌳 LivingTree AI Agent v2.1

> 工业级自主数字生命体 — Web 全栈界面 · 经济范式驱动 · RAG 2.0 检索 · Monaco 在线编辑

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![UI](https://img.shields.io/badge/UI-Web_Components-blue)](https://github.com/ookok/LivingTreeAlAgent)
[![Models](https://img.shields.io/badge/Models-50%2B_Providers-orange)](https://models.dev)

---

## 快速开始

### 一键安装

**Windows (CMD):**
```cmd
install.bat
```

### 启动

```bash
python -m livingtree          # 启动 Web 服务 (http://localhost:8100)
python -m livingtree server   # API 服务 (无界面)
```

浏览器打开 `http://localhost:8100` 即可使用完整 Web 界面。

---

## Web 前端架构

基于组件化设计，Monaco Editor 在线代码编辑，SSE 流式通信。

```
client/web/
├── index.html              # 壳页面
├── app.js                  # 启动器
├── core/
│   └── framework.js        # 组件基类 + 事件总线
├── services/
│   ├── store.js            # 状态管理
│   ├── api.js              # SSE 流式通信
│   └── renderer.js         # Markdown 渲染
└── components/
    ├── sidebar/            # 侧栏 (会话列表)
    ├── chat/               # 对话区 (消息 + 思考面板 + 文档卡片)
    ├── input/              # 输入区 (命令/文件/语音)
    ├── code-editor/        # Monaco Editor (VS Code 内核)
    ├── dashboard/          # 仪表盘首页
    ├── boot-overlay/       # 启动进度覆盖层
    ├── context-panel/      # 右面板 (上下文/任务/知识图谱)
    ├── settings/           # 设置弹窗
    ├── doc-reader/         # 文档阅读器/编辑器
    ├── notifications/      # 通知系统
    └── user-menu/          # 用户下拉菜单
```

### 核心交互

| 功能 | 说明 |
|------|------|
| ⌨️ `/` 命令 | 输入 `/` 唤出命令菜单 (ask/do/files/learn/check/docs/team/help) |
| 📎 文件上传 | 拖拽或点击上传，支持预览 |
| 🎤 语音输入 | Web Speech API 实时转录 |
| 📝 代码编辑 | Monaco Editor 全功能 (语法高亮/补全/格式化/多文件) |
| 📄 文档卡片 | AI 回复中自动检测代码块生成预览卡片 |
| 🔀 会话分叉 | 右键消息分叉，创建平行分支 |
| 📊 仪表盘 | Token 趋势图、活动时间线、统计卡片 |
| 🔗 知识图谱 | Canvas 绘制概念关系图 |
| 🌓 主题切换 | 亮色 / 暗色双主题 |

---

## 核心能力

| 领域 | 能力 |
|------|------|
| 🤖 **LLM 路由** | 50+ 模型 (models.dev 全量同步) · 10+ Provider · 经济策略自动选型 |
| 💰 **经济引擎** | 成本-速度-质量三元优化 · ROI 追踪 · 每日预算门控 · 自动降级 |
| 📝 **批量文档** | 自然语言需求 → 智能生成 → DOCX/PDF 导出 · 含审批合规 |
| 🔍 **RAG 2.0 检索** | Agentic RAG (迭代/规划/反思) · RRF 混合融合 · Cross-Encoder 重排 |
| 🧠 **自主进化** | DGM-H 规则进化 · 幻觉式规则发现 · 全局规则池跨会话复用 |
| 🌐 **P2P 网络** | 节点能力共享 · 中继服务器内网穿透 (可选) |
| 🔧 **21+ 工具** | 高斯烟羽 · 噪声衰减 · 代码图谱 · AI 训练 · 视觉渲染 |
| ⚖️ **合规审查** | 敏感信息检测 · 环评红线 · 危险代码拦截 · 三级审查 |
| 🎯 **计划验证** | AlphaFold2 式执行前验证 · 失败模式预测 · 修复建议 |
| 📊 **适应度评分** | Pareto 多目标前沿 · 轨迹学习 · 最优工具序列推荐 |

---

## 系统架构

```
                               ┌──────────────────────────┐
                               │    Web UI (组件化前端)     │
                               │  Chat · Code · KB · Tools │
                               └────────────┬─────────────┘
                                            │ SSE / REST
                               ┌────────────▼─────────────┐
                               │     FastAPI Server        │
                               │  静态文件 + API + WS      │
                               └────────────┬─────────────┘
                                            │
                               ┌────────────▼─────────────┐
                               │     Economic Gate         │
                               │  成本/速度/质量 三元审查   │
                               │  ROI · 预算 · 合规门控    │
                               └────────────┬─────────────┘
                                            │
         ┌──────────────────┬───────────────┼───────────────┬──────────────────┐
         ▼                  ▼               ▼               ▼                  ▼
   ┌──────────┐    ┌──────────────┐  ┌───────────┐  ┌───────────┐   ┌──────────────┐
   │ TreeLLM  │    │  LifeEngine  │  │ Knowledge │  │ Execution │   │  Integration │
   │ 智能路由 │    │ 7 阶段生命循环│  │ RAG 2.0   │  │ 管道+验证  │   │  Hub + 网络  │
   └────┬─────┘    └──────┬───────┘  └─────┬─────┘  └─────┬─────┘   └──────┬───────┘
        │                 │                │              │                │
   ┌────▼─────────────────▼────────────────▼──────────────▼────────────────▼───────┐
   │                           Models & Providers                                  │
   │  DeepSeek · Qwen · LongCat · XiaoMi · SiliconFlow · Zhipu · Spark · MoFang   │
   │  Aliyun · StepFun · InternLM · Bailing · OpenCode · Web2API · 50+ more       │
   └──────────────────────────────────────────────────────────────────────────────┘
```

---

## 项目结构

```
LivingTreeAlAgent/
├── run.bat                    # Windows 一键启动
├── install.bat                # 一键部署脚本
├── relay_server.py            # P2P 中继服务器
├── pyproject.toml             # 项目配置
│
├── client/web/                # 🆕 Web 前端
│   ├── index.html             #   壳页面
│   ├── app.js                 #   启动器
│   ├── core/framework.js      #   组件基类 + 事件总线
│   ├── services/              #   服务层 (store/api/renderer)
│   └── components/            #   UI 组件 (sidebar/chat/input/code-editor...)
│
├── livingtree/
│   ├── __init__.py            # 统一 lazy import 入口
│   ├── main.py                # CLI 入口 (web/server/client/test)
│   ├── api/
│   │   ├── server.py          # 🆕 FastAPI 服务 (静态文件 + API)
│   │   └── routes.py          # 42 路由 (chat/health/tools/skills/ws...)
│   │
│   ├── economy/               # 经济引擎
│   │   └── economic_engine.py # 三元优化 · ROI · 合规 · 模型选型
│   │
│   ├── treellm/               # LLM 路由引擎
│   │   ├── core.py            # TreeLLM 主类 · RouteMoA 分层路由
│   │   ├── model_registry.py  # 模型自动发现 + models.dev 同步
│   │   └── holistic_election.py # 5 维评分选举
│   │
│   ├── dna/                   # 数字生命体
│   │   ├── life_engine.py     # 7 阶段生命循环
│   │   └── self_evolving_rules.py # DGM-H 自进化规则引擎
│   │
│   ├── knowledge/             # 知识层 (RAG 2.0)
│   │   ├── knowledge_base.py  # 主知识库 + RRF 混合融合
│   │   ├── agentic_rag.py     # Agentic RAG 自主迭代检索
│   │   └── reranker.py        # Cross-Encoder 精排
│   │
│   ├── execution/             # 执行层
│   │   ├── real_pipeline.py   # 真实任务编排
│   │   ├── plan_validator.py  # 执行前计划验证
│   │   └── fitness_landscape.py # 多目标适应度评分
│   │
│   ├── capability/            # 能力层
│   │   ├── industrial_doc_engine.py # 工业文档引擎
│   │   └── unified_visual_port.py  # 统一视觉输出管道
│   │
│   ├── network/               # 网络层
│   │   ├── scinet_service.py  # Scinet 海外加速代理
│   │   └── p2p_node.py        # P2P 节点 (中继可选)
│   │
│   ├── integration/           # 集成中枢
│   │   ├── hub.py             # 启动编排
│   │   └── launcher.py        # 🆕 服务启动 (后台 Hub 初始化)
│   │
│   ├── config/                # 配置
│   │   ├── settings.py        # Pydantic 配置模型
│   │   └── secrets.py         # Fernet 加密密钥存储
│   │
│   ├── tui/                   # 残余 (待清理)
│   │   └── wt_bootstrap.py    # WT 引导器
│   │
│   └── core/                  # 核心基础
│       └── unified_registry.py # 统一注册表
│
└── .livingtree/               # 运行时数据
    ├── model_cache/            # 模型缓存
    └── meta/                   # 语义压缩密码本
```

---

## 启动流程

```
python -m livingtree
  ├── FastAPI 服务立即启动 (0s)
  │   ├── http://0.0.0.0:8100/          → Web UI
  │   ├── http://0.0.0.0:8100/api/health  → 健康检查
  │   └── http://0.0.0.0:8100/docs        → Swagger API 文档
  │
  └── Hub 后台异步初始化 (~30s)
      ├── 同步组件加载 (_init_sync)
      └── 异步服务启动 (_init_async)
      └── Web UI 实时显示进度条
```

---

## RAG 2.0 检索管线

```
用户查询
  ├── QueryDecomposer (复杂查询分解 + HyDE 假设文档)
  ├── KnowledgeRouter (SSA 内容感知路由 → 选择 1-2 最优源)
  ├── 多路并行召回
  │     ├── FTS5 全文 (精确匹配)
  │     ├── Vector 向量 (语义相似)
  │     ├── Graph 知识图谱 (实体关系)
  │     └── Engram O(1) (热数据)
  ├── RRF 混合融合 (Reciprocal Rank Fusion, k=60)
  ├── Reranker 精排 (Cross-Encoder / LLM / Heuristic)
  ├── Agentic RAG 循环 (迭代式: 不满意→精炼查询→重检)
  └── HallucinationGuard (逐句校验 → 标注来源)
```

---

## 经济引擎

```
EconomicPolicy (成本/速度/质量三元权重)
  ├── ECONOMY  (0.60/0.15/0.25) → 日常批处理, max ¥20/日
  ├── BALANCED (0.33/0.33/0.34) → 默认
  ├── QUALITY  (0.15/0.15/0.70) → 环评报告/法律, max ¥100/日
  └── SPEED    (0.15/0.70/0.15) → 实时交互, max ¥30/日

ROIModel (投入产出比)
  任务价值 = 类型基准 × 复杂度 × 优先级 + 领域加成
  ROI = 任务价值 / 预估成本
```

---

## 技术栈

| 层次 | 技术 |
|------|------|
| **UI** | Web Components + Monaco Editor — 全功能浏览器界面 |
| **后端** | FastAPI + Uvicorn — REST + SSE + WebSocket |
| **LLM 路由** | TreeLLM RouteMoA — 分层路由 · 50+ 模型 |
| **经济引擎** | EconomicEngine — 三元优化 · ROI · 合规 |
| **知识库** | SQLite FTS5 · 向量余弦 · NetworkX 图谱 · RRF |
| **RAG** | Agentic RAG · HyDE · Reranker · Parent-Child 分块 |
| **网络** | aiohttp · WebSocket P2P (可选) · Scinet 代理 |
| **安全** | Fernet 加密 · ComplianceGate · SafetyGuard |
| **可观测** | loguru · Analytics · 全链路埋点 |
| **配置** | Pydantic · YAML · Fernet 加密 |

---

## 许可证

MIT License — 详见 [LICENSE](LICENSE)
