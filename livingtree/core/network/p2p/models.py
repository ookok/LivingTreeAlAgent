"""
LivingTree P2P 网络统一模型
============================

合并 p2p_broadcast、p2p_connector、p2p_knowledge 的数据模型，
消除三套独立定义中的重复和冲突。

统一原则：
- 单向数据模型：每个概念只有一个权威定义
- 枚举标准化：状态、类型、策略的枚举统一
- 可序列化：所有模型支持 JSON 序列化/反序列化
- 类型安全：使用 dataclass + 类型注解

Author: LivingTreeAI Team
Version: 1.0.0 (统一版)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import json
import socket


# ============================================================================
# 枚举定义
# ============================================================================

class PeerStatus(str, Enum):
    """节点状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    AWAY = "away"
    BUSY = "busy"
    UNKNOWN = "unknown"


class ConnectionType(str, Enum):
    """连接类型"""
    DIRECT = "direct"            # 直连（同局域网/公网IP）
    STUN_HOLE = "stun_hole"     # STUN 打洞
    TURN_RELAY = "turn_relay"   # TURN 中继
    RELAY = "relay"             # 应用层中继
    OFFLINE = "offline"         # 离线（队列投递）


class MessageType(str, Enum):
    """消息类型"""
    TEXT = "text"
    FILE = "file"
    VOICE = "voice"
    VIDEO = "video"
    SYSTEM = "system"
    SYNC = "sync"              # 知识同步
    HEARTBEAT = "heartbeat"
    DISCOVERY = "discovery"


class NATType(str, Enum):
    """NAT 类型"""
    OPEN = "open"                    # 公网 IP / 无 NAT
    FULL_CONE = "full_cone"
    RESTRICTED_CONE = "restricted_cone"
    PORT_RESTRICTED = "port_restricted"
    SYMMETRIC = "symmetric"
    UNKNOWN = "unknown"


class TrustLevel(str, Enum):
    """信任等级"""
    SELF = "self"                # 自身
    FRIEND = "friend"            # 好友
    KNOWN = "known"              # 已知节点
    VERIFIED = "verified"        # 已验证
    UNKNOWN = "unknown"          # 未知
    BLOCKED = "blocked"          # 已屏蔽


class DiscoveryMethod(str, Enum):
    """发现方式"""
    BROADCAST = "broadcast"      # UDP 局域网广播
    DHT = "dht"                  # 分布式哈希表
    DIRECTORY = "directory"      # 目录服务
    BOOTSTRAP = "bootstrap"      # 引导节点
    MANUAL = "manual"            # 手动添加


# ============================================================================
# 核心数据模型
# ============================================================================

@dataclass
class NetworkAddress:
    """网络地址（统一表示）"""
    host: str
    port: int

    def to_tuple(self) -> tuple:
        return (self.host, self.port)

    @classmethod
    def from_tuple(cls, addr: tuple) -> "NetworkAddress":
        return cls(host=addr[0], port=addr[1])

    @classmethod
    def localhost(cls, port: int = 0) -> "NetworkAddress":
        return cls(host="127.0.0.1", port=port)

    def __str__(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass
class PeerIdentity:
    """节点身份"""
    node_id: str                                                # SHA256 哈希（全局唯一）
    short_id: str = ""                                          # 短 ID（8-12 位数字，便于人类识别）
    display_name: str = ""                                      # 显示名称
    device_name: str = socket.gethostname()                     # 设备名

    @classmethod
    def generate(cls, display_name: str = "") -> "PeerIdentity":
        """生成新的节点身份"""
        raw = f"{display_name}:{socket.gethostname()}:{datetime.now().isoformat()}"
        node_id = hashlib.sha256(raw.encode()).hexdigest()
        short_id = str(int(node_id[:12], 16) % 10_000_000_000).zfill(10)
        return cls(
            node_id=node_id,
            short_id=short_id,
            display_name=display_name,
        )


@dataclass
class PeerInfo:
    """节点完整信息"""
    identity: PeerIdentity
    local_addr: NetworkAddress = field(default_factory=lambda: NetworkAddress("0.0.0.0", 0))
    public_addr: Optional[NetworkAddress] = None
    nat_type: NATType = NATType.UNKNOWN
    status: PeerStatus = PeerStatus.UNKNOWN
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    capabilities: List[str] = field(default_factory=list)      # ["relay", "storage", "compute", ...]
    tags: List[str] = field(default_factory=list)
    last_seen: Optional[datetime] = None
    connection_type: ConnectionType = ConnectionType.DIRECT
    latency_ms: float = 0.0
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（用于网络传输）"""
        return {
            "node_id": self.identity.node_id,
            "short_id": self.identity.short_id,
            "display_name": self.identity.display_name,
            "device_name": self.identity.device_name,
            "local_host": self.local_addr.host,
            "local_port": self.local_addr.port,
            "public_host": self.public_addr.host if self.public_addr else "",
            "public_port": self.public_addr.port if self.public_addr else 0,
            "nat_type": self.nat_type.value,
            "status": self.status.value,
            "trust_level": self.trust_level.value,
            "capabilities": self.capabilities,
            "tags": self.tags,
            "last_seen": self.last_seen.isoformat() if self.last_seen else "",
            "connection_type": self.connection_type.value,
            "latency_ms": self.latency_ms,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PeerInfo":
        """从字典反序列化"""
        identity = PeerIdentity(
            node_id=data.get("node_id", ""),
            short_id=data.get("short_id", ""),
            display_name=data.get("display_name", ""),
            device_name=data.get("device_name", ""),
        )
        last_seen = None
        if data.get("last_seen"):
            try:
                last_seen = datetime.fromisoformat(data["last_seen"])
            except (ValueError, TypeError):
                pass
        return cls(
            identity=identity,
            local_addr=NetworkAddress(data.get("local_host", "0.0.0.0"), data.get("local_port", 0)),
            public_addr=(
                NetworkAddress(data["public_host"], data["public_port"])
                if data.get("public_host")
                else None
            ),
            nat_type=NATType(data.get("nat_type", "unknown")),
            status=PeerStatus(data.get("status", "unknown")),
            trust_level=TrustLevel(data.get("trust_level", "unknown")),
            capabilities=data.get("capabilities", []),
            tags=data.get("tags", []),
            last_seen=last_seen,
            connection_type=ConnectionType(data.get("connection_type", "direct")),
            latency_ms=data.get("latency_ms", 0.0),
            version=data.get("version", "1.0.0"),
        )

    def is_reachable(self) -> bool:
        """判断节点是否可达"""
        return self.status in (PeerStatus.ONLINE, PeerStatus.AWAY, PeerStatus.BUSY)

    def is_trusted(self) -> bool:
        """判断是否可信"""
        return self.trust_level in (TrustLevel.SELF, TrustLevel.FRIEND, TrustLevel.VERIFIED)


@dataclass
class P2PMessage:
    """统一 P2P 消息"""
    msg_id: str = ""
    msg_type: MessageType = MessageType.TEXT
    sender_id: str = ""
    recipient_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    ttl: int = 10                                           # 剩余跳数
    priority: int = 0                                       # 优先级 (0=normal, 1=high, 2=urgent)

    @classmethod
    def create(
        cls,
        msg_type: MessageType,
        sender_id: str,
        recipient_id: str,
        payload: Dict[str, Any],
        priority: int = 0,
    ) -> "P2PMessage":
        """创建新消息"""
        raw = f"{sender_id}:{recipient_id}:{datetime.now().isoformat()}:{json.dumps(payload, sort_keys=True)}"
        msg_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return cls(
            msg_id=msg_id,
            msg_type=msg_type,
            sender_id=sender_id,
            recipient_id=recipient_id,
            payload=payload,
            priority=priority,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.value,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "ttl": self.ttl,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "P2PMessage":
        ts = data.get("timestamp", "")
        try:
            timestamp = datetime.fromisoformat(ts) if ts else datetime.now()
        except (ValueError, TypeError):
            timestamp = datetime.now()
        return cls(
            msg_id=data.get("msg_id", ""),
            msg_type=MessageType(data.get("msg_type", "text")),
            sender_id=data.get("sender_id", ""),
            recipient_id=data.get("recipient_id", ""),
            payload=data.get("payload", {}),
            timestamp=timestamp,
            ttl=data.get("ttl", 10),
            priority=data.get("priority", 0),
        )


@dataclass
class ConnectionConfig:
    """连接配置"""
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    heartbeat_interval: float = 10.0
    max_retries: int = 3
    retry_backoff: float = 2.0   # 指数退避基数
    max_message_size: int = 10 * 1024 * 1024  # 10MB

    # NAT 穿透
    stun_servers: List[NetworkAddress] = field(default_factory=lambda: [
        NetworkAddress("stun.l.google.com", 19302),
        NetworkAddress("stun1.l.google.com", 19302),
    ])
    turn_servers: List[NetworkAddress] = field(default_factory=list)

    # 中继
    relay_hosts: List[NetworkAddress] = field(default_factory=list)

    # 发现
    broadcast_port: int = 45678
    broadcast_interval: float = 30.0
    dht_bucket_size: int = 20


# ============================================================================
# 节点路由表条目
# ============================================================================

@dataclass
class RoutingEntry:
    """DHT 风格的路由表条目"""
    peer_id: str
    address: NetworkAddress
    last_response: datetime = field(default_factory=datetime.now)
    rtt_ms: float = 0.0
    failures: int = 0

    @property
    def is_stale(self, timeout_seconds: float = 300.0) -> bool:
        """检查条目是否过期"""
        return (datetime.now() - self.last_response).total_seconds() > timeout_seconds

    @property
    def is_dead(self, max_failures: int = 5) -> bool:
        return self.failures >= max_failures


# ============================================================================
# 序列化工具
# ============================================================================

def serialize_message(msg: P2PMessage) -> bytes:
    """将消息序列化为 JSON 字节"""
    return json.dumps(msg.to_dict(), ensure_ascii=False).encode("utf-8")

def deserialize_message(data: bytes) -> P2PMessage:
    """从 JSON 字节反序列化消息"""
    return P2PMessage.from_dict(json.loads(data.decode("utf-8")))


__all__ = [
    # 枚举
    "PeerStatus", "ConnectionType", "MessageType", "NATType", "TrustLevel", "DiscoveryMethod",
    # 数据模型
    "NetworkAddress", "PeerIdentity", "PeerInfo", "P2PMessage",
    "ConnectionConfig", "RoutingEntry",
    # 序列化
    "serialize_message", "deserialize_message",
]
