# -*- coding: utf-8 -*-
"""
全源情报中心 (Intelligence Center)
Intelligence Center for Hermes Desktop

从"搜索"到"决策"的闭环：
- Multi-Search: 多源搜索聚合
- Rumor Scanner: 谣言检测与舆情分析
- Competitor Monitor: 竞品监控流
- Alert System: 预警与分发
- Report Generator: 自动化报告

MVP: 竞品监控流
1. Multi-Search 抓取对手新品
2. Rumor Scan 分析口碑风险
3. Cloud-Writer 生成日报
4. 邮件推送给运营
"""

from .models import (
    IntelligenceType,
    AlertLevel,
    RumorVerdict,
    ReportStatus,
    DataSource,
    IntelligenceSource,
    RawIntelligence,
    RumorCheckResult,
    CompetitorProfile,
    AlertRecord,
    IntelligenceReport,
    IntelligenceStats,
    MonitoringTask,
    NotificationConfig,
    IntelligenceCenterConfig,
)

from .multi_search import (
    SearchIntent,
    SearchSource,
    SearchResult,
    SearchQuery,
    SearchResponse,
    MultiSourceSearcher,
    DeepSearchPipeline,
    QueryOptimizer,
)

from .rumor_scanner import (
    RumorClaim,
    RumorResult,
    SentimentResult,
    SentimentAnalyzer,
    RumorDetector,
    SentimentAggregator,
)

from .competitor_monitor import (
    HealthStatus,
    CompetitorProfile as CMPCompetitorProfile,
    CompetitorHealth,
    CompetitorIntel,
    CompetitorMonitor,
    HealthEvaluator,
    MonitoringScheduler,
)

from .alert_system import (
    AlertChannel,
    Alert,
    EmailConfig,
    WebhookConfig,
    NotificationRule,
    AlertManager,
)

from .report_generator import (
    ReportFormat,
    ReportType,
    ReportStatus as RGReportStatus,
    ReportSection,
    IntelligenceReport as IGIntelligenceReport,
    ReportGenerator,
    CompetitorDailyReportGenerator,
)

from .intelligence_hub import (
    IntelligenceHub,
    get_intelligence_hub,
)

__version__ = "1.0.0"

__all__ = [
    # Models
    "IntelligenceType",
    "AlertLevel",
    "RumorVerdict",
    "ReportStatus",
    "DataSource",
    "IntelligenceSource",
    "RawIntelligence",
    "RumorCheckResult",
    "CompetitorProfile",
    "AlertRecord",
    "IntelligenceReport",
    "IntelligenceStats",
    "MonitoringTask",
    "NotificationConfig",
    "IntelligenceCenterConfig",
    # Search
    "SearchIntent",
    "SearchSource",
    "SearchResult",
    "SearchQuery",
    "SearchResponse",
    "MultiSourceSearcher",
    "DeepSearchPipeline",
    "QueryOptimizer",
    # Rumor
    "RumorClaim",
    "RumorResult",
    "SentimentResult",
    "SentimentAnalyzer",
    "RumorDetector",
    "SentimentAggregator",
    # Competitor
    "HealthStatus",
    "CMPCompetitorProfile",
    "CompetitorHealth",
    "CompetitorIntel",
    "CompetitorMonitor",
    "HealthEvaluator",
    "MonitoringScheduler",
    # Alert
    "AlertChannel",
    "Alert",
    "EmailConfig",
    "WebhookConfig",
    "NotificationRule",
    "AlertManager",
    # Report
    "ReportFormat",
    "ReportType",
    "ReportSection",
    "ReportGenerator",
    "CompetitorDailyReportGenerator",
    # Hub
    "IntelligenceHub",
    "get_intelligence_hub",
]