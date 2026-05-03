"""
LivingTree Relay 账本与共识引擎
================================

精简合并 relay_chain 的 ledger + consensus + mempool + sync_protocol
为统一的基于交易的账本系统。

核心功能:
1. 交易账本: 基于 nonce+prev_hash 的链式防双花
2. 共识机制: 多中继节点 >50% 确认
3. 交易池: 未确认交易的管理
4. 余额计算: 从交易历史计算账户余额

Author: LivingTreeAI Team
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from loguru import logger

from .models import (
    Tx, TxStatus, OpType, LedgerEntry,
    ConsensusVote, ConsensusResult, ConsensusState,
)


# ============================================================================
# 交易池（Mempool）
# ============================================================================

class Mempool:
    """
    交易池 —— 管理待确认交易

    功能:
    - 添加交易到待确认池
    - 去重（基于 tx_id / nonce）
    - 过期清理
    - 获取待确认交易列表
    """

    def __init__(self, max_size: int = 10000, ttl_seconds: float = 300.0):
        self._pending: Dict[str, Tx] = {}          # tx_id → Tx
        self._by_account: Dict[str, List[str]] = defaultdict(list)  # account → [tx_ids]
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    def add_tx(self, tx: Tx) -> bool:
        """添加交易到待确认池"""
        if len(self._pending) >= self.max_size:
            logger.warning("交易池已满")
            return False
        if tx.tx_id in self._pending:
            return False  # 去重
        tx.status = TxStatus.PENDING
        self._pending[tx.tx_id] = tx
        self._by_account[tx.sender_id].append(tx.tx_id)
        return True

    def remove_tx(self, tx_id: str) -> Optional[Tx]:
        """移除交易"""
        tx = self._pending.pop(tx_id, None)
        if tx:
            self._by_account[tx.sender_id].remove(tx_id)
        return tx

    def get_pending(self, limit: int = 100) -> List[Tx]:
        """获取待确认交易（按时间排序）"""
        sorted_txs = sorted(
            self._pending.values(),
            key=lambda t: t.timestamp,
        )
        return sorted_txs[:limit]

    def get_account_pending(self, account_id: str) -> List[Tx]:
        """获取某账户的待确认交易"""
        tx_ids = self._by_account.get(account_id, [])
        return [self._pending[tid] for tid in tx_ids if tid in self._pending]

    def cleanup_expired(self) -> int:
        """清理过期交易"""
        now = datetime.now()
        expired = [
            tx_id for tx_id, tx in self._pending.items()
            if (now - tx.timestamp).total_seconds() > self.ttl_seconds
        ]
        for tx_id in expired:
            tx = self._pending.pop(tx_id)
            tx.status = TxStatus.EXPIRED
        if expired:
            logger.debug(f"清理过期交易: {len(expired)}")
        return len(expired)

    @property
    def size(self) -> int:
        return len(self._pending)


# ============================================================================
# 交易账本
# ============================================================================

class Ledger:
    """
    交易账本 —— 基于交易链的余额管理

    核心思想:
    - 不存储余额, 而是存储完整交易历史
    - 余额 = sum(收入) - sum(支出)
    - 防双花: 每笔交易必须引用前一笔 (nonce+prev_hash)
    - 链式验证: 篡改任意交易会破坏整个链
    """

    def __init__(self):
        self._txs: Dict[str, Tx] = {}                    # tx_id → Tx
        self._account_txs: Dict[str, List[str]] = defaultdict(list)  # account → [tx_ids]
        self._entries: Dict[str, LedgerEntry] = {}        # account → LedgerEntry
        self._confirmed_count = 0

    def record_tx(self, tx: Tx) -> bool:
        """
        记录已确认交易

        验证:
        1. 检查上一笔交易的哈希链
        2. 更新余额
        """
        # 去重
        if tx.tx_id in self._txs:
            return False

        # 链式验证
        prev_tx = self._get_last_tx(tx.sender_id)
        if not tx.is_valid_chain(prev_tx):
            logger.warning(f"交易链验证失败: {tx.tx_id}")
            return False

        # 存储交易
        self._txs[tx.tx_id] = tx
        self._account_txs[tx.sender_id].append(tx.tx_id)
        self._confirmed_count += 1

        # 更新发送方账本
        self._update_entry(tx.sender_id, tx, is_sender=True)

        # 更新接收方账本
        if tx.receiver_id and tx.op_type in (
            OpType.CREDIT_IN, OpType.TRANSFER, OpType.REWARD, OpType.TASK_PAYMENT
        ):
            self._update_entry(tx.receiver_id, tx, is_sender=False)

        logger.debug(f"交易已确认: {tx.tx_id[:12]}... "
                     f"{tx.op_type.value} {tx.amount}")
        return True

    def get_balance(self, account_id: str) -> float:
        """获取账户余额"""
        entry = self._entries.get(account_id)
        return entry.balance if entry else 0.0

    def get_entry(self, account_id: str) -> Optional[LedgerEntry]:
        """获取账本条目"""
        return self._entries.get(account_id)

    def get_tx(self, tx_id: str) -> Optional[Tx]:
        """获取交易"""
        return self._txs.get(tx_id)

    def get_account_txs(
        self, account_id: str, limit: int = 100, offset: int = 0
    ) -> List[Tx]:
        """获取账户交易历史"""
        tx_ids = self._account_txs.get(account_id, [])
        return [
            self._txs[tid]
            for tid in tx_ids[offset : offset + limit]
            if tid in self._txs
        ]

    def verify_chain(self, account_id: str) -> bool:
        """验证账户交易链完整性"""
        tx_ids = self._account_txs.get(account_id, [])
        if not tx_ids:
            return True
        prev = None
        for tid in sorted(tx_ids, key=lambda x: self._txs[x].nonce):
            tx = self._txs[tid]
            if prev and not tx.is_valid_chain(prev):
                return False
            prev = tx
        return True

    @property
    def tx_count(self) -> int:
        return len(self._txs)

    @property
    def confirmed_count(self) -> int:
        return self._confirmed_count

    # ── 内部 ──

    def _get_last_tx(self, account_id: str) -> Optional[Tx]:
        """获取账户的最后一笔交易"""
        tx_ids = self._account_txs.get(account_id, [])
        if not tx_ids:
            return None
        last_id = tx_ids[-1]
        return self._txs.get(last_id)

    def _update_entry(self, account_id: str, tx: Tx, is_sender: bool) -> None:
        """更新账本条目"""
        if account_id not in self._entries:
            self._entries[account_id] = LedgerEntry(account_id=account_id)

        entry = self._entries[account_id]
        entry.tx_count += 1
        entry.updated_at = datetime.now()

        if is_sender:
            if tx.op_type in (OpType.CREDIT_OUT, OpType.TRANSFER):
                entry.balance -= tx.amount
                entry.total_out += tx.amount
        else:
            if tx.op_type in (
                OpType.CREDIT_IN, OpType.TRANSFER, OpType.REWARD, OpType.TASK_PAYMENT
            ):
                entry.balance += tx.amount
                entry.total_in += tx.amount

        entry.last_tx_hash = tx.compute_hash()
        entry.last_nonce = tx.nonce


# ============================================================================
# 共识引擎
# ============================================================================

class ConsensusEngine:
    """
    多中继共识引擎

    流程:
    1. 广播交易到所有中继节点
    2. 收集投票
    3. >50% 同意 → 确认
    4. 超时 → 拒绝
    """

    def __init__(
        self,
        min_confirmations: int = 2,
        vote_timeout: float = 10.0,
    ):
        self.min_confirmations = min_confirmations
        self.vote_timeout = vote_timeout

        # 当前投票轮次
        self._active_votes: Dict[str, ConsensusResult] = {}  # tx_id → ConsensusResult
        self._voters: Set[str] = set()                       # 参与共识的中继节点ID

        # 回调
        self._on_consensus_reached: List[Callable] = []

    def register_voter(self, voter_id: str) -> None:
        """注册投票节点"""
        self._voters.add(voter_id)

    def unregister_voter(self, voter_id: str) -> None:
        """注销投票节点"""
        self._voters.discard(voter_id)

    def propose(self, tx: Tx) -> str:
        """提议交易 → 开始共识"""
        result = ConsensusResult(
            tx_id=tx.tx_id,
            state=ConsensusState.PROPOSED,
            total_voters=len(self._voters),
        )
        self._active_votes[tx.tx_id] = result
        logger.debug(f"共识提议: {tx.tx_id[:12]}... (voters={len(self._voters)})")
        return tx.tx_id

    def vote(self, tx_id: str, voter_id: str, accept: bool, confidence: float = 1.0) -> Optional[ConsensusResult]:
        """
        投票

        Returns:
            如果达成共识则返回 ConsensusResult，否则 None
        """
        result = self._active_votes.get(tx_id)
        if result is None:
            # 可能是过期或未提议的交易
            return None

        if result.state not in (ConsensusState.PROPOSED, ConsensusState.VOTING):
            return result  # 已结束

        # 记录投票
        result.state = ConsensusState.VOTING
        vote = ConsensusVote(
            vote_id=f"{tx_id}_{voter_id}",
            tx_id=tx_id,
            voter_id=voter_id,
            accept=accept,
            confidence=confidence,
        )
        result.votes.append(vote)

        if accept:
            result.accept_count += 1
        else:
            result.reject_count += 1

        # 检查是否达成共识
        if result.has_majority and result.accept_count >= self.min_confirmations:
            result.state = ConsensusState.ACCEPTED
            result.decided_at = datetime.now()
            logger.info(f"共识达成: {tx_id[:12]}... "
                        f"({result.accept_count}/{result.total_voters})")
            self._notify_consensus_reached(result)
            return result

        # 检查是否不可能达成共识
        remaining = result.total_voters - (result.accept_count + result.reject_count)
        if result.reject_count > result.total_voters // 2:
            result.state = ConsensusState.REJECTED
            result.decided_at = datetime.now()
            logger.info(f"共识拒绝: {tx_id[:12]}... "
                        f"({result.reject_count}/{result.total_voters})")
            return result

        return None  # 还在投票中

    def on_consensus(self, callback: Callable) -> None:
        """注册共识达成回调"""
        self._on_consensus_reached.append(callback)

    def get_result(self, tx_id: str) -> Optional[ConsensusResult]:
        return self._active_votes.get(tx_id)

    def cleanup_old(self, max_age_seconds: float = 300.0) -> int:
        """清理过期的共识结果"""
        now = datetime.now()
        expired = [
            tx_id for tx_id, result in self._active_votes.items()
            if result.decided_at
            and (now - result.decided_at).total_seconds() > max_age_seconds
        ]
        for tx_id in expired:
            del self._active_votes[tx_id]
        return len(expired)

    @property
    def active_count(self) -> int:
        return len(self._active_votes)

    @property
    def voter_count(self) -> int:
        return len(self._voters)

    def _notify_consensus_reached(self, result: ConsensusResult) -> None:
        for cb in self._on_consensus_reached:
            try:
                cb(result)
            except Exception:
                pass


__all__ = [
    "Mempool",
    "Ledger",
    "ConsensusEngine",
]
