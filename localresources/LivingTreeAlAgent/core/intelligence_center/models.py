# -*- coding: utf-8 -*-
"""
全源情报中心 - 数据模型
Intelligence Center - Data Models

定义情报收集、分析、预警相关的核心数据结构
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import json


class IntelligenceType(Enum):
    """情报类型"""
    COMPETITOR_PRODUCT = "competitor_product"      # 竞品动态
    MARKET_TREND = "market_trend"                  # 市场趋势
    RUMOR_DETECTION = "rumor_detection"            # 谣言检测
    SENTIMENT_ANALYSIS = "sentiment_analysis"     # 舆情分析
    RISK_ALERT = "risk_alert"                     # 风险预警
    INDUSTRY_NEWS = "industry_news"                # 行业新闻
    REGULATORY_POLICY = "regulatory_policy"       # 政策法规
    CUSTOMER_FEEDBACK = "customer_feedback"       # 客户反馈


class AlertLevel(Enum):
    """预警级别"""
    INFO = 0          # 信息
    LOW = 1           # 低风险
    MEDIUM = 2        # 中风险
    HIGH = 3          # 高风险
    CRITICAL = 4      # 紧急


class RumorVerdict(Enum):
    """谣言判定"""
    TRUE = "true"                 # 属实
    MOSTLY_TRUE = "mostly_true"   # 大部分属实
    UNVERIFIED = "unverified"     # 未证实
    PARTLY_FALSE = "partly_false" # 部分失实
    FALSE = "false"               # 谣言
    MISLEADING = "misleading"      # 误导性


class ReportStatus(Enum):
    """报告状态"""
    DRAFT = "draft"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class DataSource(Enum):
    """数据来源"""
    SEARCH_WEB = "search_web"
    SEARCH_NEWS = "search_news"
    SEARCH_SOCIAL = "search_social"
    SEARCH_ACADEMIC = "search_academic"
    RUMOR_DATABASE = "rumor_database"
    SOCIAL_MEDIA = "social_media"
    OFFICIAL_WEBSITE = "official_website"
    INDUSTRY_REPORT = "industry_report"


@dataclass
class IntelligenceSource:
    """情报来源"""
    source_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""                      # 来源名称
    source_type: DataSource = DataSource.SEARCH_WEB
    url: str = ""
    credibility: float = 1.0           # 可信度 0-1
    last_accessed: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RawIntelligence:
    """原始情报条目"""
    intel_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    intel_type: IntelligenceType = IntelligenceType.COMPETITOR_PRODUCT

    # 内容
    title: str = ""
    content: str = ""
    url: str = ""
    source: str = ""

    # 元数据
    author: str = ""
    published_at: Optional[datetime] = None
    collected_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)

    # 关联实体
    related_entities: List[str] = field(default_factory=list)  # 公司/品牌/产品
    sentiment_score: float = 0.0        # 情感得分 -1到1
    importance: float = 0.0             # 重要性 0到1

    # 处理状态
    processed: bool = False
    enrichment_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RumorCheckResult:
    """谣言检测结果"""
    rumor_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # 原始信息
    claim: str = ""
    source_url: str = ""
    source_name: str = ""
    published_date: Optional[datetime] = None

    # 检测结果
    verdict: RumorVerdict = RumorVerdict.UNVERIFIED
    confidence: float = 0.0             # 置信度 0-1
    truth_score: float = 0.5            # 真实性评分 0-1

    # 分析详情
    evidence_for: List[str] = field(default_factory=list)   # 支持证据
    evidence_against: List[str] = field(default_factory=list)  # 反驳证据
    analysis_summary: str = ""

    # 风险评估
    risk_level: AlertLevel = AlertLevel.INFO
    potential_impact: str = ""

    checked_at: datetime = field(default_factory=datetime.now)


@dataclass
class CompetitorProfile:
    """竞品档案"""
    competitor_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    brand_aliases: List[str] = field(default_factory=list)  # 别名/曾用名

    # 监控配置
    website: str = ""
    social_media: Dict[str, str] = field(default_factory=dict)  # 平台:账号
    keywords: List[str] = field(default_factory=list)  # 监控关键词

    # 产品信息
    product_categories: List[str] = field(default_factory=list)
    price_range: str = ""

    # 健康度指标
    health_metrics: Dict[str, Any] = field(default_factory=dict)

    # 监控状态
    is_active: bool = True
    last_updated: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class AlertRecord:
    """预警记录"""
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    alert_level: AlertLevel = AlertLevel.INFO

    # 预警内容
    title: str = ""
    description: str = ""
    intel_ids: List[str] = field(default_factory=list)  # 关联情报ID

    # 来源
    source_type: str = ""              # rumor/competitor/sentiment
    source_id: str = ""

    # 状态
    status: str = "pending"            # pending/sent/failed/acknowledged
    sent_via: List[str] = field(default_factory=list)  # 发送渠道

    # 时间
    created_at: datetime = field(default_factory=datetime.now)
    sent_at: Optional[datetime] = None


@dataclass
class IntelligenceReport:
    """情报报告"""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # 报告基本信息
    title: str = ""
    report_type: str = ""              # daily/weekly/alert/special
    status: ReportStatus = ReportStatus.DRAFT

    # 时间范围
    start_date: datetime = field(default_factory=datetime.now)
    end_date: datetime = field(default_factory=datetime.now)
    generated_at: Optional[datetime] = None

    # 内容
    summary: str = ""
    key_findings: List[str] = field(default_factory=list)
    sections: Dict[str, str] = field(default_factory=dict)  # 分节内容

    # 统计数据
    stats: Dict[str, Any] = field(default_factory=dict)
    attachments: List[str] = field(default_factory=list)  # 附件路径

    # 格式
    format: str = "markdown"           # markdown/html/word/pdf
    file_path: str = ""


@dataclass
class MonitoringTask:
    """监控任务"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    task_type: str = ""                 # competitor/rumor/sentiment/industry

    # 配置
    config: Dict[str, Any] = field(default_factory=dict)
    schedule: str = ""                  # cron表达式或daily/weekly
    is_enabled: bool = True

    # 目标
    targets: List[str] = field(default_factory=list)  # 竞品ID列表等

    # 状态
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    success_count: int = 0

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class NotificationConfig:
    """通知配置"""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # 渠道配置
    email_enabled: bool = False
    email_recipients: List[str] = field(default_factory=list)
    email_template: str = ""

    webhook_enabled: bool = False
    webhook_url: str = ""

    # 预警阈值
    alert_levels: List[AlertLevel] = field(default_factory=lambda: [AlertLevel.INFO])
    intel_types: List[IntelligenceType] = field(default_factory=list)  # 空=全部

    # 过滤条件
    keywords_filter: List[str] = field(default_factory=list)  # 仅包含这些词
    exclude_keywords: List[str] = field(default_factory=list)  # 排除这些词


@dataclass
class IntelligenceStats:
    """情报统计"""
    total_collected: int = 0
    total_processed: int = 0
    rumor_detected: int = 0
    alerts_triggered: int = 0
    reports_generated: int = 0

    by_type: Dict[str, int] = field(default_factory=dict)
    by_source: Dict[str, int] = field(default_factory=dict)
    by_sentiment: Dict[str, int] = field(default_factory=dict)  # positive/neutral/negative

    recent_activity: List[Dict[str, Any]] = field(default_factory=list)


# ============ 配置模型 ============

@dataclass
class IntelligenceCenterConfig:
    """情报中心总配置"""
    # 搜索配置
    search_engines: List[str] = field(default_factory=lambda: ["web", "news"])
    search_cache_hours: int = 1
    max_results_per_query: int = 20

    # 监控配置
    default_monitor_interval: int = 3600  # 秒
    max_concurrent_tasks: int = 5

    # 谣言检测配置
    rumor_confidence_threshold: float = 0.6
    rumor_verification_sources: List[str] = field(default_factory=lambda: [
        "fact_check", "official_verification", "social_debunk"
    ])

    # 情感分析配置
    sentiment_positive_threshold: float = 0.3
    sentiment_negative_threshold: float = -0.3

    # 报告配置
    default_report_format: str = "markdown"
    report_output_dir: str = ""

    # 通知配置
    notification: NotificationConfig = field(default_factory=NotificationConfig)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "search_engines": self.search_engines,
            "search_cache_hours": self.search_cache_hours,
            "max_results_per_query": self.max_results_per_query,
            "default_monitor_interval": self.default_monitor_interval,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "rumor_confidence_threshold": self.rumor_confidence_threshold,
            "rumor_verification_sources": self.rumor_verification_sources,
            "sentiment_positive_threshold": self.sentiment_positive_threshold,
            "sentiment_negative_threshold": self.sentiment_negative_threshold,
            "default_report_format": self.default_report_format,
            "report_output_dir": self.report_output_dir,
            "notification": self.notification.__dict__ if isinstance(self.notification, NotificationConfig) else self.notification,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntelligenceCenterConfig":
        if "notification" in data and isinstance(data["notification"], dict):
            data["notification"] = NotificationConfig(**data["notification"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})