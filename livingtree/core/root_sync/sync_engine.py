"""
同步引擎 - Sync Engine

整合所有组件，提供完整的文件同步功能：
- BEP 协议通信
- 文件夹管理
- 冲突处理
- 版本控制
- 任务调度
"""

import asyncio
import os
import json
import time
import logging
from typing import Dict, List, Optional, Callable, Tuple
from pathlib import Path

from .models import (
    FileManifest, FileInfo, FolderConfig, DeviceInfo,
    ConflictStrategy, MessageType, BEPChunk
)
from .bep_protocol import BEPProtocol, BEPConnection
from .chunk_manager import ChunkManager
from .folder_sync import FolderSync, SyncDelta
from .device_registry import DeviceRegistry, GlobalDiscovery
from .conflict_resolver import ConflictResolver, ConflictRecord
from .version_store import VersionStore, VersioningType
from .selective_sync import SelectiveSync
from .relay_bridge import RelayBridge, RelayPool, RelayConfig
from .sync_scheduler import SyncScheduler, SyncTask, TaskPriority

logger = logging.getLogger(__name__)


class SyncEngine:
    """
    同步引擎

    整合所有组件，提供统一的文件同步接口：
    1. 管理多个文件夹的同步
    2. 管理多个设备的连接
    3. 处理同步冲突
    4. 调度同步任务
    """

    def __init__(self, device_id: str, storage_dir: str):
        self.device_id = device_id
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 组件
        self.protocol = BEPProtocol(device_id)
        self.chunk_manager = ChunkManager(
            str(self.storage_dir / "chunks"),
            block_size=256 * 1024  # 256KB
        )

        self.device_registry = DeviceRegistry(str(self.storage_dir / "devices"))
        self.discovery = GlobalDiscovery(self.device_registry)

        self.conflict_resolver = ConflictResolver(str(self.storage_dir / "conflicts"))
        self.version_store = VersionStore(str(self.storage_dir / "versions"))

        self.scheduler = SyncScheduler(max_concurrent=3)
        self.relay_pool = RelayPool(device_id)

        # 文件夹
        self.folders: Dict[str, FolderSync] = {}
        self.folder_configs: Dict[str, FolderConfig] = {}

        # 连接
        self.connections: Dict[str, BEPConnection] = {}

        # 状态
        self._running = False
        self._connected_devices: Dict[str, asyncio.Event] = {}

        # 回调
        self._on_sync_progress: Optional[Callable] = None
        self._on_conflict: Optional[Callable] = None
        self._on_device_connected: Optional[Callable] = None
        self._on_device_disconnected: Optional[Callable] = None

        # 加载配置
        self._load_config()

    @property
    def is_running(self) -> bool:
        return self._running

    def set_callbacks(self,
                     on_progress: Optional[Callable] = None,
                     on_conflict: Optional[Callable] = None,
                     on_device_connected: Optional[Callable] = None,
                     on_device_disconnected: Optional[Callable] = None):
        """设置回调"""
        self._on_sync_progress = on_progress
        self._on_conflict = on_conflict
        self._on_device_connected = on_device_connected
        self._on_device_disconnected = on_device_disconnected

    # ==================== 文件夹管理 ====================

    async def add_folder(self, config: FolderConfig) -> bool:
        """
        添加同步文件夹

        Args:
            config: 文件夹配置

        Returns:
            是否成功
        """
        if config.folder_id in self.folders:
            return False

        # 检查路径
        if not os.path.exists(config.path):
            try:
                os.makedirs(config.path, exist_ok=True)
            except Exception:
                return False

        # 创建文件夹同步器
        folder_sync = FolderSync(config, self.chunk_manager)
        self.folders[config.folder_id] = folder_sync
        self.folder_configs[config.folder_id] = config

        # 保存配置
        await self._save_folder_config(config)

        # 设置冲突处理
        folder_sync.set_callbacks(
            on_progress=self._on_sync_progress,
            on_conflict=self._handle_conflict,
        )

        return True

    async def remove_folder(self, folder_id: str):
        """移除同步文件夹"""
        if folder_id in self.folders:
            # 取消相关任务
            self.scheduler.cancel_folder_tasks(folder_id)

            del self.folders[folder_id]
            del self.folder_configs[folder_id]

            # 删除配置
            config_path = self.storage_dir / "folders" / f"{folder_id}.json"
            if config_path.exists():
                config_path.unlink()

    async def get_folder_status(self, folder_id: str) -> Optional[dict]:
        """获取文件夹状态"""
        if folder_id not in self.folders:
            return None

        folder = self.folders[folder_id]
        config = self.folder_configs[folder_id]

        return {
            "folder_id": folder_id,
            "path": config.path,
            "is_scanning": folder._scanning,
            "is_syncing": folder._syncing,
            "local_files": len(folder.local_manifest.files) if folder.local_manifest else 0,
            "remote_files": len(folder.remote_manifest.files) if folder.remote_manifest else 0,
            "pending_tasks": self.scheduler.get_folder_tasks(folder_id),
        }

    # ==================== 设备管理 ====================

    async def add_device(self, device_info: DeviceInfo) -> bool:
        """添加设备"""
        await self.device_registry.add_device(device_info)
        return True

    async def remove_device(self, device_id: str):
        """移除设备"""
        await self.device_registry.remove_device(device_id)

        # 断开连接
        if device_id in self.connections:
            await self.connections[device_id].close()
            del self.connections[device_id]

    async def connect_to_device(self, device_id: str,
                               addresses: List[str]) -> bool:
        """
        连接到设备

        Args:
            device_id: 设备ID
            addresses: 地址列表

        Returns:
            是否成功
        """
        if device_id == self.device_id:
            return False

        # 尝试每个地址
        for addr in addresses:
            try:
                host, port = self._parse_address(addr)
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=10
                )

                # 创建连接
                conn = BEPConnection(self.protocol, reader, writer, device_id)
                self.connections[device_id] = conn

                # 触发回调
                if self._on_device_connected:
                    await self._on_device_connected(device_id)

                # 启动同步
                asyncio.create_task(self._sync_with_device(device_id, conn))

                return True

            except Exception:
                continue

        # 尝试中继
        relay = await self.relay_pool.connect_to(device_id)
        if relay:
            self.connections[device_id] = relay
            return True

        return False

    async def _sync_with_device(self, device_id: str, conn: BEPConnection):
        """与设备同步"""
        try:
            # 握手
            device_info = self.device_registry.get_device(device_id)
            if not device_info:
                return

            await conn.handshake(os.environ.get("HOSTNAME", "Hermes"), device_info)

            # 同步每个文件夹
            for folder_id, folder in self.folders.items():
                # 扫描本地
                await folder.scan_local()

                # 发送本地清单
                if folder.local_manifest:
                    await self.protocol.send_index(
                        conn.writer, folder_id, folder.local_manifest
                    )

            # 保持连接，处理消息
            while conn.protocol._closed is False:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"与设备 {device_id} 同步失败: {e}")

        finally:
            if device_id in self.connections:
                del self.connections[device_id]

            if self._on_device_disconnected:
                await self._on_device_disconnected(device_id)

    async def _handle_index(self, conn: BEPConnection, index: dict):
        """处理收到的文件清单"""
        folder_id = index.get("folder_id")
        if folder_id not in self.folders:
            return

        folder = self.folders[folder_id]

        # 构建远程清单
        remote_manifest = FileManifest(
            folder_id=folder_id,
            device_id=conn.peer_device_id,
        )
        for file_id, file_data in index.get("files", {}).items():
            remote_manifest.add_file(FileInfo.from_dict(file_data))

        folder.remote_manifest = remote_manifest

        # 计算差异
        delta = folder.compute_delta(remote_manifest)

        if delta.has_work:
            # 创建同步任务
            for file_id in delta.need_download:
                task = SyncTask(
                    task_id=f"{folder_id}:{file_id}:download",
                    folder_id=folder_id,
                    device_id=conn.peer_device_id,
                    file_id=file_id,
                    file_name=remote_manifest.files[file_id].name,
                    file_size=remote_manifest.files[file_id].size,
                    operation="pull",
                    priority=TaskPriority.NORMAL,
                )
                self.scheduler.add_task(task)

            for file_id in delta.need_upload:
                task = SyncTask(
                    task_id=f"{folder_id}:{file_id}:upload",
                    folder_id=folder_id,
                    device_id=conn.peer_device_id,
                    file_id=file_id,
                    file_name=folder.local_manifest.files[file_id].name,
                    file_size=folder.local_manifest.files[file_id].size,
                    operation="push",
                    priority=TaskPriority.NORMAL,
                )
                self.scheduler.add_task(task)

    async def _handle_conflict(self, file_id: str, local: FileInfo, remote: FileInfo):
        """处理冲突"""
        record = ConflictRecord(
            file_id=file_id,
            file_name=local.name,
            local_version=local,
            remote_version=remote,
        )

        # 检测冲突类型
        conflict_type, _ = self.conflict_resolver.detect_conflict(local, remote)
        record.conflict_type = conflict_type

        # 获取解决策略
        folder_id = local.name.split("/")[0]  # 简化
        config = self.folder_configs.get(folder_id)
        if config:
            await self.conflict_resolver.resolve(record, config.conflict_strategy)

        if self._on_conflict:
            await self._on_conflict(record)

    # ==================== 同步操作 ====================

    async def sync_folder(self, folder_id: str, device_id: Optional[str] = None):
        """
        同步文件夹

        Args:
            folder_id: 文件夹ID
            device_id: 设备ID（None = 所有设备）
        """
        if folder_id not in self.folders:
            return

        folder = self.folders[folder_id]

        # 扫描本地
        await folder.scan_local()

        # 如果没有指定设备，与所有已连接设备同步
        if device_id is None:
            for peer_id, conn in self.connections.items():
                if conn.protocol._closed:
                    continue

                # 发送本地清单
                if folder.local_manifest:
                    await self.protocol.send_index(
                        conn.writer, folder_id, folder.local_manifest
                    )

        elif device_id in self.connections:
            conn = self.connections[device_id]
            if folder.local_manifest:
                await self.protocol.send_index(
                    conn.writer, folder_id, folder.local_manifest
                )

    async def force_sync(self, folder_id: str):
        """强制同步（重新计算所有差异）"""
        if folder_id not in self.folders:
            return

        folder = self.folders[folder_id]

        # 重新扫描
        await folder.scan_local()

        # 触发与所有设备的同步
        await self.sync_folder(folder_id)

    # ==================== 生命周期 ====================

    async def start(self):
        """启动同步引擎"""
        if self._running:
            return

        self._running = True

        # 启动调度器
        await self.scheduler.start()

        # 注册到发现服务
        addresses = self._get_listen_addresses()
        await self.discovery.register_device(self.device_id, addresses)

        # 尝试连接已知的设备
        for device in self.device_registry.get_all_devices():
            for addr in device.addresses:
                asyncio.create_task(self.connect_to_device(device.device_id, [addr]))

    async def stop(self):
        """停止同步引擎"""
        if not self._running:
            return

        self._running = False

        # 停止调度器
        await self.scheduler.stop()

        # 断开所有连接
        for conn in list(self.connections.values()):
            await conn.close()

        self.connections.clear()

        # 断开中继
        await self.relay_pool.disconnect_all()

    # ==================== 工具方法 ====================

    def _parse_address(self, addr: str) -> Tuple[str, int]:
        """解析地址"""
        if ":" in addr:
            host, port = addr.rsplit(":", 1)
            return host, int(port)
        return addr, 22000

    def _get_listen_addresses(self) -> List[str]:
        """获取监听地址"""
        # 简化实现
        return [f"0.0.0.0:22000"]

    async def _save_folder_config(self, config: FolderConfig):
        """保存文件夹配置"""
        folder_dir = self.storage_dir / "folders"
        folder_dir.mkdir(exist_ok=True)

        config_path = folder_dir / f"{config.folder_id}.json"
        with open(config_path, "w") as f:
            json.dump(config.to_dict(), f)

    def _load_config(self):
        """加载配置"""
        # 加载文件夹配置
        folder_dir = self.storage_dir / "folders"
        if folder_dir.exists():
            for config_file in folder_dir.glob("*.json"):
                try:
                    with open(config_file, "r") as f:
                        data = json.load(f)
                    config = FolderConfig(**data)
                    asyncio.create_task(self.add_folder(config))
                except Exception:
                    pass

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "device_id": self.device_id,
            "folders": len(self.folders),
            "devices": len(self.device_registry.get_all_devices()),
            "connections": len(self.connections),
            "scheduler": self.scheduler.get_stats(),
            "chunk_cache": self.chunk_manager.get_stats(),
        }
