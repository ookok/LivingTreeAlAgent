"""
版本控制模块
Version Control Module

实现文件版本管理，支持版本历史和回滚功能
"""

from __future__ import annotations



import time
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class FileVersion:
    """文件版本模型"""
    version_id: str
    file_id: str
    version_number: int
    size: int
    checksum: str
    created_by: str
    created_at: float = field(default_factory=time.time)
    comment: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "version_id": self.version_id,
            "file_id": self.file_id,
            "version_number": self.version_number,
            "size": self.size,
            "checksum": self.checksum,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "comment": self.comment,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FileVersion:
        """从字典创建"""
        return cls(
            version_id=data.get("version_id"),
            file_id=data.get("file_id"),
            version_number=data.get("version_number"),
            size=data.get("size"),
            checksum=data.get("checksum"),
            created_by=data.get("created_by"),
            created_at=data.get("created_at", time.time()),
            comment=data.get("comment", ""),
            metadata=data.get("metadata", {})
        )


class VersionControl:
    """版本控制系统"""

    def __init__(self):
        self.versions: Dict[str, List[FileVersion]] = {}  # {file_id: [versions]}
        self.max_versions = 10  # 每个文件的最大版本数

    def create_version(self, file_id: str, size: int, checksum: str, created_by: str, comment: str = "", metadata: Optional[Dict[str, Any]] = None) -> FileVersion:
        """创建新版本"""
        # 获取当前版本数
        if file_id not in self.versions:
            self.versions[file_id] = []

        version_number = len(self.versions[file_id]) + 1

        # 生成版本ID
        version_id = hashlib.sha256(f"{file_id}:{version_number}:{time.time()}".encode()).hexdigest()

        # 创建版本
        version = FileVersion(
            version_id=version_id,
            file_id=file_id,
            version_number=version_number,
            size=size,
            checksum=checksum,
            created_by=created_by,
            comment=comment,
            metadata=metadata or {}
        )

        # 添加到版本列表
        self.versions[file_id].append(version)

        # 限制版本数量
        if len(self.versions[file_id]) > self.max_versions:
            self.versions[file_id] = self.versions[file_id][-self.max_versions:]

        return version

    def get_version(self, file_id: str, version_number: int) -> Optional[FileVersion]:
        """获取特定版本"""
        if file_id not in self.versions:
            return None

        for version in self.versions[file_id]:
            if version.version_number == version_number:
                return version

        return None

    def get_latest_version(self, file_id: str) -> Optional[FileVersion]:
        """获取最新版本"""
        if file_id not in self.versions or not self.versions[file_id]:
            return None

        return self.versions[file_id][-1]

    def get_all_versions(self, file_id: str) -> List[FileVersion]:
        """获取所有版本"""
        return self.versions.get(file_id, [])

    def delete_version(self, file_id: str, version_number: int) -> bool:
        """删除版本"""
        if file_id not in self.versions:
            return False

        original_length = len(self.versions[file_id])
        self.versions[file_id] = [v for v in self.versions[file_id] if v.version_number != version_number]

        return len(self.versions[file_id]) < original_length

    def delete_file_versions(self, file_id: str) -> bool:
        """删除文件的所有版本"""
        if file_id in self.versions:
            del self.versions[file_id]
            return True
        return False

    def rollback_to_version(self, file_id: str, version_number: int) -> Optional[FileVersion]:
        """回滚到指定版本"""
        # 获取指定版本
        target_version = self.get_version(file_id, version_number)
        if not target_version:
            return None

        # 创建新版本作为回滚版本
        return self.create_version(
            file_id=file_id,
            size=target_version.size,
            checksum=target_version.checksum,
            created_by="system",
            comment=f"Rollback to version {version_number}",
            metadata={"rollback_from": version_number}
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_versions = sum(len(versions) for versions in self.versions.values())
        return {
            "total_files": len(self.versions),
            "total_versions": total_versions,
            "max_versions_per_file": self.max_versions
        }


# 单例
version_control = VersionControl()


def get_version_control() -> VersionControl:
    """获取版本控制系统"""
    return version_control
