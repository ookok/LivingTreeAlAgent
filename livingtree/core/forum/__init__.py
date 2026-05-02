"""
去中心化论坛 - 核心模块

基于 P2P 穿透网络、ID 寻址、端到端加密的论坛协议层

参考: ActivityPub (联邦宇宙) / NNTP (新闻组) / SSB (Scuttlebutt)
"""

from .models import (
    # 枚举
    PostStatus,
    ReplyStatus,
    ContentType,
    VoteType,
    # 数据模型
    Author,
    ContentHash,
    Attachment,
    PostContent,
    SmartDraft,
    ForumPost,
    ForumReply,
    Topic,
    Subscription,
    Vote,
    ReplySummary,
    PostNotification,
    # 函数
    generate_post_id,
    generate_reply_id,
    generate_topic_id,
    compute_hash_chain,
)

from .forum_protocol import (
    MessageType,
    ProtocolMessage,
    SyncState,
    ForumProtocol,
    ForumProtocolHandler,
)

from .forum_storage import ForumStorage

from .smart_integration import (
    DiscussionQuality,
    SmartWritingIntegration,
    ArgumentPoint,
    DiscussionAnalysis,
)

from .forum_hub import (
    ForumHubConfig,
    ForumHub,
    get_forum_hub,
    get_forum_hub_async,
)

__all__ = [
    # 枚举
    "PostStatus",
    "ReplyStatus",
    "ContentType",
    "VoteType",
    "MessageType",
    "DiscussionQuality",

    # 数据模型
    "Author",
    "ContentHash",
    "Attachment",
    "PostContent",
    "SmartDraft",
    "ForumPost",
    "ForumReply",
    "Topic",
    "Subscription",
    "Vote",
    "ReplySummary",
    "PostNotification",
    "ArgumentPoint",
    "DiscussionAnalysis",

    # 函数
    "generate_post_id",
    "generate_reply_id",
    "generate_topic_id",
    "compute_hash_chain",

    # 协议
    "ProtocolMessage",
    "SyncState",
    "ForumProtocol",
    "ForumProtocolHandler",

    # 存储
    "ForumStorage",

    # 智能写作
    "SmartWritingIntegration",

    # 核心调度器
    "ForumHubConfig",
    "ForumHub",
    "get_forum_hub",
    "get_forum_hub_async",
]
