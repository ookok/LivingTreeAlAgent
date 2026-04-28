# 统一电商面板设计方案

> 版本: 1.0.0  
> 日期: 2026-04-25  
> 状态: 设计中  

## 一、现有电商模块分析

### 1.1 模块概览

LivingTreeAI 系统已实现 5 个电商相关模块，散布在 `core/` 和 `ui/` 目录中：

| 模块 | 路径 | 功能 | UI面板 | 状态 |
|------|------|------|--------|------|
| **DeCommerce** | `core/decommerce/` | P2P去中心化电商 | `ui/decommerce_panel.py` | 较完整 |
| **LocalMarket** | `core/local_market/` | 本地市场/GeoHash发现 | `ui/local_market/main_panel.py` | 较完整 |
| **SocialCommerce** | `core/social_commerce/` | 社交电商/智能匹配 | `ui/social_commerce_panel.py` | 简化版 |
| **FlashListing** | `core/flash_listing/` | 闪电上架/图片转商品 | 无独立UI | 缺失 |
| **Commission** | `core/commission/` | 统一佣金系统 | `ui/commission_panel.py` | 较完整 |

### 1.2 现有UI面板分析

**问题**：
- 4个独立面板，功能重叠（订单管理在多处出现）
- 缺乏统一入口，用户体验割裂
- 缺少数据可视化（仪表盘）
- FlashListing 模块完全无UI

**DeCommerce面板** (1167行)：
- 7个标签页：卖家中心、买家市场、会话管理、订单管理、AI能力、穿透网络、存证审计
- 基于QTabWidget的传统布局

**LocalMarket面板** (894行)：
- 7个标签页：发现、我的商品、交易、交付、信誉、纠纷、设置
- 包含ProductCard组件和样式

**Commission面板** (706行)：
- 5个标签页：模块配置、打赏下单、订单管理、统计分析、系统设置
- 统计卡片组件

**SocialCommerce面板** (255行)：
- 3个标签页：匹配广场、会话、信用
- 大部分功能为占位符

---

## 二、统一电商面板架构

### 2.1 设计理念

```
┌─────────────────────────────────────────────────────────────────┐
│                     统一电商面板 (ECommercePanel)                │
├──────────┬──────────────────────────────────────────────────────┤
│          │                                                      │
│ 侧边栏   │              内容区域 (QStackedWidget)               │
│ 导航     │                                                      │
│          │  ┌────────────────────────────────────────────────┐  │
│ 💰 仪表盘│  │ DashboardWidget / ProductManagementWidget /  │  │
│ 📦 商品   │  │ FlashListingWidget / OrderCenterWidget /    │  │
│ ⚡ 闪电上架│  │ MatchMakingWidget / DataAnalysisWidget /    │  │
│ 📋 订单   │  │ ECommerceSettingsWidget                     │  │
│ 🤝 匹配   │  │                                              │  │
│ 📊 数据   │  │                                              │  │
│ ⚙️ 设置   │  └────────────────────────────────────────────────┘  │
│          │                                                      │
└──────────┴──────────────────────────────────────────────────────┘
```

### 2.2 模块结构

| 组件 | 类名 | 功能 | 优先级 |
|------|------|------|--------|
| 主面板 | `ECommercePanel` | 侧边栏 + QStackedWidget | P0 |
| 仪表盘 | `DashboardWidget` | 数据概览、统计卡片、热销商品 | P0 |
| 商品管理 | `ProductManagementWidget` | 商品CRUD、分类筛选、批量操作 | P0 |
| 闪电上架 | `FlashListingWidget` | 图片→AI识别→编辑→发布 | P1 |
| 订单中心 | `OrderCenterWidget` | 订单列表、状态管理、批量操作 | P0 |
| 智能匹配 | `MatchMakingWidget` | 意图雷达、信用链、AI破冰 | P2 |
| 数据分析 | `DataAnalysisWidget` | 营收图表、趋势分析、排行榜 | P2 |
| 系统设置 | `ECommerceSettingsWidget` | 支付、物流、信誉设置 | P1 |

---

## 三、功能详细设计

### 3.1 仪表盘 (DashboardWidget)

**统计卡片（4个）**：
- 💰 今日收入 - 金额 + 趋势箭头
- 📋 待处理订单 - 数量 + 颜色提示
- 🔗 活跃会话 - 实时P2P连接数
- ⭐ 信誉评分 - 1-5星可视化

**数据区域**：
- 热销商品 TOP 5（表格：商品、销量、收入、趋势）
- 近期订单列表（表格：订单号、商品、金额、状态、时间）

### 3.2 商品管理 (ProductManagementWidget)

**功能列表**：
- 商品搜索（标题、分类、状态）
- 商品列表（表格：ID、标题、分类、价格、库存、销量、状态、操作）
- 添加/编辑商品（表单弹窗）
- 批量上下架
- 分类管理
- 分页导航

**商品分类**：
- 实物商品（DeCommerce PHYSICAL_PRODUCT）
- AI计算服务（DeCommerce AI_COMPUTING）
- 知识咨询（DeCommerce KNOWLEDGE_CONSULT）
- 数字商品（DeCommerce DIGITAL_PRODUCT）
- 远程服务（DeCommerce REMOTE_ASSIST/REMOTE_LIVE_VIEW）

### 3.3 闪电上架 (FlashListingWidget) ⭐ 亮点功能

**5步流程**：

```
📸 上传图片 → 🤖 AI特征识别 → 📝 确认/编辑 → 🏷️ 一键发布 → 🤝 智能匹配
```

**UI布局**：
```
┌─────────────────────────────┬────────────────────────────────┐
│                             │                                │
│  📸 上传区域                 │  📝 商品信息编辑               │
│  (拖拽/点击选择)             │  - 标题                        │
│                             │  - 描述                        │
│  🤖 AI 特征识别结果          │  - 价格                        │
│  - 品类识别                 │  - 数量                        │
│  - 关键属性                 │  - 成色                        │
│  - 建议价格                 │  - 分类                        │
│                             │                                │
│  📊 上架进度                 │  🚚 交付方式                   │
│  [████████░░] 80%          │  □ 面交 □ 快递 □ 下载          │
│                             │                                │
│                             │  [🚀 一键发布]                 │
│                             │                                │
└─────────────────────────────┴────────────────────────────────┘
```

**AI特征识别**（集成 `core/flash_listing/models.py`）：
- 品类识别（置信度）
- 材质/尺寸/接口提取
- OCR铭牌识别
- 建议标题/价格生成

### 3.4 订单中心 (OrderCenterWidget)

**筛选功能**：
- 状态筛选：全部/待付款/待发货/待收货/已完成/已取消/退款中
- 时间筛选：全部/今天/本周/本月/自定义
- 关键词搜索

**订单表格列**：
- ☑️ 选择框
- 订单号
- 商品信息
- 买家/卖家
- 金额（含佣金）
- 订单状态
- 创建时间
- 操作（查看/发货/退款等）

**批量操作**：
- 批量导出（Excel/CSV）
- 批量发货
- 批量备注

### 3.5 智能匹配 (MatchMakingWidget)

**功能模块**（基于 `core/social_commerce/models.py`）：

1. **意图雷达**
   - 买家需求 vs 卖家供应自动匹配
   - 匹配度评分（0-100%）
   - B2B/跨境检测

2. **AI破冰消息**
   - 自动生成开场白
   - 基于交易历史和信用记录

3. **信用凭证链**
   - 哈希链追溯
   - 交易记录可视化
   - 信誉评分详情

4. **时空引力推荐**
   - GeoHash距离计算
   - 时段偏好分析

### 3.6 数据分析 (DataAnalysisWidget)

**概览卡片**：
- 总收入（本月/累计）
- 订单总数
- 转化率
- 活跃买家数

**图表区域**（占位符，待集成图表库）：
- 收入趋势折线图
- 订单来源饼图
- 分类销售排行柱状图

**排行榜**：
- 热销商品 TOP 10
- 高价值买家 TOP 10
- 优质卖家 TOP 10

### 3.7 系统设置 (ECommerceSettingsWidget)

**配置分组**：

1. **支付设置**
   - 微信支付配置
   - 支付宝配置
   - 加密货币地址
   - 佣金率设置

2. **物流设置**
   - 默认交付方式
   - 快递公司配置
   - 发货提醒

3. **信誉设置**
   - 自动好评规则
   - 差评处理流程
   - 仲裁机制

4. **AI自动回复**
   - 智能客服开关
   - 回复模板配置
   - 意图识别阈值

---

## 四、潜在功能挖掘

### 4.1 功能矩阵

| 功能 | 说明 | 技术依赖 | 优先级 | 难度 |
|------|------|----------|--------|------|
| **智能定价** | 根据竞品/成本自动建议价格 | 数据分析 | P2 | 高 |
| **交易预测** | 预测订单完成概率/流失风险 | ML模型 | P3 | 高 |
| **地理推荐** | 基于位置的商品/服务推荐 | GeoHash | P2 | 中 |
| **AI客服** | 7x24自动回复咨询 | LLM | P2 | 高 |
| **拼团功能** | 社交裂变团购 | 订单聚合 | P3 | 中 |
| **社交分销** | 分享得佣金 | 佣金系统 | P3 | 中 |
| **信誉徽章** | 交易完成自动获徽章 | 信用系统 | P2 | 低 |
| **物流追踪** | 快递状态实时同步 | 物流API | P2 | 中 |
| **快速仲裁** | 纠纷AI辅助裁决 | 规则引擎 | P3 | 高 |
| **电子合同** | 交易确认自动生成 | 签名API | P3 | 高 |

### 4.2 优先级建议

**P0 - MVP核心**（1-2周）：
- 统一面板框架
- 商品管理（CRUD）
- 订单中心
- 基础仪表盘

**P1 - 增强功能**（2-3周）：
- 闪电上架
- 智能匹配基础版
- 系统设置完善

**P2 - 增值功能**（1个月+）：
- 数据分析图表
- AI客服
- 地理推荐
- 信誉徽章

**P3 - 探索功能**（长期）：
- 智能定价
- 交易预测
- 拼团/分销
- 电子合同

---

## 五、集成方案

### 5.1 复用现有模块

| 新面板组件 | 复用现有模块 | 集成点 |
|------------|--------------|--------|
| 商品管理 | `core/decommerce/models.py` | ServiceListing, ServiceType |
| 商品管理 | `core/local_market/models.py` | Product, ProductCategory |
| 闪电上架 | `core/flash_listing/models.py` | ImageFeature, GeneratedListing |
| 闪电上架 | `core/flash_listing/flash_listing_engine.py` | AI特征提取 |
| 订单中心 | `core/decommerce/payment_guard.py` | 支付守卫 |
| 订单中心 | `core/local_market/trade.py` | TradeManager |
| 智能匹配 | `core/social_commerce/models.py` | MatchCandidate, CreditCredential |
| 佣金系统 | `core/commission/` | 佣金计算和结算 |

### 5.2 文件结构

```
client/src/presentation/panels/
├── ecommerce_panel.py          # 统一电商面板主文件
│   ├── ECommercePanel          # 主面板（侧边栏+内容）
│   ├── DashboardWidget         # 仪表盘
│   ├── ProductManagementWidget # 商品管理
│   ├── FlashListingWidget      # 闪电上架 ⭐
│   ├── OrderCenterWidget       # 订单中心
│   ├── MatchMakingWidget       # 智能匹配
│   ├── DataAnalysisWidget      # 数据分析
│   └── ECommerceSettingsWidget # 系统设置
│
└── components/
    ├── ecommerce/
    │   ├── stat_card.py        # 统计卡片组件
    │   ├── product_card.py     # 商品卡片组件
    │   ├── order_row.py        # 订单行组件
    │   └── credit_badge.py     # 信誉徽章组件
    └── ...
```

---

## 六、UI设计规范

### 6.1 配色方案

| 用途 | 颜色 | 十六进制 |
|------|------|----------|
| 主色 | 绿色 | #10B981 |
| 主色深 | 深绿 | #059669 |
| 警告 | 橙色 | #F59E0B |
| 信息 | 蓝色 | #3B82F6 |
| 成功 | 绿色 | #10B981 |
| 错误 | 红色 | #EF4444 |
| 强调 | 紫色 | #8B5CF6 |
| 背景 | 浅灰 | #F9FAFB |
| 文字 | 深灰 | #1F2937 |

### 6.2 字体规范

- 主字体：Microsoft YaHei / PingFang SC
- 标题：12px Bold
- 正文：12px Regular
- 辅助：10px Regular
- 数字：SF Pro Display / Roboto

### 6.3 间距规范

- 内边距：16px
- 卡片间距：12px
- 按钮间距：8px
- 圆角：8px（卡片）、4px（按钮）

---

## 七、实施计划

### 7.1 开发周期（建议）

```
Week 1: 基础框架 + 仪表盘 + 商品管理
Week 2: 订单中心 + 系统设置
Week 3: 闪电上架 + AI集成
Week 4: 智能匹配基础版
Week 5: 数据分析 + 优化
```

### 7.2 里程碑

| 里程碑 | 内容 | 交付物 |
|--------|------|--------|
| M1 | MVP | 可运行的统一面板，商品+订单基础功能 |
| M2 | 完整版 | 所有P0/P1功能完成 |
| M3 | 增强版 | P2功能集成，UI优化 |
| M4 | 智能化 | AI能力集成，智能推荐 |

---

## 八、风险与挑战

1. **模块耦合**：5个独立模块需要统一数据模型
2. **AI集成**：闪电上架依赖AI视觉能力
3. **实时性**：P2P会话状态需要实时更新
4. **数据一致性**：多模块订单数据同步

---

*文档版本：1.0.0*
*最后更新：2026-04-25*
