"""
LivingTree Relay 节点管理与消息传输
====================================

合并 relay_chain 的 node_manager + monitor, relay_router 的 connection_manager + health_monitor,
decentralized_mailbox 的 message_router + relay_sync 为两个统一模块:

1. NodeRegistry — 中继节点注册、健康监控、负载均衡
2. MessageTransport — 统一消息投递（P2P 直接 → 中继 → 离线队列）

Author: LivingTreeAI Team
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import heapq
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from loguru import logger

from .models import (
    RelayNode, HealthReport, NodeRole,
    MailMessage, MessageChannel, MessageStatus,
)


# ============================================================================
# 节点注册中心
# ============================================================================

class NodeRegistry:
    """
    节点注册中心

    合并 relay_chain/node_manager.py (Registry + NodeManager)
    和 relay_chain/event_ext/p2p_network/distributed_node.py (peer discovery)

    功能:
    - 节点注册/注销
    - 健康检查（周期性）
    - 负载均衡（最低负载优先）
    - 节点选择（按角色/能力过滤）
    """

    def __init__(
        self,
        health_check_interval: float = 10.0,
        max_failures: int = 5,
    ):
        self._nodes: Dict[str, RelayNode] = {}         # node_id → RelayNode
        self.health_check_interval = health_check_interval
        self.max_failures = max_failures

        # 健康回调
        self._on_node_down: List[Callable] = []
        self._on_node_recovered: List[Callable] = []

        # 后台任务
        self._running = False
        self._health_task: Optional[asyncio.Task] = None

    # ── CRUD ──────────────────────────────────────────────

    def register(self, node: RelayNode) -> None:
        """注册节点"""
        is_new = node.node_id not in self._nodes
        self._nodes[node.node_id] = node
        if is_new:
            logger.info(f"节点注册: {node.node_id[:8]}... role={node.role.value} "
                        f"addr={node.host}:{node.port}")

    def unregister(self, node_id: str) -> Optional[RelayNode]:
        """注销节点"""
        return self._nodes.pop(node_id, None)

    def get(self, node_id: str) -> Optional[RelayNode]:
        return self._nodes.get(node_id)

    def list_nodes(
        self,
        role: Optional[NodeRole] = None,
        healthy_only: bool = True,
        active_only: bool = True,
    ) -> List[RelayNode]:
        """列出节点（支持过滤）"""
        nodes = list(self._nodes.values())
        if role:
            nodes = [n for n in nodes if n.role == role]
        if healthy_only:
            nodes = [n for n in nodes if n.is_healthy]
        if active_only:
            nodes = [n for n in nodes if n.is_active]
        return nodes

    # ── 节点选择 ──────────────────────────────────────────

    def select_relay(self, strategy: str = "least_loaded") -> Optional[RelayNode]:
        """
        选择一个可用中继节点

        策略:
        - least_loaded: 选择负载最低的节点
        - lowest_latency: 选择延迟最低的节点
        - round_robin: 轮询（需外部维护状态）
        - random: 随机选择
        """
        available = [
            n for n in self._nodes.values()
            if n.role in (NodeRole.RELAY, NodeRole.VALIDATOR)
            and n.is_available()
        ]
        if not available:
            return None

        if strategy == "least_loaded":
            return min(available, key=lambda n: n.load_score)
        elif strategy == "lowest_latency":
            return min(available, key=lambda n: n.latency_ms)
        elif strategy == "random":
            import random
            return random.choice(available)
        else:
            return available[0]

    def select_relays(self, count: int, strategy: str = "least_loaded") -> List[RelayNode]:
        """选择多个中继节点"""
        available = [
            n for n in self._nodes.values()
            if n.role in (NodeRole.RELAY, NodeRole.VALIDATOR)
            and n.is_available()
        ]
        if strategy == "least_loaded":
            available.sort(key=lambda n: n.load_score)
        elif strategy == "lowest_latency":
            available.sort(key=lambda n: n.latency_ms)
        return available[:count]

    # ── 健康检查 ──────────────────────────────────────────

    async def start_health_checks(self) -> None:
        """启动后台健康检查"""
        if self._running:
            return
        self._running = True
        self._health_task = asyncio.create_task(self._health_check_loop())
        logger.info("健康检查已启动")

    async def stop_health_checks(self) -> None:
        """停止健康检查"""
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            self._health_task = None
        logger.info("健康检查已停止")

    async def _health_check_loop(self) -> None:
        """健康检查循环"""
        while self._running:
            await self._check_all_nodes()
            await asyncio.sleep(self.health_check_interval)

    async def _check_all_nodes(self) -> None:
        """检查所有节点健康状态"""
        for node in list(self._nodes.values()):
            if not node.is_active:
                continue
            report = await self._check_node(node)
            if not report.is_healthy:
                logger.warning(f"节点不健康: {node.node_id[:8]}... {report.error_message}")

    async def _check_node(self, node: RelayNode) -> HealthReport:
        """检查单个节点"""
        try:
            start = time.monotonic()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(node.host, node.port),
                timeout=5.0,
            )
            latency = (time.monotonic() - start) * 1000
            writer.close()
            await writer.wait_closed()

            node.record_success(latency)
            return HealthReport(
                node_id=node.node_id,
                is_healthy=True,
                latency_ms=latency,
            )
        except Exception as e:
            was_healthy = node.is_healthy
            node.record_failure()
            if was_healthy and not node.is_healthy:
                for cb in self._on_node_down:
                    try:
                        cb(node)
                    except Exception:
                        pass
            return HealthReport(
                node_id=node.node_id,
                is_healthy=False,
                error_message=str(e),
            )

    def on_node_down(self, callback: Callable) -> None:
        self._on_node_down.append(callback)

    def on_node_recovered(self, callback: Callable) -> None:
        self._on_node_recovered.append(callback)

    # ── 统计 ──────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        nodes = list(self._nodes.values())
        return {
            "total_nodes": len(nodes),
            "healthy_nodes": sum(1 for n in nodes if n.is_healthy),
            "active_nodes": sum(1 for n in nodes if n.is_active),
            "by_role": {
                role.value: sum(1 for n in nodes if n.role == role)
                for role in NodeRole
            },
            "avg_latency_ms": (
                sum(n.latency_ms for n in nodes) / len(nodes) if nodes else 0
            ),
        }


# ============================================================================
# 消息传输层
# ============================================================================

class MessageTransport:
    """
    统一消息传输层

    合并 decentralized_mailbox/message_router.py 和 relay_chain/sync_protocol.py

    投递策略（按优先级）:
    1. P2P_DIRECT — 对等直连（如果接收方在线）
    2. RELAY      — 通过中继节点转发
    3. EXTERNAL   — IMAP/SMTP 外部邮件
    4. OFFLINE    — 离线队列，等待对方上线

    重试机制: 指数退避 (backoff=2.0^retry)
    """

    def __init__(
        self,
        node_registry: NodeRegistry,
        max_queue_size: int = 10000,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
    ):
        self.registry = node_registry
        self.max_queue_size = max_queue_size
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

        # 离线队列：recipient_id → [messages]
        self._offline_queue: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_queue_size)
        )

        # 已投递消息
        self._delivered: Dict[str, MailMessage] = {}

        # 重试调度
        self._retry_schedule: Dict[str, float] = {}  # msg_id → next_retry_time

        # 回调
        self._on_delivered: List[Callable] = []
        self._on_failed: List[Callable] = []

        # 后台重试任务
        self._running = False
        self._retry_task: Optional[asyncio.Task] = None

    # ── 发送 ──────────────────────────────────────────────

    async def send(
        self,
        msg: MailMessage,
        preferred_channel: Optional[MessageChannel] = None,
    ) -> bool:
        """
        发送消息（自动选择最佳通道）

        Returns:
            是否成功投递
        """
        channel = preferred_channel or msg.channel

        # 1. P2P 直连
        if channel == MessageChannel.P2P_DIRECT:
            if await self._try_direct_delivery(msg):
                return True
            # 降级到中继
            channel = MessageChannel.RELAY

        # 2. 中继转发
        if channel == MessageChannel.RELAY:
            if await self._try_relay_delivery(msg):
                return True
            # 降级到离线
            channel = MessageChannel.INTERNAL

        # 3. 离线队列
        self._queue_offline(msg)
        return False

    async def send_batch(
        self, messages: List[MailMessage]
    ) -> Tuple[int, int]:
        """批量发送，返回 (成功数, 失败数)"""
        success = 0
        for msg in messages:
            if await self.send(msg):
                success += 1
        return success, len(messages) - success

    # ── 投递尝试 ──────────────────────────────────────────

    async def _try_direct_delivery(self, msg: MailMessage) -> bool:
        """尝试 P2P 直连投递"""
        for recipient_id in msg.recipient_ids:
            node = self.registry.get(recipient_id)
            if not node or not node.is_available():
                return False
            # 尝试直连（简化实现）
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(node.host, node.port),
                    timeout=5.0,
                )
                # 发送消息
                import json
                data = json.dumps(msg.to_dict(), ensure_ascii=False).encode("utf-8")
                writer.write(len(data).to_bytes(4, "big") + data)
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                self._mark_delivered(msg)
                return True
            except Exception:
                continue
        return False

    async def _try_relay_delivery(self, msg: MailMessage) -> bool:
        """尝试通过中继节点投递"""
        relay = self.registry.select_relay()
        if not relay:
            return False
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(relay.host, relay.port),
                timeout=5.0,
            )
            import json
            data = json.dumps({
                "type": "relay_message",
                "message": msg.to_dict(),
            }, ensure_ascii=False).encode("utf-8")
            writer.write(len(data).to_bytes(4, "big") + data)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            self._mark_delivered(msg)
            return True
        except Exception:
            relay.record_failure()
            return False

    # ── 离线队列 ──────────────────────────────────────────

    def _queue_offline(self, msg: MailMessage) -> None:
        """将消息加入离线队列"""
        for recipient_id in msg.recipient_ids:
            self._offline_queue[recipient_id].append(msg)
            msg.status = MessageStatus.QUEUED

    async def flush_offline_queue(self, recipient_id: str) -> int:
        """当节点上线时，冲刷其离线队列"""
        queue = self._offline_queue.get(recipient_id)
        if not queue:
            return 0

        delivered = 0
        while queue:
            msg = queue.popleft()
            if await self.send(msg, MessageChannel.P2P_DIRECT):
                delivered += 1
            else:
                # 放回队列头部
                queue.appendleft(msg)
                break

        if delivered:
            logger.info(f"离线队列冲刷: {recipient_id[:8]}... 已投递 {delivered}")
        return delivered

    # ── 重试 ──────────────────────────────────────────────

    async def start_retry_loop(self) -> None:
        """启动重试循环"""
        if self._running:
            return
        self._running = True
        self._retry_task = asyncio.create_task(self._retry_loop())

    async def stop_retry_loop(self) -> None:
        self._running = False
        if self._retry_task:
            self._retry_task.cancel()
            self._retry_task = None

    async def _retry_loop(self) -> None:
        """重试循环"""
        while self._running:
            now = time.time()
            to_retry = [
                (t, mid) for mid, t in self._retry_schedule.items() if t <= now
            ]
            for _, msg_id in to_retry:
                msg = self._delivered.get(msg_id)
                if msg and msg.can_retry():
                    msg.retry_count += 1
                    if not await self.send(msg):
                        delay = self.retry_backoff ** msg.retry_count
                        self._retry_schedule[msg_id] = now + delay
                else:
                    del self._retry_schedule[msg_id]

            await asyncio.sleep(1.0)

    # ── 状态 ──────────────────────────────────────────────

    def _mark_delivered(self, msg: MailMessage) -> None:
        msg.status = MessageStatus.DELIVERED
        msg.delivered_at = datetime.now()
        self._delivered[msg.msg_id] = msg
        for cb in self._on_delivered:
            try:
                cb(msg)
            except Exception:
                pass

    def on_delivered(self, callback: Callable) -> None:
        self._on_delivered.append(callback)

    def on_failed(self, callback: Callable) -> None:
        self._on_failed.append(callback)

    def get_queue_size(self, recipient_id: str) -> int:
        queue = self._offline_queue.get(recipient_id)
        return len(queue) if queue else 0

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_delivered": len(self._delivered),
            "offline_queues": sum(
                len(q) for q in self._offline_queue.values()
            ),
            "pending_retries": len(self._retry_schedule),
        }


__all__ = [
    "NodeRegistry",
    "MessageTransport",
]
