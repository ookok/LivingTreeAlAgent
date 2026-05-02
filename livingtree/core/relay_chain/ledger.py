"""
链式账本 - Chain Ledger

核心组件：
- Ledger: 链式账本，管理所有已确认交易
- AccountLedger: 用户级账本，计算用户余额
- LedgerValidator: 账本验证器

防双花机制：
- nonce 机制确保同一笔交易不能重复入账
- prev_hash 确保交易链完整
- 余额由账本历史计算得出，而非直接修改
"""

import hashlib
import json
import time
import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Set
from decimal import Decimal
from collections import defaultdict

from .transaction import Tx, OpType, TxValidationResult, TxBuilder


@dataclass
class AccountState:
    """账户状态"""
    user_id: str
    balance: Decimal = Decimal("0")
    last_nonce: int = -1  # -1表示无交易
    last_tx_hash: str = ""
    total_in: Decimal = Decimal("0")
    total_out: Decimal = Decimal("0")


class Ledger:
    """
    链式账本

    核心数据结构：
    - tx_index: {tx_hash -> Tx} 交易索引
    - user_txs: {user_id -> [tx_hash,...]} 用户交易列表
    - account_cache: {user_id -> AccountState} 账户缓存

    防双花核心：
    - 每个用户的交易必须按nonce顺序入账
    - prev_tx_hash 必须指向前一笔交易
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path

        # 交易存储
        self.txs: Dict[str, Tx] = {}  # tx_hash -> Tx
        self.tx_order: List[str] = []  # 按确认顺序的交易hash列表

        # 用户交易索引
        self.user_txs: Dict[str, List[str]] = defaultdict(list)

        # 账户状态缓存
        self.account_cache: Dict[str, AccountState] = {}
        self._cache_dirty: Set[str] = set()

        # 链式验证
        self.genesis_hash = self._compute_genesis()
        self._lock = threading.RLock()

    def _compute_genesis(self) -> str:
        """计算创世块哈希"""
        content = f"GENESIS|{time.time()}|HERMES_RELAY_CHAIN"
        return hashlib.sha256(content.encode()).hexdigest()

    def get_genesis(self) -> str:
        """获取创世块哈希"""
        return self.genesis_hash

    # ────────────────────────────────────────────────────────────────
    # 核心操作：添加交易
    # ────────────────────────────────────────────────────────────────

    def add_tx(self, tx: Tx) -> Tuple[bool, str]:
        """
        添加交易到账本

        Returns:
            (success, message)
        """
        with self._lock:
            # 1. 基础校验
            if not tx.verify_hash():
                return False, "交易哈希验证失败"

            # 2. 检查是否已存在
            if tx.tx_hash in self.txs:
                return False, "交易已存在"

            # 3. 获取用户状态
            state = self._get_account_state(tx.user_id)

            # 4. nonce 校验（防重放）
            if tx.nonce != state.last_nonce + 1:
                return False, f"Nonce错误: 期望{state.last_nonce + 1}, 实际{tx.nonce}"

            # 5. prev_hash 校验（链式完整性）
            if tx.nonce > 0 and tx.prev_tx_hash != state.last_tx_hash:
                return False, f"prev_hash不匹配: 期望{state.last_tx_hash[:16]}..., 实际{tx.prev_tx_hash[:16]}..."

            # 6. 余额校验（仅支出类操作）
            if tx.op_type in (OpType.OUT, OpType.TRANSFER_OUT):
                if state.balance < tx.amount:
                    return False, f"余额不足: 余额={state.balance}, 需要={tx.amount}"

            # 7. 写入账本
            return self._commit_tx(tx)

    def _commit_tx(self, tx: Tx) -> Tuple[bool, str]:
        """提交交易到账本"""
        # 更新交易存储
        self.txs[tx.tx_hash] = tx
        self.tx_order.append(tx.tx_hash)

        # 更新用户索引
        self.user_txs[tx.user_id].append(tx.tx_hash)

        # 更新账户状态
        state = self._get_account_state(tx.user_id)
        self._update_account_state(state, tx)

        # 标记缓存脏
        self._cache_dirty.add(tx.user_id)
        if tx.to_user_id:
            self._cache_dirty.add(tx.to_user_id)

        return True, "交易已确认"

    def _update_account_state(self, state: AccountState, tx: Tx):
        """更新账户状态"""
        state.last_nonce = tx.nonce
        state.last_tx_hash = tx.tx_hash

        if tx.op_type in (OpType.IN, OpType.TRANSFER_IN, OpType.RECHARGE):
            state.balance += tx.amount
            state.total_in += tx.amount
        elif tx.op_type in (OpType.OUT, OpType.TRANSFER_OUT):
            state.balance -= tx.amount
            state.total_out += tx.amount

    def _get_account_state(self, user_id: str) -> AccountState:
        """获取账户状态"""
        if user_id not in self.account_cache:
            # 从数据库重建
            state = self._rebuild_account_state(user_id)
            self.account_cache[user_id] = state
        return self.account_cache[user_id]

    def _rebuild_account_state(self, user_id: str) -> AccountState:
        """从账本历史重建账户状态"""
        state = AccountState(user_id=user_id)

        txs = self.user_txs.get(user_id, [])
        for tx_hash in txs:
            tx = self.txs.get(tx_hash)
            if not tx:
                continue
            self._update_account_state(state, tx)

        return state

    # ────────────────────────────────────────────────────────────────
    # 查询操作
    # ────────────────────────────────────────────────────────────────

    def get_balance(self, user_id: str) -> Decimal:
        """获取用户余额"""
        state = self._get_account_state(user_id)
        return state.balance

    def get_nonce(self, user_id: str) -> int:
        """获取用户下一个nonce"""
        state = self._get_account_state(user_id)
        return state.last_nonce + 1

    def get_prev_hash(self, user_id: str) -> str:
        """获取用户上一笔交易hash"""
        state = self._get_account_state(user_id)
        return state.last_tx_hash or self.genesis_hash

    def get_user_txs(self, user_id: str, limit: int = 100, offset: int = 0) -> List[Tx]:
        """获取用户交易历史"""
        tx_hashes = self.user_txs.get(user_id, [])
        result = []
        for i, h in enumerate(tx_hashes[offset:offset + limit]):
            if h in self.txs:
                result.append(self.txs[h])
        return result

    def get_tx(self, tx_hash: str) -> Optional[Tx]:
        """根据hash获取交易"""
        return self.txs.get(tx_hash)

    def get_all_txs(self, limit: int = 100, offset: int = 0) -> List[Tx]:
        """获取所有交易（分页）"""
        result = []
        for h in self.tx_order[offset:offset + limit]:
            if h in self.txs:
                result.append(self.txs[h])
        return result

    def get_stats(self) -> Dict:
        """获取账本统计"""
        total_txs = len(self.txs)
        total_users = len(self.account_cache)
        total_in = sum(s.total_in for s in self.account_cache.values())
        total_out = sum(s.total_out for s in self.account_cache.values())

        return {
            "total_transactions": total_txs,
            "total_users": total_users,
            "total_points_in": float(total_in),
            "total_points_out": float(total_out),
            "circulating": float(total_in - total_out),
            "ledger_hash": self.get_ledger_hash()
        }

    def get_ledger_hash(self) -> str:
        """计算账本哈希（所有交易的根哈希）"""
        if not self.tx_order:
            return self.genesis_hash

        content = "|".join(self.tx_order)
        return hashlib.sha256(content.encode()).hexdigest()

    # ────────────────────────────────────────────────────────────────
    # 验证操作
    # ────────────────────────────────────────────────────────────────

    def validate_tx(self, tx: Tx) -> TxValidationResult:
        """
        验证交易是否有效

        完整验证包括：
        1. 哈希验证
        2. nonce连续性
        3. prev_hash链式完整性
        4. 余额充足性
        """
        warnings = []

        # 1. 哈希验证
        if not tx.verify_hash():
            return TxValidationResult(valid=False, error="交易哈希验证失败")

        # 2. 已存在检查
        if tx.tx_hash in self.txs:
            return TxValidationResult(valid=False, error="交易已存在")

        # 3. 获取账户状态
        state = self._get_account_state(tx.user_id)

        # 4. nonce校验
        if tx.nonce < 0:
            return TxValidationResult(valid=False, error="Nonce不能为负数")

        if tx.nonce != state.last_nonce + 1:
            if tx.nonce <= state.last_nonce:
                return TxValidationResult(valid=False, error=f"Nonce重复: {tx.nonce}")
            return TxValidationResult(valid=False, error=f"Nonce跳跃: 期望{state.last_nonce + 1}, 实际{tx.nonce}")

        # 5. prev_hash校验
        if tx.nonce > 0:
            expected_prev = state.last_tx_hash or self.genesis_hash
            if tx.prev_tx_hash != expected_prev:
                warnings.append(f"prev_hash不匹配（可能需要同步）")

        # 6. 余额校验
        if tx.op_type in (OpType.OUT, OpType.TRANSFER_OUT):
            if state.balance < tx.amount:
                return TxValidationResult(
                    valid=False,
                    error=f"余额不足: 余额={state.balance}, 需要={tx.amount}"
                )

        return TxValidationResult(valid=True, warnings=warnings)

    def verify_chain_integrity(self, user_id: str) -> Tuple[bool, str]:
        """
        验证用户交易链完整性

        Returns:
            (is_valid, error_message)
        """
        txs = self.get_user_txs(user_id, limit=10000)

        if not txs:
            return True, "无交易记录"

        expected_nonce = -1
        expected_prev = self.genesis_hash

        for tx in txs:
            if tx.nonce != expected_nonce + 1:
                return False, f"Nonce不连续: 位置{len(txs)}, 期望nonce={expected_nonce + 1}, 实际={tx.nonce}"

            if tx.prev_tx_hash != expected_prev:
                return False, f"prev_hash断裂: tx={tx.tx_hash[:16]}, 期望prev={expected_prev[:16]}"

            expected_nonce = tx.nonce
            expected_prev = tx.tx_hash

        return True, "链完整性验证通过"

    # ────────────────────────────────────────────────────────────────
    # 同步操作
    # ────────────────────────────────────────────────────────────────

    def export_state(self) -> Dict:
        """导出账本状态（用于同步）"""
        return {
            "genesis_hash": self.genesis_hash,
            "tx_count": len(self.txs),
            "user_count": len(self.account_cache),
            "ledger_hash": self.get_ledger_hash(),
            "last_tx_hash": self.tx_order[-1] if self.tx_order else self.genesis_hash
        }

    def import_txs(self, txs: List[Tx]) -> Tuple[int, int]:
        """
        批量导入交易（用于节点同步）

        Returns:
            (success_count, fail_count)
        """
        success = 0
        fail = 0

        for tx in txs:
            if tx.tx_hash not in self.txs:
                ok, _ = self.add_tx(tx)
                if ok:
                    success += 1
                else:
                    fail += 1
            else:
                success += 1  # 已存在算成功

        return success, fail

    def get_missing_txs(self, remote_order: List[str]) -> List[str]:
        """
        获取本地缺失的交易hash列表

        Args:
            remote_order: 远程节点的交易顺序列表

        Returns:
            本地缺失的tx_hash列表
        """
        local_set = set(self.tx_order)
        missing = []

        for h in remote_order:
            if h not in local_set:
                missing.append(h)

        return missing


class LedgerValidator:
    """账本验证器"""

    def __init__(self, ledger: Ledger):
        self.ledger = ledger

    def validate_full(self) -> Dict[str, any]:
        """完整验证账本"""
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": self.ledger.get_stats()
        }

        # 1. 遍历所有交易验证
        for tx_hash, tx in self.ledger.txs.items():
            if not tx.verify_hash():
                results["valid"] = False
                results["errors"].append(f"交易{tx_hash[:16]}哈希验证失败")

        # 2. 验证每个用户的交易链
        for user_id in self.ledger.user_txs:
            valid, msg = self.ledger.verify_chain_integrity(user_id)
            if not valid:
                results["valid"] = False
                results["errors"].append(f"用户{user_id[:8]}链验证失败: {msg}")

        # 3. 验证账户余额
        for user_id, state in self.ledger.account_cache.items():
            if state.balance < 0:
                results["valid"] = False
                results["errors"].append(f"用户{user_id[:8]}余额为负: {state.balance}")

        return results