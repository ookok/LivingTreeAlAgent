"""
智能创作与内容监控系统 - 数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import uuid


class ContentType(Enum):
    FINANCIAL = "financial"
    LEGAL = "legal"
    PROJECT_PLAN = "project_plan"
    MEETING_NOTES = "meeting_notes"
    WORK_LOG = "work_log"
    LEARNING_NOTES = "learning_notes"
    GENERAL = "general"
    UNKNOWN = "unknown"


class AlertLevel(Enum):
    NORMAL = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ContentStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVIEWING = "reviewing"


class RuleType(Enum):
    KEYWORD = "keyword"
    REGEX = "regex"
    SEMANTIC = "semantic"
    PATTERN = "pattern"


class NotificationChannel(Enum):
    SYSTEM = "system"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"


@dataclass
class SensitiveWord:
    word: str
    category: str = "default"
    weight: int = 1
    alert_level: AlertLevel = AlertLevel.LOW
    description: str = ""


@dataclass
class MonitoringRule:
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    rule_type: RuleType = RuleType.KEYWORD
    pattern: str = ""
    alert_level: AlertLevel = AlertLevel.LOW
    action: str = "flag"
    category: str = "default"
    enabled: bool = True
    priority: int = 0


@dataclass
class ContentItem:
    content_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    content_type: ContentType = ContentType.UNKNOWN
    title: str = ""
    author: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: ContentStatus = ContentStatus.PENDING
    alert_level: AlertLevel = AlertLevel.NORMAL
    alert_reasons: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SummarizationResult:
    original_content: str
    content_type: ContentType
    summary: str = ""
    key_points: List[str] = field(default_factory=list)
    categories: Dict[str, List[str]] = field(default_factory=dict)
    statistics: Dict[str, Any] = field(default_factory=dict)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class AlertRecord:
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content_id: str = ""
    content: str = ""
    alert_level: AlertLevel = AlertLevel.NORMAL
    trigger_rules: List[str] = field(default_factory=list)
    matched_keywords: List[str] = field(default_factory=list)
    action_taken: str = ""
    handled: bool = False
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class RecognizedEntity:
    entity_type: str
    value: str
    start_pos: int
    end_pos: int
    confidence: float


@dataclass
class ContentAnalysis:
    content_id: str
    content_type: ContentType
    confidence: float
    entities: List[RecognizedEntity] = field(default_factory=list)
    sentiment: float = 0.0
    risk_score: float = 0.0
    keywords: List[str] = field(default_factory=list)


@dataclass
class SystemStats:
    total_content: int = 0
    total_alerts: int = 0
    pending_review: int = 0
    alerts_by_level: Dict[str, int] = field(default_factory=dict)
    uptime_seconds: float = 0.0
