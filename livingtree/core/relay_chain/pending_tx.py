"""
待处理交易管理 - Pending Transaction Manager

管理交易状态机：
- PENDING: 交易已创建，等待共识确认
- CONFIRMED: 交易已确认，写入账本
- FAILED: 交易失败
- EXPIRED: 交易超时

核心职责：
1. 交易预写入和状态流转
2. 超时管理和自动清理
3. 双花检测（同一用户有pending交易时禁止新交易）
"""

import json
import time
import threading
import logging
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Tuple
from enum import Enum
from decimal import Decimal

from .transaction import Tx, OpType

logger = logging.getLogger(__name__)


class TxStatus(Enum):
    """交易状态"""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


@dataclass
class PendingTx:
    """待处理交易"""
    tx_hash: str
    user_id: str
    op_type: OpType
    amount: Decimal
    biz_id: str  # 业务ID（支付单号等）
    status: TxStatus
    confirm_nodes: List[str]
    created_at: float
    confirmed_at: Optional[float] = None
    expired_at: float = 0

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['op_type'] = self.op_type.value
        d['status'] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> 'PendingTx':
        d = d.copy()
        d['op_type'] = OpType(d['op_type'])
        d['status'] = TxStatus(d['status'])
        return cls(**d)


class PendingTxManager:
    """
    待处理交易管理器

    职责：
    1. 管理交易生命周期（创建 → 确认/失败/过期）
    2. 检测双花（同一用户有pending交易）
    3. 多数派确认检测
    """

    # 默认超时时间（秒）
    DEFAULT_TIMEOUT = 60

    # 确认阈值（默认超过半数节点）
    DEFAULT_CONFIRM_THRESHOLD = 3

    def __init__(self, timeout: int = None, confirm_threshold: int = None):
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.confirm_threshold = confirm_threshold or self.DEFAULT_CONFIRM_THRESHOLD

        # 内存存储
        self._pending_txs: Dict[str, PendingTx] = {}
        self._user_pending_lock: Dict[str, threading.Lock] = {}  # 用户级锁，防止双花
        self._global_lock = threading.RLock()

        # 回调
        self._on_confirmed: Optional[callable] = None
        self._on_failed: Optional[callable] = None

        # 启动清理定时器
        self._start_cleanup_timer()

    def set_callbacks(self, on_confirmed: callable = None, on_failed: callable = None):
        """设置回调函数"""
        self._on_confirmed = on_confirmed
        self._on_failed = on_failed

    def create_pending_tx(
        self,
        tx: Tx,
        biz_id: str = "",
        relay_id: str = "local"
    ) -> Tuple[bool, str]:
        """
        创建待处理交易

        Args:
            tx: 交易对象
            biz_id: 业务ID（支付单号）
            relay_id: 创建节点ID

        Returns:
            (success, message)
        """
        with self._get_user_lock(tx.user_id):
            # 1. 双花检测：检查用户是否有pending交易
            if self._has_user_pending(tx.user_id):
                logger.warning(f"双花检测：用户 {tx.user_id} 存在pending交易")
                return False, "用户存在待确认交易，请稍后再试"

            # 2. 创建pending记录
            now = time.time()
            pending = PendingTx(
                tx_hash=tx.tx_hash,
                user_id=tx.user_id,
                op_type=tx.op_type,
                amount=tx.amount,
                biz_id=biz_id or tx.payment_order_id or "",
                status=TxStatus.PENDING,
                confirm_nodes=[relay_id],
                created_at=now,
                expired_at=now + self.timeout
            )

            # 3. 存入内存
            with self._global_lock:
                self._pending_txs[tx.tx_hash] = pending

            logger.info(f"创建pending交易: {tx.tx_hash[:16]}..., user={tx.user_id}, amount={tx.amount}")
            return True, "交易已提交，等待确认"

    def add_confirmation(self, tx_hash: str, relay_id: str) -> Tuple[bool, TxStatus]:
        """
        添加节点确认

        Args:
            tx_hash: 交易哈希
            relay_id: 确认节点ID

        Returns:
            (success, final_status)
        """
        with self._global_lock:
            if tx_hash not in self._pending_txs:
                logger.warning(f"交易不存在: {tx_hash[:16]}...")
                return False, TxStatus.FAILED

            pending = self._pending_txs[tx_hash]

            if pending.status != TxStatus.PENDING:
                logger.warning(f"交易状态不是PENDING: {pending.status}")
                return False, pending.status

            # 添加确认节点
            if relay_id not in pending.confirm_nodes:
                pending.confirm_nodes.append(relay_id)

            logger.info(f"交易确认: {tx_hash[:16]}..., confirmations={len(pending.confirm_nodes)}/{self.confirm_threshold}")

            # 检查是否达成多数派
            if len(pending.confirm_nodes) >= self.confirm_threshold:
                return self._confirm_tx(tx_hash)

            return True, TxStatus.PENDING

    def _confirm_tx(self, tx_hash: str) -> Tuple[bool, TxStatus]:
        """确认交易"""
        with self._global_lock:
            if tx_hash not in self._pending_txs:
                return False, TxStatus.FAILED

            pending = self._pending_txs[tx_hash]
            pending.status = TxStatus.CONFIRMED
            pending.confirmed_at = time.time()

            logger.info(f"交易已确认: {tx_hash[:16]}..., confirmations={len(pending.confirm_nodes)}")

            # 触发回调
            if self._on_confirmed:
                try:
                    self._on_confirmed(pending)
                except Exception as e:
                    logger.error(f"确认回调失败: {e}")

            return True, TxStatus.CONFIRMED

    def fail_tx(self, tx_hash: str, reason: str = "") -> bool:
        """标记交易失败"""
        with self._global_lock:
            if tx_hash not in self._pending_txs:
                return False

            pending = self._pending_txs[tx_hash]
            pending.status = TxStatus.FAILED

            logger.warning(f"交易失败: {tx_hash[:16]}..., reason={reason}")

            # 触发回调
            if self._on_failed:
                try:
                    self._on_failed(pending, reason)
                except Exception as e:
                    logger.error(f"失败回调失败: {e}")

            return True

    def _has_user_pending(self, user_id: str) -> bool:
        """检查用户是否有pending交易"""
        for pending in self._pending_txs.values():
            if pending.user_id == user_id and pending.status == TxStatus.PENDING:
                # 检查是否超时
                if time.time() > pending.expired_at:
                    continue
                return True
        return False

    def get_pending_by_user(self, user_id: str) -> List[PendingTx]:
        """获取用户的所有pending交易"""
        result = []
        for pending in self._pending_txs.values():
            if pending.user_id == user_id and pending.status == TxStatus.PENDING:
                if time.time() <= pending.expired_at:
                    result.append(pending)
        return result

    def get_pending(self, tx_hash: str) -> Optional[PendingTx]:
        """获取pending交易"""
        return self._pending_txs.get(tx_hash)

    def get_all_pending(self) -> List[PendingTx]:
        """获取所有pending交易"""
        return [
            p for p in self._pending_txs.values()
            if p.status == TxStatus.PENDING and time.time() <= p.expires_at
        ]

    def _get_user_lock(self, user_id: str) -> threading.Lock:
        """获取用户级锁"""
        if user_id not in self._user_pending_lock:
            with self._global_lock:
                if user_id not in self._user_pending_lock:
                    self._user_pending_lock[user_id] = threading.Lock()
        return self._user_pending_lock[user_id]

    def _cleanup_expired(self):
        """清理过期交易"""
        now = time.time()
        expired_count = 0

        with self._global_lock:
            for tx_hash, pending in list(self._pending_txs.items()):
                if pending.status == TxStatus.PENDING and now > pending.expired_at:
                    pending.status = TxStatus.EXPIRED
                    expired_count += 1
                    logger.info(f"交易已过期: {tx_hash[:16]}...")

        if expired_count > 0:
            logger.info(f"清理了 {expired_count} 个过期交易")

    def _start_cleanup_timer(self):
        """启动清理定时器"""
        def cleanup_loop():
            while True:
                time.sleep(10)  # 每10秒检查一次
                self._cleanup_expired()

        t = threading.Thread(target=cleanup_loop, daemon=True)
        t.start()

    def is_duplicate_biz_id(self, biz_id: str) -> bool:
        """检查业务ID是否已存在（幂等性检查）"""
        if not biz_id:
            return False

        for pending in self._pending_txs.values():
            if pending.biz_id == biz_id and pending.status in (TxStatus.PENDING, TxStatus.CONFIRMED):
                return True
        return False

    def get_stats(self) -> Dict:
        """获取统计信息"""
        pending = confirmed = failed = expired = 0

        now = time.time()
        for p in self._pending_txs.values():
            if p.status == TxStatus.PENDING:
                if now > p.expires_at:
                    expired += 1
                else:
                    pending += 1
            elif p.status == TxStatus.CONFIRMED:
                confirmed += 1
            elif p.status == TxStatus.FAILED:
                failed += 1
            elif p.status == TxStatus.EXPIRED:
                expired += 1

        return {
            "pending": pending,
            "confirmed": confirmed,
            "failed": failed,
            "expired": expired,
            "total": len(self._pending_txs),
            "confirm_threshold": self.confirm_threshold,
            "timeout": self.timeout
        }
