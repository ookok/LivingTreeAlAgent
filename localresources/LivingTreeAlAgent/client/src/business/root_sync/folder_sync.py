"""
文件夹同步核心 - Folder Sync

负责：
- 本地文件夹扫描
- 文件清单构建
- 远程清单对比
- 差异计算
- 同步执行
"""

import asyncio
import os
import json
import hashlib
import time
import fnmatch
from typing import Dict, List, Optional, Set, Callable, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from .models import (
    FileManifest, FileInfo, FileType, FolderConfig,
    ConflictStrategy, BEPChunk
)
from .chunk_manager import ChunkManager


@dataclass
class SyncDelta:
    """同步差异"""
    # 需要下载的文件
    need_download: List[str] = field(default_factory=list)  # file_ids
    # 需要上传的文件
    need_upload: List[str] = field(default_factory=list)
    # 需要删除的本地文件
    need_delete_local: List[str] = field(default_factory=list)
    # 需要删除的远程文件
    need_delete_remote: List[str] = field(default_factory=list)
    # 冲突文件
    conflicts: List[str] = field(default_factory=list)

    @property
    def has_work(self) -> bool:
        return bool(
            self.need_download or
            self.need_upload or
            self.need_delete_local or
            self.need_delete_remote or
            self.conflicts
        )


class FolderSync:
    """
    文件夹同步核心

    管理单个文件夹的同步逻辑：
    1. 扫描本地文件夹
    2. 构建/更新本地清单
    3. 对比远程清单
    4. 计算差异
    5. 执行同步
    """

    def __init__(self, config: FolderConfig, chunk_manager: ChunkManager):
        self.config = config
        self.chunk_manager = chunk_manager

        # 清单
        self.local_manifest: Optional[FileManifest] = None
        self.remote_manifest: Optional[FileManifest] = None

        # 扫描锁
        self._scanning = False
        self._syncing = False

        # 回调
        self._on_progress: Optional[Callable] = None
        self._on_conflict: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None

    @property
    def folder_id(self) -> str:
        return self.config.folder_id

    @property
    def path(self) -> str:
        return self.config.path

    def set_callbacks(self,
                     on_progress: Optional[Callable] = None,
                     on_conflict: Optional[Callable] = None,
                     on_complete: Optional[Callable] = None):
        """设置回调"""
        self._on_progress = on_progress
        self._on_conflict = on_conflict
        self._on_complete = on_complete

    async def scan_local(self) -> FileManifest:
        """
        扫描本地文件夹，构建本地清单

        忽略规则：
        - ignore_patterns: glob 模式
        - ignore_paths: 精确路径
        - ignore_hidden: 隐藏文件
        - ignore_subfolders: 子文件夹
        """
        if self._scanning:
            raise RuntimeError("正在扫描中")

        self._scanning = True

        try:
            manifest = FileManifest(
                folder_id=self.folder_id,
                device_id="",  # 稍后设置
            )

            base_path = Path(self.path)
            if not base_path.exists():
                return manifest

            await self._scan_directory(manifest, base_path, "")

            self.local_manifest = manifest
            return manifest

        finally:
            self._scanning = False

    async def _scan_directory(self, manifest: FileManifest,
                             dir_path: Path, relative_path: str):
        """递归扫描目录"""
        try:
            for entry in os.scandir(dir_path):
                rel_path = os.path.join(relative_path, entry.name) if relative_path else entry.name

                # 检查忽略规则
                if self._should_ignore(rel_path, entry.is_dir()):
                    continue

                if entry.is_file(follow_symlinks=False):
                    await self._add_file(manifest, entry, rel_path)
                elif entry.is_dir(follow_symlinks=False):
                    # 添加目录
                    file_info = FileInfo(
                        name=entry.name,
                        size=0,
                        mtime=entry.stat().st_mtime,
                        file_id=self._compute_file_id(rel_path),
                        file_type=FileType.DIRECTORY,
                    )
                    manifest.add_file(file_info)

                    # 递归扫描子目录
                    if not self.config.ignore_subfolders:
                        await self._scan_directory(
                            manifest,
                            Path(entry.path),
                            rel_path
                        )

        except PermissionError:
            pass

    async def _add_file(self, manifest: FileManifest,
                      entry: os.DirEntry, rel_path: str):
        """添加文件到清单"""
        try:
            stat = entry.stat()

            # 检查隐藏文件
            if self.config.ignore_hidden and entry.name.startswith('.'):
                return

            # 计算文件ID
            file_id = self._compute_file_id(rel_path)

            # 分块
            blocks = []
            if stat.st_size > 0:
                chunks = await self.chunk_manager.split_file_async(
                    entry.path, file_id
                )
                blocks = [c.chunk_id for c in chunks]

            file_info = FileInfo(
                name=entry.name,
                size=stat.st_size,
                mtime=stat.st_mtime,
                file_id=file_id,
                file_type=FileType.FILE,
                block_size=self.chunk_manager.block_size,
                blocks=blocks,
                permissions=stat.st_mode & 0o777,
            )

            manifest.add_file(file_info)

        except Exception:
            pass

    def _should_ignore(self, path: str, is_dir: bool) -> bool:
        """检查是否应忽略"""
        name = os.path.basename(path)

        # 检查隐藏文件
        if self.config.ignore_hidden and name.startswith('.'):
            return True

        # 检查忽略路径
        if path in self.config.ignore_paths:
            return True

        # 检查 glob 模式
        for pattern in self.config.ignore_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
            if fnmatch.fnmatch(path, pattern):
                return True

        return False

    def _compute_file_id(self, path: str) -> str:
        """计算文件ID"""
        data = f"{self.folder_id}:{path}".encode()
        return hashlib.sha256(data).hexdigest()[:32]

    def compute_delta(self, remote: FileManifest) -> SyncDelta:
        """
        计算与远程清单的差异

        Returns:
            SyncDelta 对象
        """
        if self.local_manifest is None:
            raise RuntimeError("本地清单未初始化")

        delta = SyncDelta()

        local_files = self.local_manifest.files
        remote_files = remote.files

        all_file_ids = set(local_files.keys()) | set(remote_files.keys())

        for file_id in all_file_ids:
            local = local_files.get(file_id)
            remote_file = remote_files.get(file_id)

            if local is None and remote_file is not None:
                # 远程有，本地没有 -> 需要下载
                delta.need_download.append(file_id)

            elif local is not None and remote_file is None:
                # 本地有，远程没有 -> 需要上传（除非配置忽略删除）
                if not self.config.ignore_delete:
                    delta.need_upload.append(file_id)

            elif local is not None and remote_file is not None:
                # 双方都有 -> 检查差异
                diff = self._compare_files(local, remote_file)

                if diff == "download":
                    delta.need_download.append(file_id)
                elif diff == "upload":
                    delta.need_upload.append(file_id)
                elif diff == "conflict":
                    delta.conflicts.append(file_id)

        return delta

    def _compare_files(self, local: FileInfo, remote: FileInfo) -> str:
        """
        比较两个文件

        Returns:
            "same" - 完全相同
            "download" - 远程更新，需要下载
            "upload" - 本地更新，需要上传
            "conflict" - 冲突
        """
        # 检查文件大小
        if local.size != remote.size:
            return self._resolve_conflict(local, remote)

        # 检查 mtime
        local_mtime = local.mtime
        remote_mtime = remote.mtime

        # 允许 2 秒的时间误差
        if abs(local_mtime - remote_mtime) <= 2:
            return "same"

        # 检查块哈希
        if local.blocks == remote.blocks:
            return "same"

        return self._resolve_conflict(local, remote)

    def _resolve_conflict(self, local: FileInfo, remote: FileInfo) -> str:
        """解决冲突"""
        strategy = self.config.conflict_strategy

        if strategy == ConflictStrategy.NEWER_WINS:
            return "download" if remote.mtime > local.mtime else "upload"

        elif strategy == ConflictStrategy.LOCAL_WINS:
            return "upload"

        elif strategy == ConflictStrategy.REMOTE_WINS:
            return "download"

        elif strategy == ConflictStrategy.KEEP_BOTH:
            return "conflict"

        else:  # MTIME_SIZE
            # mtime 优先，其次 size
            if abs(remote.mtime - local.mtime) > 2:
                return "download" if remote.mtime > local.mtime else "upload"
            else:
                return "download" if remote.size > local.size else "upload"

    async def pull_file(self, file_id: str, remote: FileManifest,
                       data_callback: Callable) -> bool:
        """
        从远程拉取文件

        Args:
            file_id: 文件ID
            remote: 远程清单
            data_callback: 数据回调，接收 (file_id, chunk_id, data) 并返回 True 表示成功

        Returns:
            是否成功
        """
        if file_id not in remote.files:
            return False

        file_info = remote.files[file_id]
        if file_info.is_directory:
            return True  # 目录直接创建

        # 获取块
        blocks = []
        for i, block_hash in enumerate(file_info.blocks):
            offset = i * file_info.block_size
            size = min(file_info.block_size, file_info.size - offset)
            blocks.append(BEPChunk(
                chunk_id=block_hash,
                file_id=file_id,
                offset=offset,
                size=size,
                hash=block_hash,
            ))

        # 获取块数据
        for chunk in blocks:
            data = await data_callback(file_id, chunk)
            if data is None:
                return False

            # 保存到块管理器
            await self.chunk_manager.put_chunk(
                chunk.chunk_id, data, file_id, chunk.offset
            )

        return True

    async def push_file(self, file_id: str,
                       data_callback: Callable[[str, BEPChunk], Optional[bytes]]) -> bool:
        """
        推送文件到远程

        Args:
            file_id: 文件ID
            data_callback: 块请求回调

        Returns:
            是否成功
        """
        if self.local_manifest is None or file_id not in self.local_manifest.files:
            return False

        file_info = self.local_manifest.files[file_id]

        # 获取块数据
        for chunk_id in file_info.blocks:
            chunk = BEPChunk(
                chunk_id=chunk_id,
                file_id=file_id,
                offset=0,
                size=0,
                hash=chunk_id,
            )
            data = await self.chunk_manager.get_chunk(chunk_id)
            if data is None:
                return False

            # 发送给远程
            if not await data_callback(file_id, chunk, data):
                return False

        return True

    async def apply_delta(self, delta: SyncDelta,
                         remote: FileManifest,
                         pull_callback: Callable,
                         push_callback: Callable):
        """
        应用同步差异

        Args:
            delta: 同步差异
            remote: 远程清单
            pull_callback: 拉取回调 (file_id, file_info) -> bool
            push_callback: 推送回调 (file_id, file_info) -> bool
        """
        self._syncing = True
        total = len(delta.need_download) + len(delta.need_upload)
        completed = 0

        try:
            # 处理下载
            for file_id in delta.need_download:
                file_info = remote.files.get(file_id)
                if file_info and await pull_callback(file_id, file_info):
                    completed += 1
                    self._report_progress(completed, total)

            # 处理上传
            for file_id in delta.need_upload:
                if self.local_manifest and file_id in self.local_manifest.files:
                    file_info = self.local_manifest.files[file_id]
                    if await push_callback(file_id, file_info):
                        completed += 1
                        self._report_progress(completed, total)

            # 处理冲突
            for file_id in delta.conflicts:
                await self._handle_conflict(file_id, remote)

            # 处理删除
            for file_id in delta.need_delete_local:
                await self._delete_local_file(file_id)

            if self._on_complete:
                self._on_complete()

        finally:
            self._syncing = False

    async def _handle_conflict(self, file_id: str, remote: FileManifest):
        """处理冲突"""
        if self.local_manifest is None:
            return

        local = self.local_manifest.files.get(file_id)
        remote_file = remote.files.get(file_id)

        if not local or not remote_file:
            return

        # 创建冲突副本
        conflict_name = f"{local.name}.conflict-{int(time.time())}"
        conflict_path = os.path.join(self.path, os.path.dirname(local.name), conflict_name)

        # 保存远程版本
        # ... (实现冲突版本保存)

        if self._on_conflict:
            self._on_conflict(file_id, local, remote_file)

    async def _delete_local_file(self, file_id: str):
        """删除本地文件"""
        if self.local_manifest and file_id in self.local_manifest.files:
            file_info = self.local_manifest.files[file_id]
            file_path = os.path.join(self.path, file_info.name)

            try:
                if os.path.exists(file_path):
                    if file_info.is_directory:
                        os.rmdir(file_path)
                    else:
                        os.remove(file_path)

                # 从清单移除
                self.local_manifest.remove_file(file_id)
            except Exception:
                pass

    def _report_progress(self, completed: int, total: int):
        """报告进度"""
        if self._on_progress:
            self._on_progress(completed, total)

    def load_manifest(self, path: str) -> Optional[FileManifest]:
        """加载清单"""
        try:
            with open(path, "r") as f:
                data = json.load(f)
            return FileManifest.from_dict(data)
        except Exception:
            return None

    def save_manifest(self, path: str, manifest: FileManifest):
        """保存清单"""
        with open(path, "w") as f:
            json.dump(manifest.to_dict(), f)
