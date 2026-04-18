"""
Credit Recharge Service - 积分充值与VIP系统
============================================

功能：
1. 用户充值获得积分（1元 = 10积分）
2. 首次充值奖励（首充额外+50%积分）
3. VIP特权系统（充值满额升级）
4. VIP每日赠送积分

设计原则：
- 积分即货币：积分是系统内的虚拟货币
- 阶梯等级：VIP等级根据累计充值金额划分
- 每日赠送：VIP用户每日可领取赠送积分
"""

import os
import uuid
import time
import json
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
import asyncio


# ============ 枚举定义 ============

class VIPLevel(str, Enum):
    """VIP等级"""
    NONE = "none"       # 非VIP
    VIP1 = "vip1"       # VIP1
    VIP2 = "vip2"       # VIP2
    VIP3 = "vip3"       # VIP3
    VIP4 = "vip4"       # VIP4
    VIP5 = "vip5"       # VIP5

    @property
    def level_value(self) -> int:
        """等级数值（用于比较）"""
        mapping = {
            VIPLevel.NONE: 0,
            VIPLevel.VIP1: 1,
            VIPLevel.VIP2: 2,
            VIPLevel.VIP3: 3,
            VIPLevel.VIP4: 4,
            VIPLevel.VIP5: 5,
        }
        return mapping.get(self, 0)

    @property
    def daily_bonus(self) -> int:
        """每日赠送积分"""
        mapping = {
            VIPLevel.NONE: 0,
            VIPLevel.VIP1: 10,
            VIPLevel.VIP2: 30,
            VIPLevel.VIP3: 80,
            VIPLevel.VIP4: 200,
            VIPLevel.VIP5: 500,
        }
        return mapping.get(self, 0)

    @property
    def min_recharge(self) -> float:
        """升级到此等级需要的最低累计充值（元）"""
        mapping = {
            VIPLevel.NONE: 0,
            VIPLevel.VIP1: 100,
            VIPLevel.VIP2: 500,
            VIPLevel.VIP3: 1000,
            VIPLevel.VIP4: 5000,
            VIPLevel.VIP5: 10000,
        }
        return mapping.get(self, 0)


class TransactionType(str, Enum):
    """积分交易类型"""
    RECHARGE = "recharge"             # 充值
    DAILY_BONUS = "daily_bonus"       # 每日赠送
    FIRST_RECHARGE_BONUS = "first_recharge_bonus"  # 首充奖励
    VIP_UPGRADE_BONUS = "vip_upgrade_bonus"        # 升级奖励
    CONSUME = "consume"               # 消费
    EXPIRE = "expire"                # 过期


# ============ 积分配置 ============

@dataclass
class CreditConfig:
    """积分系统配置"""
    # 充值比例
    credits_per_yuan: float = 10.0   # 1元 = 10积分

    # 首次充值奖励
    first_recharge_bonus_rate: float = 0.5  # 首充额外50%

    # VIP升级奖励
    vip_upgrade_bonus: Dict[str, int] = field(default_factory=lambda: {
        "vip1": 100,
        "vip2": 300,
        "vip3": 800,
        "vip4": 2000,
        "vip5": 5000,
    })

    # VIP每日赠送配置
    vip_daily_bonus: Dict[str, int] = field(default_factory=lambda: {
        "vip1": 10,
        "vip2": 30,
        "vip3": 80,
        "vip4": 200,
        "vip5": 500,
    })

    # 每日赠送领取间隔（秒）
    daily_bonus_interval: int = 86400  # 24小时

    # 数据目录
    data_dir: Path = field(default_factory=lambda: Path.home() / ".hermes-desktop" / "relay_server" / "credits")


# ============ 数据模型 ============

@dataclass
class CreditAccount:
    """积分账户"""
    user_id: str
    balance: int = 0                      # 积分余额
    total_recharged: float = 0.0         # 累计充值金额（元）
    total_earned: int = 0                 # 累计获得积分
    total_consumed: int = 0               # 累计消耗积分
    vip_level: VIPLevel = VIPLevel.NONE   # VIP等级
    is_first_recharge_done: bool = False  # 是否已完成首充
    last_daily_bonus_at: Optional[int] = None  # 上次领取每日赠送的时间
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "balance": self.balance,
            "total_recharged": self.total_recharged,
            "total_earned": self.total_earned,
            "total_consumed": self.total_consumed,
            "vip_level": self.vip_level.value if isinstance(self.vip_level, VIPLevel) else self.vip_level,
            "is_first_recharge_done": self.is_first_recharge_done,
            "last_daily_bonus_at": self.last_daily_bonus_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class CreditTransaction:
    """积分交易记录"""
    transaction_id: str
    user_id: str
    type: TransactionType
    amount: int                           # 积分数量（正数收入，负数支出）
    balance_after: int                    # 交易后余额
    related_order_id: Optional[str] = None  # 关联订单ID
    description: str = ""
    created_at: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "user_id": self.user_id,
            "type": self.type.value if isinstance(self.type, TransactionType) else self.type,
            "amount": self.amount,
            "balance_after": self.balance_after,
            "related_order_id": self.related_order_id,
            "description": self.description,
            "created_at": self.created_at,
        }


@dataclass
class DailyBonusRecord:
    """每日赠送记录"""
    record_id: str
    user_id: str
    vip_level: str
    bonus_amount: int
    given_at: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "user_id": self.user_id,
            "vip_level": self.vip_level,
            "bonus_amount": self.bonus_amount,
            "given_at": self.given_at,
        }


# ============ VIP等级计算 ============

def calculate_vip_level(total_recharged: float) -> VIPLevel:
    """根据累计充值金额计算VIP等级"""
    if total_recharged >= 10000:
        return VIPLevel.VIP5
    elif total_recharged >= 5000:
        return VIPLevel.VIP4
    elif total_recharged >= 1000:
        return VIPLevel.VIP3
    elif total_recharged >= 500:
        return VIPLevel.VIP2
    elif total_recharged >= 100:
        return VIPLevel.VIP1
    else:
        return VIPLevel.NONE


# ============ 存储层 ============

class CreditStorage:
    """积分数据存储"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.accounts_file = data_dir / "accounts.json"
        self.transactions_file = data_dir / "transactions.json"
        self.bonus_records_file = data_dir / "bonus_records.json"

        for f in [self.accounts_file, self.transactions_file, self.bonus_records_file]:
            if not f.exists():
                f.write_text("{}", encoding="utf-8")

    def _load_json(self, file: Path) -> Dict[str, Any]:
        try:
            return json.loads(file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_json(self, file: Path, data: Dict[str, Any]):
        file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ============ 账户操作 ============

    def get_account(self, user_id: str) -> Optional[CreditAccount]:
        data = self._load_json(self.accounts_file)
        if user_id in data:
            d = data[user_id]
            d["vip_level"] = VIPLevel(d["vip_level"]) if isinstance(d["vip_level"], str) else d["vip_level"]
            return CreditAccount(**d)
        return None

    def save_account(self, account: CreditAccount):
        account.updated_at = int(time.time())
        data = self._load_json(self.accounts_file)
        data[account.user_id] = account.to_dict()
        self._save_json(self.accounts_file, data)

    def get_or_create_account(self, user_id: str) -> CreditAccount:
        account = self.get_account(user_id)
        if account is None:
            account = CreditAccount(user_id=user_id)
            self.save_account(account)
        return account

    # ============ 交易记录操作 ============

    def add_transaction(self, tx: CreditTransaction):
        data = self._load_json(self.transactions_file)
        if tx.user_id not in data:
            data[tx.user_id] = []
        data[tx.user_id].append(tx.to_dict())
        self._save_json(self.transactions_file, data)

    def get_transactions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        tx_type: Optional[TransactionType] = None
    ) -> List[CreditTransaction]:
        data = self._load_json(self.transactions_file)
        txs = data.get(user_id, [])

        if tx_type:
            txs = [t for t in txs if t.get("type") == tx_type.value]

        txs = sorted(txs, key=lambda x: x.get("created_at", 0), reverse=True)
        return [CreditTransaction(**t) for t in txs[offset:offset + limit]]

    # ============ 每日赠送记录 ============

    def add_bonus_record(self, record: DailyBonusRecord):
        data = self._load_json(self.bonus_records_file)
        if record.user_id not in data:
            data[record.user_id] = []
        data[record.user_id].append(record.to_dict())
        self._save_json(self.bonus_records_file, data)

    def get_latest_bonus(self, user_id: str) -> Optional[DailyBonusRecord]:
        data = self._load_json(self.bonus_records_file)
        records = data.get(user_id, [])
        if records:
            latest = sorted(records, key=lambda x: x.get("given_at", 0), reverse=True)[0]
            return DailyBonusRecord(**latest)
        return None


# ============ 积分充值服务 ============

class CreditRechargeService:
    """积分充值服务"""

    def __init__(self, storage: CreditStorage, config: Optional[CreditConfig] = None):
        self.storage = storage
        self.config = config or CreditConfig()

    def _generate_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"

    # ============ 核心充值方法 ============

    def recharge(
        self,
        user_id: str,
        amount: float,
        order_id: Optional[str] = None
    ) -> Tuple[int, Optional[CreditAccount], str]:
        """
        用户充值

        Args:
            user_id: 用户ID
            amount: 充值金额（元）
            order_id: 关联订单ID

        Returns:
            (实际到账积分, 更新后的账户, 错误信息)
        """
        if amount <= 0:
            return 0, None, "充值金额必须大于0"

        # 获取或创建账户
        account = self.storage.get_or_create_account(user_id)

        # 计算基础积分
        base_credits = int(amount * self.config.credits_per_yuan)

        # 计算奖励积分
        bonus_credits = 0
        bonus_description = ""

        # 首次充值奖励
        if not account.is_first_recharge_done:
            bonus_credits += int(base_credits * self.config.first_recharge_bonus_rate)
            account.is_first_recharge_done = True
            bonus_description = f"首次充值奖励+{int(self.config.first_recharge_bonus_rate * 100)}%"

        # 计算新的VIP等级
        new_total = account.total_recharged + amount
        new_vip = calculate_vip_level(new_total)

        # VIP升级奖励
        if new_vip.level_value > account.vip_level.level_value:
            upgrade_bonus = self.config.vip_upgrade_bonus.get(new_vip.value, 0)
            bonus_credits += upgrade_bonus
            if bonus_description:
                bonus_description += f"，升级{new_vip.value}奖励+{upgrade_bonus}"
            else:
                bonus_description = f"升级{new_vip.value}奖励+{upgrade_bonus}"

        # 总到账积分
        total_credits = base_credits + bonus_credits

        # 更新账户
        account.balance += total_credits
        account.total_recharged = new_total
        account.total_earned += total_credits
        account.vip_level = new_vip

        # 记录基础充值积分
        self._record_transaction(
            user_id=user_id,
            tx_type=TransactionType.RECHARGE,
            amount=base_credits,
            balance_after=account.balance,
            related_order_id=order_id,
            description=f"充值{amount}元"
        )

        # 记录首充奖励
        if not account.is_first_recharge_done and account.is_first_recharge_done:
            # 首次充值奖励已经在上面标记，这里记录
            pass  # 已在上面处理

        # 记录VIP升级奖励
        if new_vip.level_value > 0:
            upgrade_bonus = self.config.vip_upgrade_bonus.get(new_vip.value, 0)
            if upgrade_bonus > 0:
                self._record_transaction(
                    user_id=user_id,
                    tx_type=TransactionType.VIP_UPGRADE_BONUS,
                    amount=upgrade_bonus,
                    balance_after=account.balance,
                    related_order_id=order_id,
                    description=f"升级{new_vip.value}奖励"
                )

        self.storage.save_account(account)

        return total_credits, account, ""

    def _record_transaction(
        self,
        user_id: str,
        tx_type: TransactionType,
        amount: int,
        balance_after: int,
        related_order_id: Optional[str] = None,
        description: str = ""
    ):
        """记录交易"""
        tx = CreditTransaction(
            transaction_id=self._generate_id("tx"),
            user_id=user_id,
            type=tx_type,
            amount=amount,
            balance_after=balance_after,
            related_order_id=related_order_id,
            description=description,
        )
        self.storage.add_transaction(tx)

    # ============ 每日赠送 ============

    def claim_daily_bonus(self, user_id: str) -> Tuple[int, Optional[CreditAccount], str]:
        """
        领取每日赠送积分

        Returns:
            (获得积分数, 更新后的账户, 错误信息)
        """
        account = self.storage.get_account(user_id)
        if not account:
            return 0, None, "账户不存在"

        if account.vip_level == VIPLevel.NONE:
            return 0, account, "非VIP用户，无法领取每日赠送"

        now = int(time.time())
        bonus_amount = account.vip_level.daily_bonus

        # 检查是否已经领取过
        if account.last_daily_bonus_at:
            elapsed = now - account.last_daily_bonus_at
            if elapsed < self.config.daily_bonus_interval:
                remaining = self.config.daily_bonus_interval - elapsed
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                return 0, account, f"每日赠送已领取，请 {hours}小时{minutes}分钟 后再试"

        # 发放每日赠送
        account.balance += bonus_amount
        account.total_earned += bonus_amount
        account.last_daily_bonus_at = now

        # 记录交易
        self._record_transaction(
            user_id=user_id,
            tx_type=TransactionType.DAILY_BONUS,
            amount=bonus_amount,
            balance_after=account.balance,
            description=f"{account.vip_level.value}每日赠送"
        )

        # 记录赠送记录
        bonus_record = DailyBonusRecord(
            record_id=self._generate_id("br"),
            user_id=user_id,
            vip_level=account.vip_level.value,
            bonus_amount=bonus_amount,
        )
        self.storage.add_bonus_record(bonus_record)

        self.storage.save_account(account)

        return bonus_amount, account, ""

    # ============ 积分消费 ============

    def consume(
        self,
        user_id: str,
        amount: int,
        description: str = ""
    ) -> Tuple[bool, Optional[CreditAccount], str]:
        """
        消费积分

        Returns:
            (是否成功, 更新后的账户, 错误信息)
        """
        if amount <= 0:
            return False, None, "消费积分必须大于0"

        account = self.storage.get_account(user_id)
        if not account:
            return False, None, "账户不存在"

        if account.balance < amount:
            return False, account, f"积分不足（当前余额: {account.balance}，需要: {amount}）"

        # 扣减积分
        account.balance -= amount
        account.total_consumed += amount

        # 记录交易
        self._record_transaction(
            user_id=user_id,
            tx_type=TransactionType.CONSUME,
            amount=-amount,
            balance_after=account.balance,
            description=description or "积分消费"
        )

        self.storage.save_account(account)

        return True, account, ""

    # ============ 查询方法 ============

    def get_account(self, user_id: str) -> Optional[CreditAccount]:
        """获取账户信息"""
        return self.storage.get_account(user_id)

    def get_or_create_account(self, user_id: str) -> CreditAccount:
        """获取或创建账户"""
        return self.storage.get_or_create_account(user_id)

    def get_transactions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        tx_type: Optional[str] = None
    ) -> List[CreditTransaction]:
        """获取交易记录"""
        type_enum = TransactionType(tx_type) if tx_type else None
        return self.storage.get_transactions(user_id, limit, offset, type_enum)

    def get_vip_info(self, account: CreditAccount) -> Dict[str, Any]:
        """获取VIP详细信息"""
        current = account.vip_level
        next_level = None
        need_more = 0.0

        # 计算下一个等级
        level_order = [VIPLevel.NONE, VIPLevel.VIP1, VIPLevel.VIP2, VIPLevel.VIP3, VIPLevel.VIP4, VIPLevel.VIP5]
        current_idx = level_order.index(current)
        if current_idx < len(level_order) - 1:
            next_level = level_order[current_idx + 1]
            need_more = next_level.min_recharge - account.total_recharged

        return {
            "current_level": current.value,
            "current_level_name": current.value.upper(),
            "daily_bonus": current.daily_bonus,
            "total_recharged": account.total_recharged,
            "next_level": next_level.value if next_level else None,
            "next_level_name": next_level.value.upper() if next_level else None,
            "next_level_daily_bonus": next_level.daily_bonus if next_level else 0,
            "need_more_to_upgrade": max(0, need_more),
            "can_claim_daily_bonus": current != VIPLevel.NONE,
            "daily_bonus_available": self._can_claim_daily_bonus(account),
            "next_claim_in_seconds": self._get_next_claim_seconds(account),
        }

    def _can_claim_daily_bonus(self, account: CreditAccount) -> bool:
        """检查是否可以领取每日赠送"""
        if account.vip_level == VIPLevel.NONE:
            return False
        if not account.last_daily_bonus_at:
            return True
        return (int(time.time()) - account.last_daily_bonus_at) >= self.config.daily_bonus_interval

    def _get_next_claim_seconds(self, account: CreditAccount) -> int:
        """获取距离下次可领取的秒数"""
        if account.vip_level == VIPLevel.NONE:
            return 0
        if not account.last_daily_bonus_at:
            return 0
        elapsed = int(time.time()) - account.last_daily_bonus_at
        remaining = self.config.daily_bonus_interval - elapsed
        return max(0, remaining)


# ============ VIP每日赠送定时器 ============

class VIPDailyBonusScheduler:
    """VIP每日赠送定时器"""

    def __init__(self, credit_service: CreditRechargeService, check_interval: int = 3600):
        self.credit_service = credit_service
        self.check_interval = check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """启动定时器"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        print(f"[VIP每日赠送定时器] 已启动，每 {self.check_interval} 秒检查一次")

    async def stop(self):
        """停止定时器"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("[VIP每日赠送定时器] 已停止")

    async def _run(self):
        """运行定时检查"""
        while self._running:
            try:
                await self._check_and_notify()
            except Exception as e:
                print(f"[VIP每日赠送定时器] 检查出错: {e}")

            await asyncio.sleep(self.check_interval)

    async def _check_and_notify(self):
        """检查并通知VIP用户"""
        # 这里可以实现更复杂的逻辑，比如发送通知给VIP用户
        # 目前只是记录日志
        pass


# ============ 单例管理 ============

_credit_storage: Optional[CreditStorage] = None
_credit_service: Optional[CreditRechargeService] = None
_credit_config: Optional[CreditConfig] = None


def get_credit_config() -> CreditConfig:
    global _credit_config
    if _credit_config is None:
        _credit_config = CreditConfig()
    return _credit_config


def get_credit_storage() -> CreditStorage:
    global _credit_storage
    if _credit_storage is None:
        _credit_storage = CreditStorage(get_credit_config().data_dir)
    return _credit_storage


def get_credit_service() -> CreditRechargeService:
    global _credit_service
    if _credit_service is None:
        _credit_service = CreditRechargeService(get_credit_storage(), get_credit_config())
    return _credit_service


def get_vip_daily_bonus_scheduler() -> VIPDailyBonusScheduler:
    return VIPDailyBonusScheduler(get_credit_service())
