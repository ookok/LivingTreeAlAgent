# -*- coding: utf-8 -*-
"""
同步数据类型定义 - Sync Data Types
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, List
from datetime import datetime
import hashlib
import json


class SyncStatus(Enum):
    """同步状态"""
    PENDING = "pending"           # 待同步
    SYNCING = "syncing"          # 同步中
    SYNCED = "synced"            # 已同步
    CONFLICT = "conflict"        # 冲突
    FAILED = "failed"            # 失败


class SyncDataType(Enum):
    """数据类型"""
    SESSION = "session"          # 会话
    KNOWLEDGE = "knowledge"       # 知识库
    SETTINGS = "settings"        # 设置
    SKILL = "skill"              # 技能
    CONTEXT = "context"          # 上下文
    MEMORY = "memory"            # 记忆


class ConflictStrategy(Enum):
    """冲突策略"""
    LAST_WRITE_WINS = "last_write_wins"  # 最后写入优先
    USER_CHOICE = "user_choice"          # 用户选择
    MERGE = "merge"                      # 合并
    KEEP_LOCAL = "keep_local"            # 保留本地
    KEEP_REMOTE = "keep_remote"          # 保留远程


@dataclass
class SyncRecord:
    """同步记录"""
    id: str = ""
    data_type: SyncDataType = SyncDataType.SESSION
    entity_id: str = ""
    content: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    checksum: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    synced_at: Optional[datetime] = None
    status: SyncStatus = SyncStatus.PENDING
    conflict_data: Optional[Dict[str, Any]] = None
    device_id: str = ""
    user_id: str = ""
    
    @staticmethod
    def generate_id(data_type: str, entity_id: str) -> str:
        """生成唯一ID"""
        raw = f"{data_type}:{entity_id}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]
    
    def compute_checksum(self) -> str:
        """计算校验和"""
        content_str = json.dumps(self.content, sort_keys=True, ensure_ascii=False)
        raw = f"{self.id}:{content_str}:{self.version}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
    
    def to_dict(self) -> Dict[str, Any]:
        """转字典"""
        return {
            "id": self.id,
            "data_type": self.data_type.value,
            "entity_id": self.entity_id,
            "content": self.content,
            "version": self.version,
            "checksum": self.checksum,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "synced_at": self.synced_at.isoformat() if self.synced_at else None,
            "status": self.status.value,
            "conflict_data": self.conflict_data,
            "device_id": self.device_id,
            "user_id": self.user_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SyncRecord:
        """从字典创建"""
        return cls(
            id=data.get("id", ""),
            data_type=SyncDataType(data.get("data_type", "session")),
            entity_id=data.get("entity_id", ""),
            content=data.get("content", {}),
            version=data.get("version", 1),
            checksum=data.get("checksum", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            synced_at=datetime.fromisoformat(data["synced_at"]) if data.get("synced_at") else None,
            status=SyncStatus(data.get("status", "pending")),
            conflict_data=data.get("conflict_data"),
            device_id=data.get("device_id", ""),
            user_id=data.get("user_id", ""),
        )


@dataclass
class SyncData:
    """同步数据包"""
    records: List[SyncRecord] = field(default_factory=list)
    total: int = 0
    synced: int = 0
    failed: int = 0
    conflicts: int = 0
    
    def add_record(self, record: SyncRecord):
        """添加记录"""
        self.records.append(record)
        self.total += 1
        if record.status == SyncStatus.SYNCED:
            self.synced += 1
        elif record.status == SyncStatus.CONFLICT:
            self.conflicts += 1
        elif record.status == SyncStatus.FAILED:
            self.failed += 1
    
    def get_pending(self) -> List[SyncRecord]:
        """获取待同步记录"""
        return [r for r in self.records if r.status == SyncStatus.PENDING]


@dataclass
class SyncConflict:
    """同步冲突"""
    record_id: str
    local_data: Dict[str, Any]
    remote_data: Dict[str, Any]
    local_version: int
    remote_version: int
    local_updated_at: datetime
    remote_updated_at: datetime
    strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS
    
    def to_dict(self) -> Dict[str, Any]:
        """转字典"""
        return {
            "record_id": self.record_id,
            "local_data": self.local_data,
            "remote_data": self.remote_data,
            "local_version": self.local_version,
            "remote_version": self.remote_version,
            "local_updated_at": self.local_updated_at.isoformat(),
            "remote_updated_at": self.remote_updated_at.isoformat(),
            "strategy": self.strategy.value,
        }


@dataclass 
class SyncStatistics:
    """同步统计"""
    total_synced: int = 0
    total_conflicts: int = 0
    total_failed: int = 0
    last_sync_at: Optional[datetime] = None
    sync_duration_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转字典"""
        return {
            "total_synced": self.total_synced,
            "total_conflicts": self.total_conflicts,
            "total_failed": self.total_failed,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "sync_duration_ms": self.sync_duration_ms,
        }
