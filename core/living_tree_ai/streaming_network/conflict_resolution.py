"""
Conflict Resolution - 冲突解决
===============================

功能：
- 乐观并发控制 (OCC)
- 最终一致性
- CRDT 数据结构

Author: LivingTreeAI Community
"""

import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Any, List, Dict, Set
from enum import Enum
from collections import defaultdict


class ConflictType(Enum):
    """冲突类型"""
    NONE = "none"
    CHAT_MERGE = "chat_merge"
    STATE_OVERWRITE = "state_overwrite"
    COUNTER_INCREMENT = "counter_increment"
    TEXT_EDIT = "text_edit"


@dataclass
class CRDTRegister:
    """
    CRDT Register

    Last-Writer-Wins (LWW) 寄存器
    """

    def __init__(self, value: Any = None):
        self.value = value
        self.timestamp = time.time()
        self.node_id = ""

    def set(self, value: Any, timestamp: float, node_id: str):
        """设置值（仅当更新的时间戳更新时）"""
        if timestamp > self.timestamp:
            self.value = value
            self.timestamp = timestamp
            self.node_id = node_id
            return True
        return False

    def merge(self, other: "CRDTRegister") -> bool:
        """合并另一个寄存器"""
        return self.set(other.value, other.timestamp, other.node_id)


@dataclass
class CRDTCounter:
    """
    CRDT Counter

    G-Counter（只增计数器）
    """

    def __init__(self):
        self.counters: Dict[str, int] = defaultdict(int)
        self.total = 0

    def increment(self, node_id: str, delta: int = 1):
        """增加"""
        self.counters[node_id] += delta
        self.total = sum(self.counters.values())

    def merge(self, other: "CRDTCounter"):
        """合并"""
        for node_id, count in other.counters.items():
            old = self.counters.get(node_id, 0)
            if count > old:
                self.counters[node_id] = count
        self.total = sum(self.counters.values())


class OptimisticConflictResolver:
    """
    乐观并发控制冲突解决器

    功能：
    1. 版本追踪
    2. 冲突检测
    3. 自动解决
    """

    def __init__(self, node_id: str):
        self.node_id = node_id

        # 版本追踪
        self.state_versions: Dict[str, int] = {}
        self.pending_updates: Dict[str, dict] = {}

        # CRDT 存储
        self.registers: Dict[str, CRDTRegister] = {}
        self.counters: Dict[str, CRDTCounter] = {}

    def get_version(self, state_key: str) -> int:
        """获取状态版本"""
        return self.state_versions.get(state_key, 0)

    async def apply_state_update(
        self,
        stream_id: str,
        update: dict,
    ) -> bool:
        """
        应用状态更新（乐观并发）

        Returns:
            是否成功应用
        """
        state_key = f"{stream_id}:{update.get('type', 'unknown')}"
        current_version = self.get_version(state_key)
        update_version = update.get("version", 0)

        # 检查版本
        if update_version < current_version:
            # 过时更新，丢弃
            return False

        # 检查冲突
        if update_version == current_version:
            if state_key in self.pending_updates:
                # 有未决更新，需要解决冲突
                return await self._resolve_conflict(state_key, update)

        # 无冲突，应用更新
        self.state_versions[state_key] = update_version + 1
        self.pending_updates[state_key] = update
        return True

    async def _resolve_conflict(
        self,
        state_key: str,
        new_update: dict,
    ) -> bool:
        """解决冲突"""
        pending = self.pending_updates.get(state_key)
        if not pending:
            return True

        conflict_type = self._detect_conflict_type(pending, new_update)

        if conflict_type == ConflictType.CHAT_MERGE:
            # 聊天合并：都保留
            merged = self._merge_chat_updates(pending, new_update)
            new_update["data"]["messages"] = merged
            self.pending_updates[state_key] = new_update
            return True

        elif conflict_type == ConflictType.STATE_OVERWRITE:
            # 状态覆盖：最新者胜
            if new_update.get("timestamp", 0) > pending.get("timestamp", 0):
                self.pending_updates[state_key] = new_update
                return True
            return False

        elif conflict_type == ConflictType.COUNTER_INCREMENT:
            # 计数器合并
            new_count = self._merge_counters(pending, new_update)
            new_update["data"]["count"] = new_count
            self.pending_updates[state_key] = new_update
            return True

        return True

    def _detect_conflict_type(
        self,
        update1: dict,
        update2: dict,
    ) -> ConflictType:
        """检测冲突类型"""
        type1 = update1.get("type")
        type2 = update2.get("type")

        if type1 == "chat" and type2 == "chat":
            return ConflictType.CHAT_MERGE
        elif type1 == "playback" and type2 == "playback":
            return ConflictType.STATE_OVERWRITE
        elif type1 == "like" and type2 == "like":
            return ConflictType.COUNTER_INCREMENT
        elif type1 == "text_edit" and type2 == "text_edit":
            return ConflictType.TEXT_EDIT

        return ConflictType.STATE_OVERWRITE

    def _merge_chat_updates(self, update1: dict, update2: dict) -> List[dict]:
        """合并聊天更新"""
        messages1 = update1.get("data", {}).get("messages", [])
        messages2 = update2.get("data", {}).get("messages", [])
        merged = messages1 + messages2

        # 按时间排序
        merged.sort(key=lambda m: m.get("timestamp", 0))
        return merged

    def _merge_counters(self, update1: dict, update2: dict) -> int:
        """合并计数器"""
        count1 = update1.get("data", {}).get("count", 0)
        count2 = update2.get("data", {}).get("count", 0)
        return count1 + count2

    # ========== CRDT 操作 ==========

    def create_register(self, key: str, initial_value: Any = None) -> CRDTRegister:
        """创建寄存器"""
        reg = CRDTRegister(initial_value)
        self.registers[key] = reg
        return reg

    def create_counter(self, key: str) -> CRDTCounter:
        """创建计数器"""
        counter = CRDTCounter()
        self.counters[key] = counter
        return counter

    def register_set(self, key: str, value: Any, timestamp: Optional[float] = None):
        """寄存器设置"""
        if key not in self.registers:
            self.create_register(key, value)
        ts = timestamp or time.time()
        self.registers[key].set(value, ts, self.node_id)

    def counter_increment(self, key: str, delta: int = 1):
        """计数器增加"""
        if key not in self.counters:
            self.create_counter(key)
        self.counters[key].increment(self.node_id, delta)

    def get_register(self, key: str) -> Optional[CRDTRegister]:
        """获取寄存器"""
        return self.registers.get(key)

    def get_counter(self, key: str) -> Optional[CRDTCounter]:
        """获取计数器"""
        return self.counters.get(key)


class EventualConsistency:
    """
    最终一致性模型

    功能：
    1. 版本向量同步
    2. 差异发现
    3. 增量同步
    """

    def __init__(self, node_id: str):
        self.node_id = node_id

        # 版本向量
        self.version_vectors: Dict[str, Dict[str, int]] = defaultdict(dict)

        # 待同步数据
        self.pending_sync: Dict[str, list] = defaultdict(list)

    def get_version_vector(self, key: str) -> Dict[str, int]:
        """获取版本向量"""
        return self.version_vectors.get(key, {}).copy()

    def increment_version(self, key: str, node_id: Optional[str] = None):
        """递增版本"""
        nid = node_id or self.node_id
        current = self.version_vectors[key].get(nid, 0)
        self.version_vectors[key][nid] = current + 1

    def compare_vectors(
        self,
        key: str,
        other: Dict[str, int],
    ) -> tuple[Set[str], Set[str]]:
        """
        比较版本向量

        Returns:
            (missing_in_local, missing_in_remote)
        """
        local = self.version_vectors.get(key, {})

        missing_local = set()  # 对方有本地无
        missing_remote = set()  # 本地有对方无

        # 检查对方有本地无的
        for node_id, version in other.items():
            local_version = local.get(node_id, 0)
            if version > local_version:
                missing_local.add(node_id)

        # 检查本地有对方无的
        for node_id, version in local.items():
            remote_version = other.get(node_id, 0)
            if version > remote_version:
                missing_remote.add(node_id)

        return missing_local, missing_remote

    async def sync_with_peer(
        self,
        peer_id: str,
        key: str,
        get_peer_data_func: Optional[callable] = None,
    ) -> dict:
        """
        与对端同步

        Args:
            peer_id: 对端ID
            key: 状态键
            get_peer_data_func: 获取对端数据的函数

        Returns:
            同步结果
        """
        result = {
            "sent": 0,
            "received": 0,
            "conflicts": 0,
        }

        if not get_peer_data_func:
            return result

        # 获取对端版本向量
        peer_vector = await get_peer_data_func(peer_id, key, "version_vector")
        if not peer_vector:
            return result

        # 比较差异
        missing_local, missing_remote = self.compare_vectors(key, peer_vector)

        # 拉取本地缺失的
        for node_id in missing_local:
            data = await get_peer_data_func(peer_id, key, f"node_{node_id}")
            if data:
                self.pending_sync[key].append(data)
                result["received"] += 1

        # 推送本地缺失的
        for node_id in missing_remote:
            data = self._get_local_data(key, node_id)
            if data:
                await self._send_to_peer(peer_id, key, data)
                result["sent"] += 1

        return result

    def _get_local_data(self, key: str, node_id: str) -> Optional[dict]:
        """获取本地数据"""
        # 简化实现
        return None

    async def _send_to_peer(self, peer_id: str, key: str, data: dict):
        """发送数据到对端"""
        pass


# 全局单例
_conflict_instance: Optional[OptimisticConflictResolver] = None


def get_conflict_resolver(node_id: str = "local") -> OptimisticConflictResolver:
    """获取冲突解决器单例"""
    global _conflict_instance
    if _conflict_instance is None:
        _conflict_instance = OptimisticConflictResolver(node_id)
    return _conflict_instance