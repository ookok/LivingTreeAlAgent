"""
Unified Chat - 统一聊天核心模块

参考 Element/Discord/Telegram 的专业级聊天 UI 架构

主要组件:
- models: 统一消息模型 (所有消息类型统一接口)
- link_preview: 链接预览服务 (Telegram 式 og: 快照)
- status_monitor: 状态监控服务 (网络/节点/传输/通话)
- session_manager: 会话管理器 (私聊/群聊/消息存储)
- chat_hub: 核心调度器 (单例, 整合所有模块)

使用方式:
    from client.src.business.unified_chat import get_chat_hub

    hub = get_chat_hub()
    hub.set_my_identity(node_id, short_id, name)
    hub.add_ui_callback(my_callback)

    # 发送消息
    await hub.send_text_message(session_id, "Hello")

    # 发送文件
    await hub.send_file_message(session_id, "/path/to/file.jpg")

    # 获取状态栏信息
    status = hub.get_status_info()
"""

from .models import (
    # 枚举
    MessageType,
    MessageStatus,
    SessionType,
    OnlineStatus,
    ConnectionQuality,
    # 数据模型
    UnifiedMessage,
    ChatSession,
    PeerInfo,
    NetworkStatus,
    CallSession,
    LinkPreview,
    FileMeta,
    # 常量
    MESSAGE_TYPE_ICONS,
    STATUS_ICONS,
    MAX_MESSAGE_LENGTH,
    MAX_FILE_SIZE,
    CHUNK_SIZE,
)

from .link_preview import LinkPreviewService, get_link_preview_service
from .status_monitor import StatusMonitor, get_status_monitor
from .session_manager import SessionManager, get_session_manager, SearchScope, SearchResult
from .chat_hub import ChatHub, get_chat_hub

# 从 p2p_connector 导入 ChannelType (避免循环导入)
from ..p2p_connector.models import ChannelType

__all__ = [
    # 枚举
    "MessageType",
    "MessageStatus",
    "SessionType",
    "OnlineStatus",
    "ConnectionQuality",
    "ChannelType",
    # 数据模型
    "UnifiedMessage",
    "ChatSession",
    "PeerInfo",
    "NetworkStatus",
    "CallSession",
    "LinkPreview",
    "FileMeta",
    # 常量
    "MESSAGE_TYPE_ICONS",
    "STATUS_ICONS",
    "MAX_MESSAGE_LENGTH",
    "MAX_FILE_SIZE",
    "CHUNK_SIZE",
    # 服务
    "LinkPreviewService",
    "get_link_preview_service",
    "StatusMonitor",
    "get_status_monitor",
    "SessionManager",
    "get_session_manager",
    "SearchScope",
    "SearchResult",
    "ChatHub",
    "get_chat_hub",
]
