# LivingTreeAI - 自我进化智能代理平台

> *「根系装配园开放，每一位开发者都是嫁接者，将创新的枝条接入生命之树。」*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-green.svg)](https://pypi.org/project/PyQt6/)
[![GitHub: Issues](https://img.shields.io/github/issues/ookok/LivingTreeAlAgent)](https://github.com/ookok/LivingTreeAlAgent/issues)
[![GitHub: Stars](https://img.shields.io/github/stars/ookok/LivingTreeAlAgent)](https://github.com/ookok/LivingTreeAlAgent/stargazers)
[![Build Status](https://img.shields.io/badge/Build-Passing-green.svg)]()

---

## 🌱 愿景

**LivingTreeAI** 是一个具备**自我意识**和**自我进化**能力的智能代理平台，融合意图驱动IDE、多智能体协作与自我进化能力，让AI真正成为你的数字伙伴。

```
LivingTreeAI = 智能代理平台 + 自我进化系统 + 意图驱动IDE + 领域面板 + 基础设施
```

我们正在构建的不是一个普通的AI助手，而是一个能够：

- 🌱 **自我生长** - 从经验中学习，不断优化
- 🔄 **自我修复** - 自动检测并修复问题
- 💡 **理解意图** - 听懂你想做什么，而非只是你说了什么
- 🤝 **协作进化** - 多智能体协同工作，共同成长
- 📊 **领域专家** - 金融、游戏、企业等多领域专业面板
- 🌐 **去中心化** - P2P网络、去中心化电商、分布式存储

---

## 🚀 核心特性

### 1. 意图驱动交互 💡

LivingTreeAI 使用先进的意图识别引擎（AIIntentEngine），能够理解用户的真实需求，而非简单的命令执行。

```python
from client.src.business.ai_intent_engine import AIIntentEngine

engine = AIIntentEngine()
intent = engine.parse("帮我写一个用户登录接口，要用 FastAPI")
# 自动理解意图，生成代码，验证结果
# 支持13种意图类型识别
# 技术栈检测、推理过程分析
```

**AIIntentEngine 特性**：
- 服务: http://www.mogoo.com.cn:8899/v1
- 模型: qwen3.5:4b
- 支持13种意图类型识别
- 技术栈检测、推理过程分析

### 2. 自我进化引擎 🔄

系统能够自动进化、测试、修复，无需人工干预。通过遗传算法、NSGA-II 多目标优化、表观遗传等技术，实现真正的自我进化。

```python
from client.src.business.evolution_engine import EvolutionEngine

engine = EvolutionEngine()
# 自动进化、测试、修复，无需人工干预
```

**核心能力**：
- 🧬 遗传算法优化
- 📊 NSGA-II 多目标优化（非支配排序+拥挤度距离）
- 🔄 自适应进化策略（实时参数调整）
- 🧬 表观遗传（Lamarckian + Baldwinian）
- 🔧 热修复引擎（自动修复代码）
- 🔍 根因追踪器（问题根源分析）
- 📊 可视化进化引擎（PyQt6 GUI）

**自我进化子系统（13个模块）**：
1. **NSGA2Engine** - 多目标进化优化
2. **AdaptiveEvolutionEngine** - 自适应进化策略
3. **EpigeneticEngine** - 表观遗传引擎
4. **LamarckianLearner** - 拉马克主义（学习获得性状直接写入基因）
5. **BaldwinianLearner** - 鲍德温效应（学习能力影响适应度，基因不遗传）
6. **CrossoverEngine** - 交叉遗传（7种策略）
7. **SelfAwarenessSystem** - 自我意识系统（零干扰后台自动升级修复）
   - MirrorLauncher - 镜像启动器（沙盒测试环境）
   - ComponentScanner - 组件扫描器（自动发现UI组件）
   - ProblemDetector - 问题检测器（异常分析/语法检查）
   - HotFixEngine - 热修复引擎（自动修复代码）
   - AutoTester - 自动测试执行器（镜像环境测试）
   - RootCauseTracer - 根因追踪器（问题根源分析）
   - DeploymentManager - 部署管理器（修复部署/回滚）
   - BackupManager - 备份管理器（版本备份/恢复）
8. **EvolutionPanel** - 进化引擎 UI 可视化面板（PyQt6）
9. **ParameterTuner** - 参数调优器
10. **ABTestFramework** - A/B测试框架
11. **SelfDiagnosis** - 系统自我诊断
12. **VisualEvolutionEngine** - 可视化进化引擎（遗传算法）
13. **SmartProxyGateway** - 智能代理网关（负载均衡/故障转移）

### 3. 多智能体协作 🤝

支持多智能体协同工作，自动任务分解、分配、执行、聚合。所有面板都通过 Agent 调用功能，确保架构统一。

```python
from client.src.business.hermes_agent import HermesAgent

agent1 = HermesAgent(name="Coder")
agent2 = HermesAgent(name="Tester")
agent1.collaborate(agent2)
# 自动任务分解、分配、执行、聚合
```

**多智能体系统（14个模块）**：
1. MultiAgentWorkflow - 多代理工作流
2. DynamicTaskDecomposer - 任务分解
3. AgentLifecycleManager - 生命周期
4. AgentMemoryStore - 记忆存储
5. SharedMemorySpace - 共享空间
6. AgentMemoryBridge - 记忆桥接
7. TaskScheduler - 任务调度
8. ResultAggregator - 结果聚合
9. ConflictResolver - 冲突解决
10. AgentProtocol - 通信协议
11. MetricsCollector - 指标收集
12. PerformanceMonitor - 性能监控
13. IntentCache - 意图缓存
14. OrchestrationViewer - 编排可视化

**面板 Agent 架构**：
| 面板 | Agent 类 | 架构路径 |
|------|----------|----------|
| 智能写作 | `WritingAgent` | UI → WritingAgent → HermesAgent → GlobalModelRouter → LLM |
| 搜索 | `SearchAgent` | UI → SearchAgent → HermesAgent → GlobalModelRouter → LLM |
| 专家训练 | `TrainingAgent` | UI → TrainingAgent → HermesAgent → GlobalModelRouter → LLM |
| 知识库 | `KnowledgeAgent` | UI → KnowledgeAgent → HermesAgent → GlobalModelRouter → LLM |
| IDE | `IdeAgent` | UI → IdeAgent → HermesAgent → GlobalModelRouter → LLM |
| 聊天 | `HermesAgent` (直接使用) | UI → HermesAgent → GlobalModelRouter → LLM |

### 4. 融合RAG（FusionRAG）📚

多源数据检索系统，结合向量检索、图谱检索、混合检索，提供精准的知识检索能力。

**三层架构**：
- L1: 向量检索（Dense Retrieval）
- L1.5: 本地文件极速搜索（FastFileIndexer，搜索延迟 6-8ms）
- L2: 图谱检索（Graph Retrieval）
- L3: 混合检索（Hybrid Retrieval）

**本地文件极速搜索**：
- 核心: FastFileIndexer - SQLite + 批量索引，搜索延迟 6-8ms
- 增量同步: USN Journal 监听（Windows）+ 轮询回退
- FusionRAG 集成: L1.5 层（LocalFileSearchRouter）
- 支持意图识别: 找文件、代码搜索、文档搜索等

### 5. 领域面板 📊

针对不同领域提供专业面板：

#### 已完成领域面板
- 💰 **FinanceHubPanel** - 金融面板（Dashboard/Investment/Payment/Credit/Project/Economics）
- 🎮 **GameHubPanel** - 游戏面板（Library/Session/Achievement/Stats）
- 🚢 **EnterpriseCockpitPanel** - 企业驾驶舱（存储管理/节点管理/任务调度/权限管理/同步状态）
- 🛒 **DeCommercePanel** - 去中心化电商（卖家中心/买家市场/会话管理/订单管理/AI能力/穿透网络/存证审计）

#### 规划中领域面板
- 🏥 **HealthHubPanel** - 健康面板（规划中）
- 📚 **EducationHubPanel** - 教育面板（规划中）

### 6. 企业级功能 🏢

#### P2P CDN 存储系统
- `client/src/business/enterprise/storage.py` - 企业存储系统（基于P2P CDN）
- 功能：分布式存储、文件夹管理、数据冗余、智能路由

#### 虚拟云盘引擎
- `client/src/business/virtual_cloud_engine.py` - 虚拟云盘引擎（715行）
- 功能：多驱动统一管理、虚拟路径解析、元数据缓存、额度感知调度
- 支持云盘：阿里云盘、Quark、115、OneDrive

#### 企业模块（9个模块）
1. `node_manager.py` - 节点管理器
2. `virtual_filesystem.py` - 虚拟文件系统
3. `storage.py` - 企业存储系统
4. `version_control.py` - 版本控制
5. `permission.py` - 权限管理
6. `file_preview.py` - 文件预览
7. `sync.py` - 同步管理
8. `task_scheduler.py` - 任务调度器
9. `intelligent_router.py` - 智能路由器

#### 企业级应用场景集成
- `client/src/business/enterprise_integration.py` - 企业集成（37.5 KB）
- 功能：场景适配器、行业模板库、工作流编排器、业务指标监控

#### 企业操作系统
- `client/src/business/living_tree_ai/enterprise_os/` - 企业OS（13个文件）
- 功能：企业数字孪生、合规知识图谱、风险预警、智能表单

### 7. 统一平台模块 🌐

内置平台功能，支持AI之间、AI与用户之间的交流：

1. **论坛（ForumTab）** - 创建帖子、查看帖子、回复帖子
2. **博客（BlogTab）** - 发布博客、查看博客详情
3. **邮箱（EmailTab）** - 写邮件、查看收件箱、配置邮件账户
4. **IM（IMTab）** - 添加联系人、发送消息、接收消息
5. **AI协作（AICollabTab）** - 发现Agent、创建任务、查看任务状态

**集成模块**：
- 论坛：`server/relay_server/services/blog_forum_api.py` + `client/src/business/forum/`
- 博客：集成在`blog_forum_api.py`中
- 邮箱：`server/relay_server/email_sender.py`
- IM：`client/src/business/unified_chat/chat_hub.py`
- AI协作：`client/src/business/a2a_protocol/` + `client/src/business/unified_platform/hermes_message_hub.py`

### 8. 去中心化电商 🛒

系统已有完整的 P2P 去中心化电商模块实现！

**核心业务逻辑** (`client/src/business/decommerce/`):
1. `models.py` - 数据模型 (ServiceListing, ServiceSession, Order, Seller)
2. `seller_node.py` - 卖家节点 (微服务器)
3. `buyer_client.py` - 买家客户端
4. `payment_guard.py` - 支付守卫 (佣金集成)
5. `service_registry.py` - 服务注册与发现
6. `edge_relay_network.py` - Edge Relay 网络穿透
7. `datachannel_transport.py` - DataChannel 传输
8. `crdt_order.py` - CRDT 订单管理 (冲突解决)
9. `audit_trail.py` - 存证审计系统
10. `ai_capability_registry.py` - AI 能力注册
11. `listing_broadcast.py` - 商品广播
12. `broker_service.py` - Broker 服务
13. `decentralized_order.py` - 去中心化订单
14. `logistics_tracker.py` - 物流追踪
15. `virtual_delivery.py` - 虚拟交付

**服务类型支持**：
1. 实物商品 (静态图文)
2. 远程实景直播 (WebRTC 视频穿透)
3. AI 计算服务 (DataChannel → 本地 Ollama)
4. 远程代操作 (DataChannel + 脚本执行)
5. 知识咨询 (音视频通话 + 屏幕共享)
6. 数字商品 (可下载文件)

### 9. 智能搜索联想 🔍

- `client/src/presentation/widgets/knowledge_suggestion.py` - 知识库联想组件
- 功能：所有输入框支持从知识库联想
- 特性：在输入下方出现推荐面板，最多显示5行，支持键盘上下选择、回车确认、ESC关闭，带防抖机制（200ms）

**SearchAgent 增强**：
- 支持文档搜索（PDF/DOCX/TXT）
- 支持图片搜索（JPG/PNG，多模态）
- 支持语义搜索（使用向量相似度）
- 支持文本压缩（使用语义压缩）
- 支持分块处理（SemanticChunker，5种策略）

### 10. 知识自动领航员 🧭

- `client/src/business/knowledge_autopilot.py` - 知识自动领航员
- 功能：自动发现知识缺口、智能调度搜索、自动验证更新

**核心模块**：
1. `VectorAwareGapDetector` - 向量感知的缺口发现（语义级）
2. `IntelligentCrawlerScheduler` - 智能爬虫调度器
3. `KnowledgeAutopilot` - 全自动知识增长系统

**闭环知识进化流程**：
```
用户输入长文本/上传文档
    ↓
SemanticChunker 分块
    ↓
VectorAwareGapDetector 发现缺口
    ↓
IntelligentCrawlerScheduler 调度爬取
    ↓
KnowledgeAutopilot 填补缺口
    ↓
向量库更新
    ↓
循环（直到收敛）
```

### 11. 环境感知模块 🌍

- `client/src/business/environment_awareness.py` - 动态获取用户位置信息
- 功能：动态本地化搜索，根据位置信息动态生成本地来源

**位置获取优先级**：
1. 系统配置（用户手动设置）
2. IP 地址地理位置（自动检测）
3. 默认值（未获取到时使用）

### 12. 专家管理系统 🎓

- `client/src/presentation/panels/expert_management_panel.py` - 专家管理面板
- `client/src/presentation/panels/expert_detail_panel.py` - 专家详情面板

**功能**：
- 专家命名规范化（"行业+职业"格式，如：金融_分析师、医疗_医生）
- 专家详情管理（简介/技能树/版本说明）
- 专家同步功能（上传到中继服务器、从中继服务器下载）

**集成**：
- 集成到训练面板（作为第6个Tab）
- 智能写作界面支持邀请专家

---

## 🏗️ 技术架构

### 已完成迁移（2026-04-26）

项目已完成从 `core/` + `ui/` 到 `client/src/` 的迁移，采用清晰的三层架构：

```
LivingTreeAlAgent/
├── client/src/                  # ✅ 所有代码已迁移到此
│   ├── main.py                  # PyQt6 入口 → HomePage
│   ├── business/               # 业务逻辑 (~340+ 文件)
│   │   ├── amphiloop/         # 调度系统
│   │   ├── optimization/       # PRISM 优化
│   │   ├── enterprise/         # P2P 存储 & 任务调度 (9个模块)
│   │   ├── digital_twin/       # 数字孪生
│   │   ├── credit_economy/     # 积分系统
│   │   ├── decommerce/         # 去中心化电商 (15个模块)
│   │   ├── living_tree_ai/     # 语音、浏览器、会议 (300+ files)
│   │   ├── fusion_rag/         # 多源检索
│   │   ├── knowledge_graph/    # 知识图谱
│   │   ├── plugin_framework/   # 插件框架
│   │   ├── hermes_agent/       # Agent 框架
│   │   ├── p2p_*/             # P2P 网络通信 (7个模块)
│   │   ├── personal_mode/      # 个性化配置
│   │   ├── ecc_*/              # Agent 本能/技能
│   │   ├── evolving_community/ # 社区进化
│   │   ├── intelligent_hints/  # 智能提示
│   │   ├── office_automation/  # 办公自动化
│   │   ├── long_context/       # 长上下文处理
│   │   │   ├── adaptive_compressor.py      # 自适应差异化压缩
│   │   │   ├── semantic_chunker.py        # LLM 驱动的语义分块
│   │   │   └── progressive_understanding.py # 渐进式理解
│   │   ├── ai_intent_engine.py          # AI意图引擎（Ollama驱动）
│   │   ├── evolution_engine/            # 进化引擎 (13个模块)
│   │   ├── knowledge_autopilot.py      # 知识自动领航员
│   │   ├── environment_awareness.py   # 环境感知模块
│   │   ├── nanochat_config.py         # NanochatConfig (dataclass-based)
│   │   ├── config.py                  # UnifiedConfig 兼容层
│   │   └── ...                        # ~300+ 更多模块
│   ├── presentation/           # UI (~200+ 文件)
│   │   ├── panels/            # 所有面板 (102+ 文件)
│   │   │   ├── enterprise_cockpit_panel.py  # 企业驾驶舱面板
│   │   │   ├── decommerce_panel.py          # 去中心化电商面板
│   │   │   ├── finance_hub_panel.py        # 金融面板
│   │   │   ├── game_hub_panel.py          # 游戏面板
│   │   │   ├── evolution_panel.py         # 进化引擎面板
│   │   │   ├── expert_management_panel.py # 专家管理面板
│   │   │   └── ...                        # 其他面板
│   │   ├── components/        # 可复用组件 (50+ files)
│   │   ├── widgets/          # 自定义控件 (30+ files)
│   │   │   ├── knowledge_suggestion.py    # 知识库联想组件
│   │   │   └── ...
│   │   ├── dialogs/          # 对话框窗口 (20+ files)
│   │   ├── modules/          # 子模块 (50+ files)
│   │   │   ├── unified_platform/         # 统一平台模块
│   │   │   │   ├── panel.py             # 主面板窗口（QTabWidget）
│   │   │   │   ├── forum_tab.py        # 论坛功能Tab
│   │   │   │   ├── blog_tab.py         # 博客功能Tab
│   │   │   │   ├── email_tab.py        # 邮箱功能Tab
│   │   │   │   ├── im_tab.py           # IM功能Tab
│   │   │   │   └── ai_collab_tab.py    # AI协作Tab
│   │   │   ├── search/                 # 搜索模块
│   │   │   ├── training/               # 专家训练模块
│   │   │   ├── knowledge/              # 知识库模块
│   │   │   ├── ide/                    # IDE模块
│   │   │   └── writing/               # 智能写作模块
│   │   └── ...
│   ├── infrastructure/         # 数据库、配置、网络
│   │   ├── database/         # 数据库迁移 (v1-v14)
│   │   ├── config/           # 配置管理
│   │   ├── network/          # 网络通信
│   │   ├── model/            # 模型管理
│   │   └── storage/         # 存储管理
│   └── shared/               # 共享工具
├── server/                     # 服务器层
│   ├── relay_server/           # FastAPI relay (api/, cluster/, database/)
│   └── tracker_server.py      # P2P tracker
├── app/                        # 独立企业应用
├── mobile/                     # PWA/移动端
├── packages/                   # 共享库
│   ├── living_tree_naming/    # 命名规范
│   └── shared/               # 共享代码
├── tests/                      # 测试套件
├── docs/                       # 文档
│   ├── 系统架构梳理_2026-04-26.md
│   ├── 待办任务清单_2026-04-26.md
│   └── ...
└── config/                     # 配置文件
```

**✅ 迁移完成**：
- `core/` → `client/src/business/` (28个子目录 + 44个独立文件)
- `ui/` → `client/src/presentation/` (102个文件 + 39个子目录)
- 所有导入引用已更新
- 临时脚本和过时文档已清理

### 五大技术支柱

| 支柱 | 定位 | 核心能力 | 状态 |
|------|------|----------|------|
| 🧠 **智能代理** | 核心引擎 | 多智能体协作、任务分解、知识管理 | ✅ 100% |
| 🔄 **自我进化** | 差异化优势 | 自我测试、诊断、修复、进化 | ✅ 100% |
| 💡 **意图驱动** | 用户接口 | 自然语言交互、代码生成、验证 | ✅ 100% |
| 📊 **领域面板** | 功能载体 | 金融面板、游戏面板、企业驾驶舱、去中心化电商 | 🔄 80% |
| 🔧 **基础设施** | 技术底座 | 统一配置、代理网关、A2A协议、P2P网络 | ✅ 100% |

---

## 📈 项目进度

| 阶段 | 状态 | 核心模块数 | 完成度 | 备注 |
|------|------|-----------|--------|------|
| **Phase 0: 基础夯实** | ✅ | - | 100% | 完成 |
| **Phase 1: 核心引擎** | ✅ | 10个 | 100% | 完成 |
| **Phase 2: 智能代理** | ✅ | 14个 | 100% | 完成 |
| **Phase 3: 领域面板** | 🔄 | 4个 | 80% | 进行中 |
| **Phase 4: 自我进化** | ✅ | 13个 | 100% | 完成 |
| **Phase 5: 生态完善** | 🔄 | 2个 | 60% | 进行中 |
| **Phase 6: 云原生** | 🔄 | 5个 | 20% | 启动 |

### Phase 详细进度

#### Phase 1: 核心引擎 (10个模块) ✅ 100%
- ✅ IntentEngine MVP - 意图驱动引擎（规则版）
- ✅ **AIIntentEngine** - AI意图引擎（Ollama驱动）
- ✅ EvolutionEngine - 进化引擎
- ✅ 自我意识系统 - 五层架构
- ✅ PyQt6测试指挥官 - AI测试GUI
- ✅ A2A协议 - 多智能体通信
- ✅ 智能代理编排 - DAG工作流
- ✅ 知识区块链 - PoC贡献
- ✅ 统一代理网关 - SmartProxyGateway
- ✅ IDE Intent Panel - 意图IDE
- ✅ PlatformHubPanel - 统一平台

#### Phase 2: 智能代理 (14个模块) ✅ 100%
- ✅ MultiAgentWorkflow - 多代理工作流
- ✅ DynamicTaskDecomposer - 任务分解
- ✅ AgentLifecycleManager - 生命周期
- ✅ AgentMemoryStore - 记忆存储
- ✅ SharedMemorySpace - 共享空间
- ✅ AgentMemoryBridge - 记忆桥接
- ✅ TaskScheduler - 任务调度
- ✅ ResultAggregator - 结果聚合
- ✅ ConflictResolver - 冲突解决
- ✅ AgentProtocol - 通信协议
- ✅ MetricsCollector - 指标收集
- ✅ PerformanceMonitor - 性能监控
- ✅ IntentCache - 意图缓存
- ✅ OrchestrationViewer - 编排可视化

#### Phase 3: 领域面板 🔄 80%
- ✅ FinanceHubPanel - 金融面板
- ✅ GameHubPanel - 游戏面板
- ✅ EnterpriseCockpitPanel - 企业驾驶舱面板
- ✅ DeCommercePanel - 去中心化电商面板
- 🔄 其他领域面板（待开发）

#### Phase 4: 自我进化 (13个模块) ✅ 100%
- ✅ SmartProxyGateway - 智能代理网关
- ✅ VisualEvolutionEngine - 可视化进化引擎
- ✅ **NSGA2Engine** - 多目标进化优化
- ✅ **AdaptiveEvolutionEngine** - 自适应进化策略
- ✅ **EpigeneticEngine** - 表观遗传引擎
- ✅ **LamarckianLearner** - 拉马克主义
- ✅ **BaldwinianLearner** - 鲍德温效应
- ✅ **CrossoverEngine** - 交叉遗传
- ✅ **SelfAwarenessSystem** - 自我意识系统
- ✅ EvolutionPanel - 进化引擎 UI 可视化面板
- ✅ ParameterTuner - 参数调优器
- ✅ ABTestFramework - A/B测试框架
- ✅ SelfDiagnosis - 系统自我诊断

#### Phase 5: 生态完善 🔄 60%
- ✅ PluginManager - 插件管理系统
- ✅ Marketplace - 生态市场
- 🔄 其他生态功能（待完善）

#### Phase 6: 云原生 🔄 20%
- 🔄 LanguageManager - 多语言引擎 (12种语言)
- 🔄 Benchmark - 性能基准测试
- 🔄 Dockerfile - Docker多阶段构建
- 🔄 docker-compose.yml - 容器编排
- 🔄 deploy.sh - 部署脚本

---

## 🛠️ 技术栈

### 后端技术

| 技术 | 版本 | 用途 |
|------|------|------|
| **Python** | 3.11+ | 主力开发语言 |
| **PyQt6** | 6.0+ | 桌面 GUI 框架 |
| **FastAPI** | 0.104+ | 服务器 API 框架 |
| **SQLite** | 3.35+ | 本地数据库 |
| **PostgreSQL** | 14+ | 服务器数据库（可选） |

### AI/ML 技术

| 技术 | 版本 | 用途 |
|------|------|------|
| **Ollama** | 0.1.0+ | 本地 LLM 运行框架 |
| **Qwen** | 3.5:4b | 默认推理模型 |
| **LangChain** | 0.0.340+ | Agent 开发框架 |
| **ChromaDB** | 0.4.0+ | 向量数据库 |

### 前端技术

| 技术 | 版本 | 用途 |
|------|------|------|
| **PyQt6** | 6.0+ | UI 组件库 |
| **QSS** | - | 样式表（类似 CSS） |
| **Matplotlib** | 3.8+ | 图表绘制 |

### 部署技术

| 技术 | 版本 | 用途 |
|------|------|------|
| **Docker** | 20.10+ | 容器化 |
| **Docker Compose** | 2.0+ | 容器编排 |
| **PWA** | - | 移动端支持 |

---

## ⚡ 快速开始

### 环境要求

- Python 3.11+
- PyQt6 6.0+
- Windows 10+ / macOS / Ubuntu

### 安装

```bash
git clone https://github.com/ookok/LivingTreeAlAgent.git
cd LivingTreeAlAgent

# 按顺序安装
pip install -e ./client
pip install -e ./server/relay_server
pip install -e ./app
```

### 启动

```bash
# 桌面客户端
python main.py client

# 中继服务器
python main.py relay

# P2P tracker
python main.py tracker

# 企业应用
python main.py app

# 全部服务
python main.py all
```

### CLI 使用

```bash
# 通过 CLI 入口点
python -m livingtree client

# 查看帮助
livingtree --help
```

---

## 📊 项目统计

| 指标 | 数值 |
|------|------|
| **总提交数** | 17+ 次 |
| **总文件数** | 3400+ 个 |
| **业务模块** | 340+ files |
| **UI 组件** | 200+ files |
| **核心模块** | 48 个 |
| **Phase** | 7 个 |
| **总代码行数** | 35,000+ 行 |
| **设计文档** | 15+ 份 |

---

## 🎯 设计原则

1. **意图驱动** - 用户只关心"做什么"，不关心"怎么做"
2. **自我进化** - 系统能够自我测试、诊断、修复
3. **模块化** - 高度解耦，易于扩展
4. **可视化** - 所有过程可视化追踪
5. **安全性** - 沙箱隔离、权限控制
6. **极简配置** - 学习 nanochat 设计哲学（配置即代码，dataclass 优先）

---

## 🆕 最新更新 (2026-04-26)

### 项目结构优化

- ✅ **`core/` 目录完全迁移** - 所有 28 个子目录和 44 个独立文件已迁移到 `client/src/business/`
- ✅ **`ui/` 目录完全迁移** - 所有 102 个文件和 39 个子目录已迁移到 `client/src/presentation/`
- ✅ **导入引用全部更新** - 项目中不再有 `from core.xxx` 或 `from ui.xxx` 的导入
- ✅ **临时文件清理** - 删除 30+ 个临时脚本和 15+ 个过时报告文档
- ✅ **AGENTS.md 更新** - 反映新的项目结构

### 配置系统重构

- ✅ **NanochatConfig 引入** - 极简 dataclass 风格配置
- ✅ **性能提升 10x** - 无 YAML 解析，无字典查找
- ✅ **类型安全** - IDE 自动补全
- ⚠️ **UnifiedConfig 弃用** - 仍工作但显示警告

### 新增功能模块

- ✅ **企业驾驶舱面板** - P2P CDN存储、虚拟云盘、节点管理、任务调度、权限管理、同步状态
- ✅ **去中心化电商面板** - 卖家中心、买家市场、会话管理、订单管理、AI能力、穿透网络、存证审计
- ✅ **统一平台模块** - 论坛、博客、邮箱、IM、AI协作
- ✅ **知识自动领航员** - 自动发现知识缺口、智能调度搜索、自动验证更新
- ✅ **环境感知模块** - 动态获取用户位置信息，动态本地化搜索
- ✅ **专家管理系统** - 专家命名规范化、专家详情管理、专家同步功能
- ✅ **智能搜索联想** - 所有输入框支持从知识库联想
- ✅ **登录登出功能** - 主窗口右上角显示用户状态，支持登录、登出、用户菜单
- ✅ **错误提示系统** - 将技术错误转换为用户友好消息，支持重试回调
- ✅ **模块联动服务** - 企业驾驶舱 ↔ 知识库/IM/写作/IDE 的联动功能
- ✅ **UI动画效果** - 渐入渐出、滑动、缩放、震动、脉冲等动画效果

### 架构升级

- ✅ **所有面板 Agent 化** - 每个面板都对应一个新的智能体（继承 HermesAgent）
- ✅ **UI 操作通过智能体调用** - 确保架构统一
- ✅ **不允许直接调用 LLM** - 所有调用都通过 GlobalModelRouter
- ✅ **Agent 注册管理** - 所有面板 Agent 已注册到 AgentFactory

---

## 🆕 最新更新 (2026-04-27)

### 统一架构层改造方案 ⭐ **核心设计**

- ✅ **统一架构层设计** - ToolRegistry/BaseTool/ToolDefinition/ToolResult 标准化工具框架
- ✅ **自我进化引擎设计** - 8 个核心组件（工具缺失检测、自主创建、主动学习、自我反思、用户澄清、代理源管理、CLI 工具发现、模型自动检测与升级）
- ✅ **环境感知与自适应能力** - 6 个维度全面感知（物理、用户、系统、业务、时间、社会），自动适应环境变化
- ✅ **系统设计理念与创新建议** - 活体智能体架构、集体智慧网络、极简 UI、绿色 AI、联邦学习、知识蒸馏、自愈系统、情感智能、多模态智能

### 设计文档

- 📄 [统一架构层改造方案（完整版 v4）](./docs/统一架构层改造方案_完整版_v3.md) - 14 章完整设计文档

---

## 📚 文档

### 设计文档（2026-04-27 新增）

- [统一架构层改造方案（完整版 v4）](./docs/统一架构层改造方案_完整版_v3.md) - ⭐ **核心设计文档**
  - 一、项目背景
  - 二、智能体体系架构
  - 三、系统已有工具模块全面梳理（18 个已实现 + 6 个需新建）
  - 四、统一架构层设计方案（ToolRegistry/BaseTool/ToolDefinition）
  - 五、自我进化引擎设计（8 个核心组件）
  - 六、环境感知与自适应能力（6 个维度全面感知）
  - 七、总结：系统设计理念与创新建议
  - 八～十四、实施计划、待办清单、开发规范、风险评估等

### 架构与指南

- [系统架构梳理](./docs/系统架构梳理_2026-04-26.md) - 详细架构文档
- [待办任务清单](./docs/待办任务清单_2026-04-26.md) - 按优先级分类的任务清单
- [AGENTS.md](./AGENTS.md) - AI 指引文档（含项目结构、运行命令、代码规范）
- [ARCHITECTURE.md](./ARCHITECTURE.md) - 详细架构文档
- [PROGRAMMING_OS_ROADMAP.md](./PROGRAMMING_OS_ROADMAP.md) - 编程操作系统路线图

---

## 🤝 贡献指南

我们欢迎任何形式的贡献！

### 开发流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 代码规范

- 遵循 PEP 8 代码风格
- 使用 `from client.src.business.xxx` 导入（而非 `from core.xxx`）
- 新功能先更新待办任务清单再开始开发
- 提交前确保测试通过
- 所有面板必须通过 Agent 调用功能（继承 HermesAgent）

---

## 📝 待办任务

详见 [待办任务清单](./docs/待办任务清单_2026-04-26.md) 查看完整的待办任务清单。

**任务统计**：

| 优先级 | 任务数 | 已完成 | 进行中 | 待处理 |
|--------|--------|--------|----------|----------|
| **P0** | 4 | 3 | 1 | 0 |
| **P1** | 4 | 1 | 0 | 3 |
| **P2** | 4 | 4 | 0 | 0 |
| **P3** | 3 | 0 | 0 | 3 |
| **总计** | **15** | **8** | **1** | **6** |

**高优先级任务**：
- [ ] 配置系统迁移（P0 - 进行中）
- [ ] 启动系统测试（P1 - 待处理）
- [ ] 完善认证系统后端（P1 - 待处理）
- [ ] 深度搜索集成（P1 - 待处理）

---

## ⚠️ 已知问题

### 高优先级问题

1. **链接管理器语法错误** ⚠️
   - 文件: `client/src/business/link_manager.py`
   - 问题: 存在无效字符
   - 状态: 待修复
   - 优先级: P1

2. **配置系统迁移未完成** ⚠️
   - 多个模块仍使用旧配置系统
   - 状态: 进行中
   - 优先级: P0

3. **测试覆盖率低** ⚠️
   - 目前只有1个真实测试文件
   - 状态: 待完善
   - 优先级: P3

---

## 🙏 致谢

- [PyQt6](https://pypi.org/project/PyQt6/) - 桌面应用框架
- [Ollama](https://ollama.ai/) - 本地 LLM 运行框架
- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) - Agent 架构参考
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Web 框架
- [LangChain](https://python.langchain.com/) - LLM 应用开发框架
- [ChromaDB](https://www.trychroma.com/) - 向量数据库

---

## 📄 License

本项目采用 MIT License - 查看 [LICENSE](LICENSE) 文件了解详情。

---

## 📧 联系方式

- GitHub Issues: [提交问题](https://github.com/ookok/LivingTreeAlAgent/issues)
- 讨论区: [参与讨论](https://github.com/ookok/LivingTreeAlAgent/discussions)

---

## 🔗 相关链接

- [在线演示](https://livingtree.ai/demo)（即将上线）
- [文档中心](https://docs.livingtree.ai)（即将上线）
- [社区论坛](https://community.livingtree.ai)（即将上线）

---

*LivingTree AI - 让智能体像生命一样进化* 🌱

---

*最后更新：2026-04-27*
