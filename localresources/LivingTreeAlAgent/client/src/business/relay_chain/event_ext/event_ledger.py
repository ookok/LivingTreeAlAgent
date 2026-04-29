"""
事件账本 - Event Ledger

泛化的链式账本，支持所有事件类型的统一管理

核心设计：
1. 统一的 EventTx 交易结构
2. 按 OpCategory 分组统计
3. 支持业务级查询（biz_id、tenant_id、asset_type）
4. 完整的防双花验证

防双花机制：
- nonce 机制：同一用户的交易必须按顺序入账
- prev_hash：每笔交易指向前驱，形成哈希链
- biz_id：业务级幂等（任务ID、资产ID、消息ID）
- 余额校验：仅对积分类操作生效
"""

import hashlib
import json
import time
import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Set, Any
from decimal import Decimal
from collections import defaultdict

from .event_transaction import (
    EventTx, OpType, OpCategory, EventValidationResult,
    get_op_category, is_points_op, is_balance_mutating,
    is_im_op, is_file_op
)


@dataclass
class AccountState:
    """账户状态"""
    user_id: str
    balance: Decimal = Decimal("0")
    last_nonce: int = -1  # -1表示无交易
    last_tx_hash: str = ""
    total_in: Decimal = Decimal("0")
    total_out: Decimal = Decimal("0")
    # 扩展字段
    task_count: int = 0       # 累计任务数
    asset_count: int = 0      # 累计资产操作数
    msg_count: int = 0        # 累计消息数


@dataclass
class EventStats:
    """事件统计"""
    total_events: int = 0
    by_category: Dict[str, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)
    by_tenant: Dict[str, int] = field(default_factory=dict)
    by_asset_type: Dict[str, int] = field(default_factory=dict)


class EventLedger:
    """
    事件账本

    统一管理所有类型的事件交易：
    - 积分交易
    - 任务调度
    - 跨租户消息
    - 游戏资产
    - 政务一码通

    核心数据结构：
    - txs: {tx_hash -> EventTx} 交易索引
    - tx_order: [tx_hash, ...] 按确认顺序
    - user_txs: {user_id -> [tx_hash, ...]} 用户交易列表
    - biz_txs: {biz_id -> [tx_hash, ...]} 业务ID索引（任务ID/消息ID）
    - account_cache: {user_id -> AccountState} 账户状态缓存
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path

        # 交易存储
        self.txs: Dict[str, EventTx] = {}  # tx_hash -> EventTx
        self.tx_order: List[str] = []      # 按确认顺序的交易hash列表

        # 索引结构
        self.user_txs: Dict[str, List[str]] = defaultdict(list)  # 用户交易
        self.biz_txs: Dict[str, List[str]] = defaultdict(list)   # 业务ID索引
        self.tenant_txs: Dict[str, List[str]] = defaultdict(list)  # 租户索引
        self.asset_txs: Dict[str, List[str]] = defaultdict(list)  # 资产索引

        # 账户状态缓存
        self.account_cache: Dict[str, AccountState] = {}
        self._cache_dirty: Set[str] = set()

        # 链式验证
        self.genesis_hash = self._compute_genesis()
        self._lock = threading.RLock()

        # 统计
        self.stats = EventStats()

    def _compute_genesis(self) -> str:
        """计算创世块哈希"""
        content = f"GENESIS|{time.time()}|HERMES_EVENT_LEDGER"
        return hashlib.sha256(content.encode()).hexdigest()

    def get_genesis(self) -> str:
        """获取创世块哈希"""
        return self.genesis_hash

    # ───────────────────────────────────────────────────────────
    # 核心操作：添加事件
    # ───────────────────────────────────────────────────────────

    def add_tx(self, tx: EventTx) -> Tuple[bool, str]:
        """
        添加事件到账本

        验证逻辑：
        1. 哈希验证
        2. 已存在检查（防重放）
        3. nonce 校验（防重放）
        4. prev_hash 链式完整性
        5. 余额校验（仅积分类操作）
        6. 业务级幂等检查（biz_id）

        Args:
            tx: 事件交易

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

            # 6. 余额校验（仅积分类支出操作）
            if tx.op_type in (OpType.OUT, OpType.TRANSFER_OUT):
                if state.balance < tx.amount:
                    return False, f"余额不足: 余额={state.balance}, 需要={tx.amount}"

            # 7. 业务级幂等检查（biz_id）
            if tx.biz_id:
                existing = self.biz_txs.get(tx.biz_id, [])
                if existing:
                    # 该业务ID已有交易记录
                    for biz_tx_hash in existing:
                        biz_tx = self.txs.get(biz_tx_hash)
                        if biz_tx and biz_tx.op_type == tx.op_type:
                            return False, f"业务ID重复: {tx.biz_id}，类型{tx.op_type.value}"

            # 8. 提交账本
            return self._commit_tx(tx)

    def _commit_tx(self, tx: EventTx) -> Tuple[bool, str]:
        """提交交易到账本"""
        # 更新交易存储
        self.txs[tx.tx_hash] = tx
        self.tx_order.append(tx.tx_hash)

        # 更新用户索引
        self.user_txs[tx.user_id].append(tx.tx_hash)

        # 更新业务索引
        if tx.biz_id:
            self.biz_txs[tx.biz_id].append(tx.tx_hash)

        # 更新租户索引
        if tx.tenant_id:
            self.tenant_txs[tx.tenant_id].append(tx.tx_hash)

        # 更新资产索引
        if tx.asset_type:
            self.asset_txs[tx.asset_type].append(tx.tx_hash)

        # 更新账户状态
        state = self._get_account_state(tx.user_id)
        self._update_account_state(state, tx)

        # 标记缓存脏
        self._cache_dirty.add(tx.user_id)
        if tx.to_user_id:
            self._cache_dirty.add(tx.to_user_id)

        # 更新统计
        self._update_stats(tx)

        return True, "事件已确认"

    def _update_account_state(self, state: AccountState, tx: EventTx):
        """更新账户状态"""
        state.last_nonce = tx.nonce
        state.last_tx_hash = tx.tx_hash

        # 积分类操作
        if is_points_op(tx.op_type):
            if tx.op_type in (OpType.IN, OpType.TRANSFER_IN, OpType.RECHARGE):
                state.balance += tx.amount
                state.total_in += tx.amount
            elif tx.op_type in (OpType.OUT, OpType.TRANSFER_OUT):
                state.balance -= tx.amount
                state.total_out += tx.amount

        # 任务类操作
        if tx.op_type in (OpType.TASK_DISPATCH, OpType.TASK_EXECUTE, OpType.TASK_COMPLETE):
            state.task_count += 1

        # 消息类操作
        if tx.op_type in (OpType.CROSS_TENANT_MSG, OpType.TENANT_RECEIPT):
            state.msg_count += 1

        # 资产类操作
        if tx.op_type in (OpType.ASSET_GRANT, OpType.ASSET_TRANSFER, OpType.ASSET_CONSUME):
            state.asset_count += 1

    def _update_stats(self, tx: EventTx):
        """更新统计信息"""
        self.stats.total_events += 1

        # 按类型统计
        op_type_key = tx.op_type.value
        self.stats.by_type[op_type_key] = self.stats.by_type.get(op_type_key, 0) + 1

        # 按类别统计
        category = get_op_category(tx.op_type)
        cat_key = category.value
        self.stats.by_category[cat_key] = self.stats.by_category.get(cat_key, 0) + 1

        # 按租户统计
        if tx.tenant_id:
            self.stats.by_tenant[tx.tenant_id] = self.stats.by_tenant.get(tx.tenant_id, 0) + 1

        # 按资产类型统计
        if tx.asset_type:
            self.stats.by_asset_type[tx.asset_type] = self.stats.by_asset_type.get(tx.asset_type, 0) + 1

    def _get_account_state(self, user_id: str) -> AccountState:
        """获取账户状态"""
        if user_id not in self.account_cache:
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

    # ───────────────────────────────────────────────────────────
    # 查询操作
    # ───────────────────────────────────────────────────────────

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

    def get_user_txs(self, user_id: str, limit: int = 100, offset: int = 0) -> List[EventTx]:
        """获取用户交易历史"""
        tx_hashes = self.user_txs.get(user_id, [])
        result = []
        for h in tx_hashes[offset:offset + limit]:
            if h in self.txs:
                result.append(self.txs[h])
        return result

    def get_biz_txs(self, biz_id: str) -> List[EventTx]:
        """根据业务ID获取交易（如任务ID、消息ID）"""
        tx_hashes = self.biz_txs.get(biz_id, [])
        return [self.txs[h] for h in tx_hashes if h in self.txs]

    def get_tenant_txs(self, tenant_id: str, limit: int = 100, offset: int = 0) -> List[EventTx]:
        """获取租户的交易历史"""
        tx_hashes = self.tenant_txs.get(tenant_id, [])
        result = []
        for h in tx_hashes[offset:offset + limit]:
            if h in self.txs:
                result.append(self.txs[h])
        return result

    def get_asset_history(self, asset_id: str) -> List[EventTx]:
        """获取资产的所有操作历史"""
        return self.get_biz_txs(asset_id)

    def get_tx(self, tx_hash: str) -> Optional[EventTx]:
        """根据hash获取交易"""
        return self.txs.get(tx_hash)

    def get_all_txs(self, limit: int = 100, offset: int = 0) -> List[EventTx]:
        """获取所有交易（分页）"""
        result = []
        for h in self.tx_order[offset:offset + limit]:
            if h in self.txs:
                result.append(self.txs[h])
        return result

    def get_stats(self) -> Dict[str, Any]:
        """获取账本统计"""
        total_txs = len(self.txs)
        total_users = len(self.account_cache)
        total_in = sum(s.total_in for s in self.account_cache.values())
        total_out = sum(s.total_out for s in self.account_cache.values())

        return {
            "total_events": total_txs,
            "total_users": total_users,
            "total_points_in": float(total_in),
            "total_points_out": float(total_out),
            "circulating": float(total_in - total_out),
            "ledger_hash": self.get_ledger_hash(),
            "by_category": dict(self.stats.by_category),
            "by_type": dict(self.stats.by_type),
        }

    def get_ledger_hash(self) -> str:
        """计算账本哈希"""
        if not self.tx_order:
            return self.genesis_hash
        content = "|".join(self.tx_order)
        return hashlib.sha256(content.encode()).hexdigest()

    # ───────────────────────────────────────────────────────────
    # 验证操作
    # ───────────────────────────────────────────────────────────

    def validate_tx(self, tx: EventTx) -> EventValidationResult:
        """
        验证交易是否有效

        完整验证包括：
        1. 哈希验证
        2. nonce连续性
        3. prev_hash链式完整性
        4. 余额充足性（仅积分类）
        5. 业务级幂等
        """
        warnings = []
        category = get_op_category(tx.op_type)

        # 1. 哈希验证
        if not tx.verify_hash():
            return EventValidationResult(
                valid=False,
                error="交易哈希验证失败",
                category=category
            )

        # 2. 已存在检查
        if tx.tx_hash in self.txs:
            return EventValidationResult(
                valid=False,
                error="交易已存在",
                category=category
            )

        # 3. 获取账户状态
        state = self._get_account_state(tx.user_id)

        # 4. nonce校验
        if tx.nonce < 0:
            return EventValidationResult(
                valid=False,
                error="Nonce不能为负数",
                category=category
            )

        if tx.nonce != state.last_nonce + 1:
            if tx.nonce <= state.last_nonce:
                return EventValidationResult(
                    valid=False,
                    error=f"Nonce重复: {tx.nonce}",
                    category=category
                )
            return EventValidationResult(
                valid=False,
                error=f"Nonce跳跃: 期望{state.last_nonce + 1}, 实际{tx.nonce}",
                category=category
            )

        # 5. prev_hash校验
        if tx.nonce > 0:
            expected_prev = state.last_tx_hash or self.genesis_hash
            if tx.prev_tx_hash != expected_prev:
                warnings.append(f"prev_hash不匹配（可能需要同步）")

        # 6. 余额校验（仅积分类支出）
        if tx.op_type in (OpType.OUT, OpType.TRANSFER_OUT):
            if state.balance < tx.amount:
                return EventValidationResult(
                    valid=False,
                    error=f"余额不足: 余额={state.balance}, 需要={tx.amount}",
                    category=category
                )

        # 7. 业务级幂等检查
        if tx.biz_id:
            existing = self.biz_txs.get(tx.biz_id, [])
            for biz_tx_hash in existing:
                biz_tx = self.txs.get(biz_tx_hash)
                if biz_tx and biz_tx.op_type == tx.op_type:
                    return EventValidationResult(
                        valid=False,
                        error=f"业务ID重复: {tx.biz_id}",
                        category=category
                    )

        return EventValidationResult(valid=True, warnings=warnings, category=category)

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

    # ───────────────────────────────────────────────────────────
    # 同步操作
    # ───────────────────────────────────────────────────────────

    def export_state(self) -> Dict:
        """导出账本状态（用于同步）"""
        return {
            "genesis_hash": self.genesis_hash,
            "tx_count": len(self.txs),
            "user_count": len(self.account_cache),
            "ledger_hash": self.get_ledger_hash(),
            "last_tx_hash": self.tx_order[-1] if self.tx_order else self.genesis_hash,
            "stats": {
                "by_category": dict(self.stats.by_category),
                "by_type": dict(self.stats.by_type),
            }
        }

    def import_txs(self, txs: List[EventTx]) -> Tuple[int, int]:
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
        """获取本地缺失的交易hash列表"""
        local_set = set(self.tx_order)
        missing = []
        for h in remote_order:
            if h not in local_set:
                missing.append(h)
        return missing


class EventLedgerValidator:
    """事件账本验证器"""

    def __init__(self, ledger: EventLedger):
        self.ledger = ledger

    def validate_full(self) -> Dict[str, Any]:
        """完整验证账本"""
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": self.ledger.get_stats()
        }

        # 1. 遍历所有交易验证哈希
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

    def validate_task_chain(self, task_id: str) -> Tuple[bool, str, List[EventTx]]:
        """
        验证任务链完整性

        一个完整的任务流程应该是：
        DISPATCH -> EXECUTE -> COMPLETE/CANCEL

        Returns:
            (is_valid, message, task_txs)
        """
        txs = self.ledger.get_biz_txs(task_id)

        if not txs:
            return False, f"任务{task_id}不存在", []

        # 按nonce排序
        txs_sorted = sorted(txs, key=lambda x: x.nonce)

        # 检查操作类型序列
        op_sequence = [tx.op_type for tx in txs_sorted]

        # 基本验证：必须有DISPATCH
        if OpType.TASK_DISPATCH not in op_sequence:
            return False, f"任务{task_id}缺少派发记录", txs_sorted

        # 检查是否有重复的操作（除了DISPATCH）
        for op_type in [OpType.TASK_EXECUTE, OpType.TASK_COMPLETE, OpType.TASK_CANCEL]:
            count = op_sequence.count(op_type)
            if count > 1:
                return False, f"任务{task_id}有重复的{op_type.value}操作", txs_sorted

        return True, "任务链完整", txs_sorted

    def validate_asset_chain(self, asset_id: str) -> Tuple[bool, str, List[EventTx]]:
        """
        验证资产链完整性

        资产流转：GRANT -> TRANSFER/CONSUME

        Returns:
            (is_valid, message, asset_txs)
        """
        txs = self.ledger.get_asset_history(asset_id)

        if not txs:
            return False, f"资产{asset_id}不存在", []

        txs_sorted = sorted(txs, key=lambda x: x.nonce)

        # 检查是否有GRANT
        op_sequence = [tx.op_type for tx in txs_sorted]
        if OpType.ASSET_GRANT not in op_sequence:
            return False, f"资产{asset_id}缺少发放记录", txs_sorted

        return True, "资产链完整", txs_sorted