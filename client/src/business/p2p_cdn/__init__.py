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
import logging
import time
import hashlib
from typing import Optional, Dict, List, Any, Set, Tuple
from pathlib import Path

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
    """
    P2P CDN 核心类
    管理分布式缓存、智能路由和数据同步
    """
    
    def __init__(
        self,
        node_id: str,
        data_dir: Optional[str] = None,
        max_cache_size: int = 1024 * 1024 * 1024,  # 1GB
        enable_metrics: bool = True
    ):
        self.node_id = node_id
        self.data_dir = Path(data_dir or f"~/.p2p_cdn/{self.node_id}").expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 核心组件
        self.storage = CDNStorage(str(self.data_dir / "storage"))
        self.cache_manager = CacheManager(
            storage=self.storage,
            max_cache_size=max_cache_size
        )
        self.router = CDNRouter()
        self.data_sync = DataSyncManager(self.node_id)
        self.metrics = MetricsCollector() if enable_metrics else None
        
        # 状态
        self.is_running = False
        self.known_nodes: Dict[str, CDNNode] = {}
        self.data_index: Dict[str, DataMetadata] = {}
        
        # 配置
        self.max_replication_factor = 3  # 最大副本数
        self.hot_data_threshold = 5  # 热门数据阈值（访问次数）
        self.heartbeat_interval = 30  # 心跳间隔（秒）
        
        # 任务
        self._heartbeat_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动 P2P CDN"""
        logger.info(f"Starting P2P CDN node {self.node_id}...")
        
        # 初始化存储
        await self.storage.init()
        
        # 初始化缓存
        await self.cache_manager.init()
        
        # 加载数据索引
        self._load_data_index()
        
        # 初始化本地节点状态
        await self._update_node_status()
        
        # 启动心跳任务
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        self.is_running = True
        logger.info(f"P2P CDN node {self.node_id} started successfully")
    
    async def stop(self):
        """停止 P2P CDN"""
        logger.info(f"Stopping P2P CDN node {self.node_id}...")
        
        self.is_running = False
        
        # 停止心跳任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # 保存数据索引
        self._save_data_index()
        
        # 关闭存储
        await self.storage.close()
        
        logger.info(f"P2P CDN node {self.node_id} stopped")
    
    async def _heartbeat_loop(self):
        """心跳循环，定期更新节点状态"""
        while self.is_running:
            try:
                # 更新本地节点状态
                await self._update_node_status()
                
                # 清理过期数据
                await self.cache_manager.cleanup_expired()
                
                # 复制热门数据
                await self._replicate_hot_data()
                
                await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(self.heartbeat_interval)
    
    async def _update_node_status(self):
        """更新本地节点状态"""
        # 计算节点能力
        capability = await self._calculate_capability()
        
        # 更新本地节点信息
        local_node = CDNNode(
            node_id=self.node_id,
            capability=capability,
            last_seen=time.time(),
            cache_stats=self.cache_manager.get_stats()
        )
        
        self.known_nodes[self.node_id] = local_node
    
    async def _calculate_capability(self) -> NodeCapability:
        """计算节点能力"""
        # 这里可以根据实际情况计算节点能力
        # 包括存储容量、带宽、CPU 使用率等
        return NodeCapability(
            storage_available=self.storage.get_available_space(),
            bandwidth=100,  # 假设 100 Mbps
            uptime=3600,  # 假设 1 小时
            reliability=0.99  # 假设 99% 可靠性
        )
    
    async def _replicate_hot_data(self):
        """复制热门数据到其他节点"""
        # 获取热门数据
        hot_data = await self.cache_manager.get_hot_data(self.hot_data_threshold)
        
        for data_id, metadata in hot_data.items():
            # 检查当前副本数
            current_replicas = len(metadata.replicas)
            
            if current_replicas < self.max_replication_factor:
                # 选择合适的节点进行复制
                suitable_nodes = await self._select_suitable_nodes(data_id)
                
                for node in suitable_nodes[:self.max_replication_factor - current_replicas]:
                    try:
                        # 复制数据到目标节点
                        await self._replicate_data(data_id, node.node_id)
                    except Exception as e:
                        logger.error(f"Failed to replicate data {data_id} to node {node.node_id}: {e}")
    
    async def _select_suitable_nodes(self, data_id: str) -> List[CDNNode]:
        """选择合适的节点进行数据复制"""
        # 排除已存储该数据的节点
        exclude_nodes = set()
        if data_id in self.data_index:
            exclude_nodes = set(self.data_index[data_id].replicas)
        
        # 按节点能力排序
        suitable_nodes = [
            node for node_id, node in self.known_nodes.items()
            if node_id not in exclude_nodes and node_id != self.node_id
        ]
        
        # 按节点能力和网络延迟排序
        suitable_nodes.sort(key=lambda x: (
            -x.capability.storage_available,  # 优先选择存储容量大的
            -x.capability.bandwidth,  # 优先选择带宽大的
            -x.capability.uptime,  # 优先选择在线时间长的
            -x.capability.reliability  # 优先选择可靠性高的
        ))
        
        return suitable_nodes
    
    async def _replicate_data(self, data_id: str, target_node_id: str):
        """复制数据到目标节点"""
        # 这里需要实现与目标节点的通信
        # 实际项目中需要通过 P2P 网络发送数据
        logger.info(f"Replicating data {data_id} to node {target_node_id}")
        
        # 模拟复制过程
        await asyncio.sleep(1)
        
        # 更新数据索引
        if data_id in self.data_index:
            self.data_index[data_id].replicas.add(target_node_id)
            self._save_data_index()
    
    def _load_data_index(self):
        """加载数据索引"""
        index_file = self.data_dir / "data_index.json"
        if index_file.exists():
            try:
                import json
                with open(index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for data_id, metadata in data.items():
                        self.data_index[data_id] = DataMetadata.from_dict(metadata)
            except Exception as e:
                logger.error(f"Failed to load data index: {e}")
    
    def _save_data_index(self):
        """保存数据索引"""
        index_file = self.data_dir / "data_index.json"
        try:
            import json
            data = {}
            for data_id, metadata in self.data_index.items():
                data[data_id] = metadata.to_dict()
            
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save data index: {e}")
    
    # ========== 数据操作 ==========
    
    async def store_data(self, data: Dict[str, Any], data_type: str = "json") -> str:
        """存储结构化数据"""
        # 生成数据 ID
        data_str = str(data)
        data_id = hashlib.sha256(data_str.encode()).hexdigest()
        
        # 检查数据是否已存在
        if data_id in self.data_index:
            # 更新访问次数
            self.data_index[data_id].access_count += 1
            self.data_index[data_id].last_access = time.time()
            self._save_data_index()
            return data_id
        
        # 存储数据
        cdn_data = CDNData(
            data_id=data_id,
            data=data,
            data_type=data_type,
            created_at=time.time(),
            version=1
        )
        
        await self.storage.store_data(cdn_data)
        
        # 创建元数据
        metadata = DataMetadata(
            data_id=data_id,
            data_type=data_type,
            size=len(data_str),
            created_at=time.time(),
            access_count=1,
            last_access=time.time(),
            replicas={self.node_id}
        )
        
        self.data_index[data_id] = metadata
        self._save_data_index()
        
        # 缓存数据
        await self.cache_manager.cache_data(cdn_data)
        
        return data_id
    
    async def get_data(self, data_id: str) -> Optional[Dict[str, Any]]:
        """获取结构化数据"""
        # 检查数据是否已被删除
        if data_id not in self.data_index:
            return None
        
        # 先从本地缓存获取
        cached_data = await self.cache_manager.get_data(data_id)
        if cached_data:
            # 更新访问次数
            if data_id in self.data_index:
                self.data_index[data_id].access_count += 1
                self.data_index[data_id].last_access = time.time()
                self._save_data_index()
            return cached_data.data
        
        # 从本地存储获取
        stored_data = await self.storage.get_data(data_id)
        if stored_data:
            # 更新访问次数
            if data_id in self.data_index:
                self.data_index[data_id].access_count += 1
                self.data_index[data_id].last_access = time.time()
                self._save_data_index()
            
            # 缓存数据
            await self.cache_manager.cache_data(stored_data)
            return stored_data.data
        
        # 从其他节点获取
        best_node = await self.router.find_best_node(data_id, self.known_nodes)
        if best_node:
            try:
                # 从最佳节点获取数据
                data = await self._fetch_data_from_node(data_id, best_node.node_id)
                if data:
                    # 存储并缓存数据
                    cdn_data = CDNData(
                        data_id=data_id,
                        data=data,
                        data_type="json",  # 假设是 JSON
                        created_at=time.time(),
                        version=1
                    )
                    
                    await self.storage.store_data(cdn_data)
                    await self.cache_manager.cache_data(cdn_data)
                    
                    # 更新数据索引
                    if data_id not in self.data_index:
                        metadata = DataMetadata(
                            data_id=data_id,
                            data_type="json",
                            size=len(str(data)),
                            created_at=time.time(),
                            access_count=1,
                            last_access=time.time(),
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
        """从其他节点获取数据"""
        # 这里需要实现与其他节点的通信
        # 实际项目中需要通过 P2P 网络获取数据
        logger.info(f"Fetching data {data_id} from node {node_id}")
        
        # 模拟获取过程
        await asyncio.sleep(0.5)
        
        # 模拟数据获取成功
        # 实际项目中需要通过网络请求获取数据
        return {"message": "Fetched from other node"}
    
    async def update_data(self, data_id: str, data: Dict[str, Any]) -> bool:
        """更新结构化数据"""
        if data_id not in self.data_index:
            return False
        
        # 生成新的版本
        current_version = self.data_index[data_id].version
        new_version = current_version + 1
        
        # 存储更新后的数据
        cdn_data = CDNData(
            data_id=data_id,
            data=data,
            data_type=self.data_index[data_id].data_type,
            created_at=time.time(),
            version=new_version
        )
        
        await self.storage.store_data(cdn_data)
        
        # 更新缓存
        await self.cache_manager.cache_data(cdn_data)
        
        # 更新元数据
        self.data_index[data_id].version = new_version
        self.data_index[data_id].size = len(str(data))
        self.data_index[data_id].last_access = time.time()
        self._save_data_index()
        
        # 通知其他节点更新数据
        await self._notify_nodes_update(data_id, new_version)
        
        return True
    
    async def _notify_nodes_update(self, data_id: str, new_version: int):
        """通知其他节点更新数据"""
        if data_id in self.data_index:
            for node_id in self.data_index[data_id].replicas:
                if node_id != self.node_id:
                    try:
                        # 这里需要实现与其他节点的通信
                        # 实际项目中需要通过 P2P 网络发送更新通知
                        logger.info(f"Notifying node {node_id} to update data {data_id} to version {new_version}")
                    except Exception as e:
                        logger.error(f"Failed to notify node {node_id}: {e}")
    
    async def delete_data(self, data_id: str) -> bool:
        """删除数据"""
        if data_id not in self.data_index:
            return False
        
        # 从存储中删除
        await self.storage.delete_data(data_id)
        
        # 从缓存中删除
        await self.cache_manager.remove_data(data_id)
        
        # 从索引中删除
        del self.data_index[data_id]
        self._save_data_index()
        
        # 通知其他节点删除数据
        await self._notify_nodes_delete(data_id)
        
        return True
    
    async def _notify_nodes_delete(self, data_id: str):
        """通知其他节点删除数据"""
        # 这里需要实现与其他节点的通信
        # 实际项目中需要通过 P2P 网络发送删除通知
        logger.info(f"Notifying nodes to delete data {data_id}")
    
    # ========== 节点管理 ==========
    
    def add_node(self, node: CDNNode):
        """添加节点"""
        self.known_nodes[node.node_id] = node
    
    def remove_node(self, node_id: str):
        """移除节点"""
        if node_id in self.known_nodes:
            del self.known_nodes[node_id]
            
            # 从数据副本中移除
            for data_id, metadata in self.data_index.items():
                if node_id in metadata.replicas:
                    metadata.replicas.remove(node_id)
            
            self._save_data_index()
    
    def get_known_nodes(self) -> List[CDNNode]:
        """获取已知节点列表"""
        return list(self.known_nodes.values())
    
    # ========== 统计信息 ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "node_id": self.node_id,
            "is_running": self.is_running,
            "known_nodes_count": len(self.known_nodes),
            "data_count": len(self.data_index),
            "cache_stats": self.cache_manager.get_stats(),
            "storage_stats": self.storage.get_stats(),
            "metrics": self.metrics.get_metrics() if self.metrics else {}
        }


# ========== 便捷函数 ==========

async def create_p2p_cdn(
    node_id: str,
    data_dir: Optional[str] = None,
    max_cache_size: int = 1024 * 1024 * 1024,
    enable_metrics: bool = True
) -> P2PCDN:
    """创建 P2P CDN 实例"""
    cdn = P2PCDN(node_id, data_dir, max_cache_size, enable_metrics)
    await cdn.start()
    return cdn


# ========== 模块导出 ==========

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
