# 🌳 LivingTree AI Agent v2.1

> 工业级自主数字生命体 — 经济范式驱动 · RAG 2.0 检索 · 多模型自适应路由

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![UI](https://img.shields.io/badge/UI-Toad-blue)](https://github.com/batrachianai/toad)
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
livingtree              # TUI 对话界面
livingtree relay        # 启动中继服务器
python -m livingtree tui # 直接 TUI
```

**快捷启动 (Windows 便携版):**
- 双击 `wt-quick.bat` → Windows Terminal + LivingTree TUI
- 双击 `scinet-quick.bat` → 独立 Scinet 代理 (端口 7890)

---

## 核心能力

| 领域 | 能力 |
|------|------|
| 🤖 **LLM 路由** | 50+ 模型 (models.dev 全量同步) · 10+ Provider · 经济策略自动选型 |
| 💰 **经济引擎** | 成本-速度-质量三元优化 · ROI 追踪 · 每日预算门控 · 自动降级 |
| 📝 **批量文档** | 自然语言需求 → 智能生成 → DOCX/PDF 导出 · 含审批合规 |
| 🔍 **RAG 2.0 检索** | Agentic RAG (迭代/规划/反思) · RRF 混合融合 · Cross-Encoder 重排 |
| 🧠 **自主进化** | DGM-H 规则进化 · 幻觉式规则发现 · 全局规则池跨会话复用 |
| 🌐 **P2P 网络** | 节点能力共享 · 中继服务器内网穿透 |
| 🔧 **21+ 工具** | 高斯烟羽 · 噪声衰减 · 代码图谱 · AI 训练 · 视觉渲染 |
| ⚖️ **合规审查** | 敏感信息检测 · 环评红线 · 危险代码拦截 · 三级审查 |
| 🎯 **计划验证** | AlphaFold2 式执行前验证 · 失败模式预测 · 修复建议 |
| 📊 **适应度评分** | Pareto 多目标前沿 · 轨迹学习 · 最优工具序列推荐 |

---

## 系统架构

```
                              ┌──────────────────────────┐
                              │    TUI (Toad + Textual)   │
                              │  Chat · Code · KB · Tools │
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
├── main.py                   # 主入口
├── relay_server.py           # P2P 中继服务器
├── pyproject.toml            # 项目配置
├── install.bat               # Windows 一键部署
├── wt-quick.bat              # WT 便携版快捷启动
├── scinet-quick.bat          # Scinet 代理快捷启动
├── .wt/settings.json         # Windows Terminal 配置
│
├── livingtree/
│   ├── __init__.py           # 统一 lazy import 入口
│   │
│   ├── economy/              # 🆕 经济引擎
│   │   └── economic_engine.py  # 三元优化 · ROI · 合规 · 模型选型
│   │
│   ├── treellm/              # LLM 路由引擎
│   │   ├── core.py             # TreeLLM 主类 · RouteMoA 分层路由
│   │   ├── model_registry.py   # 模型自动发现 + models.dev 同步
│   │   ├── models_dev_sync.py  # 🆕 models.dev 全量同步 (50+厂商)
│   │   ├── holistic_election.py # 5 维评分选举
│   │   ├── foresight_gate.py   # 执行预测门控
│   │   └── skill_router.py     # 全文本技能路由
│   │
│   ├── dna/                  # 数字生命体
│   │   ├── life_engine.py      # 7 阶段生命循环 (1650行)
│   │   ├── dual_consciousness.py # 双模型意识
│   │   ├── self_evolving_rules.py # 🆕 DGM-H 自进化规则引擎
│   │   ├── self_evolving.py    # 代码自进化
│   │   ├── evolution_store.py  # 进化记忆存储
│   │   ├── prompt_optimizer.py # 提示词优化 (693行)
│   │   └── output_compressor.py # 🆕 上下文压缩 (含进化规则)
│   │
│   ├── knowledge/            # 知识层 (RAG 2.0)
│   │   ├── knowledge_base.py   # 主知识库 + RRF 混合融合 (832行)
│   │   ├── agentic_rag.py      # 🆕 Agentic RAG 自主迭代检索
│   │   ├── reranker.py         # 🆕 Cross-Encoder 精排
│   │   ├── hierarchical_chunker.py # 🆕 父子文档切分
│   │   ├── intelligent_kb.py   # 智能检索 + 事实核查
│   │   ├── struct_mem.py       # 层次化记忆 (1406行)
│   │   ├── query_decomposer.py # 查询分解 + HyDE
│   │   └── retrieval_validator.py # 检索质量验证
│   │
│   ├── execution/            # 执行层
│   │   ├── real_pipeline.py    # 真实任务编排 + PipelineOptimizer
│   │   ├── react_executor.py   # ReAct 执行器 + TACO 压缩
│   │   ├── plan_validator.py   # 🆕 执行前计划验证
│   │   ├── fitness_landscape.py # 🆕 多目标适应度评分
│   │   ├── diffusion_planner.py # 🆕 渐进式计划精炼
│   │   ├── global_rule_pool.py # 🆕 跨会话压缩规则池
│   │   ├── terminal_compressor.py # 🆕 终端输出压缩
│   │   ├── context_codex.py    # 语义符号压缩
│   │   ├── cost_aware.py       # 🆕 成本追踪 + 千问定价 + models.dev 同步
│   │   └── dag_executor.py     # DAG 并行执行
│   │
│   ├── capability/           # 能力层 (61 文件)
│   │   ├── industrial_doc_engine.py  # 工业文档引擎
│   │   ├── unified_visual_port.py    # 🆕 统一视觉输出管道
│   │   ├── code_engine.py     # 代码生成
│   │   └── tool_executor.py   # 工具执行器
│   │
│   ├── network/              # 网络层 (22 文件)
│   │   ├── scinet_service.py  # 🆕 Scinet 海外加速代理
│   │   └── resilience.py      # 网络韧性
│   │
│   ├── integration/          # 集成中枢 (11 文件)
│   │   └── hub.py             # 启动编排 (1583 行)
│   │
│   ├── config/               # 配置 (6 文件)
│   │   ├── secrets.py         # Fernet 加密密钥存储
│   │   └── system_config.py   # 系统常量
│   │
│   ├── tui/                  # TUI 界面
│   │   ├── app.py             # App 主类
│   │   ├── td/                # Toad 框架 (48 文件)
│   │   ├── widgets/           # UI 组件 (73 文件)
│   │   └── screens/           # 面板 (25 文件)
│   │
│   └── core/                 # 核心基础 (12 文件)
│       └── unified_registry.py # 统一注册表
│
└── .livingtree/              # 运行时数据
    ├── model_cache/          # 模型缓存 (models_dev.json)
    ├── meta/codex.json       # 语义压缩密码本
    └── meta/evolve/          # 进化历史
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
  │     └── Attention-Weighted RRF (RuView 多频段)
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

ComplianceGate (三级合规审查)
  ├── 敏感信息检测 (身份证/银行卡/API密钥)
  ├── 环评红线 (伪造数据/瞒报排放/越权审批)
  └── 危险代码 (DROP TABLE/rm -rf/chmod 777)

ROIModel (投入产出比)
  任务价值 = 类型基准 × 复杂度 × 优先级 + 领域加成
  ROI = 任务价值 / 预估成本
  累计ROI = Σ价值 / Σ成本
```

---

## 技术栈

| 层次 | 技术 |
|------|------|
| **UI** | Toad (Textual 8.2.5) — 终端原生界面 |
| **LLM 路由** | TreeLLM RouteMoA — 分层路由 · 50+ 模型 |
| **经济引擎** | EconomicEngine — 三元优化 · ROI · 合规 |
| **知识库** | SQLite FTS5 · 向量余弦 · NetworkX 图谱 · RRF |
| **RAG** | Agentic RAG · HyDE · Reranker · Parent-Child 分块 |
| **压缩** | TACO 终端压缩 · ContextCodex 语义符号 · ContextFold |
| **网络** | aiohttp · WebSocket P2P 中继 · Scinet 代理 |
| **安全** | Fernet 加密 · ComplianceGate · SafetyGuard |
| **可观测** | loguru · Analytics · 全链路埋点 |
| **配置** | Pydantic · YAML · Fernet 加密 |

---

## 关键模型

| 模型 | 输入 ¥/1M | 输出 ¥/1M | Context | 用途 |
|------|----------|-----------|---------|------|
| deepseek-v4-pro | 3.0 | 6.0 | 128K | 高复杂度推理 |
| deepseek-v4-flash | 1.0 | 2.0 | 128K | 日常快速 |
| qwen3.6-plus | 2.90 | 17.40 | 1M | 旗舰多模态 |
| qwen3.6-flash | 0.73 | 2.90 | 1M | 极低成本 |
| qwq-plus | 5.80 | 17.40 | 128K | 思维推理 |

> 📊 **全量模型定价** → 自动从 [models.dev](https://models.dev) 同步 (6h 刷新)

---

## 许可证

MIT License — 详见 [LICENSE](LICENSE)
