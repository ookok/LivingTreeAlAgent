"""
LivingTree Relay 中继链数据模型
================================

精简合并 relay_chain (35文件) + relay_router (5文件) + decentralized_mailbox (14文件) 
的核心数据模型，消除三套独立定义中的冗余。

核心概念:
- Tx: 交易/事件记录，带 nonce + prev_hash 防双花
- LedgerEntry: 账本条目，基于交易链计算余额
- RelayNode: 中继节点信息
- ConsensusVote: 共识投票
- MailMessage: 邮件消息（继承自 P2P 消息）

Author: LivingTreeAI Team
Version: 1.0.0 (精简统一版)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import json
import time


# ============================================================================
# 枚举
# ============================================================================

class OpType(str, Enum):
    """操作类型"""
    CREDIT_IN = "credit_in"          # 积分收入
    CREDIT_OUT = "credit_out"        # 积分支出
    TRANSFER = "transfer"            # 转账
    RECHARGE = "recharge"            # 充值
    REWARD = "reward"                # 奖励
    TASK_PAYMENT = "task_payment"    # 任务支付
    SYSTEM = "system"                # 系统操作


class TxStatus(str, Enum):
    """交易状态"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    EXPIRED = "expired"
    REVERSED = "reversed"


class NodeRole(str, Enum):
    """节点角色"""
    RELAY = "relay"          # 中继节点
    CLIENT = "client"        # 客户端
    VALIDATOR = "validator"  # 验证者
    TRACKER = "tracker"      # 跟踪器


class ConsensusState(str, Enum):
    """共识状态"""
    PROPOSED = "proposed"
    VOTING = "voting"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class MessageChannel(str, Enum):
    """消息通道"""
    P2P_DIRECT = "p2p_direct"
    RELAY = "relay"
    EXTERNAL = "external"     # IMAP/SMTP
    INTERNAL = "internal"     # .tree 内部


class MessageStatus(str, Enum):
    """消息投递状态"""
    QUEUED = "queued"
    SENDING = "sending"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    BOUNCED = "bounced"


# ============================================================================
# 交易数据模型
# ============================================================================

@dataclass
class Tx:
    """
    交易记录

    双花防护: nonce + prev_hash 链式验证
    每个账户的交易形成单向链表, 篡改任一交易会破坏哈希链
    """
    tx_id: str = ""
    sender_id: str = ""            # 发送方 node_id
    receiver_id: str = ""          # 接收方 node_id
    op_type: OpType = OpType.CREDIT_IN
    amount: float = 0.0
    nonce: int = 0                 # 发送方交易序号
    prev_hash: str = ""            # 前一笔交易哈希
    timestamp: datetime = field(default_factory=datetime.now)
    status: TxStatus = TxStatus.PENDING
    relay_id: str = ""             # 确认此交易的中继节点
    signature: str = ""            # 发送方签名
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_hash(self) -> str:
        """计算交易哈希"""
        content = (
            f"{self.sender_id}:{self.receiver_id}:{self.op_type.value}:"
            f"{self.amount}:{self.nonce}:{self.prev_hash}:"
            f"{self.timestamp.isoformat()}"
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def is_valid_chain(self, prev_tx: Optional["Tx"]) -> bool:
        """验证链式关系"""
        if prev_tx is None:
            return self.prev_hash == "" and self.nonce == 0
        return (
            self.nonce == prev_tx.nonce + 1
            and self.prev_hash == prev_tx.compute_hash()
        )


@dataclass
class LedgerEntry:
    """账本条目"""
    account_id: str
    balance: float = 0.0
    total_in: float = 0.0
    total_out: float = 0.0
    tx_count: int = 0
    last_tx_hash: str = ""
    last_nonce: int = -1
    updated_at: datetime = field(default_factory=datetime.now)


# ============================================================================
# 共识数据模型
# ============================================================================

@dataclass
class ConsensusVote:
    """共识投票"""
    vote_id: str = ""
    tx_id: str = ""
    voter_id: str = ""             # 投票节点 ID
    accept: bool = True
    confidence: float = 1.0        # 置信度 (0-1)
    comment: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    signature: str = ""


@dataclass
class ConsensusResult:
    """共识结果"""
    tx_id: str
    state: ConsensusState
    accept_count: int = 0
    reject_count: int = 0
    total_voters: int = 0
    votes: List[ConsensusVote] = field(default_factory=list)
    decided_at: Optional[datetime] = None

    @property
    def is_accepted(self) -> bool:
        return self.state == ConsensusState.ACCEPTED

    @property
    def acceptance_rate(self) -> float:
        if self.total_voters == 0:
            return 0.0
        return self.accept_count / self.total_voters

    @property
    def has_majority(self) -> bool:
        """是否达成多数共识 (>50%)"""
        return self.acceptance_rate > 0.5


# ============================================================================
# 节点与健康数据模型
# ============================================================================

@dataclass
class RelayNode:
    """中继节点信息"""
    node_id: str
    role: NodeRole = NodeRole.RELAY
    host: str = "0.0.0.0"
    port: int = 8888
    is_active: bool = True
    is_healthy: bool = True
    priority: int = 0               # 优先级 (越高越优先)
    load_score: float = 0.0         # 负载分数 (0=空闲, 1=满载)
    latency_ms: float = 0.0
    failure_count: int = 0
    max_failures: int = 5
    last_heartbeat: Optional[datetime] = None
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def record_success(self, latency_ms: float = 0) -> None:
        """记录成功"""
        self.failure_count = 0
        self.is_healthy = True
        self.latency_ms = (self.latency_ms * 0.7 + latency_ms * 0.3)  # EWMA
        self.last_heartbeat = datetime.now()

    def record_failure(self) -> None:
        """记录失败"""
        self.failure_count += 1
        if self.failure_count >= self.max_failures:
            self.is_healthy = False
        self.last_heartbeat = datetime.now()

    def is_available(self, max_latency_ms: float = 500.0) -> bool:
        """判断节点是否可用"""
        return (
            self.is_active
            and self.is_healthy
            and self.latency_ms <= max_latency_ms
        )


@dataclass
class HealthReport:
    """健康报告"""
    node_id: str
    is_healthy: bool
    checked_at: datetime = field(default_factory=datetime.now)
    latency_ms: float = 0.0
    error_message: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# 消息数据模型
# ============================================================================

@dataclass
class MailMessage:
    """
    统一邮件消息模型

    合并 decentralized_mailbox 的消息模型 + relay 的消息传输
    """
    msg_id: str = ""
    sender_id: str = ""
    recipient_ids: List[str] = field(default_factory=list)
    subject: str = ""
    body: str = ""
    channel: MessageChannel = MessageChannel.P2P_DIRECT
    status: MessageStatus = MessageStatus.QUEUED
    priority: int = 0
    has_attachments: bool = False
    attachment_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        sender_id: str,
        recipients: List[str],
        subject: str,
        body: str,
        channel: MessageChannel = MessageChannel.P2P_DIRECT,
        priority: int = 0,
    ) -> "MailMessage":
        raw = f"{sender_id}:{','.join(recipients)}:{subject}:{datetime.now().isoformat()}"
        msg_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return cls(
            msg_id=msg_id,
            sender_id=sender_id,
            recipient_ids=recipients,
            subject=subject,
            body=body,
            channel=channel,
            priority=priority,
        )

    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries

    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_id": self.msg_id,
            "sender_id": self.sender_id,
            "recipient_ids": self.recipient_ids,
            "subject": self.subject,
            "body": self.body,
            "channel": self.channel.value,
            "status": self.status.value,
            "priority": self.priority,
            "has_attachments": self.has_attachments,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MailMessage":
        return cls(
            msg_id=data.get("msg_id", ""),
            sender_id=data.get("sender_id", ""),
            recipient_ids=data.get("recipient_ids", []),
            subject=data.get("subject", ""),
            body=data.get("body", ""),
            channel=MessageChannel(data.get("channel", "p2p_direct")),
            status=MessageStatus(data.get("status", "queued")),
            priority=data.get("priority", 0),
            has_attachments=data.get("has_attachments", False),
            metadata=data.get("metadata", {}),
        )


# ============================================================================
# 序列化工具
# ============================================================================

def serialize_tx(tx: Tx) -> bytes:
    """序列化交易"""
    return json.dumps({
        "tx_id": tx.tx_id,
        "sender_id": tx.sender_id,
        "receiver_id": tx.receiver_id,
        "op_type": tx.op_type.value,
        "amount": tx.amount,
        "nonce": tx.nonce,
        "prev_hash": tx.prev_hash,
        "timestamp": tx.timestamp.isoformat(),
        "relay_id": tx.relay_id,
        "signature": tx.signature,
        "metadata": tx.metadata,
    }, ensure_ascii=False).encode("utf-8")

def deserialize_tx(data: bytes) -> Tx:
    """反序列化交易"""
    d = json.loads(data.decode("utf-8"))
    return Tx(
        tx_id=d.get("tx_id", ""),
        sender_id=d.get("sender_id", ""),
        receiver_id=d.get("receiver_id", ""),
        op_type=OpType(d.get("op_type", "credit_in")),
        amount=d.get("amount", 0.0),
        nonce=d.get("nonce", 0),
        prev_hash=d.get("prev_hash", ""),
        timestamp=datetime.fromisoformat(d["timestamp"]) if d.get("timestamp") else datetime.now(),
        status=TxStatus(d.get("status", "pending")),
        relay_id=d.get("relay_id", ""),
        signature=d.get("signature", ""),
        metadata=d.get("metadata", {}),
    )


__all__ = [
    # 枚举
    "OpType", "TxStatus", "NodeRole", "ConsensusState",
    "MessageChannel", "MessageStatus",
    # 交易
    "Tx", "LedgerEntry",
    # 共识
    "ConsensusVote", "ConsensusResult",
    # 节点
    "RelayNode", "HealthReport",
    # 消息
    "MailMessage",
    # 序列化
    "serialize_tx", "deserialize_tx",
]
