"""
网络优化系统数据模型
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time


class NodeLevel(Enum):
    """节点级别"""
    SUPER = "super"       # 超级节点
    NORMAL = "normal"     # 普通节点
    EDGE = "edge"         # 边缘节点
    MOBILE = "mobile"     # 移动节点


class ConnectionQuality(Enum):
    """连接质量等级"""
    EXCELLENT = 5  # <50ms, >10Mbps
    GOOD = 4      # <100ms, >5Mbps
    FAIR = 3      # <200ms, >1Mbps
    POOR = 2      # <500ms, >256Kbps
    BAD = 1       # >500ms or >5%丢包


class NetworkTier(Enum):
    """网络层级"""
    LAN = "lan"           # 局域网
    P2P = "p2p"           # P2P网络
    RELAY = "relay"       # 中继网络
    OFFLINE = "offline"   # 离线


class CongestionLevel(Enum):
    """拥塞等级"""
    NONE = 0
    MILD = 1
    MODERATE = 2
    SEVERE = 3


class QoSPriority(Enum):
    """QoS优先级"""
    CRITICAL = 0  # 控制信令
    HIGH = 1      # 实时音视频
    NORMAL = 2    # 交互消息
    LOW = 3       # 文件传输
    BACKGROUND = 4 # 后台同步


class TrafficType(Enum):
    """流量类型"""
    CONTROL = "control"
    REALTIME = "realtime"      # 音视频
    INTERACTIVE = "interactive"
    FILE_TRANSFER = "file"
    BACKGROUND = "background"


@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str
    level: NodeLevel = NodeLevel.NORMAL
    host: str = ""
    port: int = 0
    public_ip: Optional[str] = None
    latency_ms: float = 0
    bandwidth_mbps: float = 0
    stability: float = 1.0  # 0-1
    cpu_usage: float = 0
    memory_usage: float = 0
    uptime_seconds: int = 0
    is_online: bool = True
    is_super_node: bool = False
    region: str = ""
    last_seen: float = field(default_factory=time.time)
    capabilities: list[str] = field(default_factory=list)
    
    @property
    def quality_score(self) -> float:
        """计算节点质量分数"""
        latency_score = max(0, 1 - self.latency_ms / 500) * 40
        bandwidth_score = min(self.bandwidth_mbps / 10, 1) * 30
        stability_score = self.stability * 20
        resource_score = max(0, 1 - (self.cpu_usage + self.memory_usage) / 200) * 10
        return latency_score + bandwidth_score + stability_score + resource_score


@dataclass
class ConnectionInfo:
    """连接信息"""
    conn_id: str
    peer_id: str
    peer_node: NodeInfo
    protocol: str = "tcp"  # tcp, udp, quic
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    bytes_sent: int = 0
    bytes_received: int = 0
    packets_sent: int = 0
    packets_received: int = 0
    packets_failed: int = 0
    avg_latency_ms: float = 0
    jitter_ms: float = 0
    packet_loss: float = 0  # 0-1
    quality: ConnectionQuality = ConnectionQuality.FAIR
    priority: int = 2
    is_active: bool = True
    tier: NetworkTier = NetworkTier.P2P
    
    def update_stats(self, latency_ms: float, packet_loss: float):
        """更新连接统计"""
        self.last_active = time.time()
        self.avg_latency_ms = (self.avg_latency_ms * 0.7 + latency_ms * 0.3)
        self.jitter_ms = abs(latency_ms - self.avg_latency_ms)
        self.packet_loss = packet_loss
        self._update_quality()
    
    def _update_quality(self):
        """更新连接质量等级"""
        if self.avg_latency_ms < 50 and self.packet_loss < 0.01:
            self.quality = ConnectionQuality.EXCELLENT
        elif self.avg_latency_ms < 100 and self.packet_loss < 0.02:
            self.quality = ConnectionQuality.GOOD
        elif self.avg_latency_ms < 200 and self.packet_loss < 0.05:
            self.quality = ConnectionQuality.FAIR
        elif self.avg_latency_ms < 500 and self.packet_loss < 0.1:
            self.quality = ConnectionQuality.POOR
        else:
            self.quality = ConnectionQuality.BAD


@dataclass
class SyncChunk:
    """同步数据块"""
    chunk_id: str
    content: bytes
    hash: str = ""
    offset: int = 0
    size: int = 0
    is_critical: bool = False
    retry_count: int = 0
    status: str = "pending"  # pending, sending, completed, failed


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    task_type: str  # compute, storage, relay
    payload: bytes = field(default_factory=bytes)
    required_cpu: float = 1.0
    required_memory_mb: float = 100
    required_bandwidth_mbps: float = 1
    priority: QoSPriority = QoSPriority.NORMAL
    deadline_seconds: Optional[float] = None
    source_node: str = ""
    target_nodes: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    status: str = "pending"
    progress: float = 0
    result: Optional[bytes] = None


@dataclass
class NetworkStats:
    """网络统计"""
    bytes_sent: int = 0
    bytes_received: int = 0
    packets_sent: int = 0
    packets_received: int = 0
    packets_failed: int = 0
    connection_count: int = 0
    active_node_count: int = 0
    avg_latency_ms: float = 0
    avg_bandwidth_mbps: float = 0
    congestion_rate: float = 0
    flow_controller_state: dict = field(default_factory=dict)
    congestion_state: dict = field(default_factory=dict)
    monitor_state: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class MerkleNode:
    """Merkle树节点"""
    hash: str
    left: Optional['MerkleNode'] = None
    right: Optional['MerkleNode'] = None
    is_leaf: bool = False
    data: Optional[bytes] = None
    
    @property
    def is_empty(self) -> bool:
        return self.hash == ""


@dataclass
class KBucket:
    """K桶（Kademlia路由表）"""
    node_id_prefix: str
    nodes: list[NodeInfo] = field(default_factory=list)
    last_refresh: float = field(default_factory=time.time)
    max_size: int = 20
    
    def add_node(self, node: NodeInfo) -> bool:
        """添加节点到K桶"""
        if node in self.nodes:
            return False
        if len(self.nodes) >= self.max_size:
            # 移除最老的节点
            self.nodes.sort(key=lambda n: n.last_seen)
            self.nodes.pop(0)
        self.nodes.append(node)
        return True
    
    def get_nodes(self, count: int = 3) -> list[NodeInfo]:
        """获取最近的N个节点"""
        sorted_nodes = sorted(self.nodes, key=lambda n: n.quality_score, reverse=True)
        return sorted_nodes[:count]
