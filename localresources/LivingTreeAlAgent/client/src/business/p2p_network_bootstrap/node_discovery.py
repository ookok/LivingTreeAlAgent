# -*- coding: utf-8 -*-
"""
Phase 1: 节点即配置源 (Node-as-a-Config)
P2P网络自举协议 - 核心节点发现与推送模块

核心理念：
- 节点本身就是活的配置中心
- 客户端连接任一节点即可获取全网拓扑
- 配置实时更新，节点下线立刻剔除

作者：Hermes Desktop V2.0
版本：1.0.0
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
import asyncio
import hashlib
import random


class NodeRole(Enum):
    """节点角色"""
    PEER = "peer"           # 普通P2P节点
    RELAY = "relay"         # 中继服务器
    BOOTSTRAP = "bootstrap" # 引导节点
    WEBRTC_GATEWAY = "webrtc"  # WebRTC信令网关


class NodeStatus(Enum):
    """节点状态"""
    UNKNOWN = "unknown"
    ALIVE = "alive"
    DEGRADED = "degraded"   # 降级（延迟高/丢包）
    DEAD = "dead"
    SUSPECTED = "suspected" # 疑似死亡


@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str
    url: str  # WebSocket URL
    role: NodeRole = NodeRole.PEER
    status: NodeStatus = NodeStatus.UNKNOWN

    # 质量指标
    latency_ms: float = 0.0
    packet_loss_rate: float = 0.0  # 丢包率 0-1
    last_probe: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    # 负载信息
    connected_clients: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0

    # 地理位置（可选）
    region: str = ""
    country: str = ""

    # 权重（用于选择）
    weight: float = 1.0

    # 信任相关
    trust_score: float = 1.0  # 0-1
    first_seen: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.last_seen is None:
            self.last_seen = datetime.now()

    def is_stale(self, threshold_seconds: int = 300) -> bool:
        """检查节点是否过时"""
        if self.last_seen is None:
            return True
        return (datetime.now() - self.last_seen).total_seconds() > threshold_seconds

    def calculate_quality_score(self) -> float:
        """计算质量分数 0-100"""
        score = 100.0

        # 延迟扣分 (0-50分)
        if self.latency_ms > 0:
            score -= min(50, self.latency_ms / 10)

        # 丢包扣分 (0-40分)
        score -= self.packet_loss_rate * 40

        # 负载扣分 (0-10分)
        if self.cpu_usage > 0.8:
            score -= 5
        if self.memory_usage > 0.9:
            score -= 5

        return max(0, score)

    def update_weight(self):
        """根据质量更新权重"""
        quality = self.calculate_quality_score()
        trust = self.trust_score

        # 权重 = 质量 * 信任 * 基础权重
        self.weight = (quality / 100.0) * trust * 1.0


@dataclass
class NetworkTopology:
    """网络拓扑快照"""
    timestamp: datetime
    nodes: List[NodeInfo]
    total_peers: int
    total_relays: int
    total_webrtc_gateways: int

    # 版本号（用于增量更新）
    version: int = 0

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "url": n.url,
                    "role": n.role.value,
                    "latency_ms": n.latency_ms,
                    "packet_loss_rate": n.packet_loss_rate,
                    "connected_clients": n.connected_clients,
                    "region": n.region,
                    "weight": n.weight,
                    "trust_score": n.trust_score
                }
                for n in self.nodes
            ],
            "total_peers": self.total_peers,
            "total_relays": self.total_relays,
            "total_webrtc_gateways": self.total_webrtc_gateways
        }


class NodeRegistry:
    """节点注册表 - 管理所有已知节点"""

    def __init__(self):
        self.nodes: Dict[str, NodeInfo] = {}
        self.version = 0
        self._lock = asyncio.Lock()

    async def add_node(self, node: NodeInfo) -> bool:
        """添加节点"""
        async with self._lock:
            if node.node_id in self.nodes:
                # 更新已有节点
                existing = self.nodes[node.node_id]
                existing.last_seen = datetime.now()
                existing.latency_ms = node.latency_ms
                existing.packet_loss_rate = node.packet_loss_rate
                existing.connected_clients = node.connected_clients
                existing.update_weight()
                return False  # 已存在

            node.last_seen = datetime.now()
            self.nodes[node.node_id] = node
            self.version += 1
            return True  # 新增

    async def remove_node(self, node_id: str) -> bool:
        """移除节点"""
        async with self._lock:
            if node_id in self.nodes:
                del self.nodes[node_id]
                self.version += 1
                return True
            return False

    async def get_node(self, node_id: str) -> Optional[NodeInfo]:
        """获取节点"""
        return self.nodes.get(node_id)

    async def get_all_nodes(self) -> List[NodeInfo]:
        """获取所有节点"""
        return list(self.nodes.values())

    async def get_alive_nodes(self, max_count: int = 50) -> List[NodeInfo]:
        """获取活跃节点"""
        alive = [
            n for n in self.nodes.values()
            if n.status in [NodeStatus.ALIVE, NodeStatus.DEGRADED]
            and not n.is_stale()
        ]

        # 按权重排序
        alive.sort(key=lambda n: n.weight, reverse=True)
        return alive[:max_count]

    async def get_nodes_by_role(self, role: NodeRole) -> List[NodeInfo]:
        """按角色获取节点"""
        return [
            n for n in self.nodes.values()
            if n.role == role and n.status == NodeStatus.ALIVE
        ]

    async def update_node_status(self, node_id: str, status: NodeStatus):
        """更新节点状态"""
        if node_id in self.nodes:
            self.nodes[node_id].status = status

    async def mark_node_dead(self, node_id: str):
        """标记节点死亡"""
        if node_id in self.nodes:
            self.nodes[node_id].status = NodeStatus.DEAD

    async def cleanup_stale_nodes(self, threshold_seconds: int = 300):
        """清理过时节点"""
        async with self._lock:
            stale = [
                nid for nid, n in self.nodes.items()
                if n.is_stale(threshold_seconds)
            ]
            for nid in stale:
                del self.nodes[nid]
            if stale:
                self.version += 1

    async def get_topology(self) -> NetworkTopology:
        """获取网络拓扑"""
        nodes = await self.get_alive_nodes(max_count=100)

        peers = [n for n in nodes if n.role == NodeRole.PEER]
        relays = [n for n in nodes if n.role == NodeRole.RELAY]
        webrtc_gateways = [n for n in nodes if n.role == NodeRole.WEBRTC_GATEWAY]

        return NetworkTopology(
            timestamp=datetime.now(),
            nodes=nodes,
            total_peers=len(peers),
            total_relays=len(relays),
            total_webrtc_gateways=len(webrtc_gateways),
            version=self.version
        )


class NodeDiscoveryService:
    """
    节点发现服务 - Phase 1 核心

    功能：
    1. 响应客户端的拓扑请求
    2. 推送邻居变更事件
    3. 主动发现新节点
    """

    def __init__(self, node_id: str, url: str, role: NodeRole = NodeRole.PEER):
        self.node_id = node_id
        self.url = url
        self.role = role

        self.registry = NodeRegistry()

        # 注册自己
        self_self = NodeInfo(
            node_id=node_id,
            url=url,
            role=role,
            status=NodeStatus.ALIVE
        )
        asyncio.create_task(self.registry.add_node(self_self))

        # 回调
        self.on_node_discovered: Optional[callable] = None
        self.on_node_lost: Optional[callable] = None

        # 统计
        self.discovery_requests = 0
        self.last_topology_push = datetime.now()

    async def handle_topology_request(self, client_id: str, include_relays: bool = True) -> NetworkTopology:
        """
        处理拓扑请求 - 核心接口

        客户端发送 GET /network/topology 请求
        返回当前节点的实时拓扑
        """
        self.discovery_requests += 1

        # 清理过时节点
        await self.registry.cleanup_stale_nodes()

        # 获取拓扑
        topology = await self.registry.get_topology()

        # 如果需要包含中继，且当前节点不是中继，则添加一些中继
        if include_relays and self.role != NodeRole.RELAY:
            relay_nodes = await self.registry.get_nodes_by_role(NodeRole.RELAY)
            if relay_nodes:
                # 添加最优质的中继（最多3个）
                relay_nodes.sort(key=lambda n: n.weight, reverse=True)
                for relay in relay_nodes[:3]:
                    if relay.node_id not in [n.node_id for n in topology.nodes]:
                        topology.nodes.append(relay)

        # 标记推送时间
        self.last_topology_push = datetime.now()

        return topology

    async def broadcast_node_up(self, node: NodeInfo):
        """广播节点上线事件"""
        event = {
            "event": "node_up",
            "node": {
                "node_id": node.node_id,
                "url": node.url,
                "role": node.role.value,
                "region": node.region,
                "weight": node.weight
            },
            "timestamp": datetime.now().isoformat()
        }

        # 通知所有连接的客户端
        if self.on_node_discovered:
            await self.on_node_discovered(event)

    async def broadcast_node_down(self, node_id: str):
        """广播节点下线事件"""
        event = {
            "event": "node_down",
            "node_id": node_id,
            "timestamp": datetime.now().isoformat()
        }

        if self.on_node_lost:
            await self.on_node_lost(event)

    async def add_peer_from_external(self, peer_info: Dict) -> bool:
        """从外部信息添加节点（如从其他节点同步）"""
        try:
            node = NodeInfo(
                node_id=peer_info["node_id"],
                url=peer_info["url"],
                role=NodeRole(peer_info.get("role", "peer")),
                region=peer_info.get("region", ""),
                weight=peer_info.get("weight", 1.0),
                trust_score=peer_info.get("trust_score", 0.8)
            )

            is_new = await self.registry.add_node(node)

            if is_new and self.on_node_discovered:
                await self.broadcast_node_up(node)

            return is_new
        except Exception:
            return False

    def generate_node_id(self) -> str:
        """生成节点ID"""
        timestamp = datetime.now().isoformat()
        random_bytes = str(random.randint(0, 999999)).encode()
        hash_input = f"{self.url}{timestamp}{random_bytes}".encode()
        return hashlib.sha256(hash_input).hexdigest()[:16]


class TopologyPushService:
    """
    拓扑推送服务

    主动向客户端推送拓扑变更
    实现"连接即感染"的病毒式传播
    """

    def __init__(self, discovery_service: NodeDiscoveryService):
        self.discovery = discovery_service
        self.subscribed_clients: Set[str] = set()
        self.push_interval = 30  # 秒

        self._push_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动推送服务"""
        self._push_task = asyncio.create_task(self._push_loop())

    async def stop(self):
        """停止推送服务"""
        if self._push_task:
            self._push_task.cancel()
            try:
                await self._push_task
            except asyncio.CancelledError:
                pass

    async def subscribe(self, client_id: str):
        """订阅拓扑推送"""
        self.subscribed_clients.add(client_id)

    async def unsubscribe(self, client_id: str):
        """取消订阅"""
        self.subscribed_clients.discard(client_id)

    async def _push_loop(self):
        """推送循环"""
        while True:
            await asyncio.sleep(self.push_interval)

            if not self.subscribed_clients:
                continue

            try:
                # 获取最新拓扑
                topology = await self.discovery.handle_topology_request("push_service")

                # 构建推送消息
                push_event = {
                    "type": "topology_update",
                    "data": topology.to_dict(),
                    "subscribers": len(self.subscribed_clients)
                }

                # 这里会通过WebSocket等机制推送给所有订阅者
                # 实际实现时连接到消息队列或WebSocket广播

            except Exception as e:
                # 推送失败，记录日志但不中断
                pass

    async def notify_topology_change(self, change_type: str, node_id: str):
        """
        通知拓扑变更 - 用于Gossip传播
        """
        change_event = {
            "type": "topology_change",
            "change_type": change_type,  # node_up, node_down, quality_update
            "node_id": node_id,
            "origin": self.discovery.node_id,
            "timestamp": datetime.now().isoformat()
        }

        # 通过Gossip协议传播给其他节点
        # 实际实现时通过节点间通信


class BootstrapProtocol:
    """
    引导协议 - 实现"零配置"启动

    客户端启动时只需要知道任意一个节点的地址
    通过该节点获取全网拓扑
    """

    def __init__(self):
        self.known_bootstrap_nodes: List[str] = []

    def add_bootstrap_node(self, url: str):
        """添加引导节点"""
        if url not in self.known_bootstrap_nodes:
            self.known_bootstrap_nodes.append(url)

    async def discover_initial_nodes(self) -> List[NodeInfo]:
        """
        发现初始节点

        实现逻辑：
        1. 尝试连接已知引导节点
        2. 获取拓扑
        3. 将拓扑中的节点作为新的连接候选
        """
        discovered = []

        for bootstrap_url in self.known_bootstrap_nodes:
            try:
                # 模拟HTTP/WebSocket请求获取拓扑
                # 实际实现时使用aiohttp或websockets
                topology = await self._fetch_topology(bootstrap_url)

                if topology:
                    discovered.extend(topology.nodes)

                    # 如果获取到足够节点就停止
                    if len(discovered) >= 10:
                        break

            except Exception:
                # 引导节点不可用，尝试下一个
                continue

        return discovered

    async def _fetch_topology(self, url: str) -> Optional[NetworkTopology]:
        """从节点获取拓扑"""
        # 这里是模拟实现
        # 实际需要建立WebSocket连接并请求拓扑
        return None


# 便捷函数
def create_bootstrap_node(url: str, role: NodeRole = NodeRole.PEER) -> NodeDiscoveryService:
    """创建引导节点"""
    node_id = hashlib.sha256(url.encode()).hexdigest()[:16]
    service = NodeDiscoveryService(node_id, url, role)
    return service
