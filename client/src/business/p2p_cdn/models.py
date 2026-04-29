"""
P2P CDN 数据模型

定义 CDN 系统中使用的数据结构
from __future__ import annotations
"""


import time
from typing import Dict, Set, Optional, Any


class NodeCapability:
    """
    节点能力模型
    描述节点的存储、带宽、在线时间和可靠性等能力
    """
    
    def __init__(
        self,
        storage_available: int,
        bandwidth: int,
        uptime: int,
        reliability: float
    ):
        self.storage_available = storage_available  # 可用存储空间（字节）
        self.bandwidth = bandwidth  # 带宽（Mbps）
        self.uptime = uptime  # 在线时间（秒）
        self.reliability = reliability  # 可靠性（0-1）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "storage_available": self.storage_available,
            "bandwidth": self.bandwidth,
            "uptime": self.uptime,
            "reliability": self.reliability
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NodeCapability:
        """从字典创建"""
        return cls(
            storage_available=data.get("storage_available", 0),
            bandwidth=data.get("bandwidth", 0),
            uptime=data.get("uptime", 0),
            reliability=data.get("reliability", 0.0)
        )


class CacheStatus:
    """
    缓存状态
    """
    IDLE = "idle"      # 空闲
    CACHING = "caching"  # 正在缓存
    CACHED = "cached"   # 已缓存
    EVICTED = "evicted"  # 已淘汰


class CDNNode:
    """
    CDN 节点模型
    描述网络中的 CDN 节点
    """
    
    def __init__(
        self,
        node_id: str,
        capability: NodeCapability,
        last_seen: float,
        cache_stats: Optional[Dict[str, Any]] = None
    ):
        self.node_id = node_id  # 节点 ID
        self.capability = capability  # 节点能力
        self.last_seen = last_seen  # 最后 seen 时间
        self.cache_stats = cache_stats or {}  # 缓存统计信息
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "capability": self.capability.to_dict(),
            "last_seen": self.last_seen,
            "cache_stats": self.cache_stats
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CDNNode:
        """从字典创建"""
        return cls(
            node_id=data.get("node_id"),
            capability=NodeCapability.from_dict(data.get("capability", {})),
            last_seen=data.get("last_seen", time.time()),
            cache_stats=data.get("cache_stats", {})
        )


class CDNData:
    """
    CDN 数据模型
    描述存储在 CDN 中的结构化数据
    """
    
    def __init__(
        self,
        data_id: str,
        data: Dict[str, Any],
        data_type: str,
        created_at: float,
        version: int
    ):
        self.data_id = data_id  # 数据 ID
        self.data = data  # 实际数据
        self.data_type = data_type  # 数据类型（json, yaml, etc.）
        self.created_at = created_at  # 创建时间
        self.version = version  # 数据版本
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "data_id": self.data_id,
            "data": self.data,
            "data_type": self.data_type,
            "created_at": self.created_at,
            "version": self.version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CDNData:
        """从字典创建"""
        return cls(
            data_id=data.get("data_id"),
            data=data.get("data", {}),
            data_type=data.get("data_type", "json"),
            created_at=data.get("created_at", time.time()),
            version=data.get("version", 1)
        )


class DataMetadata:
    """
    数据元数据模型
    描述数据的元信息，如大小、访问次数、副本分布等
    """
    
    def __init__(
        self,
        data_id: str,
        data_type: str,
        size: int,
        created_at: float,
        access_count: int,
        last_access: float,
        replicas: Set[str],
        version: int = 1
    ):
        self.data_id = data_id  # 数据 ID
        self.data_type = data_type  # 数据类型
        self.size = size  # 数据大小（字节）
        self.created_at = created_at  # 创建时间
        self.access_count = access_count  # 访问次数
        self.last_access = last_access  # 最后访问时间
        self.replicas = replicas  # 副本节点 ID 集合
        self.version = version  # 数据版本
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "data_id": self.data_id,
            "data_type": self.data_type,
            "size": self.size,
            "created_at": self.created_at,
            "access_count": self.access_count,
            "last_access": self.last_access,
            "replicas": list(self.replicas),
            "version": self.version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DataMetadata:
        """从字典创建"""
        return cls(
            data_id=data.get("data_id"),
            data_type=data.get("data_type", "json"),
            size=data.get("size", 0),
            created_at=data.get("created_at", time.time()),
            access_count=data.get("access_count", 0),
            last_access=data.get("last_access", time.time()),
            replicas=set(data.get("replicas", [])),
            version=data.get("version", 1)
        )


class DataVersion:
    """
    数据版本模型
    描述数据的版本信息
    """
    
    def __init__(
        self,
        data_id: str,
        version: int,
        created_at: float,
        node_id: str
    ):
        self.data_id = data_id  # 数据 ID
        self.version = version  # 版本号
        self.created_at = created_at  # 创建时间
        self.node_id = node_id  # 创建节点 ID
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "data_id": self.data_id,
            "version": self.version,
            "created_at": self.created_at,
            "node_id": self.node_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DataVersion:
        """从字典创建"""
        return cls(
            data_id=data.get("data_id"),
            version=data.get("version", 1),
            created_at=data.get("created_at", time.time()),
            node_id=data.get("node_id")
        )


class NetworkMetrics:
    """
    网络指标模型
    描述网络性能指标
    """
    
    def __init__(
        self,
        node_id: str,
        latency: float,
        bandwidth: float,
        packet_loss: float,
        measured_at: float
    ):
        self.node_id = node_id  # 节点 ID
        self.latency = latency  # 延迟（毫秒）
        self.bandwidth = bandwidth  # 带宽（Mbps）
        self.packet_loss = packet_loss  # 丢包率（0-1）
        self.measured_at = measured_at  # 测量时间
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "latency": self.latency,
            "bandwidth": self.bandwidth,
            "packet_loss": self.packet_loss,
            "measured_at": self.measured_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NetworkMetrics:
        """从字典创建"""
        return cls(
            node_id=data.get("node_id"),
            latency=data.get("latency", 0.0),
            bandwidth=data.get("bandwidth", 0.0),
            packet_loss=data.get("packet_loss", 0.0),
            measured_at=data.get("measured_at", time.time())
        )
