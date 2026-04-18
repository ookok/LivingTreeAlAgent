"""
Sync Manager - 同步管理器
=========================

整合三层同步体系：
1. 事件同步（实时） - Gossip协议
2. 增量同步（定期） - Merkle树 + 版本向量
3. 全量同步（兜底） - 分片 + 校验

Author: LivingTreeAI Community
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any, List, Dict
from enum import Enum

from .event_sync import GossipSync, EventType, SyncEvent, get_gossip_sync
from .incremental_sync import IncrementalSync, DataType, VersionVector, get_incremental_sync
from .full_sync import FullSync, Snapshot, get_full_sync
from .consistency import ConsistencyModel, ConsistencyLevel, get_consistency_model


class SyncConfig:
    """同步配置"""

    # 同步频率配置（秒）
    SYNC_FREQUENCY = {
        "event_sync": 0,       # 事件同步实时
        "node_status": 60,     # 节点状态：1分钟
        "cache_index": 300,     # 缓存索引：5分钟
        "credit_records": 3600, # 贡献记录：1小时
        "specialty_info": 1800, # 专长信息：30分钟
    }

    # 同步伙伴数量
    SYNC_PARTNER_COUNT = 3

    # 差异化同步阈值
    FULL_SYNC_THRESHOLD = 0.5  # 数据差异超过50%时触发全量同步

    def __init__(self):
        # 启用的同步类型
        self.enabled = {
            "event_sync": True,
            "incremental_sync": True,
            "full_sync": True,
        }

        # 同步伙伴
        self.known_peers: List[str] = []

        # 自动同步
        self.auto_sync = True
        self.sync_interval = 300  # 基础同步间隔：5分钟

    def get_frequency(self, sync_type: str) -> float:
        """获取同步频率"""
        return self.SYNC_FREQUENCY.get(sync_type, self.sync_interval)


@dataclass
class SyncPartner:
    """同步伙伴"""
    node_id: str
    last_sync: float = 0
    sync_count: int = 0
    success_count: int = 0
    avg_latency: float = 0
    reputation: float = 1.0
    is_stable: bool = False
    data互补: List[str] = field(default_factory=list)  # 互补的数据类型

    @property
    def success_rate(self) -> float:
        if self.sync_count == 0:
            return 1.0
        return self.success_count / self.sync_count


@dataclass
class SyncStats:
    """同步统计"""
    total_syncs: int = 0
    successful_syncs: int = 0
    failed_syncs: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    event_broadcasts: int = 0
    incremental_syncs: int = 0
    full_syncs: int = 0
    conflicts_resolved: int = 0
    last_sync_time: float = 0

    @property
    def success_rate(self) -> float:
        if self.total_syncs == 0:
            return 1.0
        return self.successful_syncs / self.total_syncs


class SyncManager:
    """
    同步管理器

    功能：
    1. 整合三层同步
    2. 智能伙伴选择
    3. 差异化同步频率
    4. 同步调度
    """

    def __init__(
        self,
        node_id: str,
        config: Optional[SyncConfig] = None,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
    ):
        self.node_id = node_id
        self.config = config or SyncConfig()
        self._send_func = send_func

        # 初始化三层同步
        self.gossip = get_gossip_sync(node_id)
        self.incremental = get_incremental_sync(node_id)
        self.full_sync = get_full_sync(node_id)
        self.consistency = get_consistency_model(node_id)

        # 同步伙伴
        self.partners: Dict[str, SyncPartner] = {}

        # 统计
        self.stats = SyncStats()

        # 运行状态
        self._running = False
        self._sync_tasks: List[asyncio.Task] = []

        # 回调
        self._on_event_sync: Optional[Callable] = None
        self._on_sync_complete: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

    # ========== 节点管理 ==========

    def add_peer(self, peer_id: str):
        """添加同步伙伴"""
        if peer_id not in self.partners:
            self.partners[peer_id] = SyncPartner(node_id=peer_id)
            self.gossip.add_peer(peer_id)
            self.config.known_peers.append(peer_id)

    def remove_peer(self, peer_id: str):
        """移除同步伙伴"""
        if peer_id in self.partners:
            del self.partners[peer_id]
            self.gossip.remove_peer(peer_id)
            if peer_id in self.config.known_peers:
                self.config.known_peers.remove(peer_id)

    def select_sync_partners(self) -> List[str]:
        """
        选择同步伙伴

        策略：
        1. 稳定的高信誉节点
        2. 数据互补的节点
        3. 地理邻近的节点
        """
        partners = []

        # 1. 稳定的高信誉节点
        stable = [
            p.node_id for p in self.partners.values()
            if p.is_stable and p.reputation > 0.8
        ]
        partners.extend(stable[:2])

        # 2. 数据互补的节点
        complementary = [
            p.node_id for p in self.partners.values()
            if p.data互补 and p not in partners
        ]
        partners.extend(complementary[:2])

        # 3. 随机选择
        remaining = [
            p.node_id for p in self.partners.values()
            if p.node_id not in partners
        ]
        import random
        random.shuffle(remaining)
        partners.extend(remaining[:1])

        return partners[:self.config.SYNC_PARTNER_COUNT]

    # ========== 事件同步 ==========

    async def broadcast_event(
        self,
        event_type: EventType,
        data: dict,
    ) -> SyncEvent:
        """广播同步事件"""
        self.stats.event_broadcasts += 1

        if self._on_event_sync:
            self._on_event_sync(event_type, data)

        return await self.gossip.broadcast_event(event_type, data)

    async def broadcast_cache_index(self, cache_data: dict):
        """广播缓存索引更新"""
        return await self.broadcast_event(EventType.CACHE_INDEX_NEW, cache_data)

    async def broadcast_node_status(self, status_data: dict):
        """广播节点状态"""
        return await self.broadcast_event(EventType.NODE_STATUS_CHANGE, status_data)

    async def broadcast_contribution(self, contrib_data: dict):
        """广播贡献证明"""
        return await self.broadcast_event(EventType.CONTRIBUTION_NEW, contrib_data)

    # ========== 增量同步 ==========

    async def incremental_sync(self, peer_id: str) -> dict:
        """执行增量同步"""
        start_time = time.time()

        try:
            result = await self.incremental.sync_with_peer(peer_id)

            # 更新伙伴统计
            if peer_id in self.partners:
                partner = self.partners[peer_id]
                partner.sync_count += 1
                partner.success_count += 1
                partner.last_sync = time.time()

                # 更新平均延迟
                latency = time.time() - start_time
                partner.avg_latency = partner.avg_latency * 0.9 + latency * 0.1

            self.stats.incremental_syncs += 1
            self.stats.successful_syncs += 1

            return result

        except Exception as e:
            if peer_id in self.partners:
                self.partners[peer_id].sync_count += 1

            self.stats.failed_syncs += 1
            if self._on_error:
                self._on_error(f"Incremental sync failed with {peer_id}: {e}")

            return {"error": str(e)}

    async def periodic_incremental_sync(self):
        """定期增量同步"""
        while self._running:
            await asyncio.sleep(self.config.get_frequency("cache_index"))

            if not self.config.enabled.get("incremental_sync"):
                continue

            partners = self.select_sync_partners()
            for peer_id in partners:
                await self.incremental_sync(peer_id)

    # ========== 全量同步 ==========

    async def full_sync(self, peer_id: Optional[str] = None) -> bool:
        """
        执行全量同步

        Args:
            peer_id: 指定同步伙伴，为None则自动选择
        """
        start_time = time.time()

        try:
            # 选择伙伴
            if not peer_id:
                partners = self.select_sync_partners()
                peer_id = partners[0] if partners else None

            if not peer_id:
                return False

            # 获取快照
            snapshot = await self.full_sync.get_snapshot_from_peer(peer_id)
            if not snapshot:
                return False

            # 下载快照
            sources = [peer_id] + [p for p in self.select_sync_partners() if p != peer_id]
            success = await self.full_sync.download_snapshot(snapshot, sources)

            if success:
                self.stats.full_syncs += 1
                self.stats.successful_syncs += 1
            else:
                self.stats.failed_syncs += 1

            return success

        except Exception as e:
            self.stats.failed_syncs += 1
            if self._on_error:
                self._on_error(f"Full sync failed: {e}")
            return False

    async def should_trigger_full_sync(self) -> bool:
        """判断是否应该触发全量同步"""
        # 检查数据差异率
        total_items = sum(
            len(self.incremental.data_stores.get(dt, {}))
            for dt in DataType
        )

        if total_items == 0:
            return True

        # 简化判断：数据为空时触发全量同步
        return total_items < 10

    # ========== 调度运行 ==========

    async def start(self):
        """启动同步管理器"""
        self._running = True

        # 启动事件同步（Gossip已集成在广播中）

        # 启动增量同步任务
        incremental_task = asyncio.create_task(self.periodic_incremental_sync())
        self._sync_tasks.append(incremental_task)

    async def stop(self):
        """停止同步管理器"""
        self._running = False

        for task in self._sync_tasks:
            task.cancel()

        self._sync_tasks.clear()

    async def sync_once(self):
        """执行一次完整同步"""
        self.stats.total_syncs += 1

        # 1. 事件同步（广播本地状态）
        await self.broadcast_node_status({
            "node_id": self.node_id,
            "version_vector": self.incremental.version_vector.to_dict(),
            "timestamp": time.time(),
        })

        # 2. 检查是否需要全量同步
        if await self.should_trigger_full_sync():
            await self.full_sync()
        else:
            # 3. 增量同步
            partners = self.select_sync_partners()
            for peer_id in partners:
                await self.incremental_sync(peer_id)

        self.stats.last_sync_time = time.time()

        if self._on_sync_complete:
            self._on_sync_complete(self.stats)

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取同步统计"""
        return {
            "manager": {
                "total_syncs": self.stats.total_syncs,
                "success_rate": f"{self.stats.success_rate:.1%}",
                "bytes_sent": self.stats.total_bytes_sent,
                "bytes_received": self.stats.total_bytes_received,
            },
            "event_sync": self.gossip.get_stats(),
            "incremental_sync": {
                "data_types": [
                    {
                        "type": dt.value,
                        "items": len(self.incremental.data_stores.get(dt, {})),
                    }
                    for dt in DataType
                ],
            },
            "full_syncs": self.stats.full_syncs,
            "conflicts_resolved": self.stats.conflicts_resolved,
            "partners": {
                node_id: {
                    "success_rate": partner.success_rate,
                    "avg_latency_ms": f"{partner.avg_latency * 1000:.1f}",
                    "is_stable": partner.is_stable,
                }
                for node_id, partner in self.partners.items()
            },
        }

    # ========== 回调设置 ==========

    def set_event_sync_callback(self, callback: Callable):
        """设置事件同步回调"""
        self._on_event_sync = callback

    def set_sync_complete_callback(self, callback: Callable):
        """设置同步完成回调"""
        self._on_sync_complete = callback

    def set_error_callback(self, callback: Callable):
        """设置错误回调"""
        self._on_error = callback


# 全局单例
_sync_manager_instance: Optional[SyncManager] = None


def get_sync_manager(node_id: str = "local") -> SyncManager:
    """获取同步管理器单例"""
    global _sync_manager_instance
    if _sync_manager_instance is None:
        _sync_manager_instance = SyncManager(node_id)
    return _sync_manager_instance