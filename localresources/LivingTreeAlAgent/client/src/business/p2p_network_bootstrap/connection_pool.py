# -*- coding: utf-8 -*-
"""
Phase 2: 连接池与QoS自动切换
P2P网络自举协议 - 智能连接池管理

核心理念：
- 客户端维护多个连接，基于QoS自动选择最优路径
- 连接池动态调整，根据网络状况自动切换
- 节点下线时自动迁移到备用节点

作者：Hermes Desktop V2.0
版本：1.0.0
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
import random


class ConnectionStatus(Enum):
    """连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class ConnectionQuality(Enum):
    """连接质量"""
    EXCELLENT = "excellent"   # < 50ms, 0% 丢包
    GOOD = "good"            # < 150ms, < 5% 丢包
    FAIR = "fair"            # < 300ms, < 10% 丢包
    POOR = "poor"            # >= 300ms 或 >= 10% 丢包


@dataclass
class ConnectionMetrics:
    """连接指标"""
    latency_ms: float = 0.0
    packet_loss_rate: float = 0.0
    last_probe: Optional[datetime] = None
    probe_count: int = 0

    # 滑动窗口统计
    latency_history: List[float] = field(default_factory=list)
    packet_loss_history: List[float] = field(default_factory=list)

    def update_latency(self, latency: float):
        """更新延迟"""
        self.latency_ms = latency
        self.last_probe = datetime.now()
        self.probe_count += 1

        # 保持历史记录（最多10条）
        self.latency_history.append(latency)
        if len(self.latency_history) > 10:
            self.latency_history.pop(0)

    def update_packet_loss(self, loss_rate: float):
        """更新丢包率"""
        self.packet_loss_rate = loss_rate
        self.packet_loss_history.append(loss_rate)
        if len(self.packet_loss_history) > 10:
            self.packet_loss_history.pop(0)

    def get_average_latency(self) -> float:
        """获取平均延迟"""
        if not self.latency_history:
            return self.latency_ms
        return sum(self.latency_history) / len(self.latency_history)

    def get_average_packet_loss(self) -> float:
        """获取平均丢包率"""
        if not self.packet_loss_history:
            return self.packet_loss_rate
        return sum(self.packet_loss_history) / len(self.packet_loss_history)

    def calculate_quality(self) -> ConnectionQuality:
        """计算连接质量"""
        avg_latency = self.get_average_latency()
        avg_loss = self.get_average_packet_loss()

        if avg_latency < 50 and avg_loss < 0.01:
            return ConnectionQuality.EXCELLENT
        elif avg_latency < 150 and avg_loss < 0.05:
            return ConnectionQuality.GOOD
        elif avg_latency < 300 and avg_loss < 0.10:
            return ConnectionQuality.FAIR
        else:
            return ConnectionQuality.POOR


@dataclass
class Connection:
    """连接对象"""
    connection_id: str
    node_id: str
    url: str

    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    metrics: ConnectionMetrics = field(default_factory=ConnectionMetrics)

    # 连接属性
    is_primary: bool = False      # 是否主连接
    is_backup: bool = False       # 是否备用连接
    failover_count: int = 0       # 故障转移次数

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    connected_at: Optional[datetime] = None
    last_active: datetime = field(default_factory=datetime.now)

    # 底层连接（WebSocket等）
    _connection: Optional[Any] = None

    def quality_score(self) -> float:
        """计算质量分数 0-100"""
        if self.status != ConnectionStatus.CONNECTED:
            return 0

        quality = self.metrics.calculate_quality()

        scores = {
            ConnectionQuality.EXCELLENT: 100,
            ConnectionQuality.GOOD: 80,
            ConnectionQuality.FAIR: 60,
            ConnectionQuality.POOR: 30
        }

        return scores.get(quality, 0)


class ConnectionPool:
    """
    连接池管理器 - Phase 2 核心

    功能：
    1. 维护多个节点连接
    2. 基于QoS自动选择最优连接
    3. 故障自动转移
    4. 连接池动态调整
    """

    def __init__(
        self,
        client_id: str,
        min_connections: int = 2,
        max_connections: int = 5,
        probe_interval: int = 10  # 探测间隔（秒）
    ):
        self.client_id = client_id

        # 连接池配置
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.probe_interval = probe_interval

        # 连接管理
        self.connections: Dict[str, Connection] = {}
        self.primary_connection: Optional[Connection] = None

        # 节点注册表引用
        self.node_registry: Optional[Any] = None

        # 回调
        self.on_connection_established: Optional[Callable] = None
        self.on_connection_lost: Optional[Callable] = None
        self.on_failover: Optional[Callable] = None
        self.on_quality_change: Optional[Callable] = None

        # 统计
        self.total_failovers = 0
        self.last_failover_time: Optional[datetime] = None

        # 内部任务
        self._probe_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """启动连接池"""
        self._running = True
        self._probe_task = asyncio.create_task(self._probe_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self):
        """停止连接池"""
        self._running = False

        if self._probe_task:
            self._probe_task.cancel()
            try:
                await self._probe_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # 关闭所有连接
        for conn in self.connections.values():
            await self._close_connection(conn)

    async def add_node(self, node_info: Dict) -> Optional[Connection]:
        """
        添加节点到连接池

        评估节点质量后建立连接
        """
        node_id = node_info["node_id"]

        # 如果已存在，跳过
        if node_id in self.connections:
            return self.connections[node_id]

        # 如果连接池已满，移除最差的连接
        if len(self.connections) >= self.max_connections:
            await self._evict_worst_connection()

        # 创建连接
        conn = Connection(
            connection_id=f"{self.client_id}_{node_id}",
            node_id=node_id,
            url=node_info["url"]
        )

        self.connections[node_id] = conn

        # 建立连接
        await self._establish_connection(conn)

        # 如果没有主连接，设为主连接
        if self.primary_connection is None and conn.status == ConnectionStatus.CONNECTED:
            await self._promote_to_primary(conn)

        return conn

    async def remove_node(self, node_id: str):
        """从连接池移除节点"""
        if node_id not in self.connections:
            return

        conn = self.connections[node_id]

        # 如果是主连接，先故障转移
        if self.primary_connection and self.primary_connection.node_id == node_id:
            await self._failover_to_best()

        await self._close_connection(conn)
        del self.connections[node_id]

    async def get_best_connection(self) -> Optional[Connection]:
        """获取最优连接"""
        connected = [
            c for c in self.connections.values()
            if c.status == ConnectionStatus.CONNECTED
        ]

        if not connected:
            return None

        # 按质量分数排序
        connected.sort(key=lambda c: c.quality_score(), reverse=True)
        return connected[0]

    async def get_or_create_connection(self, node_id: str) -> Optional[Connection]:
        """获取或创建到指定节点的连接"""
        if node_id in self.connections:
            conn = self.connections[node_id]
            if conn.status == ConnectionStatus.CONNECTED:
                return conn
            # 如果连接断开，尝试重连
            await self._establish_connection(conn)
            return conn

        # 需要创建新连接
        # 这里应该从节点注册表获取节点信息
        # 简化实现，返回None
        return None

    async def switch_to_best(self) -> bool:
        """
        切换到最优连接

        如果当前连接质量下降，自动切换到更优的备用连接
        """
        current = self.primary_connection
        best = await self.get_best_connection()

        if best and current and best.node_id != current.node_id:
            # 质量差异足够大时才切换
            quality_diff = best.quality_score() - current.quality_score()
            if quality_diff > 20:  # 20分差距
                await self._promote_to_primary(best)
                return True

        return False

    async def _establish_connection(self, conn: Connection):
        """建立连接"""
        conn.status = ConnectionStatus.CONNECTING

        try:
            # 模拟连接建立（实际使用WebSocket）
            # await self._do_connect(conn)

            conn.status = ConnectionStatus.CONNECTED
            conn.connected_at = datetime.now()
            conn.last_active = datetime.now()

            # 初始探测
            await self._probe_connection(conn)

        except Exception as e:
            conn.status = ConnectionStatus.FAILED

    async def _close_connection(self, conn: Connection):
        """关闭连接"""
        conn.status = ConnectionStatus.DISCONNECTED
        # 实际关闭底层连接
        # if conn._connection:
        #     await conn._connection.close()

    async def _promote_to_primary(self, conn: Connection):
        """提升为主连接"""
        # 降级原主连接
        if self.primary_connection:
            self.primary_connection.is_primary = False

        # 提升新主连接
        conn.is_primary = True
        self.primary_connection = conn

        if self.on_connection_established:
            await self.on_connection_established(conn)

    async def _failover_to_best(self):
        """故障转移到最优连接"""
        best = await self.get_best_connection()

        if best and best.node_id != self.primary_connection.node_id:
            await self._promote_to_primary(best)
            self.total_failovers += 1
            self.last_failover_time = datetime.now()

            if self.on_failover:
                await self.on_failover(best)

    async def _evict_worst_connection(self):
        """移除最差连接"""
        if not self.connections:
            return

        worst = min(
            self.connections.values(),
            key=lambda c: c.quality_score()
        )

        await self.remove_node(worst.node_id)

    async def _probe_connection(self, conn: Connection):
        """探测连接质量"""
        try:
            # 模拟探测（实际发送探测包并测量延迟）
            start = datetime.now()
            # await self._send_probe(conn)
            end = datetime.now()

            latency = (end - start).total_seconds() * 1000

            # 模拟丢包率
            packet_loss = random.uniform(0, 0.05)

            conn.metrics.update_latency(latency)
            conn.metrics.update_packet_loss(packet_loss)

            # 更新连接状态
            quality = conn.metrics.calculate_quality()
            if quality == ConnectionQuality.POOR:
                conn.status = ConnectionStatus.DEGRADED

            if self.on_quality_change:
                await self.on_quality_change(conn, quality)

        except Exception:
            conn.status = ConnectionStatus.DEGRADED

    async def _probe_loop(self):
        """探测循环"""
        while self._running:
            await asyncio.sleep(self.probe_interval)

            for conn in self.connections.values():
                if conn.status in [ConnectionStatus.CONNECTED, ConnectionStatus.DEGRADED]:
                    await self._probe_connection(conn)

            # 检查是否需要切换
            await self.switch_to_best()

    async def _cleanup_loop(self):
        """清理循环"""
        while self._running:
            await asyncio.sleep(60)  # 每分钟清理

            # 移除失败的连接
            failed = [
                node_id for node_id, conn in self.connections.items()
                if conn.status == ConnectionStatus.FAILED
            ]

            for node_id in failed:
                await self.remove_node(node_id)

            # 确保最小连接数
            connected_count = sum(
                1 for c in self.connections.values()
                if c.status == ConnectionStatus.CONNECTED
            )

            if connected_count < self.min_connections:
                # 需要添加新连接
                if self.node_registry:
                    nodes = await self.node_registry.get_alive_nodes()
                    for node in nodes[:self.min_connections - connected_count]:
                        if node.node_id not in self.connections:
                            await self.add_node({
                                "node_id": node.node_id,
                                "url": node.url
                            })

    def get_pool_status(self) -> Dict:
        """获取连接池状态"""
        total = len(self.connections)
        connected = sum(
            1 for c in self.connections.values()
            if c.status == ConnectionStatus.CONNECTED
        )

        return {
            "total_connections": total,
            "connected": connected,
            "primary_node": self.primary_connection.node_id if self.primary_connection else None,
            "primary_quality": self.primary_connection.quality_score() if self.primary_connection else 0,
            "total_failovers": self.total_failovers,
            "last_failover": self.last_failover_time.isoformat() if self.last_failover_time else None,
            "connections": {
                node_id: {
                    "status": conn.status.value,
                    "quality": conn.metrics.calculate_quality().value,
                    "latency_ms": conn.metrics.get_average_latency(),
                    "is_primary": conn.is_primary
                }
                for node_id, conn in self.connections.items()
            }
        }


class QoSRouter:
    """
    QoS路由器 - 基于质量的智能路由

    根据连接质量自动选择最优路径
    实现网络拓扑的客户端驱动优化
    """

    def __init__(self, connection_pool: ConnectionPool):
        self.pool = connection_pool

        # 路由策略
        self.prefer_low_latency = True
        self.prefer_low_packet_loss = True

        # 阈值
        self.latency_threshold_ms = 200
        self.packet_loss_threshold = 0.05

    async def route_message(self, message: Dict) -> Optional[str]:
        """
        路由消息到最优连接

        返回选中的节点ID
        """
        best = await self.pool.get_best_connection()

        if not best:
            return None

        # 检查质量是否满足阈值
        quality = best.metrics.calculate_quality()

        if quality == ConnectionQuality.POOR:
            # 质量太差，尝试切换
            switched = await self.pool.switch_to_best()
            if switched:
                best = await self.pool.get_best_connection()

        return best.node_id if best else None

    async def should_migrate(self) -> bool:
        """
        判断是否应该迁移连接

        当发现更优质的节点时触发迁移
        """
        current = self.pool.primary_connection
        if not current:
            return True

        best = await self.pool.get_best_connection()
        if not best:
            return False

        # 质量差异超过阈值
        diff = best.quality_score() - current.quality_score()
        return diff > 30  # 30分差距


class AdaptiveTopologyManager:
    """
    自适应拓扑管理器

    根据客户端的探测数据，动态更新网络拓扑
    实现"客户端拉动的自适应网络"
    """

    def __init__(self, connection_pool: ConnectionPool, node_registry: Any):
        self.pool = connection_pool
        self.registry = node_registry

        # 探测结果缓存
        self.probe_cache: Dict[str, List[ConnectionMetrics]] = defaultdict(list)

    async def report_probe_result(self, node_id: str, metrics: ConnectionMetrics):
        """
        上报探测结果到拓扑管理器

        节点可以根据客户端的探测结果更新节点质量
        """
        self.probe_cache[node_id].append(metrics)

        # 保持缓存大小
        if len(self.probe_cache[node_id]) > 100:
            self.probe_cache[node_id] = self.probe_cache[node_id][-100:]

        # 计算平均质量并更新注册表
        if node_id in self.probe_cache:
            caches = self.probe_cache[node_id]
            avg_latency = sum(c.latency_ms for c in caches) / len(caches)
            avg_loss = sum(c.packet_loss_rate for c in caches) / len(caches)

            # 更新注册表中的节点
            node = await self.registry.get_node(node_id)
            if node:
                node.latency_ms = avg_latency
                node.packet_loss_rate = avg_loss
                node.update_weight()

    async def get_optimized_topology(self) -> Dict:
        """
        获取优化后的拓扑

        基于客户端探测数据，生成优化拓扑
        """
        topology = await self.registry.get_topology()

        # 按客户端视角的质量重新排序
        nodes = sorted(
            topology.nodes,
            key=lambda n: n.weight,
            reverse=True
        )

        return {
            "nodes": [n.node_id for n in nodes],
            "version": topology.version,
            "optimization": "client_probed"
        }
