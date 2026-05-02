"""
跨租户消息通道 - Cross-Tenant Message Channel

基于事件账本的跨租户数据通道，实现多方不可抵赖的通信

核心思路：
1. 消息即交易：A租户发给B租户的消息 = CROSS_TENANT_MSG 交易
2. 全网记账：A租户发出消息，全网所有节点都会记录
3. 不可抵赖：B租户可以凭 tx_hash 证明"这消息确实是A发的"
4. 幂等性：biz_id 确保同一消息不会被重复处理

对比传统方案：
| 特性 | HTTP回调 | 事件账本通道 |
|------|---------|-------------|
| 不可抵赖 | 需额外签名 | 天然不可篡改 |
| 可靠性 | 依赖网络 | 全网记账 |
| 防重放 | 需业务层处理 | biz_id 天然防重放 |
| 审计追溯 | 需日志系统 | 天然全网审计 |

使用场景：
1. SaaS 多租户系统：A租户给B租户发送业务通知
2. 供应链系统：供应商给采购商发送订单确认
3. 政务系统：部门A给部门B发送协同请求
"""

import time
import threading
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable, Any, Tuple
from decimal import Decimal
from enum import Enum
from collections import defaultdict

from .event_transaction import EventTx, OpType, EventTxBuilder
from .event_ledger import EventLedger


class MessageType(Enum):
    """消息类型"""
    NOTIFICATION = "notification"   # 通知
    REQUEST = "request"           # 请求
    RESPONSE = "response"         # 响应
    CONFIRM = "confirm"           # 确认
    ALERT = "alert"              # 告警


class ReceiptStatus(Enum):
    """回执状态"""
    RECEIVED = "received"        # 已收到
    READ = "read"               # 已读
    PROCESSED = "processed"      # 已处理
    REJECTED = "rejected"       # 已拒绝


@dataclass
class TenantMessage:
    """租户消息"""
    biz_id: str                  # 消息唯一ID
    sender: str                  # 发送者
    sender_tenant: str           # 发送者租户
    recipient: str               # 接收者
    recipient_tenant: str        # 接收者租户

    message_type: MessageType = MessageType.NOTIFICATION
    message: str = ""            # 消息内容
    summary: str = ""            # 消息摘要

    # 交易记录
    send_tx: Optional[EventTx] = None
    receipt_tx: Optional[EventTx] = None

    # 时间
    sent_at: float = 0
    receipt_at: float = 0

    # 回执状态
    receipt_status: ReceiptStatus = ReceiptStatus.RECEIVED

    @property
    def is_received(self) -> bool:
        """是否已收到回执"""
        return self.receipt_tx is not None

    @property
    def latency(self) -> float:
        """消息延迟（秒）"""
        if self.sent_at and self.receipt_at:
            return self.receipt_at - self.sent_at
        return 0


@dataclass
class TenantChannel:
    """租户通道配置"""
    tenant_id: str
    tenant_name: str = ""
    allowed_outgoing: List[str] = field(default_factory=list)
    allowed_incoming: List[str] = field(default_factory=list)
    rate_limit: int = 1000
    is_active: bool = True


class CrossTenantChannel:
    """
    跨租户消息通道

    提供不可抵赖的跨租户通信能力
    """

    def __init__(
        self,
        ledger: EventLedger,
        relay_id: Optional[str] = None,
    ):
        self.ledger = ledger
        self.relay_id = relay_id or "relay_default"

        # 内存缓存
        self._message_cache: Dict[str, TenantMessage] = {}
        self._tenant_config: Dict[str, TenantChannel] = {}
        self._lock = threading.RLock()

        # 回调
        self.on_message_sent: Optional[Callable] = None
        self.on_message_received: Optional[Callable] = None
        self.on_receipt_received: Optional[Callable] = None

        # 预加载
        self._load_existing_messages()

    def _load_existing_messages(self):
        """加载已存在的消息"""
        for tx in self.ledger.txs.values():
            if tx.op_type == OpType.CROSS_TENANT_MSG:
                self._process_sent_message(tx)
            elif tx.op_type == OpType.TENANT_RECEIPT:
                self._process_receipt(tx)

    def _process_sent_message(self, tx: EventTx):
        """处理发送消息交易"""
        metadata = tx.get_metadata()
        msg = TenantMessage(
            biz_id=tx.biz_id,
            sender=tx.user_id,
            sender_tenant=tx.tenant_id,
            recipient=tx.to_user_id or "",
            recipient_tenant=metadata.get("recipient_tenant", ""),
            message_type=MessageType(metadata.get("msg_type", "notification")),
            message=metadata.get("message", ""),
            summary=metadata.get("summary", ""),
            send_tx=tx,
            sent_at=tx.created_at,
        )
        self._message_cache[tx.biz_id] = msg

    def _process_receipt(self, tx: EventTx):
        """处理回执交易"""
        metadata = tx.get_metadata()
        original_biz_id = tx.biz_id

        if original_biz_id in self._message_cache:
            msg = self._message_cache[original_biz_id]
            msg.receipt_tx = tx
            msg.receipt_at = tx.created_at
            msg.receipt_status = ReceiptStatus(metadata.get("receipt_status", "received"))

    def send_message(
        self,
        sender: str,
        sender_tenant: str,
        recipient: str,
        recipient_tenant: str,
        message: str,
        biz_id: Optional[str] = None,
        message_type: MessageType = MessageType.NOTIFICATION,
        summary: str = "",
        skip_receipt: bool = False,
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """发送跨租户消息"""
        with self._lock:
            if not biz_id:
                biz_id = self._generate_message_id(sender, recipient, message)

            if biz_id in self._message_cache:
                existing = self._message_cache[biz_id]
                if existing.send_tx:
                    return False, f"消息已存在: {biz_id}", existing.send_tx

            nonce = self.ledger.get_nonce(sender)
            prev_hash = self.ledger.get_prev_hash(sender)

            tx = EventTxBuilder.build_cross_tenant_msg(
                user_id=sender,
                to_user_id=recipient,
                message=message,
                biz_id=biz_id,
                nonce=nonce,
                prev_tx_hash=prev_hash,
                tenant_id=sender_tenant,
                msg_type=message_type.value,
                relay_id=self.relay_id,
            )

            metadata = tx.get_metadata()
            metadata["recipient_tenant"] = recipient_tenant
            metadata["summary"] = summary or message[:50]
            metadata["skip_receipt"] = skip_receipt
            tx.set_metadata(metadata)

            ok, msg_text = self.ledger.add_tx(tx)
            if not ok:
                return False, f"账本提交失败: {msg_text}", None

            tenant_msg = TenantMessage(
                biz_id=biz_id,
                sender=sender,
                sender_tenant=sender_tenant,
                recipient=recipient,
                recipient_tenant=recipient_tenant,
                message_type=message_type,
                message=message,
                summary=summary or message[:50],
                send_tx=tx,
                sent_at=time.time(),
            )
            self._message_cache[biz_id] = tenant_msg

            if self.on_message_sent:
                try:
                    self.on_message_sent(tenant_msg)
                except Exception:
                    pass

            return True, biz_id, tx

    def send_receipt(
        self,
        recipient: str,
        original_msg_biz_id: str,
        receipt_status: ReceiptStatus = ReceiptStatus.RECEIVED,
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """发送消息回执"""
        with self._lock:
            if original_msg_biz_id not in self._message_cache:
                txs = self.ledger.get_biz_txs(original_msg_biz_id)
                for tx in txs:
                    if tx.op_type == OpType.CROSS_TENANT_MSG:
                        self._process_sent_message(tx)
                        break

            if original_msg_biz_id not in self._message_cache:
                return False, f"原消息不存在: {original_msg_biz_id}", None

            original_msg = self._message_cache[original_msg_biz_id]

            if original_msg.receipt_tx:
                return False, f"已有回执", None

            nonce = self.ledger.get_nonce(recipient)
            prev_hash = self.ledger.get_prev_hash(recipient)

            tx = EventTxBuilder.build_tenant_receipt(
                user_id=recipient,
                original_msg_biz_id=original_msg_biz_id,
                nonce=nonce,
                prev_tx_hash=prev_hash,
                receipt_status=receipt_status.value,
                relay_id=self.relay_id,
            )

            ok, msg_text = self.ledger.add_tx(tx)
            if not ok:
                return False, f"账本提交失败: {msg_text}", None

            original_msg.receipt_tx = tx
            original_msg.receipt_at = time.time()
            original_msg.receipt_status = receipt_status

            return True, "回执已发送", tx

    def get_message(self, biz_id: str) -> Optional[TenantMessage]:
        """获取消息"""
        return self._message_cache.get(biz_id)

    def get_sent_messages(
        self,
        sender: str,
        tenant_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[TenantMessage]:
        """获取发送的消息"""
        messages = []
        for msg in self._message_cache.values():
            if msg.sender != sender:
                continue
            if tenant_id and msg.sender_tenant != tenant_id:
                continue
            if msg.send_tx:
                messages.append(msg)
            if len(messages) >= limit:
                break
        return messages

    def get_received_messages(
        self,
        recipient: str,
        tenant_id: Optional[str] = None,
        unreceived_only: bool = False,
        limit: int = 100,
    ) -> List[TenantMessage]:
        """获取接收的消息"""
        messages = []
        for msg in self._message_cache.values():
            if msg.recipient != recipient:
                continue
            if tenant_id and msg.recipient_tenant != tenant_id:
                continue
            if unreceived_only and msg.is_received:
                continue
            if msg.send_tx:
                messages.append(msg)
            if len(messages) >= limit:
                break
        return messages

    def verify_message(self, biz_id: str) -> Tuple[bool, str, Optional[TenantMessage]]:
        """验证消息真实性"""
        if biz_id not in self._message_cache:
            return False, "消息不存在", None

        msg = self._message_cache[biz_id]
        if not msg.send_tx:
            return False, "消息无交易记录", None

        if not msg.send_tx.verify_hash():
            return False, "消息哈希验证失败", msg

        return True, "消息验证通过", msg

    def register_tenant(self, channel: TenantChannel) -> bool:
        """注册租户通道"""
        with self._lock:
            self._tenant_config[channel.tenant_id] = channel
            return True

    def get_tenant(self, tenant_id: str) -> Optional[TenantChannel]:
        """获取租户配置"""
        return self._tenant_config.get(tenant_id)

    def _generate_message_id(self, sender: str, recipient: str, message: str) -> str:
        """生成消息ID"""
        content = f"{sender}|{recipient}|{message}|{time.time()}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def get_stats(self) -> Dict[str, Any]:
        """获取通道统计"""
        total = len(self._message_cache)
        with_receipt = sum(1 for m in self._message_cache.values() if m.is_received)
        return {
            "total_messages": total,
            "with_receipt": with_receipt,
            "without_receipt": total - with_receipt,
            "receipt_rate": f"{with_receipt / total * 100:.1f}%" if total else "0%",
            "registered_tenants": len(self._tenant_config),
        }