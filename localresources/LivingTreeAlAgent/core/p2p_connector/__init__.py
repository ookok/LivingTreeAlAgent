"""
P2P连接器 - 短ID寻址 + 多通道通信

实现:
- 8-12位纯数字短ID (user-friendly)
- ID寻址与连接 (目录服务)
- 多通道通信 (文本/文件/语音/视频/直播/邮件)
- 端到端加密
"""

from .models import (
    ShortID,
    NodeProfile,
    P2PConnection,
    ChannelSession,
    Contact,
    ChannelType,
    ConnectionStatus,
    PeerStatus,
    DEFAULT_DIRECTORY_SERVERS,
    DEFAULT_RELAY_SERVERS
)

from .short_id import ShortIDGenerator
from .directory_service import DirectoryService
from .multi_channel_manager import MultiChannelManager, Message as ChannelMessage
from .connector_hub import ConnectorHub, get_connector_hub, get_connector_hub_sync

__all__ = [
    # 模型
    "ShortID",
    "NodeProfile",
    "P2PConnection",
    "ChannelSession",
    "Contact",
    "ChannelType",
    "ConnectionStatus",
    "PeerStatus",
    "Message",
    "DEFAULT_DIRECTORY_SERVERS",
    "DEFAULT_RELAY_SERVERS",
    # 组件
    "ShortIDGenerator",
    "DirectoryService",
    "MultiChannelManager",
    "ChannelMessage",
    # 核心
    "ConnectorHub",
    "get_connector_hub",
    "get_connector_hub_sync",
]
