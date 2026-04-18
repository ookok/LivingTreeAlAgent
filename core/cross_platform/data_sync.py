"""
Data Sync - 三端数据同步
=====================

统一数据同步机制:
- LocalStorage (本地SQLite)
- CloudStorage (可选云同步)
- P2PStorage (P2P网络同步)
"""

import asyncio
import json
import time
import hashlib
import copy
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import threading


class SyncSource(Enum):
    """同步来源"""
    LOCAL = "local"
    CLOUD = "cloud"
    P2P = "p2p"
    WEB = "web"


class ConflictStrategy(Enum):
    """冲突解决策略"""
    LOCAL_WINS = "local_wins"      # 本地优先
    CLOUD_WINS = "cloud_wins"       # 云端优先
    LATEST_WINS = "latest_wins"     # 最新优先
    MANUAL = "manual"               # 手动解决


@dataclass
class DataSnapshot:
    """数据快照"""
    key: str
    value: Any
    version: int = 1
    timestamp: float = field(default_factory=time.time)
    source: SyncSource = SyncSource.LOCAL
    checksum: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.checksum:
            self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        """计算校验和"""
        content = f"{self.key}:{json.dumps(self.value, sort_keys=True)}:{self.version}"
        return hashlib.md5(content.encode()).hexdigest()[:8]

    def is_valid(self) -> bool:
        """验证数据完整性"""
        return self.checksum == self._calculate_checksum()


@dataclass
class SyncEvent:
    """同步事件"""
    event_type: str  # created/updated/deleted/synced
    key: str
    snapshot: Optional[DataSnapshot] = None
    timestamp: float = field(default_factory=time.time)
    source: SyncSource = SyncSource.LOCAL


class ConflictResolver:
    """
    冲突解决器

    支持多种冲突解决策略
    """

    def __init__(self, strategy: ConflictStrategy = ConflictStrategy.LATEST_WINS):
        self.strategy = strategy
        self._manual_conflicts: Dict[str, Any] = {}

    def resolve(self, local: DataSnapshot, remote: DataSnapshot) -> DataSnapshot:
        """
        解决冲突

        Args:
            local: 本地数据
            remote: 远程数据

        Returns:
            解决后的数据快照
        """
        # 检查手动解决
        if self.strategy == ConflictStrategy.MANUAL:
            if local.key in self._manual_conflicts:
                return self._manual_conflicts[local.key]

        if self.strategy == ConflictStrategy.LOCAL_WINS:
            return local

        if self.strategy == ConflictStrategy.CLOUD_WINS:
            return remote

        # LATEST_WINS
        if local.timestamp >= remote.timestamp:
            return local
        return remote

    def set_manual_resolution(self, key: str, snapshot: DataSnapshot):
        """设置手动解决结果"""
        self._manual_conflicts[key] = snapshot


class LocalStorage:
    """
    本地存储

    基于SQLite的本地数据存储
    """

    def __init__(self, db_path: str = "data/sync_local.db"):
        self.db_path = db_path
        self._data: Dict[str, DataSnapshot] = {}
        self._lock = threading.Lock()
        self._init_storage()

    def _init_storage(self):
        """初始化存储"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # 简化实现：使用内存存储，生产环境应用SQLite
        self._load_from_disk()

    def _load_from_disk(self):
        """从磁盘加载"""
        import os
        disk_path = self.db_path.replace('.db', '.json')
        if os.path.exists(disk_path):
            try:
                with open(disk_path, 'r') as f:
                    data = json.load(f)
                    for key, item in data.items():
                        self._data[key] = DataSnapshot(**item)
            except Exception as e:
                print(f"[LocalStorage] Load error: {e}")

    def _save_to_disk(self):
        """保存到磁盘"""
        import os
        disk_path = self.db_path.replace('.db', '.json')
        os.makedirs(os.path.dirname(disk_path), exist_ok=True)
        try:
            with open(disk_path, 'w') as f:
                data = {k: asdict(v) for k, v in self._data.items()}
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[LocalStorage] Save error: {e}")

    def get(self, key: str) -> Optional[DataSnapshot]:
        """获取数据"""
        with self._lock:
            return self._data.get(key)

    def set(self, key: str, value: Any, metadata: Dict[str, Any] = None) -> DataSnapshot:
        """设置数据"""
        with self._lock:
            existing = self._data.get(key)
            version = existing.version + 1 if existing else 1

            snapshot = DataSnapshot(
                key=key,
                value=value,
                version=version,
                timestamp=time.time(),
                source=SyncSource.LOCAL,
                metadata=metadata or {}
            )

            self._data[key] = snapshot
            self._save_to_disk()
            return snapshot

    def delete(self, key: str) -> bool:
        """删除数据"""
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._save_to_disk()
                return True
            return False

    def get_all(self) -> Dict[str, DataSnapshot]:
        """获取所有数据"""
        with self._lock:
            return copy.deepcopy(self._data)

    def keys(self) -> List[str]:
        """获取所有键"""
        with self._lock:
            return list(self._data.keys())


class P2PStorage:
    """
    P2P存储

    通过P2P网络同步数据
    """

    def __init__(self, peer_id: str, relay_server: str = None):
        self.peer_id = peer_id
        self.relay_server = relay_server
        self._connected_peers: Set[str] = set()
        self._pending_syncs: List[SyncEvent] = []
        self._lock = asyncio.Lock()

    async def connect(self):
        """连接到P2P网络"""
        if self.relay_server:
            # 连接中继服务器
            pass

    async def broadcast(self, event: SyncEvent):
        """广播同步事件"""
        async with self._lock:
            self._pending_syncs.append(event)

        # 通过relay_chain广播到网络
        # 实现略

    async def receive(self) -> Optional[SyncEvent]:
        """接收同步事件"""
        async with self._lock:
            if self._pending_syncs:
                return self._pending_syncs.pop(0)
        return None

    def add_peer(self, peer_id: str):
        """添加对等节点"""
        self._connected_peers.add(peer_id)

    def remove_peer(self, peer_id: str):
        """移除对等节点"""
        self._connected_peers.discard(peer_id)

    @property
    def peers(self) -> Set[str]:
        """获取连接的对等节点"""
        return self._connected_peers.copy()


class SyncManager:
    """
    同步管理器

    统一管理三端数据同步
    """

    def __init__(
        self,
        local_storage: LocalStorage = None,
        cloud_storage: Any = None,
        p2p_storage: P2PStorage = None,
        conflict_strategy: ConflictStrategy = ConflictStrategy.LATEST_WINS
    ):
        self.local = local_storage or LocalStorage()
        self.cloud = cloud_storage
        self.p2p = p2p_storage
        self.conflict_resolver = ConflictResolver(conflict_strategy)

        self._sync_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._listeners: List[Callable] = []

    async def start(self):
        """启动同步"""
        self._running = True
        asyncio.create_task(self._sync_loop())

        if self.p2p:
            await self.p2p.connect()

    async def stop(self):
        """停止同步"""
        self._running = False

    async def _sync_loop(self):
        """同步循环"""
        while self._running:
            try:
                # 处理同步队列
                await self._process_sync_queue()

                # 从P2P接收
                if self.p2p:
                    event = await self.p2p.receive()
                    if event:
                        await self._handle_sync_event(event)

                # 等待下次同步
                await asyncio.sleep(5)  # 5秒同步一次

            except Exception as e:
                print(f"[SyncManager] Sync loop error: {e}")

    async def _process_sync_queue(self):
        """处理同步队列"""
        while not self._sync_queue.empty():
            event = await self._sync_queue.get()
            await self._handle_sync_event(event)

    async def _handle_sync_event(self, event: SyncEvent):
        """处理同步事件"""
        if event.event_type in ('created', 'updated'):
            snapshot = event.snapshot

            # 检查本地冲突
            local = self.local.get(snapshot.key)
            if local and local.version >= snapshot.version:
                # 存在冲突，解决
                snapshot = self.conflict_resolver.resolve(local, snapshot)

            # 更新本地
            self.local.set(snapshot.key, snapshot.value, snapshot.metadata)

            # 广播到P2P
            if self.p2p:
                await self.p2p.broadcast(event)

        elif event.event_type == 'deleted':
            self.local.delete(event.key)

            # 广播到P2P
            if self.p2p:
                await self.p2p.broadcast(event)

        # 通知监听器
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                print(f"[SyncManager] Listener error: {e}")

    async def set(self, key: str, value: Any, metadata: Dict[str, Any] = None):
        """设置数据并触发同步"""
        snapshot = self.local.set(key, value, metadata)

        await self._sync_queue.put(SyncEvent(
            event_type='updated',
            key=key,
            snapshot=snapshot,
            source=SyncSource.LOCAL
        ))

    async def get(self, key: str) -> Optional[Any]:
        """获取数据"""
        snapshot = self.local.get(key)
        return snapshot.value if snapshot else None

    async def delete(self, key: str):
        """删除数据"""
        self.local.delete(key)

        await self._sync_queue.put(SyncEvent(
            event_type='deleted',
            key=key,
            source=SyncSource.LOCAL
        ))

    def add_listener(self, listener: Callable):
        """添加同步监听器"""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable):
        """移除同步监听器"""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def create_snapshot(self) -> Dict[str, DataSnapshot]:
        """创建数据快照"""
        return self.local.get_all()


class UniversalDataSync:
    """
    统一数据同步入口

    提供简洁的API
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._manager = SyncManager()

    async def start(self):
        """启动同步"""
        await self._manager.start()

    async def stop(self):
        """停止同步"""
        await self._manager.stop()

    async def sync(self, key: str, value: Any):
        """同步数据"""
        await self._manager.set(key, value)

    async def get(self, key: str) -> Optional[Any]:
        """获取数据"""
        return await self._manager.get(key)

    async def remove(self, key: str):
        """删除数据"""
        await self._manager.delete(key)

    @property
    def manager(self) -> SyncManager:
        """获取同步管理器"""
        return self._manager


# 全局实例
_global_sync: Optional[UniversalDataSync] = None


def get_sync_manager() -> UniversalDataSync:
    """获取全局同步管理器"""
    global _global_sync
    if _global_sync is None:
        _global_sync = UniversalDataSync()
    return _global_sync