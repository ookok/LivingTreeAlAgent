"""
状态数据库 (State DB)
=====================

基于 SQLite + CRDT 实现多设备状态同步

核心理念：本地即真理，拥有最终解释权

CRDT 实现：
- LWW-Register (Last-Write-Wins): 最后写入优先，用于配置值
- G-Counter: 只增计数器，用于版本号
- OR-Set: 可添加/删除的集合，用于标签等

Author: Hermes Desktop AI Assistant
"""

import os
import json
import time
import sqlite3
import hashlib
import logging
import threading
import uuid
from typing import Optional, Dict, Any, List, Tuple, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================================
# CRDT 实现
# ============================================================

class CRDTType(Enum):
    """CRDT类型"""
    LWW_REGISTER = "lww_register"    # 最后写入优先
    G_COUNTER = "g_counter"          # 只增计数器
    OR_SET = "or_set"                # 可添加删除集合
    LWW_MAP = "lww_map"               # LWW键值映射


@dataclass
class CRDTOperation:
    """CRDT操作"""
    op_id: str           # 操作ID (uuid)
    op_type: str         # 操作类型: SET, DELETE, INCREMENT, ADD, REMOVE
    key: str             # 操作的键
    value: Any           # 值
    timestamp: float     # 逻辑时间戳
    device_id: str       # 设备ID
    vector_clock: Dict[str, int] = field(default_factory=dict)  # 向量时钟


@dataclass
class LWWRegister:
    """最后写入优先寄存器"""
    value: Any = None
    timestamp: float = 0.0
    device_id: str = ""


class LWWRegisterDB:
    """
    LWW寄存器数据库实现

    规则：timestamp大的赢，timestamp相同则device_id字典序大的赢
    """

    def __init__(self):
        self._data: Dict[str, LWWRegister] = {}

    def set(self, key: str, value: Any, timestamp: float, device_id: str) -> bool:
        """
        设置值

        Returns:
            是否更新了值
        """
        current = self._data.get(key)

        if current is None:
            self._data[key] = LWWRegister(value, timestamp, device_id)
            return True

        # 比较：timestamp大的赢，相同则device_id大的赢
        if (timestamp > current.timestamp or
            (timestamp == current.timestamp and device_id > current.device_id)):
            self._data[key] = LWWRegister(value, timestamp, device_id)
            return True

        return False

    def get(self, key: str) -> Any:
        """获取值"""
        reg = self._data.get(key)
        return reg.value if reg else None

    def merge(self, other: 'LWWRegisterDB') -> int:
        """
        合并另一个数据库

        Returns:
            更新的键数量
        """
        updates = 0
        for key, reg in other._data.items():
            if self.set(key, reg.value, reg.timestamp, reg.device_id):
                updates += 1
        return updates

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.value for k, v in self._data.items()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LWWRegisterDB':
        db = cls()
        for k, v in data.items():
            if isinstance(v, dict) and 'value' in v:
                db._data[k] = LWWRegister(**v)
            else:
                db._data[k] = LWWRegister(v, 0, "")
        return db


class GCounter:
    """只增计数器"""

    def __init__(self):
        self._counters: Dict[str, int] = defaultdict(int)  # device_id -> count

    def increment(self, device_id: str, amount: int = 1) -> int:
        """递增"""
        self._counters[device_id] += amount
        return self._counters[device_id]

    def value(self) -> int:
        """获取总值"""
        return sum(self._counters.values())

    def merge(self, other: 'GCounter'):
        """合并"""
        for device_id, count in other._counters.items():
            self._counters[device_id] = max(self._counters[device_id], count)

    def to_dict(self) -> Dict[str, int]:
        return dict(self._counters)

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> 'GCounter':
        counter = cls()
        counter._counters = defaultdict(int, data)
        return counter


class ORSet:
    """
    可添加删除集合

    规则：元素要么存在(add多于remove)，要么不存在
    """

    def __init__(self):
        self._adds: Dict[str, Dict[str, float]] = {}  # element -> {tag -> timestamp}
        self._removes: Set[str] = set()  # 已删除的tag

    def add(self, element: str, tag: str, timestamp: float) -> bool:
        """添加元素"""
        if element not in self._adds:
            self._adds[element] = {}
        self._adds[element][tag] = timestamp
        return True

    def remove(self, element: str) -> bool:
        """删除元素（标记）"""
        if element in self._adds:
            # 标记所有标签为已删除
            for tag in self._adds[element]:
                self._removes.add(tag)
            return True
        return False

    def contains(self, element: str) -> bool:
        """检查元素是否存在"""
        if element not in self._adds:
            return False

        for tag in self._adds[element]:
            if tag not in self._removes:
                return True
        return False

    def merge(self, other: 'ORSet') -> int:
        """合并"""
        updates = 0

        for element, tags in other._adds.items():
            if element not in self._adds:
                self._adds[element] = {}
            for tag, ts in tags.items():
                if tag not in self._adds[element]:
                    updates += 1
                self._adds[element][tag] = ts

        for tag in other._removes:
            if tag not in self._removes:
                self._removes.add(tag)
                updates += 1

        return updates

    def to_list(self) -> List[str]:
        """转为列表"""
        result = []
        for element in self._adds:
            if self.contains(element):
                result.append(element)
        return result

    def to_dict(self) -> dict:
        return {
            "adds": self._adds,
            "removes": list(self._removes)
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ORSet':
        s = cls()
        s._adds = {k: v for k, v in data.get("adds", {}).items()}
        s._removes = set(data.get("removes", []))
        return s


# ============================================================
# 向量时钟
# ============================================================

class VectorClock:
    """
    向量时钟

    用于跟踪事件的偏序关系
    """

    def __init__(self):
        self._clock: Dict[str, int] = {}  # device_id -> counter

    def increment(self, device_id: str) -> int:
        """递增当前设备的时钟"""
        self._clock[device_id] = self._clock.get(device_id, 0) + 1
        return self._clock[device_id]

    def merge(self, other: 'VectorClock') -> bool:
        """合并另一个时钟"""
        changed = False
        for device_id, counter in other._clock.items():
            if counter > self._clock.get(device_id, 0):
                self._clock[device_id] = counter
                changed = True
        return changed

    def happened_before(self, other: 'VectorClock') -> bool:
        """判断是否happened-before另一个时钟"""
        for device_id in set(self._clock.keys()) | set(other._clock.keys()):
            self_val = self._clock.get(device_id, 0)
            other_val = other._clock.get(device_id, 0)
            if self_val > other_val:
                return False
        return any(
            self._clock.get(d, 0) < other._clock.get(d, 0)
            for d in set(self._clock.keys()) | set(other._clock.keys())
        )

    def concurrent(self, other: 'VectorClock') -> bool:
        """判断是否并发"""
        return not self.happened_before(other) and not other.happened_before(self)

    def to_dict(self) -> Dict[str, int]:
        return dict(self._clock)

    def to_json(self) -> str:
        return json.dumps(self._clock, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> 'VectorClock':
        vc = cls()
        vc._clock = dict(data)
        return vc


# ============================================================
# 操作日志
# ============================================================

class OpType(Enum):
    """操作类型"""
    SET = "set"
    DELETE = "delete"
    INCREMENT = "increment"
    ADD = "add"
    REMOVE = "remove"
    BATCH = "batch"


@dataclass
class Operation:
    """操作记录"""
    id: str
    type: OpType
    key: str
    value: Any
    timestamp: float
    device_id: str
    vector_clock: Dict[str, int]
    crdt_type: str = "lww_register"
    tags: List[str] = field(default_factory=list)  # for OR-Set

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "key": self.key,
            "value": self.value,
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "vector_clock": self.vector_clock,
            "crdt_type": self.crdt_type,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Operation':
        return cls(
            id=data["id"],
            type=OpType(data["type"]),
            key=data["key"],
            value=data["value"],
            timestamp=data["timestamp"],
            device_id=data["device_id"],
            vector_clock=data.get("vector_clock", {}),
            crdt_type=data.get("crdt_type", "lww_register"),
            tags=data.get("tags", [])
        )


# ============================================================
# 状态数据库
# ============================================================

class StateDB:
    """
    状态数据库

    特性：
    1. SQLite 本地存储
    2. CRDT 支持多设备合并
    3. 操作日志记录
    4. 向量时钟跟踪因果关系
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS state (
        key TEXT PRIMARY KEY,
        crdt_type TEXT NOT NULL,
        value TEXT NOT NULL,
        timestamp REAL NOT NULL,
        device_id TEXT NOT NULL,
        vector_clock TEXT NOT NULL,
        UNIQUE(key, device_id)
    );

    CREATE TABLE IF NOT EXISTS operations (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        timestamp REAL NOT NULL,
        device_id TEXT NOT NULL,
        vector_clock TEXT NOT NULL,
        crdt_type TEXT NOT NULL,
        tags TEXT,
        applied INTEGER DEFAULT 0,
        created_at REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS device_registry (
        device_id TEXT PRIMARY KEY,
        public_key TEXT,
        last_seen REAL,
        metadata TEXT,
        created_at REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sync_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        peer_id TEXT NOT NULL,
        direction TEXT NOT NULL,
        op_count INTEGER,
        timestamp REAL NOT NULL,
        status TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_ops_key ON operations(key);
    CREATE INDEX IF NOT EXISTS idx_ops_timestamp ON operations(timestamp);
    CREATE INDEX IF NOT EXISTS idx_ops_applied ON operations(applied);
    CREATE INDEX IF NOT EXISTS idx_sync_peer ON sync_log(peer_id);
    """

    def __init__(self, db_path: str, device_id: str):
        self.db_path = Path(db_path)
        self.device_id = device_id
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()

        # CRDT 实例
        self._lww = LWWRegisterDB()
        self._counters: Dict[str, GCounter] = defaultdict(GCounter)
        self._sets: Dict[str, ORSet] = defaultdict(ORSet)

        # 向量时钟
        self._vector_clock = VectorClock()

        # 初始化
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        with self._lock:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.executescript(self.SCHEMA)
            self._conn.commit()

            # 加载现有数据到CRDT
            self._load_to_crdt()

    def _load_to_crdt(self):
        """从SQLite加载到CRDT内存"""
        cursor = self._conn.execute(
            "SELECT key, crdt_type, value, timestamp, device_id FROM state"
        )
        for row in cursor.fetchall():
            key, crdt_type, value, timestamp, device_id = row
            try:
                val = json.loads(value)
            except:
                val = value

            if crdt_type == "lww_register":
                self._lww.set(key, val, timestamp, device_id)
            elif crdt_type == "g_counter":
                self._counters[key]._counters[device_id] = max(
                    self._counters[key]._counters.get(device_id, 0),
                    timestamp  # 用timestamp作为计数器值
                )
            elif crdt_type == "or_set":
                if isinstance(val, dict):
                    self._sets[key] = ORSet.from_dict(val)

    def _get_timestamp(self) -> float:
        """获取当前时间戳"""
        return time.time()

    def _generate_op_id(self) -> str:
        """生成操作ID"""
        return f"{self.device_id}:{uuid.uuid4().hex[:12]}"

    def set(self, key: str, value: Any, crdt_type: str = "lww_register") -> Operation:
        """
        设置值

        Args:
            key: 键
            value: 值
            crdt_type: CRDT类型

        Returns:
            创建的操作
        """
        with self._lock:
            timestamp = self._get_timestamp()
            self._vector_clock.increment(self.device_id)

            op = Operation(
                id=self._generate_op_id(),
                type=OpType.SET,
                key=key,
                value=value,
                timestamp=timestamp,
                device_id=self.device_id,
                vector_clock=self._vector_clock.to_dict(),
                crdt_type=crdt_type
            )

            # 应用到CRDT
            if crdt_type == "lww_register":
                self._lww.set(key, value, timestamp, self.device_id)
            elif crdt_type == "g_counter":
                self._counters[key].increment(self.device_id, value if isinstance(value, int) else 1)
            elif crdt_type == "or_set":
                tag = str(uuid.uuid4())
                self._sets[key].add(str(value), tag, timestamp)
                op.tags = [tag]

            # 记录操作
            self._conn.execute(
                """INSERT OR REPLACE INTO operations
                   (id, type, key, value, timestamp, device_id, vector_clock, crdt_type, tags, applied, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (op.id, op.type.value, key, json.dumps(value), timestamp,
                 self.device_id, op.to_json(), crdt_type, json.dumps(op.tags), timestamp)
            )

            # 更新状态表
            self._conn.execute(
                """INSERT OR REPLACE INTO state
                   (key, crdt_type, value, timestamp, device_id, vector_clock)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (key, crdt_type, json.dumps(value), timestamp,
                 self.device_id, op.to_json())
            )

            self._conn.commit()

            return op

    def get(self, key: str, default: Any = None) -> Any:
        """获取值"""
        with self._lock:
            if key in self._lww._data:
                return self._lww.get(key)
            return default

    def delete(self, key: str) -> Operation:
        """删除值"""
        with self._lock:
            timestamp = self._get_timestamp()
            self._vector_clock.increment(self.device_id)

            op = Operation(
                id=self._generate_op_id(),
                type=OpType.DELETE,
                key=key,
                value=None,
                timestamp=timestamp,
                device_id=self.device_id,
                vector_clock=self._vector_clock.to_dict()
            )

            # 从CRDT删除
            if key in self._lww._data:
                del self._lww._data[key]
            if key in self._counters:
                del self._counters[key]
            if key in self._sets:
                del self._sets[key]

            # 记录删除操作
            self._conn.execute(
                """INSERT INTO operations
                   (id, type, key, value, timestamp, device_id, vector_clock, crdt_type, tags, applied, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (op.id, op.type.value, key, None, timestamp,
                 self.device_id, op.to_json(), "lww_register", "[]", timestamp)
            )

            # 标记状态为已删除
            self._conn.execute(
                "DELETE FROM state WHERE key = ? AND device_id = ?",
                (key, self.device_id)
            )

            self._conn.commit()

            return op

    def increment(self, key: str, amount: int = 1) -> Operation:
        """递增计数器"""
        with self._lock:
            return self.set(key, amount, crdt_type="g_counter")

    def add_to_set(self, key: str, element: Any) -> Operation:
        """添加到集合"""
        with self._lock:
            timestamp = self._get_timestamp()
            self._vector_clock.increment(self.device_id)
            tag = str(uuid.uuid4())

            op = Operation(
                id=self._generate_op_id(),
                type=OpType.ADD,
                key=key,
                value=element,
                timestamp=timestamp,
                device_id=self.device_id,
                vector_clock=self._vector_clock.to_dict(),
                crdt_type="or_set",
                tags=[tag]
            )

            self._sets[key].add(str(element), tag, timestamp)

            self._conn.execute(
                """INSERT OR REPLACE INTO state
                   (key, crdt_type, value, timestamp, device_id, vector_clock)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (key, "or_set", json.dumps(self._sets[key].to_dict()),
                 timestamp, self.device_id, op.to_json())
            )

            self._conn.commit()
            return op

    def remove_from_set(self, key: str, element: Any) -> Operation:
        """从集合删除"""
        with self._lock:
            timestamp = self._get_timestamp()
            self._vector_clock.increment(self.device_id)

            op = Operation(
                id=self._generate_op_id(),
                type=OpType.REMOVE,
                key=key,
                value=element,
                timestamp=timestamp,
                device_id=self.device_id,
                vector_clock=self._vector_clock.to_dict(),
                crdt_type="or_set"
            )

            self._sets[key].remove(str(element))

            self._conn.execute(
                """INSERT OR REPLACE INTO state
                   (key, crdt_type, value, timestamp, device_id, vector_clock)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (key, "or_set", json.dumps(self._sets[key].to_dict()),
                 timestamp, self.device_id, op.to_json())
            )

            self._conn.commit()
            return op

    def get_all(self) -> Dict[str, Any]:
        """获取所有值"""
        with self._lock:
            result = self._lww.to_dict()
            for key, counter in self._counters.items():
                result[key] = counter.value()
            for key, s in self._sets.items():
                result[key] = s.to_list()
            return result

    def get_pending_ops(self) -> List[Operation]:
        """获取未同步的操作"""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT * FROM operations WHERE applied = 0 ORDER BY timestamp"
            )
            return [Operation.from_dict(dict(zip(
                ['id', 'type', 'key', 'value', 'timestamp', 'device_id',
                 'vector_clock', 'crdt_type', 'tags', 'applied', 'created_at'],
                row
            ))) for row in cursor.fetchall()]

    def apply_ops(self, ops: List[Operation]) -> int:
        """
        应用一组操作（来自其他设备）

        Returns:
            应用的操作数量
        """
        with self._lock:
            applied = 0

            for op in ops:
                # 更新向量时钟
                other_vc = VectorClock.from_dict(op.vector_clock)
                self._vector_clock.merge(other_vc)

                # 应用操作
                if op.type == OpType.SET:
                    if op.crdt_type == "lww_register":
                        self._lww.set(op.key, op.value, op.timestamp, op.device_id)
                    elif op.crdt_type == "g_counter":
                        self._counters[op.key]._counters[op.device_id] = max(
                            self._counters[op.key]._counters.get(op.device_id, 0),
                            op.value
                        )

                    # 更新状态表
                    self._conn.execute(
                        """INSERT OR REPLACE INTO state
                           (key, crdt_type, value, timestamp, device_id, vector_clock)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (op.key, op.crdt_type, json.dumps(op.value),
                         op.timestamp, op.device_id, json.dumps(op.vector_clock))
                    )

                    applied += 1

                elif op.type == OpType.DELETE:
                    if op.key in self._lww._data:
                        del self._lww._data[op.key]
                    if op.key in self._counters:
                        del self._counters[op.key]
                    if op.key in self._sets:
                        del self._sets[op.key]

                    self._conn.execute(
                        "DELETE FROM state WHERE key = ? AND device_id = ?",
                        (op.key, op.device_id)
                    )
                    applied += 1

                elif op.type == OpType.ADD:
                    if op.tags:
                        self._sets[op.key].add(str(op.value), op.tags[0], op.timestamp)
                        applied += 1

                elif op.type == OpType.REMOVE:
                    self._sets[op.key].remove(str(op.value))
                    applied += 1

                # 标记已应用
                self._conn.execute(
                    "UPDATE operations SET applied = 1 WHERE id = ?",
                    (op.id,)
                )

            self._conn.commit()
            return applied

    def merge_from(self, other_state: Dict[str, Any]) -> int:
        """
        从另一个状态字典合并

        用于处理同步回来的状态
        """
        updates = 0
        with self._lock:
            for key, value in other_state.items():
                if isinstance(value, dict) and 'timestamp' in value:
                    # LWW格式
                    updates += self._lww.set(
                        key, value.get('value'), value['timestamp'], value.get('device_id', '')
                    )
                elif isinstance(value, int):
                    # 计数器
                    self._counters[key]._counters[self.device_id] = max(
                        self._counters[key]._counters.get(self.device_id, 0),
                        value
                    )
                    updates += 1
                elif isinstance(value, list):
                    # 集合
                    self._sets[key] = ORSet.from_dict({"adds": {str(v): {"t": 0} for v in value}, "removes": []})
                    updates += 1
                else:
                    # 简单值
                    updates += self._lww.set(key, value, time.time(), self.device_id)

            self._conn.commit()
            return updates

    def export_state(self) -> Dict[str, Any]:
        """导出当前状态"""
        with self._lock:
            return {
                "lww": self._lww.to_dict(),
                "counters": {k: v.to_dict() for k, v in self._counters.items()},
                "sets": {k: v.to_dict() for k, v in self._sets.items()},
                "vector_clock": self._vector_clock.to_dict()
            }

    def import_state(self, state: Dict[str, Any]):
        """导入状态"""
        with self._lock:
            if "lww" in state:
                self._lww = LWWRegisterDB.from_dict(state["lww"])

            if "counters" in state:
                self._counters = {
                    k: GCounter.from_dict(v) for k, v in state["counters"].items()
                }

            if "sets" in state:
                self._sets = {
                    k: ORSet.from_dict(v) for k, v in state["sets"].items()
                }

            if "vector_clock" in state:
                self._vector_clock = VectorClock.from_dict(state["vector_clock"])

            self._conn.commit()

    def register_device(self, device_id: str, public_key: str = "", metadata: dict = None):
        """注册设备"""
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO device_registry
                   (device_id, public_key, last_seen, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (device_id, public_key, time.time(),
                 json.dumps(metadata or {}), time.time())
            )
            self._conn.commit()

    def get_devices(self) -> List[Dict[str, Any]]:
        """获取已注册设备"""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT device_id, public_key, last_seen, metadata FROM device_registry"
            )
            return [
                {
                    "device_id": row[0],
                    "public_key": row[1],
                    "last_seen": row[2],
                    "metadata": json.loads(row[3]) if row[3] else {}
                }
                for row in cursor.fetchall()
            ]

    def close(self):
        """关闭数据库"""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None


# ============================================================
# 全局单例
# ============================================================

_state_db: Optional[StateDB] = None


def get_state_db(device_id: str = "") -> StateDB:
    """获取全局状态数据库"""
    global _state_db
    if _state_db is None:
        db_path = Path.home() / ".hermes" / "data" / "state.db"
        dev_id = device_id or str(uuid.uuid4())[:16]
        _state_db = StateDB(str(db_path), dev_id)
    return _state_db


def reset_state_db():
    """重置全局状态数据库"""
    global _state_db
    if _state_db:
        _state_db.close()
    _state_db = None