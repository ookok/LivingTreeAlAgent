"""
共识机制 - Consensus Mechanism

实现"交易确认 + 多数派同步"机制

核心概念：
- 确认阈值：超过N个中继确认即认为交易有效
- 多数派：网络中50%以上的中继
- 共识状态：每个中继维护自己的共识视图

无币无挖矿设计：
- 不需要工作量证明（PoW）
- 不需要权益证明（PoS）
- 只需要多数派确认即可
"""

import time
import threading
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from collections import defaultdict

from .transaction import Tx, TxValidationResult
from .mempool import Mempool, PendingTx


class ConsensusState(Enum):
    """共识状态"""
    PENDING = "pending"      # 待确认
    CONFIRMING = "confirming" # 确认中
    CONFIRMED = "confirmed"   # 已确认
    REJECTED = "rejected"     # 已拒绝


@dataclass
class ConsensusVote:
    """共识投票"""
    tx_hash: str
    relay_id: str
    valid: bool
    reason: str = ""
    voted_at: float = field(default_factory=time.time)


@dataclass
class TxConsensus:
    """交易共识状态"""
    tx_hash: str
    state: ConsensusState = ConsensusState.PENDING
    votes: List[ConsensusVote] = field(default_factory=list)
    confirmed_at: Optional[float] = None
    confirmed_by: Set[str] = field(default_factory=set)
    rejected_by: Set[str] = field(default_factory=set)

    @property
    def confirmations(self) -> int:
        return len(self.confirmed_by)

    @property
    def rejections(self) -> int:
        return len(self.rejected_by)


class ConsensusEngine:
    """
    共识引擎

    工作流程：
    1. 收到交易 → 进入 PENDING 状态
    2. 本地验证通过 → 广播 VALIDATE_REQUEST 到全网
    3. 收到其他中继的投票 → 更新共识状态
    4. 达到确认阈值 → 进入 CONFIRMED 状态，提交到账本
    5. 达到拒绝阈值 → 进入 REJECTED 状态

    配置参数：
    - confirmation_threshold: 确认阈值（默认3个中继，或50%）
    - rejection_threshold: 拒绝阈值（默认2个中继）
    - confirmation_timeout: 确认超时（默认60秒）
    """

    def __init__(
        self,
        mempool: Mempool,
        relay_id: str,
        confirmation_threshold: int = 3,
        rejection_threshold: int = 2,
        confirmation_timeout: float = 60.0
    ):
        self.mempool = mempool
        self.relay_id = relay_id

        # 阈值配置
        self.confirmation_threshold = confirmation_threshold
        self.rejection_threshold = rejection_threshold
        self.confirmation_timeout = confirmation_timeout

        # 共识状态
        self.consensus_states: Dict[str, TxConsensus] = {}

        # 节点列表（注册中心同步）
        self.known_relays: Set[str] = {relay_id}  # 包含自己
        self.relay_count: int = 1

        # 回调
        self.on_state_change: Optional[callable] = None
        self.on_consensus_reached: Optional[callable] = None
        self.on_broadcast: Optional[callable] = None

        self._lock = threading.RLock()

    # ────────────────────────────────────────────────────────────────
    # 交易处理
    # ────────────────────────────────────────────────────────────────

    def submit_transaction(self, tx: Tx) -> Tuple[bool, str, ConsensusState]:
        """
        提交交易到共识流程

        Returns:
            (accepted, message, state)
        """
        with self._lock:
            # 1. 本地验证
            result = self.mempool.ledger.validate_tx(tx)
            if not result.valid:
                return False, result.error, ConsensusState.REJECTED

            # 2. 加入交易池
            accepted, msg, pending = self.mempool.receive_tx(tx, self.relay_id)
            if not accepted:
                return False, msg, ConsensusState.PENDING

            # 3. 创建共识状态
            consensus = TxConsensus(tx_hash=tx.tx_hash)
            consensus.state = ConsensusState.CONFIRMING
            self.consensus_states[tx.tx_hash] = consensus

            # 4. 本地投票（视为第一个确认）
            self._add_vote(tx.tx_hash, self.relay_id, True)

            # 5. 广播验证请求
            self._broadcast_validation_request(tx)

            return True, "交易已提交共识", ConsensusState.CONFIRMING

    def receive_vote(self, vote: ConsensusVote) -> Tuple[bool, str]:
        """
        接收来自其他中继的投票

        Returns:
            (processed, message)
        """
        with self._lock:
            if vote.tx_hash not in self.consensus_states:
                # 交易不在共识表中，可能需要同步
                return False, "交易不在共识表中"

            consensus = self.consensus_states[vote.tx_hash]

            # 忽略已确认/已拒绝的交易
            if consensus.state in (ConsensusState.CONFIRMED, ConsensusState.REJECTED):
                return True, f"交易已{consensus.state.value}"

            # 添加投票
            self._add_vote(vote.tx_hash, vote.relay_id, vote.valid)

            # 更新交易池确认状态
            self.mempool.confirm_tx(vote.tx_hash, vote.relay_id)

            # 检查是否达成共识
            return self._check_consensus(vote.tx_hash)

    def _add_vote(self, tx_hash: str, relay_id: str, valid: bool):
        """添加投票"""
        if tx_hash not in self.consensus_states:
            return

        consensus = self.consensus_states[tx_hash]

        # 检查是否已投过
        for v in consensus.votes:
            if v.relay_id == relay_id:
                return  # 已投过，忽略

        # 添加投票
        vote = ConsensusVote(tx_hash=tx_hash, relay_id=relay_id, valid=valid)
        consensus.votes.append(vote)

        if valid:
            consensus.confirmed_by.add(relay_id)
        else:
            consensus.rejected_by.add(relay_id)

        # 更新本地交易池
        pending = self.mempool.get_pending(tx_hash)
        if pending and relay_id not in pending.confirmed_by:
            pending.confirmed_by.add(relay_id)

    def _check_consensus(self, tx_hash: str) -> Tuple[bool, str]:
        """检查是否达成共识"""
        if tx_hash not in self.consensus_states:
            return False, "交易不在共识表中"

        consensus = self.consensus_states[tx_hash]

        # 检查是否达到确认阈值
        if consensus.confirmations >= self.confirmation_threshold:
            consensus.state = ConsensusState.CONFIRMED
            consensus.confirmed_at = time.time()

            # 提交到账本
            ok, msg = self.mempool.commit_tx(tx_hash)
            if ok:
                self._trigger_consensus_reached(tx_hash)
                return True, f"共识达成：{consensus.confirmations}个中继确认"
            else:
                consensus.state = ConsensusState.REJECTED
                return False, f"账本提交失败: {msg}"

        # 检查是否达到拒绝阈值
        if consensus.rejections >= self.rejection_threshold:
            consensus.state = ConsensusState.REJECTED
            self.mempool.reject_tx(tx_hash, "多数派拒绝")
            return True, f"交易被拒绝：{consensus.rejections}个中继拒绝"

        return True, f"等待确认：{consensus.confirmations}/{self.confirmation_threshold}"

    def _broadcast_validation_request(self, tx: Tx):
        """广播验证请求"""
        if self.on_broadcast:
            self.on_broadcast({
                "type": "validation_request",
                "tx": tx.to_dict(),
                "relay_id": self.relay_id
            })

    def _trigger_consensus_reached(self, tx_hash: str):
        """触发共识达成回调"""
        if self.on_consensus_reached:
            tx = self.mempool.ledger.get_tx(tx_hash)
            if tx:
                self.on_consensus_reached(tx)

    # ────────────────────────────────────────────────────────────────
    # 节点管理
    # ────────────────────────────────────────────────────────────────

    def update_relay_list(self, relays: Set[str]):
        """更新已知中继列表"""
        with self._lock:
            self.known_relays = relays
            self.relay_count = len(relays)

            # 动态调整阈值
            # 确认阈值 = 多数派（>50%）或最小3个
            self.confirmation_threshold = max(3, self.relay_count // 2 + 1)
            self.rejection_threshold = max(2, self.relay_count // 3)

    def get_consensus_state(self, tx_hash: str) -> Optional[TxConsensus]:
        """获取交易共识状态"""
        return self.consensus_states.get(tx_hash)

    def get_pending_consensus(self) -> List[TxConsensus]:
        """获取正在共识中的交易"""
        return [
            c for c in self.consensus_states.values()
            if c.state == ConsensusState.CONFIRMING
        ]

    # ────────────────────────────────────────────────────────────────
    # 同步支持
    # ────────────────────────────────────────────────────────────────

    def get_consensus_snapshot(self) -> Dict:
        """获取共识快照（用于同步）"""
        return {
            "relay_id": self.relay_id,
            "relay_count": self.relay_count,
            "confirmation_threshold": self.confirmation_threshold,
            "rejection_threshold": self.rejection_threshold,
            "pending_count": len([
                c for c in self.consensus_states.values()
                if c.state == ConsensusState.CONFIRMING
            ])
        }

    def import_votes(self, votes: List[ConsensusVote]) -> int:
        """
        导入外部投票

        Returns:
            处理的投票数量
        """
        processed = 0
        for vote in votes:
            ok, _ = self.receive_vote(vote)
            if ok:
                processed += 1
        return processed

    def cleanup_stale(self, max_age: float = 300) -> int:
        """
        清理过期的共识状态

        Returns:
            清理的数量
        """
        with self._lock:
            now = time.time()
            to_remove = []

            for tx_hash, consensus in self.consensus_states.items():
                if consensus.state == ConsensusState.CONFIRMING:
                    # 检查最老投票的时间
                    if consensus.votes:
                        oldest = min(v.voted_at for v in consensus.votes)
                        if now - oldest > max_age:
                            to_remove.append(tx_hash)

            for tx_hash in to_remove:
                del self.consensus_states[tx_hash]

            return len(to_remove)