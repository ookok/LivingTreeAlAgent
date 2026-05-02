"""
同步模块
Sync Module

实现企业网盘与虚拟（聚合）云盘的同步功能
"""

from __future__ import annotations



import asyncio
import logging
import time
import os
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class SyncDirection:
    """同步方向"""
    TO_CLOUD = "to_cloud"  # 企业网盘 -> 云盘
    FROM_CLOUD = "from_cloud"  # 云盘 -> 企业网盘
    BIDIRECTIONAL = "bidirectional"  # 双向同步


class SyncStatus:
    """同步状态"""
    IDLE = "idle"  # 空闲
    SYNCING = "syncing"  # 同步中
    SUCCESS = "success"  # 同步成功
    FAILED = "failed"  # 同步失败


class SyncItem:
    """同步项"""
    def __init__(self, local_path: str, cloud_path: str, last_modified: float):
        self.local_path = local_path
        self.cloud_path = cloud_path
        self.last_modified = last_modified
        self.status = "pending"
        self.error = None


class CloudStorageAdapter:
    """云存储适配器基类"""

    async def list_files(self, path: str) -> List[Dict[str, Any]]:
        """列出云存储中的文件"""
        raise NotImplementedError

    async def upload_file(self, local_path: str, cloud_path: str) -> bool:
        """上传文件到云存储"""
        raise NotImplementedError

    async def download_file(self, cloud_path: str, local_path: str) -> bool:
        """从云存储下载文件"""
        raise NotImplementedError

    async def delete_file(self, cloud_path: str) -> bool:
        """从云存储删除文件"""
        raise NotImplementedError

    async def get_file_info(self, cloud_path: str) -> Optional[Dict[str, Any]]:
        """获取云存储文件信息"""
        raise NotImplementedError


class DummyCloudAdapter(CloudStorageAdapter):
    """模拟云存储适配器"""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def list_files(self, path: str) -> List[Dict[str, Any]]:
        """列出云存储中的文件"""
        cloud_dir = self.base_path / path
        if not cloud_dir.exists():
            return []

        files = []
        for item in cloud_dir.iterdir():
            files.append({
                "path": str(item.relative_to(self.base_path)),
                "name": item.name,
                "size": item.stat().st_size,
                "last_modified": item.stat().st_mtime,
                "is_directory": item.is_dir()
            })
        return files

    async def upload_file(self, local_path: str, cloud_path: str) -> bool:
        """上传文件到云存储"""
        cloud_file = self.base_path / cloud_path
        cloud_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            import shutil
            shutil.copy2(local_path, cloud_file)
            return True
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            return False

    async def download_file(self, cloud_path: str, local_path: str) -> bool:
        """从云存储下载文件"""
        cloud_file = self.base_path / cloud_path
        if not cloud_file.exists():
            return False

        local_file = Path(local_path)
        local_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            import shutil
            shutil.copy2(cloud_file, local_file)
            return True
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            return False

    async def delete_file(self, cloud_path: str) -> bool:
        """从云存储删除文件"""
        cloud_file = self.base_path / cloud_path
        if not cloud_file.exists():
            return True

        try:
            if cloud_file.is_dir():
                import shutil
                shutil.rmtree(cloud_file)
            else:
                cloud_file.unlink()
            return True
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return False

    async def get_file_info(self, cloud_path: str) -> Optional[Dict[str, Any]]:
        """获取云存储文件信息"""
        cloud_file = self.base_path / cloud_path
        if not cloud_file.exists():
            return None

        return {
            "path": str(cloud_file.relative_to(self.base_path)),
            "name": cloud_file.name,
            "size": cloud_file.stat().st_size,
            "last_modified": cloud_file.stat().st_mtime,
            "is_directory": cloud_file.is_dir()
        }


class SyncManager:
    """同步管理器"""

    def __init__(self):
        self.sync_jobs: Dict[str, SyncJob] = {}

    def create_sync_job(self, job_id: str, local_root: str, cloud_root: str, direction: str, adapter: CloudStorageAdapter) -> "SyncJob":
        """创建同步任务"""
        job = SyncJob(job_id, local_root, cloud_root, direction, adapter)
        self.sync_jobs[job_id] = job
        return job

    def get_sync_job(self, job_id: str) -> Optional["SyncJob"]:
        """获取同步任务"""
        return self.sync_jobs.get(job_id)

    def list_sync_jobs(self) -> List[Dict[str, Any]]:
        """列出所有同步任务"""
        return [job.to_dict() for job in self.sync_jobs.values()]

    async def start_sync_job(self, job_id: str) -> bool:
        """启动同步任务"""
        job = self.get_sync_job(job_id)
        if not job:
            return False
        await job.start()
        return True

    async def stop_sync_job(self, job_id: str) -> bool:
        """停止同步任务"""
        job = self.get_sync_job(job_id)
        if not job:
            return False
        await job.stop()
        return True


class SyncJob:
    """同步任务"""

    def __init__(self, job_id: str, local_root: str, cloud_root: str, direction: str, adapter: CloudStorageAdapter):
        self.job_id = job_id
        self.local_root = local_root
        self.cloud_root = cloud_root
        self.direction = direction
        self.adapter = adapter
        self.status = SyncStatus.IDLE
        self.last_sync = None
        self.sync_items: List[SyncItem] = []
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """开始同步"""
        if self._running:
            return

        self._running = True
        self.status = SyncStatus.SYNCING
        self._task = asyncio.create_task(self._sync_loop())

    async def stop(self):
        """停止同步"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.status = SyncStatus.IDLE

    async def _sync_loop(self):
        """同步循环"""
        try:
            await self._perform_sync()
            self.status = SyncStatus.SUCCESS
            self.last_sync = time.time()
        except Exception as e:
            logger.error(f"Sync job failed: {e}")
            self.status = SyncStatus.FAILED
        finally:
            self._running = False

    async def _perform_sync(self):
        """执行同步"""
        # 扫描本地文件
        local_files = await self._scan_local_files(self.local_root)
        # 扫描云存储文件
        cloud_files = await self._scan_cloud_files(self.cloud_root)

        # 比较文件，生成同步项
        self.sync_items = await self._generate_sync_items(local_files, cloud_files)

        # 执行同步
        for item in self.sync_items:
            if not self._running:
                break

            try:
                item.status = "syncing"
                success = await self._sync_item(item)
                if success:
                    item.status = "success"
                else:
                    item.status = "failed"
                    item.error = "Sync failed"
            except Exception as e:
                item.status = "failed"
                item.error = str(e)
            await asyncio.sleep(0.1)  # 避免过于密集的操作

    async def _scan_local_files(self, root: str) -> Dict[str, Dict[str, Any]]:
        """扫描本地文件"""
        files = {}
        root_path = Path(root)

        for dirpath, dirnames, filenames in os.walk(root):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(file_path, root)
                stat = os.stat(file_path)
                files[rel_path] = {
                    "path": file_path,
                    "size": stat.st_size,
                    "last_modified": stat.st_mtime
                }

        return files

    async def _scan_cloud_files(self, root: str) -> Dict[str, Dict[str, Any]]:
        """扫描云存储文件"""
        files = {}
        cloud_files = await self.adapter.list_files(root)

        for file_info in cloud_files:
            if not file_info.get("is_directory"):
                rel_path = os.path.relpath(file_info["path"], root)
                files[rel_path] = {
                    "path": file_info["path"],
                    "size": file_info["size"],
                    "last_modified": file_info["last_modified"]
                }

        return files

    async def _generate_sync_items(self, local_files: Dict[str, Dict[str, Any]], cloud_files: Dict[str, Dict[str, Any]]) -> List[SyncItem]:
        """生成同步项"""
        items = []

        if self.direction in [SyncDirection.TO_CLOUD, SyncDirection.BIDIRECTIONAL]:
            # 本地 -> 云盘
            for rel_path, local_info in local_files.items():
                cloud_info = cloud_files.get(rel_path)
                if not cloud_info or local_info["last_modified"] > cloud_info["last_modified"]:
                    local_path = local_info["path"]
                    cloud_path = os.path.join(self.cloud_root, rel_path).replace("\\", "/")
                    items.append(SyncItem(local_path, cloud_path, local_info["last_modified"]))

        if self.direction in [SyncDirection.FROM_CLOUD, SyncDirection.BIDIRECTIONAL]:
            # 云盘 -> 本地
            for rel_path, cloud_info in cloud_files.items():
                local_info = local_files.get(rel_path)
                if not local_info or cloud_info["last_modified"] > local_info["last_modified"]:
                    local_path = os.path.join(self.local_root, rel_path)
                    cloud_path = cloud_info["path"]
                    items.append(SyncItem(local_path, cloud_path, cloud_info["last_modified"]))

        return items

    async def _sync_item(self, item: SyncItem) -> bool:
        """同步单个项目"""
        if self.direction in [SyncDirection.TO_CLOUD, SyncDirection.BIDIRECTIONAL]:
            # 本地 -> 云盘
            return await self.adapter.upload_file(item.local_path, item.cloud_path)
        elif self.direction == SyncDirection.FROM_CLOUD:
            # 云盘 -> 本地
            return await self.adapter.download_file(item.cloud_path, item.local_path)
        return False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "job_id": self.job_id,
            "local_root": self.local_root,
            "cloud_root": self.cloud_root,
            "direction": self.direction,
            "status": self.status,
            "last_sync": self.last_sync,
            "sync_items_count": len(self.sync_items)
        }


# 单例
sync_manager = SyncManager()


def get_sync_manager() -> SyncManager:
    """获取同步管理器"""
    return sync_manager
