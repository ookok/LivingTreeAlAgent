# propagation.py — 版本波纹扩散算法

"""
版本波纹扩散算法
================

核心理念：当一个节点升级到新版本时，向直接连接的节点广播"版本升级信号"，
形成涟漪式扩散，避免网络风暴。

机制设计：
1. 版本波纹扩散 - 类似水波纹的层层扩散
2. TTL 限制 - 防止无限传播
3. 去重机制 - 避免重复传播
4. 多源优先级 - 选择最优更新源
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable, Any
from enum import Enum
import random

from .models import (
    NodeInfo, VersionInfo, PropagationRecord, UpdateManifest,
    NodeState, generate_node_id
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class PropagationConfig:
    """传播配置"""
    max_ttl: int = 5                       # 最大 TTL
    fanout: int = 3                        # 每层扩散节点数
    max_depth: int = 5                     # 最大扩散深度
    deduplication_window: int = 300         # 去重窗口 (秒)
    cooldown_period: int = 60               # 相同版本冷却期 (秒)
    broadcast_interval: float = 10.0        # 广播间隔 (秒)


# ═══════════════════════════════════════════════════════════════════════════════
# 传播状态机
# ═══════════════════════════════════════════════════════════════════════════════


class PropagationState(Enum):
    """传播状态"""
    IDLE = "idle"           # 空闲
    PROPAGATING = "propagating"  # 传播中
    COOLDOWN = "cooldown"    # 冷却中
    COMPLETED = "completed"  # 完成


@dataclass
class PropagationContext:
    """传播上下文"""
    version: str                             # 正在传播的版本
    origin_node: str                          # 起源节点
    start_time: float = 0                     # 开始时间
    ttl: int = 0                              # 当前 TTL
    depth: int = 0                            # 当前深度
    state: PropagationState = PropagationState.IDLE
    received_from: Set[str] = field(default_factory=set)  # 已接收的节点列表
    sent_to: Set[str] = field(default_factory=set)       # 已发送的节点列表
    statistics: Dict[str, int] = field(default_factory=dict)  # 统计信息

    def __post_init__(self):
        if self.start_time == 0:
            self.start_time = time.time()


# ═══════════════════════════════════════════════════════════════════════════════
# 波纹扩散器
# ═══════════════════════════════════════════════════════════════════════════════


class RipplePropagator:
    """
    波纹扩散器

    实现版本波纹扩散算法：
    1. 当节点升级到新版本时，立即向直接连接的节点广播
    2. 接收节点验证后，再向自己的连接节点广播
    3. 形成涟漪式扩散，设置 TTL 防止无限传播
    """

    def __init__(self, config: PropagationConfig = None):
        self.config = config or PropagationConfig()
        self.contexts: Dict[str, PropagationContext] = {}  # version -> context
        self.pending_broadcasts: Dict[str, asyncio.Event] = {}  # version -> event
        self.recent_announcements: Dict[str, float] = {}  # node_id:version -> timestamp
        self.version_cooldowns: Dict[str, float] = {}  # node_id:version -> cooldown_until
        self._lock = asyncio.Lock()
        self._running = False
        self._tasks: List[asyncio.Task] = []

        # 回调函数
        self.on_version_announced: Optional[Callable] = None
        self.on_propagation_complete: Optional[Callable] = None

        logger.info("RipplePropagator initialized")

    @property
    def active_propagations(self) -> int:
        """活跃传播数"""
        return sum(
            1 for ctx in self.contexts.values()
            if ctx.state == PropagationState.PROPAGATING
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # 核心传播逻辑
    # ═══════════════════════════════════════════════════════════════════════════

    async def announce_version(
        self,
        version_info: VersionInfo,
        announcer: NodeInfo,
        origin: str = None,
        initial_ttl: int = None
    ):
        """
        宣告新版本（触发波纹扩散）

        Args:
            version_info: 版本信息
            announcer: 宣告节点
            origin: 起源节点（用于追踪）
            initial_ttl: 初始 TTL
        """
        key = f"{version_info.version}"
        initial_ttl = initial_ttl or self.config.max_ttl

        async with self._lock:
            # 检查冷却期
            cooldown_key = f"{announcer.node_id}:{version_info.version}"
            if cooldown_key in self.version_cooldowns:
                if time.time() < self.version_cooldowns[cooldown_key]:
                    logger.debug(f"Version {version_info.version} in cooldown for {announcer.node_id[:8]}")
                    return

            # 创建或更新传播上下文
            if key not in self.contexts:
                self.contexts[key] = PropagationContext(
                    version=version_info.version,
                    origin_node=origin or announcer.node_id,
                    ttl=initial_ttl,
                    state=PropagationState.PROPAGATING
                )

            ctx = self.contexts[key]
            ctx.received_from.add(announcer.node_id)

        # 设置冷却期
        self.version_cooldowns[cooldown_key] = time.time() + self.config.cooldown_period

        # 触发回调
        if self.on_version_announced:
            try:
                await self.on_version_announced(version_info, announcer)
            except Exception as e:
                logger.error(f"Version announced callback error: {e}")

        logger.info(
            f"Version {version_info.version} announced by {announcer.node_id[:8]}, "
            f"TTL={initial_ttl}, origin={origin or announcer.node_id[:8]}"
        )

    async def propagate_to_peers(
        self,
        version_info: VersionInfo,
        source_node: NodeInfo,
        available_peers: List[NodeInfo],
        hop: int = 0
    ):
        """
        向邻居节点传播版本

        Args:
            version_info: 版本信息
            source_node: 接收到的来源节点
            available_peers: 可用的邻居节点列表
            hop: 当前跳数
        """
        if hop >= self.config.max_depth:
            logger.debug(f"Max depth reached for {version_info.version}")
            return

        async with self._lock:
            key = f"{version_info.version}"
            if key not in self.contexts:
                return

            ctx = self.contexts[key]

            # 检查 TTL
            if ctx.ttl <= 0:
                ctx.state = PropagationState.COMPLETED
                return

            # 消耗 TTL
            ctx.ttl -= 1
            ctx.depth = max(ctx.depth, hop)

        # 选择最优 peers 进行传播（多源优先级策略）
        selected_peers = self._select_best_peers(
            version_info,
            available_peers,
            exclude={source_node.node_id, ctx.origin_node}
        )

        if not selected_peers:
            logger.debug(f"No peers to propagate for {version_info.version}")
            return

        # 向选中的 peers 发送传播
        for peer in selected_peers:
            if peer.node_id in ctx.sent_to:
                continue

            ctx.sent_to.add(peer.node_id)

            # 实际实现中这里会发送网络消息
            # 简化处理：触发回调
            if self.on_propagation_complete:
                try:
                    await self.on_propagation_complete(version_info, source_node, peer, hop + 1)
                except Exception as e:
                    logger.error(f"Propagation callback error: {e}")

            logger.debug(
                f"Propagated {version_info.version} to {peer.node_id[:8]} "
                f"(hop={hop + 1}, ttl={ctx.ttl})"
            )

        # 更新统计
        ctx.statistics['total_sent'] = len(ctx.sent_to)
        ctx.statistics['unique_peers'] = len(ctx.sent_to - ctx.received_from)

    def _select_best_peers(
        self,
        version_info: VersionInfo,
        peers: List[NodeInfo],
        exclude: Set[str] = None
    ) -> List[NodeInfo]:
        """
        选择最优的 peers 进行传播

        多源优先级策略：
        1. 网络距离（优先同 ISP/同地区）
        2. 节点信誉分（历史分发成功率）
        3. 带宽能力（高带宽节点优先）
        4. 版本新鲜度（刚更新的节点优先）
        5. 连接稳定性（长连接节点优先）
        """
        exclude = exclude or set()

        # 过滤排除的节点
        candidates = [p for p in peers if p.node_id not in exclude]

        if not candidates:
            return []

        # 计算优先级分数
        scored_peers = []
        for peer in candidates:
            score = self._calculate_peer_priority(version_info, peer)
            scored_peers.append((peer, score))

        # 按分数降序排序
        scored_peers.sort(key=lambda x: x[1], reverse=True)

        # 返回 top N
        return [peer for peer, _ in scored_peers[:self.config.fanout]]

    def _calculate_peer_priority(
        self,
        version_info: VersionInfo,
        peer: NodeInfo
    ) -> float:
        """
        计算节点的传播优先级分数

        权重分配：
        - 信誉分: 35%
        - 带宽分: 25%
        - 稳定性: 20%
        - 版本新鲜度: 20%
        """
        # 信誉分 (0-100) * 0.35
        reputation = peer.reputation_score * 0.35

        # 带宽分 (0-100) * 0.25
        bandwidth = peer.bandwidth_score * 0.25

        # 稳定性分 (0-100) * 0.20
        stability = peer.stability_score * 0.20

        # 版本新鲜度：节点当前版本越接近新版本，说明越活跃
        freshness = min(100, (peer.reputation_score * 0.2))

        total = reputation + bandwidth + stability + freshness

        # 信誉等级加成
        if peer.reputation_level.value >= 3:  # HIGHLY_TRUSTED 或 AUTHORITY
            total *= 1.2

        return total

    # ═══════════════════════════════════════════════════════════════════════════
    # 去重机制
    # ═══════════════════════════════════════════════════════════════════════════

    async def should_propagate(self, version: str, sender: str) -> bool:
        """
        检查是否应该传播（去重）

        Returns:
            True 如果之前没有收到过这个版本的宣告
        """
        key = f"{sender}:{version}"

        async with self._lock:
            now = time.time()

            # 检查去重窗口
            if key in self.recent_announcements:
                if now - self.recent_announcements[key] < self.config.deduplication_window:
                    return False

            # 记录宣告
            self.recent_announcements[key] = now

            # 清理过期记录
            expired = [k for k, t in self.recent_announcements.items()
                      if now - t > self.config.deduplication_window * 2]
            for k in expired:
                del self.recent_announcements[k]

            return True

    # ═══════════════════════════════════════════════════════════════════════════
    # 生命周期管理
    # ═══════════════════════════════════════════════════════════════════════════

    async def start(self):
        """启动传播器"""
        if self._running:
            return

        self._running = True
        self._tasks.append(asyncio.create_task(self._cleanup_loop()))

        logger.info("RipplePropagator started")

    async def stop(self):
        """停止传播器"""
        self._running = False

        for task in self._tasks:
            task.cancel()

        self._tasks.clear()
        logger.info("RipplePropagator stopped")

    async def _cleanup_loop(self):
        """清理过期上下文"""
        while self._running:
            try:
                await asyncio.sleep(60)
                await self._cleanup_contexts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

    async def _cleanup_contexts(self):
        """清理已完成的传播上下文"""
        async with self._lock:
            now = time.time()
            completed_keys = []

            for key, ctx in self.contexts.items():
                # 移除超过 1 小时的上下文
                if now - ctx.start_time > 3600:
                    completed_keys.append(key)

            for key in completed_keys:
                del self.contexts[key]

            if completed_keys:
                logger.debug(f"Cleaned up {len(completed_keys)} propagation contexts")


# ═══════════════════════════════════════════════════════════════════════════════
# 版本查询器
# ═══════════════════════════════════════════════════════════════════════════════


class VersionQuerier:
    """
    版本查询器

    用于主动查询网络中的最新版本
    """

    def __init__(self):
        self.pending_queries: Dict[str, asyncio.Future] = {}
        self.query_history: Dict[str, float] = {}  # version -> last_query_time
        self.query_cooldown = 60  # 查询冷却期 (秒)

    async def query_version(
        self,
        app_id: str,
        current_version: str = None,
        timeout: float = 30.0
    ) -> Optional[VersionInfo]:
        """
        查询最新版本

        Args:
            app_id: 应用ID
            current_version: 当前版本
            timeout: 超时时间

        Returns:
            最新版本信息
        """
        # 检查查询冷却
        query_key = f"{app_id}:{current_version or 'any'}"
        now = time.time()

        if query_key in self.query_history:
            if now - self.query_history[query_key] < self.query_cooldown:
                logger.debug(f"Query in cooldown: {query_key}")
                return None

        self.query_history[query_key] = now

        # 创建查询 future
        future = asyncio.Future()
        self.pending_queries[query_key] = future

        try:
            # 等待结果或超时
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Query timeout: {query_key}")
            return None
        finally:
            self.pending_queries.pop(query_key, None)

    async def on_version_discovered(self, version: VersionInfo, source: str):
        """当发现版本时通知等待的查询"""
        for key, future in self.pending_queries.items():
            if not future.done():
                future.set_result(version)
                break


# ═══════════════════════════════════════════════════════════════════════════════
# 全局实例
# ═══════════════════════════════════════════════════════════════════════════════


_propagator: Optional[RipplePropagator] = None
_querier: Optional[VersionQuerier] = None


def get_propagator() -> RipplePropagator:
    """获取全局波纹扩散器"""
    global _propagator
    if _propagator is None:
        _propagator = RipplePropagator()
    return _propagator


def get_querier() -> VersionQuerier:
    """获取全局版本查询器"""
    global _querier
    if _querier is None:
        _querier = VersionQuerier()
    return _querier
