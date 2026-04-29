"""
LivingTreeAI Broadcast Network - 订阅制广播系统
================================================

三层订阅网络：
┌─────────────────────────────────────────────────────────────┐
│                    广播系统架构                               │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────┐│
│  │   内容层        │→ │   广播层         │→ │  索引层   ││
│  │ Content Types  │  │ Gossip + Flood  │  │ Dist Index││
│  │ (邮件/网站/帖子) │  │  (订阅制洪泛)    │  │ (倒排索引) ││
│  └─────────────────┘  └─────────────────┘  └───────────┘│
├─────────────────────────────────────────────────────────────┤
│                    反滥用层                                 │
│  (信誉评分 / 速率限制 / 垃圾过滤)                            │
└─────────────────────────────────────────────────────────────┘

模块：
- content_types.py    : 统一内容格式
- subscription_broadcast.py : 订阅制广播
- distributed_index.py : 分布式倒排索引
- anti_spam.py       : 反滥用系统
- email_system.py     : 邮件系统
- broadcast_manager.py : 广播管理器

Author: LivingTreeAI Community
License: Apache 2.0
"""

__version__ = "1.0.0"

from .content_types import (
    Content,
    ContentType,
    ContentScope,
    get_content_type,
)

from .subscription_broadcast import (
    SubscriptionBroadcast,
    SubscriptionType,
    BoardSubscription,
    AuthorSubscription,
    KeywordSubscription,
    get_subscription_broadcast,
)

from .distributed_index import (
    DistributedInvertedIndex,
    IndexEntry,
    SearchQuery,
    SearchResult,
    get_distributed_index,
)

from .anti_spam import (
    AntiSpamSystem,
    RateLimiter,
    ReputationSystem,
    SpamScore,
    get_anti_spam,
)

from .email_system import (
    EncryptedEmail,
    InboxManager,
    EmailAccount,
    get_email_system,
)

from .broadcast_manager import (
    BroadcastManager,
    BroadcastConfig,
    BroadcastStats,
    get_broadcast_manager,
)

__all__ = [
    # 版本
    "__version__",
    # 内容类型
    "Content",
    "ContentType",
    "ContentScope",
    "get_content_type",
    # 订阅广播
    "SubscriptionBroadcast",
    "SubscriptionType",
    "BoardSubscription",
    "AuthorSubscription",
    "KeywordSubscription",
    "get_subscription_broadcast",
    # 分布式索引
    "DistributedInvertedIndex",
    "IndexEntry",
    "SearchQuery",
    "SearchResult",
    "get_distributed_index",
    # 反滥用
    "AntiSpamSystem",
    "RateLimiter",
    "ReputationSystem",
    "SpamScore",
    "get_anti_spam",
    # 邮件
    "EncryptedEmail",
    "InboxManager",
    "EmailAccount",
    "get_email_system",
    # 管理器
    "BroadcastManager",
    "BroadcastConfig",
    "BroadcastStats",
    "get_broadcast_manager",
]