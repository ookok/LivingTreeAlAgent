# models.py — 智能进化系统数据模型

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import hashlib
import json


# ============ 枚举定义 ============

class PatchAction(Enum):
    """补丁动作类型"""
    INCREASE_TIMEOUT = "increase_timeout"       # 增加超时
    DECREASE_TIMEOUT = "decrease_timeout"      # 减少超时
    ENABLE_CACHE = "enable_cache"              # 启用缓存
    DISABLE_CACHE = "disable_cache"            # 禁用缓存
    ADD_FALLBACK = "add_fallback"              # 添加降级方案
    RETRY策略 = "update_retry"                # 更新重试策略
    UI_SIMPLIFY = "ui_simplify"               # UI简化
    UI_ADD_HINT = "ui_add_hint"               # UI添加提示
    UI_CHANGE_DEFAULT = "ui_change_default"   # 更改默认值
    CUSTOM = "custom"                         # 自定义


class PainType(Enum):
    """UI痛点类型"""
    REPEATED_HELP = "repeated_help"           # 反复求助
    LONG_STAY = "long_stay"                  # 长停留
    OPERATION_ROLLBACK = "operation_rollback"  # 操作回退
    FORM_ABANDON = "form_abandon"            # 表单放弃
    CONFUSING_UI = "confusing_ui"            # 界面困惑
    SLOW_RESPONSE = "slow_response"          # 响应慢


class PainCause(Enum):
    """痛点原因推断"""
    INSUFFICIENT_HINT = "insufficient_hint"  # 说明不足
    OPTION_COMPLEX = "option_complex"        # 选项复杂
    DEFAULT_UNREASONABLE = "default_unreasonable"  # 默认不合理
    FLOW_UNCLEAR = "flow_unclear"           # 流程不清
    NETWORK_ISSUE = "network_issue"          # 网络问题
    UNKNOWN = "unknown"                     # 未知


class ReportStatus(Enum):
    """上报状态"""
    PENDING = "pending"     # 待上报
    UPLOADED = "uploaded"   # 已上报
    FAILED = "failed"       # 上报失败


class PatchStatus(Enum):
    """补丁状态"""
    APPLIED = "applied"      # 已应用
    REJECTED = "rejected"    # 已拒绝
    EXPIRED = "expired"     # 已过期
    PENDING = "pending"     # 待审核
    LEGACY = "legacy"       # 已标记为遗留 (升级后)


# ============ 升级扫描系统枚举 ============

class OSSReplacementDecision(Enum):
    """开源库替换决策"""
    ADOPT = "adopt"                 # 直接采用
    WRAP_AND_ADOPT = "wrap_and_adopt"  # 封装后采用
    KEEP_CUSTOM = "keep_custom"     # 保留自研
    DEFER = "defer"                 # 延后决策
    REJECT = "reject"              # 拒绝


class ScanSource(Enum):
    """扫描来源"""
    GITHUB = "github"
    GITEE = "gitee"
    LOCAL_CACHE = "local_cache"
    PRESET_HOT = "preset_hot"
    ALIYUN_MIRROR = "aliyun_mirror"


class DataMigrationStrategy(Enum):
    """数据迁移策略"""
    LAZY = "lazy"           # 惰性迁移
    EAGER = "eager"         # 立即迁移
    DUAL_READ = "dual_read" # 双读兼容


# ============ 核心数据结构 ============

@dataclass
class PatchDoc:
    """
    补丁文档

    描述一个运行时补丁的结构化记录
    """
    id: str                          # 唯一标识 (sha256前8位)
    module: str                      # 模块名 (如 "network_retry")
    action: PatchAction              # 动作类型
    old_value: Any                   # 旧值
    new_value: Any                   # 新值
    reason: str                      # 生成原因
    signature: str                   # 签名 (防止篡改)
    timestamp: int                   # 时间戳
    client_id: str                   # 匿名客户端ID
    status: PatchStatus = PatchStatus.PENDING  # 状态
    applied_at: Optional[int] = None # 应用时间

    def __post_init__(self):
        if isinstance(self.action, str):
            self.action = PatchAction(self.action)
        if isinstance(self.status, str):
            self.status = PatchStatus(self.status)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "module": self.module,
            "action": self.action.value if isinstance(self.action, PatchAction) else self.action,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "signature": self.signature,
            "timestamp": self.timestamp,
            "client_id": self.client_id,
            "status": self.status.value if isinstance(self.status, PatchStatus) else self.status,
            "applied_at": self.applied_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PatchDoc":
        return cls(
            id=data["id"],
            module=data["module"],
            action=PatchAction(data["action"]),
            old_value=data["old_value"],
            new_value=data["new_value"],
            reason=data["reason"],
            signature=data["signature"],
            timestamp=data["timestamp"],
            client_id=data["client_id"],
            status=PatchStatus(data.get("status", "pending")),
            applied_at=data.get("applied_at"),
        )

    def generate_id(self) -> str:
        """生成补丁ID"""
        raw = f"{self.module}:{self.action.value}:{self.new_value}:{self.timestamp}"
        return hashlib.sha256(raw.encode()).hexdigest()[:8]

    def sign(self, secret: str = "") -> str:
        """生成签名"""
        raw = f"{self.id}:{self.module}:{self.new_value}:{secret}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class UIPainPoint:
    """
    UI痛点事件

    描述一个用户体验痛点的结构化记录
    """
    id: str                          # 唯一标识
    module: str                      # 涉及模块
    pain_type: PainType              # 痛点类型
    cause: PainCause                 # 推断原因
    description: str                 # 描述
    timestamp: int                   # 发生时间
    client_id: str                   # 匿名客户端ID
    count: int = 1                   # 累计次数
    resolved: bool = False           # 是否已解决

    def __post_init__(self):
        if isinstance(self.pain_type, str):
            self.pain_type = PainType(self.pain_type)
        if isinstance(self.cause, str):
            self.cause = PainCause(self.cause)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "module": self.module,
            "pain_type": self.pain_type.value if isinstance(self.pain_type, PainType) else self.pain_type,
            "cause": self.cause.value if isinstance(self.cause, PainCause) else self.cause,
            "description": self.description,
            "timestamp": self.timestamp,
            "client_id": self.client_id,
            "count": self.count,
            "resolved": self.resolved,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UIPainPoint":
        return cls(
            id=data["id"],
            module=data["module"],
            pain_type=PainType(data["pain_type"]),
            cause=PainCause(data.get("cause", "unknown")),
            description=data["description"],
            timestamp=data["timestamp"],
            client_id=data["client_id"],
            count=data.get("count", 1),
            resolved=data.get("resolved", False),
        )


@dataclass
class WeeklyReport:
    """
    周报

    客户端每周上报的数据包
    """
    week_id: str                     # 周标识 (如 "2025-W15")
    client_id: str                   # 匿名客户端ID
    patches: List[PatchDoc]          # 补丁列表
    pain_points: List[UIPainPoint]   # UI痛点列表
    generated_at: int                 # 生成时间戳
    uploaded_at: Optional[int] = None # 上传时间
    status: ReportStatus = ReportStatus.PENDING
    client_version: str = "1.0.0"    # 客户端版本
    platform: str = "windows"        # 平台

    def __post_init__(self):
        if isinstance(self.status, str):
            self.status = ReportStatus(self.status)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "week_id": self.week_id,
            "client_id": self.client_id,
            "patches": [p.to_dict() for p in self.patches],
            "pain_points": [p.to_dict() for p in self.pain_points],
            "generated_at": self.generated_at,
            "uploaded_at": self.uploaded_at,
            "status": self.status.value if isinstance(self.status, ReportStatus) else self.status,
            "client_version": self.client_version,
            "platform": self.platform,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeeklyReport":
        return cls(
            week_id=data["week_id"],
            client_id=data["client_id"],
            patches=[PatchDoc.from_dict(p) for p in data.get("patches", [])],
            pain_points=[UIPainPoint.from_dict(p) for p in data.get("pain_points", [])],
            generated_at=data["generated_at"],
            uploaded_at=data.get("uploaded_at"),
            status=ReportStatus(data.get("status", "pending")),
            client_version=data.get("client_version", "1.0.0"),
            platform=data.get("platform", "unknown"),
        )

    def mark_uploaded(self):
        """标记为已上传"""
        self.status = ReportStatus.UPLOADED
        self.uploaded_at = int(datetime.now().timestamp())

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "patch_count": len(self.patches),
            "pain_point_count": len(self.pain_points),
            "modules_affected": list(set(p.module for p in self.patches + self.pain_points)),
        }


# ============ 配置与状态 ============

@dataclass
class ClientConfig:
    """客户端配置"""
    enabled: bool = True              # 是否启用进化系统
    auto_patch: bool = True          # 自动应用补丁
    auto_upload: bool = True         # 自动上传周报
    upload_interval_days: int = 7    # 上传周期（天）
    relay_server_url: str = "http://localhost:8766"  # 中继服务器地址
    token: str = ""                  # 认证Token（可选）
    min_upload_interval: int = 3600  # 最小上报间隔（秒）
    last_upload: Optional[int] = None # 上次上传时间
    client_id: str = ""              # 匿名客户端ID
    whitelist_modules: List[str] = field(default_factory=lambda: [
        "network_retry", "ui_tweaks", "cache", "timeout", "retry"
    ])
    blacklist_modules: List[str] = field(default_factory=lambda: [
        "auth", "password", "token", "secret", "core"
    ])

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClientConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class EvolutionStats:
    """进化统计"""
    total_patches: int = 0           # 总补丁数
    applied_patches: int = 0         # 已应用补丁
    rejected_patches: int = 0        # 已拒绝补丁
    total_pain_points: int = 0       # 总痛点数
    resolved_pain_points: int = 0     # 已解决痛点
    reports_generated: int = 0       # 生成报告数
    reports_uploaded: int = 0         # 上传报告数
    last_patch_time: Optional[int] = None
    last_report_time: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============ 服务器端数据结构 ============

@dataclass
class AggregatedModuleHits:
    """聚合模块热度"""
    module: str
    patch_count: int
    pain_point_count: int
    total_hits: int
    week_over_week_change: float = 0  # 环比变化

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AggregatedTrend:
    """聚合趋势数据"""
    week_id: str
    total_patches: int
    total_pain_points: int
    top_modules: List[str]
    top_patch_actions: List[str]
    new_clients: int
    active_clients: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============ 工具函数 ============

def get_week_id(t: datetime = None) -> str:
    """获取当前周标识 (ISO format)"""
    if t is None:
        t = datetime.now()
    # 获取ISO周
    iso_calendar = t.isocalendar()
    return f"{iso_calendar[0]}-W{iso_calendar[1]:02d}"


def generate_client_id() -> str:
    """生成匿名客户端ID"""
    import uuid
    raw = f"{uuid.uuid4().hex}{datetime.now().isoformat()}"
    return f"anon_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def hash_for_dedup(*parts: str) -> str:
    """生成去重哈希"""
    return hashlib.sha256(":".join(parts).encode()).hexdigest()[:16]


# ============ 终极版新增：社区共享与外部求解 ============

class ForumPostType(Enum):
    """论坛帖子类型"""
    PATCH_SHARE = "patch_share"         # 补丁分享
    HELP_REQUEST = "help_request"       # 求助帖
    KNOWLEDGE分享 = "knowledge_share"   # 知识分享
    DISCUSSION = "discussion"           # 讨论帖


class PostStatus(Enum):
    """帖子状态"""
    DRAFT = "draft"           # 草稿
    PUBLISHED = "published"    # 已发布
    EXTERNAL = "external"     # 已转发外部
    ARCHIVED = "archived"     # 已归档


class ExternalPlatform(Enum):
    """外部平台"""
    TWITTER = "twitter"       # Twitter/X
    ZHIHU = "zhihu"           # 知乎
    WEIBO = "weibo"          # 微博
    REDDIT = "reddit"        # Reddit


class DistillationCategory(Enum):
    """蒸馏知识类别"""
    SEARCH_FILTER = "search_filter"     # 搜索筛选
    PRODUCT_PREFERENCE = "product_preference"  # 产品偏好
    PRICE_SENSITIVITY = "price_sensitivity"   # 价格敏感度
    BRAND_LOYALTY = "brand_loyalty"     # 品牌忠诚
    USER_HABIT = "user_habit"          # 用户习惯


@dataclass
class ForumPost:
    """
    论坛帖子

    描述一个论坛帖子的结构化记录 (.tree 网络)
    """
    id: str                           # 唯一标识
    post_type: ForumPostType         # 帖子类型
    title: str                       # 标题
    content: str                     # 内容 (Markdown)
    author_client_id: str            # 作者匿名ID
    timestamp: int                   # 发布时间
    status: PostStatus = PostStatus.DRAFT
    external_platform: Optional[ExternalPlatform] = None  # 外发平台
    external_url: Optional[str] = None  # 外发链接
    parent_post_id: Optional[str] = None  # 父帖子ID (回复)
    tags: List[str] = field(default_factory=list)
    upvotes: int = 0                  # 点赞数
    reply_count: int = 0              # 回复数
    referenced_patch_id: Optional[str] = None  # 引用的补丁ID

    def __post_init__(self):
        if isinstance(self.post_type, str):
            self.post_type = ForumPostType(self.post_type)
        if isinstance(self.status, str):
            self.status = PostStatus(self.status)
        if isinstance(self.external_platform, str):
            self.external_platform = ExternalPlatform(self.external_platform)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "post_type": self.post_type.value if isinstance(self.post_type, ForumPostType) else self.post_type,
            "title": self.title,
            "content": self.content,
            "author_client_id": self.author_client_id,
            "timestamp": self.timestamp,
            "status": self.status.value if isinstance(self.status, PostStatus) else self.status,
            "external_platform": self.external_platform.value if isinstance(self.external_platform, ExternalPlatform) else self.external_platform,
            "external_url": self.external_url,
            "parent_post_id": self.parent_post_id,
            "tags": self.tags,
            "upvotes": self.upvotes,
            "reply_count": self.reply_count,
            "referenced_patch_id": self.referenced_patch_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForumPost":
        return cls(
            id=data["id"],
            post_type=ForumPostType(data["post_type"]),
            title=data["title"],
            content=data["content"],
            author_client_id=data["author_client_id"],
            timestamp=data["timestamp"],
            status=PostStatus(data.get("status", "draft")),
            external_platform=ExternalPlatform(data["external_platform"]) if data.get("external_platform") else None,
            external_url=data.get("external_url"),
            parent_post_id=data.get("parent_post_id"),
            tags=data.get("tags", []),
            upvotes=data.get("upvotes", 0),
            reply_count=data.get("reply_count", 0),
            referenced_patch_id=data.get("referenced_patch_id"),
        )

    def to_markdown(self) -> str:
        """转换为 Markdown 格式 (机器可解析)"""
        lines = [
            f"<!-- .tree post_id={self.id} type={self.post_type.value} -->",
            f"# {self.title}",
            f"",
            self.content,
            "",
            f"<!-- meta: author={self.author_client_id} timestamp={self.timestamp} -->",
        ]
        if self.referenced_patch_id:
            lines.insert(3, f"```tree-patch\n{self.referenced_patch_id}\n```")
        return "\n".join(lines)

    @classmethod
    def parse_from_markdown(cls, md: str, client_id: str) -> "ForumPost":
        """从 Markdown 解析 (机器解析)"""
        import re
        # 提取 post_id
        id_match = re.search(r"post_id=(\S+)", md)
        post_id = id_match.group(1) if id_match else hash_for_dedup(md, str(int(datetime.now().timestamp())))
        # 提取类型
        type_match = re.search(r"type=(\S+)", md)
        post_type = ForumPostType(type_match.group(1)) if type_match else ForumPostType.DISCUSSION
        # 提取标题
        title_match = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
        title = title_match.group(1) if title_match else "Untitled"
        # 移除 meta 注释后提取内容
        content = re.sub(r"<!--.*?-->", "", md, flags=re.DOTALL).strip()
        content = re.sub(r"^#\s+.+$", "", content, flags=re.MULTILINE).strip()
        return cls(
            id=post_id,
            post_type=post_type,
            title=title,
            content=content,
            author_client_id=client_id,
            timestamp=int(datetime.now().timestamp()),
        )


@dataclass
class DistillationRule:
    """
    蒸馏规则

    从用户行为中提炼的行业知识规则
    """
    id: str                           # 唯一标识
    category: DistillationCategory   # 知识类别
    pattern: str                      # 匹配模式
    rule: str                         # 提炼出的规则
    created_at: int                   # 创建时间
    updated_at: int                   # 更新时间
    evidence_count: int = 0          # 证据数量
    confidence: float = 0.0          # 置信度 (0-1)
    source_modules: List[str] = field(default_factory=list)  # 来源模块
    enabled: bool = True             # 是否启用
    example: str = ""                 # 示例

    def __post_init__(self):
        if isinstance(self.category, str):
            self.category = DistillationCategory(self.category)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value if isinstance(self.category, DistillationCategory) else self.category,
            "pattern": self.pattern,
            "rule": self.rule,
            "evidence_count": self.evidence_count,
            "confidence": self.confidence,
            "source_modules": self.source_modules,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "enabled": self.enabled,
            "example": self.example,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DistillationRule":
        return cls(
            id=data["id"],
            category=DistillationCategory(data["category"]),
            pattern=data["pattern"],
            rule=data["rule"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            evidence_count=data.get("evidence_count", 0),
            confidence=data.get("confidence", 0.0),
            source_modules=data.get("source_modules", []),
            enabled=data.get("enabled", True),
            example=data.get("example", ""),
        )


@dataclass
class IndustryInsight:
    """
    行业洞察事件

    用户行为的脱敏记录，用于蒸馏
    """
    id: str                           # 唯一标识
    category: DistillationCategory   # 事件类别
    keywords: List[str]              # 关键词
    timestamp: int                   # 发生时间
    frequency: int = 1               # 出现频率
    context: str = ""                # 上下文描述
    module: str = ""                 # 来源模块

    def __post_init__(self):
        if isinstance(self.category, str):
            self.category = DistillationCategory(self.category)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value if isinstance(self.category, DistillationCategory) else self.category,
            "keywords": self.keywords,
            "timestamp": self.timestamp,
            "frequency": self.frequency,
            "context": self.context,
            "module": self.module,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IndustryInsight":
        return cls(
            id=data["id"],
            category=DistillationCategory(data["category"]),
            keywords=data["keywords"],
            timestamp=data["timestamp"],
            frequency=data.get("frequency", 1),
            context=data.get("context", ""),
            module=data.get("module", ""),
        )


@dataclass
class BotConfig:
    """
    官方 Bot 配置

    中继服务器管理的平台账号配置
    """
    platform: ExternalPlatform       # 平台
    bot_name: str                    # Bot 名称
    enabled: bool = True             # 是否启用
    rate_limit_per_hour: int = 1     # 每小时限流
    api_key_encrypted: str = ""      # 加密的 API Key
    api_secret_encrypted: str = ""   # 加密的 API Secret
    access_token_encrypted: str = ""  # 加密的 Access Token
    refresh_token_encrypted: str = ""  # 加密的 Refresh Token
    last_post_time: Optional[int] = None  # 最后发帖时间
    total_posts: int = 0            # 总发帖数
    status: str = "active"           # 状态 (active/disabled/expired)
    created_at: int = 0              # 创建时间
    updated_at: int = 0              # 更新时间

    def __post_init__(self):
        if isinstance(self.platform, str):
            self.platform = ExternalPlatform(self.platform)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform.value if isinstance(self.platform, ExternalPlatform) else self.platform,
            "bot_name": self.bot_name,
            "enabled": self.enabled,
            "rate_limit_per_hour": self.rate_limit_per_hour,
            "api_key_encrypted": self.api_key_encrypted,
            "api_secret_encrypted": self.api_secret_encrypted,
            "access_token_encrypted": self.access_token_encrypted,
            "refresh_token_encrypted": self.refresh_token_encrypted,
            "last_post_time": self.last_post_time,
            "total_posts": self.total_posts,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotConfig":
        return cls(
            platform=ExternalPlatform(data["platform"]),
            bot_name=data["bot_name"],
            enabled=data.get("enabled", True),
            rate_limit_per_hour=data.get("rate_limit_per_hour", 1),
            api_key_encrypted=data.get("api_key_encrypted", ""),
            api_secret_encrypted=data.get("api_secret_encrypted", ""),
            access_token_encrypted=data.get("access_token_encrypted", ""),
            refresh_token_encrypted=data.get("refresh_token_encrypted", ""),
            last_post_time=data.get("last_post_time"),
            total_posts=data.get("total_posts", 0),
            status=data.get("status", "active"),
            created_at=data.get("created_at", 0),
            updated_at=data.get("updated_at", 0),
        )


@dataclass
class ExternalPost:
    """
    外部发帖记录

    追踪发往外部平台的帖子
    """
    id: str                           # 唯一标识
    attribution_id: str               # 归因ID
    original_content: str             # 原文
    humanized_content: str            # 拟人化后的内容
    platform: ExternalPlatform        # 目标平台
    status: str = "pending"           # pending/success/failed/safety_rejected
    external_url: Optional[str] = None  # 外部链接
    posted_at: Optional[int] = None   # 发帖时间
    error_message: Optional[str] = None  # 错误信息
    safety_score: float = 1.0        # 安全评分 (0-1)
    replies_received: int = 0         # 收到的回复数

    def __post_init__(self):
        if isinstance(self.platform, str):
            self.platform = ExternalPlatform(self.platform)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "attribution_id": self.attribution_id,
            "original_content": self.original_content,
            "humanized_content": self.humanized_content,
            "platform": self.platform.value if isinstance(self.platform, ExternalPlatform) else self.platform,
            "status": self.status,
            "external_url": self.external_url,
            "posted_at": self.posted_at,
            "error_message": self.error_message,
            "safety_score": self.safety_score,
            "replies_received": self.replies_received,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExternalPost":
        return cls(
            id=data["id"],
            attribution_id=data["attribution_id"],
            original_content=data["original_content"],
            humanized_content=data["humanized_content"],
            platform=ExternalPlatform(data["platform"]),
            status=data.get("status", "pending"),
            external_url=data.get("external_url"),
            posted_at=data.get("posted_at"),
            error_message=data.get("error_message"),
            safety_score=data.get("safety_score", 1.0),
            replies_received=data.get("replies_received", 0),
        )


@dataclass
class Reply回流:
    """
    外部平台回复回流

    从外部平台收集的回复，用于内化
    """
    id: str                           # 唯一标识
    external_post_id: str             # 对应的外部帖子ID
    platform: ExternalPlatform        # 来源平台
    author: str                       # 作者
    content: str                     # 回复内容
    timestamp: int                   # 发布时间
    knowledge_tags: List[str] = field(default_factory=list)  # 知识标签
    is_helpful: bool = False         # 是否有帮助
    absorbed: bool = False           # 是否已内化
    absorbed_at: Optional[int] = None  # 内化时间

    def __post_init__(self):
        if isinstance(self.platform, str):
            self.platform = ExternalPlatform(self.platform)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "external_post_id": self.external_post_id,
            "platform": self.platform.value if isinstance(self.platform, ExternalPlatform) else self.platform,
            "author": self.author,
            "content": self.content,
            "timestamp": self.timestamp,
            "is_helpful": self.is_helpful,
            "absorbed": self.absorbed,
            "absorbed_at": self.absorbed_at,
            "knowledge_tags": self.knowledge_tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reply回流":
        return cls(
            id=data["id"],
            external_post_id=data["external_post_id"],
            platform=ExternalPlatform(data["platform"]),
            author=data["author"],
            content=data["content"],
            timestamp=data["timestamp"],
            knowledge_tags=data.get("knowledge_tags", []),
            is_helpful=data.get("is_helpful", False),
            absorbed=data.get("absorbed", False),
            absorbed_at=data.get("absorbed_at"),
        )


# ============ 增强版配置 ============

@dataclass
class ClientConfigUltimate:
    """终极版客户端配置"""
    # 基础配置
    enabled: bool = True
    auto_patch: bool = True
    auto_upload: bool = True
    upload_interval_days: int = 7

    # 服务器配置
    relay_server_url: str = "http://localhost:8766"
    token: str = ""

    # 社区配置
    forum_enabled: bool = True        # 启用论坛
    p2p_enabled: bool = True          # 启用 P2P
    auto_share_patches: bool = True   # 自动分享补丁

    # 外部求解配置
    external_enabled: bool = True     # 启用外部求解
    bot_name: str = "LivingTree_Bot"  # Bot 名称
    auto_humanize: bool = True        # 自动拟人化
    max_posts_per_hour: int = 1       # 每小时最大发帖数

    # 行业蒸馏配置
    distillation_enabled: bool = True  # 启用行业蒸馏
    min_confidence: float = 0.7       # 最小置信度

    # 安全配置
    min_upload_interval: int = 3600
    last_upload: Optional[int] = None
    client_id: str = ""
    whitelist_modules: List[str] = field(default_factory=lambda: [
        "network_retry", "ui_tweaks", "cache", "timeout", "retry", "distillation"
    ])
    blacklist_modules: List[str] = field(default_factory=lambda: [
        "auth", "password", "token", "secret", "core", "payment"
    ])

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClientConfigUltimate":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ============ 兼容性别名 ============

# 为了向后兼容，保留原始 ClientConfig
ClientConfigUltimate = ClientConfigUltimate
