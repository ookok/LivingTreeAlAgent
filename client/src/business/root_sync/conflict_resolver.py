"""
冲突解决器 - Conflict Resolver

支持多种冲突解决策略：
- CRDT 风格自动解决
- 交互式冲突处理
- 冲突历史追踪
"""

import asyncio
import os
import json
import hashlib
import time
import shutil
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import IntEnum

from .models import FileInfo, ConflictStrategy


class ConflictType(IntEnum):
    """冲突类型"""
    NONE = 0
    CONTENT = 1      # 内容冲突
    MODTIME = 2      # 修改时间冲突
    PERMISSION = 3   # 权限冲突
    BOTH_DELETED = 4  # 双方都删除
    DELETED_MODIFIED = 5  # 一方删除，一方修改


@dataclass
class ConflictRecord:
    """冲突记录"""
    file_id: str
    file_name: str

    # 冲突的文件版本
    local_version: FileInfo
    remote_version: FileInfo

    # 元数据
    conflict_type: ConflictType = ConflictType.CONTENT
    detected_at: float = field(default_factory=time.time)
    resolved: bool = False
    resolution: str = ""  # "local" / "remote" / "merged" / "deleted"

    # 冲突文件路径
    local_conflict_path: str = ""
    remote_conflict_path: str = ""


class ConflictResolver:
    """
    冲突解决器

    检测并解决文件同步冲突：
    1. 冲突检测
    2. 自动解决（基于策略）
    3. 交互式解决（用户确认）
    4. 冲突历史
    """

    def __init__(self, storage_dir: str):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 冲突历史
        self._history: Dict[str, List[ConflictRecord]] = {}

        # 回调
        self._on_conflict_detected: Optional[Callable] = None
        self._on_conflict_resolved: Optional[Callable] = None

        # 加载历史
        self._load_history()

    def set_callbacks(self,
                     on_detected: Optional[Callable] = None,
                     on_resolved: Optional[Callable] = None):
        """设置回调"""
        self._on_conflict_detected = on_detected
        self._on_conflict_resolved = on_resolved

    def detect_conflict(self, local: Optional[FileInfo],
                       remote: Optional[FileInfo]) -> Tuple[bool, ConflictType]:
        """
        检测冲突

        Returns:
            (is_conflict, conflict_type)
        """
        if local is None and remote is None:
            return False, ConflictType.NONE

        if local is None and remote is not None:
            # 远程新增，本地无 -> 不是冲突
            return False, ConflictType.NONE

        if local is not None and remote is None:
            # 本地新增，远程无 -> 不是冲突
            return False, ConflictType.NONE

        # 双方都有
        # 检查是否都标记为删除
        if local.size == -1 and remote.size == -1:
            return True, ConflictType.BOTH_DELETED

        # 检查修改时间
        if abs(local.mtime - remote.mtime) > 2:
            return True, ConflictType.MODTIME

        # 检查内容（块哈希）
        if local.blocks != remote.blocks:
            return True, ConflictType.CONTENT

        return False, ConflictType.NONE

    async def resolve(self, record: ConflictRecord,
                    strategy: ConflictStrategy) -> str:
        """
        解决冲突

        Args:
            record: 冲突记录
            strategy: 解决策略

        Returns:
            解决方式: "local" / "remote" / "merged" / "deleted"
        """
        # 保存冲突副本
        await self._save_conflict_copies(record)

        if strategy == ConflictStrategy.LOCAL_WINS:
            result = "local"
        elif strategy == ConflictStrategy.REMOTE_WINS:
            result = "remote"
        elif strategy == ConflictStrategy.NEWER_WINS:
            if record.local_version.mtime > record.remote_version.mtime:
                result = "local"
            else:
                result = "remote"
        elif strategy == ConflictStrategy.KEEP_BOTH:
            # 保留双方版本（已在 _save_conflict_copies 中处理）
            result = "merged"
        else:  # MTIME_SIZE
            # 基于 mtime 和 size 的综合判断
            time_diff = record.local_version.mtime - record.remote_version.mtime
            if abs(time_diff) <= 2:
                # 时间相近，看大小
                if record.local_version.size >= record.remote_version.size:
                    result = "local"
                else:
                    result = "remote"
            else:
                result = "local" if time_diff > 0 else "remote"

        # 更新记录
        record.resolved = True
        record.resolution = result
        self._save_record(record)

        # 触发回调
        if self._on_conflict_resolved:
            await self._on_conflict_resolved(record)

        return result

    async def _save_conflict_copies(self, record: ConflictRecord):
        """保存冲突文件副本"""
        timestamp = int(record.detected_at)
        base_name = record.file_name
        name_without_ext, ext = os.path.splitext(base_name)

        # 本地版本副本
        local_name = f"{name_without_ext}.local-{timestamp}{ext}"
        remote_name = f"{name_without_ext}.remote-{timestamp}{ext}"

        # 获取目录
        if hasattr(record.local_version, 'path'):
            file_dir = os.path.dirname(record.local_version.path)
        else:
            file_dir = self.storage_dir / "conflicts"

        os.makedirs(file_dir, exist_ok=True)

        record.local_conflict_path = os.path.join(file_dir, local_name)
        record.remote_conflict_path = os.path.join(file_dir, remote_name)

        # 实际文件复制将在同步层处理
        # 这里只记录路径

    async def resolve_interactive(self, record: ConflictRecord) -> str:
        """
        交互式解决（需要用户确认）

        返回用户选择
        """
        if self._on_conflict_detected:
            await self._on_conflict_detected(record)

        # 等待用户选择（通过回调设置）
        return "pending"

    async def create_merged_version(self, record: ConflictRecord,
                                   local_data: bytes,
                                   remote_data: bytes) -> bytes:
        """
        合并两个版本

        简单策略：拼接，或基于行合并
        """
        # 简单的三路合并
        # 对于文本文件，可以尝试行级合并
        # 对于二进制文件，只能选择其一

        try:
            local_text = local_data.decode("utf-8")
            remote_text = remote_data.decode("utf-8")

            # 简单策略：使用较新的版本
            if record.local_version.mtime > record.remote_version.mtime:
                return local_data
            else:
                return remote_data

        except UnicodeDecodeError:
            # 二进制文件，选择较大的
            if len(local_data) >= len(remote_data):
                return local_data
            else:
                return remote_data

    def get_conflict_history(self, file_id: Optional[str] = None) -> List[ConflictRecord]:
        """获取冲突历史"""
        if file_id:
            return self._history.get(file_id, [])
        else:
            # 返回所有冲突
            result = []
            for records in self._history.values():
                result.extend(records)
            return sorted(result, key=lambda r: r.detected_at, reverse=True)

    def _save_record(self, record: ConflictRecord):
        """保存冲突记录"""
        if record.file_id not in self._history:
            self._history[record.file_id] = []

        # 检查是否已存在
        for i, existing in enumerate(self._history[record.file_id]):
            if existing.detected_at == record.detected_at:
                self._history[record.file_id][i] = record
                break
        else:
            self._history[record.file_id].append(record)

        self._persist_history()

    def _persist_history(self):
        """持久化历史"""
        history_path = self.storage_dir / "conflict_history.json"

        data = {
            file_id: [
                {
                    "file_id": r.file_id,
                    "file_name": r.file_name,
                    "local_version": r.local_version.to_dict() if r.local_version else None,
                    "remote_version": r.remote_version.to_dict() if r.remote_version else None,
                    "conflict_type": int(r.conflict_type),
                    "detected_at": r.detected_at,
                    "resolved": r.resolved,
                    "resolution": r.resolution,
                    "local_conflict_path": r.local_conflict_path,
                    "remote_conflict_path": r.remote_conflict_path,
                }
                for r in records
            ]
            for file_id, records in self._history.items()
        }

        with open(history_path, "w") as f:
            json.dump(data, f)

    def _load_history(self):
        """加载历史"""
        history_path = self.storage_dir / "conflict_history.json"
        if not history_path.exists():
            return

        try:
            with open(history_path, "r") as f:
                data = json.load(f)

            self._history = {}
            for file_id, records in data.items():
                self._history[file_id] = [
                    ConflictRecord(
                        file_id=r["file_id"],
                        file_name=r["file_name"],
                        local_version=FileInfo.from_dict(r["local_version"]) if r["local_version"] else None,
                        remote_version=FileInfo.from_dict(r["remote_version"]) if r["remote_version"] else None,
                        conflict_type=ConflictType(r.get("conflict_type", 0)),
                        detected_at=r.get("detected_at", 0),
                        resolved=r.get("resolved", False),
                        resolution=r.get("resolution", ""),
                        local_conflict_path=r.get("local_conflict_path", ""),
                        remote_conflict_path=r.get("remote_conflict_path", ""),
                    )
                    for r in records
                ]
        except Exception:
            pass

    def clear_resolved(self, before_timestamp: Optional[float] = None):
        """清理已解决的冲突记录"""
        if before_timestamp is None:
            before_timestamp = time.time() - 86400 * 7  # 默认清理 7 天前

        for file_id in list(self._history.keys()):
            self._history[file_id] = [
                r for r in self._history[file_id]
                if not r.resolved or r.detected_at > before_timestamp
            ]

            if not self._history[file_id]:
                del self._history[file_id]

        self._persist_history()
