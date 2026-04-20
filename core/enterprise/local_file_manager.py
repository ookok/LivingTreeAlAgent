"""
本地文件管理器
Local File Manager

管理本地文件的路径记录和状态监控
"""

from __future__ import annotations

import os
import time
import asyncio
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class LocalFileMonitor:
    """本地文件监控器"""

    def __init__(self):
        self.monitored_files: Dict[str, Dict[str, Any]] = {}
        self.monitor_task: Optional[asyncio.Task] = None
        self.is_running = False
        self.check_interval = 30  # 检查间隔（秒）

    async def start(self):
        """启动监控"""
        self.is_running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Local file monitor started")

    async def stop(self):
        """停止监控"""
        self.is_running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Local file monitor stopped")

    async def _monitor_loop(self):
        """监控循环"""
        while self.is_running:
            try:
                await self._check_files()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(self.check_interval)

    async def _check_files(self):
        """检查文件状态"""
        for file_id, file_info in list(self.monitored_files.items()):
            local_path = file_info.get("local_path")
            if not local_path:
                continue

            path = Path(local_path)
            status = "exists"
            modified_at = None

            if not path.exists():
                status = "deleted"
            else:
                modified_at = path.stat().st_mtime
                # 检查是否被修改
                if file_info.get("last_modified") and modified_at > file_info.get("last_modified"):
                    status = "modified"

            # 更新状态
            self.monitored_files[file_id].update({
                "status": status,
                "last_modified": modified_at,
                "last_checked": time.time()
            })

            if status != "exists":
                logger.info(f"File {local_path} status changed: {status}")

    def add_file(self, file_id: str, local_path: str):
        """添加文件到监控"""
        path = Path(local_path)
        status = "exists" if path.exists() else "deleted"
        modified_at = path.stat().st_mtime if path.exists() else None

        self.monitored_files[file_id] = {
            "local_path": local_path,
            "status": status,
            "last_modified": modified_at,
            "last_checked": time.time()
        }
        logger.info(f"Added file to monitor: {local_path}")

    def remove_file(self, file_id: str):
        """从监控中移除文件"""
        if file_id in self.monitored_files:
            del self.monitored_files[file_id]
            logger.info(f"Removed file from monitor: {file_id}")

    def get_file_status(self, file_id: str) -> Optional[Dict[str, Any]]:
        """获取文件状态"""
        return self.monitored_files.get(file_id)

    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """获取所有文件状态"""
        return self.monitored_files


class LocalFileManager:
    """本地文件管理器"""

    def __init__(self):
        self.file_monitor = LocalFileMonitor()
        self.local_files: Dict[str, Dict[str, Any]] = {}

    async def start(self):
        """启动管理器"""
        await self.file_monitor.start()

    async def stop(self):
        """停止管理器"""
        await self.file_monitor.stop()

    def add_local_file(self, file_id: str, local_path: str, metadata: Optional[Dict[str, Any]] = None):
        """添加本地文件"""
        if not os.path.exists(local_path):
            raise ValueError(f"Local file does not exist: {local_path}")

        # 获取文件信息
        path = Path(local_path)
        file_info = {
            "local_path": local_path,
            "is_directory": path.is_dir(),
            "size": self._get_size(path),
            "created_at": path.stat().st_ctime,
            "modified_at": path.stat().st_mtime,
            "metadata": metadata or {}
        }

        self.local_files[file_id] = file_info
        self.file_monitor.add_file(file_id, local_path)
        logger.info(f"Added local file: {local_path}")

    def remove_local_file(self, file_id: str):
        """移除本地文件记录"""
        if file_id in self.local_files:
            del self.local_files[file_id]
            self.file_monitor.remove_file(file_id)
            logger.info(f"Removed local file record: {file_id}")

    def get_local_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """获取本地文件信息"""
        file_info = self.local_files.get(file_id)
        if file_info:
            # 获取最新状态
            status = self.file_monitor.get_file_status(file_id)
            if status:
                file_info["status"] = status.get("status")
                file_info["last_checked"] = status.get("last_checked")
        return file_info

    def get_local_files(self) -> Dict[str, Dict[str, Any]]:
        """获取所有本地文件"""
        return self.local_files

    def _get_size(self, path: Path) -> int:
        """获取文件或文件夹大小"""
        if path.is_file():
            return path.stat().st_size
        elif path.is_dir():
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    total_size += os.path.getsize(filepath)
            return total_size
        return 0


# 单例
local_file_manager = LocalFileManager()


def get_local_file_manager() -> LocalFileManager:
    """获取本地文件管理器"""
    return local_file_manager
