"""
P2P连接器数据模型

定义节点、连接、会话等核心数据结构
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


class ConnectionStatus(Enum):
    """连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    ERROR = "error"


class ChannelType(Enum):
    """通道类型"""
    TEXT = "text"              # 富文本/链接
    FILE = "file"              # 文件传输
    VOICE = "voice"            # 语音通话
    VIDEO = "video"            # 视频通话
    LIVE = "live"             # 直播流
    EMAIL = "email"            # 邮件推送


class PeerStatus(Enum):
    """节点状态"""
    OFFLINE = "offline"
    ONLINE = "online"
    AWAY = "away"
    BUSY = "busy"


@dataclass
class ShortID:
    """
    短ID - 用于用户间互报的ID
    
    8-12位纯数字，易记易输入
    """
    code: str                  # 纯数字ID
    node_id: str              # 对应的完整节点ID
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    
    @property
    def display(self) -> str:
        """显示格式"""
        return self.code
    
    @property
    def is_valid(self) -> bool:
        """是否有效"""
        return len(self.code) >= 8 and self.code.isdigit()
    
    def __str__(self) -> str:
        return self.code
    
    def __hash__(self) -> int:
        return hash(self.code)
    
    def __eq__(self, other) -> bool:
        if isinstance(other, ShortID):
            return self.code == other.code
        return False


@dataclass
class NodeProfile:
    """
    节点档案
    
    存储在目录服务中的节点信息
    """
    node_id: str              # 完整节点ID (SHA256)
    short_id: str             # 短ID (8-10位数字)
    
    # 基本信息
    display_name: str = ""    # 显示名称
    avatar: Optional[str] = None  # 头像URL/Base64
    
    # 网络信息
    public_ip: Optional[str] = None
    public_port: Optional[int] = None
    nat_type: int = 0         # NAT类型
    
    # 连接信息
    relay_hosts: List[str] = field(default_factory=list)  # 中继服务器地址
    stun_hosts: List[str] = field(default_factory=list)     # STUN服务器地址
    
    # 公钥 (用于加密)
    public_key: Optional[str] = None
    
    # 状态
    status: PeerStatus = PeerStatus.OFFLINE
    last_seen: float = field(default_factory=time.time)
    
    # 能力
    capabilities: List[str] = field(default_factory=list)
    # 支持: text, file, voice, video, live, email
    
    # 元数据
    tags: List[str] = field(default_factory=list)  # 标签/分组
    bio: str = ""           # 简介
    
    @property
    def is_online(self) -> bool:
        """是否在线"""
        return self.status == PeerStatus.ONLINE
    
    @property
    def connection_priority(self) -> List[str]:
        """连接优先级"""
        # 1. 公网直连
        # 2. P2P穿透
        # 3. 中继转发
        return ["direct", "p2p", "relay"]
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "short_id": self.short_id,
            "display_name": self.display_name,
            "avatar": self.avatar,
            "public_ip": self.public_ip,
            "public_port": self.public_port,
            "nat_type": self.nat_type,
            "relay_hosts": self.relay_hosts,
            "public_key": self.public_key,
            "status": self.status.value,
            "last_seen": self.last_seen,
            "capabilities": self.capabilities,
            "tags": self.tags,
            "bio": self.bio
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "NodeProfile":
        """从字典创建"""
        return cls(
            node_id=data["node_id"],
            short_id=data["short_id"],
            display_name=data.get("display_name", ""),
            avatar=data.get("avatar"),
            public_ip=data.get("public_ip"),
            public_port=data.get("public_port"),
            nat_type=data.get("nat_type", 0),
            relay_hosts=data.get("relay_hosts", []),
            public_key=data.get("public_key"),
            status=PeerStatus(data.get("status", "offline")),
            last_seen=data.get("last_seen", time.time()),
            capabilities=data.get("capabilities", []),
            tags=data.get("tags", []),
            bio=data.get("bio", "")
        )


@dataclass
class P2PConnection:
    """
    P2P连接
    
    两个节点之间的连接会话
    """
    connection_id: str        # 连接ID
    peer_node_id: str        # 对端节点ID
    peer_short_id: str       # 对端短ID
    
    # 通道
    active_channels: List[ChannelType] = field(default_factory=list)
    
    # 状态
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    connected_at: Optional[float] = None
    last_activity: float = field(default_factory=time.time)
    
    # 加密
    shared_key: Optional[bytes] = None  # 共享密钥
    
    # 统计数据
    bytes_sent: int = 0
    bytes_received: int = 0
    latency: float = 0  # 毫秒
    
    # 底层连接信息
    local_addr: Optional[str] = None
    peer_addr: Optional[str] = None
    via_relay: bool = False
    relay_server: Optional[str] = None
    
    @property
    def duration(self) -> float:
        """连接时长"""
        if self.connected_at:
            return time.time() - self.connected_at
        return 0
    
    @property
    def is_active(self) -> bool:
        """是否活跃"""
        return self.status == ConnectionStatus.CONNECTED


@dataclass
class ChannelSession:
    """
    通道会话
    
    特定类型的通信会话
    """
    session_id: str
    connection_id: str
    channel_type: ChannelType
    
    # 状态
    status: str = "pending"  # pending, active, closed
    created_at: float = field(default_factory=time.time)
    
    # 通道特定数据
    file_path: Optional[str] = None   # 文件传输路径
    file_size: int = 0              # 文件大小
    file_progress: float = 0         # 传输进度
    
    # 音视频
    codec: Optional[str] = None
    resolution: Optional[str] = None
    bitrate: int = 0
    
    # 直播
    viewer_count: int = 0
    stream_key: Optional[str] = None
    
    # 消息
    message_count: int = 0
    
    @property
    def channel_icon(self) -> str:
        """通道图标"""
        return {
            ChannelType.TEXT: "💬",
            ChannelType.FILE: "📎",
            ChannelType.VOICE: "🎙️",
            ChannelType.VIDEO: "📹",
            ChannelType.LIVE: "📺",
            ChannelType.EMAIL: "📧"
        }.get(self.channel_type, "❓")


@dataclass
class Contact:
    """
    联系人
    
    保存的好友/联系人
    """
    short_id: str
    node_id: str
    display_name: str = ""
    avatar: Optional[str] = None
    
    # 关系
    is_friend: bool = False
    is_blocked: bool = False
    
    # 统计
    total_messages: int = 0
    total_files: int = 0
    last_contact: Optional[float] = None
    
    # 标签
    tags: List[str] = field(default_factory=list)
    
    # 备注
    notes: str = ""


# 目录服务器配置
DEFAULT_DIRECTORY_SERVERS = [
    "139.199.124.242:8890",  # 默认中继服务器
]

# 中继服务器配置
DEFAULT_RELAY_SERVERS = [
    ("139.199.124.242", 8888),
]
