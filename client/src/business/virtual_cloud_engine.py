"""
Virtual Cloud Engine - 虚拟云盘引擎

统一管理多个云盘驱动，提供虚拟文件系统接口，
实现元数据缓存、额度感知调度、任务队列等功能。

架构参考: CloudSync (KKRainnn/CloudSync)
接口参考: fsspec 文件系统抽象
"""

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Optional

from client.src.business.cloud_drivers.base_driver import (
    BaseCloudDriver,
    CloudEntry,
    CloudProvider,
    CloudQuota,
    DriverConfig,
    DriverRegistry,
    EntryType,
)


# ============= 缓存策略 =============

class CachePolicy(Enum):
    """缓存策略"""
    NEVER = "never"           # 从不缓存
    MEMORY = "memory"         # 仅内存缓存
    DISK = "disk"            # 磁盘缓存
    ALL = "all"              # 内存 + 磁盘


@dataclass
class CacheEntry:
    """缓存条目"""
    entry: CloudEntry
    cached_at: float
    expires_at: float  # 过期时间戳
    local_path: Optional[Path] = None  # 本地缓存路径

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


# ============= 任务模型 =============

class TaskType(Enum):
    """任务类型"""
    DOWNLOAD = "download"
    UPLOAD = "upload"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TransferTask:
    """传输任务"""
    task_id: str
    task_type: TaskType
    source_path: str      # 源路径 (虚拟路径)
    dest_path: str        # 目标路径 (本地或虚拟)
    size: int = 0         # 总大小
    transferred: int = 0  # 已传输大小
    status: TaskStatus = TaskStatus.PENDING
    driver_name: str = "" # 使用的驱动
    error: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    @property
    def progress(self) -> float:
        """进度百分比"""
        if self.size == 0:
            return 0.0
        return (self.transferred / self.size) * 100


# ============= 虚拟云盘引擎 =============

class VirtualCloudEngine:
    """
    虚拟云盘引擎

    功能:
    - 多驱动统一管理
    - 虚拟路径解析
    - 元数据缓存
    - 额度感知调度
    - 传输任务队列
    - 本地磁盘缓存
    """

    def __init__(
        self,
        cache_dir: str = None,
        default_cache_ttl: int = 300  # 默认缓存5分钟
    ):
        # 路径配置
        self.cache_dir = Path(cache_dir or "./.hermes/clouds_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 驱动注册表
        self.drivers = DriverRegistry()

        # 缓存
        self._memory_cache: dict[str, CacheEntry] = {}
        self.default_cache_ttl = default_cache_ttl

        # 任务队列
        self._tasks: dict[str, TransferTask] = {}
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._task_lock = asyncio.Lock()

        # 调度策略
        self._read_priority: list[str] = []  # 读操作优先级顺序
        self._write_priority: list[str] = []  # 写操作优先级顺序

    # ── 驱动管理 ─────────────────────────────────────────────────────

    def register_driver(
        self,
        name: str,
        driver: BaseCloudDriver,
        set_default: bool = False
    ) -> None:
        """注册云盘驱动"""
        self.drivers.register(name, driver, set_default)

        # 更新调度优先级
        if driver.config.provider.value not in self._read_priority:
            self._read_priority.append(driver.config.provider.value)
        if driver.config.provider.value not in self._write_priority:
            self._write_priority.append(driver.config.provider.value)

    def get_driver(self, name: str) -> Optional[BaseCloudDriver]:
        """获取驱动"""
        return self.drivers.get(name)

    def resolve_driver(self, virtual_path: str) -> tuple[Optional[str], Optional[BaseCloudDriver]]:
        """
        根据虚拟路径解析驱动

        Args:
            virtual_path: 虚拟路径，格式: /clouds/{driver_name}/...

        Returns:
            (驱动名称, 驱动实例)
        """
        # 解析路径
        parts = virtual_path.strip("/").split("/", 2)
        if len(parts) < 2 or parts[0] != "clouds":
            return None, None

        driver_name = parts[1]
        driver = self.drivers.get(driver_name)

        return driver_name, driver

    # ── 缓存 ─────────────────────────────────────────────────────

    def _get_cache_key(self, virtual_path: str) -> str:
        """获取缓存键"""
        return virtual_path.strip("/").lower()

    def _get_cached(self, virtual_path: str) -> Optional[CloudEntry]:
        """获取缓存条目"""
        key = self._get_cache_key(virtual_path)
        cached = self._memory_cache.get(key)

        if cached and not cached.is_expired():
            return cached.entry

        # 检查过期，删除
        if cached:
            del self._memory_cache[key]

        return None

    def _set_cache(
        self,
        virtual_path: str,
        entry: CloudEntry,
        ttl: Optional[int] = None
    ) -> None:
        """设置缓存"""
        if ttl == 0:  # ttl=0 表示不缓存
            return

        key = self._get_cache_key(virtual_path)
        now = time.time()
        expires_at = now + (ttl or self.default_cache_ttl)

        self._memory_cache[key] = CacheEntry(
            entry=entry,
            cached_at=now,
            expires_at=expires_at
        )

    def invalidate_cache(self, virtual_path: str) -> None:
        """使缓存失效"""
        key = self._get_cache_key(virtual_path)
        if key in self._memory_cache:
            del self._memory_cache[key]

    def clear_cache(self) -> None:
        """清空所有缓存"""
        self._memory_cache.clear()

    # ── 虚拟文件系统操作 ─────────────────────────────────────────────────────

    async def list_directory(self, virtual_path: str = "/") -> list[CloudEntry]:
        """
        列出目录内容

        Args:
            virtual_path: 虚拟路径

        Returns:
            条目列表
        """
        # 检查缓存
        cached = self._get_cached(virtual_path)
        if cached:
            # 返回缓存的目录内容（需要额外获取子项）
            pass

        # 解析驱动
        driver_name, driver = self.resolve_driver(virtual_path)
        if not driver:
            # 根目录或云盘列表
            return await self._list_clouds(virtual_path)

        # 转发到驱动
        cloud_path = driver.virtual_to_cloud_path(virtual_path)
        entries, _ = await driver.list(cloud_path)

        # 转换为本引擎的虚拟路径
        for entry in entries:
            entry.path = f"/clouds/{driver_name}/{driver.virtual_to_cloud_path(entry.path).lstrip('/')}"
            entry.cloud = driver_name

        return entries

    async def _list_clouds(self, virtual_path: str) -> list[CloudEntry]:
        """列出所有云盘"""
        entries = []

        for name in self.drivers.names:
            driver = self.drivers.get(name)
            if not driver or not driver.config.enabled:
                continue

            entries.append(CloudEntry(
                path=f"/clouds/{name}",
                name=name,
                entry_type=EntryType.FOLDER,
                cloud=name,
                real_id=name,
            ))

        return entries

    async def stat(self, virtual_path: str) -> Optional[CloudEntry]:
        """
        获取文件/目录信息

        Args:
            virtual_path: 虚拟路径

        Returns:
            CloudEntry 或 None
        """
        # 检查缓存
        cached = self._get_cached(virtual_path)
        if cached:
            return cached

        # 解析驱动
        driver_name, driver = self.resolve_driver(virtual_path)
        if not driver:
            # 根目录
            if virtual_path == "/" or virtual_path == "":
                return CloudEntry(
                    path="/",
                    name="",
                    entry_type=EntryType.FOLDER,
                    size=0
                )
            return None

        # 转发到驱动
        cloud_path = driver.virtual_to_cloud_path(virtual_path)
        entry = await driver.stat(cloud_path)

        if entry:
            entry.path = f"/clouds/{driver_name}/{cloud_path.lstrip('/')}"
            entry.cloud = driver_name
            self._set_cache(virtual_path, entry)

        return entry

    async def download(
        self,
        virtual_path: str,
        dest: BinaryIO,
        progress_callback: Optional[callable] = None,
        driver_name: Optional[str] = None
    ) -> int:
        """
        下载文件

        Args:
            virtual_path: 虚拟路径
            dest: 目标文件对象
            progress_callback: 进度回调
            driver_name: 指定驱动 (不指定则自动选择)

        Returns:
            下载字节数
        """
        # 解析驱动
        if driver_name:
            driver = self.drivers.get(driver_name)
        else:
            _, driver = self.resolve_driver(virtual_path)

        if not driver:
            raise ValueError(f"找不到云盘驱动: {virtual_path}")

        # 检查缓存
        cached = self._get_cached(virtual_path)
        if cached and cached.local_path and cached.local_path.exists():
            # 使用本地缓存
            with open(cached.local_path, "rb") as f:
                shutil.copyfileobj(f, dest)
            return cached.entry.size

        # 从云盘下载
        cloud_path = driver.virtual_to_cloud_path(virtual_path)

        async def _progress_wrapper(downloaded: int, total: int):
            if progress_callback:
                progress_callback(downloaded, total)

        bytes_read = await driver.download(
            cloud_path,
            dest,
            progress_callback=_progress_wrapper
        )

        # 使缓存失效（文件可能已更新）
        self.invalidate_cache(virtual_path)

        return bytes_read

    async def upload(
        self,
        source: BinaryIO,
        virtual_path: str,
        size: int,
        progress_callback: Optional[callable] = None,
        driver_name: Optional[str] = None
    ) -> Optional[CloudEntry]:
        """
        上传文件

        Args:
            source: 源文件对象
            virtual_path: 目标虚拟路径
            size: 文件大小
            progress_callback: 进度回调
            driver_name: 指定驱动 (不指定则额度感知选择)

        Returns:
            上传后的 CloudEntry
        """
        # 选择驱动（额度感知）
        if not driver_name:
            driver_name = await self._select_driver_for_upload()
            if not driver_name:
                raise ValueError("没有可用的云盘驱动")

        driver = self.drivers.get(driver_name)
        if not driver:
            raise ValueError(f"云盘驱动不可用: {driver_name}")

        # 上传到云盘
        cloud_path = driver.virtual_to_cloud_path(virtual_path)

        entry = await driver.upload(
            source,
            cloud_path,
            size,
            progress_callback=progress_callback
        )

        if entry:
            entry.path = virtual_path
            entry.cloud = driver_name
            # 缓存新上传的文件
            self._set_cache(virtual_path, entry, ttl=60)  # 上传后缓存1分钟

        return entry

    # ── 额度感知调度 ─────────────────────────────────────────────────────

    async def _select_driver_for_upload(self) -> Optional[str]:
        """
        选择最适合上传的驱动（额度感知）

        选择策略:
        1. 优先选择免费额度充足且未满的盘
        2. 其次选择已用比例最低的盘
        3. 最后按优先级顺序

        Returns:
            驱动名称
        """
        candidates = []

        for name in self._write_priority:
            driver = self.drivers.get(name)
            if not driver or not driver.is_authenticated:
                continue

            try:
                quota = await driver.get_quota()
                free_percent = (quota.free / quota.total * 100) if quota.total > 0 else 0

                candidates.append({
                    "name": name,
                    "free": quota.free,
                    "free_percent": free_percent,
                    "priority": self._write_priority.index(name)
                })
            except Exception:
                continue

        if not candidates:
            return None

        # 按剩余空间排序
        candidates.sort(key=lambda x: (-x["free_percent"], x["priority"]))
        return candidates[0]["name"]

    async def _select_driver_for_download(self) -> Optional[str]:
        """
        选择最适合下载的驱动（读优先策略）

        Returns:
            驱动名称
        """
        # 读优先：直接按优先级返回第一个可用的
        for name in self._read_priority:
            driver = self.drivers.get(name)
            if driver and driver.is_authenticated:
                return name
        return None

    # ── 任务队列 ─────────────────────────────────────────────────────

    async def submit_download(
        self,
        virtual_path: str,
        dest_path: str,
        driver_name: Optional[str] = None
    ) -> str:
        """
        提交下载任务

        Returns:
            任务ID
        """
        task_id = self._generate_task_id()

        # 获取文件信息
        entry = await self.stat(virtual_path)
        if not entry:
            raise ValueError(f"文件不存在: {virtual_path}")

        task = TransferTask(
            task_id=task_id,
            task_type=TaskType.DOWNLOAD,
            source_path=virtual_path,
            dest_path=dest_path,
            size=entry.size,
            driver_name=driver_name or (await self._select_driver_for_download() or "")
        )

        async with self._task_lock:
            self._tasks[task_id] = task

        await self._task_queue.put(task_id)
        return task_id

    async def submit_upload(
        self,
        source_path: str,
        virtual_path: str,
        size: int,
        driver_name: Optional[str] = None
    ) -> str:
        """
        提交上传任务

        Returns:
            任务ID
        """
        task_id = self._generate_task_id()

        task = TransferTask(
            task_id=task_id,
            task_type=TaskType.UPLOAD,
            source_path=source_path,
            dest_path=virtual_path,
            size=size,
            driver_name=driver_name or (await self._select_driver_for_upload() or "")
        )

        async with self._task_lock:
            self._tasks[task_id] = task

        await self._task_queue.put(task_id)
        return task_id

    def get_task(self, task_id: str) -> Optional[TransferTask]:
        """获取任务信息"""
        return self._tasks.get(task_id)

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None
    ) -> list[TransferTask]:
        """列出任务"""
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return False

        task.status = TaskStatus.CANCELLED
        return True

    def _generate_task_id(self) -> str:
        """生成任务ID"""
        import uuid
        return str(uuid.uuid4())[:8]

    # ── 虚拟目录树 ─────────────────────────────────────────────────────

    async def get_tree(
        self,
        virtual_path: str = "/",
        max_depth: int = 3,
        current_depth: int = 0
    ) -> dict:
        """
        获取虚拟目录树

        Args:
            virtual_path: 起始路径
            max_depth: 最大深度
            current_depth: 当前深度

        Returns:
            目录树字典
        """
        if current_depth >= max_depth:
            return {"type": "truncated"}

        entry = await self.stat(virtual_path)
        if not entry:
            return {}

        if entry.is_file:
            return {
                "type": "file",
                "name": entry.name,
                "size": entry.size
            }

        # 目录
        children = await self.list(virtual_path)
        tree = {
            "type": "folder",
            "name": entry.name or "/",
            "children": []
        }

        for child in children[:50]:  # 限制每个目录最多50项
            child_path = child.path
            if child.is_folder:
                subtree = await self.get_tree(
                    child_path,
                    max_depth=max_depth,
                    current_depth=current_depth + 1
                )
                tree["children"].append(subtree)
            else:
                tree["children"].append({
                    "type": "file",
                    "name": child.name,
                    "size": child.size
                })

        return tree

    # ── 分享操作 ─────────────────────────────────────────────────────

    async def share(
        self,
        virtual_path: str,
        password: Optional[str] = None,
        expire_days: Optional[int] = None
    ) -> tuple[str, Optional[str]]:
        """
        创建分享链接

        Args:
            virtual_path: 虚拟路径
            password: 分享密码
            expire_days: 过期天数

        Returns:
            (分享链接, 分享密码)
        """
        driver_name, driver = self.resolve_driver(virtual_path)
        if not driver:
            raise ValueError(f"无法分享根目录")

        cloud_path = driver.virtual_to_cloud_path(virtual_path)
        return await driver.share(cloud_path, password, expire_days)

    # ── 工具方法 ─────────────────────────────────────────────────────

    def get_mount_points(self) -> list[dict]:
        """获取所有挂载点"""
        mounts = []
        for name in self.drivers.names:
            driver = self.drivers.get(name)
            if not driver:
                continue

            mounts.append({
                "name": name,
                "provider": driver.config.provider.value,
                "enabled": driver.config.enabled,
                "authenticated": driver.is_authenticated,
                "cache_dir": str(self.cache_dir / name)
            })

        return mounts

    async def get_all_quotas(self) -> dict[str, CloudQuota]:
        """获取所有驱动的配额"""
        quotas = {}

        for name in self.drivers.names:
            driver = self.drivers.get(name)
            if not driver or not driver.is_authenticated:
                continue

            try:
                quota = await driver.get_quota()
                quotas[name] = quota
            except Exception:
                pass

        return quotas

    def get_cache_stats(self) -> dict:
        """获取缓存统计"""
        total_entries = len(self._memory_cache)
        expired = sum(1 for c in self._memory_cache.values() if c.is_expired())

        return {
            "total_entries": total_entries,
            "expired": expired,
            "active": total_entries - expired,
            "cache_dir": str(self.cache_dir)
        }


# ============= 单例 =============

_engine: Optional[VirtualCloudEngine] = None


def get_virtual_cloud_engine() -> VirtualCloudEngine:
    """获取虚拟云盘引擎单例"""
    global _engine
    if _engine is None:
        _engine = VirtualCloudEngine()
    return _engine
