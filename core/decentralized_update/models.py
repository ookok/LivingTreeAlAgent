# models.py — P2P 去中心化更新系统数据模型

"""
数据模型定义
==============

包含：
- 枚举类型（节点状态、更新阶段、消息类型等）
- 数据类（版本信息、节点信息、分片信息等）
- 工具函数
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 枚举类型
# ═══════════════════════════════════════════════════════════════════════════════


class NodeState(Enum):
    """节点状态"""
    OFFLINE = "offline"           # 离线
    ONLINE = "online"             # 在线
    UPDATING = "updating"         # 正在更新
    Distributing = "distributing"  # 正在分发
    SYNCING = "syncing"           # 正在同步


class UpdateStage(Enum):
    """更新阶段"""
    IDLE = "idle"                         # 空闲
    CHECKING = "checking"                  # 检查中
    DOWNLOADING = "downloading"            # 下载中
    VERIFYING = "verifying"                # 验证中
    APPLYING = "applying"                  # 应用中
    ROLLBACK = "rollback"                  # 回滚中
    COMPLETED = "completed"                # 完成


class MessageType(Enum):
    """消息类型"""
    # 发现层消息
    ANNOUNCE = "announce"                 # 节点宣告（广播版本升级）
    QUERY = "query"                        # 版本查询
    RESPONSE = "response"                  # 查询响应
    PING = "ping"                          # 心跳
    PONG = "pong"                          # 心跳响应

    # 分发层消息
    HAVE = "have"                          # 拥有分片宣告
    REQUEST = "request"                    # 请求分片
    DATA = "data"                           # 分片数据
    CANCEL = "cancel"                      # 取消请求

    # 验证层消息
    ENDORSEMENT = "endorsement"            # 背书签名
    CHALLENGE = "challenge"                 # 挑战验证
    PROOF = "proof"                         # 证明响应


class ReputationLevel(Enum):
    """信誉等级"""
    UNTRUSTED = 0      # 不可信 (< 20分)
    NEWCOMER = 1       # 新加入 (20-50分)
    TRUSTED = 2        # 可信 (50-80分)
    HIGHLY_TRUSTED = 3 # 高可信 (80-95分)
    AUTHORITY = 4      # 权威 (> 95分)


class UpdateStrategy(Enum):
    """更新策略"""
    AUTO = "auto"           # 自动更新
    MANUAL = "manual"        # 手动更新
    SCHEDULED = "scheduled"  # 定时更新
    NOTIFY = "notify"        # 仅通知


class SignatureType(Enum):
    """签名类型"""
    DEVELOPER = "developer"           # 开发者签名
    ENDORSEMENT = "endorsement"       # 背书签名
    COMMUNITY = "community"           # 社区共识签名


# ═══════════════════════════════════════════════════════════════════════════════
# 数据类
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class VersionInfo:
    """版本信息"""
    version: str                           # 版本号 (如 "1.2.0")
    version_code: int                      # 版本数值 (用于比较)
    checksum: str                          # 完整包 SHA256
    merkle_root: str                       # Merkle 树根
    delta_from: Optional[str] = None       # 增量更新的起始版本
    delta_checksum: Optional[str] = None   # 增量包 SHA256
    delta_size: int = 0                    # 增量包大小 (字节)
    full_size: int = 0                     # 完整包大小 (字节)
    release_time: float = 0                # 发布时间戳
    min_version: Optional[str] = None       # 最低支持版本
    breaking: bool = False                  # 是否破坏性更新
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def version_tuple(self) -> tuple:
        """返回版本元组用于比较"""
        return tuple(int(x) for x in self.version.lstrip('v').split('.'))

    def is_newer_than(self, other: VersionInfo) -> bool:
        """判断是否比另一个版本更新"""
        return self.version_code > other.version_code


@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str                           # 节点唯一标识
    version: str                            # 当前版本
    state: NodeState = NodeState.ONLINE     # 状态
    last_seen: float = 0                    # 最后活跃时间
    endpoint: Optional[str] = None           # 网络端点 (host:port)
    reputation_score: float = 50.0           # 信誉分 (0-100)
    reputation_level: ReputationLevel = ReputationLevel.TRUSTED
    bandwidth_score: float = 50.0           # 带宽评分 (0-100)
    stability_score: float = 50.0           # 稳定性评分 (0-100)
    successful_distributes: int = 0         # 成功分发次数
    total_distributes: int = 0              # 总分发次数
    region: Optional[str] = None            # 地区
    is_seed: bool = False                   # 是否为种子节点
    capabilities: Set[str] = field(default_factory=set)  # 能力集
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.last_seen == 0:
            self.last_seen = time.time()

    @property
    def online_duration(self) -> float:
        """在线时长（秒）"""
        return time.time() - self.last_seen

    def update_reputation(self, success: bool, delta: float = 5.0):
        """更新信誉分"""
        if success:
            self.reputation_score = min(100, self.reputation_score + delta)
            self.successful_distributes += 1
        else:
            self.reputation_score = max(0, self.reputation_score - delta * 2)
        self.total_distributes += 1

        # 更新等级
        if self.reputation_score < 20:
            self.reputation_level = ReputationLevel.UNTRUSTED
        elif self.reputation_score < 50:
            self.reputation_level = ReputationLevel.NEWCOMER
        elif self.reputation_score < 80:
            self.reputation_level = ReputationLevel.TRUSTED
        elif self.reputation_score < 95:
            self.reputation_level = ReputationLevel.HIGHLY_TRUSTED
        else:
            self.reputation_level = ReputationLevel.AUTHORITY


@dataclass
class ChunkInfo:
    """分片信息"""
    chunk_id: str                           # 分片ID
    hash: str                               # 分片哈希
    size: int                               # 分片大小
    index: int                              # 分片索引
    total_chunks: int                       # 总分片数


@dataclass
class UpdateManifest:
    """更新清单"""
    app_id: str                             # 应用ID
    current_version: str                     # 当前版本
    latest_version: str                     # 最新版本
    update_channel: str = "stable"          # 更新通道 (stable/beta/nightly)
    versions: List[VersionInfo] = field(default_factory=list)
    endorsed_signatures: List[EndorsementSignature] = field(default_factory=list)
    merkle_tree: Dict[str, str] = field(default_factory=dict)  # hash -> chunk_hash
    created_at: float = 0

    def __post_init__(self):
        if self.created_at == 0:
            self.created_at = time.time()

    def get_version(self, version: str) -> Optional[VersionInfo]:
        """获取指定版本信息"""
        for v in self.versions:
            if v.version == version:
                return v
        return None

    def get_min_delta_version(self, from_version: str) -> Optional[VersionInfo]:
        """获取从指定版本到最新版本的最小增量"""
        from_tuple = tuple(int(x) for x in from_version.lstrip('v').split('.'))
        candidates = []

        for v in self.versions:
            if v.is_newer_than(VersionInfo(version=from_version, version_code=0, checksum="")):
                if v.delta_from and v.delta_from == from_version:
                    candidates.append(v)

        if candidates:
            return min(candidates, key=lambda x: x.delta_size)
        return None


@dataclass
class EndorsementSignature:
    """背书签名"""
    signer_id: str                           # 签名者ID
    signature_type: SignatureType             # 签名类型
    version: str                              # 签名版本
    signature: str                            # 签名数据
    timestamp: float = 0                      # 签名时间
    merkle_proof: List[str] = field(default_factory=list)  # Merkle 证明路径

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()


@dataclass
class UpdateTask:
    """更新任务"""
    task_id: str                             # 任务ID
    from_version: str                         # 起始版本
    to_version: str                           # 目标版本
    stage: UpdateStage = UpdateStage.IDLE     # 当前阶段
    progress: float = 0                       # 进度 (0-1)
    downloaded_chunks: Set[str] = field(default_factory(set))  # 已下载分片ID
    total_chunks: int = 0                     # 总分片数
    speed_bps: float = 0                      # 下载速度 (字节/秒)
    remaining_time: float = 0                 # 剩余时间 (秒)
    error: Optional[str] = None               # 错误信息
    sources: List[NodeInfo] = field(default_factory=list)  # 下载源节点
    created_at: float = 0
    updated_at: float = 0

    def __post_init__(self):
        if self.created_at == 0:
            self.created_at = time.time()
        if self.updated_at == 0:
            self.updated_at = time.time()

    @property
    def chunk_progress(self) -> float:
        """分片进度"""
        if self.total_chunks == 0:
            return 0
        return len(self.downloaded_chunks) / self.total_chunks


@dataclass
class PropagationRecord:
    """传播记录（用于波纹扩散算法）"""
    origin_node: str                          # 原始广播节点
    target_version: str                       # 目标版本
    ttl: int                                  # 剩余TTL
    depth: int                                # 当前深度
    timestamp: float = 0                       # 传播时间

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()


# ═══════════════════════════════════════════════════════════════════════════════
# 消息类
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ProtocolMessage:
    """协议消息基类"""
    msg_type: MessageType
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    ttl: int = 3                             # 默认 TTL
    hop: int = 0                             # 跳数


@dataclass
class AnnounceMessage(ProtocolMessage):
    """宣告消息 - 广播版本升级"""
    version_info: VersionInfo = None
    announcer: NodeInfo = None
    merkle_proof: List[str] = field(default_factory=list)


@dataclass
class QueryMessage(ProtocolMessage):
    """查询消息"""
    app_id: str = ""
    current_version: str = ""
    target_version: Optional[str] = None


@dataclass
class ResponseMessage(ProtocolMessage):
    """响应消息"""
    request_id: str = ""
    versions: List[VersionInfo] = field(default_factory=list)
    nodes: List[NodeInfo] = field(default_factory=list)


@dataclass
class HaveMessage(ProtocolMessage):
    """拥有分片宣告"""
    chunk_ids: List[str] = field(default_factory=list)


@dataclass
class RequestChunkMessage(ProtocolMessage):
    """请求分片"""
    chunk_id: str = ""
    preferred_nodes: List[str] = field(default_factory=list)


@dataclass
class ChunkDataMessage(ProtocolMessage):
    """分片数据"""
    chunk: ChunkInfo = None
    data: bytes = b""


@dataclass
class EndorsementMessage(ProtocolMessage):
    """背书签名消息"""
    signature: EndorsementSignature = None


# ═══════════════════════════════════════════════════════════════════════════════
# Merkle 树工具
# ═══════════════════════════════════════════════════════════════════════════════


class MerkleTree:
    """Merkle 树实现"""

    def __init__(self, chunks: List[bytes]):
        self.chunks = chunks
        self.hashes = [self._hash(c) for c in chunks]
        self.tree = self._build_tree()

    @staticmethod
    def _hash(data: bytes) -> str:
        """计算 SHA256 哈希"""
        return hashlib.sha256(data).hexdigest()

    def _build_tree(self) -> List[List[str]]:
        """构建 Merkle 树"""
        if not self.hashes:
            return []

        tree = [self.hashes[:]]
        current = self.hashes[:]

        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                left = current[i]
                right = current[i + 1] if i + 1 < len(current) else current[i]
                next_level.append(self._hash((left + right).encode()))
            tree.append(next_level)
            current = next_level

        return tree

    @property
    def root(self) -> str:
        """获取根哈希"""
        if not self.tree:
            return ""
        return self.tree[-1][0]

    def get_proof(self, index: int) -> List[str]:
        """获取默克尔证明路径"""
        if index < 0 or index >= len(self.hashes):
            return []

        proof = []
        idx = index

        for level in range(len(self.tree) - 1):
            sibling_idx = idx + 1 if idx % 2 == 0 else idx - 1
            if sibling_idx < len(self.tree[level]):
                proof.append(self.tree[level][sibling_idx])
            else:
                proof.append(self.tree[level][idx])
            idx = idx // 2

        return proof

    @staticmethod
    def verify_proof(root: str, leaf: str, proof: List[str]) -> bool:
        """验证默克尔证明"""
        current = leaf
        for sibling in proof:
            current = MerkleTree._hash((current + sibling).encode())
        return current == root


# ═══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════════


def generate_task_id() -> str:
    """生成任务ID"""
    return f"task_{uuid.uuid4().hex[:12]}"


def generate_node_id() -> str:
    """生成节点ID"""
    return f"node_{uuid.uuid4().hex[:16]}"


def calculate_version_code(version: str) -> int:
    """计算版本数值用于比较"""
    parts = version.lstrip('v').split('.')
    code = 0
    for i, part in enumerate(parts[:3]):  # 最多3位
        try:
            code += int(part) * (1000 ** (2 - i))
        except ValueError:
            code += int(part.split('-')[0]) * (1000 ** (2 - i))
    return code


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def format_speed(bytes_per_second: float) -> str:
    """格式化速度"""
    return f"{format_size(int(bytes_per_second))}/s"


def format_duration(seconds: float) -> str:
    """格式化时长"""
    if seconds < 60:
        return f"{int(seconds)}秒"
    elif seconds < 3600:
        return f"{int(seconds // 60)}分{int(seconds % 60)}秒"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}小时{minutes}分"
