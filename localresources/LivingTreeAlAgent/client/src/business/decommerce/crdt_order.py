"""
CRDT 订单状态同步
CRDT-based Order State Synchronization

使用无冲突复制数据类型 (CRDT) 思路管理订单状态,
允许买卖两端在网络抖动时各自记账，复通后自动合并，
不丢单、不乱序。

特性:
1. LWW-Register (Last-Write-Wins) - 订单状态
2. G-Counter - 金额计数器
3. PN-Counter - 正负计数器 (用于冻结/解冻)
4. OR-Set - 操作集合 (用于事件历史)
5. 版本向量 - 检测并发冲突
"""

from typing import Dict, Any, Optional, List, Set, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
import time
import uuid
import hashlib

logger = logging.getLogger(__name__)


class OrderAction(Enum):
    """订单动作"""
    CREATE = "create"
    FREEZE = "freeze"
    UNFREEZE = "unfreeze"
    COMPLETE = "complete"
    CANCEL = "cancel"
    REFUND = "refund"
    DISPUTE = "dispute"


@dataclass
class VersionVector:
    """版本向量 - 跟踪各节点最后更新时间"""
    versions: Dict[str, float] = field(default_factory=dict)  # node_id -> timestamp

    def merge(self, other: "VersionVector") -> None:
        """合并两个版本向量"""
        for node_id, ts in other.versions.items():
            self.versions[node_id] = max(self.versions.get(node_id, 0), ts)

    def is_concurrent_with(self, other: "VersionVector") -> bool:
        """检测是否并发"""
        self_newer = False
        other_newer = False

        all_nodes = set(self.versions.keys()) | set(other.versions.keys())
        for node in all_nodes:
            self_ts = self.versions.get(node, 0)
            other_ts = other.versions.get(node, 0)

            if self_ts > other_ts:
                self_newer = True
            elif other_ts > self_ts:
                other_newer = True

        return self_newer and other_newer

    def to_dict(self) -> Dict[str, float]:
        return self.versions.copy()


@dataclass
class LWWRegister:
    """Last-Write-Wins Register - 最后写入胜出寄存器"""
    value: Any = None
    timestamp: float = 0
    node_id: str = ""

    def set(self, value: Any, node_id: str) -> None:
        """设置值 (只有更新的时间戳才能覆盖)"""
        now = time.time()
        if now >= self.timestamp:
            self.value = value
            self.timestamp = now
            self.node_id = node_id

    def merge(self, other: "LWWRegister") -> bool:
        """合并另一个寄存器,返回是否有变化"""
        if other.timestamp > self.timestamp:
            self.value = other.value
            self.timestamp = other.timestamp
            self.node_id = other.node_id
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "timestamp": self.timestamp,
            "node_id": self.node_id,
        }


@dataclass
class PNCounter:
    """
    Positive-Negative Counter
    正负计数器,用于冻结/解冻金额
    """
    positive: Dict[str, int] = field(default_factory=dict)
    negative: Dict[str, int] = field(default_factory=dict)
    node_id: str = ""

    def increment(self, amount: int, node_id: str) -> None:
        self.positive[node_id] = self.positive.get(node_id, 0) + amount

    def decrement(self, amount: int, node_id: str) -> None:
        self.negative[node_id] = self.negative.get(node_id, 0) + amount

    def value(self) -> int:
        return sum(self.positive.values()) + sum(self.negative.values())

    def merge(self, other: "PNCounter") -> bool:
        changed = False
        for node, val in other.positive.items():
            if val > self.positive.get(node, 0):
                self.positive[node] = val
                changed = True
        for node, val in other.negative.items():
            if val > self.negative.get(node, 0):
                self.negative[node] = val
                changed = True
        return changed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "positive": self.positive.copy(),
            "negative": self.negative.copy(),
            "value": self.value(),
        }


@dataclass
class ORSetItem:
    """OR-Set 中的元素"""
    value: Any
    tag: str
    added_at: float = field(default_factory=time.time)
    removed: bool = False


class ORSet:
    """Observed-Remove Set - 用于订单事件历史"""
    def __init__(self, node_id: str = ""):
        self.node_id = node_id
        self._items: Dict[str, ORSetItem] = {}
        self._tags_by_value: Dict[str, Set[str]] = {}

    def add(self, value: Any) -> str:
        tag = hashlib.sha256(f"{value}{time.time()}{uuid.uuid4()}".encode()).hexdigest()[:12]
        item = ORSetItem(value=value, tag=tag)
        self._items[tag] = item
        if value not in self._tags_by_value:
            self._tags_by_value[value] = set()
        self._tags_by_value[value].add(tag)
        return tag

    def remove(self, value: Any) -> None:
        if value in self._tags_by_value:
            for tag in self._tags_by_value[value]:
                if tag in self._items:
                    self._items[tag].removed = True
            del self._tags_by_value[value]

    def contains(self, value: Any) -> bool:
        if value not in self._tags_by_value:
            return False
        for tag in self._tags_by_value[value]:
            if tag in self._items and not self._items[tag].removed:
                return True
        return False

    def get_all(self) -> List[Any]:
        result = []
        for value, tags in self._tags_by_value.items():
            for tag in tags:
                if tag in self._items and not self._items[tag].removed:
                    result.append(value)
                    break
        return result

    def merge(self, other: "ORSet") -> bool:
        changed = False
        for tag, item in other._items.items():
            if tag not in self._items:
                self._items[tag] = item
                changed = True
            elif item.removed and not self._items[tag].removed:
                self._items[tag].removed = True
                changed = True

        self._tags_by_value.clear()
        for tag, item in self._items.items():
            if not item.removed:
                if item.value not in self._tags_by_value:
                    self._tags_by_value[item.value] = set()
                self._tags_by_value[item.value].add(tag)
        return changed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": [
                {"tag": t, "value": i.value, "removed": i.removed}
                for t, i in self._items.items()
            ]
        }


@dataclass
class OrderStateCRDT:
    """
    订单状态CRDT复合数据类型
    """
    order_id: str
    status: LWWRegister = field(default_factory=LWWRegister)
    frozen_amount: PNCounter = field(default_factory=PNCounter)
    released_amount: PNCounter = field(default_factory=PNCounter)
    events: ORSet = field(default_factory=ORSet)
    version_vector: VersionVector = field(default_factory=VersionVector)
    node_id: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.status.value:
            self.status.value = "pending"
        if not self.node_id:
            self.node_id = str(uuid.uuid4())[:8]

    def create_order(self, initial_amount: int) -> None:
        self.status.set("pending", self.node_id)
        self.frozen_amount.positive[self.node_id] = initial_amount
        self.version_vector.versions[self.node_id] = time.time()
        self.events.add(f"create:{initial_amount}")
        self.updated_at = time.time()

    def freeze(self, amount: int) -> bool:
        self.frozen_amount.increment(amount, self.node_id)
        self.version_vector.versions[self.node_id] = time.time()
        self.events.add(f"freeze:{amount}")
        self.updated_at = time.time()
        logger.info(f"[CRDT] Froze {amount} for order {self.order_id}, total frozen: {self.frozen_amount.value()}")
        return True

    def unfreeze(self, amount: int) -> bool:
        self.frozen_amount.decrement(amount, self.node_id)
        self.released_amount.increment(amount, self.node_id)
        self.version_vector.versions[self.node_id] = time.time()
        self.events.add(f"unfreeze:{amount}")
        self.updated_at = time.time()
        logger.info(f"[CRDT] Unfroze {amount} for order {self.order_id}, remaining frozen: {self.frozen_amount.value()}")
        return True

    def complete(self) -> bool:
        if self.status.value not in ("active", "frozen"):
            return False
        self.status.set("completed", self.node_id)
        self.version_vector.versions[self.node_id] = time.time()
        self.events.add("complete")
        self.updated_at = time.time()
        return True

    def cancel(self, reason: str = "") -> bool:
        if self.status.value in ("completed", "refunded"):
            return False
        self.status.set("cancelled", self.node_id)
        self.version_vector.versions[self.node_id] = time.time()
        self.events.add(f"cancel:{reason}")
        self.updated_at = time.time()
        return True

    def refund(self, amount: int) -> bool:
        self.status.set("refunded", self.node_id)
        self.frozen_amount.decrement(amount, self.node_id)
        self.released_amount.increment(amount, self.node_id)
        self.version_vector.versions[self.node_id] = time.time()
        self.events.add(f"refund:{amount}")
        self.updated_at = time.time()
        return True

    def merge(self, other: "OrderStateCRDT") -> bool:
        if self.order_id != other.order_id:
            raise ValueError("Cannot merge orders with different IDs")

        changed = False
        if other.status.timestamp > self.status.timestamp:
            self.status = other.status
            changed = True

        if other.frozen_amount.merge(self.frozen_amount):
            changed = True
        if self.frozen_amount.merge(other.frozen_amount):
            changed = True

        if other.released_amount.merge(self.released_amount):
            changed = True
        if self.released_amount.merge(other.released_amount):
            changed = True

        if self.events.merge(other.events):
            changed = True

        self.version_vector.merge(other.version_vector)

        if changed:
            self.updated_at = time.time()

        return changed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "status": self.status.value,
            "status_timestamp": self.status.timestamp,
            "frozen_amount": self.frozen_amount.value(),
            "released_amount": self.released_amount.value(),
            "events": self.events.get_all(),
            "version_vector": self.version_vector.to_dict(),
            "node_id": self.node_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class CRDTOrderManager:
    """CRDT订单状态管理器"""
    def __init__(self, node_id: str = ""):
        self.node_id = node_id or str(uuid.uuid4())[:8]
        self._orders: Dict[str, OrderStateCRDT] = {}
        self._pending_syncs: Dict[str, List[OrderStateCRDT]] = {}
        self._sync_task: Optional[asyncio.Task] = None
        self._running = False
        self._on_order_changed: List[Callable] = []
        self._on_conflict_detected: List[Callable] = []
        logger.info(f"[CRDTOrderManager] Initialized with node_id: {self.node_id}")

    async def start(self) -> None:
        self._running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info("[CRDTOrderManager] Started")

    async def stop(self) -> None:
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

    def create_order(self, order_id: str, initial_amount: int) -> OrderStateCRDT:
        order = OrderStateCRDT(order_id=order_id, node_id=self.node_id)
        order.create_order(initial_amount)
        self._orders[order_id] = order
        logger.info(f"[CRDTOrderManager] Created order {order_id} with amount {initial_amount}")
        return order

    def get_order(self, order_id: str) -> Optional[OrderStateCRDT]:
        return self._orders.get(order_id)

    def freeze(self, order_id: str, amount: int) -> bool:
        order = self._orders.get(order_id)
        if not order:
            return False
        order.freeze(amount)
        self._notify_order_changed(order)
        return True

    def unfreeze(self, order_id: str, amount: int) -> bool:
        order = self._orders.get(order_id)
        if not order:
            return False
        if order.frozen_amount.value() < amount:
            return False
        order.unfreeze(amount)
        self._notify_order_changed(order)
        return True

    def unfreeze_tiered(
        self,
        order_id: str,
        progress: float,
        tiers: List[Tuple[float, int]]
    ) -> int:
        """
        分段解冻

        Args:
            order_id: 订单ID
            progress: 当前进度 (0.0 - 1.0)
            tiers: 分段列表 [(进度点, 解冻比例), ...]
                   例如: [(0.3, 0.1), (0.6, 0.4), (1.0, 1.0)]
        Returns:
            本次解冻的金额
        """
        order = self._orders.get(order_id)
        if not order:
            return 0

        current_frozen = order.frozen_amount.value()
        if current_frozen <= 0:
            return 0

        already_released = order.released_amount.value()

        # 计算当前进度应解冻总额
        to_release_total = 0
        for threshold, release_ratio in tiers:
            if progress >= threshold:
                to_release_total = int(release_ratio * (order.frozen_amount.value() + already_released))

        # 扣除已解冻
        to_release = max(0, to_release_total - already_released)
        to_release = min(to_release, current_frozen)

        if to_release > 0:
            order.unfreeze(to_release)
            self._notify_order_changed(order)

        return to_release

    def complete(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if not order:
            return False
        if order.complete():
            self._notify_order_changed(order)
            return True
        return False

    def cancel(self, order_id: str, reason: str = "") -> bool:
        order = self._orders.get(order_id)
        if not order:
            return False
        if order.cancel(reason):
            frozen = order.frozen_amount.value()
            if frozen > 0:
                order.unfreeze(frozen)
            self._notify_order_changed(order)
            return True
        return False

    def receive_remote_state(self, state: OrderStateCRDT) -> bool:
        order_id = state.order_id
        if order_id not in self._pending_syncs:
            self._pending_syncs[order_id] = []
        self._pending_syncs[order_id].append(state)
        return True

    async def _sync_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(5)
                for order_id in list(self._pending_syncs.keys()):
                    pending = self._pending_syncs.get(order_id, [])
                    if not pending:
                        continue

                    local_order = self._orders.get(order_id)
                    for remote_state in pending:
                        if local_order:
                            if local_order.version_vector.is_concurrent_with(remote_state.version_vector):
                                logger.warning(f"[CRDTOrderManager] Concurrent modification for order {order_id}")
                                self._notify_conflict(order_id, local_order, remote_state)
                            if local_order.merge(remote_state):
                                self._notify_order_changed(local_order)
                        else:
                            self._orders[order_id] = remote_state
                            self._notify_order_changed(remote_state)

                    del self._pending_syncs[order_id]

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[CRDTOrderManager] Sync error: {e}")

    def export_state(self, order_id: str) -> Optional[Dict[str, Any]]:
        order = self._orders.get(order_id)
        return order.to_dict() if order else None

    def on_order_changed(self, callback: Callable) -> None:
        self._on_order_changed.append(callback)

    def on_conflict_detected(self, callback: Callable) -> None:
        self._on_conflict_detected.append(callback)

    def _notify_order_changed(self, order: OrderStateCRDT) -> None:
        for cb in self._on_order_changed:
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(order))
                else:
                    cb(order)
            except Exception as e:
                logger.error(f"[CRDTOrderManager] Callback error: {e}")

    def _notify_conflict(self, order_id: str, local: OrderStateCRDT, remote: OrderStateCRDT) -> None:
        for cb in self._on_conflict_detected:
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(order_id, local, remote))
                else:
                    cb(order_id, local, remote)
            except Exception as e:
                logger.error(f"[CRDTOrderManager] Conflict callback error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "total_orders": len(self._orders),
            "pending_syncs": sum(len(v) for v in self._pending_syncs.values()),
        }


# 全局单例
_crdt_order_manager: Optional[CRDTOrderManager] = None

def get_crdt_order_manager() -> CRDTOrderManager:
    global _crdt_order_manager
    if _crdt_order_manager is None:
        _crdt_order_manager = CRDTOrderManager()
    return _crdt_order_manager
