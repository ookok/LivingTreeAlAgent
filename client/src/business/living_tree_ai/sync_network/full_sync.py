"""
Full Sync - 全量同步（分片 + 校验）
==================================

功能：
- 快照生成
- 分片下载
- 完整性校验
- 多源冗余

Author: LivingTreeAI Community
"""

import asyncio
import hashlib
import time
import json
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any, List, Dict
from enum import Enum
from collections import defaultdict


class ShardStatus(Enum):
    """分片状态"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    VERIFIED = "verified"
    FAILED = "failed"
    APPLIED = "applied"


@dataclass
class Shard:
    """数据分片"""
    shard_id: str
    index: int
    total_shards: int
    data_type: str
    data: Optional[bytes] = None
    hash: str = ""
    size: int = 0
    status: ShardStatus = ShardStatus.PENDING
    sources: List[str] = field(default_factory=list)  # 可用的源节点
    download_attempts: int = 0
    max_attempts: int = 3

    def verify(self) -> bool:
        """验证分片完整性"""
        if not self.data:
            return False
        actual_hash = hashlib.sha256(self.data).hexdigest()
        return actual_hash == self.hash


@dataclass
class Snapshot:
    """完整快照"""
    snapshot_id: str
    node_id: str  # 快照来源节点
    created_at: float
    expires_at: float
    total_shards: int
    total_size: int
    root_hash: str  # 整个快照的根哈希
    data_types: List[str]
    shards: List[Shard] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() > self.expires_at

    def get_status_summary(self) -> dict:
        """获取状态摘要"""
        status_counts = defaultdict(int)
        for shard in self.shards:
            status_counts[shard.status.value] += 1
        return dict(status_counts)


class FullSync:
    """
    全量同步

    用于：
    - 新节点加入网络
    - 节点数据损坏修复
    - 网络分裂后的合并

    特点：
    - 分片并行下载
    - 多源冗余
    - 完整性校验
    """

    # 配置
    DEFAULT_SHARD_SIZE = 1024 * 1024  # 1MB per shard
    MAX_PARALLEL_DOWNLOADS = 5
    SNAPSHOT_EXPIRY = 3600  # 1小时

    def __init__(
        self,
        node_id: str,
        get_data_func: Optional[Callable[[List[str]], dict]] = None,
        apply_data_func: Optional[Callable[[dict], Awaitable]] = None,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
    ):
        self.node_id = node_id

        # 数据提供函数
        self._get_data = get_data_func or (lambda types: {})
        self._apply_data = apply_data_func or (lambda data: None)
        self._send_func = send_func

        # 当前快照
        self.current_snapshot: Optional[Snapshot] = None

        # 分片下载进度
        self.download_progress: Dict[str, float] = {}

        # 回调
        self._on_progress: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

    # ========== 快照生成 ==========

    async def create_snapshot(self, data_types: List[str]) -> Snapshot:
        """
        创建完整快照

        Args:
            data_types: 要包含的数据类型列表

        Returns:
            Snapshot对象
        """
        # 收集数据
        all_data = await self._get_data(data_types)

        # 序列化数据
        data_bytes = json.dumps(all_data, default=str).encode()
        total_size = len(data_bytes)

        # 生成分片
        shards = self._create_shards(data_bytes, data_types)

        # 计算根哈希
        root_hash = self._compute_root_hash(shards)

        # 创建快照
        snapshot = Snapshot(
            snapshot_id=self._generate_snapshot_id(),
            node_id=self.node_id,
            created_at=time.time(),
            expires_at=time.time() + self.SNAPSHOT_EXPIRY,
            total_shards=len(shards),
            total_size=total_size,
            root_hash=root_hash,
            data_types=data_types,
            shards=shards,
            metadata={
                "data_types": data_types,
                "shard_count": len(shards),
            },
        )

        self.current_snapshot = snapshot
        return snapshot

    def _create_shards(self, data_bytes: bytes, data_types: List[str]) -> List[Shard]:
        """将数据分片"""
        shards = []
        shard_size = self.DEFAULT_SHARD_SIZE

        for i in range(0, len(data_bytes), shard_size):
            shard_data = data_bytes[i:i + shard_size]
            shard = Shard(
                shard_id=f"{self.node_id}:{len(shards)}",
                index=len(shards),
                total_shards=(len(data_bytes) + shard_size - 1) // shard_size,
                data_type=",".join(data_types),
                data=shard_data,
                hash=hashlib.sha256(shard_data).hexdigest(),
                size=len(shard_data),
            )
            shards.append(shard)

        return shards

    def _compute_root_hash(self, shards: List[Shard]) -> str:
        """计算根哈希"""
        if not shards:
            return ""

        # 构建Merkle树根
        hashes = [s.hash for s in shards]
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                new_hashes.append(hashlib.sha256(combined.encode()).hexdigest())
            hashes = new_hashes

        return hashes[0] if hashes else ""

    def _generate_snapshot_id(self) -> str:
        """生成快照ID"""
        data = f"{self.node_id}:{time.time()}:{random.randint(0, 1000000)}"
        return hashlib.sha256(data.encode()).hexdigest()[:24]

    # ========== 快照获取 ==========

    async def get_snapshot_from_peer(self, peer_id: str) -> Optional[Snapshot]:
        """从指定节点获取快照"""
        if not self._send_func:
            return None

        try:
            response = await self._send_func(peer_id, {
                "type": "full_sync",
                "action": "get_snapshot_info",
                "node_id": self.node_id,
            })

            if not response.get("available"):
                return None

            # 创建快照对象
            snapshot = Snapshot(
                snapshot_id=response["snapshot_id"],
                node_id=peer_id,
                created_at=response["created_at"],
                expires_at=response["expires_at"],
                total_shards=response["total_shards"],
                total_size=response["total_size"],
                root_hash=response["root_hash"],
                data_types=response["data_types"],
            )

            return snapshot

        except Exception:
            return None

    async def get_snapshots_from_multiple_peers(self, peer_ids: List[str]) -> List[Snapshot]:
        """从多个节点获取快照信息，选择最新的"""
        snapshots = []

        for peer_id in peer_ids:
            snapshot = await self.get_snapshot_from_peer(peer_id)
            if snapshot:
                snapshots.append(snapshot)

        # 选择最新的
        if not snapshots:
            return []

        return sorted(snapshots, key=lambda s: s.created_at, reverse=True)

    # ========== 分片下载 ==========

    async def download_shard(
        self,
        shard: Shard,
        sources: List[str],
    ) -> bool:
        """
        从多个源下载分片

        Returns:
            是否成功
        """
        shard.status = ShardStatus.DOWNLOADING
        shard.download_attempts += 1

        for source in sources:
            try:
                if not self._send_func:
                    continue

                response = await self._send_func(source, {
                    "type": "full_sync",
                    "action": "get_shard",
                    "shard_id": shard.shard_id,
                    "snapshot_id": self.current_snapshot.snapshot_id if self.current_snapshot else None,
                    "node_id": self.node_id,
                })

                shard_data = response.get("data")
                if shard_data:
                    shard.data = shard_data
                    if shard.verify():
                        shard.status = ShardStatus.VERIFIED
                        return True

            except Exception:
                continue

        shard.status = ShardStatus.FAILED
        return False

    async def download_snapshot(
        self,
        snapshot: Snapshot,
        sources: List[str],
    ) -> bool:
        """
        下载完整快照

        流程：
        1. 并行下载所有分片
        2. 验证完整性
        3. 应用数据
        """
        self.current_snapshot = snapshot

        # 并行下载分片（限制并发数）
        semaphore = asyncio.Semaphore(self.MAX_PARALLEL_DOWNLOADS)

        async def download_with_semaphore(shard: Shard):
            async with semaphore:
                return await self.download_shard(shard, sources)

        tasks = [download_with_semaphore(shard) for shard in snapshot.shards]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 检查所有分片
        success_count = sum(
            1 for r in results if r is True
        )

        if success_count != len(snapshot.shards):
            # 部分失败
            if self._on_error:
                self._on_error(f"Only {success_count}/{len(snapshot.shards)} shards downloaded")
            return False

        # 组装数据
        full_data = b"".join(shard.data for shard in sorted(snapshot.shards, key=lambda s: s.index))

        # 验证根哈希
        actual_root = self._compute_root_hash(snapshot.shards)
        if actual_root != snapshot.root_hash:
            if self._on_error:
                self._on_error("Root hash mismatch")
            return False

        # 应用数据
        try:
            data_dict = json.loads(full_data.decode())
            await self._apply_data(data_dict)
        except Exception as e:
            if self._on_error:
                self._on_error(f"Failed to apply data: {e}")
            return False

        # 更新状态
        for shard in snapshot.shards:
            shard.status = ShardStatus.APPLIED

        if self._on_complete:
            self._on_complete()

        return True

    # ========== 处理请求 ==========

    async def handle_sync_request(self, request: dict) -> dict:
        """处理同步请求"""
        action = request.get("action")
        requester = request.get("node_id")

        if action == "get_snapshot_info":
            if not self.current_snapshot:
                return {"available": False}

            if self.current_snapshot.is_expired():
                return {"available": False}

            return {
                "available": True,
                "snapshot_id": self.current_snapshot.snapshot_id,
                "created_at": self.current_snapshot.created_at,
                "expires_at": self.current_snapshot.expires_at,
                "total_shards": self.current_snapshot.total_shards,
                "total_size": self.current_snapshot.total_size,
                "root_hash": self.current_snapshot.root_hash,
                "data_types": self.current_snapshot.data_types,
            }

        elif action == "get_shard":
            shard_id = request.get("shard_id")
            if not self.current_snapshot:
                return {"error": "No snapshot"}

            for shard in self.current_snapshot.shards:
                if shard.shard_id == shard_id:
                    return {"data": shard.data}

            return {"error": "Shard not found"}

        return {}

    # ========== 进度追踪 ==========

    def get_download_progress(self) -> dict:
        """获取下载进度"""
        if not self.current_snapshot:
            return {}

        total = len(self.current_snapshot.shards)
        completed = sum(
            1 for s in self.current_snapshot.shards
            if s.status in (ShardStatus.VERIFIED, ShardStatus.APPLIED)
        )

        return {
            "total_shards": total,
            "completed_shards": completed,
            "progress_percent": (completed / total * 100) if total > 0 else 0,
            "total_size": self.current_snapshot.total_size,
        }

    def set_progress_callback(self, callback: Callable):
        """设置进度回调"""
        self._on_progress = callback

    def set_complete_callback(self, callback: Callable):
        """设置完成回调"""
        self._on_complete = callback

    def set_error_callback(self, callback: Callable):
        """设置错误回调"""
        self._on_error = callback


# 导入random
import random

# 全局单例
_full_instance: Optional[FullSync] = None


def get_full_sync(node_id: str = "local") -> FullSync:
    """获取全量同步单例"""
    global _full_instance
    if _full_instance is None:
        _full_instance = FullSync(node_id)
    return _full_instance