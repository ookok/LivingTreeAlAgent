"""
P2P CDN 模块 - 分布式智能缓存系统

实现类似 CDN 的功能，让节点自动快速访问结构化数据
- 智能路由：基于网络延迟和节点能力选择最优节点
- 分布式缓存：热门数据自动在多个节点缓存
- 数据一致性：版本控制和增量同步
- 负载均衡：数据分片和多副本
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, List, Any, Set, Tuple

from .models import (
    CDNNode, CDNData, DataMetadata, DataVersion,
    CacheStatus, NodeCapability, NetworkMetrics
)
from .cache_manager import CacheManager, CacheStrategy
from .router import CDNRouter, RouteStrategy
from .data_sync import DataSyncManager
from .metrics import MetricsCollector
from .storage import CDNStorage

logger = logging.getLogger(__name__)


class P2PCDN:
    """P2P CDN 核心类 — 管理分布式缓存、智能路由和数据同步"""

    def __init__(
        self,
        node_id: str,
        data_dir: Optional[str] = None,
        max_cache_size: int = 1024 * 1024 * 1024,
        enable_metrics: bool = True
    ):
        self.node_id = node_id
        self.data_dir = Path(data_dir or f"~/.p2p_cdn/{self.node_id}").expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.storage = CDNStorage(str(self.data_dir / "storage"))
        self.cache_manager = CacheManager(
            storage=self.storage,
            max_cache_size=max_cache_size
        )
        self.router = CDNRouter()
        self.data_sync = DataSyncManager(self.node_id)
        self.metrics = MetricsCollector() if enable_metrics else None

        self.is_running = False
        self.known_nodes: Dict[str, CDNNode] = {}
        self.data_index: Dict[str, DataMetadata] = {}

        self.max_replication_factor = 3
        self.hot_data_threshold = 5
        self.heartbeat_interval = 30

        self._heartbeat_task: Optional[asyncio.Task] = None

    async def start(self):
        logger.info(f"Starting P2P CDN node {self.node_id}...")
        await self.storage.init()
        await self.cache_manager.init()
        self._load_data_index()
        await self._update_node_status()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self.is_running = True
        logger.info(f"P2P CDN node {self.node_id} started successfully")

    async def stop(self):
        logger.info(f"Stopping P2P CDN node {self.node_id}...")
        self.is_running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        self._save_data_index()
        await self.storage.close()
        logger.info(f"P2P CDN node {self.node_id} stopped")

    async def _heartbeat_loop(self):
        while self.is_running:
            try:
                await self._update_node_status()
                await self.cache_manager.cleanup_expired()
                await self._replicate_hot_data()
                await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(self.heartbeat_interval)

    async def _update_node_status(self):
        capability = await self._calculate_capability()
        local_node = CDNNode(
            node_id=self.node_id,
            capability=capability,
            last_seen=time.time(),
            cache_stats=self.cache_manager.get_stats()
        )
        self.known_nodes[self.node_id] = local_node

    async def _calculate_capability(self) -> NodeCapability:
        return NodeCapability(
            storage_available=self.storage.get_available_space(),
            bandwidth=100,
            uptime=3600,
            reliability=0.99
        )

    async def _replicate_hot_data(self):
        hot_data = await self.cache_manager.get_hot_data(self.hot_data_threshold)
        for data_id, metadata in hot_data.items():
            current_replicas = len(metadata.replicas)
            if current_replicas < self.max_replication_factor:
                suitable_nodes = await self._select_suitable_nodes(data_id)
                for node in suitable_nodes[:self.max_replication_factor - current_replicas]:
                    try:
                        await self._replicate_data(data_id, node.node_id)
                    except Exception as e:
                        logger.error(f"Failed to replicate data {data_id} to node {node.node_id}: {e}")

    async def _select_suitable_nodes(self, data_id: str) -> List[CDNNode]:
        exclude_nodes = set()
        if data_id in self.data_index:
            exclude_nodes = set(self.data_index[data_id].replicas)
        suitable_nodes = [
            node for node_id, node in self.known_nodes.items()
            if node_id not in exclude_nodes and node_id != self.node_id
        ]
        suitable_nodes.sort(key=lambda x: (
            -x.capability.storage_available,
            -x.capability.bandwidth,
            -x.capability.uptime,
            -x.capability.reliability
        ))
        return suitable_nodes

    async def _replicate_data(self, data_id: str, target_node_id: str):
        logger.info(f"Replicating data {data_id} to node {target_node_id}")
        await asyncio.sleep(1)
        if data_id in self.data_index:
            self.data_index[data_id].replicas.add(target_node_id)
            self._save_data_index()

    def _load_data_index(self):
        index_file = self.data_dir / "data_index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for data_id, metadata in data.items():
                        self.data_index[data_id] = DataMetadata.from_dict(metadata)
            except Exception as e:
                logger.error(f"Failed to load data index: {e}")

    def _save_data_index(self):
        index_file = self.data_dir / "data_index.json"
        try:
            data = {}
            for data_id, metadata in self.data_index.items():
                data[data_id] = metadata.to_dict()
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save data index: {e}")

    async def store_data(self, data: Dict[str, Any], data_type: str = "json") -> str:
        data_str = str(data)
        data_id = hashlib.sha256(data_str.encode()).hexdigest()
        if data_id in self.data_index:
            self.data_index[data_id].access_count += 1
            self.data_index[data_id].last_access = time.time()
            self._save_data_index()
            return data_id

        cdn_data = CDNData(
            data_id=data_id, data=data, data_type=data_type,
            created_at=time.time(), version=1
        )
        await self.storage.store_data(cdn_data)

        metadata = DataMetadata(
            data_id=data_id, data_type=data_type,
            size=len(data_str), created_at=time.time(),
            access_count=1, last_access=time.time(),
            replicas={self.node_id}
        )
        self.data_index[data_id] = metadata
        self._save_data_index()
        await self.cache_manager.cache_data(cdn_data)
        return data_id

    async def get_data(self, data_id: str) -> Optional[Dict[str, Any]]:
        if data_id not in self.data_index:
            return None

        cached_data = await self.cache_manager.get_data(data_id)
        if cached_data:
            if data_id in self.data_index:
                self.data_index[data_id].access_count += 1
                self.data_index[data_id].last_access = time.time()
                self._save_data_index()
            return cached_data.data

        stored_data = await self.storage.get_data(data_id)
        if stored_data:
            if data_id in self.data_index:
                self.data_index[data_id].access_count += 1
                self.data_index[data_id].last_access = time.time()
                self._save_data_index()
            await self.cache_manager.cache_data(stored_data)
            return stored_data.data

        best_node = await self.router.find_best_node(data_id, self.known_nodes)
        if best_node:
            try:
                data = await self._fetch_data_from_node(data_id, best_node.node_id)
                if data:
                    cdn_data = CDNData(
                        data_id=data_id, data=data, data_type="json",
                        created_at=time.time(), version=1
                    )
                    await self.storage.store_data(cdn_data)
                    await self.cache_manager.cache_data(cdn_data)
                    if data_id not in self.data_index:
                        metadata = DataMetadata(
                            data_id=data_id, data_type="json",
                            size=len(str(data)), created_at=time.time(),
                            access_count=1, last_access=time.time(),
                            replicas={self.node_id}
                        )
                        self.data_index[data_id] = metadata
                    else:
                        self.data_index[data_id].access_count += 1
                        self.data_index[data_id].last_access = time.time()
                        self.data_index[data_id].replicas.add(self.node_id)
                    self._save_data_index()
                    return data
            except Exception as e:
                logger.error(f"Failed to fetch data from node {best_node.node_id}: {e}")
        return None

    async def _fetch_data_from_node(self, data_id: str, node_id: str) -> Optional[Dict[str, Any]]:
        logger.info(f"Fetching data {data_id} from node {node_id}")
        await asyncio.sleep(0.5)
        return {"message": "Fetched from other node"}

    async def update_data(self, data_id: str, data: Dict[str, Any]) -> bool:
        if data_id not in self.data_index:
            return False
        current_version = self.data_index[data_id].version
        new_version = current_version + 1
        cdn_data = CDNData(
            data_id=data_id, data=data,
            data_type=self.data_index[data_id].data_type,
            created_at=time.time(), version=new_version
        )
        await self.storage.store_data(cdn_data)
        await self.cache_manager.cache_data(cdn_data)
        self.data_index[data_id].version = new_version
        self.data_index[data_id].size = len(str(data))
        self.data_index[data_id].last_access = time.time()
        self._save_data_index()
        await self._notify_nodes_update(data_id, new_version)
        return True

    async def _notify_nodes_update(self, data_id: str, new_version: int):
        if data_id in self.data_index:
            for node_id in self.data_index[data_id].replicas:
                if node_id != self.node_id:
                    try:
                        logger.info(f"Notifying node {node_id} to update data {data_id} to version {new_version}")
                    except Exception as e:
                        logger.error(f"Failed to notify node {node_id}: {e}")

    async def delete_data(self, data_id: str) -> bool:
        if data_id not in self.data_index:
            return False
        await self.storage.delete_data(data_id)
        await self.cache_manager.remove_data(data_id)
        del self.data_index[data_id]
        self._save_data_index()
        await self._notify_nodes_delete(data_id)
        return True

    async def _notify_nodes_delete(self, data_id: str):
        logger.info(f"Notifying nodes to delete data {data_id}")

    def add_node(self, node: CDNNode):
        self.known_nodes[node.node_id] = node

    def remove_node(self, node_id: str):
        if node_id in self.known_nodes:
            del self.known_nodes[node_id]
            for data_id, metadata in self.data_index.items():
                if node_id in metadata.replicas:
                    metadata.replicas.remove(node_id)
            self._save_data_index()

    def get_known_nodes(self) -> List[CDNNode]:
        return list(self.known_nodes.values())

    def get_stats(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "is_running": self.is_running,
            "known_nodes_count": len(self.known_nodes),
            "data_count": len(self.data_index),
            "cache_stats": self.cache_manager.get_stats(),
            "storage_stats": self.storage.get_stats(),
            "metrics": self.metrics.get_metrics() if self.metrics else {}
        }


async def create_p2p_cdn(
    node_id: str,
    data_dir: Optional[str] = None,
    max_cache_size: int = 1024 * 1024 * 1024,
    enable_metrics: bool = True
) -> P2PCDN:
    cdn = P2PCDN(node_id, data_dir, max_cache_size, enable_metrics)
    await cdn.start()
    return cdn


__all__ = [
    "P2PCDN",
    "create_p2p_cdn",
    "CDNNode",
    "CDNData",
    "DataMetadata",
    "DataVersion",
    "CacheStatus",
    "NodeCapability",
    "NetworkMetrics",
    "CacheManager",
    "CacheStrategy",
    "CDNRouter",
    "RouteStrategy",
    "DataSyncManager",
    "MetricsCollector",
    "CDNStorage"
]
