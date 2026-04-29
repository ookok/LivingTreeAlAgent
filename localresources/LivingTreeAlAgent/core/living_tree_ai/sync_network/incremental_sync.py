"""
Incremental Sync - 增量同步（Merkle树 + 版本向量）
=================================================

功能：
- 版本向量追踪
- Merkle树差异计算
- 增量数据同步

Author: LivingTreeAI Community
"""

import asyncio
import hashlib
import time
import json
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any, Dict, Set, List
from enum import Enum
from collections import defaultdict


class DataType(Enum):
    """数据类型"""
    CACHE_INDEX = "cache_index"
    CREDIT_RECORD = "credit_record"
    SPECIALTY_INFO = "specialty_info"
    NODE_STATUS = "node_status"
    USER_DATA = "user_data"


@dataclass
class VersionVector:
    """
    版本向量

    记录每个节点对各数据类型的版本号
    格式: {node_id: {data_type: version}}
    """

    _versions: Dict[str, Dict[str, int]] = field(default_factory=lambda: defaultdict(dict))

    def get(self, node_id: str, data_type: DataType) -> int:
        """获取节点的特定数据类型版本"""
        return self._versions.get(node_id, {}).get(data_type.value, 0)

    def set(self, node_id: str, data_type: DataType, version: int):
        """设置版本"""
        self._versions[node_id][data_type.value] = version

    def increment(self, node_id: str, data_type: DataType) -> int:
        """递增版本"""
        current = self.get(node_id, data_type)
        new_version = current + 1
        self._versions[node_id][data_type.value] = new_version
        return new_version

    def compare(self, other: "VersionVector") -> tuple[Set[str], Set[str]]:
        """
        比较版本差异

        Returns:
            (missing, outdated) - 对方有我们无的，对方版本比我们高的
        """
        missing = set()
        outdated = set()

        for node_id, types in other._versions.items():
            for dtype, version in types.items():
                local_version = self._versions.get(node_id, {}).get(dtype, 0)

                if node_id not in self._versions or dtype not in self._versions.get(node_id, {}):
                    missing.add(f"{node_id}:{dtype}")
                elif version > local_version:
                    outdated.add(f"{node_id}:{dtype}")

        return missing, outdated

    def merge(self, other: "VersionVector"):
        """合并版本向量（取最大值）"""
        for node_id, types in other._versions.items():
            for dtype, version in types.items():
                current = self.get(node_id, DataType(dtype))
                if version > current:
                    self.set(node_id, DataType(dtype), version)

    def to_dict(self) -> dict:
        return dict(self._versions)

    @classmethod
    def from_dict(cls, data: dict) -> "VersionVector":
        vv = cls()
        vv._versions = defaultdict(dict, data)
        return vv


class MerkleNode:
    """Merkle树节点"""

    def __init__(self, key: str, value: str, left: Optional["MerkleNode"] = None, right: Optional["MerkleNode"] = None):
        self.key = key
        self.value = value
        self.left = left
        self.right = right
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """计算节点哈希"""
        if self.left is None and self.right is None:
            content = f"leaf:{self.key}:{self.value}"
        else:
            left_hash = self.left.hash if self.left else ""
            right_hash = self.right.hash if self.right else ""
            content = f"inner:{left_hash}:{right_hash}"
        return hashlib.sha256(content.encode()).hexdigest()

    def is_leaf(self) -> bool:
        return self.left is None and self.right is None


class MerkleTree:
    """
    Merkle树

    用于快速比较大量数据的差异
    """

    def __init__(self, data: Optional[dict] = None):
        self.root: Optional[MerkleNode] = None
        self.leaves: Dict[str, MerkleNode] = {}
        if data:
            self.build(data)

    def build(self, data: dict):
        """
        构建Merkle树

        Args:
            data: {key: value} 格式的数据
        """
        if not data:
            self.root = None
            self.leaves = {}
            return

        # 创建叶子节点
        self.leaves = {
            key: MerkleNode(key, str(value))
            for key, value in data.items()
        }

        # 排序键（保证顺序一致）
        sorted_keys = sorted(self.leaves.keys())

        # 构建树
        self.root = self._build_recursive(sorted_keys)

    def _build_recursive(self, keys: List[str]) -> MerkleNode:
        """递归构建树"""
        if not keys:
            return None

        if len(keys) == 1:
            return self.leaves[keys[0]]

        mid = (len(keys) + 1) // 2
        left_keys = keys[:mid]
        right_keys = keys[mid:]

        left_node = self._build_recursive(left_keys)
        right_node = self._build_recursive(right_keys)

        return MerkleNode("", "", left_node, right_node)

    def get_root_hash(self) -> str:
        """获取根哈希"""
        return self.root.hash if self.root else ""

    def get_leaf_hash(self, key: str) -> Optional[str]:
        """获取叶子节点哈希"""
        leaf = self.leaves.get(key)
        return leaf.hash if leaf else None

    def find_different_keys(self, other: "MerkleTree") -> List[str]:
        """
        找出与另一棵树的差异键

        Returns:
            有差异的键列表
        """
        if not self.root or not other.root:
            return list(self.leaves.keys()) + list(other.leaves.keys())

        # 简单实现：比较所有叶子
        different = []

        all_keys = set(self.leaves.keys()) | set(other.leaves.keys())
        for key in all_keys:
            self_hash = self.get_leaf_hash(key)
            other_hash = other.get_leaf_hash(key)
            if self_hash != other_hash:
                different.append(key)

        return different


@dataclass
class DataDigest:
    """数据摘要"""

    data_type: DataType
    version: int
    root_hash: str
    item_count: int
    total_size: int
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "data_type": self.data_type.value,
            "version": self.version,
            "root_hash": self.root_hash,
            "item_count": self.item_count,
            "total_size": self.total_size,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DataDigest":
        return cls(
            data_type=DataType(data["data_type"]),
            version=data["version"],
            root_hash=data["root_hash"],
            item_count=data["item_count"],
            total_size=data["total_size"],
            timestamp=data["timestamp"],
        )


class IncrementalSync:
    """
    增量同步

    特点：
    - 版本向量追踪变化
    - Merkle树快速比较
    - 增量数据传输
    """

    SYNC_BATCH_SIZE = 100  # 每批同步的数据量

    def __init__(
        self,
        node_id: str,
        get_data_func: Optional[Callable[[DataType], dict]] = None,
        apply_data_func: Optional[Callable[[DataType, dict], Awaitable]] = None,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
    ):
        self.node_id = node_id

        # 数据存储
        self.data_stores: Dict[DataType, dict] = {
            dt: {} for dt in DataType
        }

        # 版本向量
        self.version_vector = VersionVector()

        # Merkle树
        self.merkle_trees: Dict[DataType, MerkleTree] = {}

        # 网络函数
        self._get_data = get_data_func or (lambda dt: {})
        self._apply_data = apply_data_func or (lambda dt, d: None)
        self._send_func = send_func

        # 待同步数据
        self.pending_sync: Dict[DataType, list] = defaultdict(list)

    # ========== 数据操作 ==========

    def put(self, data_type: DataType, key: str, value: Any):
        """写入数据"""
        self.data_stores[data_type][key] = value
        self.version_vector.increment(self.node_id, data_type)
        self._rebuild_merkle(data_type)

    def get(self, data_type: DataType, key: str) -> Optional[Any]:
        """读取数据"""
        return self.data_stores[data_type].get(key)

    def delete(self, data_type: DataType, key: str):
        """删除数据"""
        if key in self.data_stores[data_type]:
            del self.data_stores[data_type][key]
            self.version_vector.increment(self.node_id, data_type)
            self._rebuild_merkle(data_type)

    def get_all(self, data_type: DataType) -> dict:
        """获取所有数据"""
        return self.data_stores[data_type].copy()

    def _rebuild_merkle(self, data_type: DataType):
        """重建Merkle树"""
        self.merkle_trees[data_type] = MerkleTree(self.data_stores[data_type])

    # ========== 同步操作 ==========

    async def sync_with_peer(self, peer_id: str) -> dict:
        """
        与指定节点同步差异

        流程：
        1. 交换版本向量
        2. 比较差异
        3. 交换Merkle树根
        4. 获取差异数据
        5. 应用差异
        """
        result = {
            "synced": 0,
            "received": 0,
            "errors": [],
        }

        # 1. 获取对方的版本向量
        peer_vector = await self._get_peer_version_vector(peer_id)
        if peer_vector is None:
            return {"error": "Failed to get peer version vector", **result}

        # 2. 比较差异
        missing, outdated = self.version_vector.compare(peer_vector)

        # 3. 对每个有差异的数据类型处理
        changed_types = set()
        for item in missing | outdated:
            node_id, dtype = item.split(":")
            changed_types.add(dtype)

        for dtype in changed_types:
            data_type = DataType(dtype)

            # 4. 比较Merkle树根
            peer_root = await self._get_peer_merkle_root(peer_id, data_type)
            local_root = self.merkle_trees.get(data_type)

            if local_root is None or peer_root != local_root.get_root_hash():
                # 5. 获取差异数据
                diff_data = await self._get_diff_data(peer_id, data_type)

                # 6. 应用差异
                if diff_data:
                    await self._apply_diff_data(data_type, diff_data)
                    result["received"] += len(diff_data)

        # 7. 发送本地更新给对方
        await self._send_local_updates(peer_id, peer_vector)

        # 8. 更新版本向量
        self.version_vector.merge(peer_vector)

        return result

    async def _get_peer_version_vector(self, peer_id: str) -> Optional[VersionVector]:
        """获取对方的版本向量"""
        if not self._send_func:
            return None

        try:
            response = await self._send_func(peer_id, {
                "type": "sync_request",
                "action": "get_version_vector",
                "node_id": self.node_id,
            })
            return VersionVector.from_dict(response.get("version_vector", {}))
        except Exception:
            return None

    async def _get_peer_merkle_root(self, peer_id: str, data_type: DataType) -> str:
        """获取对方的Merkle根"""
        if not self._send_func:
            return ""

        try:
            response = await self._send_func(peer_id, {
                "type": "sync_request",
                "action": "get_merkle_root",
                "data_type": data_type.value,
                "node_id": self.node_id,
            })
            return response.get("root_hash", "")
        except Exception:
            return ""

    async def _get_diff_data(self, peer_id: str, data_type: DataType) -> dict:
        """获取差异数据"""
        if not self._send_func:
            return {}

        try:
            response = await self._send_func(peer_id, {
                "type": "sync_request",
                "action": "get_diff",
                "data_type": data_type.value,
                "node_id": self.node_id,
            })
            return response.get("data", {})
        except Exception:
            return {}

    async def _send_local_updates(self, peer_id: str, peer_vector: VersionVector):
        """发送本地更新给对方"""
        if not self._send_func:
            return

        # 找出对方没有或过时的数据类型
        for data_type in DataType:
            peer_version = peer_vector.get(peer_id, data_type)
            local_version = self.version_vector.get(self.node_id, data_type)

            if local_version > peer_version:
                # 发送本地数据
                await self._send_func(peer_id, {
                    "type": "sync_response",
                    "action": "push_data",
                    "data_type": data_type.value,
                    "data": self.data_stores[data_type],
                    "version": local_version,
                })

    async def _apply_diff_data(self, data_type: DataType, diff_data: dict):
        """应用差异数据"""
        for key, value in diff_data.items():
            if value is None:
                # 删除标记
                self.data_stores[data_type].pop(key, None)
            else:
                self.data_stores[data_type][key] = value

        self.version_vector.increment(self.node_id, data_type)
        self._rebuild_merkle(data_type)

        # 调用应用回调
        await self._apply_data(data_type, diff_data)

    # ========== 处理同步请求 ==========

    async def handle_sync_request(self, request: dict) -> dict:
        """处理同步请求"""
        action = request.get("action")
        sender = request.get("node_id")

        if action == "get_version_vector":
            return {"version_vector": self.version_vector.to_dict()}

        elif action == "get_merkle_root":
            data_type = DataType(request.get("data_type", "cache_index"))
            merkle = self.merkle_trees.get(data_type)
            return {"root_hash": merkle.get_root_hash() if merkle else ""}

        elif action == "get_diff":
            data_type = DataType(request.get("data_type", "cache_index"))
            merkle = self.merkle_trees.get(data_type)
            if merkle:
                # 返回所有数据（简化实现）
                return {"data": self.data_stores[data_type]}
            return {"data": {}}

        return {}

    async def handle_sync_response(self, response: dict):
        """处理同步响应"""
        action = response.get("action")

        if action == "push_data":
            data_type = DataType(response.get("data_type", "cache_index"))
            data = response.get("data", {})
            await self._apply_diff_data(data_type, data)

    # ========== 工具方法 ==========

    def generate_digest(self, data_type: DataType) -> DataDigest:
        """生成数据摘要"""
        data = self.data_stores[data_type]
        total_size = sum(len(str(v)) for v in data.values())

        merkle = self.merkle_trees.get(data_type)
        root_hash = merkle.get_root_hash() if merkle else ""

        return DataDigest(
            data_type=data_type,
            version=self.version_vector.get(self.node_id, data_type),
            root_hash=root_hash,
            item_count=len(data),
            total_size=total_size,
            timestamp=time.time(),
        )

    def get_all_digests(self) -> List[DataDigest]:
        """获取所有数据类型的摘要"""
        return [self.generate_digest(dt) for dt in DataType]


# 全局单例
_incremental_instance: Optional[IncrementalSync] = None


def get_incremental_sync(node_id: str = "local") -> IncrementalSync:
    """获取增量同步单例"""
    global _incremental_instance
    if _incremental_instance is None:
        _incremental_instance = IncrementalSync(node_id)
    return _incremental_instance