# -*- coding: utf-8 -*-
"""
去中心化知识区块链系统 - 分布式存储

实现:
- DHT网络: 知识定位、冗余存储、动态调整
- 存储策略: 全量/分片/缓存/归档存储
- 检索优化: 本地缓存、预测预取、并行检索
"""

import asyncio
import logging
import json
import os
import shutil
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import random

logger = logging.getLogger(__name__)


class StorageType(Enum):
    """存储类型"""
    FULL = "full"        # 全量存储
    SHARD = "shard"      # 分片存储
    CACHE = "cache"      # 缓存存储
    ARCHIVE = "archive"  # 归档存储


class NodeStatus(Enum):
    """节点状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    SYNCING = "syncing"
    DEGRADED = "degraded"


@dataclass
class StorageNode:
    """存储节点"""
    node_id: str
    address: str
    port: int
    status: NodeStatus
    storage_type: StorageType
    capacity: int  # 字节
    used_space: int  # 字节
    last_seen: datetime
    
    @property
    def available_space(self) -> int:
        return max(0, self.capacity - self.used_space)
    
    @property
    def usage_ratio(self) -> float:
        return self.used_space / self.capacity if self.capacity > 0 else 0


@dataclass
class ShardInfo:
    """分片信息"""
    shard_id: str
    data_hash: str
    nodes: List[str]  # 存储此分片的节点ID列表
    size: int
    created_at: datetime
    replica_count: int = 3


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: datetime
    access_count: int = 0
    last_access: datetime
    size: int
    priority: float = 0.0


@dataclass
class StorageStats:
    """存储统计"""
    total_capacity: int = 0
    used_space: int = 0
    cache_size: int = 0
    shard_count: int = 0
    network_nodes: int = 0
    hit_rate: float = 0.0
    write_count: int = 0
    read_count: int = 0


class DistributedStorage:
    """分布式存储"""

    def __init__(
        self,
        node_id: str,
        storage_path: str = "./data/storage",
        max_storage: int = 10 * 1024 * 1024 * 1024  # 10GB
    ):
        """
        初始化分布式存储
        
        Args:
            node_id: 节点ID
            storage_path: 存储路径
            max_storage: 最大存储空间
        """
        self.node_id = node_id
        self.storage_path = storage_path
        self.max_storage = max_storage
        
        # 本地存储
        self.local_storage: Dict[str, Any] = {}
        self.local_files: Dict[str, str] = {}  # key -> file_path
        
        # 缓存
        self.cache: Dict[str, CacheEntry] = {}
        self.cache_max_size = 100 * 1024 * 1024  # 100MB
        self.cache_current_size = 0
        self.cache_hits = 0
        self.cache_misses = 0
        
        # 分片管理
        self.shards: Dict[str, ShardInfo] = {}
        self.key_to_shards: Dict[str, List[str]] = {}  # key -> shard_ids
        
        # 网络节点
        self.network_nodes: Dict[str, StorageNode] = {}
        
        # DHT路由表
        self.routing_table: Dict[str, List[str]] = defaultdict(list)
        
        # 统计
        self.stats = StorageStats()
        
        # 创建存储目录
        os.makedirs(storage_path, exist_ok=True)
        os.makedirs(f"{storage_path}/blocks", exist_ok=True)
        os.makedirs(f"{storage_path}/knowledge", exist_ok=True)
        os.makedirs(f"{storage_path}/cache", exist_ok=True)
        
        logger.info(f"分布式存储初始化: {node_id}")

    async def start(self):
        """启动存储"""
        # 加载本地数据
        await self._load_local_data()
        
        # 启动缓存清理任务
        asyncio.create_task(self._cache_cleanup_loop())
        
        # 启动节点发现任务
        asyncio.create_task(self._node_discovery_loop())
        
        logger.info("✅ 分布式存储启动")
        return True

    async def stop(self):
        """停止存储"""
        # 保存本地数据
        await self._save_local_data()
        
        # 清理缓存
        self.cache.clear()
        
        logger.info("分布式存储已停止")

    # ==================== 基础存储操作 ====================

    async def put(self, key: str, value: Any) -> bool:
        """
        存储数据
        
        Args:
            key: 键
            value: 值
            
        Returns:
            是否成功
        """
        try:
            # 序列化值
            if isinstance(value, str):
                data = value.encode('utf-8')
            else:
                data = json.dumps(value, ensure_ascii=False).encode('utf-8')
            
            data_size = len(data)
            
            # 检查存储空间
            if self.stats.used_space + data_size > self.max_storage:
                await self._cleanup_storage(data_size)
            
            # 存储到本地
            file_path = f"{self.storage_path}/{key[:2]}/{key}"
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'wb') as f:
                f.write(data)
            
            self.local_files[key] = file_path
            self.stats.used_space += data_size
            self.stats.write_count += 1
            
            # 添加到缓存
            await self._add_to_cache(key, value, data_size)
            
            # 复制到网络节点
            await self._replicate_to_network(key, value, data_size)
            
            logger.debug(f"存储: {key} ({data_size} bytes)")
            
            return True
            
        except Exception as e:
            logger.error(f"存储失败: {e}")
            return False

    async def get(self, key: str) -> Optional[Any]:
        """
        获取数据
        
        Args:
            key: 键
            
        Returns:
            值
        """
        # 先检查缓存
        cached = await self._get_from_cache(key)
        if cached is not None:
            return cached
        
        # 从本地获取
        file_path = self.local_files.get(key)
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'rb') as f:
                    data = f.read()
                
                self.stats.read_count += 1
                
                # 尝试解析为JSON
                try:
                    return json.loads(data.decode('utf-8'))
                except:
                    return data.decode('utf-8')
                    
            except Exception as e:
                logger.error(f"读取失败: {e}")
        
        # 从网络获取
        value = await self._fetch_from_network(key)
        if value is not None:
            # 添加到本地缓存
            data_size = len(json.dumps(value))
            await self._add_to_cache(key, value, data_size)
            return value
        
        return None

    async def delete(self, key: str) -> bool:
        """
        删除数据
        
        Args:
            key: 键
            
        Returns:
            是否成功
        """
        try:
            # 删除本地文件
            file_path = self.local_files.get(key)
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                del self.local_files[key]
            
            # 从缓存删除
            if key in self.cache:
                entry = self.cache[key]
                self.cache_current_size -= entry.size
                del self.cache[key]
            
            # 从网络删除
            await self._delete_from_network(key)
            
            logger.debug(f"删除: {key}")
            
            return True
            
        except Exception as e:
            logger.error(f"删除失败: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if key in self.local_files:
            return True
        if key in self.cache:
            return True
        return False

    # ==================== DHT 操作 ====================

    def _generate_dht_key(self, data: Any) -> str:
        """生成DHT键"""
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    async def _find_nodes(self, key: str, count: int = 3) -> List[StorageNode]:
        """找到负责存储给定键的节点"""
        # 简化实现：返回本地和随机网络节点
        nodes = []
        
        # 本地节点
        local_node = StorageNode(
            node_id=self.node_id,
            address="localhost",
            port=0,
            status=NodeStatus.ONLINE,
            storage_type=StorageType.FULL,
            capacity=self.max_storage,
            used_space=self.stats.used_space,
            last_seen=datetime.now()
        )
        nodes.append(local_node)
        
        # 随机选择网络节点
        network_node_list = [
            n for n in self.network_nodes.values()
            if n.status == NodeStatus.ONLINE
        ]
        
        random.shuffle(network_node_list)
        nodes.extend(network_node_list[:count-1])
        
        return nodes

    async def _replicate_to_network(
        self,
        key: str,
        value: Any,
        size: int
    ):
        """复制数据到网络节点"""
        nodes = await self._find_nodes(key, 3)
        
        for node in nodes:
            if node.node_id != self.node_id:
                # 模拟网络复制
                asyncio.create_task(self._send_to_node(node, key, value))

    async def _fetch_from_network(self, key: str) -> Optional[Any]:
        """从网络获取数据"""
        nodes = await self._find_nodes(key, 3)
        
        for node in nodes:
            if node.node_id != self.node_id:
                value = await self._receive_from_node(node, key)
                if value is not None:
                    return value
        
        return None

    async def _delete_from_network(self, key: str):
        """从网络删除数据"""
        nodes = await self._find_nodes(key, 3)
        
        for node in nodes:
            if node.node_id != self.node_id:
                asyncio.create_task(self._delete_on_node(node, key))

    # ==================== 分片操作 ====================

    async def put_sharded(
        self,
        key: str,
        value: Any,
        shard_count: int = 3
    ) -> bool:
        """
        分片存储
        
        Args:
            key: 键
            value: 值
            shard_count: 分片数量
            
        Returns:
            是否成功
        """
        # 序列化
        data = json.dumps(value, ensure_ascii=False)
        data_bytes = data.encode('utf-8')
        
        # 计算分片大小
        shard_size = (len(data_bytes) + shard_count - 1) // shard_count
        
        # 创建分片
        shards = []
        for i in range(shard_count):
            start = i * shard_size
            end = min(start + shard_size, len(data_bytes))
            shard_data = data_bytes[start:end]
            
            shard_id = self._generate_shard_id(key, i)
            
            shard_info = ShardInfo(
                shard_id=shard_id,
                data_hash=hashlib.sha256(shard_data).hexdigest(),
                nodes=[],
                size=len(shard_data),
                created_at=datetime.now()
            )
            
            # 存储分片
            await self.put(shard_id, shard_data)
            
            # 分配节点
            nodes = await self._find_nodes(shard_id, shard_info.replica_count)
            shard_info.nodes = [n.node_id for n in nodes]
            
            shards.append(shard_info)
        
        # 保存分片信息
        self.shards[key] = shards
        self.key_to_shards[key] = [s.shard_id for s in shards]
        self.stats.shard_count += shard_count
        
        return True

    async def get_sharded(self, key: str) -> Optional[Any]:
        """获取分片数据"""
        shard_ids = self.key_to_shards.get(key)
        if not shard_ids:
            return None
        
        # 收集所有分片
        shard_data_list = []
        for shard_id in shard_ids:
            data = await self.get(shard_id)
            if data is None:
                return None
            shard_data_list.append(data)
        
        # 合并分片
        combined = b''.join(shard_data_list)
        return json.loads(combined.decode('utf-8'))

    def _generate_shard_id(self, key: str, index: int) -> str:
        """生成分片ID"""
        data = f"{key}_shard_{index}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    # ==================== 缓存管理 ====================

    async def _add_to_cache(
        self,
        key: str,
        value: Any,
        size: int
    ):
        """添加到缓存"""
        # 清理空间
        while self.cache_current_size + size > self.cache_max_size:
            await self._evict_cache_entry()
        
        # 计算优先级
        priority = self._calculate_cache_priority(key, value)
        
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.now(),
            access_count=1,
            last_access=datetime.now(),
            size=size,
            priority=priority
        )
        
        self.cache[key] = entry
        self.cache_current_size += size

    async def _get_from_cache(self, key: str) -> Optional[Any]:
        """从缓存获取"""
        if key in self.cache:
            entry = self.cache[key]
            entry.access_count += 1
            entry.last_access = datetime.now()
            
            # 更新优先级
            entry.priority = self._calculate_cache_priority(key, entry.value)
            
            self.cache_hits += 1
            return entry.value
        
        self.cache_misses += 1
        return None

    async def _evict_cache_entry(self):
        """驱逐缓存条目"""
        if not self.cache:
            return
        
        # 选择优先级最低的
        min_priority = min(e.priority for e in self.cache.values())
        
        for key, entry in list(self.cache.items()):
            if entry.priority == min_priority:
                del self.cache[key]
                self.cache_current_size -= entry.size
                break

    def _calculate_cache_priority(self, key: str, value: Any) -> float:
        """计算缓存优先级"""
        priority = 1.0
        
        # 基于访问频率
        if key in self.cache:
            priority *= (1 + self.cache[key].access_count * 0.1)
        
        # 基于数据大小（小数据优先）
        data_size = len(json.dumps(value))
        priority *= (1 - data_size / self.cache_max_size * 0.5)
        
        # 基于时间（新建优先）
        if key in self.cache:
            age = (datetime.now() - self.cache[key].created_at).total_seconds()
            priority *= (1 + age / 86400 * 0.01)  # 每天增加1%
        
        return priority

    async def _cache_cleanup_loop(self):
        """缓存清理循环"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟
                
                # 清理过期条目
                cutoff = datetime.now() - timedelta(hours=1)
                for key, entry in list(self.cache.items()):
                    if entry.last_access < cutoff:
                        del self.cache[key]
                        self.cache_current_size -= entry.size
                        
            except Exception as e:
                logger.error(f"缓存清理错误: {e}")

    # ==================== 网络节点 ====================

    async def register_node(self, node: StorageNode):
        """注册网络节点"""
        self.network_nodes[node.node_id] = node
        self.stats.network_nodes = len(self.network_nodes)
        logger.info(f"节点注册: {node.node_id}")

    async def unregister_node(self, node_id: str):
        """注销网络节点"""
        if node_id in self.network_nodes:
            del self.network_nodes[node_id]
            self.stats.network_nodes = len(self.network_nodes)
            logger.info(f"节点注销: {node_id}")

    async def _send_to_node(
        self,
        node: StorageNode,
        key: str,
        value: Any
    ):
        """发送数据到节点（模拟）"""
        # 简化实现
        pass

    async def _receive_from_node(
        self,
        node: StorageNode,
        key: str
    ) -> Optional[Any]:
        """从节点接收数据（模拟）"""
        # 简化实现
        return None

    async def _delete_on_node(self, node: StorageNode, key: str):
        """在节点上删除数据（模拟）"""
        pass

    async def _node_discovery_loop(self):
        """节点发现循环"""
        while True:
            try:
                await asyncio.sleep(30)  # 每30秒
                
                # 更新节点状态
                for node in self.network_nodes.values():
                    time_since_seen = (datetime.now() - node.last_seen).total_seconds()
                    
                    if time_since_seen > 300:  # 5分钟
                        node.status = NodeStatus.OFFLINE
                    elif time_since_seen > 60:
                        node.status = NodeStatus.DEGRADED
                        
            except Exception as e:
                logger.error(f"节点发现错误: {e}")

    # ==================== 存储清理 ====================

    async def _cleanup_storage(self, needed_space: int):
        """清理存储空间"""
        # 归档旧数据
        await self._archive_old_data()
        
        # 删除缓存
        if self.cache_current_size > 0:
            target_size = self.cache_max_size // 2
            while self.cache_current_size > target_size:
                await self._evict_cache_entry()

    async def _archive_old_data(self):
        """归档旧数据"""
        # 简化实现：删除最旧的文件
        if not self.local_files:
            return
        
        oldest_key = None
        oldest_mtime = datetime.now()
        
        for key, path in self.local_files.items():
            if os.path.exists(path):
                mtime = datetime.fromtimestamp(os.path.getmtime(path))
                if mtime < oldest_mtime:
                    oldest_mtime = mtime
                    oldest_key = key
        
        if oldest_key:
            await self.delete(oldest_key)

    # ==================== 本地数据管理 ====================

    async def _load_local_data(self):
        """加载本地数据"""
        try:
            # 扫描存储目录
            for root, dirs, files in os.walk(self.storage_path):
                for f in files:
                    file_path = os.path.join(root, f)
                    rel_path = os.path.relpath(file_path, self.storage_path)
                    
                    with open(file_path, 'rb') as fp:
                        data = fp.read()
                    
                    self.local_files[rel_path] = file_path
                    self.stats.used_space += len(data)
                    
            logger.info(f"加载本地数据: {len(self.local_files)} 个文件")
            
        except Exception as e:
            logger.error(f"加载本地数据失败: {e}")

    async def _save_local_data(self):
        """保存本地数据"""
        # 简化实现
        pass

    # ==================== 统计 ====================

    def get_stats(self) -> StorageStats:
        """获取存储统计"""
        self.stats.total_capacity = self.max_storage
        self.stats.used_space = self.stats.used_space
        self.stats.cache_size = self.cache_current_size
        
        total = self.cache_hits + self.cache_misses
        self.stats.hit_rate = self.cache_hits / total if total > 0 else 0.0
        
        return self.stats
