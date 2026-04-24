"""
积分事务账本 (Transaction Ledger)
====================================

为每次积分交易创建不可篡改的记录，实现：
1. 积分消耗追溯
2. 余额核对
3. 异常检测
4. 审计报表

与 EventLedger 的 event_ext 集成：
- CREDIT_DEBIT / CREDIT_REWARD 等事件类型
- 每条消息都是一条链式记账
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from threading import RLock
import time
import hashlib
import json
from core.logger import get_logger
logger = get_logger('credit_economy.transaction_ledger')



class TransactionType(Enum):
    """积分交易类型"""
    # 消费类
    TASK_EXECUTION = "task_execution"     # 任务执行扣积分
    API_CALL = "api_call"                 # API调用扣积分
    RESOURCE_USAGE = "resource_usage"     # 资源使用扣积分

    # 充值类
    RECHARGE = "recharge"                 # 充值
    REWARD = "reward"                    # 奖励
    REFERRAL_BONUS = "referral_bonus"    # 推荐奖励
    ACTIVITY_BONUS = "activity_bonus"    # 活动奖励

    # 转移类
    TRANSFER_IN = "transfer_in"          # 转入
    TRANSFER_OUT = "transfer_out"        # 转出
    GIFT = "gift"                         # 赠送

    # 特殊类
    REFUND = "refund"                    # 退款
    COMPENSATION = "compensation"       # 补偿
    ADMIN_ADJUSTMENT = "admin_adjustment" # 管理员调整

    # 学习类
    PREDICTION_REWARD = "prediction_reward"  # 预测准确奖励
    QUALITY_BONUS = "quality_bonus"          # 质量达标奖励


class TransactionStatus(Enum):
    """交易状态"""
    PENDING = "pending"                   # 待确认
    CONFIRMED = "confirmed"              # 已确认
    FAILED = "failed"                    # 失败
    REVERSED = "reversed"                # 已撤销


@dataclass
class Transaction:
    """
    积分交易记录

    每笔交易都会产生一条不可篡改的记录。
    """
    # 基础信息
    tx_id: str                            # 交易ID（哈希）
    tx_type: TransactionType
    status: TransactionStatus
    user_id: str                         # 用户ID
    amount: float                        # 交易金额（正数）

    # 可选字段（带默认值）
    account_id: str = "default"           # 账户ID
    balance_before: float = 0.0          # 交易前余额
    balance_after: float = 0.0           # 交易后余额

    # 关联
    task_id: Optional[str] = None        # 关联任务ID
    plugin_id: Optional[str] = None       # 关联插件ID
    workflow_id: Optional[str] = None    # 关联工作流ID

    # 详情
    description: str = ""                # 交易描述
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 链式结构
    prev_tx_hash: str = ""                # 前一笔交易的哈希
    tx_hash: str = ""                    # 本交易的哈希

    # 时间戳
    created_at: float = field(default_factory=time.time)
    confirmed_at: Optional[float] = None

    def generate_hash(self) -> str:
        """生成交易哈希"""
        content = f"{self.tx_id}|{self.tx_type.value}|{self.user_id}|{self.amount}|{self.created_at}|{self.prev_tx_hash}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def confirm(self) -> bool:
        """确认交易"""
        if self.status != TransactionStatus.PENDING:
            return False
        self.status = TransactionStatus.CONFIRMED
        self.confirmed_at = time.time()
        self.tx_hash = self.generate_hash()
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tx_id": self.tx_id,
            "tx_type": self.tx_type.value,
            "status": self.status.value,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "amount": self.amount,
            "balance_before": self.balance_before,
            "balance_after": self.balance_after,
            "task_id": self.task_id,
            "plugin_id": self.plugin_id,
            "workflow_id": self.workflow_id,
            "description": self.description,
            "metadata": self.metadata,
            "prev_tx_hash": self.prev_tx_hash,
            "tx_hash": self.tx_hash,
            "created_at": self.created_at,
            "confirmed_at": self.confirmed_at,
        }


@dataclass
class Account:
    """积分账户"""
    user_id: str
    account_id: str = "default"
    balance: float = 0.0
    total_earned: float = 0.0            # 累计获得
    total_spent: float = 0.0             # 累计消耗
    created_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "account_id": self.account_id,
            "balance": self.balance,
            "total_earned": self.total_earned,
            "total_spent": self.total_spent,
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
        }


class TransactionLedger:
    """
    积分事务账本

    核心职责：
    1. 记录所有积分交易
    2. 管理账户余额
    3. 验证交易完整性
    4. 生成审计报表
    """

    _instance = None
    _lock = RLock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 账户
        self._accounts: Dict[str, Account] = {}  # (user_id, account_id) -> Account

        # 交易记录
        self._transactions: List[Transaction] = []

        # 链式哈希
        self._last_tx_hash: str = "genesis"

        # 观察者
        self._observers: Dict[str, List[Callable]] = {}

        # 初始化默认账户
        self._init_default_accounts()

    def _init_default_accounts(self):
        """初始化默认账户"""
        # 系统账户（用于奖励、补偿等）
        self._accounts[("system", "reward")] = Account(
            user_id="system",
            account_id="reward",
            balance=1000000.0,
        )

        # 系统账户（用于冻结、托管等）
        self._accounts[("system", "escrow")] = Account(
            user_id="system",
            account_id="escrow",
            balance=0.0,
        )

    @classmethod
    def get_instance(cls) -> 'TransactionLedger':
        return cls()

    # ==================== 账户管理 ====================

    def get_or_create_account(
        self,
        user_id: str,
        account_id: str = "default",
        initial_balance: float = 0.0
    ) -> Account:
        """获取或创建账户"""
        key = (user_id, account_id)
        if key not in self._accounts:
            self._accounts[key] = Account(
                user_id=user_id,
                account_id=account_id,
                balance=initial_balance,
            )
        return self._accounts[key]

    def get_account(self, user_id: str, account_id: str = "default") -> Optional[Account]:
        """获取账户"""
        return self._accounts.get((user_id, account_id))

    def get_balance(self, user_id: str, account_id: str = "default") -> float:
        """获取余额"""
        account = self.get_account(user_id, account_id)
        return account.balance if account else 0.0

    # ==================== 交易操作 ====================

    def record_transaction(
        self,
        tx_type: TransactionType,
        user_id: str,
        amount: float,
        account_id: str = "default",
        task_id: Optional[str] = None,
        plugin_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        auto_confirm: bool = True
    ) -> Transaction:
        """
        记录交易

        Args:
            tx_type: 交易类型
            user_id: 用户ID
            amount: 交易金额（正数）
            account_id: 账户ID
            task_id: 关联任务ID
            plugin_id: 关联插件ID
            workflow_id: 关联工作流ID
            description: 描述
            metadata: 额外数据
            auto_confirm: 是否自动确认

        Returns:
            交易记录
        """
        with self._lock:
            # 获取/创建账户
            account = self.get_or_create_account(user_id, account_id)

            # 生成交易ID
            tx_id = self._generate_tx_id(tx_type, user_id, amount)

            # 确定状态
            status = TransactionStatus.CONFIRMED if auto_confirm else TransactionStatus.PENDING

            # 计算余额变化
            is_debit = tx_type in [
                TransactionType.TASK_EXECUTION,
                TransactionType.API_CALL,
                TransactionType.RESOURCE_USAGE,
                TransactionType.TRANSFER_OUT,
            ]

            balance_before = account.balance
            if is_debit:
                if account.balance < amount:
                    # 余额不足，但仍然记录（允许负余额，需后续处理）
                    pass
                account.balance -= amount
                account.total_spent += amount
            else:
                account.balance += amount
                account.total_earned += amount

            account.last_active_at = time.time()

            # 创建交易记录
            tx = Transaction(
                tx_id=tx_id,
                tx_type=tx_type,
                status=status,
                user_id=user_id,
                account_id=account_id,
                amount=amount,
                balance_before=balance_before,
                balance_after=account.balance,
                task_id=task_id,
                plugin_id=plugin_id,
                workflow_id=workflow_id,
                description=description,
                metadata=metadata or {},
                prev_tx_hash=self._last_tx_hash,
            )

            if auto_confirm:
                tx.tx_hash = tx.generate_hash()
                self._last_tx_hash = tx.tx_hash
                tx.confirmed_at = time.time()

            # 保存
            self._transactions.append(tx)

            # 通知观察者
            self._notify_observers("transaction_recorded", tx)

            return tx

    def _generate_tx_id(
        self,
        tx_type: TransactionType,
        user_id: str,
        amount: float
    ) -> str:
        """生成交易ID"""
        timestamp = time.time()
        content = f"{tx_type.value}|{user_id}|{amount}|{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def confirm_transaction(self, tx_id: str) -> bool:
        """确认交易"""
        with self._lock:
            for tx in reversed(self._transactions):
                if tx.tx_id == tx_id:
                    if tx.status != TransactionStatus.PENDING:
                        return False
                    tx.confirm()
                    self._last_tx_hash = tx.tx_hash
                    self._notify_observers("transaction_confirmed", tx)
                    return True
            return False

    def reverse_transaction(self, tx_id: str, reason: str = "") -> Optional[Transaction]:
        """撤销交易"""
        with self._lock:
            for tx in reversed(self._transactions):
                if tx.tx_id == tx_id:
                    if tx.status == TransactionStatus.REVERSED:
                        return None

                    # 创建反向交易
                    reverse_tx = self.record_transaction(
                        tx_type=TransactionType.REFUND if tx.amount > 0 else TransactionType.RECHARGE,
                        user_id=tx.user_id,
                        amount=tx.amount,
                        account_id=tx.account_id,
                        task_id=tx.task_id,
                        plugin_id=tx.plugin_id,
                        description=f"撤销: {tx.description}，原因: {reason}",
                        metadata={"reversed_tx_id": tx_id},
                    )

                    tx.status = TransactionStatus.REVERSED
                    return reverse_tx
            return None

    # ==================== 便捷方法 ====================

    def deduct(
        self,
        user_id: str,
        amount: float,
        task_id: str,
        plugin_id: str,
        description: str = "",
        account_id: str = "default"
    ) -> Transaction:
        """扣减积分"""
        return self.record_transaction(
            tx_type=TransactionType.TASK_EXECUTION,
            user_id=user_id,
            amount=amount,
            account_id=account_id,
            task_id=task_id,
            plugin_id=plugin_id,
            description=description or f"任务执行: {task_id}",
        )

    def reward(
        self,
        user_id: str,
        amount: float,
        reason: str,
        source: str = "system",
        account_id: str = "default"
    ) -> Transaction:
        """奖励积分"""
        return self.record_transaction(
            tx_type=TransactionType.REWARD,
            user_id=user_id,
            amount=amount,
            account_id=account_id,
            description=reason,
            metadata={"source": source},
        )

    def recharge(
        self,
        user_id: str,
        amount: float,
        source: str = "manual",
        account_id: str = "default"
    ) -> Transaction:
        """充值"""
        return self.record_transaction(
            tx_type=TransactionType.RECHARGE,
            user_id=user_id,
            amount=amount,
            account_id=account_id,
            description=f"充值: {source}",
            metadata={"source": source},
        )

    # ==================== 查询 ====================

    def get_transactions(
        self,
        user_id: Optional[str] = None,
        tx_type: Optional[TransactionType] = None,
        status: Optional[TransactionStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Transaction]:
        """查询交易记录"""
        result = self._transactions

        if user_id:
            result = [tx for tx in result if tx.user_id == user_id]
        if tx_type:
            result = [tx for tx in result if tx.tx_type == tx_type]
        if status:
            result = [tx for tx in result if tx.status == status]

        # 逆序（最新的在前）
        result = list(reversed(result))

        return result[offset:offset+limit]

    def get_user_summary(self, user_id: str) -> Dict[str, Any]:
        """获取用户摘要"""
        transactions = self.get_transactions(user_id=user_id, limit=1000)

        total_earned = 0.0
        total_spent = 0.0
        by_type: Dict[str, float] = {}

        for tx in transactions:
            if tx.tx_type in [TransactionType.RECHARGE, TransactionType.REWARD, TransactionType.TRANSFER_IN]:
                total_earned += tx.amount
            elif tx.tx_type in [TransactionType.TASK_EXECUTION, TransactionType.API_CALL]:
                total_spent += tx.amount

            type_key = tx.tx_type.value
            by_type[type_key] = by_type.get(type_key, 0) + tx.amount

        account = self.get_account(user_id)

        return {
            "user_id": user_id,
            "balance": account.balance if account else 0.0,
            "total_earned": total_earned,
            "total_spent": total_spent,
            "transaction_count": len(transactions),
            "by_type": by_type,
        }

    # ==================== 审计 ====================

    def verify_integrity(self) -> Dict[str, Any]:
        """验证账本完整性"""
        issues = []
        prev_hash = "genesis"

        for i, tx in enumerate(self._transactions):
            if tx.prev_tx_hash != prev_hash:
                issues.append(f"交易 {tx.tx_id} 的前驱哈希不匹配")

            if tx.status == TransactionStatus.CONFIRMED and not tx.tx_hash:
                issues.append(f"交易 {tx.tx_id} 已确认但无哈希")

            prev_hash = tx.tx_hash if tx.tx_hash else tx.generate_hash()

        return {
            "is_valid": len(issues) == 0,
            "transaction_count": len(self._transactions),
            "issues": issues,
        }

    def generate_audit_report(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """生成审计报表"""
        transactions = self._transactions

        if start_time:
            transactions = [tx for tx in transactions if tx.created_at >= start_time]
        if end_time:
            transactions = [tx for tx in transactions if tx.created_at <= end_time]

        # 按用户汇总
        by_user: Dict[str, Dict] = {}
        for tx in transactions:
            if tx.user_id not in by_user:
                by_user[tx.user_id] = {"earned": 0, "spent": 0, "count": 0}
            by_user[tx.user_id]["count"] += 1
            if tx.tx_type in [TransactionType.RECHARGE, TransactionType.REWARD]:
                by_user[tx.user_id]["earned"] += tx.amount
            elif tx.tx_type in [TransactionType.TASK_EXECUTION, TransactionType.API_CALL]:
                by_user[tx.user_id]["spent"] += tx.amount

        # 按类型汇总
        by_type: Dict[str, int] = {}
        for tx in transactions:
            by_type[tx.tx_type.value] = by_type.get(tx.tx_type.value, 0) + 1

        return {
            "period": {
                "start": start_time,
                "end": end_time,
            },
            "summary": {
                "total_transactions": len(transactions),
                "total_users": len(by_user),
            },
            "by_user": by_user,
            "by_type": by_type,
        }

    # ==================== 观察者 ====================

    def add_observer(self, event_type: str, callback: Callable) -> None:
        """添加观察者"""
        if event_type not in self._observers:
            self._observers[event_type] = []
        self._observers[event_type].append(callback)

    def _notify_observers(self, event_type: str, data: Any) -> None:
        """通知观察者"""
        for callback in self._observers.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                logger.info(f"Ledger observer error: {e}")

    # ==================== 导出 ====================

    def export_json(self) -> str:
        """导出为JSON"""
        data = {
            "accounts": {
                f"{k[0]}_{k[1]}": v.to_dict()
                for k, v in self._accounts.items()
            },
            "transactions": [tx.to_dict() for tx in self._transactions],
            "last_tx_hash": self._last_tx_hash,
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def import_json(self, json_str: str) -> bool:
        """从JSON导入"""
        try:
            data = json.loads(json_str)
            # 重建账户
            for key, v in data.get("accounts", {}).items():
                parts = key.split("_", 1)
                if len(parts) == 2:
                    self._accounts[(parts[0], parts[1])] = Account(**v)
            # 重建交易
            for tx_data in data.get("transactions", []):
                tx_data["tx_type"] = TransactionType(tx_data["tx_type"])
                tx_data["status"] = TransactionStatus(tx_data["status"])
                self._transactions.append(Transaction(**tx_data))
            return True
        except Exception as e:
            logger.info(f"Import error: {e}")
            return False


def get_transaction_ledger() -> TransactionLedger:
    """获取账本单例"""
    return TransactionLedger.get_instance()
