# models.py — 聚合推荐系统数据模型

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


class FeedSource(Enum):
    """信息来源"""
    WEIBO = "weibo"           # 微博
    ZHIHU = "zhihu"           # 知乎
    REDDIT = "reddit"         # Reddit
    GITHUB = "github"         # GitHub
    NEWS = "news"             # 新闻
    FORUM = "forum"           # 论坛
    ORDER = "order"           # 订单/待办
    CUSTOM = "custom"         # 自定义
    UNKNOWN = "unknown"


class MediaType(Enum):
    """媒体类型"""
    NONE = "none"             # 无图
    IMAGE = "image"           # 图片
    VIDEO = "video"           # 视频
    GIF = "gif"               # 动图


class FeedType(Enum):
    """内容类型"""
    NEWS = "news"             # 新闻
    TECH = "tech"             # 技术
    SOCIAL = "social"         # 社交
    VIDEO = "video"           # 视频
    PRODUCT = "product"       # 产品
    ORDER = "order"           # 订单
    TASK = "task"             # 任务
    OTHER = "other"


@dataclass
class FeedItem:
    """
    聚合信息条目

    增强字段：
    - thumbnail_url: 缩略图 URL
    - video_embed: 视频嵌入 URL
    - media_type: 媒体类型
    - media_size: 媒体尺寸 (width, height)
    """
    # 基础信息
    id: str
    title: str
    summary: str
    source: FeedSource

    # 媒体信息
    url: str                          # 原始链接
    thumbnail_url: str = ""            # 缩略图 URL
    video_embed: str = ""              # 视频嵌入 URL
    media_type: MediaType = MediaType.NONE
    media_width: int = 0
    media_height: int = 0

    # 元数据
    feed_type: FeedType = FeedType.OTHER
    author: str = ""
    author_avatar: str = ""
    tags: List[str] = field(default_factory=list)

    # 互动数据
    likes: int = 0                     # 点赞数
    comments: int = 0                  # 评论数
    shares: int = 0                    # 分享数
    views: int = 0                     # 阅读数

    # 时间
    published_at: Optional[datetime] = None
    fetched_at: datetime = field(default_factory=datetime.now)

    # 状态
    is_read: bool = False
    is_bookmarked: bool = False
    is_interested: bool = False       # 用户感兴趣

    # 兴趣权重（由引擎计算）
    interest_score: float = 0.0        # 0.0-1.0

    # 安全
    safety_level: str = "safe"         # safe/review/block

    # 来源特定数据
    extra_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_media(self) -> bool:
        return self.media_type != MediaType.NONE

    @property
    def has_thumbnail(self) -> bool:
        return bool(self.thumbnail_url)

    @property
    def display_time(self) -> str:
        """友好的时间显示"""
        if not self.published_at:
            return ""

        now = datetime.now()
        diff = now - self.published_at

        if diff.total_seconds() < 60:
            return "刚刚"
        elif diff.total_seconds() < 3600:
            return f"{int(diff.total_seconds() / 60)}分钟前"
        elif diff.total_seconds() < 86400:
            return f"{int(diff.total_seconds() / 3600)}小时前"
        elif diff.days < 7:
            return f"{diff.days}天前"
        else:
            return self.published_at.strftime("%m-%d")


@dataclass
class InterestProfile:
    """
    用户兴趣画像

    存储用户偏好，用于个性化推荐排序
    """
    # 标签权重 (tag -> weight, 0.0-1.0)
    tag_weights: Dict[str, float] = field(default_factory=dict)

    # 来源权重
    source_weights: Dict[str, float] = field(default_factory=dict)

    # 类型权重
    type_weights: Dict[str, float] = field(default_factory=dict)

    # 行为统计
    total_clicks: int = 0
    total_views: int = 0
    total_hides: int = 0              # 不感兴趣次数

    # 最后更新时间
    updated_at: datetime = field(default_factory=datetime.now)

    def get_tag_weight(self, tag: str) -> float:
        """获取标签权重"""
        return self.tag_weights.get(tag.lower(), 0.5)

    def boost_tag(self, tag: str, amount: float = 0.1):
        """提升标签权重"""
        tag = tag.lower()
        current = self.tag_weights.get(tag, 0.5)
        self.tag_weights[tag] = min(1.0, current + amount)
        self.updated_at = datetime.now()

    def decay_tag(self, tag: str, amount: float = 0.15):
        """降低标签权重 (负向反馈)"""
        tag = tag.lower()
        current = self.tag_weights.get(tag, 0.5)
        self.tag_weights[tag] = max(0.0, current - amount)
        self.updated_at = datetime.now()

    def boost_source(self, source: str, amount: float = 0.1):
        """提升来源权重"""
        current = self.source_weights.get(source, 0.5)
        self.source_weights[source] = min(1.0, current + amount)
        self.updated_at = datetime.now()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_tags": len(self.tag_weights),
            "total_clicks": self.total_clicks,
            "total_views": self.total_views,
            "total_hides": self.total_hides,
        }


@dataclass
class FeedConfig:
    """聚合配置"""
    # 抓取配置
    fetch_interval_minutes: int = 30     # 抓取间隔
    max_items_per_source: int = 20       # 每来源最大条数
    thumbnail_max_size_kb: int = 100     # 缩略图最大 KB

    # UI 配置
    card_width: int = 300               # 卡片宽度 px
    card_max_height: int = 400          # 卡片最大高度
    visible_cards: int = 50             # 可见卡片数

    # 兴趣配置
    interest_decay_factor: float = 0.7  # 负反馈衰减因子 (↓30%)
    interest_boost_factor: float = 1.2 # 正反馈增强因子
    time_decay_days: int = 7            # 内容过期天数

    # 安全配置
    strict_mode: bool = True             # 严格模式


@dataclass
class FeedSourceConfig:
    """单个来源的配置"""
    source: FeedSource
    enabled: bool = True
    name: str = ""
    icon: str = ""
    api_endpoint: str = ""
    api_key: str = ""
    tags: List[str] = field(default_factory=list)  # 自动标签
