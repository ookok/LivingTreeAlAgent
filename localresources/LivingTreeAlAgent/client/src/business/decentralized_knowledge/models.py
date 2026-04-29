"""
去中心化知识系统数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class NodeStatus(Enum):
    """节点状态"""
    OFFLINE = "offline"
    ONLINE = "online"
    CONNECTING = "connecting"
    ERROR = "error"


class ConnectionQuality(Enum):
    """连接质量"""
    UNKNOWN = "unknown"
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


@dataclass
class KnowledgeEntry:
    """知识条目"""
    entry_id: str
    title: str
    content: str
    
    # 作者
    author_id: str
    author_name: str = ""
    
    # 标签和分类
    tags: List[str] = field(default_factory=list)
    category: str = ""
    
    # 版本信息
    version: int = 1
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # 同步状态
    sync_status: str = "local"  # local, synced, conflict
    remote_version: int = 0
    
    # 引用计数
    references: int = 0
    likes: int = 0
    views: int = 0
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PeerInfo:
    """对等节点信息"""
    peer_id: str
    peer_name: str = ""
    
    # 连接信息
    host: str = ""
    port: int = 0
    public_ip: Optional[str] = None
    
    # 状态
    status: NodeStatus = NodeStatus.OFFLINE
    connection_quality: ConnectionQuality = ConnectionQuality.UNKNOWN
    latency_ms: float = 0.0
    
    # 能力
    can_relay: bool = False
    can_store: bool = False
    storage_available_gb: float = 0.0
    
    # 统计
    connected_at: Optional[datetime] = None
    last_active: datetime = field(default_factory=datetime.now)
    messages_forwarded: int = 0
    
    # 用户信息
    user_id: Optional[str] = None


@dataclass
class SyncMetadata:
    """同步元数据"""
    total_entries: int = 0
    synced_entries: int = 0
    pending_entries: int = 0
    conflict_entries: int = 0
    
    last_sync: Optional[datetime] = None
    sync_duration_ms: float = 0.0
    
    # 同步统计
    bytes_uploaded: int = 0
    bytes_downloaded: int = 0
