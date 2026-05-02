"""
P2P 搜索代理数据模型

定义搜索代理网络的核心数据结构
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Optional


class SearchEngineType(Enum):
    """搜索引擎类型"""
    DUCKDUCKGO = "duckduckgo"
    GOOGLE = "google"
    BING = "bing"
    EXA = "exa"
    SEARXNG = "searxng"
    JINA = "jina"


class SearchResultStatus(Enum):
    """搜索结果状态"""
    SUCCESS = "success"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    ERROR = "error"
    NO_PEER = "no_peer_available"


class PeerCapability(IntEnum):
    """节点能力标记"""
    NONE = 0
    HAS_EXTERNAL_NET = 1 << 0      # 有外网访问能力
    HAS_SEARCH_TOOLS = 1 << 1     # 已安装搜索工具
    RELAY_ENABLED = 1 << 2        # 启用中继
    HIGH_BANDWIDTH = 1 << 3        # 高带宽


@dataclass
class SearchTask:
    """搜索任务"""
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    query: str = ""
    engine: SearchEngineType = SearchEngineType.DUCKDUCKGO
    max_results: int = 5
    created_at: float = field(default_factory=time.time)
    timeout: int = 30
    use_p2p: bool = False  # 是否强制使用P2P

    # 路由信息
    source_node: str = ""  # 请求来源节点
    target_node: str = ""  # 执行节点

    # 结果
    status: SearchResultStatus = SearchResultStatus.SUCCESS
    results: list = field(default_factory=list)
    error: str = ""

    # 性能指标
    latency_ms: float = 0.0
    route_type: str = "direct"  # direct/p2p/relay


@dataclass
class SearchResult:
    """搜索结果"""
    title: str = ""
    snippet: str = ""
    url: str = ""
    platform: str = ""
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "snippet": self.snippet,
            "url": self.url,
            "platform": self.platform,
            "score": self.score,
        }


@dataclass
class PeerSearchCapability:
    """节点搜索能力"""
    node_id: str
    capabilities: int = PeerCapability.NONE.value
    last_seen: float = field(default_factory=time.time)
    latency_ms: float = 0.0
    search_success_count: int = 0
    search_fail_count: int = 0

    # 能力检查
    def has_external_net(self) -> bool:
        return bool(self.capabilities & PeerCapability.HAS_EXTERNAL_NET.value)

    def has_search_tools(self) -> bool:
        return bool(self.capabilities & PeerCapability.HAS_SEARCH_TOOLS.value)

    def is_reliable(self) -> bool:
        """判断节点是否可靠（成功率>80%）"""
        total = self.search_success_count + self.search_fail_count
        if total < 3:
            return True  # 新节点默认可信
        return self.search_success_count / total > 0.8

    def get_priority(self) -> float:
        """计算节点优先级"""
        priority = 0.0

        # 基础能力分
        if self.has_external_net():
            priority += 10.0
        if self.has_search_tools():
            priority += 5.0
        if self.capabilities & PeerCapability.HIGH_BANDWIDTH.value:
            priority += 3.0

        # 可靠性分
        total = self.search_success_count + self.search_fail_count
        if total >= 3:
            success_rate = self.search_success_count / total
            priority += success_rate * 5.0

        # 延迟惩罚
        if self.latency_ms > 0:
            priority -= self.latency_ms / 1000.0  # 每秒惩罚1分

        return max(0.0, priority)


@dataclass
class SearchRouteDecision:
    """搜索路由决策"""
    route_type: str  # direct/p2p/relay/fallback
    target_node: Optional[str] = None
    reason: str = ""
    estimated_latency_ms: float = 0.0
    confidence: float = 0.0

    @property
    def is_p2p(self) -> bool:
        return self.route_type in ("p2p", "relay")


@dataclass
class P2PSearchConfig:
    """P2P搜索配置"""
    # 能力标记
    advertise_external_net: bool = False  # 向外广告自己有外网能力
    advertise_search_tools: bool = False   # 向外广告自己有搜索工具

    # 路由策略
    prefer_direct: bool = True  # 优先直连
    p2p_timeout: int = 15       # P2P请求超时(秒)
    direct_timeout: int = 10     # 直连超时(秒)

    # 信任设置
    min_peer_priority: float = 3.0  # 最低peer优先级
    max_hops: int = 3              # 最大跳数

    # 中继服务器
    relay_servers: list[str] = field(default_factory=list)  # ["host:port", ...]

    def to_dict(self) -> dict:
        return {
            "advertise_external_net": self.advertise_external_net,
            "advertise_search_tools": self.advertise_search_tools,
            "prefer_direct": self.prefer_direct,
            "p2p_timeout": self.p2p_timeout,
            "direct_timeout": self.direct_timeout,
            "min_peer_priority": self.min_peer_priority,
            "max_hops": self.max_hops,
            "relay_servers": self.relay_servers,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "P2PSearchConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
