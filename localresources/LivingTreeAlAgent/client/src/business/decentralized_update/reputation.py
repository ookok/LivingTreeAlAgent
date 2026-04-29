# reputation.py — 信誉系统

"""
信誉系统
=========

核心理念：建立去中心化的信誉系统，激励节点贡献，惩罚恶意行为。

信誉系统设计：
- 基础分：在线时长、网络稳定性
- 贡献分：成功分发次数、带宽贡献
- 违规分：传播错误版本、恶意行为
- 衰减机制：信誉随时间自然衰减
"""

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum

from .models import (
    NodeInfo, ReputationLevel, NodeState
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ReputationConfig:
    """信誉配置"""
    initial_score: float = 50.0           # 初始信誉分
    max_score: float = 100.0              # 最大信誉分
    min_score: float = 0.0                # 最小信誉分

    # 加分项
    online_duration_bonus: float = 0.1    # 每小时在线加分
    successful_distribute_bonus: float = 2.0  # 每次成功分发加分
    bandwidth_contribution_bonus: float = 1.0   # 每 MB 带宽贡献加分

    # 扣分项
    failed_distribute_penalty: float = 5.0  # 每次失败分发扣分
    malicious_behavior_penalty: float = 20.0  # 恶意行为扣分
    version_fake_penalty: float = 30.0       # 传播虚假版本扣分

    # 衰减
    decay_rate: float = 0.01              # 每日衰减率
    decay_threshold: float = 20.0        # 衰减门槛（低于此分数不衰减）

    # 等级阈值
    untrusted_threshold: float = 20.0    # 不可信阈值
    newcomer_threshold: float = 50.0     # 新加入阈值
    trusted_threshold: float = 80.0       # 可信阈值
    highly_trusted_threshold: float = 95.0  # 高可信阈值


# ═══════════════════════════════════════════════════════════════════════════════
# 信誉事件
# ═══════════════════════════════════════════════════════════════════════════════


class ReputationEvent(Enum):
    """信誉事件类型"""
    # 加分事件
    ONLINE = "online"                         # 在线
    DISTRIBUTE_SUCCESS = "distribute_success"  # 分发成功
    BANDWIDTH_CONTRIBUTION = "bandwidth_contribution"  # 带宽贡献
    VERSION_ENDORSEMENT = "version_endorsement"  # 版本背书
    STABILITY_BONUS = "stability_bonus"       # 稳定性奖励

    # 扣分事件
    DISTRIBUTE_FAILED = "distribute_failed"   # 分发失败
    MALICIOUS_BEHAVIOR = "malicious_behavior"  # 恶意行为
    VERSION_FAKE = "version_fake"             # 传播虚假版本
    SPAM_BROADCAST = "spam_broadcast"          # 垃圾广播
    ECLIPSE_ATTACK = "eclipse_attack"          # 日食攻击嫌疑


@dataclass
class ReputationRecord:
    """信誉记录"""
    event: ReputationEvent                     # 事件类型
    node_id: str                               # 节点ID
    delta: float                                # 变化量
    reason: str = ""                            # 原因
    timestamp: float = 0
    verified: bool = False                       # 是否验证

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()


# ═══════════════════════════════════════════════════════════════════════════════
# 信誉追踪器
# ═══════════════════════════════════════════════════════════════════════════════


class ReputationTracker:
    """
    信誉追踪器

    追踪节点信誉变化历史
    """

    def __init__(self):
        self.records: Dict[str, List[ReputationRecord]] = defaultdict(list)  # node_id -> records
        self.node_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'total_distributes': 0,
            'successful_distributes': 0,
            'failed_distributes': 0,
            'total_bandwidth': 0,
            'online_time': 0,
            'last_online': 0,
            'last_decay': 0
        })
        self._lock = asyncio.Lock()

    async def record_event(
        self,
        node_id: str,
        event: ReputationEvent,
        delta: float,
        reason: str = "",
        verified: bool = False
    ):
        """记录信誉事件"""
        async with self._lock:
            record = ReputationRecord(
                event=event,
                node_id=node_id,
                delta=delta,
                reason=reason,
                verified=verified
            )
            self.records[node_id].append(record)

            # 更新统计
            stats = self.node_stats[node_id]

            if event == ReputationEvent.DISTRIBUTE_SUCCESS:
                stats['successful_distributes'] += 1
            elif event == ReputationEvent.DISTRIBUTE_FAILED:
                stats['failed_distributes'] += 1
            elif event == ReputationEvent.BANDWIDTH_CONTRIBUTION:
                stats['total_bandwidth'] += abs(delta)
            elif event == ReputationEvent.ONLINE:
                stats['online_time'] += abs(delta)
                stats['last_online'] = time.time()

    async def get_history(
        self,
        node_id: str,
        limit: int = 100
    ) -> List[ReputationRecord]:
        """获取节点信誉历史"""
        async with self._lock:
            records = self.records.get(node_id, [])
            return records[-limit:]

    async def get_stats(self, node_id: str) -> Dict[str, Any]:
        """获取节点统计信息"""
        async with self._lock:
            return self.node_stats.get(node_id, {})


# ═══════════════════════════════════════════════════════════════════════════════
# 信誉计算器
# ═══════════════════════════════════════════════════════════════════════════════


class ReputationCalculator:
    """
    信誉计算器

    根据事件计算信誉分
    """

    def __init__(self, config: ReputationConfig = None):
        self.config = config or ReputationConfig()

    def calculate(
        self,
        base_score: float,
        stats: Dict[str, Any],
        recent_events: List[ReputationRecord]
    ) -> float:
        """
        计算信誉分

        Args:
            base_score: 基础分
            stats: 节点统计
            recent_events: 最近事件

        Returns:
            计算后的信誉分
        """
        score = base_score

        # 处理最近事件
        for event in recent_events:
            if event.verified or event.event in (
                ReputationEvent.ONLINE,
                ReputationEvent.DISTRIBUTE_SUCCESS,
                ReputationEvent.DISTRIBUTE_FAILED
            ):
                score += event.delta

        # 在线时长加成
        online_hours = stats.get('online_time', 0) / 3600
        score += online_hours * self.config.online_duration_bonus

        # 分发成功率加成
        total = stats.get('total_distributes', 0)
        successful = stats.get('successful_distributes', 0)
        if total > 0:
            success_rate = successful / total
            if success_rate > 0.9:
                score += 5  # 高成功率奖励

        # 带宽贡献加成
        bandwidth_mb = stats.get('total_bandwidth', 0) / (1024 * 1024)
        score += bandwidth_mb * self.config.bandwidth_contribution_bonus

        # 限制范围
        score = max(self.config.min_score, min(self.config.max_score, score))

        return score

    def calculate_level(self, score: float) -> ReputationLevel:
        """根据分数计算信誉等级"""
        if score < self.config.untrusted_threshold:
            return ReputationLevel.UNTRUSTED
        elif score < self.config.newcomer_threshold:
            return ReputationLevel.NEWCOMER
        elif score < self.config.trusted_threshold:
            return ReputationLevel.TRUSTED
        elif score < self.config.highly_trusted_threshold:
            return ReputationLevel.HIGHLY_TRUSTED
        else:
            return ReputationLevel.AUTHORITY


# ═══════════════════════════════════════════════════════════════════════════════
# 信誉管理器
# ═══════════════════════════════════════════════════════════════════════════════


class ReputationManager:
    """
    信誉管理器

    整合追踪器、计算器和节点信息
    """

    def __init__(self, config: ReputationConfig = None):
        self.config = config or ReputationConfig()
        self.tracker = ReputationTracker()
        self.calculator = ReputationCalculator(config)
        self.nodes: Dict[str, NodeInfo] = {}  # node_id -> NodeInfo
        self._lock = asyncio.Lock()
        self._running = False
        self._tasks: List[asyncio.Task] = []

    async def register_node(self, node: NodeInfo):
        """注册节点"""
        async with self._lock:
            if node.node_id not in self.nodes:
                node.reputation_score = self.config.initial_score
                node.reputation_level = ReputationLevel.NEWCOMER
            self.nodes[node.node_id] = node

            logger.info(f"Registered node: {node.node_id[:8]}, initial score: {self.config.initial_score}")

    async def unregister_node(self, node_id: str):
        """注销节点"""
        async with self._lock:
            if node_id in self.nodes:
                del self.nodes[node_id]
                logger.info(f"Unregistered node: {node_id[:8]}")

    async def update_reputation(
        self,
        node_id: str,
        event: ReputationEvent,
        delta: float,
        reason: str = "",
        verified: bool = False
    ) -> float:
        """
        更新信誉分

        Args:
            node_id: 节点ID
            event: 事件类型
            delta: 变化量
            reason: 原因
            verified: 是否验证

        Returns:
            更新后的信誉分
        """
        # 记录事件
        await self.tracker.record_event(node_id, event, delta, reason, verified)

        # 获取节点和统计
        async with self._lock:
            if node_id not in self.nodes:
                return 0

            node = self.nodes[node_id]
            stats = await self.tracker.get_stats(node_id)
            history = await self.tracker.get_history(node_id)

            # 计算新分数
            new_score = self.calculator.calculate(
                node.reputation_score,
                stats,
                history
            )

            # 更新节点
            node.reputation_score = new_score
            node.reputation_level = self.calculator.calculate_level(new_score)

            logger.debug(
                f"Updated reputation for {node_id[:8]}: "
                f"{node.reputation_score:.2f} -> {new_score:.2f} "
                f"(level: {node.reputation_level.name})"
            )

            return new_score

    async def record_distribution(
        self,
        node_id: str,
        success: bool,
        bandwidth_bytes: int = 0
    ):
        """记录分发结果"""
        if success:
            await self.update_reputation(
                node_id,
                ReputationEvent.DISTRIBUTE_SUCCESS,
                self.config.successful_distribute_bonus,
                "Successful distribution"
            )
            if bandwidth_bytes > 0:
                await self.tracker.record_event(
                    node_id,
                    ReputationEvent.BANDWIDTH_CONTRIBUTION,
                    bandwidth_bytes,
                    f"Bandwidth contribution: {bandwidth_bytes / 1024 / 1024:.2f} MB"
                )
        else:
            await self.update_reputation(
                node_id,
                ReputationEvent.DISTRIBUTE_FAILED,
                -self.config.failed_distribute_penalty,
                "Failed distribution"
            )

    async def penalize(
        self,
        node_id: str,
        penalty_type: ReputationEvent,
        reason: str = ""
    ):
        """惩罚恶意节点"""
        if penalty_type == ReputationEvent.MALICIOUS_BEHAVIOR:
            delta = -self.config.malicious_behavior_penalty
        elif penalty_type == ReputationEvent.VERSION_FAKE:
            delta = -self.config.version_fake_penalty
        elif penalty_type == ReputationEvent.SPAM_BROADCAST:
            delta = -self.config.malicious_behavior_penalty
        else:
            delta = -10.0

        await self.update_reputation(
            node_id,
            penalty_type,
            delta,
            reason
        )

        logger.warning(f"Penalized node {node_id[:8]}: {penalty_type.value}, delta={delta}")

    async def decay_loop(self):
        """信誉衰减循环"""
        while self._running:
            try:
                await asyncio.sleep(3600)  # 每小时检查一次
                await self._apply_decay()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Decay loop error: {e}")

    async def _apply_decay(self):
        """应用信誉衰减"""
        now = time.time()

        async with self._lock:
            for node_id, node in self.nodes.items():
                # 只对低于门槛的节点衰减
                if node.reputation_score <= self.config.decay_threshold:
                    continue

                # 检查上次衰减时间
                stats = self.node_stats.get(node_id, {})
                last_decay = stats.get('last_decay', 0)

                # 每天最多衰减一次
                if now - last_decay < 86400:
                    continue

                # 应用衰减
                decay_amount = node.reputation_score * self.config.decay_rate
                node.reputation_score -= decay_amount

                # 重新计算等级
                node.reputation_level = self.calculator.calculate_level(node.reputation_score)

                logger.debug(f"Decayed reputation for {node_id[:8]}: -{decay_amount:.2f}")

    async def get_node_reputation(self, node_id: str) -> Optional[Tuple[float, ReputationLevel]]:
        """获取节点信誉"""
        async with self._lock:
            if node_id not in self.nodes:
                return None
            node = self.nodes[node_id]
            return node.reputation_score, node.reputation_level

    async def get_top_nodes(self, count: int = 10) -> List[NodeInfo]:
        """获取信誉最高的节点"""
        async with self._lock:
            sorted_nodes = sorted(
                self.nodes.values(),
                key=lambda n: n.reputation_score,
                reverse=True
            )
            return sorted_nodes[:count]

    async def start(self):
        """启动信誉管理器"""
        self._running = True
        self._tasks.append(asyncio.create_task(self.decay_loop()))
        logger.info("Reputation manager started")

    async def stop(self):
        """停止信誉管理器"""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("Reputation manager stopped")


# ═══════════════════════════════════════════════════════════════════════════════
# 全局实例
# ═══════════════════════════════════════════════════════════════════════════════


_reputation_manager: Optional[ReputationManager] = None


def get_reputation_manager() -> ReputationManager:
    """获取全局信誉管理器"""
    global _reputation_manager
    if _reputation_manager is None:
        _reputation_manager = ReputationManager()
    return _reputation_manager
