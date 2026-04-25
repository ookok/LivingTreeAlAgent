# -*- coding: utf-8 -*-
"""
Phase 3: Gossip协议自愈网络
P2P网络自举协议 - 分布式状态传播

核心理念：
- 模仿病毒传播，连接即"感染"
- 节点状态变更通过Gossip协议迅速传播
- 网络具备自愈能力，节点下线不影响整体可用性

作者：Hermes Desktop V2.0
版本：1.0.0
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable
from datetime import datetime, timedelta
import asyncio
import random
import hashlib

from core.config.unified_config import UnifiedConfig


class GossipEventType(Enum):
    """Gossip事件类型"""
    NODE_UP = "node_up"              # 节点上线
    NODE_DOWN = "node_down"          # 节点下线
    NODE_QUALITY_UPDATE = "quality"  # 节点质量更新
    NODE_ANNOUNCE = "announce"       # 节点声明
    TOPOLOGY_SYNC = "sync"           # 拓扑同步


@dataclass
class GossipEvent:
    """Gossip事件"""
    event_type: GossipEventType
    node_id: str
    timestamp: datetime
    ttl: int = 3  # 传播跳数
    origin: str = ""  # 起源节点

    # 事件数据
    data: Dict = field(default_factory=dict)

    # 用于去重
    event_id: str = ""

    def __post_init__(self):
        if not self.event_id:
            content = f"{self.event_type.value}_{self.node_id}_{self.timestamp.isoformat()}"
            self.event_id = hashlib.sha256(content.encode()).hexdigest()[:16]

    def should_rebroadcast(self) -> bool:
        """是否应该重新广播"""
        return self.ttl > 0

    def decrement_ttl(self):
        """减少TTL"""
        self.ttl -= 1


@dataclass
class PeerState:
    """对等体状态"""
    peer_id: str
    url: str

    # Gossip状态
    known_events: Set[str] = field(default_factory=set)  # 已知道事件ID
    last_sync: datetime = field(default_factory=datetime.now)

    # 健康状态
    is_healthy: bool = True
    miss_count: int = 0  # 连续未响应次数

    # 反向推荐：记录该peer推荐的其他节点
    reverse_recommendations: List[str] = field(default_factory=list)


class GossipProtocol:
    """
    Gossip协议实现 - Phase 3 核心

    功能：
    1. 节点状态变更的快速传播
    2. 拓扑信息的分布式同步
    3. 反向推荐机制（客户端作为传播载体）
    4. 网络自愈
    """

    def __init__(
        self,
        node_id: str,
        fanout: int = 3,           # 每次传播的节点数
        gossip_interval: Optional[int] = None,   # Gossip间隔（秒）
        sync_interval: Optional[int] = None,     # 完整同步间隔（秒）
        ttl: int = 3                # 默认TTL
    ):
        config = UnifiedConfig.get_instance()
        
        self.node_id = node_id
        self.fanout = fanout
        self.gossip_interval = gossip_interval if gossip_interval is not None else config.get("p2p_network.gossip_interval", 5)
        self.sync_interval = sync_interval if sync_interval is not None else config.get("p2p_network.sync_interval", 30)
        self.default_ttl = ttl

        # 事件历史（用于去重和响应查询）
        self.event_history: Dict[str, GossipEvent] = {}
        self.event_history_max_size = 1000

        # 对等体管理
        self.peers: Dict[str, PeerState] = {}

        # 待处理事件队列
        self.pending_events: asyncio.Queue = asyncio.Queue()

        # 回调
        self.on_event_received: Optional[Callable] = None
        self.on_network_changed: Optional[Callable] = None

        # 统计
        self.events_sent = 0
        self.events_received = 0
        self.bytes_transferred = 0

        # 内部任务
        self._gossip_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """启动Gossip协议"""
        self._running = True
        self._gossip_task = asyncio.create_task(self._gossip_loop())

    async def stop(self):
        """停止Gossip协议"""
        self._running = False

        if self._gossip_task:
            self._gossip_task.cancel()
            try:
                await self._gossip_task
            except asyncio.CancelledError:
                pass

    def add_peer(self, peer_id: str, url: str):
        """添加对等体"""
        if peer_id not in self.peers:
            self.peers[peer_id] = PeerState(peer_id, url)

    def remove_peer(self, peer_id: str):
        """移除对等体"""
        if peer_id in self.peers:
            del self.peers[peer_id]

    async def broadcast_event(self, event: GossipEvent):
        """
        广播事件

        将事件传播给多个对等体
        """
        event.origin = self.node_id
        event.ttl = self.default_ttl

        # 记录到历史
        self._add_to_history(event)

        # 放入待处理队列
        await self.pending_events.put(event)

        if self.on_network_changed:
            await self.on_network_changed(event)

    async def announce_node_up(self, node_info: Dict):
        """广播节点上线"""
        event = GossipEvent(
            event_type=GossipEventType.NODE_UP,
            node_id=node_info["node_id"],
            timestamp=datetime.now(),
            data={
                "url": node_info["url"],
                "role": node_info.get("role", "peer"),
                "region": node_info.get("region", ""),
                "weight": node_info.get("weight", 1.0)
            }
        )

        await self.broadcast_event(event)

    async def announce_node_down(self, node_id: str):
        """广播节点下线"""
        event = GossipEvent(
            event_type=GossipEventType.NODE_DOWN,
            node_id=node_id,
            timestamp=datetime.now()
        )

        await self.broadcast_event(event)

    async def announce_quality_update(self, node_id: str, quality_data: Dict):
        """广播质量更新"""
        event = GossipEvent(
            event_type=GossipEventType.NODE_QUALITY_UPDATE,
            node_id=node_id,
            timestamp=datetime.now(),
            data=quality_data
        )

        await self.broadcast_event(event)

    async def _gossip_loop(self):
        """Gossip传播循环"""
        while self._running:
            try:
                # Gossip间隔
                await asyncio.sleep(self.gossip_interval)

                # 处理待发送事件
                await self._process_pending_events()

                # 与随机对等体交换状态
                await self._random_gossip_exchange()

                # 清理不健康对等体
                await self._cleanup_unhealthy_peers()

            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _process_pending_events(self):
        """处理待发送事件"""
        sent_this_round = 0
        max_per_round = self.fanout * 2

        while not self.pending_events.empty() and sent_this_round < max_per_round:
            try:
                event = self.pending_events.get_nowait()

                # 检查TTL
                if not event.should_rebroadcast():
                    continue

                # 选择要发送的对等体
                targets = self._select_gossip_targets(event)

                # 发送事件到目标
                for peer_id in targets:
                    if peer_id in self.peers:
                        if event.event_id not in self.peers[peer_id].known_events:
                            await self._send_event_to_peer(peer_id, event)
                            self.events_sent += 1

                sent_this_round += 1

                # 重新放入队列（递减TTL）
                event.decrement_ttl()
                if event.should_rebroadcast():
                    await self.pending_events.put(event)

            except asyncio.QueueEmpty:
                break

    def _select_gossip_targets(self, event: GossipEvent) -> List[str]:
        """
        选择Gossip目标节点

        优先选择：
        1. 不知道该事件的对等体
        2. 健康的的对等体
        3. 随机性（保证传播的随机性）
        """
        eligible = [
            pid for pid, peer in self.peers.items()
            if event.event_id not in peer.known_events and peer.is_healthy
        ]

        if not eligible:
            # 如果都已知，随机选择一些
            eligible = list(self.peers.keys())

        # 随机选择fanout个
        random.shuffle(eligible)
        return eligible[:self.fanout]

    async def _send_event_to_peer(self, peer_id: str, event: GossipEvent):
        """发送事件到对等体"""
        peer = self.peers[peer_id]

        try:
            # 模拟发送（实际使用WebSocket等）
            # await self._do_send(peer, event)

            # 标记为已知
            peer.known_events.add(event.event_id)

            # 记录反向推荐
            if event.event_type == GossipEventType.NODE_UP:
                peer.reverse_recommendations.append(event.node_id)

            peer.last_sync = datetime.now()
            peer.miss_count = 0

            # 更新统计
            self.bytes_transferred += len(str(event.data))

        except Exception:
            peer.miss_count += 1
            if peer.miss_count >= 3:
                peer.is_healthy = False

    async def _random_gossip_exchange(self):
        """
        随机Gossip交换

        与随机对等体交换已知道件列表
        实现拓扑同步
        """
        if len(self.peers) < 2:
            return

        # 随机选择一个对等体
        peer_ids = list(self.peers.keys())
        random_peer_id = random.choice(peer_ids)

        # 获取本地事件ID列表
        local_event_ids = set(self.event_history.keys())

        # 获取对端已知事件ID
        peer_known_ids = self.peers[random_peer_id].known_events

        # 计算差异
        need_from_peer = local_event_ids - peer_known_ids
        need_from_local = peer_known_ids - local_event_ids

        # 请求对端缺少的事件
        if need_from_peer:
            await self._request_events(random_peer_id, list(need_from_peer)[:10])

        # 向对端发送本地独有的事件
        for event_id in list(need_from_local)[:5]:
            if event_id in self.event_history:
                await self._send_event_to_peer(random_peer_id, self.event_history[event_id])

    async def _request_events(self, peer_id: str, event_ids: List[str]):
        """请求事件"""
        # 模拟请求（实际发送请求并等待响应）
        # await self._do_request(peer_id, event_ids)
        pass

    async def _cleanup_unhealthy_peers(self):
        """清理不健康对等体"""
        unhealthy = [
            pid for pid, peer in self.peers.items()
            if not peer.is_healthy and peer.miss_count >= 5
        ]

        for pid in unhealthy:
            del self.peers[pid]

    def _add_to_history(self, event: GossipEvent):
        """添加到事件历史"""
        self.event_history[event.event_id] = event

        # 限制历史大小
        if len(self.event_history) > self.event_history_max_size:
            # 删除最旧的事件
            oldest = min(
                self.event_history.items(),
                key=lambda x: x[1].timestamp
            )
            del self.event_history[oldest[0]]

    def get_network_health(self) -> Dict:
        """获取网络健康状态"""
        total_peers = len(self.peers)
        healthy_peers = sum(1 for p in self.peers.values() if p.is_healthy)

        return {
            "node_id": self.node_id,
            "total_peers": total_peers,
            "healthy_peers": healthy_peers,
            "events_in_history": len(self.event_history),
            "events_sent": self.events_sent,
            "events_received": self.events_received,
            "bytes_transferred": self.bytes_transferred,
            "pending_events": self.pending_events.qsize()
        }


class ReverseRecommendationEngine:
    """
    反向推荐引擎

    实现"客户端作为传播载体"的逻辑：
    客户端A从节点1获取了节点2的信息，
    当客户端A连接到节点3时，可以将节点2"反向推荐"给节点3
    """

    def __init__(self, gossip_protocol: GossipProtocol):
        self.gossip = gossip_protocol

        # 反向推荐缓存
        # client_id -> set of known nodes
        self.client_node_cache: Dict[str, Set[str]] = defaultdict(set)

        # 推荐权重
        self.recommendation_weights: Dict[str, float] = {
            GossipEventType.NODE_UP.value: 1.0,
            GossipEventType.NODE_QUALITY_UPDATE.value: 0.5,
        }

    async def register_client_nodes(self, client_id: str, node_ids: List[str]):
        """注册客户端已知的节点"""
        self.client_node_cache[client_id] = set(node_ids)

    async def unregister_client(self, client_id: str):
        """注销客户端"""
        if client_id in self.client_node_cache:
            del self.client_node_cache[client_id]

    async def get_reverse_recommendations(self, exclude_node_ids: Set[str]) -> List[Dict]:
        """
        获取反向推荐节点列表

        基于所有客户端缓存，计算应该推荐的节点
        """
        # 统计每个节点被多少客户端知道
        node_referral_count: Dict[str, int] = defaultdict(int)
        node_referral_quality: Dict[str, float] = defaultdict(float)

        for client_id, nodes in self.client_node_cache.items():
            for node_id in nodes:
                if node_id not in exclude_node_ids:
                    node_referral_count[node_id] += 1
                    # 考虑时间衰减（越新推荐权重越高）
                    node_referral_quality[node_id] += 1.0

        # 排序并返回Top N
        sorted_nodes = sorted(
            node_referral_count.items(),
            key=lambda x: x[1] * node_referral_quality[x[0]],
            reverse=True
        )

        return [
            {
                "node_id": node_id,
                "referral_count": count,
                "quality_score": node_referral_quality[node_id]
            }
            for node_id, count in sorted_nodes[:10]
        ]

    async def propagate_reverse_recommendation(self, from_client_id: str, to_peer_id: str):
        """
        将反向推荐传播给对等体

        当客户端连接到新节点时，
        将之前缓存的节点信息推荐给新节点
        """
        if from_client_id not in self.client_node_cache:
            return

        known_nodes = self.client_node_cache[from_client_id]

        # 构建推荐消息
        recommendation = {
            "type": "reverse_recommendation",
            "from_client": from_client_id,
            "nodes": list(known_nodes),
            "timestamp": datetime.now().isoformat()
        }

        # 通过Gossip传播
        event = GossipEvent(
            event_type=GossipEventType.NODE_ANNOUNCE,
            node_id=from_client_id,
            timestamp=datetime.now(),
            data=recommendation
        )

        await self.gossip.broadcast_event(event)


class SelfHealingManager:
    """
    自愈管理器

    监控网络状态，自动修复损坏的连接和缺失的节点
    """

    def __init__(
        self,
        gossip_protocol: GossipProtocol,
        connection_pool: Any = None,
        node_registry: Any = None
    ):
        config = UnifiedConfig.get_instance()
        
        self.gossip = gossip_protocol
        self.connection_pool = connection_pool
        self.node_registry = node_registry

        # 自愈配置
        self.node_timeout_seconds = 120
        self.health_check_interval = config.get("p2p_network.health_check_interval", 30)

        # 任务
        self._healing_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """启动自愈管理"""
        self._running = True
        self._healing_task = asyncio.create_task(self._healing_loop())

    async def stop(self):
        """停止自愈管理"""
        self._running = False

        if self._healing_task:
            self._healing_task.cancel()
            try:
                await self._healing_task
            except asyncio.CancelledError:
                pass

    async def _healing_loop(self):
        """自愈循环"""
        while self._running:
            await asyncio.sleep(self.health_check_interval)

            try:
                # 检测节点超时
                await self._detect_timed_out_nodes()

                # 尝试补充节点
                await self._ensure_minimum_nodes()

                # 修复断开的连接
                await self._heal_connections()

            except Exception:
                pass

    async def _detect_timed_out_nodes(self):
        """检测超时的节点"""
        if not self.node_registry:
            return

        nodes = await self.node_registry.get_all_nodes()
        now = datetime.now()

        for node in nodes:
            if node.last_seen:
                elapsed = (now - node.last_seen).total_seconds()
                if elapsed > self.node_timeout_seconds:
                    # 节点疑似死亡
                    await self.node_registry.update_node_status(
                        node.node_id,
                        "suspected"  # NodeStatus.SUSPECTED
                    )

                    # 通过Gossip广播
                    await self.gossip.announce_node_down(node.node_id)

    async def _ensure_minimum_nodes(self):
        """确保最小节点数"""
        if not self.node_registry:
            return

        nodes = await self.node_registry.get_alive_nodes()

        if len(nodes) < 5:
            # 节点数不足，尝试从已知对等体获取更多节点
            # 这里会触发Gossip请求
            pass

    async def _heal_connections(self):
        """修复断开的连接"""
        if not self.connection_pool:
            return

        status = self.connection_pool.get_pool_status()

        if status["connected"] < status["total_connections"]:
            # 有连接断开，尝试重新连接
            # 实际实现会根据节点注册表选择新节点
            pass
