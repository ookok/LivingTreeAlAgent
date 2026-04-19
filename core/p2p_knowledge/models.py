"""
P2P知识库系统 - 核心数据模型

零成本零配置内网穿透与分布式知识库系统
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Optional


class NatType(IntEnum):
    """NAT类型枚举"""
    UNKNOWN = 0
    OPEN = 1           # 公网IP
    FULL_CONE = 2      # 全锥型
    RESTRICTED_CONE = 3 # 受限锥型
    PORT_RESTRICTED = 4 # 端口受限锥型
    SYMMETRIC = 5      # 对称型


class NodeRole(IntEnum):
    """节点角色"""
    PEER = 0           # 普通对等节点
    RELAY = 1          # 中继服务器
    BOOTSTRAP = 2      # 引导节点


class SyncStatus(IntEnum):
    """同步状态"""
    IDLE = 0
    SYNCING = 1
    COMPLETED = 2
    FAILED = 3
    CONFLICT = 4


class ShareType(IntEnum):
    """分享类型"""
    LINK = 0           # 短链接分享
    QRCODE = 1          # 二维码分享
    PEER = 2            # P2P直连分享


@dataclass
class NetworkAddress:
    """网络地址"""
    ip: str
    port: int
    nat_type: NatType = NatType.UNKNOWN
    is_public: bool = False
    
    def __str__(self) -> str:
        return f"{self.ip}:{self.port}"
    
    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "port": self.port,
            "nat_type": self.nat_type.value,
            "is_public": self.is_public
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> NetworkAddress:
        return cls(
            ip=data["ip"],
            port=data["port"],
            nat_type=NatType(data.get("nat_type", 0)),
            is_public=data.get("is_public", False)
        )


@dataclass
class PeerNode:
    """对等节点"""
    node_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_id: Optional[str] = None
    local_addr: Optional[NetworkAddress] = None
    public_addr: Optional[NetworkAddress] = None
    relay_addr: Optional[NetworkAddress] = None
    role: NodeRole = NodeRole.PEER
    is_online: bool = False
    last_seen: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    nat_type: NatType = NatType.UNKNOWN
    connection_count: int = 0
    total_transfer: int = 0  # 字节数
    score: float = 1.0      # 信誉分
    tags: list[str] = field(default_factory=list)
    
    def is_stale(self, timeout: int = 60) -> bool:
        """检查节点是否过期"""
        return time.time() - self.last_heartbeat > timeout
    
    def touch(self):
        """更新心跳时间"""
        self.last_heartbeat = time.time()
    
    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "user_id": self.user_id,
            "local_addr": self.local_addr.to_dict() if self.local_addr else None,
            "public_addr": self.public_addr.to_dict() if self.public_addr else None,
            "relay_addr": self.relay_addr.to_dict() if self.relay_addr else None,
            "role": self.role.value,
            "is_online": self.is_online,
            "last_seen": self.last_seen,
            "nat_type": self.nat_type.value,
            "connection_count": self.connection_count,
            "score": self.score
        }


@dataclass
class KnowledgeItem:
    """知识库条目"""
    user_id: str
    title: str
    content: str
    item_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    content_type: str = "text"  # text, markdown, code, file
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    version: int = 1
    checksum: Optional[str] = None
    size: int = 0  # 字节数
    file_path: Optional[str] = None
    is_deleted: bool = False
    
    def compute_checksum(self) -> str:
        """计算内容校验和"""
        data = f"{self.item_id}:{self.updated_at}:{self.content}".encode()
        self.checksum = hashlib.sha256(data).hexdigest()[:16]
        return self.checksum
    
    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "user_id": self.user_id,
            "title": self.title,
            "content": self.content,
            "content_type": self.content_type,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "checksum": self.checksum,
            "size": self.size,
            "is_deleted": self.is_deleted
        }


@dataclass
class SyncOperation:
    """同步操作"""
    item_id: str
    user_id: str
    op_type: str  # create, update, delete
    op_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    version: int = 1
    checksum: Optional[str] = None
    payload: Optional[dict] = None
    source_node: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "op_id": self.op_id,
            "item_id": self.item_id,
            "user_id": self.user_id,
            "op_type": self.op_type,
            "timestamp": self.timestamp,
            "version": self.version,
            "checksum": self.checksum,
            "source_node": self.source_node
        }


@dataclass
class SyncConflict:
    """同步冲突"""
    item_id: str
    local_version: KnowledgeItem
    remote_version: KnowledgeItem
    conflict_type: str  # content, delete, metadata
    detected_at: float = field(default_factory=time.time)
    resolved: bool = False
    resolution: Optional[str] = None


@dataclass
class ShareLink:
    """分享链接"""
    item_id: str
    user_id: str
    share_code: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    share_type: ShareType = ShareType.LINK
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    max_access_count: Optional[int] = None
    access_count: int = 0
    password: Optional[str] = None
    is_active: bool = True
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def to_dict(self) -> dict:
        return {
            "share_code": self.share_code,
            "item_id": self.item_id,
            "user_id": self.user_id,
            "share_type": self.share_type.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "access_count": self.access_count,
            "is_active": self.is_active
        }


@dataclass
class StorageProvider:
    """存储提供商配置"""
    name: str
    provider_type: str  # baidu, aliyun, local, etc.
    provider_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    api_endpoint: str = ""
    enabled: bool = True
    total_space: int = 0
    used_space: int = 0
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    supports_chunking: bool = False
    credentials: dict = field(default_factory=dict)
    priority: int = 0
    
    def get_available_space(self) -> int:
        if self.total_space == 0:
            return 0
        return self.total_space - self.used_space


@dataclass
class FileChunk:
    """文件分块"""
    file_id: str
    chunk_index: int
    size: int
    checksum: str
    chunk_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    provider_id: Optional[str] = None
    storage_path: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "file_id": self.file_id,
            "chunk_index": self.chunk_index,
            "size": self.size,
            "checksum": self.checksum,
            "provider_id": self.provider_id,
            "storage_path": self.storage_path
        }


@dataclass
class RelayServer:
    """中继服务器"""
    name: str
    addr: NetworkAddress
    server_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    region: str = "unknown"
    bandwidth: int = 0  # Mbps
    is_volunteer: bool = False
    owner_id: Optional[str] = None
    is_online: bool = False
    load: float = 0.0  # 0.0-1.0
    latency: float = 0.0  # ms
    score: float = 1.0
    max_connections: int = 100
    current_connections: int = 0
    last_heartbeat: float = field(default_factory=time.time)
    version: str = "1.0.0"
    
    def is_available(self) -> bool:
        return self.is_online and self.load < 0.9 and self.current_connections < self.max_connections
    
    def to_dict(self) -> dict:
        return {
            "server_id": self.server_id,
            "name": self.name,
            "addr": self.addr.to_dict(),
            "region": self.region,
            "is_volunteer": self.is_volunteer,
            "is_online": self.is_online,
            "load": self.load,
            "latency": self.latency,
            "score": self.score,
            "max_connections": self.max_connections,
            "current_connections": self.current_connections,
            "version": self.version
        }


@dataclass
class Message:
    """P2P消息"""
    msg_type: str  # handshake, ping, pong, find_node, nodes, store, find_value, relay
    source_id: str
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    target_id: Optional[str] = None
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    ttl: int = 3  # 跳数限制
    hop_count: int = 0
    
    def to_bytes(self) -> bytes:
        """序列化消息"""
        import json
        return json.dumps({
            "msg_id": self.msg_id,
            "msg_type": self.msg_type,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "ttl": self.ttl,
            "hop_count": self.hop_count
        }).encode('utf-8')
    
    @classmethod
    def from_bytes(cls, data: bytes) -> Message:
        """反序列化消息"""
        import json
        d = json.loads(data.decode('utf-8'))
        return cls(
            msg_id=d["msg_id"],
            msg_type=d["msg_type"],
            source_id=d["source_id"],
            target_id=d.get("target_id"),
            payload=d.get("payload", {}),
            timestamp=d.get("timestamp", time.time()),
            ttl=d.get("ttl", 3),
            hop_count=d.get("hop_count", 0)
        )


@dataclass
class SyncState:
    """同步状态"""
    user_id: str
    last_sync: float = 0
    status: SyncStatus = SyncStatus.IDLE
    pending_ops: int = 0
    synced_items: int = 0
    conflicts: int = 0
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "last_sync": self.last_sync,
            "status": self.status.value,
            "pending_ops": self.pending_ops,
            "synced_items": self.synced_items,
            "conflicts": self.conflicts
        }


@dataclass
class ConnectionStats:
    """连接统计"""
    total_connections: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    relay_connections: int = 0
    total_data_sent: int = 0  # bytes
    total_data_received: int = 0  # bytes
    average_latency: float = 0.0  # ms
    uptime: float = 0.0  # seconds
    
    def success_rate(self) -> float:
        if self.total_connections == 0:
            return 0.0
        return self.successful_connections / self.total_connections


# ============= 常量定义 =============

# 协议常量
PROTOCOL_VERSION = "1.0.0"
DEFAULT_UDP_PORT = 18888
DEFAULT_TCP_PORT = 18889
DEFAULT_RELAY_PORT = 18890

# NAT穿透常量
STUN_SERVERS = [
    ("stun.l.google.com", 19302),
    ("stun1.l.google.com", 19302),
    ("stun.cloudflare.com", 3478),
]

# 中继服务器配置
RELAY_HEARTBEAT_INTERVAL = 30  # 秒
RELAY_TIMEOUT = 90  # 秒
NODE_EXPIRY_TIME = 300  # 秒

# 同步配置
CHUNK_SIZE = 1024 * 1024  # 1MB
MAX_CHUNK_SIZE = 5 * 1024 * 1024  # 5MB
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# 缓存配置
KNOWLEDGE_CACHE_SIZE = 1000
OPERATION_CACHE_SIZE = 5000
NODE_CACHE_SIZE = 500
