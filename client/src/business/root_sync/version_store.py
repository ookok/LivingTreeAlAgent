"""
版本存储 - Version Store

支持多种版本控制策略：
- Staggered: 按时限保留版本
- Trash: 回收站模式
- Linked: 软链接历史版本
"""

import asyncio
import os
import json
import time
import shutil
import hashlib
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import IntEnum


class VersioningType(IntEnum):
    """版本控制类型"""
    NONE = 0
    STAGGERED = 1   # 阶梯版本
    TRASHED = 2     # 回收站
    LINKED = 3      # 软链接


@dataclass
class VersionEntry:
    """版本条目"""
    version_id: str
    file_id: str
    file_name: str

    # 版本信息
    size: int
    mtime: float
    created_at: float

    # 文件路径
    path: str

    # 版本元数据
    version_number: int = 0
    is_deleted: bool = False

    def to_dict(self) -> dict:
        return {
            "version_id": self.version_id,
            "file_id": self.file_id,
            "file_name": self.file_name,
            "size": self.size,
            "mtime": self.mtime,
            "created_at": self.created_at,
            "path": self.path,
            "version_number": self.version_number,
            "is_deleted": self.is_deleted,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VersionEntry":
        return cls(**data)


@dataclass
class StaggeredConfig:
    """阶梯版本配置"""
    # 保留策略: {max_age: max_versions}
    # 例: {3600: 5, 86400: 4, 2592000: 3} = 1小时内保留5个, 1-3天保留4个, 3-30天保留3个
    intervals: Dict[int, int] = field(default_factory=lambda: {
        3600: 5,       # 1 小时内每小时一个
        86400: 4,      # 1-3 天每天一个
        2592000: 3,    # 3-30 天每周一个
    })


class VersionStore:
    """
    版本存储管理器

    支持：
    1. 阶梯版本 (Staggered)
    2. 回收站 (Trashed)
    3. 软链接版本 (Linked)
    """

    def __init__(self, storage_dir: str, versioning_type: VersioningType = VersioningType.STAGGERED):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.versioning_type = versioning_type

        # 版本目录
        self.versions_dir = self.storage_dir / "versions"
        self.versions_dir.mkdir(exist_ok=True)

        # 版本索引
        self._versions: Dict[str, List[VersionEntry]] = {}

        # 配置
        self._staggered_config = StaggeredConfig()

        # 加载索引
        self._load_index()

    def set_staggered_config(self, config: StaggeredConfig):
        """设置阶梯版本配置"""
        self._staggered_config = config

    async def add_version(self, file_id: str, file_name: str,
                         source_path: str, size: int, mtime: float):
        """
        添加版本

        Args:
            file_id: 文件ID
            file_name: 文件名
            source_path: 源文件路径
            size: 文件大小
            mtime: 修改时间
        """
        version_id = self._generate_version_id(file_id, mtime)
        version_number = len(self._versions.get(file_id, [])) + 1

        # 确定版本存储路径
        version_subdir = self.versions_dir / file_id[:2]
        version_subdir.mkdir(exist_ok=True)
        version_path = version_subdir / f"{version_id}.ver"

        # 复制文件
        try:
            shutil.copy2(source_path, version_path)
        except Exception:
            return None

        # 创建版本条目
        entry = VersionEntry(
            version_id=version_id,
            file_id=file_id,
            file_name=file_name,
            size=size,
            mtime=mtime,
            created_at=time.time(),
            path=str(version_path),
            version_number=version_number,
        )

        # 添加到索引
        if file_id not in self._versions:
            self._versions[file_id] = []
        self._versions[file_id].append(entry)

        # 应用版本保留策略
        await self._apply_retention_policy(file_id)

        # 保存索引
        self._save_index()

        return entry

    async def _apply_retention_policy(self, file_id: str):
        """应用版本保留策略"""
        if self.versioning_type == VersioningType.STAGGERED:
            await self._apply_staggered_policy(file_id)
        elif self.versioning_type == VersioningType.TRASHED:
            await self._apply_trashed_policy(file_id)
        elif self.versioning_type == VersioningType.LINKED:
            await self._apply_linked_policy(file_id)

    async def _apply_staggered_policy(self, file_id: str):
        """阶梯版本保留策略"""
        if file_id not in self._versions:
            return

        versions = self._versions[file_id]
        if len(versions) <= 1:
            return

        # 按时间分组
        now = time.time()
        to_delete = []

        for entry in versions:
            age = now - entry.created_at

            # 找到适用的时间段
            max_age = max(self._staggered_config.intervals.keys())
            for interval, max_versions in sorted(self._staggered_config.intervals.items()):
                if age <= interval:
                    max_age = interval
                    break

            # 检查是否超出保留数
            same_interval = [
                v for v in versions
                if abs(v.created_at - entry.created_at) <= max_age
                and v.version_id != entry.version_id
            ]

            if len(same_interval) >= self._staggered_config.intervals.get(max_age, 1):
                to_delete.append(entry.version_id)

        # 删除多余版本
        for vid in to_delete:
            await self._delete_version(file_id, vid)

    async def _apply_trashed_policy(self, file_id: str):
        """回收站策略 - 保留所有版本直到手动清理"""
        pass

    async def _apply_linked_policy(self, file_id: str):
        """软链接策略"""
        pass

    async def _delete_version(self, file_id: str, version_id: str):
        """删除版本"""
        if file_id not in self._versions:
            return

        entry_to_delete = None
        for entry in self._versions[file_id]:
            if entry.version_id == version_id:
                entry_to_delete = entry
                break

        if not entry_to_delete:
            return

        # 删除文件
        try:
            if os.path.exists(entry_to_delete.path):
                os.remove(entry_to_delete.path)
        except Exception:
            pass

        # 从索引移除
        self._versions[file_id] = [
            v for v in self._versions[file_id]
            if v.version_id != version_id
        ]

        if not self._versions[file_id]:
            del self._versions[file_id]

    def get_versions(self, file_id: str) -> List[VersionEntry]:
        """获取文件的所有版本"""
        return self._versions.get(file_id, [])

    async def restore_version(self, version_id: str,
                           target_path: str) -> bool:
        """恢复指定版本"""
        # 找到版本
        entry = None
        for versions in self._versions.values():
            for v in versions:
                if v.version_id == version_id:
                    entry = v
                    break
            if entry:
                break

        if not entry or not os.path.exists(entry.path):
            return False

        try:
            shutil.copy2(entry.path, target_path)
            return True
        except Exception:
            return False

    async def delete_file_versions(self, file_id: str):
        """删除文件的所有版本"""
        if file_id not in self._versions:
            return

        for entry in self._versions[file_id]:
            try:
                if os.path.exists(entry.path):
                    os.remove(entry.path)
            except Exception:
                pass

        del self._versions[file_id]
        self._save_index()

    def _generate_version_id(self, file_id: str, mtime: float) -> str:
        """生成版本ID"""
        data = f"{file_id}:{mtime}:{time.time()}".encode()
        return hashlib.sha256(data).hexdigest()[:24]

    def _save_index(self):
        """保存版本索引"""
        index_path = self.storage_dir / "version_index.json"

        data = {
            file_id: [v.to_dict() for v in versions]
            for file_id, versions in self._versions.items()
        }

        with open(index_path, "w") as f:
            json.dump(data, f)

    def _load_index(self):
        """加载版本索引"""
        index_path = self.storage_dir / "version_index.json"
        if not index_path.exists():
            return

        try:
            with open(index_path, "r") as f:
                data = json.load(f)

            self._versions = {
                file_id: [VersionEntry.from_dict(v) for v in versions]
                for file_id, versions in data.items()
            }
        except Exception:
            pass

    def get_stats(self) -> dict:
        """获取统计信息"""
        total_versions = sum(len(v) for v in self._versions.values())
        total_size = sum(
            sum(e.size for e in versions)
            for versions in self._versions.values()
        )

        return {
            "total_files": len(self._versions),
            "total_versions": total_versions,
            "total_size": total_size,
            "versioning_type": self.versioning_type.name,
        }
