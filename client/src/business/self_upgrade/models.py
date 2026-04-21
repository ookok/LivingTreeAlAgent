# models.py — 自我升级系统数据模型

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


class DebateRole(Enum):
    """辩论角色"""
    CONSERVATIVE = "conservative"  # 保守派 — 稳健、风险规避
    RADICAL = "radical"           # 激进派 — 创新、风险偏好
    MEDIATOR = "mediator"         # 调解者 — 综合两边


class DebateVerdict(Enum):
    """辩论结论"""
    CONSERVATIVE_WINS = "conservative_wins"
    RADICAL_WINS = "radical_wins"
    COMPROMISE = "compromise"      # 妥协
    INCONCLUSIVE = "inconclusive"  # 未决
    TBD = "tbd"                   # 待定（需人工）


class ExternalSource(Enum):
    """外部信息来源"""
    REDDIT = "reddit"
    ZHIHU = "zhihu"
    WEIBO = "weibo"
    GITHUB = "github"
    NEWS = "news"
    UNKNOWN = "unknown"


class HumanVerdict(Enum):
    """人类终审结论"""
    APPROVED = "approved"       # ✅ 认可
    REVISED = "revised"         # ⚠️ 存疑/修改
    REJECTED = "rejected"       # ❌ 驳回
    PENDING = "pending"         # 待审核


class SafetyLevel(Enum):
    """安全等级"""
    SAFE = "safe"              # 安全，可发布
    REVIEW = "review"          # 需人工审核
    BLOCK = "block"            # 阻断，不可用


@dataclass
class DebateArgument:
    """辩论论点"""
    role: DebateRole
    论点: str
    论据: List[str] = field(default_factory=list)
    反驳: str = ""
    confidence: float = 0.5  # 0.0-1.0


@dataclass
class DebateRecord:
    """完整辩论记录"""
    id: str
    topic: str                          # 辩题
    topic_category: str                 # 类别 (network/security/performance等)
    context: Dict[str, Any]             # 原始上下文
    conservative_args: List[DebateArgument] = field(default_factory=list)
    radical_args: List[DebateArgument] = field(default_factory=list)
    verdict: DebateVerdict = DebateVerdict.TBD
    final_conclusion: str = ""          # 最终结论
    contradictions: List[str] = field(default_factory=list)  # 矛盾点
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    human_verdict: HumanVerdict = HumanVerdict.PENDING
    human_notes: str = ""


@dataclass
class ExternalInsight:
    """外部吸收洞察"""
    id: str
    source: ExternalSource
    source_url: str
    source_title: str
    content_summary: str               # 内容摘要
    key_points: List[str] = field(default_factory=list)
    local_belief: str = ""             # 本地原有认知
    difference_flagged: str = ""       # 标记的差异
    absorbed: bool = False            # 是否已被吸收进知识库
    absorbed_at: Optional[datetime] = None
    safety_level: SafetyLevel = SafetyLevel.SAFE
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class KnowledgeEntry:
    """知识库条目"""
    id: str
    category: str                     # 类别 (network/performance/security等)
    key: str                          # 知识 key
    value: str                        # 知识 value
    source_debate_id: Optional[str] = None   # 来源辩论
    source_external_id: Optional[str] = None  # 来源外部洞察
    human_verdict: HumanVerdict = HumanVerdict.PENDING
    version: int = 1                  # 版本号
    previous_value: str = ""          # 修改前值
    tags: List[str] = field(default_factory=list)  # 标签
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expired_at: Optional[datetime] = None  # 过期时间（可选）


@dataclass
class SafetyCheckResult:
    """安全审查结果"""
    passed: bool
    level: SafetyLevel
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvolutionTask:
    """进化任务"""
    id: str
    task_type: str                    # debate/external/review/safety
    trigger: str                      # 触发原因 (idle/conflict/publish/manual)
    status: str = "pending"           # pending/running/completed/failed
    topic: str = ""
    result_summary: str = ""
    error_message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


@dataclass
class SystemConfig:
    """系统配置"""
    # 调度配置
    idle_trigger_minutes: int = 5      # 闲置多少分钟触发
    auto_debate_enabled: bool = True
    auto_external_enabled: bool = True
    auto_safety_enabled: bool = True

    # 外部抓取配置
    reddit_enabled: bool = False
    zhihu_enabled: bool = False
    weibo_enabled: bool = False

    # 安全配置
    safety_level_strict: bool = True   # 严格模式
    require_human_review: bool = True  # 是否需要人工审核

    # 辩论配置
    max_arguments_per_side: int = 3    # 每方最多论点
    debate_rounds: int = 2             # 辩论轮数
