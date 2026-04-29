"""
交易池 - Mempool

交易池负责：
1. 暂存已收到但未确认的交易
2. 去重：同一tx_hash不重复接收
3. 防双花：检查nonce和余额
4. 广播：收到交易后广播给网络
5. 清理：超时交易自动清除
"""

import time
import threading
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable
from collections import deque
from decimal import Decimal

from .transaction import Tx, TxValidationResult, OpType
from .ledger import Ledger


@dataclass
class PendingTx:
    """待确认交易"""
    tx: Tx
    received_at: float = field(default_factory=time.time)
    relay_id: str = ""  # 来自哪个中继
    signature: str = ""  # 中继签名（可选）
    confirmed_by: Set[str] = field(default_factory=set)  # 已确认的中继ID集合

    def age(self) -> float:
        """存活时间（秒）"""
        return time.time() - self.received_at


class Mempool:
    """
    交易池

    核心数据结构：
    - pending: {tx_hash -> PendingTx} 待确认交易
    - by_user: {user_id -> [tx_hash,...]} 用户待确认交易

    特性：
    - 线程安全
    - 自动清理超时交易（默认5分钟）
    - 防重复接收
    """

    def __init__(self, ledger: Ledger, max_age: float = 300):
        """
        Args:
            ledger: 关联的账本
            max_age: 交易最大存活时间（秒），默认5分钟
        """
        self.ledger = ledger
        self.max_age = max_age

        # 待确认交易
        self.pending: Dict[str, PendingTx] = {}
        self.by_user: Dict[str, List[str]] = {}  # user_id -> [tx_hash,...]

        # 回调
        self.on_tx_confirmed: Optional[Callable[[Tx], None]] = None
        self.on_tx_rejected: Optional[Callable[[Tx, str], None]] = None
        self.on_broadcast: Optional[Callable[[Tx, Set[str]], None]] = None

        self._lock = threading.RLock()

    # ────────────────────────────────────────────────────────────────
    # 核心操作
    # ────────────────────────────────────────────────────────────────

    def receive_tx(self, tx: Tx, relay_id: str = "") -> Tuple[bool, str, Optional[PendingTx]]:
        """
        接收交易

        流程：
        1. 检查是否重复
        2. 基本验证
        3. 加入待确认池
        4. 触发广播回调

        Returns:
            (accepted, reason, pending_tx)
        """
        with self._lock:
            # 1. 检查是否已存在
            if tx.tx_hash in self.pending:
                # 已存在但未确认，尝试合并确认
                pending = self.pending[tx.tx_hash]
                if relay_id and relay_id not in pending.confirmed_by:
                    pending.confirmed_by.add(relay_id)
                return True, "交易已在池中", pending

            # 2. 检查是否已确认（账本中）
            if tx.tx_hash in self.ledger.txs:
                return False, "交易已确认", None

            # 3. 账本验证
            result = self.ledger.validate_tx(tx)
            if not result.valid:
                return False, result.error, None

            # 4. 创建PendingTx并加入池
            pending = PendingTx(
                tx=tx,
                received_at=time.time(),
                relay_id=relay_id,
                confirmed_by={relay_id} if relay_id else set()
            )

            self.pending[tx.tx_hash] = pending

            # 5. 更新用户索引
            if tx.user_id not in self.by_user:
                self.by_user[tx.user_id] = []
            self.by_user[tx.user_id].append(tx.tx_hash)

            # 6. 触发广播回调
            if self.on_broadcast:
                self.on_broadcast(tx, set())

            return True, "交易已接收", pending

    def confirm_tx(self, tx_hash: str, relay_id: str = "") -> Tuple[bool, str]:
        """
        确认交易（从网络收到确认信号）

        Returns:
            (confirmed, message)
        """
        with self._lock:
            if tx_hash not in self.pending:
                return False, "交易不在池中"

            pending = self.pending[tx_hash]
            if relay_id:
                pending.confirmed_by.add(relay_id)

            return True, f"已确认 ({len(pending.confirmed_by)}个中继)"

    def commit_tx(self, tx_hash: str) -> Tuple[bool, str]:
        """
        将交易提交到账本

        Returns:
            (success, message)
        """
        with self._lock:
            if tx_hash not in self.pending:
                return False, "交易不在池中"

            pending = self.pending[tx_hash]
            tx = pending.tx

            # 再次验证
            result = self.ledger.validate_tx(tx)
            if not result.valid:
                self._remove_pending(tx_hash)
                if self.on_tx_rejected:
                    self.on_tx_rejected(tx, result.error)
                return False, result.error

            # 提交到账本
            ok, msg = self.ledger.add_tx(tx)
            if not ok:
                self._remove_pending(tx_hash)
                if self.on_tx_rejected:
                    self.on_tx_rejected(tx, msg)
                return False, msg

            # 从池中移除
            self._remove_pending(tx_hash)

            # 触发确认回调
            if self.on_tx_confirmed:
                self.on_tx_confirmed(tx)

            return True, "交易已确认"

    def reject_tx(self, tx_hash: str, reason: str):
        """拒绝交易"""
        with self._lock:
            if tx_hash in self.pending:
                tx = self.pending[tx_hash].tx
                self._remove_pending(tx_hash)
                if self.on_tx_rejected:
                    self.on_tx_rejected(tx, reason)

    def _remove_pending(self, tx_hash: str):
        """从池中移除交易"""
        if tx_hash not in self.pending:
            return

        pending = self.pending[tx_hash]

        # 从用户索引移除
        user_txs = self.by_user.get(pending.tx.user_id, [])
        if tx_hash in user_txs:
            user_txs.remove(tx_hash)
            if not user_txs:
                del self.by_user[pending.tx.user_id]

        # 从池移除
        del self.pending[tx_hash]

    # ────────────────────────────────────────────────────────────────
    # 查询操作
    # ────────────────────────────────────────────────────────────────

    def get_pending(self, tx_hash: str) -> Optional[PendingTx]:
        """获取待确认交易"""
        return self.pending.get(tx_hash)

    def get_user_pending(self, user_id: str) -> List[Tx]:
        """获取用户待确认交易"""
        with self._lock:
            txs = []
            for h in self.by_user.get(user_id, []):
                if h in self.pending:
                    txs.append(self.pending[h].tx)
            return txs

    def get_all_pending(self) -> List[PendingTx]:
        """获取所有待确认交易"""
        return list(self.pending.values())

    def get_pending_count(self) -> int:
        """获取待确认交易数量"""
        return len(self.pending)

    def get_confirmations(self, tx_hash: str) -> int:
        """获取交易确认数"""
        if tx_hash in self.pending:
            return len(self.pending[tx_hash].confirmed_by)
        return 0

    # ────────────────────────────────────────────────────────────────
    # 清理操作
    # ────────────────────────────────────────────────────────────────

    def cleanup_expired(self) -> int:
        """
        清理超时交易

        Returns:
            清理的交易数量
        """
        with self._lock:
            now = time.time()
            to_remove = []

            for tx_hash, pending in self.pending.items():
                if now - pending.received_at > self.max_age:
                    to_remove.append(tx_hash)

            for tx_hash in to_remove:
                self._remove_pending(tx_hash)

            return len(to_remove)

    def get_stats(self) -> Dict:
        """获取交易池统计"""
        total_age = 0
        oldest_age = 0
        newest_age = float('inf')

        now = time.time()
        for pending in self.pending.values():
            age = now - pending.received_at
            total_age += age
            oldest_age = max(oldest_age, age)
            newest_age = min(newest_age, age)

        count = len(self.pending)
        avg_age = total_age / count if count > 0 else 0

        return {
            "pending_count": count,
            "avg_age_seconds": avg_age,
            "oldest_age_seconds": oldest_age,
            "newest_age_seconds": newest_age,
            "max_age_seconds": self.max_age,
            "by_user_count": len(self.by_user)
        }


class MempoolSynchronizer:
    """交易池同步器"""

    def __init__(self, mempool: Mempool):
        self.mempool = mempool
        self._lock = threading.Lock()

    def get_pending_hashes(self) -> List[str]:
        """获取本地待确认交易的hash列表"""
        return list(self.mempool.pending.keys())

    def get_pending_txs(self) -> List[Tx]:
        """获取本地待确认交易列表"""
        return [p.tx for p in self.mempool.get_all_pending()]

    def merge_pending(self, remote_hashes: List[str], remote_txs: List[Tx]) -> Dict:
        """
        合并远程待确认交易

        Returns:
            {
                "new_count": 新增数量,
                "known_count": 已存在数量,
                "missing_hashes": 本地缺失的远程hash
            }
        """
        result = {"new_count": 0, "known_count": 0, "missing_hashes": []}

        # 建立remote映射
        remote_map = {tx.tx_hash: tx for tx in remote_txs}

        # 查找本地缺失的
        local_set = set(self.mempool.pending.keys())
        for h in remote_hashes:
            if h not in local_set:
                result["missing_hashes"].append(h)

        # 接收新交易
        for tx in remote_txs:
            if tx.tx_hash not in self.mempool.pending:
                ok, _, _ = self.mempool.receive_tx(tx)
                if ok:
                    result["new_count"] += 1
                else:
                    result["known_count"] += 1  # 验证失败也视为已知
            else:
                result["known_count"] += 1

        return result