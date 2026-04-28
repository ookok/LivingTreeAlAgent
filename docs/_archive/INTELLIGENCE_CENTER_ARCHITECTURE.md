# 全源情报中心 + 自动化运营引擎
## Intelligence Center Architecture

---

## 一、整体架构：从"搜索"到"决策"的闭环

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Intelligence Hub                                 │
│                     (情报中心核心调度器)                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐             │
│   │ Multi-Search │    │ Rumor-Scanner│    │Competitor    │             │
│   │ 多源搜索聚合  │───▶│ 谣言检测与   │───▶│ Monitor      │             │
│   │              │    │ 舆情分析      │    │ 竞品监控流   │             │
│   └──────────────┘    └──────────────┘    └──────────────┘             │
│         │                    │                    │                    │
│         │                    │                    │                    │
│         ▼                    ▼                    ▼                    │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐             │
│   │ Alert System │    │   Report     │    │    Skill     │             │
│   │ 预警与分发    │◀───│  Generator   │◀───│   Scanner    │             │
│   │              │    │  报告生成器   │    │  能力发现    │             │
│   └──────────────┘    └──────────────┘    └──────────────┘             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              UI Layer                                    │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐           │
│  │  搜索   │  │  竞品   │  │  谣言   │  │  预警   │  │  报告   │           │
│  │  Tab    │  │  Tab    │  │  Tab    │  │  Tab    │  │  Tab    │           │
│  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心模块详解

### 2.1 Multi-Search 多源搜索聚合引擎

**文件**: `core/intelligence_center/multi_search.py`

```
┌─────────────────────────────────────────┐
│         MultiSourceSearcher              │
├─────────────────────────────────────────┤
│ + search(query, sources) → SearchResponse│
│ + DeepSearchPipeline                    │
│   - search_competitor()                 │
│   - search_product_releases()           │
│   - search_sentiment()                  │
├─────────────────────────────────────────┤
│ + QueryOptimizer                        │
│   - detect_intent() → SearchIntent      │
│   - generate_variants()                 │
│   - is_ad_result()                      │
├─────────────────────────────────────────┤
│ + SearchCache (TTL 1小时)               │
└─────────────────────────────────────────┘
```

**支持引擎**:
- 百度 (web/news)
- Bing (web)
- 知乎 (social)

**搜索意图识别**:
- GENERAL - 通用搜索
- COMPETITOR - 竞品相关
- PRODUCT - 产品评测
- NEWS - 新闻动态
- RUMOR - 谣言核查
- REVIEW - 评价口碑

---

### 2.2 Rumor Scanner 谣言检测与舆情分析

**文件**: `core/intelligence_center/rumor_scanner.py`

```
┌─────────────────────────────────────────┐
│           RumorDetector                  │
├─────────────────────────────────────────┤
│ + check(claim) → RumorResult            │
│   - 高风险关键词检测                      │
│   - 谣言模式匹配                         │
│   - 情感分析                             │
│   - 风险等级评估                         │
├─────────────────────────────────────────┤
│ + SentimentAnalyzer                     │
│   - analyze(text) → SentimentResult     │
│   - POSITIVE/NEGATIVE/NEUTRAL           │
├─────────────────────────────────────────┤
│ + SentimentAggregator                   │
│   - get_trend() → 舆情趋势              │
└─────────────────────────────────────────┘
```

**谣言判定**:
- TRUE - 属实
- MOSTLY_TRUE - 大部分属实
- UNVERIFIED - 未证实
- PARTLY_FALSE - 部分失实
- FALSE - 谣言
- MISLEADING - 误导性

---

### 2.3 Competitor Monitor 竞品监控流

**文件**: `core/intelligence_center/competitor_monitor.py`

```
┌─────────────────────────────────────────┐
│         CompetitorMonitor               │
├─────────────────────────────────────────┤
│ + add_competitor(profile) → id          │
│ + remove_competitor(id)                 │
│ + collect_intel(id) → List[Intel]       │
│ + evaluate_health(id) → Health         │
│ + run_monitoring_cycle()                │
├─────────────────────────────────────────┤
│ + HealthEvaluator                       │
│   - 基础指标: 更新频率/社交互动/评分     │
│   - 风险指标: 负面占比/谣言/投诉         │
│   - 综合评分: 0-100                     │
├─────────────────────────────────────────┤
│ + MonitoringScheduler                   │
│   - 定时监控 (默认1小时)                │
└─────────────────────────────────────────┘
```

**健康度状态**:
- EXCELLENT (≥80分)
- GOOD (≥60分)
- WARNING (≥40分)
- DANGER (≥20分)
- UNKNOWN

---

### 2.4 Alert System 预警与分发系统

**文件**: `core/intelligence_center/alert_system.py`

```
┌─────────────────────────────────────────┐
│           AlertManager                   │
├─────────────────────────────────────────┤
│ + create_alert() → Alert                │
│ + add_rule(rule)                        │
│ + register_callback(fn)                  │
│ + get_recent_alerts()                   │
│ + get_alert_stats()                     │
├─────────────────────────────────────────┤
│ 支持渠道:                                │
│ - Email (SMTP)                         │
│ - Webhook (签名验证)                    │
│ - System (日志)                         │
├─────────────────────────────────────────┤
│ + NotificationRule                       │
│   - min_level: 最低预警级别              │
│   - keywords_filter: 关键词过滤          │
│   - exclude_keywords: 排除关键词        │
└─────────────────────────────────────────┘
```

---

### 2.5 Report Generator 报告生成器

**文件**: `core/intelligence_center/report_generator.py`

```
┌─────────────────────────────────────────┐
│          ReportGenerator                 │
├─────────────────────────────────────────┤
│ + generate() → IntelligenceReport        │
│ + render_markdown()                     │
│ + render_html()                          │
│ + save() → file_path                    │
├─────────────────────────────────────────┤
│ + CompetitorDailyReportGenerator        │
│   - 竞品概览                             │
│   - 最新动态                             │
│   - 健康度分析                           │
│   - 风险预警                             │
└─────────────────────────────────────────┘
```

**报告类型**:
- DAILY - 日报
- WEEKLY - 周报
- ALERT - 预警报告
- SPECIAL - 专题报告

**输出格式**:
- Markdown
- HTML

---

## 三、MVP竞品监控流

```
输入: 竞品名称
  │
  ▼
┌─────────────────────────────────────────────────────┐
│ Step 1: Multi-Search 抓取对手新品                    │
│   - 搜索竞品名称 + [新品/评测/价格]                   │
│   - 并行多源搜索                                     │
│   - 去重排序                                        │
└─────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────┐
│ Step 2: Rumor Scan 分析口碑风险                      │
│   - 检测 [品牌+假货/欺骗/投诉] 等关键词               │
│   - 谣言判定: false/partly_false/misleading         │
│   - 风险等级: CRITICAL/HIGH/MEDIUM/LOW/INFO        │
└─────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────┐
│ Step 3: Sentiment Analysis 舆情分析                  │
│   - 情感得分: -1 到 1                               │
│   - 情感标签: positive/negative/neutral             │
│   - 关键短语提取                                    │
└─────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────┐
│ Step 4: Report Generator 生成日报                    │
│   - 竞品动态                                        │
│   - 风险检测                                        │
│   - 舆情分析                                        │
│   - 输出 Markdown 报告                              │
└─────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────┐
│ Step 5: Email-Sender 邮件推送                        │
│   - 配置邮件发送                                    │
│   - 按规则触发预警                                  │
└─────────────────────────────────────────────────────┘
  │
  ▼
输出: 竞品监控报告 + 可选邮件通知
```

---

## 四、数据模型

### 4.1 核心枚举

```python
class IntelligenceType(Enum):
    COMPETITOR_PRODUCT = "competitor_product"
    MARKET_TREND = "market_trend"
    RUMOR_DETECTION = "rumor_detection"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    RISK_ALERT = "risk_alert"

class AlertLevel(Enum):
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class RumorVerdict(Enum):
    TRUE = "true"
    MOSTLY_TRUE = "mostly_true"
    UNVERIFIED = "unverified"
    PARTLY_FALSE = "partly_false"
    FALSE = "false"
    MISLEADING = "misleading"
```

### 4.2 核心数据类

```python
@dataclass
class CompetitorProfile:
    competitor_id: str
    name: str
    aliases: List[str]
    keywords: List[str]
    is_active: bool

@dataclass
class RumorResult:
    verdict: RumorVerdict
    confidence: float
    truth_score: float
    risk_level: AlertLevel

@dataclass
class CompetitorHealth:
    health_score: float  # 0-100
    status: HealthStatus
    trend: str  # improving/declining/stable
```

---

## 五、API接口

### 5.1 IntelligenceHub 主接口

```python
hub = get_intelligence_hub()

# 搜索
await hub.search(query, sources=["baidu"])
await hub.deep_search(query, search_type="competitor")

# 谣言检测
await hub.check_rumor(text)
await hub.analyze_sentiment(text)
hub.get_sentiment_trend()

# 竞品管理
hub.add_competitor(name, keywords, website)
hub.list_competitors()
await hub.collect_competitor_intel(competitor_id)
await hub.evaluate_competitor_health(competitor_id)

# 预警
await hub.send_alert(level, title, description, content)
hub.get_recent_alerts(limit=50)
hub.get_alert_stats()

# 报告
await hub.generate_daily_report()
hub.generate_report(title, report_type, sections)

# MVP竞品监控流
await hub.run_competitor_monitoring_flow(competitor_name)
```

---

## 六、UI面板

**文件**: `ui/intelligence/intelligence_panel.py`

**5个标签页**:

| 标签页 | 功能 |
|--------|------|
| 搜索 | 多源搜索 + 深度检索 |
| 竞品 | 竞品添加/监控/健康度 |
| 谣言 | 谣言检测 + 舆情趋势 |
| 预警 | 预警记录 + 统计 |
| 报告 | 报告生成 + 预览 |

---

## 七、文件结构

```
core/intelligence_center/
├── __init__.py              # 模块导出
├── models.py                # 数据模型
├── multi_search.py          # 多源搜索
├── rumor_scanner.py         # 谣言检测
├── competitor_monitor.py    # 竞品监控
├── alert_system.py          # 预警系统
├── report_generator.py      # 报告生成
└── intelligence_hub.py      # 核心调度器

ui/intelligence/
├── __init__.py
└── intelligence_panel.py    # PyQt6 UI面板

docs/
└── INTELLIGENCE_CENTER_ARCHITECTURE.md
```

---

## 八、快速开始

```python
from core.intelligence_center import get_intelligence_hub, AlertLevel

# 获取单例
hub = get_intelligence_hub()

# 添加竞品
hub.add_competitor(
    name="某竞品",
    keywords=["新品", "评测"]
)

# 运行竞品监控流
result = await hub.run_competitor_monitoring_flow("某竞品")
# result = {
#     "search_results": [...],
#     "rumor_results": [...],
#     "sentiment": {...},
#     "report_path": "..."
# }
```