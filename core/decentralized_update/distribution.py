# distribution.py — BitTorrent 式分片分发

"""
BitTorrent 式分片分发
=====================

核心理念：利用 BitTorrent 的思想实现高效、去中心化的文件分发。

分发机制：
1. 文件分片 - 将更新包分割成固定大小的分片
2. Piece Map - 追踪已下载的分片
3. 最优源选择 - 优先从高信誉、高带宽节点下载
4. 并行下载 - 同时从多个节点下载不同分片
5. 断点续传 - 支持分片级别的断点续传
"""

import asyncio
import hashlib
import logging
import os
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from enum import Enum

from .models import (
    NodeInfo, ChunkInfo, UpdateTask, UpdateStage,
    NodeState, MerkleTree, format_size, format_speed
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class DistributionConfig:
    """分发配置"""
    chunk_size: int = 512 * 1024          # 分片大小 (512KB)
    max_concurrent_chunks: int = 5        # 最大并发分片数
    max_sources_per_chunk: int = 3        # 每个分片最大源数
    min_sources: int = 1                  # 最小源数
    request_timeout: float = 30.0          # 请求超时 (秒)
    download_retry: int = 3               # 下载重试次数
    rarest_first: bool = True              # 稀缺优先策略
    seed_bandwidth_threshold: int = 100 * 1024 * 1024  # 种子带宽阈值 (100MB/s)


# ═══════════════════════════════════════════════════════════════════════════════
# 分片状态
# ═══════════════════════════════════════════════════════════════════════════════


class ChunkState(Enum):
    """分片状态"""
    PENDING = "pending"       # 待下载
    DOWNLOADING = "downloading"  # 下载中
    COMPLETED = "completed"      # 已完成
    VERIFIED = "verified"       # 已验证
    FAILED = "failed"           # 失败


@dataclass
class ChunkDownload:
    """分片下载信息"""
    chunk_id: str                            # 分片ID
    state: ChunkState = ChunkState.PENDING
    data: Optional[bytes] = None              # 分片数据
    hash: str = ""                            # 期望哈希
    sources: List[NodeInfo] = field(default_factory=list)  # 可用源
    active_source: Optional[NodeInfo] = None  # 当前下载源
    retry_count: int = 0                      # 重试次数
    download_start: float = 0                   # 下载开始时间
    progress: float = 0                        # 下载进度 (0-1)


# ═══════════════════════════════════════════════════════════════════════════════
# 分片管理器
# ═══════════════════════════════════════════════════════════════════════════════


class ChunkManager:
    """
    分片管理器

    管理文件的分片和下载状态
    """

    def __init__(self, config: DistributionConfig = None):
        self.config = config or DistributionConfig()
        self.chunks: Dict[str, ChunkDownload] = {}  # chunk_id -> ChunkDownload
        self.merkle_tree: Optional[MerkleTree] = None
        self.total_chunks: int = 0
        self.completed_chunks: int = 0
        self._lock = asyncio.Lock()

    def initialize(self, file_path: Path) -> List[ChunkInfo]:
        """
        初始化分片

        Args:
            file_path: 文件路径

        Returns:
            分片信息列表
        """
        # 读取文件
        with open(file_path, 'rb') as f:
            data = f.read()

        # 计算文件哈希
        file_hash = hashlib.sha256(data).hexdigest()

        # 分片
        chunk_infos = []
        chunk_data_list = []

        chunk_size = self.config.chunk_size
        for i in range(0, len(data), chunk_size):
            chunk_data = data[i:i + chunk_size]
            chunk_hash = hashlib.sha256(chunk_data).hexdigest()

            chunk_id = f"chunk_{i // chunk_size:04d}"

            chunk_info = ChunkInfo(
                chunk_id=chunk_id,
                hash=chunk_hash,
                size=len(chunk_data),
                index=i // chunk_size,
                total_chunks=(len(data) + chunk_size - 1) // chunk_size
            )

            chunk_infos.append(chunk_info)
            chunk_data_list.append(chunk_data)

            self.chunks[chunk_id] = ChunkDownload(
                chunk_id=chunk_id,
                hash=chunk_hash,
                sources=[],
                retry_count=0
            )

        # 构建 Merkle 树
        self.merkle_tree = MerkleTree(chunk_data_list)
        self.total_chunks = len(chunk_infos)

        logger.info(
            f"Initialized {self.total_chunks} chunks, "
            f"total size: {format_size(len(data))}"
        )

        return chunk_infos

    async def mark_have(self, chunk_id: str, source: NodeInfo):
        """标记节点拥有某个分片"""
        async with self._lock:
            if chunk_id in self.chunks:
                chunk = self.chunks[chunk_id]
                if source not in chunk.sources:
                    chunk.sources.append(source)

    async def get_pending_chunks(self) -> List[ChunkDownload]:
        """获取待下载的分片"""
        async with self._lock:
            pending = [
                c for c in self.chunks.values()
                if c.state in (ChunkState.PENDING, ChunkState.FAILED)
            ]

            if self.config.rarest_first:
                # 稀缺优先：先下载拥有者最少的分片
                pending.sort(key=lambda c: len(c.sources))
            else:
                # 顺序下载
                pending.sort(key=lambda c: c.chunk_id)

            return pending

    async def request_chunk(
        self,
        chunk_id: str,
        preferred_sources: List[NodeInfo] = None
    ) -> Optional[NodeInfo]:
        """
        请求分片下载

        Args:
            chunk_id: 分片ID
            preferred_sources: 优先源列表

        Returns:
            分配的下载源节点
        """
        async with self._lock:
            if chunk_id not in self.chunks:
                return None

            chunk = self.chunks[chunk_id]

            if chunk.state == ChunkState.COMPLETED:
                return None

            # 选择最优源
            sources = preferred_sources or chunk.sources
            if not sources:
                return None

            # 按信誉和带宽排序
            sources.sort(
                key=lambda n: n.reputation_score * 0.6 + n.bandwidth_score * 0.4,
                reverse=True
            )

            # 选择前 N 个源
            selected = sources[:self.config.max_sources_per_chunk]

            # 分配第一个可用源
            chunk.active_source = selected[0] if selected else None
            chunk.state = ChunkState.DOWNLOADING
            chunk.download_start = time.time()

            return chunk.active_source

    async def complete_chunk(
        self,
        chunk_id: str,
        data: bytes
    ) -> bool:
        """
        完成分片下载

        Args:
            chunk_id: 分片ID
            data: 分片数据

        Returns:
            True 如果验证通过
        """
        async with self._lock:
            if chunk_id not in self.chunks:
                return False

            chunk = self.chunks[chunk_id]

            # 验证哈希
            expected_hash = chunk.hash
            actual_hash = hashlib.sha256(data).hexdigest()

            if actual_hash != expected_hash:
                logger.warning(f"Chunk {chunk_id} hash mismatch")
                chunk.state = ChunkState.FAILED
                chunk.retry_count += 1
                return False

            # 验证 Merkle 证明
            if self.merkle_tree:
                proof = self.merkle_tree.get_proof(chunk.index)
                if not MerkleTree.verify_proof(self.merkle_tree.root, actual_hash, proof):
                    logger.warning(f"Chunk {chunk_id} Merkle proof verification failed")
                    chunk.state = ChunkState.FAILED
                    return False

            chunk.data = data
            chunk.state = ChunkState.VERIFIED
            chunk.progress = 1.0
            self.completed_chunks += 1

            logger.debug(f"Chunk {chunk_id} completed ({self.completed_chunks}/{self.total_chunks})")
            return True

    async def reassign_chunk(self, chunk_id: str) -> bool:
        """重新分配失败的 chunk"""
        async with self._lock:
            if chunk_id not in self.chunks:
                return False

            chunk = self.chunks[chunk_id]

            if chunk.retry_count >= self.config.download_retry:
                logger.error(f"Chunk {chunk_id} exceeded max retries")
                return False

            chunk.state = ChunkState.PENDING
            chunk.active_source = None
            chunk.retry_count += 1

            return True

    @property
    def progress(self) -> float:
        """下载进度"""
        if self.total_chunks == 0:
            return 0
        return self.completed_chunks / self.total_chunks

    def assemble_file(self, output_path: Path) -> bool:
        """
        组装文件

        Args:
            output_path: 输出路径

        Returns:
            True 如果成功
        """
        # 检查所有分片是否完成
        incomplete = [
            c.chunk_id for c in self.chunks.values()
            if c.state != ChunkState.VERIFIED
        ]

        if incomplete:
            logger.error(f"Cannot assemble: {len(incomplete)} chunks incomplete")
            return False

        # 合并分片
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'wb') as f:
            for i in range(self.total_chunks):
                chunk_id = f"chunk_{i:04d}"
                chunk = self.chunks.get(chunk_id)
                if chunk and chunk.data:
                    f.write(chunk.data)

        logger.info(f"File assembled: {output_path}")
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# 分发器
# ═══════════════════════════════════════════════════════════════════════════════


class DistributionManager:
    """
    分发管理器

    协调多个分片的并行下载
    """

    def __init__(self, config: DistributionConfig = None):
        self.config = config or DistributionConfig()
        self.chunk_manager = ChunkManager(config)
        self.active_tasks: Dict[str, UpdateTask] = {}  # task_id -> task
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._download_callbacks: Dict[str, Callable] = {}  # chunk_id -> callback

        # 统计
        self.total_downloaded = 0
        self.total_bytes_downloaded = 0
        self.download_speeds: List[float] = []  # 最近速度记录

    async def start_download(
        self,
        task: UpdateTask,
        sources: List[NodeInfo],
        file_info: Dict[str, Any]
    ) -> UpdateTask:
        """
        开始下载任务

        Args:
            task: 更新任务
            sources: 可用的下载源
            file_info: 文件信息 (path, chunks, etc.)

        Returns:
            更新后的任务
        """
        task.stage = UpdateStage.DOWNLOADING
        task.sources = sources

        # 初始化分片管理器
        file_path = Path(file_info.get('path', ''))
        if file_path.exists():
            self.chunk_manager.initialize(file_path)

        # 更新任务信息
        task.total_chunks = self.chunk_manager.total_chunks
        self.active_tasks[task.task_id] = task

        logger.info(
            f"Starting download task {task.task_id}: "
            f"{task.total_chunks} chunks, {len(sources)} sources"
        )

        # 启动下载循环
        self._running = True
        self._tasks.append(asyncio.create_task(self._download_loop(task.task_id)))

        return task

    async def stop_download(self, task_id: str):
        """停止下载任务"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            task.stage = UpdateStage.IDLE
            task.error = "Cancelled by user"

        self._running = False

        for t in self._tasks:
            t.cancel()

        self._tasks.clear()

        logger.info(f"Download task {task_id} stopped")

    async def pause_download(self, task_id: str):
        """暂停下载任务"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            task.stage = UpdateStage.IDLE
            logger.info(f"Download task {task_id} paused")

    async def resume_download(self, task_id: str):
        """恢复下载任务"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            task.stage = UpdateStage.DOWNLOADING
            logger.info(f"Download task {task_id} resumed")

    async def _download_loop(self, task_id: str):
        """下载循环"""
        while self._running:
            try:
                # 获取待下载分片
                pending = await self.chunk_manager.get_pending_chunks()

                if not pending:
                    # 所有分片已分配，等待完成
                    await asyncio.sleep(1)
                    continue

                # 检查并发数
                active_count = sum(
                    1 for c in self.chunk_manager.chunks.values()
                    if c.state == ChunkState.DOWNLOADING
                )

                if active_count >= self.config.max_concurrent_chunks:
                    await asyncio.sleep(0.5)
                    continue

                # 分配分片下载
                for chunk in pending[:self.config.max_concurrent_chunks - active_count]:
                    node = await self.chunk_manager.request_chunk(chunk.chunk_id)
                    if node:
                        asyncio.create_task(self._download_chunk(task_id, chunk.chunk_id, node))

                await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Download loop error: {e}")
                await asyncio.sleep(1)

    async def _download_chunk(
        self,
        task_id: str,
        chunk_id: str,
        source: NodeInfo
    ):
        """下载单个分片"""
        if task_id not in self.active_tasks:
            return

        task = self.active_tasks[task_id]

        try:
            # 模拟下载过程
            # 实际实现中会从 source 节点请求分片数据
            chunk = self.chunk_manager.chunks.get(chunk_id)
            if not chunk:
                return

            # 模拟从网络下载
            await asyncio.sleep(0.1)  # 模拟网络延迟

            # 假设下载成功
            data = b"fake_chunk_data"  # 实际会从 source 获取
            success = await self.chunk_manager.complete_chunk(chunk_id, data)

            if success:
                task.downloaded_chunks.add(chunk_id)
                self.total_chunks_downloaded = self.chunk_manager.completed_chunks
                self.total_bytes_downloaded += chunk.size

                # 更新进度
                task.progress = self.chunk_manager.progress

                # 检查是否完成
                if self.chunk_manager.completed_chunks >= self.chunk_manager.total_chunks:
                    task.stage = UpdateStage.COMPLETED
                    self._running = False
            else:
                # 重试
                await self.chunk_manager.reassign_chunk(chunk_id)

        except Exception as e:
            logger.error(f"Chunk download error: {chunk_id}: {e}")
            await self.chunk_manager.reassign_chunk(chunk_id)

    def get_task_status(self, task_id: str) -> Optional[UpdateTask]:
        """获取任务状态"""
        return self.active_tasks.get(task_id)

    def calculate_speed(self) -> float:
        """计算当前下载速度"""
        if not self.download_speeds:
            return 0
        return sum(self.download_speeds[-10:]) / len(self.download_speeds[-10:])


# ═══════════════════════════════════════════════════════════════════════════════
# CDN 优先策略
# ═══════════════════════════════════════════════════════════════════════════════


class CDNOptimizer:
    """
    CDN 优先策略

    根据网络条件选择最优的分发源
    """

    def __init__(self):
        self.cdn_nodes: Dict[str, NodeInfo] = {}  # CDN 节点列表
        self.region_cache: Dict[str, List[str]] = {}  # region -> node_ids

    def register_cdn(self, node: NodeInfo, region: str = None):
        """注册 CDN 节点"""
        self.cdn_nodes[node.node_id] = node
        if region:
            if region not in self.region_cache:
                self.region_cache[region] = []
            if node.node_id not in self.region_cache[region]:
                self.region_cache[region].append(node.node_id)

    def get_best_source(
        self,
        chunk_id: str,
        available_sources: List[NodeInfo],
        user_region: str = None
    ) -> Optional[NodeInfo]:
        """
        获取最优源

        优先级：
        1. 同区域 CDN
        2. 高带宽 CDN
        3. 高信誉节点
        """
        candidates = []

        # 同区域 CDN
        if user_region and user_region in self.region_cache:
            region_nodes = [
                self.cdn_nodes[nid]
                for nid in self.region_cache[user_region]
                if nid in self.cdn_nodes
            ]
            candidates.extend(region_nodes)

        # 添加其他 CDN
        candidates.extend([n for n in available_sources if n.is_seed])

        # 如果没有 CDN，使用普通节点
        if not candidates:
            candidates = available_sources

        if not candidates:
            return None

        # 按评分排序
        candidates.sort(
            key=lambda n: (
                n.bandwidth_score * 0.5 +
                n.reputation_score * 0.3 +
                n.stability_score * 0.2
            ),
            reverse=True
        )

        return candidates[0]


# ═══════════════════════════════════════════════════════════════════════════════
# 全局实例
# ═══════════════════════════════════════════════════════════════════════════════


_distribution_manager: Optional[DistributionManager] = None
_cdn_optimizer: Optional[CDNOptimizer] = None


def get_distribution_manager() -> DistributionManager:
    """获取全局分发管理器"""
    global _distribution_manager
    if _distribution_manager is None:
        _distribution_manager = DistributionManager()
    return _distribution_manager


def get_cdn_optimizer() -> CDNOptimizer:
    """获取全局 CDN 优化器"""
    global _cdn_optimizer
    if _cdn_optimizer is None:
        _cdn_optimizer = CDNOptimizer()
    return _cdn_optimizer
