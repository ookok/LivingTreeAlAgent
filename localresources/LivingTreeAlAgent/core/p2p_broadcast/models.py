"""
广播发现与P2P通信系统 - 数据模型

定义系统所需的全部数据结构和枚举类型
"""

from __future__ import annotations

import uuid
import time
import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum


# ============= 常量定义 =============

# 协议版本
PROTOCOL_VERSION = "2.0.0"

# 默认端口
BROADCAST_PORT = 45678  # UDP广播端口
CHAT_PORT = 45679       # TCP聊天端口
RELAY_PORT = 45680      # 中继服务端口

# 超时设置
BROADCAST_INTERVAL = 5      # 广播间隔（秒）
DEVICE_TIMEOUT = 30         # 设备超时（秒）
HEARTBEAT_INTERVAL = 10     # 心跳间隔（秒）
CONNECTION_TIMEOUT = 30     # 连接超时（秒）

# 能力标识
CAPABILITY_TEXT = "text"
CAPABILITY_FILE = "file"
CAPABILITY_AUDIO = "audio"
CAPABILITY_VIDEO = "video"
CAPABILITY_SCREEN = "screen"
CAPABILITY_WHITEBOARD = "whiteboard"

# ============= 枚举定义 =============


class MessageType(Enum):
    """消息类型"""
    # 发现相关
    DISCOVERY = "discovery"           # 设备发现广播
    DISCOVERY_ACK = "discovery_ack"  # 发现响应
    BYE = "bye"                       # 离开通知
    HEARTBEAT = "heartbeat"           # 心跳包
    
    # 聊天相关
    TEXT = "text"                     # 文本消息
    FILE_REQUEST = "file_request"    # 文件传输请求
    FILE_DATA = "file_data"           # 文件数据
    FILE_COMPLETE = "file_complete"  # 文件传输完成
    FILE_CANCEL = "file_cancel"      # 文件传输取消
    
    # 音视频相关
    AUDIO = "audio"                  # 音频数据
    VIDEO = "video"                  # 视频数据
    CALL_REQUEST = "call_request"    # 通话请求
    CALL_ACCEPT = "call_accept"      # 通话接受
    CALL_REJECT = "call_reject"      # 通话拒绝
    CALL_END = "call_end"            # 通话结束
    
    # 好友相关
    FRIEND_REQUEST = "friend_request"    # 好友请求
    FRIEND_RESPONSE = "friend_response" # 好友响应
    FRIEND_REMOVED = "friend_removed"   # 好友删除
    STATUS_UPDATE = "status_update"     # 状态更新
    
    # 控制相关
    ACK = "ack"                      # 确认消息
    PING = "ping"                    # ping
    PONG = "pong"                    # pong
    ERROR = "error"                  # 错误消息


class DeviceStatus(Enum):
    """设备状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    AWAY = "away"
    BUSY = "busy"
    DND = "dnd"  # Do Not Disturb


class ConnectionType(Enum):
    """连接类型"""
    DIRECT_LAN = "direct_lan"        # 局域网直连
    DIRECT_WAN = "direct_wan"        # 公网直连
    STUN = "stun"                   # STUN穿透
    TURN = "turn"                   # TURN中继
    RELAY = "relay"                 # 中继服务器


class MessageStatus(Enum):
    """消息状态"""
    PENDING = "pending"      # 待发送
    SENDING = "sending"      # 发送中
    SENT = "sent"           # 已发送
    DELIVERED = "delivered" # 已送达
    READ = "read"           # 已读
    FAILED = "failed"       # 发送失败


class BroadcastCategory(Enum):
    """广播分类"""
    GENERAL = "general"              # 通用广播
    KNOWLEDGE_SYNC = "knowledge-sync"  # 知识同步
    FILE_SHARE = "file-share"        # 文件分享
    MEETING = "meeting"              # 会议邀请
    QUESTION = "question"           # 问题求助


class ResponseType(Enum):
    """广播响应类型"""
    CONNECT = "connect"              # 连接请求
    REPLY = "reply"                 # 回复消息
    IGNORE = "ignore"               # 忽略


# ============= 数据类定义 =============


@dataclass
class DeviceInfo:
    """设备信息"""
    device_id: str
    device_name: str
    user_id: str
    user_name: str
    local_ip: str = ""
    public_ip: str = ""
    port: int = CHAT_PORT
    nat_type: str = "unknown"
    capabilities: List[str] = field(default_factory=lambda: [CAPABILITY_TEXT, CAPABILITY_FILE])
    avatar: str = ""
    status: DeviceStatus = DeviceStatus.ONLINE
    last_seen: float = field(default_factory=time.time)
    latency: float = 0.0  # 延迟（毫秒）
    is_friend: bool = False
    relay_server: str = ""
    
    def is_online(self) -> bool:
        """检查是否在线"""
        return time.time() - self.last_seen < DEVICE_TIMEOUT
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "local_ip": self.local_ip,
            "public_ip": self.public_ip,
            "port": self.port,
            "nat_type": self.nat_type,
            "capabilities": self.capabilities,
            "avatar": self.avatar,
            "status": self.status.value,
            "last_seen": self.last_seen,
            "latency": self.latency,
            "is_friend": self.is_friend,
            "relay_server": self.relay_server,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceInfo":
        """从字典创建"""
        return cls(
            device_id=data.get("device_id", ""),
            device_name=data.get("device_name", ""),
            user_id=data.get("user_id", ""),
            user_name=data.get("user_name", ""),
            local_ip=data.get("local_ip", ""),
            public_ip=data.get("public_ip", ""),
            port=data.get("port", CHAT_PORT),
            nat_type=data.get("nat_type", "unknown"),
            capabilities=data.get("capabilities", [CAPABILITY_TEXT, CAPABILITY_FILE]),
            avatar=data.get("avatar", ""),
            status=DeviceStatus(data.get("status", "online")),
            last_seen=data.get("last_seen", time.time()),
            latency=data.get("latency", 0.0),
            is_friend=data.get("is_friend", False),
            relay_server=data.get("relay_server", ""),
        )


@dataclass
class ChatMessage:
    """聊天消息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    msg_type: MessageType = MessageType.TEXT
    sender_id: str = ""
    sender_name: str = ""
    receiver_id: str = ""
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    status: MessageStatus = MessageStatus.PENDING
    read: bool = False
    is_ai: bool = False  # AI自动生成
    
    # 文件传输相关
    file_name: str = ""
    file_size: int = 0
    file_hash: str = ""
    chunk_index: int = 0
    total_chunks: int = 0
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "msg_type": self.msg_type.value if isinstance(self.msg_type, MessageType) else self.msg_type,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "receiver_id": self.receiver_id,
            "content": self.content,
            "timestamp": self.timestamp,
            "status": self.status.value if isinstance(self.status, MessageStatus) else self.status,
            "read": self.read,
            "is_ai": self.is_ai,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_hash": self.file_hash,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        """从字典创建"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            msg_type=MessageType(data.get("msg_type", "text")),
            sender_id=data.get("sender_id", ""),
            sender_name=data.get("sender_name", ""),
            receiver_id=data.get("receiver_id", ""),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", time.time()),
            status=MessageStatus(data.get("status", "pending")),
            read=data.get("read", False),
            is_ai=data.get("is_ai", False),
            file_name=data.get("file_name", ""),
            file_size=data.get("file_size", 0),
            file_hash=data.get("file_hash", ""),
            chunk_index=data.get("chunk_index", 0),
            total_chunks=data.get("total_chunks", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class BroadcastMessage:
    """广播消息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: DeviceInfo = None
    content: str = ""
    category: BroadcastCategory = BroadcastCategory.GENERAL
    keywords: List[str] = field(default_factory=list)
    response_type: ResponseType = ResponseType.REPLY
    timestamp: float = field(default_factory=time.time)
    expires_at: float = 0.0  # 过期时间
    
    def __post_init__(self):
        if self.expires_at == 0.0:
            self.expires_at = self.timestamp + 60  # 默认60秒过期
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "sender": self.sender.to_dict() if self.sender else {},
            "content": self.content,
            "category": self.category.value if isinstance(self.category, BroadcastCategory) else self.category,
            "keywords": self.keywords,
            "response_type": self.response_type.value if isinstance(self.response_type, ResponseType) else self.response_type,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BroadcastMessage":
        """从字典创建"""
        sender_data = data.get("sender", {})
        sender = DeviceInfo.from_dict(sender_data) if sender_data else None
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            sender=sender,
            content=data.get("content", ""),
            category=BroadcastCategory(data.get("category", "general")),
            keywords=data.get("keywords", []),
            response_type=ResponseType(data.get("response_type", "reply")),
            timestamp=data.get("timestamp", time.time()),
            expires_at=data.get("expires_at", 0.0),
        )


@dataclass
class FriendRequest:
    """好友请求"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_user: str = ""
    from_name: str = ""
    to_user: str = ""
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    status: str = "pending"  # pending, accepted, rejected
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "from_user": self.from_user,
            "from_name": self.from_name,
            "to_user": self.to_user,
            "message": self.message,
            "timestamp": self.timestamp,
            "status": self.status,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FriendRequest":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            from_user=data.get("from_user", ""),
            from_name=data.get("from_name", ""),
            to_user=data.get("to_user", ""),
            message=data.get("message", ""),
            timestamp=data.get("timestamp", time.time()),
            status=data.get("status", "pending"),
        )


@dataclass
class Conversation:
    """会话"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    peer_id: str = ""
    peer_name: str = ""
    is_group: bool = False
    is_temporary: bool = False  # 临时会话
    messages: List[ChatMessage] = field(default_factory=list)
    last_message_time: float = 0.0
    unread_count: int = 0
    created_at: float = field(default_factory=time.time)
    
    def add_message(self, message: ChatMessage):
        """添加消息"""
        self.messages.append(message)
        self.last_message_time = message.timestamp
        if not message.read and message.receiver_id:  # 收到消息
            self.unread_count += 1
    
    def mark_read(self):
        """标记已读"""
        self.unread_count = 0
        for msg in self.messages:
            msg.read = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "peer_id": self.peer_id,
            "peer_name": self.peer_name,
            "is_group": self.is_group,
            "is_temporary": self.is_temporary,
            "last_message_time": self.last_message_time,
            "unread_count": self.unread_count,
            "created_at": self.created_at,
        }


@dataclass
class NetworkAddress:
    """网络地址"""
    ip: str
    port: int
    nat_type: str = "unknown"
    priority: int = 100  # 优先级，越小越优先
    
    def __str__(self) -> str:
        return f"{self.ip}:{self.port}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ip": self.ip,
            "port": self.port,
            "nat_type": self.nat_type,
            "priority": self.priority,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NetworkAddress":
        return cls(
            ip=data.get("ip", ""),
            port=data.get("port", 0),
            nat_type=data.get("nat_type", "unknown"),
            priority=data.get("priority", 100),
        )


@dataclass
class PeerConnection:
    """对等连接"""
    peer_id: str
    connection_type: ConnectionType
    local_addr: Optional[NetworkAddress] = None
    public_addr: Optional[NetworkAddress] = None
    is_connected: bool = False
    is_encrypted: bool = True
    latency: float = 0.0
    last_active: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "peer_id": self.peer_id,
            "connection_type": self.connection_type.value if isinstance(self.connection_type, ConnectionType) else self.connection_type,
            "local_addr": self.local_addr.to_dict() if self.local_addr else None,
            "public_addr": self.public_addr.to_dict() if self.public_addr else None,
            "is_connected": self.is_connected,
            "is_encrypted": self.is_encrypted,
            "latency": self.latency,
            "last_active": self.last_active,
        }


@dataclass
class SystemConfig:
    """系统配置"""
    # 用户信息
    user_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_name: str = "Hermes User"
    device_name: str = "My Device"
    
    # 网络配置
    broadcast_port: int = BROADCAST_PORT
    chat_port: int = CHAT_PORT
    relay_server: str = ""
    stun_server: str = "stun.l.google.com"
    
    # 发现配置
    broadcast_enabled: bool = True
    auto_discovery: bool = True
    broadcast_interval: int = BROADCAST_INTERVAL
    discovery_range: str = "lan"  # lan, wan, all
    
    # 安全配置
    encryption_enabled: bool = True
    allow_temp_chat: bool = True
    allow_friend_request: bool = True
    privacy_mode: str = "normal"  # open, normal, strict
    
    # 通知配置
    notify_enabled: bool = True
    notify_sound: bool = True
    show_online_status: bool = True
    
    # 存储配置
    message_retention_days: int = 30
    auto_backup: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "device_name": self.device_name,
            "broadcast_port": self.broadcast_port,
            "chat_port": self.chat_port,
            "relay_server": self.relay_server,
            "stun_server": self.stun_server,
            "broadcast_enabled": self.broadcast_enabled,
            "auto_discovery": self.auto_discovery,
            "broadcast_interval": self.broadcast_interval,
            "discovery_range": self.discovery_range,
            "encryption_enabled": self.encryption_enabled,
            "allow_temp_chat": self.allow_temp_chat,
            "allow_friend_request": self.allow_friend_request,
            "privacy_mode": self.privacy_mode,
            "notify_enabled": self.notify_enabled,
            "notify_sound": self.notify_sound,
            "show_online_status": self.show_online_status,
            "message_retention_days": self.message_retention_days,
            "auto_backup": self.auto_backup,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ============= 模块导出 =============

__all__ = [
    # 常量
    "PROTOCOL_VERSION",
    "BROADCAST_PORT",
    "CHAT_PORT",
    "RELAY_PORT",
    "BROADCAST_INTERVAL",
    "DEVICE_TIMEOUT",
    "HEARTBEAT_INTERVAL",
    "CONNECTION_TIMEOUT",
    "CAPABILITY_TEXT",
    "CAPABILITY_FILE",
    "CAPABILITY_AUDIO",
    "CAPABILITY_VIDEO",
    "CAPABILITY_SCREEN",
    "CAPABILITY_WHITEBOARD",
    
    # 枚举
    "MessageType",
    "DeviceStatus",
    "ConnectionType",
    "MessageStatus",
    "BroadcastCategory",
    "ResponseType",
    
    # 数据类
    "DeviceInfo",
    "ChatMessage",
    "BroadcastMessage",
    "FriendRequest",
    "Conversation",
    "NetworkAddress",
    "PeerConnection",
    "SystemConfig",
]
