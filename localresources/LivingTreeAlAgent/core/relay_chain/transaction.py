"""
交易数据结构 - Transaction Data Structures

定义积分系统的核心交易数据结构，包括：
- Tx: 积分交易
- TxHash: 交易哈希计算
- OpType: 操作类型（IN/OUT）
"""

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from enum import Enum
from decimal import Decimal


class OpType(Enum):
    """操作类型"""
    IN = "IN"           # 积分收入（后台发放）
    OUT = "OUT"         # 积分支出（消费）
    TRANSFER_IN = "TRANSFER_IN"   # 转账收入
    TRANSFER_OUT = "TRANSFER_OUT" # 转账支出
    RECHARGE = "RECHARGE"         # 充值（微信/支付宝回调）


@dataclass
class Tx:
    """
    积分交易

    字段说明：
    - tx_hash: 交易哈希，是本笔交易的唯一标识
    - prev_tx_hash: 用户上一笔交易的哈希，用于构建哈希链
    - user_id: 用户ID
    - op_type: 操作类型
    - amount: 交易金额（正数）
    - nonce: 用户级自增序号，防重放
    - to_user_id: 目标用户ID（转账用）
    - memo: 交易备注
    - created_at: 创建时间戳
    - signature: 签名（可选）
    - relay_id: 受理中继ID
    """
    user_id: str
    op_type: OpType
    amount: Decimal

    # 链式结构
    prev_tx_hash: str = ""  # 上一笔交易的hash，空表示第一笔

    # 交易ID
    nonce: int = 0  # 用户级自增序号

    # 目标（转账用）
    to_user_id: Optional[str] = None

    # 元数据
    memo: str = ""
    created_at: float = field(default_factory=time.time)
    relay_id: Optional[str] = None

    # 派生字段
    tx_hash: str = ""  # 交易哈希，由系统计算
    signature: str = ""  # 签名
    payment_order_id: str = ""  # 支付订单号（充值用，幂等性检查）

    def __post_init__(self):
        """初始化后计算tx_hash"""
        if not self.tx_hash:
            self.tx_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """计算交易哈希"""
        content = (
            f"{self.user_id}|{self.op_type.value}|{self.amount}|{self.nonce}|"
            f"{self.prev_tx_hash}|{self.to_user_id or ''}|{self.payment_order_id or ''}|{self.created_at}"
        )
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        d = asdict(self)
        d['op_type'] = self.op_type.value
        d['amount'] = str(self.amount)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Tx':
        """从字典创建"""
        d = d.copy()
        d['op_type'] = OpType(d['op_type'])
        d['amount'] = Decimal(d['amount'])
        return cls(**d)

    def to_json(self) -> str:
        """序列化为JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> 'Tx':
        """从JSON反序列化"""
        return cls.from_dict(json.loads(s))

    def verify_hash(self) -> bool:
        """验证哈希是否正确"""
        expected = self._compute_hash()
        return self.tx_hash == expected

    def __str__(self) -> str:
        op_symbol = "+" if self.op_type in (OpType.IN, OpType.TRANSFER_IN) else "-"
        return f"Tx({self.tx_hash[:8]}... {self.user_id[:8]}... {op_symbol}{self.amount} nonce={self.nonce})"


@dataclass
class TxValidationResult:
    """交易校验结果"""
    valid: bool
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "error": self.error,
            "warnings": self.warnings
        }


@dataclass
class TxConfirm:
    """交易确认信息"""
    tx_hash: str
    relay_id: str
    confirmed_at: float = field(default_factory=time.time)
    block_height: int = 0


class TxBuilder:
    """交易构建器"""

    @staticmethod
    def build_transfer(
        from_user: str,
        to_user: str,
        amount: Decimal,
        nonce: int,
        prev_tx_hash: str,
        memo: str = "",
        relay_id: Optional[str] = None
    ) -> Tx:
        """构建转账交易"""
        return Tx(
            user_id=from_user,
            op_type=OpType.TRANSFER_OUT,
            amount=amount,
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            to_user_id=to_user,
            memo=memo,
            relay_id=relay_id
        )

    @staticmethod
    def build_grant(
        user_id: str,
        amount: Decimal,
        nonce: int,
        prev_tx_hash: str,
        memo: str = "",
        relay_id: Optional[str] = None
    ) -> Tx:
        """构建积分发放交易"""
        return Tx(
            user_id=user_id,
            op_type=OpType.IN,
            amount=amount,
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            memo=f"积分发放: {memo}",
            relay_id=relay_id
        )

    @staticmethod
    def build_consume(
        user_id: str,
        amount: Decimal,
        nonce: int,
        prev_tx_hash: str,
        memo: str = "",
        relay_id: Optional[str] = None
    ) -> Tx:
        """构建积分消费交易"""
        return Tx(
            user_id=user_id,
            op_type=OpType.OUT,
            amount=amount,
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            memo=f"积分消费: {memo}",
            relay_id=relay_id
        )

    @staticmethod
    def build_recharge(
        user_id: str,
        amount: Decimal,
        nonce: int,
        prev_tx_hash: str,
        payment_order_id: str,
        payment_channel: str = "wechat",
        memo: str = "",
        relay_id: Optional[str] = None
    ) -> Tx:
        """
        构建充值交易（微信/支付宝回调）

        Args:
            user_id: 用户ID
            amount: 充值金额
            nonce: 用户交易序号
            prev_tx_hash: 用户上一笔交易hash
            payment_order_id: 支付订单号（用于幂等性检查）
            payment_channel: 支付渠道（wechat/alipay/bank）
            memo: 备注
            relay_id: 受理中继ID
        """
        return Tx(
            user_id=user_id,
            op_type=OpType.RECHARGE,
            amount=amount,
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            payment_order_id=payment_order_id,
            memo=f"充值:{payment_channel}|订单:{payment_order_id}|{memo}",
            relay_id=relay_id
        )