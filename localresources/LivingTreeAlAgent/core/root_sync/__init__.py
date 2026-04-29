"""
Root Sync - 根系同步 🌳

基于 Syncthing BEP 协议的去中心化文件同步系统

特性：
- BEP 协议 (Block Exchange Protocol)
- 设备证书认证
- 增量块同步
- CRDT 冲突解决
- 多版本控制
- 选择性同步
- 中继穿透
- 优先级调度

Usage:
    from core.root_sync import RootSyncSystem, FolderConfig

    # 创建系统
    system = RootSyncSystem(storage_dir="~/.hermes/root_sync")

    # 添加同步文件夹
    config = FolderConfig(
        folder_id="documents",
        path="/path/to/folder",
        label="我的文档",
    )
    await system.add_folder(config)

    # 启动
    await system.start()
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable

from .models import (
    FileManifest, FileInfo, FolderConfig, DeviceInfo,
    ConflictStrategy, BEPChunk, FileType,
    SyncRequest, SyncResponse, DownloadProgress,
    MessageType,
)
from .version_store import VersioningType
from .bep_protocol import BEPProtocol, BEPConnection
from .chunk_manager import ChunkManager
from .folder_sync import FolderSync, SyncDelta
from .device_registry import DeviceRegistry, GlobalDiscovery
from .conflict_resolver import ConflictResolver, ConflictRecord, ConflictType
from .version_store import VersionStore
from .selective_sync import SelectiveSync, SyncFilter
from .relay_bridge import RelayBridge, RelayPool, RelaySession
from .sync_scheduler import SyncScheduler, SyncTask, TaskPriority, BandwidthLimiter
from .sync_engine import SyncEngine


logger = logging.getLogger(__name__)


class RootSyncSystem:
    """
    根系同步系统

    统一的同步系统入口，整合所有组件

    Example:
        system = RootSyncSystem(storage_dir="~/.hermes/root_sync")

        # 初始化设备
        device_id, cert, key = await system.initialize_device("MyDevice")

        # 添加文件夹
        config = FolderConfig(
            folder_id="backup",
            path="/data/backup",
            label="备份",
            versioning_enabled=True,
            versioning_type="staggered",
        )
        await system.add_folder(config)

        # 连接设备
        await system.connect_device("remote-device-id", ["192.168.1.100:22000"])

        # 启动
        await system.start()
    """

    def __init__(self, storage_dir: str):
        import os
        from pathlib import Path

        self.storage_dir = Path(storage_dir).expanduser()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 核心组件
        self._engine: Optional[SyncEngine] = None
        self._initialized = False

        # 配置
        self._device_id: Optional[str] = None
        self._device_name: str = ""

        # 回调
        self._callbacks: Dict[str, Callable] = {}

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def device_id(self) -> Optional[str]:
        return self._device_id

    @property
    def is_running(self) -> bool:
        return self._engine.is_running if self._engine else False

    async def initialize_device(self, device_name: str) -> tuple:
        """
        初始化设备

        Args:
            device_name: 设备名称

        Returns:
            (device_id, cert_pem, private_key_pem)
        """
        # 创建设备注册表
        registry = DeviceRegistry(str(self.storage_dir / "devices"))

        # 尝试加载已有证书
        cert_data = await registry.load_my_certificate()
        if cert_data:
            self._device_id = cert_data[0]
            self._initialized = True
            return cert_data

        # 生成新证书
        device_id, cert_pem, key_pem = await registry.generate_my_certificate(device_name)
        self._device_id = device_id
        self._device_name = device_name
        self._initialized = True

        logger.info(f"设备初始化完成: {device_id}")

        return device_id, cert_pem, key_pem

    async def load_device(self) -> Optional[str]:
        """加载已有设备"""
        registry = DeviceRegistry(str(self.storage_dir / "devices"))
        cert_data = await registry.load_my_certificate()

        if cert_data:
            self._device_id = cert_data[0]
            self._initialized = True
            return self._device_id

        return None

    async def add_folder(self, config: FolderConfig) -> bool:
        """添加同步文件夹"""
        if not self._engine:
            await self._ensure_engine()

        return await self._engine.add_folder(config)

    async def remove_folder(self, folder_id: str):
        """移除同步文件夹"""
        if self._engine:
            await self._engine.remove_folder(folder_id)

    async def add_device(self, device_info: DeviceInfo) -> bool:
        """添加设备"""
        if not self._engine:
            await self._ensure_engine()

        return await self._engine.add_device(device_info)

    async def import_device(self, data: dict) -> Optional[DeviceInfo]:
        """导入设备（来自分享）"""
        if not self._engine:
            await self._ensure_engine()

        registry = self._engine.device_registry
        return await registry.import_device(data)

    async def export_device(self, device_id: str) -> Optional[dict]:
        """导出设备（用于分享）"""
        if not self._engine:
            return None

        registry = self._engine.device_registry
        return await registry.export_device(device_id)

    async def connect_device(self, device_id: str,
                           addresses: List[str]) -> bool:
        """连接到设备"""
        if not self._engine:
            await self._ensure_engine()

        return await self._engine.connect_to_device(device_id, addresses)

    async def sync_folder(self, folder_id: str,
                         device_id: Optional[str] = None):
        """同步文件夹"""
        if not self._engine:
            return

        await self._engine.sync_folder(folder_id, device_id)

    async def force_sync(self, folder_id: str):
        """强制同步"""
        if not self._engine:
            return

        await self._engine.force_sync(folder_id)

    async def add_relay_server(self, url: str, token: Optional[str] = None):
        """添加中继服务器"""
        if not self._engine:
            await self._ensure_engine()

        await self._engine.relay_pool.add_relay(url, token)

    async def set_callback(self, event: str, callback: Callable):
        """设置回调"""
        self._callbacks[event] = callback

        if self._engine:
            if event == "progress":
                self._engine.set_callbacks(on_progress=callback)
            elif event == "conflict":
                self._engine.set_callbacks(on_conflict=callback)
            elif event == "device_connected":
                self._engine.set_callbacks(on_device_connected=callback)
            elif event == "device_disconnected":
                self._engine.set_callbacks(on_device_disconnected=callback)

    async def start(self):
        """启动同步系统"""
        if not self._initialized:
            raise RuntimeError("设备未初始化")

        await self._ensure_engine()
        await self._engine.start()

        logger.info("根系同步系统已启动")

    async def stop(self):
        """停止同步系统"""
        if self._engine:
            await self._engine.stop()

        logger.info("根系同步系统已停止")

    async def _ensure_engine(self):
        """确保引擎已创建"""
        if self._engine:
            return

        if not self._device_id:
            raise RuntimeError("设备未初始化")

        self._engine = SyncEngine(self._device_id, str(self.storage_dir))

        # 设置回调
        if "progress" in self._callbacks:
            self._engine.set_callbacks(on_progress=self._callbacks["progress"])
        if "conflict" in self._callbacks:
            self._engine.set_callbacks(on_conflict=self._callbacks["conflict"])
        if "device_connected" in self._callbacks:
            self._engine.set_callbacks(on_device_connected=self._callbacks["device_connected"])
        if "device_disconnected" in self._callbacks:
            self._engine.set_callbacks(on_device_disconnected=self._callbacks["device_disconnected"])

    def get_stats(self) -> dict:
        """获取统计信息"""
        if not self._engine:
            return {"initialized": False}

        return {
            "initialized": self._initialized,
            "device_id": self._device_id,
            "running": self._engine.is_running,
            **self._engine.get_stats(),
        }

    async def get_folder_status(self, folder_id: str) -> Optional[dict]:
        """获取文件夹状态"""
        if not self._engine:
            return None

        return await self._engine.get_folder_status(folder_id)

    def get_connected_devices(self) -> List[str]:
        """获取已连接的设备"""
        if not self._engine:
            return []

        return list(self._engine.connections.keys())

    async def wait_for_device(self, device_id: str, timeout: float = 30) -> bool:
        """
        等待设备连接

        Args:
            device_id: 设备ID
            timeout: 超时时间（秒）

        Returns:
            是否连接成功
        """
        if not self._engine:
            return False

        event = asyncio.Event()
        connected = [False]

        async def on_connected(dev_id: str):
            if dev_id == device_id:
                connected[0] = True
                event.set()

        self._engine.set_callbacks(on_device_connected=on_connected)

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return connected[0]
        except asyncio.TimeoutError:
            return False


# 导出所有公共接口
__all__ = [
    # 核心类
    "RootSyncSystem",
    "SyncEngine",
    "BEPProtocol",
    "BEPConnection",

    # 管理器
    "ChunkManager",
    "FolderSync",
    "DeviceRegistry",
    "GlobalDiscovery",
    "ConflictResolver",
    "VersionStore",
    "SelectiveSync",
    "RelayBridge",
    "RelayPool",
    "SyncScheduler",

    # 数据模型
    "FileManifest",
    "FileInfo",
    "FolderConfig",
    "DeviceInfo",
    "BEPChunk",
    "SyncDelta",
    "SyncTask",
    "ConflictRecord",
    "VersionEntry",

    # 枚举
    "MessageType",
    "FileType",
    "ConflictType",
    "ConflictStrategy",
    "VersioningType",
    "TaskPriority",
    "SyncState",
]
