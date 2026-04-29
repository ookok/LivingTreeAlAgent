"""
智能创作与专业审核增强系统 - 数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import uuid


class ReviewDomain(Enum):
    """审核领域"""
    EIA = "eia"                    # 环评
    FINANCIAL = "financial"        # 财务
    LEGAL = "legal"                # 法律
    TECHNICAL = "technical"        # 技术文档
    GENERAL = "general"           # 通用


class ReviewLevel(Enum):
    """审核级别"""
    AUTO_PREVIEW = "auto_preview"    # 自动预审
    PROFESSIONAL = "professional"     # 专业深度审核
    COMPREHENSIVE = "comprehensive"  # 综合评估
    FINAL = "final"                 # 最终审核


class ReviewStatus(Enum):
    """审核状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    REVISION = "revision"


class IssueSeverity(Enum):
    """问题严重程度"""
    CRITICAL = "critical"    # 严重
    MAJOR = "major"          # 主要
    MINOR = "minor"          # 次要
    SUGGESTION = "suggestion"  # 建议


class IssueCategory(Enum):
    """问题类别"""
    ACCURACY = "accuracy"           # 准确性
    COMPLETENESS = "completeness"   # 完整性
    LOGIC = "logic"                 # 逻辑性
    FORMAT = "format"               # 格式
    COMPLIANCE = "compliance"       # 合规性
    CONSISTENCY = "consistency"     # 一致性
    STYLE = "style"                 # 风格


class QualityLevel(Enum):
    """质量等级"""
    EXCELLENT = "excellent"    # 优秀
    GOOD = "good"             # 良好
    ACCEPTABLE = "acceptable"  # 合格
    POOR = "poor"             # 不合格


class EntityType(Enum):
    """实体类型"""
    PERSON = "person"
    ORG = "org"
    TIME = "time"
    LOCATION = "location"
    MONEY = "money"
    LAW = "law"
    STANDARD = "standard"
    TERM = "term"


@dataclass
class Entity:
    """实体"""
    entity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    entity_type: EntityType = EntityType.TERM
    text: str = ""
    start_pos: int = 0
    end_pos: int = 0
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewIssue:
    """审核问题"""
    issue_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    location: str = ""  # 位置描述
    severity: IssueSeverity = IssueSeverity.MINOR
    category: IssueCategory = IssueCategory.ACCURACY
    evidence: str = ""  # 依据
    suggestion: str = ""  # 修改建议
    example: str = ""  # 修改示例
    domain: ReviewDomain = ReviewDomain.GENERAL
    auto_fixed: bool = False
    fixed_version: Optional[str] = None


@dataclass
class ReviewResult:
    """审核结果"""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    domain: ReviewDomain = ReviewDomain.GENERAL
    
    # 审核信息
    status: ReviewStatus = ReviewStatus.PENDING
    review_level: ReviewLevel = ReviewLevel.AUTO_PREVIEW
    
    # 评分
    overall_score: float = 0.0  # 0-100
    quality_level: QualityLevel = QualityLevel.ACCEPTABLE
    
    # 问题列表
    issues: List[ReviewIssue] = field(default_factory=list)
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0
    suggestion_count: int = 0
    
    # 时间统计
    processing_time_ms: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 引擎信息
    engine_version: str = "1.0.0"
    confidence: float = 0.0


@dataclass
class ReviewOpinion:
    """审核意见"""
    opinion_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # 基本信息
    reviewer_id: str = ""
    reviewer_name: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    
    # 意见内容
    summary: str = ""  # 总体评价摘要
    verdict: str = ""  # 通过/不通过/修改
    key_findings: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)  # 优点
    improvements: List[str] = field(default_factory=list)  # 改进点
    
    # 详细意见
    detailed_opinions: List[Dict[str, Any]] = field(default_factory=list)
    
    # 签名
    signature: Optional[str] = None
    verified: bool = False


@dataclass
class Document:
    """文档"""
    doc_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    content: str = ""
    content_type: str = "general"
    domain: ReviewDomain = ReviewDomain.GENERAL
    
    # 元数据
    author: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # 版本
    version: int = 1
    parent_id: Optional[str] = None
    
    # 状态
    status: str = "draft"
    review_result: Optional[ReviewResult] = None
    
    # 标签
    tags: List[str] = field(default_factory=list)


@dataclass
class KnowledgeEntry:
    """知识条目"""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # 内容
    title: str = ""
    content: str = ""
    domain: ReviewDomain = ReviewDomain.GENERAL
    
    # 分类
    category: str = ""
    tags: List[str] = field(default_factory=list)
    
    # 属性
    properties: Dict[str, Any] = field(default_factory=dict)
    
    # 关系
    relations: List[Dict[str, str]] = field(default_factory=list)
    
    # 来源
    source: str = ""
    source_url: str = ""
    
    # 质量
    quality_score: float = 0.0
    usage_count: int = 0
    
    # 时间
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    verified_at: Optional[datetime] = None


@dataclass
class CollaborationSession:
    """协作会话"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # 文档
    document_id: str = ""
    
    # 参与者
    participants: List[Dict[str, str]] = field(default_factory=list)
    
    # 权限
    permissions: Dict[str, List[str]] = field(default_factory=dict)  # user_id -> [permissions]
    
    # 状态
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.now)
    
    # 活动
    activities: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Activity:
    """活动记录"""
    activity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    type: str = ""  # edit, comment, review, etc.
    user_id: str = ""
    user_name: str = ""
    
    content: Dict[str, Any] = field(default_factory=dict)
    
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class QualityCertification:
    """质量认证"""
    cert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # 认证对象
    document_id: str = ""
    creator_id: str = ""
    
    # 认证级别
    level: QualityLevel = QualityLevel.GOOD
    
    # 评分
    overall_score: float = 0.0
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    
    # 认证信息
    certified_by: List[str] = field(default_factory=list)  # 认证者
    certified_at: datetime = field(default_factory=datetime.now)
    
    # 有效期
    valid_until: Optional[datetime] = None
    
    # 徽章
    badge: str = ""
    badge_url: Optional[str] = None
    
    # 状态
    status: str = "active"


@dataclass
class SystemStats:
    """系统统计"""
    total_documents: int = 0
    total_reviews: int = 0
    avg_review_time_ms: float = 0.0
    pass_rate: float = 0.0
    avg_score: float = 0.0
    
    domain_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    quality_distribution: Dict[str, int] = field(default_factory=dict)
    
    top_reviewers: List[Dict[str, Any]] = field(default_factory=list)
    recent_activities: List[Dict[str, Any]] = field(default_factory=list)
