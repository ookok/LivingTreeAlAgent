"""
去中心化论坛 - 数据模型
基于 P2P 穿透网络、ID 寻址、端到端加密的论坛协议层

参考: ActivityPub (联邦宇宙) / NNTP (新闻组) / SSB (Scuttlebutt)
"""

import time
import uuid
import hashlib
import json
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque


class PostStatus(Enum):
    """帖子状态"""
    DRAFT = "draft"           # 草稿
    PUBLISHED = "published"   # 已发布
    DELETED = "deleted"      # 已删除
    HIDDEN = "hidden"        # 已隐藏


class ReplyStatus(Enum):
    """回复状态"""
    NORMAL = "normal"        # 正常
    DELETED = "deleted"     # 已删除
    HIDDEN = "hidden"       # 已隐藏


class ContentType(Enum):
    """内容类型"""
    TEXT = "text"            # 纯文本
    RICH_TEXT = "rich_text"  # 富文本 (Markdown/HTML)
    IMAGE = "image"          # 图片
    FILE = "file"           # 附件


class VoteType(Enum):
    """投票类型"""
    NONE = "none"           # 无投票
    UP = "up"              # 点赞/顶
    DOWN = "down"          # 点踩/踩
    BOTH = "both"          # 双向投票 (如评分)


@dataclass
class Author:
    """作者信息"""
    node_id: str           # P2P 节点 ID
    display_name: str       # 显示名称
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    reputation: float = 0.0  # 信誉分
    post_count: int = 0       # 发帖数
    reply_count: int = 0      # 回复数

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'Author':
        return cls(**data)


@dataclass
class ContentHash:
    """内容哈希链 (防篡改)"""
    previous_hash: str      # 前一个内容的哈希
    current_hash: str       # 当前内容的哈希
    timestamp: float        # 时间戳

    def verify(self, content: str, previous_hash: str) -> bool:
        """验证内容完整性"""
        expected = hashlib.sha256(f"{previous_hash}{content}{self.timestamp}".encode()).hexdigest()
        return expected == self.current_hash


@dataclass
class Attachment:
    """附件"""
    file_id: str           # 文件 ID (云盘中的标识)
    file_name: str         # 文件名
    file_size: int         # 文件大小 (字节)
    file_type: str         # MIME 类型
    file_url: Optional[str] = None  # 云盘 URL (可选)
    thumbnail_url: Optional[str] = None  # 缩略图 URL
    checksum: Optional[str] = None     # 文件校验和

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'Attachment':
        return cls(**data)


@dataclass
class PostContent:
    """帖子内容"""
    text: str              # 文本内容
    content_type: ContentType = ContentType.TEXT
    attachments: List[Attachment] = field(default_factory=list)
    language: str = "zh"   # 内容语言

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "content_type": self.content_type.value,
            "attachments": [a.to_dict() for a in self.attachments],
            "language": self.language
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PostContent':
        data = dict(data)
        data["content_type"] = ContentType(data.get("content_type", "text"))
        data["attachments"] = [Attachment.from_dict(a) for a in data.get("attachments", [])]
        return cls(**data)


@dataclass
class SmartDraft:
    """智能写作草稿"""
    topic: str             # 主题
    outline: List[str]     # 大纲要点
    arguments_for: List[str]  # 支持论点
    arguments_against: List[str]  # 反对论点
    suggested_references: List[str]  # 建议参考资料
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "outline": self.outline,
            "arguments_for": self.arguments_for,
            "arguments_against": self.arguments_against,
            "suggested_references": self.suggested_references,
            "generated_at": self.generated_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'SmartDraft':
        return cls(**data)


@dataclass
class ForumPost:
    """论坛帖子"""
    post_id: str           # 帖子唯一 ID
    topic_id: str          # 所属话题/版块 ID
    author: Author          # 作者
    title: str             # 标题
    content: PostContent   # 内容
    status: PostStatus = PostStatus.PUBLISHED

    # 互动数据
    upvotes: int = 0       # 点赞数
    downvotes: int = 0     # 点踩数
    reply_count: int = 0   # 回复数
    view_count: int = 0    # 浏览数

    # 哈希链
    hash_chain: Optional[ContentHash] = None

    # 元数据
    created_at: float = field(default_factory=time.time)
    updated_at: Optional[float] = None
    expires_at: Optional[float] = None  # 过期时间 (可选)

    # 草稿 (智能写作)
    smart_draft: Optional[SmartDraft] = None

    # 标签
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        result = {
            "post_id": self.post_id,
            "topic_id": self.topic_id,
            "author": self.author.to_dict(),
            "title": self.title,
            "content": self.content.to_dict(),
            "status": self.status.value,
            "upvotes": self.upvotes,
            "downvotes": self.downvotes,
            "reply_count": self.reply_count,
            "view_count": self.view_count,
            "hash_chain": self.hash_chain.__dict__ if self.hash_chain else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "smart_draft": self.smart_draft.to_dict() if self.smart_draft else None,
            "tags": self.tags
        }
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'ForumPost':
        data = dict(data)
        data["author"] = Author.from_dict(data["author"])
        data["content"] = PostContent.from_dict(data["content"])
        data["status"] = PostStatus(data.get("status", "published"))
        if data.get("hash_chain"):
            data["hash_chain"] = ContentHash(**data["hash_chain"])
        if data.get("smart_draft"):
            data["smart_draft"] = SmartDraft.from_dict(data["smart_draft"])
        return cls(**data)

    def get_score(self) -> float:
        """计算帖子评分 (用于排序)"""
        # 使用威尔逊评分算法
        n = self.upvotes + self.downvotes
        if n == 0:
            return 0.0
        z = 1.644853  # 95% 置信度
        p = self.upvotes / n
        return (p + z*z/(2*n) - z*((p*(1-p) + z*z/(4*n)) / n)**0.5) / (1 + z*z/n)


@dataclass
class ForumReply:
    """论坛回复"""
    reply_id: str          # 回复唯一 ID
    post_id: str          # 所属帖子 ID
    author: Author         # 作者
    content: PostContent  # 内容
    parent_reply_id: Optional[str] = None  # 父回复 ID (嵌套回复)
    status: ReplyStatus = ReplyStatus.NORMAL

    # 互动数据
    upvotes: int = 0
    downvotes: int = 0

    # 哈希链
    hash_chain: Optional[ContentHash] = None

    # 元数据
    created_at: float = field(default_factory=time.time)
    updated_at: Optional[float] = None

    def to_dict(self) -> dict:
        result = {
            "reply_id": self.reply_id,
            "post_id": self.post_id,
            "parent_reply_id": self.parent_reply_id,
            "author": self.author.to_dict(),
            "content": self.content.to_dict(),
            "status": self.status.value,
            "upvotes": self.upvotes,
            "downvotes": self.downvotes,
            "hash_chain": self.hash_chain.__dict__ if self.hash_chain else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'ForumReply':
        data = dict(data)
        data["author"] = Author.from_dict(data["author"])
        data["content"] = PostContent.from_dict(data["content"])
        data["status"] = ReplyStatus(data.get("status", "normal"))
        if data.get("hash_chain"):
            data["hash_chain"] = ContentHash(**data["hash_chain"])
        return cls(**data)


@dataclass
class Topic:
    """话题/版块"""
    topic_id: str          # 话题 ID
    name: str              # 名称
    description: str      # 描述
    icon: str = "📋"      # 图标
    color: str = "#4A90D9"  # 颜色

    # 统计
    post_count: int = 0
    member_count: int = 0

    # 权限
    is_private: bool = False  # 是否私有
    is_nsfw: bool = False     # 是否成人内容

    # 元数据
    created_at: float = field(default_factory=time.time)
    creator_id: str = ""      # 创建者节点 ID

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "color": self.color,
            "post_count": self.post_count,
            "member_count": self.member_count,
            "is_private": self.is_private,
            "is_nsfw": self.is_nsfw,
            "created_at": self.created_at,
            "creator_id": self.creator_id
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Topic':
        return cls(**data)


@dataclass
class Subscription:
    """订阅"""
    subscriber_id: str    # 订阅者节点 ID
    topic_id: str         # 订阅的话题 ID
    subscribed_at: float = field(default_factory=time.time)
    notify_enabled: bool = True  # 是否启用通知

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'Subscription':
        return cls(**data)


@dataclass
class Vote:
    """投票/评分"""
    voter_id: str         # 投票者节点 ID
    target_type: str      # "post" 或 "reply"
    target_id: str         # 目标 ID
    vote_type: VoteType   # 投票类型
    weight: float = 1.0   # 权重 (可用于信誉加权)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "voter_id": self.voter_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "vote_type": self.vote_type.value,
            "weight": self.weight,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Vote':
        data = dict(data)
        data["vote_type"] = VoteType(data.get("vote_type", "none"))
        return cls(**data)


@dataclass
class ReplySummary:
    """AI 生成的回复摘要/分析"""
    reply_id: str
    summary: str           # 摘要
    sentiment: str         # 情感 (positive/neutral/negative)
    key_points: List[str] = field(default_factory=list)  # 关键论点
    suggested_counter: List[str] = field(default_factory=list)  # 建议反驳
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'ReplySummary':
        return cls(**data)


@dataclass
class PostNotification:
    """帖子通知"""
    notification_id: str
    recipient_id: str      # 接收者节点 ID
    notification_type: str  # "new_post" / "new_reply" / "mention" / "vote"
    actor_id: str          # 触发通知的节点 ID
    actor_name: str       # 触发通知的用户名
    message: str           # 通知消息
    post_id: Optional[str] = None
    reply_id: Optional[str] = None
    is_read: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "notification_id": self.notification_id,
            "recipient_id": self.recipient_id,
            "notification_type": self.notification_type,
            "post_id": self.post_id,
            "reply_id": self.reply_id,
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "message": self.message,
            "is_read": self.is_read,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ReplySummary':
        return cls(**data)


def generate_post_id() -> str:
    """生成帖子 ID"""
    return f"post_{uuid.uuid4().hex[:16]}"


def generate_reply_id() -> str:
    """生成回复 ID"""
    return f"reply_{uuid.uuid4().hex[:16]}"


def generate_topic_id(name: str) -> str:
    """生成话题 ID (基于名称的哈希)"""
    hash_val = hashlib.sha256(name.encode()).hexdigest()[:12]
    return f"topic_{hash_val}"


def compute_hash_chain(content: str, previous_hash: str = "") -> ContentHash:
    """计算内容哈希链"""
    timestamp = time.time()
    current_hash = hashlib.sha256(f"{previous_hash}{content}{timestamp}".encode()).hexdigest()
    return ContentHash(
        previous_hash=previous_hash,
        current_hash=current_hash,
        timestamp=timestamp
    )
