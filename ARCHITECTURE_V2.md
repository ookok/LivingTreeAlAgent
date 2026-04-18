# Hermes Desktop V2.0 - 完整架构文档

> 🌳 *"生命之树苏醒，根系伸向远方，林间交易的风已经开始流动。"*

## 概述

**Hermes Desktop V2.0** 是一个基于 PyQt6 的桌面 AI 编程助手，集成 GPT4All 和 NousHermes，支持从魔搭社区（ModelScope）获取 Qwen、LLM-Research 等组织的 GGUF 模型。

**核心技术栈**：
- Python 3.11+ / PyQt6 (GUI)
- SQLite (WAL模式) / FastAPI / Uvicorn
- Ollama API / llama-cpp-python
- ModelScope SDK

**设计原则**：
- 身份即钥匙 — 基于加密身份的授权体系
- 本地即真理 — 核心功能不依赖服务器
- 网络是邮差 — P2P 网络负责数据传输

---

## 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Hermes Desktop V2.0                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         Presentation Layer (UI层)                           │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐             │   │
│  │  │ MainWindow │ │ Metaverse  │ │ ChatPanel  │ │TradeDeck   │  ...        │   │
│  │  │  主窗口    │ │   舰桥UI   │ │  聊天面板  │ │  贸易舱    │             │   │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘             │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                           │
│  ┌────────────────────────────────────┴────────────────────────────────────────┐ │
│  │                              Core Layer (业务逻辑层)                           │ │
│  │                                                                          │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │ │
│  │  │ FusionRAG       │  │ Intelligence    │  │ CreditEconomy   │            │ │
│  │  │ 多源融合检索     │  │ Center         │  │ 积分经济系统     │            │ │
│  │  │ (基础层)        │  │ 全源情报中心    │  │                 │            │ │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘            │ │
│  │           │                    │                    │                     │ │
│  │  ┌────────┴────────────────────┴────────────────────┴────────┐          │ │
│  │  │                   业务模块层 (Business Modules)              │          │ │
│  │  │  SkillMarket│PersonaSkill│IdleGrade│Achievement│BlockChain │          │ │
│  │  └──────────────────────────────────────────────────────────────┘          │ │
│  │                                                                          │ │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                           │
│  ┌────────────────────────────────────┴────────────────────────────────────────┐ │
│  │                          Infrastructure Layer (基础设施层)                      │ │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐                 │ │
│  │  │  Agent     │ │  Ollama    │ │  Session   │ │  Config    │                 │ │
│  │  │  代理核心   │ │  Client   │ │  DB       │ │  Manager   │                 │ │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘                 │ │
│  └──────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                          Server Layer (服务端层)                              │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │  │
│  │  │ Relay Server    │  │ Tracker Server  │  │ Admin License   │            │  │
│  │  │ 中继服务器       │  │ 追踪服务器      │  │ 管理员授权系统   │            │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘            │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 核心模块详解

### 1. FusionRAG - 多源融合检索层

**路径**: `core/fusion_rag/`

**定位**: 四层混合检索 + L4 异构执行层，支撑上层 AI 能力

**架构**:
```
┌────────────────────────────────────────────────────────────┐
│                   IntelligentRouter                        │
│                      (智能路由)                              │
├────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Exact   │  │ Session  │  │Knowledge │  │Database  │  │
│  │  Cache   │  │  Cache   │  │  Base    │  │  Layer   │  │
│  │ (毫秒级)  │  │(上下文)  │  │ (深度)   │  │(结构化)  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
├────────────────────────────────────────────────────────────┤
│                    L4 Relay Executor                      │
│                   (L4 异构执行层)                          │
└────────────────────────────────────────────────────────────┘
```

**核心导出**:
- `ExactCacheLayer` - 精确缓存层
- `SessionCacheLayer` - 会话缓存层
- `KnowledgeBaseLayer` - 知识库检索层
- `DatabaseLayer` - 数据库查询层
- `IntelligentRouter` - 意图分类 + 智能路由
- `FusionEngine` - 多源融合引擎
- `L4RelayExecutor` - L4 执行器

---

### 2. Intelligence Center - 全源情报中心

**路径**: `core/intelligence_center/`

**定位**: 从"搜索"到"决策"的闭环

**核心功能**:
- Multi-Search: 多源搜索聚合
- Rumor Scanner: 谣言检测与舆情分析
- Competitor Monitor: 竞品监控流
- Alert System: 预警与分发
- Report Generator: 自动化报告

---

### 3. Credit Economy - 积分经济系统

**路径**: `core/credit_economy/`

**核心理念**: 平衡积分发放与消耗，构建可持续的 P2P 经济体系

**核心组件**:
| 组件 | 功能 |
|------|------|
| DynamicCreditIssuance | 动态积分发放（基础1000+贡献奖励+活跃奖励+稀缺性调节） |
| SmartCreditConsumption | 智能积分消耗（任务成本预估+动态定价+智能议价） |
| LayeredConsensus | 分层共识（即时<100/日终批量<10000/全局结算>10000） |
| CreditStateChannel | 状态通道（高频交易链下处理+挑战期机制） |
| ProbabilisticFinality | 概率性最终性（渐进式确认） |
| DecentralizedSkillMarket | 去中心化技能市场 |
| IdeaNFTMarketplace | 创意NFT市场 |
| SkillRevenueTokens | 技能收益代币化 |
| CreditPredictionMarket | 积分预测市场 |

---

### 4. Idle Grade System - 挂机积分与等级粘性增强系统

**路径**: `core/idle_grade_system/`

**核心理念**: 让用户的每一秒在线时间都产生价值，构建可见的成长路径和社会地位体系

**核心组件**:
| 组件 | 功能 |
|------|------|
| IdleCreditSystem | 智能挂机积分（多维度收益算法） |
| IdleMiniGame | 挂机小游戏（数据挖矿/节点耕作/AI训练场/知识收割） |
| DynamicLevelSystem | 动态等级系统（10级体系：萌新→神话） |
| LevelPrivileges | 等级特权系统 |
| LevelAchievementSystem | 等级成就系统 |
| DailyLoginReward | 每日登录奖励 |
| LevelChallengeSystem | 等级挑战任务 |
| LevelLeaderboard | 等级排行榜 |
| LevelShowcaseSystem | 等级炫耀系统 |
| LevelCompanionPet | 等级养成宠物 |

---

### 5. Achievement System - 全链路成就系统

**路径**: `core/achievement_system/`

**核心理念**: 每个行为都有成就，每次成长都有记录，从萌新到传奇的全过程可追溯、可展示、可传承

**核心组件**:
| 组件 | 功能 |
|------|------|
| AchievementMetaverse | 成就元数据引擎（任务-成就映射+成就定义库） |
| AchievementDetector | 智能成就探测器（事件钩子+模式识别+组合检测） |
| AchievementTracker | 成就进度追踪器 |
| TimeCapsuleAchievement | 时间胶囊成就 |
| EvolvingAchievement | 成就进化系统 |
| AchievementComboSystem | 成就组合技 |
| AchievementMetaverseGallery | 成就元宇宙画廊 |
| AchievementTimeTravel | 成就时空穿越 |
| AchievementGeneInheritance | 成就基因传承 |
| AchievementNeuralNetwork | 成就神经网络（AI预测下一成就） |
| AchievementLiveCard | 成就动态卡片 |
| AchievementSocialNetwork | 成就社交网络 |

---

### 6. Universal Asset Ecosystem - 通用资产交易生态

**路径**: `core/universal_asset_ecosystem/`

**核心理念**: 从数字到物理的完整社会模式，打造微型社会生态系统

**核心组件**:
| 组件 | 功能 |
|------|------|
| AssetDeliveryRouter | 资产交付智能路由（5种交付方式自动匹配） |
| DigitalAssetIntegrator | 数字资产集成器 |
| UniversalAssetTemplate | 通用资产模板引擎 |
| LogisticsIntegration | 物流集成系统 |
| AddressBookManager | 地址管理系统 |
| AssetConversationSystem | 资产对话系统 |
| TrustNetwork | 信任网络系统 |
| CreditLendingSystem | 积分借贷系统 |
| CreditGiftSystem | 积分红包系统 |
| CommunityContributionProof | 社区贡献证明 |
| MicroSocietyDAO | 微型社会DAO |
| SocietyLifecycle | 社会生命周期 |
| InterSocietyBridge | 跨社会桥 |

---

### 7. Admin License System - 管理员授权系统

**路径**: `core/admin_license_system/`

**核心理念**: "三端发布时内置作者信息，作者登录自动获得管理员权限，最多100个管理员，只有管理员才能生成序列号"

**四级角色体系**:
| 角色 | 权限 |
|------|------|
| 作者 | 最高权限，内置发布时配置 |
| 超级管理员 | 完全控制 |
| 普通管理员 | 大部分管理权限 |
| 操作员 | 基础操作权限 |

**核心模块**:
| 模块 | 功能 |
|------|------|
| author_config.py | 三端发布时内置作者信息（Windows/macOS/Linux/Web） |
| admin_auth.py | 管理员注册/登录/作者免密登录/权限验证/会话管理 |
| admin_manager.py | 管理员CRUD操作/数量限制/审计日志 |
| license_auth.py | 验证用户是否有权限生成序列号/记录生成操作 |

---

### 8. User Auth Service - 用户认证系统

**路径**: `server/relay_server/services/user_auth_service.py`

**核心理念**: "用户的注册和认证由中继服务器响应，同时自动注册节点信息"

**核心服务**:
| 服务 | 功能 |
|------|------|
| UserAuthService | 用户注册/JWT Token/第三方OAuth (GitHub/Google/微信) |
| NodeService | 节点注册/激活/心跳/多节点支持 |
| PaymentGateway | 统一支付网关（微信/支付宝回调转发） |

---

### 9. Credit Recharge Service - 积分充值与VIP系统

**路径**: `server/relay_server/services/credit_recharge_service.py`

**核心理念**: "用户充值获得积分，首次充值有奖励，VIP用户每日可领取赠送积分"

**VIP等级体系**:
| 等级 | 最低充值 | 每日赠送 | 升级奖励 |
|------|---------|---------|---------|
| VIP1 | 100元 | 10积分 | 100积分 |
| VIP2 | 500元 | 30积分 | 300积分 |
| VIP3 | 1000元 | 80积分 | 800积分 |
| VIP4 | 5000元 | 200积分 | 2000积分 |
| VIP5 | 10000元 | 500积分 | 5000积分 |

**充值规则**:
- 充值比例: 1元 = 10积分
- 首充额外+50%积分

---

### 10. Event-Driven Ledger - 事件驱动账本扩展

**路径**: `relay_chain/event_ext/`

**核心理念**: 将"积分记账"泛化为"事件日志"

**扩展事件类型**:
| 类型 | 事件 |
|------|------|
| 积分类 | IN, OUT, RECHARGE, TRANSFER_IN, TRANSFER_OUT, GRANT, CONSUME |
| 任务类 | TASK_DISPATCH, TASK_EXECUTE, TASK_COMPLETE, TASK_CANCEL, TASK_RETRY |
| 租户类 | CROSS_TENANT_MSG, TENANT_NOTIFY, TENANT_RECEIPT |
| 资产类 | ASSET_GRANT, ASSET_TRANSFER, ASSET_CONSUME, ASSET_FREEZE, ASSET_UNFREEZE |
| 政务类 | GOV_CHECKIN, GOV_CHECKOUT, GOV_VERIFY, GOV_REVOKE, GOV_TRANSFER |
| 隐私类 | ZK_PROOF_SUBMIT, ZK_PROOF_VERIFY, ZK_RANGE_PROOF |

**核心模块**:
| 模块 | 功能 |
|------|------|
| event_transaction.py | 扩展 OpType 枚举 |
| event_ledger.py | 泛化事件账本 |
| task_scheduler.py | 任务调度防重放 |
| cross_tenant.py | 跨租户消息通道 |
| game_asset.py | 游戏资产管理 |

---

## 模块依赖关系

```
                    ┌─────────────────────────────────────────┐
                    │              FusionRAG                  │
                    │          (多源融合检索基础层)              │
                    └───────────────────┬─────────────────────┘
                                        │ 被依赖
                    ┌───────────────────┴─────────────────────┐
                    │         Intelligence Center              │
                    │             (全源情报中心)                │
                    └───────────────────┬─────────────────────┘
                                        │ 提供AI能力
          ┌─────────────────────────────┼─────────────────────────────┐
          ▼                             ▼                             ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  Credit Economy     │    │    Idle Grade       │    │  Achievement System │
│     (积分经济)       │    │   (挂机等级)        │    │    (全链路成就)      │
│                      │    │                     │    │                     │
│  DynamicIssuance    │    │  IdleCreditSystem  │    │  AchievementDetector │
│  SmartConsumption   │    │  DynamicLevel      │    │  AchievementTracker  │
│  LayeredConsensus   │    │  LevelPrivileges   │    │  EvolvingAchievement │
└──────────┬──────────┘    └──────────┬──────────┘    └─────────────────────┘
           │                          │
           │ 依赖去中心化技能市场        │ 依赖等级挑战
           ▼                          ▼
┌─────────────────────┐    ┌─────────────────────┐
│Universal Asset      │    │  Level Challenge    │
│Ecosystem            │    │     System          │
│(通用资产交易生态)     │    │  (等级挑战任务)      │
│                     │    │                     │
│ AssetDeliveryRouter │    │  WeeklyChallenge   │
│ DigitalIntegrator   │    │  UpgradeChallenge  │
│ TrustNetwork        │    │  SocialChallenge   │
└─────────────────────┘    └─────────────────────┘
           │
           │ 被UI调用
           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Metaverse UI                                      │
│                        (舰桥操作系统 - 元宇宙界面)                            │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐                 │
│  │  Bridge    │ │Holographic│ │  Trade     │ │   Oracle   │                 │
│  │  Console   │ │  StarMap   │ │   Deck     │ │   Core     │                 │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 数据库

**主数据库**: `database/migrations.py`

**表结构** (v1-v14):
- v1-v6: 基础表 (sessions, messages, files, tasks, skills, agents)
- v7: MCP Servers 表
- v8: Skills 表
- v9: LAN Chat 表
- v10: Digital Avatar 表
- v11: Learning World 表
- v12: 智能记忆与决策支持表
- v13: 文档审核与生命周期管理表
- v14: 强容错分布式任务表

---

## UI 面板

**路径**: `ui/` / `client/src/presentation/`

| 面板 | 文件 | 说明 |
|------|------|------|
| 主窗口 | `main_window.py` | 三栏布局 + Tab切换 |
| 舰桥 | `metaverse_ui_panel.py` | 元宇宙UI集成面板 |
| 积分经济 | `credit_economy_panel.py` | 积分经济系统UI |
| 挂机等级 | `idle_grade_panel.py` | 8标签页等级系统 |
| 成就中心 | `achievement_panel.py` | 全链路成就UI |
| 资产交易 | `universal_asset_panel.py` | 8标签页资产生态 |
| 管理授权 | `admin_license_panel.py` | 4标签页管理员系统 |

---

## 中继服务器

**路径**: `server/relay_server/`

**核心功能**:
- 配置同步 API (`/api/config/sync`)
- 用户认证 (`/api/auth/*`)
- 积分充值 (`/api/credit/*`)
- 支付网关 (`/api/payment/*`)
- 节点管理 (`/api/nodes/*`)
- Web 管理界面 (`/`, `/web`, `/admin`)

**API 端点**:
| 端点 | 方法 | 功能 |
|------|------|------|
| `/` | GET | 首页或JSON API信息 |
| `/api/health` | GET | 健康检查 |
| `/api/config/sync` | GET/POST | 配置同步 |
| `/api/collect` | POST | 收集客户端数据 |
| `/api/heartbeat` | POST | 心跳 |
| `/api/relay/params` | GET/POST | 中继参数 |
| `/api/stats/overview` | GET | 统计概览 |
| `/api/stats/trends` | GET | 进化趋势 |
| `/api/weekly/{week_id}` | GET | 周数据 |
| `/api/admin/stats` | GET | 管理统计 |
| `/api/admin/config` | POST | 更新配置 |

---

## 生命之树命名法典 (Living Tree Naming Codex)

核心理念：拒绝冰冷术语，用生长语言重塑技术模块。

### 顶层架构

| 技术概念 | 生命之树命名 | 隐喻 |
|---------|-------------|------|
| 客户端本体 | 生命主干 (The Trunk) | 一切功能的承载主体 |
| P2P网络 | 根系网络 (The Root Network) | 连接万物，输送养分与信号 |
| AI核心 | 智慧树芯 (The Heartwood) | 决策与思考的中心年轮 |
| 数据底座 | 沃土库 (The Soil Bank) | 记忆与知识的基底 |

### 智能与进化

| 技术概念 | 生命之树命名 | 隐喻 |
|---------|-------------|------|
| Hermes Agent | 信使叶灵 (Leaf Messenger) | 穿梭于枝叶间的信息传递者 |
| 自我修补 | 愈伤机制 (Cambium Repair) | 树皮受伤后的自愈层 |
| 补丁分发 | 花粉传播 (Pollen Drift) | 优秀改良随风扩散 |
| 知识蒸馏 | 蜜露酿制 (Nectar Refining) | 从百花中提炼精华 |

### 网络与通信

| 技术概念 | 生命之树命名 | 隐喻 |
|---------|-------------|------|
| 节点发现 | 根须触碰 (Root Contact) | 根系在地下相互探寻 |
| 伪域名 | 林间记号 (Forest Sigil) | 刻在树皮上的指引符号 |
| 广播机制 | 季风广播 (Monsoon Cast) | 消息随风远扬 |
| 中继服务 | 水源泉眼 (The Springhead) | 汇聚信息的活水源头 |

### 经济与成就

| 技术概念 | 生命之树命名 | 隐喻 |
|---------|-------------|------|
| 积分系统 | 智慧蜜 (Wisdom Honey) | 知识活动的甜美报酬 |
| 等级系统 | 年轮成长 (Ring Growth) | 每一次参与都是一圈年轮 |
| 成就系统 | 荣誉勋章 (Achievement Medals) | 成长路上的里程碑 |
| 资产交易 | 林间集市 (Forest Market) | 万物交换的热闹场所 |

---

## 版本信息

| 模块 | 版本 | 状态 |
|------|------|------|
| fusion_rag | v2.0.0 | 最新 |
| intelligence_center | v1.0.0 | 稳定 |
| credit_economy | v1.0.0 | 稳定 |
| idle_grade_system | v1.0.0 | 稳定 |
| achievement_system | v1.0.0 | 稳定 |
| universal_asset_ecosystem | v1.0.0 | 稳定 |
| admin_license_system | v1.0.0 | 稳定 |
| relay_server | v2.0.0 | 最新 |
| metaverse_ui | v1.0.0 | 稳定 |

---

## 文件索引

### 核心模块
- `core/fusion_rag/` - 多源融合检索 (11个子模块)
- `core/intelligence_center/` - 全源情报中心 (10个子模块)
- `core/credit_economy/` - 积分经济系统 (10个子模块)
- `core/idle_grade_system/` - 挂机等级系统 (12个子模块)
- `core/achievement_system/` - 全链路成就系统 (14个子模块)
- `core/universal_asset_ecosystem/` - 通用资产生态 (14个子模块)
- `core/admin_license_system/` - 管理员授权系统 (5个子模块)
- `core/metaverse_ui/` - 舰桥UI (9个子模块)

### 服务端
- `server/relay_server/main.py` - 中继服务器入口
- `server/relay_server/services/user_auth_service.py` - 用户认证
- `server/relay_server/services/credit_recharge_service.py` - 积分充值
- `server/relay_server/services/payment_gateway.py` - 支付网关

### UI 面板
- `ui/main_window.py` - 主窗口
- `ui/metaverse_ui_panel.py` - 舰桥面板
- `ui/credit_economy_panel.py` - 积分经济面板
- `ui/idle_grade_panel.py` - 挂机等级面板
- `ui/achievement_panel.py` - 成就面板
- `ui/admin_license_panel.py` - 管理授权面板

### 数据库
- `database/migrations.py` - 数据库迁移 (v1-v14)

---

*本文档由 AI 自动维护*
*最后更新: 2026-04-19*