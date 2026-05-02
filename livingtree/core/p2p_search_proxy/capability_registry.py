"""
P2P 搜索代理能力注册表

管理外网节点的能力发现与注册
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional
from dataclasses import dataclass, field

from .models import (
    PeerSearchCapability, PeerCapability, SearchTask,
    SearchResultStatus, SearchRouteDecision, P2PSearchConfig
)

logger = logging.getLogger(__name__)


class CapabilityRegistry:
    """
    节点能力注册表

    管理外网节点的能力发现、注册、健康检测
    """

    def __init__(self, config: Optional[P2PSearchConfig] = None):
        self.config = config or P2PSearchConfig()
        self._capabilities: dict[str, PeerSearchCapability] = {}
        self._lock = asyncio.Lock()

        # 健康检测
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """启动注册表"""
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Capability registry started")

    async def stop(self):
        """停止注册表"""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Capability registry stopped")

    async def register_peer(self, capability: PeerSearchCapability):
        """
        注册节点能力

        Args:
            capability: 节点能力信息
        """
        async with self._lock:
            existing = self._capabilities.get(capability.node_id)

            if existing:
                # 更新现有节点
                existing.capabilities = capability.capabilities
                existing.last_seen = time.time()
                existing.latency_ms = min(existing.latency_ms, capability.latency_ms)
                logger.debug(f"Updated peer capability: {capability.node_id}")
            else:
                # 新节点
                self._capabilities[capability.node_id] = capability
                logger.info(f"Registered new peer: {capability.node_id} "
                           f"(external_net={capability.has_external_net()}, "
                           f"search_tools={capability.has_search_tools()})")

    async def unregister_peer(self, node_id: str):
        """注销节点"""
        async with self._lock:
            if node_id in self._capabilities:
                del self._capabilities[node_id]
                logger.info(f"Unregistered peer: {node_id}")

    async def update_peer_stats(self, node_id: str, success: bool, latency_ms: float = 0.0):
        """更新节点统计"""
        async with self._lock:
            cap = self._capabilities.get(node_id)
            if cap:
                if success:
                    cap.search_success_count += 1
                else:
                    cap.search_fail_count += 1
                if latency_ms > 0:
                    cap.latency_ms = (cap.latency_ms + latency_ms) / 2
                cap.last_seen = time.time()

    async def find_best_peer(self, require_external_net: bool = True) -> Optional[PeerSearchCapability]:
        """
        查找最优节点

        Args:
            require_external_net: 是否必须有外网访问能力

        Returns:
            最优节点，如果不存在返回None
        """
        async with self._lock:
            candidates = []

            for node_id, cap in self._capabilities.items():
                # 检查基础能力
                if require_external_net and not cap.has_external_net():
                    continue

                if not cap.has_search_tools():
                    continue

                # 检查可靠性
                if not cap.is_reliable():
                    continue

                # 检查优先级
                priority = cap.get_priority()
                if priority < self.config.min_peer_priority:
                    continue

                # 检查活跃度
                if time.time() - cap.last_seen > 300:  # 5分钟不活跃
                    continue

                candidates.append((node_id, priority))

            if not candidates:
                return None

            # 按优先级排序
            candidates.sort(key=lambda x: x[1], reverse=True)
            return self._capabilities[candidates[0][0]]

    async def find_peers_by_capability(
        self,
        capabilities: int,
        min_count: int = 1
    ) -> list[PeerSearchCapability]:
        """
        按能力查找节点

        Args:
            capabilities: 能力位掩码
            min_count: 最少需要的节点数

        Returns:
            符合条件的节点列表
        """
        async with self._lock:
            results = []

            for node_id, cap in self._capabilities.items():
                if cap.capabilities & capabilities == capabilities:
                    if cap.is_reliable() and (time.time() - cap.last_seen) < 300:
                        results.append(cap)

            # 按优先级排序
            results.sort(key=lambda x: x.get_priority(), reverse=True)
            return results[:min_count]

    def get_all_peers(self) -> list[PeerSearchCapability]:
        """获取所有注册的节点"""
        return list(self._capabilities.values())

    def get_peer_count(self) -> int:
        """获取节点数量"""
        return len(self._capabilities)

    async def get_best_route(self, task: SearchTask) -> SearchRouteDecision:
        """
        获取最佳路由决策

        Args:
            task: 搜索任务

        Returns:
            路由决策
        """
        # 策略1: 如果强制使用P2P
        if task.use_p2p:
            peer = await self.find_best_peer()
            if peer:
                return SearchRouteDecision(
                    route_type="p2p",
                    target_node=peer.node_id,
                    reason="Forced P2P mode",
                    estimated_latency_ms=peer.latency_ms + 200,
                    confidence=0.9
                )
            return SearchRouteDecision(
                route_type="error",
                reason="No P2P peer available"
            )

        # 策略2: 如果不强制P2P，先检查直连是否可能
        # （这里简化处理，实际可能需要探测）

        # 策略3: 查找最优P2P节点
        peer = await self.find_best_peer()

        if not peer:
            return SearchRouteDecision(
                route_type="direct",
                reason="No external peer available, try direct",
                confidence=0.5
            )

        # 比较直连和P2P的预估延迟
        # 假设直连延迟为 500ms，P2P额外开销 200ms
        direct_latency = 500.0
        p2p_latency = peer.latency_ms + 200

        if self.config.prefer_direct and direct_latency <= p2p_latency * 1.5:
            return SearchRouteDecision(
                route_type="direct",
                reason="Direct connection is fast enough",
                estimated_latency_ms=direct_latency,
                confidence=0.7
            )

        return SearchRouteDecision(
            route_type="p2p",
            target_node=peer.node_id,
            reason=f"Better route via peer {peer.node_id[:8]}",
            estimated_latency_ms=p2p_latency,
            confidence=0.8
        )

    async def _health_check_loop(self):
        """健康检测循环"""
        while self._running:
            try:
                await asyncio.sleep(60)  # 每分钟检测

                async with self._lock:
                    now = time.time()
                    stale_nodes = []

                    for node_id, cap in self._capabilities.items():
                        # 移除10分钟不活跃的节点
                        if now - cap.last_seen > 600:
                            stale_nodes.append(node_id)

                    for node_id in stale_nodes:
                        del self._capabilities[node_id]
                        logger.info(f"Removed stale peer: {node_id}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
