"""
同步协议 - Synchronization Protocol

负责节点间的数据同步：
1. 全量同步：新节点加入时拉取全量账本
2. 增量同步：节点恢复时同步缺失的交易
3. 交易池同步：待确认交易的同步
4. 节点列表同步：注册中心节点列表同步

同步策略：
- 核心中继（南京）：内网RPC高速同步
- 边缘中继：异步同步，容忍秒级延迟
"""

import time
import threading
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Callable
from enum import Enum
from collections import deque

from .transaction import Tx
from .ledger import Ledger
from .mempool import Mempool, PendingTx


class SyncState(Enum):
    """同步状态"""
    IDLE = "idle"           # 空闲
    SYNCING = "syncing"      # 同步中
    SYNCED = "synced"        # 已同步
    ERROR = "error"          # 同步错误


class SyncMessageType(Enum):
    """同步消息类型"""
    SYNC_REQUEST = "sync_request"       # 同步请求
    SYNC_RESPONSE = "sync_response"     # 同步响应
    TX_BROADCAST = "tx_broadcast"       # 交易广播
    TX_CONFIRM = "tx_confirm"           # 交易确认
    STATE_HASH = "state_hash"           # 状态哈希
    CATCH_UP_REQUEST = "catch_up_request"  # 追赶请求
    CATCH_UP_RESPONSE = "catch_up_response" # 追赶响应


@dataclass
class SyncMessage:
    """同步消息"""
    type: SyncMessageType
    from_relay: str
    to_relay: str = ""  # 空表示广播
    payload: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    message_id: str = ""

    def __post_init__(self):
        if not self.message_id:
            self.message_id = self._generate_id()

    def _generate_id(self) -> str:
        content = f"{self.type.value}|{self.from_relay}|{self.timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class SyncProgress:
    """同步进度"""
    state: SyncState = SyncState.IDLE
    total_items: int = 0
    synced_items: int = 0
    start_time: float = 0
    last_sync_time: float = 0
    error_message: str = ""

    @property
    def progress_percent(self) -> float:
        if self.total_items == 0:
            return 0
        return (self.synced_items / self.total_items) * 100

    @property
    def sync_age_seconds(self) -> float:
        if self.last_sync_time == 0:
            return 0
        return time.time() - self.last_sync_time


class SyncProtocol:
    """
    同步协议

    工作流程：
    1. 节点启动 → 向邻居请求状态哈希
    2. 状态哈希不匹配 → 发起增量同步
    3. 新节点 → 全量同步
    4. 交易池同步 → 广播待确认交易
    """

    def __init__(
        self,
        relay_id: str,
        ledger: Ledger,
        mempool: Mempool,
        on_send_message: Callable[[SyncMessage], None] = None
    ):
        self.relay_id = relay_id
        self.ledger = ledger
        self.mempool = mempool
        self.on_send_message = on_send_message

        # 同步状态
        self.state = SyncState.IDLE
        self.progress = SyncProgress()

        # 邻居节点
        self.neighbors: Set[str] = set()

        # 同步历史
        self.sync_history: deque = deque(maxlen=100)

        # 锁
        self._lock = threading.RLock()

    # ────────────────────────────────────────────────────────────────
    # 同步控制
    # ────────────────────────────────────────────────────────────────

    def start_full_sync(self, source_relay: str) -> bool:
        """
        发起全量同步

        Args:
            source_relay: 同步源节点ID

        Returns:
            是否成功发起
        """
        with self._lock:
            if self.state == SyncState.SYNCING:
                return False

            self.state = SyncState.SYNCING
            self.progress = SyncProgress(
                state=SyncState.SYNCING,
                start_time=time.time()
            )

            # 发送同步请求
            msg = SyncMessage(
                type=SyncMessageType.SYNC_REQUEST,
                from_relay=self.relay_id,
                to_relay=source_relay,
                payload={
                    "mode": "full",
                    "from_tx_hash": self.ledger.get_genesis()
                }
            )

            if self.on_send_message:
                self.on_send_message(msg)

            return True

    def start_catch_up(self, source_relay: str, from_tx_hash: str) -> bool:
        """
        发起增量同步（追赶）

        Args:
            source_relay: 同步源节点
            from_tx_hash: 从哪个交易之后开始同步

        Returns:
            是否成功发起
        """
        with self._lock:
            msg = SyncMessage(
                type=SyncMessageType.CATCH_UP_REQUEST,
                from_relay=self.relay_id,
                to_relay=source_relay,
                payload={
                    "from_tx_hash": from_tx_hash
                }
            )

            if self.on_send_message:
                self.on_send_message(msg)

            return True

    def handle_sync_response(self, msg: SyncMessage) -> Tuple[bool, str]:
        """
        处理同步响应

        Returns:
            (success, message)
        """
        with self._lock:
            payload = msg.payload

            # 获取交易列表
            txs_data = payload.get("txs", [])
            txs = [Tx.from_dict(d) for d in txs_data]

            # 更新进度
            self.progress.total_items = len(txs)
            self.progress.synced_items = 0

            # 导入交易
            success, fail = self.ledger.import_txs(txs)
            self.progress.synced_items = success

            # 更新状态
            self.state = SyncState.SYNCED
            self.progress.state = SyncState.SYNCED
            self.progress.last_sync_time = time.time()

            # 记录历史
            self.sync_history.append({
                "type": "full_sync",
                "source": msg.from_relay,
                "success": success,
                "fail": fail,
                "at": time.time()
            })

            return True, f"同步成功: {success}笔交易"

    def handle_catch_up_response(self, msg: SyncMessage) -> Tuple[bool, str]:
        """处理追赶响应"""
        with self._lock:
            payload = msg.payload

            txs_data = payload.get("txs", [])
            txs = [Tx.from_dict(d) for d in txs_data]

            success, fail = self.ledger.import_txs(txs)

            self.state = SyncState.SYNCED
            self.progress.last_sync_time = time.time()

            return True, f"追赶成功: {success}笔新交易"

    # ────────────────────────────────────────────────────────────────
    # 交易广播
    # ────────────────────────────────────────────────────────────────

    def broadcast_transaction(self, tx: Tx):
        """广播交易到网络"""
        msg = SyncMessage(
            type=SyncMessageType.TX_BROADCAST,
            from_relay=self.relay_id,
            payload={
                "tx": tx.to_dict()
            }
        )

        if self.on_send_message:
            self.on_send_message(msg)

    def broadcast_confirmation(self, tx_hash: str, confirmed_by: Set[str]):
        """广播交易确认"""
        msg = SyncMessage(
            type=SyncMessageType.TX_CONFIRM,
            from_relay=self.relay_id,
            payload={
                "tx_hash": tx_hash,
                "confirmed_by": list(confirmed_by)
            }
        )

        if self.on_send_message:
            self.on_send_message(msg)

    def handle_tx_broadcast(self, msg: SyncMessage) -> Tuple[bool, str]:
        """
        处理交易广播

        Returns:
            (accepted, reason)
        """
        tx_data = msg.payload.get("tx")
        if not tx_data:
            return False, "无交易数据"

        tx = Tx.from_dict(tx_data)

        # 加入本地交易池
        ok, reason, _ = self.mempool.receive_tx(tx, msg.from_relay)
        return ok, reason

    def handle_tx_confirm(self, msg: SyncMessage) -> bool:
        """处理交易确认广播"""
        tx_hash = msg.payload.get("tx_hash")
        confirmed_by = set(msg.payload.get("confirmed_by", []))

        if tx_hash:
            self.mempool.confirm_tx(tx_hash, msg.from_relay)

        return True

    # ────────────────────────────────────────────────────────────────
    # 状态哈希
    # ────────────────────────────────────────────────────────────────

    def request_state_hash(self, target_relay: str):
        """请求其他节点的状态哈希"""
        msg = SyncMessage(
            type=SyncMessageType.STATE_HASH,
            from_relay=self.relay_id,
            to_relay=target_relay,
            payload={
                "ledger_hash": self.ledger.get_ledger_hash(),
                "tx_count": len(self.ledger.txs),
                "pending_count": self.mempool.get_pending_count()
            }
        )

        if self.on_send_message:
            self.on_send_message(msg)

    def compare_and_sync(self, remote_hash: str, remote_tx_count: int) -> Tuple[bool, str]:
        """
        比较状态并决定是否同步

        Returns:
            (needs_sync, reason)
        """
        local_hash = self.ledger.get_ledger_hash()
        local_count = len(self.ledger.txs)

        if remote_hash != local_hash or remote_tx_count > local_count:
            # 需要同步
            if remote_tx_count > local_count * 2:
                return True, "差异过大，需要全量同步"
            return True, f"本地{local_count}笔，远程{remote_tx_count}笔"
        else:
            return False, "状态一致，无需同步"

    # ────────────────────────────────────────────────────────────────
    # 邻居管理
    # ────────────────────────────────────────────────────────────────

    def add_neighbor(self, relay_id: str):
        """添加邻居节点"""
        with self._lock:
            self.neighbors.add(relay_id)

    def remove_neighbor(self, relay_id: str):
        """移除邻居节点"""
        with self._lock:
            self.neighbors.discard(relay_id)

    def get_neighbors(self) -> List[str]:
        """获取邻居列表"""
        return list(self.neighbors)

    # ────────────────────────────────────────────────────────────────
    # 统计
    # ────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """获取同步统计"""
        return {
            "state": self.state.value,
            "progress_percent": self.progress.progress_percent,
            "synced_items": self.progress.synced_items,
            "total_items": self.progress.total_items,
            "last_sync_age_seconds": self.progress.sync_age_seconds,
            "neighbors_count": len(self.neighbors),
            "sync_history_count": len(self.sync_history)
        }


class StateComparator:
    """状态比较器"""

    @staticmethod
    def compare_ledger_states(local: Dict, remote: Dict) -> Dict:
        """
        比较账本状态

        Returns:
            比较结果
        """
        result = {
            "in_sync": True,
            "local_ahead": False,
            "remote_ahead": False,
            "differences": []
        }

        local_hash = local.get("ledger_hash", "")
        remote_hash = remote.get("ledger_hash", "")

        if local_hash != remote_hash:
            result["in_sync"] = False
            result["differences"].append("账本哈希不一致")

        local_count = local.get("tx_count", 0)
        remote_count = remote.get("tx_count", 0)

        if remote_count > local_count:
            result["in_sync"] = False
            result["remote_ahead"] = True
            result["differences"].append(f"远程多{remote_count - local_count}笔交易")
        elif local_count > remote_count:
            result["in_sync"] = False
            result["local_ahead"] = True
            result["differences"].append(f"本地多{local_count - remote_count}笔交易")

        return result