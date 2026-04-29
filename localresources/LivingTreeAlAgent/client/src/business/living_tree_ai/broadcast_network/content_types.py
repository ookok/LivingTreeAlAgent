"""
Content Types - 统一内容格式
=============================

支持：邮件、网站、帖子 三种内容类型

Author: LivingTreeAI Community
"""

import hashlib
import time
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum


class ContentType(Enum):
    """内容类型"""
    EMAIL = "email"
    WEBSITE = "website"
    POST = "post"


class ContentScope(Enum):
    """广播范围"""
    SUBSCRIBERS = "subscribers"  # 只发给订阅者
    BOARD = "board"            # 发给板块
    RECIPIENTS = "recipients"  # 发给特定收件人（邮件）
    PUBLIC = "public"         # 公开广播
    FOLLOWERS = "followers"    # 只发给关注者


@dataclass
class Content:
    """
    统一内容格式

    支持三种类型：
    - email: 邮件（需要收件人）
    - website: 网站（需要URL）
    - post: 帖子（需要板块）
    """

    # 基本字段
    content_id: str = ""           # 内容哈希
    type: ContentType = ContentType.POST  # 内容类型
    author: str = ""              # 作者节点ID
    title: str = ""               # 标题/主题
    body: str = ""                # 正文内容
    attachments: List[Dict] = field(default_factory=list)  # 附件
    metadata: Dict = field(default_factory=dict)  # 元数据
    timestamp: float = field(default_factory=time.time)  # 发布时间
    signature: str = ""           # 作者签名

    # 类型特定字段
    recipients: Optional[List[str]] = None  # 邮件收件人
    url: Optional[str] = None              # 网站URL
    board: Optional[str] = None            # 帖子板块

    # 广播控制
    scope: ContentScope = ContentScope.SUBSCRIBERS  # 广播范围
    tags: List[str] = field(default_factory=list)  # 标签

    # 状态
    views: int = 0              # 阅读数
    replies: int = 0           # 回复数
    forwarded: int = 0         # 转发数

    def __post_init__(self):
        """后处理"""
        if isinstance(self.type, str):
            self.type = ContentType(self.type)
        if isinstance(self.scope, str):
            self.scope = ContentScope(self.scope)

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "content_id": self.content_id,
            "type": self.type.value,
            "author": self.author,
            "title": self.title,
            "body": self.body,
            "attachments": self.attachments,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "recipients": self.recipients,
            "url": self.url,
            "board": self.board,
            "scope": self.scope.value,
            "tags": self.tags,
            "views": self.views,
            "replies": self.replies,
            "forwarded": self.forwarded,
        }
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Content":
        """从字典创建"""
        type_str = data.get("type", "post")
        if isinstance(type_str, str):
            type_enum = ContentType(type_str)
        else:
            type_enum = type_str

        scope_str = data.get("scope", "subscribers")
        if isinstance(scope_str, str):
            scope_enum = ContentScope(scope_str)
        else:
            scope_enum = scope_str

        return cls(
            content_id=data.get("content_id", ""),
            type=type_enum,
            author=data.get("author", ""),
            title=data.get("title", ""),
            body=data.get("body", ""),
            attachments=data.get("attachments", []),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", time.time()),
            signature=data.get("signature", ""),
            recipients=data.get("recipients"),
            url=data.get("url"),
            board=data.get("board"),
            scope=scope_enum,
            tags=data.get("tags", []),
            views=data.get("views", 0),
            replies=data.get("replies", 0),
            forwarded=data.get("forwarded", 0),
        )

    def compute_id(self) -> str:
        """计算内容ID（内容哈希）"""
        data = {
            "type": self.type.value,
            "author": self.author,
            "title": self.title,
            "body": self.body,
            "timestamp": self.timestamp,
        }
        content_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()[:32]

    def is_valid(self) -> bool:
        """检查内容是否有效"""
        if not self.author:
            return False
        if not self.title and not self.body:
            return False
        if self.type == ContentType.EMAIL and not self.recipients:
            return False
        if self.type == ContentType.WEBSITE and not self.url:
            return False
        if self.type == ContentType.POST and not self.board:
            return False
        return True


class Email(Content):
    """邮件内容"""

    def __init__(
        self,
        author: str,
        recipients: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        priority: str = "normal",
        attachments: Optional[List[Dict]] = None,
        metadata: Optional[Dict] = None,
    ):
        super().__init__(
            type=ContentType.EMAIL,
            author=author,
            recipients=recipients,
            title=subject,
            body=body,
            attachments=attachments or [],
            metadata=metadata or {},
            scope=ContentScope.RECIPIENTS,
        )
        self.cc = cc
        self.bcc = bcc
        self.metadata["priority"] = priority
        self.metadata["cc"] = cc or []
        self.metadata["bcc"] = bcc or []


class Website(Content):
    """网站内容"""

    def __init__(
        self,
        author: str,
        url: str,
        title: str,
        body: str,
        category: str = "general",
        access: str = "public",
        attachments: Optional[List[Dict]] = None,
        metadata: Optional[Dict] = None,
    ):
        super().__init__(
            type=ContentType.WEBSITE,
            author=author,
            url=url,
            title=title,
            body=body,
            attachments=attachments or [],
            metadata=metadata or {},
            scope=ContentScope.PUBLIC,
        )
        self.metadata["category"] = category
        self.metadata["access"] = access


class Post(Content):
    """帖子内容"""

    def __init__(
        self,
        author: str,
        board: str,
        title: str,
        body: str,
        tags: Optional[List[str]] = None,
        attachments: Optional[List[Dict]] = None,
        metadata: Optional[Dict] = None,
    ):
        super().__init__(
            type=ContentType.POST,
            author=author,
            board=board,
            title=title,
            body=body,
            attachments=attachments or [],
            metadata=metadata or {},
            scope=ContentScope.BOARD,
            tags=tags or [],
        )


def get_content_type(type_str: str) -> ContentType:
    """获取内容类型枚举"""
    return ContentType(type_str)


# ========== 便捷构造函数 ==========

def create_email(
    author: str,
    recipients: List[str],
    subject: str,
    body: str,
    **kwargs
) -> Email:
    """创建邮件"""
    return Email(author, recipients, subject, body, **kwargs)


def create_website(
    author: str,
    url: str,
    title: str,
    body: str,
    **kwargs
) -> Website:
    """创建网站"""
    return Website(author, url, title, body, **kwargs)


def create_post(
    author: str,
    board: str,
    title: str,
    body: str,
    **kwargs
) -> Post:
    """创建帖子"""
    return Post(author, board, title, body, **kwargs)