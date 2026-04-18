# resilience.py — 容错与自愈机制

"""
容错与自愈机制
==============

核心理念：网络不稳定和节点离线是常态，系统需要具备自我修复能力。

容错机制：
1. 节点离线检测与切换
2. 分片完整性验证
3. 网络分裂处理
4. 冲突检测与合并
"""

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from enum import Enum

from .models import (
    NodeInfo, ChunkInfo, UpdateTask, UpdateStage,
    NodeState, format_duration
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ResilienceConfig:
    """容错配置"""
    heartbeat_interval: float = 30.0        # 心跳间隔 (秒)
    heartbeat_timeout: float = 120.0        # 心跳超时 (秒)
    reconnect_delay: float = 5.0           # 重连延迟 (秒)
    max_reconnect_attempts: int = 5       # 最大重连次数
    chunk_verification_interval: float = 60.0  # 分片验证间隔
    min_sources_for_recovery: int = 2     # 恢复所需的最小源数
    network_split_timeout: float = 300.0  # 网络分裂检测超时
    conflict_resolution_strategy: str = "latest"  # 冲突解决策略


# ═══════════════════════════════════════════════════════════════════════════════
# 故障类型
# ═══════════════════════════════════════════════════════════════════════════════


class FailureType(Enum):
    """故障类型"""
    NODE_OFFLINE = "node_offline"                 # 节点离线
    CONNECTION_LOST = "connection_lost"           # 连接丢失
    CHUNK_CORRUPTED = "chunk_corrupted"           # 分片损坏
    NETWORK_SPLIT = "network_split"               # 网络分裂
    VERSION_CONFLICT = "version_conflict"         # 版本冲突
    DOWNLOAD_STALLED = "download_stalled"         # 下载停滞


@dataclass
class FailureEvent:
    """故障事件"""
    failure_type: FailureType                    # 故障类型
    affected_entity: str                          # 受影响实体 (chunk_id / node_id / etc)
    timestamp: float = 0
    details: Dict[str, Any] = field(default_factory=dict)
    recovered: bool = False
    recovery_time: float = 0

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()


@dataclass
class Checkpoint:
    """检查点"""
    task_id: str                                 # 任务ID
    downloaded_chunks: Set[str]                   # 已下载的分片ID
    chunk_data_hashes: Dict[str, str]           # chunk_id -> hash
    timestamp: float = 0
    node_states: Dict[str, NodeState] = field(default_factory=dict)  # 节点状态快照

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()


# ═══════════════════════════════════════════════════════════════════════════════
# 故障检测器
# ═══════════════════════════════════════════════════════════════════════════════


class FailureDetector:
    """
    故障检测器

    检测节点离线、连接丢失等故障
    """

    def __init__(self, config: ResilienceConfig = None):
        self.config = config or ResilienceConfig()
        self.last_heartbeat: Dict[str, float] = {}  # node_id -> last_heartbeat
        self.active_failures: Dict[str, FailureEvent] = {}  # entity -> failure
        self.failure_history: List[FailureEvent] = []
        self._lock = asyncio.Lock()

        # 回调函数
        self.on_failure_detected: Optional[Callable] = None
        self.on_failure_recovered: Optional[Callable] = None

    async def register_node(self, node_id: str):
        """注册节点"""
        async with self._lock:
            self.last_heartbeat[node_id] = time.time()

    async def unregister_node(self, node_id: str):
        """注销节点"""
        async with self._lock:
            self.last_heartbeat.pop(node_id, None)

    async def record_heartbeat(self, node_id: str):
        """记录心跳"""
        async with self._lock:
            self.last_heartbeat[node_id] = time.time()

            # 如果之前有故障，标记为恢复
            if node_id in self.active_failures:
                failure = self.active_failures[node_id]
                if failure.failure_type == FailureType.NODE_OFFLINE:
                    failure.recovered = True
                    failure.recovery_time = time.time()
                    del self.active_failures[node_id]

                    if self.on_failure_recovered:
                        await self.on_failure_recovered(failure)

    async def check_failures(self) -> List[FailureEvent]:
        """
        检查故障

        Returns:
            新检测到的故障列表
        """
        now = time.time()
        new_failures = []

        async with self._lock:
            for node_id, last_time in list(self.last_heartbeat.items()):
                timeout = now - last_time

                if timeout > self.config.heartbeat_timeout:
                    # 检测到节点离线
                    if node_id not in self.active_failures:
                        failure = FailureEvent(
                            failure_type=FailureType.NODE_OFFLINE,
                            affected_entity=node_id,
                            details={'timeout': timeout}
                        )
                        self.active_failures[node_id] = failure
                        new_failures.append(failure)

                        logger.warning(
                            f"Node {node_id[:8]} offline "
                            f"(timeout: {format_duration(timeout)})"
                        )

        # 触发回调
        if new_failures and self.on_failure_detected:
            for failure in new_failures:
                await self.on_failure_detected(failure)

        return new_failures

    async def record_chunk_failure(
        self,
        chunk_id: str,
        details: Dict[str, Any] = None
    ):
        """记录分片故障"""
        async with self._lock:
            failure = FailureEvent(
                failure_type=FailureType.CHUNK_CORRUPTED,
                affected_entity=chunk_id,
                details=details or {}
            )
            self.active_failures[chunk_id] = failure
            self.failure_history.append(failure)

            logger.warning(f"Chunk {chunk_id} corrupted")

    async def mark_chunk_recovered(self, chunk_id: str):
        """标记分片已恢复"""
        async with self._lock:
            if chunk_id in self.active_failures:
                failure = self.active_failures[chunk_id]
                failure.recovered = True
                failure.recovery_time = time.time()
                del self.active_failures[chunk_id]

                logger.info(f"Chunk {chunk_id} recovered")

    def get_active_failures(self) -> List[FailureEvent]:
        """获取活跃故障列表"""
        return list(self.active_failures.values())

    def get_failure_stats(self) -> Dict[str, Any]:
        """获取故障统计"""
        total = len(self.failure_history)
        recovered = sum(1 for f in self.failure_history if f.recovered)

        return {
            'total_failures': total,
            'active_failures': len(self.active_failures),
            'recovered': recovered,
            'recovery_rate': recovered / total if total > 0 else 0
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 连接管理器
# ═══════════════════════════════════════════════════════════════════════════════


class ConnectionManager:
    """
    连接管理器

    管理节点连接，支持自动重连
    """

    def __init__(self, config: ResilienceConfig = None):
        self.config = config or ResilienceConfig()
        self.connections: Dict[str, NodeInfo] = {}  # node_id -> node
        self.pending_connections: Set[str] = set()  # 正在连接的节点
        self.failed_connections: Dict[str, int] = {}  # node_id -> fail_count
        self._lock = asyncio.Lock()

        # 回调
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None
        self.on_reconnect_failed: Optional[Callable] = None

    async def add_connection(self, node: NodeInfo) -> bool:
        """添加连接"""
        async with self._lock:
            if node.node_id in self.connections:
                return True  # 已连接

            self.pending_connections.add(node.node_id)

            try:
                # 模拟连接过程
                # 实际实现中会建立 TCP 连接
                await asyncio.sleep(0.1)

                self.connections[node.node_id] = node
                self.pending_connections.discard(node.node_id)
                self.failed_connections.pop(node.node_id, None)

                if self.on_connected:
                    await self.on_connected(node)

                logger.info(f"Connected to {node.node_id[:8]}")
                return True

            except Exception as e:
                logger.error(f"Failed to connect to {node.node_id[:8]}: {e}")
                self.pending_connections.discard(node.node_id)
                return False

    async def remove_connection(self, node_id: str):
        """移除连接"""
        async with self._lock:
            if node_id in self.connections:
                node = self.connections.pop(node_id)

                if self.on_disconnected:
                    await self.on_disconnected(node)

                logger.info(f"Disconnected from {node_id[:8]}")

    async def reconnect(self, node_id: str) -> bool:
        """尝试重连"""
        if node_id not in self.failed_connections:
            self.failed_connections[node_id] = 0

        self.failed_connections[node_id] += 1

        if self.failed_connections[node_id] > self.config.max_reconnect_attempts:
            if self.on_reconnect_failed:
                await self.on_reconnect_failed(node_id)
            return False

        # 延迟重连
        delay = self.config.reconnect_delay * self.failed_connections[node_id]
        await asyncio.sleep(delay)

        # 重新获取节点信息并连接
        if node_id in self.connections:
            node = self.connections[node_id]
            return await self.add_connection(node)

        return False

    async def get_alive_connections(self) -> List[NodeInfo]:
        """获取活跃连接"""
        async with self._lock:
            return list(self.connections.values())

    @property
    def connection_count(self) -> int:
        """连接数"""
        return len(self.connections)


# ═══════════════════════════════════════════════════════════════════════════════
# 检查点管理器
# ═══════════════════════════════════════════════════════════════════════════════


class CheckpointManager:
    """
    检查点管理器

    支持断点续传，定期保存下载进度
    """

    def __init__(self):
        self.checkpoints: Dict[str, Checkpoint] = {}  # task_id -> checkpoint
        self._lock = asyncio.Lock()

    async def save_checkpoint(self, task: UpdateTask, chunk_manager=None):
        """
        保存检查点

        Args:
            task: 更新任务
            chunk_manager: 分片管理器（可选）
        """
        async with self._lock:
            # 获取已下载分片的哈希
            chunk_hashes = {}
            if chunk_manager:
                for chunk_id, chunk in chunk_manager.chunks.items():
                    if chunk.state.value in ("completed", "verified"):
                        chunk_hashes[chunk_id] = chunk.hash

            checkpoint = Checkpoint(
                task_id=task.task_id,
                downloaded_chunks=task.downloaded_chunks.copy(),
                chunk_data_hashes=chunk_hashes,
                node_states={}
            )

            self.checkpoints[task.task_id] = checkpoint

            logger.debug(
                f"Checkpoint saved for {task.task_id}: "
                f"{len(task.downloaded_chunks)} chunks"
            )

    async def load_checkpoint(self, task_id: str) -> Optional[Checkpoint]:
        """加载检查点"""
        async with self._lock:
            return self.checkpoints.get(task_id)

    async def restore_from_checkpoint(
        self,
        task_id: str,
        task: UpdateTask
    ) -> bool:
        """
        从检查点恢复

        Returns:
            True 如果恢复成功
        """
        checkpoint = await self.load_checkpoint(task_id)
        if not checkpoint:
            return False

        # 恢复分片状态
        task.downloaded_chunks = checkpoint.downloaded_chunks.copy()

        logger.info(
            f"Restored from checkpoint for {task_id}: "
            f"{len(task.downloaded_chunks)} chunks"
        )

        return True

    async def delete_checkpoint(self, task_id: str):
        """删除检查点"""
        async with self._lock:
            if task_id in self.checkpoints:
                del self.checkpoints[task_id]


# ═══════════════════════════════════════════════════════════════════════════════
# 网络分裂检测器
# ═══════════════════════════════════════════════════════════════════════════════


class NetworkSplitDetector:
    """
    网络分裂检测器

    检测网络分区并处理
    """

    def __init__(self, config: ResilienceConfig = None):
        self.config = config or ResilienceConfig()
        self.split_regions: Dict[str, Set[str]] = defaultdict(set)  # region -> node_ids
        self.last_sync: Dict[str, float] = {}  # region -> last_sync_time
        self._lock = asyncio.Lock()
        self._running = False
        self._tasks: List[asyncio.Task] = []

    async def record_node_region(self, node_id: str, region: str):
        """记录节点区域"""
        async with self._lock:
            self.split_regions[region].add(node_id)
            self.last_sync[region] = time.time()

    async def check_splits(self) -> List[Tuple[Set[str], Set[str]]]:
        """
        检查网络分裂

        Returns:
            分裂区域对列表 [(region1_nodes, region2_nodes), ...]
        """
        async with self._lock:
            regions = list(self.split_regions.keys())
            splits = []

            now = time.time()

            for i, r1 in enumerate(regions):
                for r2 in regions[i + 1:]:
                    # 检查两个区域的最后同步时间差异
                    t1 = self.last_sync.get(r1, 0)
                    t2 = self.last_sync.get(r2, 0)

                    if abs(now - t1) > self.config.network_split_timeout and \
                       abs(now - t2) > self.config.network_split_timeout:
                        # 两个区域都长时间没有同步，认为发生了分裂
                        splits.append((
                            self.split_regions[r1],
                            self.split_regions[r2]
                        ))

            return splits

    async def merge_region(self, region: str):
        """合并区域（网络恢复）"""
        async with self._lock:
            self.last_sync[region] = time.time()
            logger.info(f"Region {region} merged (network restored)")


# ═══════════════════════════════════════════════════════════════════════════════
# 冲突解决器
# ═══════════════════════════════════════════════════════════════════════════════


class ConflictResolver:
    """
    冲突解决器

    解决版本冲突和其他冲突
    """

    def __init__(self, strategy: str = "latest"):
        self.strategy = strategy

    def resolve_version_conflict(
        self,
        local_version: str,
        remote_version: str
    ) -> str:
        """
        解决版本冲突

        Args:
            local_version: 本地版本
            remote_version: 远程版本

        Returns:
            保留的版本
        """
        if self.strategy == "latest":
            # 使用最新版本
            def parse_version(v):
                parts = v.lstrip('v').split('.')
                return tuple(int(p) for p in parts)

            if parse_version(local_version) >= parse_version(remote_version):
                return local_version
            else:
                return remote_version

        elif self.strategy == "remote":
            return remote_version

        elif self.strategy == "local":
            return local_version

        else:
            # 默认使用最新
            return max(local_version, remote_version)

    def resolve_chunk_conflict(
        self,
        local_hash: str,
        remote_hash: str,
        chunk_data: bytes
    ) -> Tuple[bool, bytes]:
        """
        解决分片冲突

        Returns:
            (is_valid, data)
        """
        # 验证数据哈希
        actual_hash = hashlib.sha256(chunk_data).hexdigest()

        if actual_hash == local_hash:
            return True, chunk_data
        elif actual_hash == remote_hash:
            return True, chunk_data
        else:
            # 数据损坏
            return False, b""


# ═══════════════════════════════════════════════════════════════════════════════
# 容错管理器
# ═══════════════════════════════════════════════════════════════════════════════


class ResilienceManager:
    """
    容错管理器

    整合所有容错组件
    """

    def __init__(self, config: ResilienceConfig = None):
        self.config = config or ResilienceConfig()
        self.failure_detector = FailureDetector(config)
        self.connection_manager = ConnectionManager(config)
        self.checkpoint_manager = CheckpointManager()
        self.split_detector = NetworkSplitDetector(config)
        self.conflict_resolver = ConflictResolver(config.strategy)

        self._running = False
        self._tasks: List[asyncio.Task] = []

        # 回调
        self.on_source_switch: Optional[Callable] = None
        self.on_chunk_recovery: Optional[Callable] = None

    async def handle_source_failure(
        self,
        task: UpdateTask,
        failed_source: str,
        available_sources: List[NodeInfo]
    ) -> Optional[NodeInfo]:
        """
        处理源节点故障，切换到备用源

        Args:
            task: 更新任务
            failed_source: 故障源节点ID
            available_sources: 可用的备用源

        Returns:
            新的源节点
        """
        # 过滤掉故障源
        candidates = [n for n in available_sources if n.node_id != failed_source]

        if not candidates:
            logger.warning(f"No backup sources for task {task.task_id}")
            return None

        # 选择最优备用源
        candidates.sort(
            key=lambda n: n.reputation_score * 0.6 + n.bandwidth_score * 0.4,
            reverse=True
        )

        new_source = candidates[0]

        if self.on_source_switch:
            await self.on_source_switch(task, failed_source, new_source)

        logger.info(
            f"Switched source for {task.task_id}: "
            f"{failed_source[:8]} -> {new_source.node_id[:8]}"
        )

        return new_source

    async def recover_chunk(
        self,
        task: UpdateTask,
        chunk_id: str,
        sources: List[NodeInfo]
    ) -> bool:
        """
        尝试恢复损坏的分片

        Args:
            task: 更新任务
            chunk_id: 分片ID
            sources: 可用的源节点

        Returns:
            True 如果恢复成功
        """
        for source in sources:
            try:
                # 模拟从源节点重新下载
                # 实际实现中会向 source 请求 chunk_id

                logger.info(
                    f"Attempting to recover chunk {chunk_id} from {source.node_id[:8]}"
                )

                # 假设恢复成功
                if self.on_chunk_recovery:
                    await self.on_chunk_recovery(task, chunk_id, source)

                return True

            except Exception as e:
                logger.warning(f"Chunk recovery failed from {source.node_id[:8]}: {e}")
                continue

        # 所有源都失败
        await self.failure_detector.record_chunk_failure(chunk_id)
        return False

    async def verify_task_integrity(
        self,
        task: UpdateTask,
        chunk_manager
    ) -> Tuple[bool, List[str]]:
        """
        验证任务完整性

        Returns:
            (is_valid, corrupted_chunks)
        """
        if not chunk_manager:
            return True, []

        corrupted = []

        for chunk_id, chunk in chunk_manager.chunks.items():
            if chunk.state.value in ("completed", "verified"):
                # 验证哈希
                if chunk.data:
                    actual_hash = hashlib.sha256(chunk.data).hexdigest()
                    if actual_hash != chunk.hash:
                        corrupted.append(chunk_id)
                        await self.failure_detector.record_chunk_failure(chunk_id)

        is_valid = len(corrupted) == 0

        if not is_valid:
            logger.warning(f"Task {task.task_id} integrity check failed: {len(corrupted)} corrupted chunks")

        return is_valid, corrupted

    async def start(self):
        """启动容错管理器"""
        self._running = True

        # 启动故障检测循环
        self._tasks.append(asyncio.create_task(self._failure_check_loop()))

        # 启动检查点保存循环
        self._tasks.append(asyncio.create_task(self._checkpoint_loop()))

        logger.info("Resilience manager started")

    async def stop(self):
        """停止容错管理器"""
        self._running = False

        for task in self._tasks:
            task.cancel()

        self._tasks.clear()
        logger.info("Resilience manager stopped")

    async def _failure_check_loop(self):
        """故障检测循环"""
        while self._running:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                await self.failure_detector.check_failures()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Failure check loop error: {e}")

    async def _checkpoint_loop(self):
        """检查点保存循环"""
        while self._running:
            try:
                await asyncio.sleep(60)  # 每分钟保存一次
                # 实际实现中会遍历所有活跃任务并保存检查点
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Checkpoint loop error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# 全局实例
# ═══════════════════════════════════════════════════════════════════════════════


_resilience_manager: Optional[ResilienceManager] = None


def get_resilience_manager() -> ResilienceManager:
    """获取全局容错管理器"""
    global _resilience_manager
    if _resilience_manager is None:
        _resilience_manager = ResilienceManager()
    return _resilience_manager
