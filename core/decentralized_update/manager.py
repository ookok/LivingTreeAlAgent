# manager.py — 统一管理器

"""
P2P 去中心化更新系统统一管理器
=============================

整合所有子模块，提供统一的更新接口
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Callable
from enum import Enum

from .models import (
    NodeInfo, VersionInfo, UpdateTask, UpdateStage, UpdateManifest,
    NodeState, UpdateStrategy, generate_task_id, format_size, format_speed, format_duration
)
from .discovery import DHTNode, SeedNodeManager, get_dht_node, get_seed_manager
from .propagation import RipplePropagator, get_propagator
from .delta_update import DeltaManager, get_delta_manager
from .signature import SignatureService, get_signature_service
from .distribution import DistributionManager, get_distribution_manager
from .reputation import ReputationManager, get_reputation_manager
from .resilience import ResilienceManager, get_resilience_manager

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class UpdateConfig:
    """更新系统配置"""
    # 应用信息
    app_id: str = "hermes-desktop"
    current_version: str = "1.0.0"

    # 更新策略
    update_strategy: UpdateStrategy = UpdateStrategy.AUTO
    check_interval: int = 3600  # 检查间隔 (秒)
    auto_update_window: str = "02:00-04:00"  # 自动更新时段

    # P2P 设置
    max_peers: int = 20            # 最大连接 peers 数
    max_download_sources: int = 5  # 最大下载源数
    seed_bandwidth_threshold: int = 10 * 1024 * 1024  # 种子带宽阈值 (10MB/s)

    # 验证设置
    require_signatures: bool = True  # 是否要求签名验证
    min_endorsements: int = 3        # 最少背书数量

    # 增量更新
    enable_delta: bool = True        # 启用增量更新
    max_delta_chain: int = 3        # 最大增量链长度

    # 容错设置
    enable_checkpoint: bool = True   # 启用检查点
    checkpoint_interval: int = 60   # 检查点间隔 (秒)


# ═══════════════════════════════════════════════════════════════════════════════
# 系统状态
# ═══════════════════════════════════════════════════════════════════════════════


class SystemState(Enum):
    """系统状态"""
    IDLE = "idle"
    CHECKING = "checking"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    APPLYING = "applying"
    ERROR = "error"


@dataclass
class UpdateSystemStatus:
    """更新系统状态"""
    state: SystemState = SystemState.IDLE
    current_version: str = ""
    latest_version: Optional[str] = None
    update_available: bool = False
    download_progress: float = 0
    download_speed: float = 0
    remaining_time: float = 0
    active_task: Optional[UpdateTask] = None
    error: Optional[str] = None
    stats: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# 统一管理器
# ═══════════════════════════════════════════════════════════════════════════════


class UpdateManager:
    """
    P2P 去中心化更新系统统一管理器

    整合所有子模块，提供：
    1. 版本检查
    2. 增量更新计算
    3. P2P 下载
    4. 签名验证
    5. 容错处理
    """

    def __init__(self, config: UpdateConfig = None):
        self.config = config or UpdateConfig()
        self.state = SystemState.IDLE

        # 子系统
        self.dht_node: Optional[DHTNode] = None
        self.seed_manager: Optional[SeedNodeManager] = None
        self.propagator: Optional[RipplePropagator] = None
        self.delta_manager: Optional[DeltaManager] = None
        self.signature_service: Optional[SignatureService] = None
        self.distribution: Optional[DistributionManager] = None
        self.reputation: Optional[ReputationManager] = None
        self.resilience: Optional[ResilienceManager] = None

        # 状态
        self.status = UpdateSystemStatus()
        self.active_tasks: Dict[str, UpdateTask] = {}
        self.version_cache: Dict[str, VersionInfo] = {}

        # 回调
        self.on_status_change: Optional[Callable] = None
        self.on_update_available: Optional[Callable] = None
        self.on_download_progress: Optional[Callable] = None

        # 锁
        self._lock = asyncio.Lock()
        self._running = False
        self._tasks: List[asyncio.Task] = []

        logger.info("UpdateManager initialized")

    # ═══════════════════════════════════════════════════════════════════════════
    # 生命周期
    # ═══════════════════════════════════════════════════════════════════════════

    async def initialize(self):
        """初始化更新系统"""
        logger.info("Initializing P2P Update System...")

        # 初始化子系统
        self.dht_node = get_dht_node()
        self.seed_manager = get_seed_manager()
        self.propagator = get_propagator()
        self.delta_manager = get_delta_manager()
        self.signature_service = get_signature_service()
        self.distribution = get_distribution_manager()
        self.reputation = get_reputation_manager()
        self.resilience = get_resilience_manager()

        # 启动子系统
        await self.dht_node.start()
        await self.propagator.start()
        await self.reputation.start()
        await self.resilience.start()

        # 注册为种子节点（如果是最新版本）
        await self._register_as_seed()

        # 启动检查循环
        self._running = True
        self._tasks.append(asyncio.create_task(self._check_loop()))

        logger.info("P2P Update System initialized")

    async def shutdown(self):
        """关闭更新系统"""
        logger.info("Shutting down P2P Update System...")

        self._running = False

        # 停止子系统
        for task in self._tasks:
            task.cancel()

        await self.dht_node.stop()
        await self.propagator.stop()
        await self.reputation.stop()
        await self.resilience.stop()

        logger.info("P2P Update System stopped")

    # ═══════════════════════════════════════════════════════════════════════════
    # 版本检查
    # ═══════════════════════════════════════════════════════════════════════════

    async def check_for_updates(self) -> Optional[VersionInfo]:
        """
        检查更新

        Returns:
            最新版本信息（如果有更新）
        """
        async with self._lock:
            self._set_state(SystemState.CHECKING)

        try:
            logger.info("Checking for updates...")

            # 查询网络中的最新版本
            latest = await self.dht_node.query_latest_version(self.config.app_id)

            if latest:
                current_code = self._parse_version_code(self.config.current_version)
                if latest.version_code > current_code:
                    self.status.latest_version = latest.version
                    self.status.update_available = True

                    logger.info(f"Update available: {latest.version}")

                    if self.on_update_available:
                        await self.on_update_available(latest)

                    return latest
                else:
                    logger.info("Already on latest version")
                    self.status.update_available = False
                    return None
            else:
                logger.warning("No version info found in network")
                return None

        except Exception as e:
            logger.error(f"Check for updates failed: {e}")
            self._set_error(str(e))
            return None

        finally:
            self._set_state(SystemState.IDLE)

    async def get_version_info(self, version: str = None) -> Optional[VersionInfo]:
        """获取版本信息"""
        if version:
            return self.version_cache.get(version)
        return self.version_cache.get(self.status.latest_version)

    # ═══════════════════════════════════════════════════════════════════════════
    # 更新下载
    # ═══════════════════════════════════════════════════════════════════════════

    async def download_update(
        self,
        version: VersionInfo,
        sources: List[NodeInfo] = None
    ) -> Optional[UpdateTask]:
        """
        开始下载更新

        Args:
            version: 目标版本
            sources: 下载源列表

        Returns:
            更新任务
        """
        async with self._lock:
            self._set_state(SystemState.DOWNLOADING)

        try:
            # 创建更新任务
            task = UpdateTask(
                task_id=generate_task_id(),
                from_version=self.config.current_version,
                to_version=version.version,
                stage=UpdateStage.DOWNLOADING
            )

            self.active_tasks[task.task_id] = task
            self.status.active_task = task

            # 获取下载源
            if not sources:
                sources = await self._get_download_sources(version)

            if not sources:
                raise Exception("No download sources available")

            task.sources = sources

            # 计算增量
            if self.config.enable_delta:
                plan = self.delta_manager.get_upgrade_plan(
                    self.config.current_version,
                    version.version
                )
                if plan and plan.get('delta_chain'):
                    logger.info(f"Using delta chain: {plan['path']}")

            # 准备文件信息（简化处理）
            file_info = {
                'path': str(Path.home() / ".hermes-desktop" / "updates" / f"{version.version}.bin"),
                'size': version.full_size
            }

            # 开始下载
            await self.distribution.start_download(task, sources, file_info)

            logger.info(f"Started download: {task.task_id}")

            # 启动进度监控
            asyncio.create_task(self._monitor_download(task.task_id))

            return task

        except Exception as e:
            logger.error(f"Download failed: {e}")
            self._set_error(str(e))
            self._set_state(SystemState.ERROR)
            return None

    async def pause_update(self, task_id: str):
        """暂停更新"""
        if task_id in self.active_tasks:
            await self.distribution.pause_download(task_id)
            logger.info(f"Paused update: {task_id}")

    async def resume_update(self, task_id: str):
        """恢复更新"""
        if task_id in self.active_tasks:
            await self.distribution.resume_download(task_id)
            logger.info(f"Resumed update: {task_id}")

    async def cancel_update(self, task_id: str):
        """取消更新"""
        if task_id in self.active_tasks:
            await self.distribution.stop_download(task_id)
            del self.active_tasks[task_id]
            logger.info(f"Cancelled update: {task_id}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 版本验证
    # ═══════════════════════════════════════════════════════════════════════════

    async def verify_update(self, version: VersionInfo) -> Tuple[bool, float]:
        """
        验证更新包

        Returns:
            (is_valid, trust_score)
        """
        async with self._lock:
            self._set_state(SystemState.VERIFYING)

        try:
            if self.config.require_signatures:
                return await self.signature_service.verify_version(version)
            else:
                return True, 1.0

        finally:
            self._set_state(SystemState.IDLE)

    # ═══════════════════════════════════════════════════════════════════════════
    # 版本应用
    # ═══════════════════════════════════════════════════════════════════════════

    async def apply_update(self, task_id: str) -> bool:
        """
        应用更新

        Args:
            task_id: 任务ID

        Returns:
            True 如果成功
        """
        task = self.active_tasks.get(task_id)
        if not task:
            return False

        async with self._lock:
            self._set_state(SystemState.APPLYING)

        try:
            task.stage = UpdateStage.APPLYING

            # 组装文件
            output_path = Path.home() / ".hermes-desktop" / "updates" / f"{task.to_version}.bin"
            success = self.distribution.chunk_manager.assemble_file(output_path)

            if success:
                task.stage = UpdateStage.COMPLETED
                self.config.current_version = task.to_version

                logger.info(f"Update applied: {task.to_version}")

                # 广播版本升级
                await self._broadcast_version_upgrade(task.to_version)

                return True
            else:
                raise Exception("Failed to assemble update file")

        except Exception as e:
            logger.error(f"Apply update failed: {e}")
            task.error = str(e)
            task.stage = UpdateStage.ROLLBACK
            self._set_error(str(e))
            return False

        finally:
            self._set_state(SystemState.IDLE)

    # ═══════════════════════════════════════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════════════════════════════════════

    def _set_state(self, state: SystemState):
        """设置状态"""
        self.state = state
        self.status.state = state

        if self.on_status_change:
            asyncio.create_task(self.on_status_change(state))

    def _set_error(self, error: str):
        """设置错误"""
        self.status.error = error
        logger.error(f"Update system error: {error}")

    def _parse_version_code(self, version: str) -> int:
        """解析版本号"""
        parts = version.lstrip('v').split('.')
        code = 0
        for i, part in enumerate(parts[:3]):
            try:
                code += int(part) * (1000 ** (2 - i))
            except ValueError:
                code += int(part.split('-')[0]) * (1000 ** (2 - i))
        return code

    async def _get_download_sources(self, version: VersionInfo) -> List[NodeInfo]:
        """获取下载源"""
        # 从种子节点获取
        seeds = await self.seed_manager.get_best_seeds(
            count=self.config.max_download_sources
        )

        # 从 DHT 获取拥有该版本的节点
        closest = await self.dht_node.get_closest_nodes(self.dht_node.node_id, self.config.max_peers)

        # 合并并去重
        all_sources = {n.node_id: n for n in seeds}
        for n in closest:
            if n.state == NodeState.ONLINE:
                all_sources[n.node_id] = n

        return list(all_sources.values())

    async def _register_as_seed(self):
        """注册为种子节点"""
        node = NodeInfo(
            node_id=self.dht_node.node_id,
            version=self.config.current_version,
            state=NodeState.ONLINE,
            endpoint="127.0.0.1:0",
            is_seed=True
        )

        await self.seed_manager.register_seed(node)
        await self.reputation.register_node(node)

        logger.info(f"Registered as seed node: {node.node_id[:8]}")

    async def _broadcast_version_upgrade(self, version: str):
        """广播版本升级"""
        version_info = self.version_cache.get(version)
        if not version_info:
            return

        node = NodeInfo(
            node_id=self.dht_node.node_id,
            version=version,
            state=NodeState.ONLINE
        )

        await self.propagator.announce_version(version_info, node)

    async def _check_loop(self):
        """定期检查循环"""
        while self._running:
            try:
                await asyncio.sleep(self.config.check_interval)

                if self.config.update_strategy in (UpdateStrategy.AUTO, UpdateStrategy.NOTIFY):
                    await self.check_for_updates()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Check loop error: {e}")

    async def _monitor_download(self, task_id: str):
        """监控下载进度"""
        while self._running and task_id in self.active_tasks:
            task = self.active_tasks.get(task_id)
            if not task:
                break

            # 更新状态
            self.status.download_progress = task.progress

            if self.distribution:
                speed = self.distribution.calculate_speed()
                self.status.download_speed = speed

                if speed > 0:
                    remaining = (1 - task.progress) * task.total_chunks * 1024 * 1024 / speed
                    self.status.remaining_time = remaining

            # 触发回调
            if self.on_download_progress:
                await self.on_download_progress(task)

            # 检查完成
            if task.stage == UpdateStage.COMPLETED:
                break

            await asyncio.sleep(1)

    # ═══════════════════════════════════════════════════════════════════════════
    # 状态查询
    # ═══════════════════════════════════════════════════════════════════════════

    def get_status(self) -> UpdateSystemStatus:
        """获取系统状态"""
        return self.status

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'state': self.state.value,
            'active_tasks': len(self.active_tasks),
            'connected_peers': len(self.dht_node.get_closest_nodes(self.dht_node.node_id)) if self.dht_node else 0,
            'reputation': self.reputation.get_node_reputation(self.dht_node.node_id) if self.reputation else None,
            'download_progress': self.status.download_progress,
            'download_speed': format_speed(self.status.download_speed),
            'remaining_time': format_duration(self.status.remaining_time)
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 全局实例
# ═══════════════════════════════════════════════════════════════════════════════


_update_manager: Optional[UpdateManager] = None


def get_update_manager() -> UpdateManager:
    """获取全局更新管理器"""
    global _update_manager
    if _update_manager is None:
        _update_manager = UpdateManager()
    return _update_manager


async def initialize_update_system(config: UpdateConfig = None) -> UpdateManager:
    """初始化更新系统"""
    manager = get_update_manager()
    if config:
        manager.config = config
    await manager.initialize()
    return manager


async def shutdown_update_system():
    """关闭更新系统"""
    global _update_manager
    if _update_manager:
        await _update_manager.shutdown()
        _update_manager = None
