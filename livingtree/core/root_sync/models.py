"""
Root Sync 数据模型 - Syncthing 风格文件同步数据结构

定义 BEP 协议核心数据结构，包括块、文件清单、设备信息等。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import IntEnum
import hashlib
import time


class MessageType(IntEnum):
    """BEP 消息类型"""
    # 内部消息 (不发送)
    HELLO = 1
    INIT = 2
    INDEX = 3
    REQUEST = 4
    RESPONSE = 5
    CLOSE = 6

    # 协议消息
    PING = 20
    PONG = 21
    GET_HELLO = 22
    HELLO_AGAIN = 23
    CLUSTER_CONFIG = 25
    INDEX_UPDATE = 28
    REQUEST_RESPONSE = 30
    DOWNLOAD_PROGRESS = 31


class FileType(IntEnum):
    """文件类型"""
    FILE = 0
    DIRECTORY = 1
    SYMLINK = 2
    _INVALID = 3  # 保留


class ConflictStrategy(IntEnum):
    """冲突解决策略"""
    MTIME_SIZE = 0      # mtime 优先，其次 size
    NEWER_WINS = 1      # 较新者胜出
    KEEP_BOTH = 2       # 保留双方版本
    LOCAL_WINS = 3      # 本地优先
    REMOTE_WINS = 4     # 远程优先


@dataclass
class BEPChunk:
    """BEP 块 - 文件数据分块"""
    chunk_id: str           # 块唯一ID (哈希)
    file_id: str            # 所属文件ID
    offset: int             # 块在文件中的偏移
    size: int               # 块大小
    hash: str               # SHA-256 哈希
    compressed: bool = False  # 是否压缩
    weak_hash: int = 0      # 弱哈希 (用于快速校验)

    @classmethod
    def compute_hash(cls, data: bytes) -> tuple:
        """计算块的强哈希和弱哈希"""
        import struct
        import zlib

        # 弱哈希: ADF 哈希
        a = 0
        for byte in data:
            a = (a + byte) & 0xFFFF
            a = (a * 31) & 0xFFFF

        weak_hash = a

        # 强哈希: SHA-256
        strong_hash = hashlib.sha256(data).hexdigest()

        return strong_hash, weak_hash

    def verify(self, data: bytes) -> bool:
        """验证块数据"""
        h, w = self.compute_hash(data)
        return h == self.hash and w == self.weak_hash


@dataclass
class FileInfo:
    """文件信息"""
    name: str               # 文件名
    size: int               # 文件大小
    mtime: float            # 修改时间
    file_id: str            # 文件唯一ID
    file_type: FileType = FileType.FILE
    symlink_target: str = ""  # 符号链接目标
    block_size: int = 0    # 块大小
    blocks: List[str] = field(default_factory=list)  # 块哈希列表
    permissions: int = 0o644  # 权限

    # 冲突相关
    local_version: int = 0   # 本地版本号
    remote_version: int = 0  # 远程版本号
    is_conflict: bool = False
    conflict_of: Optional[str] = None  # 冲突来源文件ID

    @property
    def is_directory(self) -> bool:
        return self.file_type == FileType.DIRECTORY

    @property
    def is_symlink(self) -> bool:
        return self.file_type == FileType.SYMLINK

    def compute_file_id(self) -> str:
        """基于路径和名称计算文件ID"""
        data = f"{self.name}".encode()
        return hashlib.sha256(data).hexdigest()[:32]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "size": self.size,
            "mtime": self.mtime,
            "file_id": self.file_id,
            "file_type": int(self.file_type),
            "symlink_target": self.symlink_target,
            "block_size": self.block_size,
            "blocks": self.blocks,
            "permissions": self.permissions,
            "local_version": self.local_version,
            "remote_version": self.remote_version,
            "is_conflict": self.is_conflict,
            "conflict_of": self.conflict_of,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileInfo":
        return cls(
            name=data["name"],
            size=data["size"],
            mtime=data["mtime"],
            file_id=data["file_id"],
            file_type=FileType(data.get("file_type", 0)),
            symlink_target=data.get("symlink_target", ""),
            block_size=data.get("block_size", 0),
            blocks=data.get("blocks", []),
            permissions=data.get("permissions", 0o644),
            local_version=data.get("local_version", 0),
            remote_version=data.get("remote_version", 0),
            is_conflict=data.get("is_conflict", False),
            conflict_of=data.get("conflict_of"),
        )


@dataclass
class FileManifest:
    """文件清单 - Syncthing 核心数据结构"""
    folder_id: str                      # 文件夹ID
    device_id: str                      # 设备ID
    file_count: int = 0                 # 文件数
    root_hash: str = ""                 # Merkle 根哈希
    files: Dict[str, FileInfo] = field(default_factory=dict)  # 文件ID -> FileInfo

    # 元数据
    created_at: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)
    sequence: int = 0                   # 序列号

    def add_file(self, file_info: FileInfo):
        """添加文件到清单"""
        self.files[file_info.file_id] = file_info
        self.file_count = len(self.files)
        self._compute_root_hash()
        self.last_update = time.time()
        self.sequence += 1

    def remove_file(self, file_id: str):
        """从清单移除文件"""
        if file_id in self.files:
            del self.files[file_id]
            self.file_count = len(self.files)
            self._compute_root_hash()
            self.last_update = time.time()
            self.sequence += 1

    def _compute_root_hash(self):
        """计算 Merkle 根哈希"""
        if not self.files:
            self.root_hash = ""
            return

        # 对所有块哈希排序后计算 SHA-256
        all_hashes = []
        for f in sorted(self.files.values(), key=lambda x: x.file_id):
            all_hashes.extend(f.blocks)

        if not all_hashes:
            self.root_hash = ""
            return

        data = "|".join(sorted(all_hashes)).encode()
        self.root_hash = hashlib.sha256(data).hexdigest()

    def get_file_ids(self) -> List[str]:
        """获取所有文件ID"""
        return list(self.files.keys())

    def to_dict(self) -> dict:
        return {
            "folder_id": self.folder_id,
            "device_id": self.device_id,
            "file_count": self.file_count,
            "root_hash": self.root_hash,
            "files": {k: v.to_dict() for k, v in self.files.items()},
            "created_at": self.created_at,
            "last_update": self.last_update,
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileManifest":
        files = {k: FileInfo.from_dict(v) for k, v in data.get("files", {}).items()}
        return cls(
            folder_id=data["folder_id"],
            device_id=data["device_id"],
            file_count=data.get("file_count", len(files)),
            root_hash=data.get("root_hash", ""),
            files=files,
            created_at=data.get("created_at", time.time()),
            last_update=data.get("last_update", time.time()),
            sequence=data.get("sequence", 0),
        )


@dataclass
class DeviceInfo:
    """设备信息"""
    device_id: str            # 设备唯一ID (证书哈希)
    name: str                 # 设备名称
    addresses: List[str] = field(default_factory=list)  # 连接地址

    # 证书 (用于验证)
    cert_serial: int = 0
    cert_signature: str = ""

    # 状态
    introduced: bool = False    # 是否已引入
    introduced_by: Optional[str] = None  # 引入者

    # 能力
    max_file_size: int = 100 * 1024 * 1024 * 1024  # 最大文件大小
    compress_threshold: int = 100 * 1024  # 压缩阈值

    # 标志
    is_compatible: bool = True
    is_introducer: bool = False  # 引入者 (可信任设备)

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "addresses": self.addresses,
            "cert_serial": self.cert_serial,
            "cert_signature": self.cert_signature,
            "introduced": self.introduced,
            "introduced_by": self.introduced_by,
            "max_file_size": self.max_file_size,
            "compress_threshold": self.compress_threshold,
            "is_compatible": self.is_compatible,
            "is_introducer": self.is_introducer,
        }


@dataclass
class FolderConfig:
    """文件夹配置"""
    folder_id: str
    path: str                          # 本地路径
    label: str = ""                    # 显示名称

    # 同步选项
    ignore_permissions: bool = False
    ignore_delete: bool = False
    ignore_subfolders: bool = False
    ignore_hidden: bool = False

    # 文件过滤
    ignore_patterns: List[str] = field(default_factory=list)  # 忽略模式
    ignore_paths: List[str] = field(default_factory=list)     # 忽略路径

    # 版本控制
    versioning_enabled: bool = False
    versioning_type: str = "staggered"  # staggered/trashed/linked
    versioning_keep: int = 5            # 保留版本数

    # 冲突解决
    conflict_strategy: ConflictStrategy = ConflictStrategy.MTIME_SIZE

    # 设备
    devices: List[str] = field(default_factory=list)  # 允许的设备ID列表

    # 状态
    is_master: bool = False            # 主设备
    auto_accept: bool = False          # 自动接受变更

    def to_dict(self) -> dict:
        return {
            "folder_id": self.folder_id,
            "path": self.path,
            "label": self.label,
            "ignore_permissions": self.ignore_permissions,
            "ignore_delete": self.ignore_delete,
            "ignore_subfolders": self.ignore_subfolders,
            "ignore_hidden": self.ignore_hidden,
            "ignore_patterns": self.ignore_patterns,
            "ignore_paths": self.ignore_paths,
            "versioning_enabled": self.versioning_enabled,
            "versioning_type": self.versioning_type,
            "versioning_keep": self.versioning_keep,
            "conflict_strategy": int(self.conflict_strategy),
            "devices": self.devices,
            "is_master": self.is_master,
            "auto_accept": self.auto_accept,
        }


@dataclass
class SyncRequest:
    """同步请求"""
    folder_id: str
    file_id: str
    chunk_id: str
    offset: int
    size: int
    compress: bool = True


@dataclass
class SyncResponse:
    """同步响应"""
    folder_id: str
    file_id: str
    chunk_id: str
    offset: int
    data: bytes
    compressed: bool = False


@dataclass
class DownloadProgress:
    """下载进度"""
    folder_id: str
    file_id: str
    total_chunks: int
    completed_chunks: int
    bytes_downloaded: int
    bytes_total: int
    speed_bps: float = 0.0


@dataclass
class ClusterConfig:
    """集群配置"""
    device_id: str
    folders: List[str] = field(default_factory=list)  # 文件夹列表
    introduced: bool = False
    introducer: bool = False
    index_id: int = 0
    max_batch_size: int = 100
    peer_name: str = ""


# 协议常量
PROTOCOL_VERSION = 1
DEFAULT_PORT = 22000
RELAY_PORT = 22067
MAX_BLOCK_SIZE = 1024 * 1024  # 1MB
MIN_BLOCK_SIZE = 1024         # 1KB
COMPRESSION_THRESHOLD = 100 * 1024  # 100KB 以上才压缩
