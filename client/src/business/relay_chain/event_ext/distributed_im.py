"""
分布式 IM 模块 - Distributed IM

消息即交易，每条消息都是一条链式记账。

核心设计：
1. 消息账本：每条消息都是 EventTx，消息 ID 作为 biz_id
2. 会话链：每个会话（私聊/群聊）都有独立的哈希链
3. 签名验证：消息发送者必须签名，接收者验证签名
4. Gossip 传播：消息广播给邻居节点，邻居节点继续传播
5. 消息回执：接收者发送 MSG_RECEIPT 交易确认已读

架构分层：
├── Micro Relay（微中继）：手机/浏览器，仅存储相关消息链
├── Super Node（超级节点）：中继服务器，全量消息存储 + 最终一致性仲裁
└── Gossip Protocol：邻居节点间消息扩散

适用场景：
- 私聊：A -> B 的消息，A和B各自有独立的交易链
- 群聊：群里广播消息，所有群成员共享群消息链
- 政务通知：政府 -> 市民的消息，可验证真伪
- 企业内部 IM：去中心化，无单点故障

与传统 IM 的区别：
| 维度 | 传统 IM | 分布式 IM |
|------|---------|----------|
| 存储 | 服务器中心化存储 | 链式账本，全网同步 |
| 消息溯源 | 服务器说了算 | 哈希链可验证 |
| 删除/编辑 | 服务器可篡改 | 只能追加 EDIT/DELETE 交易 |
| 离线消息 | 依赖服务器 | Gossip 延迟，但最终可达 |
| 单点故障 | 服务器挂了全挂 | 节点自组网，抗瘫 |
"""

import hashlib
import json
import time
import uuid
import secrets
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Set, Tuple, Any, Callable
from enum import Enum
from collections import defaultdict
from threading import RLock

from .event_transaction import OpType, OpCategory, EventTx, EventValidationResult
from .event_ledger import EventLedger


# ═══════════════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════════════

class ConversationType(Enum):
    """会话类型"""
    PRIVATE = "PRIVATE"           # 私聊：1对1
    GROUP = "GROUP"               # 群聊：N对N
    CHANNEL = "CHANNEL"           # 频道：1对N（发布-订阅）
    BROADCAST = "BROADCAST"       # 广播：1对全网


class MessageType(Enum):
    """消息类型"""
    TEXT = "TEXT"                 # 文本消息
    IMAGE = "IMAGE"               # 图片
    FILE = "FILE"                # 文件
    AUDIO = "AUDIO"              # 语音
    VIDEO = "VIDEO"               # 视频
    LOCATION = "LOCATION"         # 位置
    CARD = "CARD"                 # 名片/卡券
    SYSTEM = "SYSTEM"             # 系统消息


class ReceiptType(Enum):
    """回执类型"""
    SENT = "SENT"                 # 已发送（消息已到达服务器）
    DELIVERED = "DELIVERED"       # 已送达（消息已到达接收者设备）
    READ = "READ"                 # 已读


@dataclass
class Message:
    """
    消息结构

    注意：这是业务层的消息视图，发送到链上时会转换为 EventTx
    """
    msg_id: str                   # 消息唯一ID（biz_id）
    sender: str                   # 发送者 user_id
    conversation_id: str          # 会话ID
    conversation_type: ConversationType  # 会话类型

    content: str                  # 消息内容
    msg_type: MessageType = MessageType.TEXT  # 消息类型

    # 扩展
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展元数据
    reply_to: Optional[str] = None  # 回复的消息ID
    reactions: List[Dict] = field(default_factory=list)  # 反应（emoji）

    # 引用消息（编辑用）
    edit_ref: Optional[str] = None  # 被编辑的消息ID
    delete_ref: Optional[str] = None  # 被删除的消息ID

    # 媒体信息
    media_url: Optional[str] = None
    media_hash: Optional[str] = None
    media_size: int = 0

    # 时间戳
    created_at: float = field(default_factory=time.time)
    updated_at: Optional[float] = None

    def to_event_tx(self, user_id: str, prev_tx_hash: str, nonce: int) -> EventTx:
        """转换为 EventTx"""
        content_json = json.dumps({
            "msg_id": self.msg_id,
            "content": self.content,
            "msg_type": self.msg_type.value,
            "conversation_id": self.conversation_id,
            "conversation_type": self.conversation_type.value,
            "reply_to": self.reply_to,
            "reactions": self.reactions,
            "metadata": self.metadata,
            "media_url": self.media_url,
            "media_hash": self.media_hash,
            "media_size": self.media_size,
            "created_at": self.created_at,
        }, ensure_ascii=False)

        return EventTx(
            tx_hash="",  # 待计算
            prev_tx_hash=prev_tx_hash,
            user_id=user_id,
            op_type=OpType.MSG_SEND,
            amount=1,
            biz_id=self.msg_id,
            to_user_id=self._get_recipient_user_id(),
            metadata=content_json,
        )

    def _get_recipient_user_id(self) -> Optional[str]:
        """获取接收者 user_id（私聊用）"""
        if self.conversation_type == ConversationType.PRIVATE:
            # 私聊：conversation_id 格式为 "userA_userB"
            parts = self.conversation_id.split("_")
            for p in parts:
                if p != self.sender:
                    return p
        return None


@dataclass
class Conversation:
    """
    会话结构
    """
    conv_id: str                  # 会话ID
    conv_type: ConversationType   # 会话类型
    name: str                     # 会话名称（群名/频道名）
    owner: str                    # 创建者

    # 成员
    members: Set[str] = field(default_factory=set)  # 成员 user_id 集合

    # 链信息（每个成员都有独立的交易链）
    member_chains: Dict[str, str] = field(default_factory=dict)  # user_id -> 最后一条 tx_hash

    # 统计
    msg_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # 设置
    is_encrypted: bool = False    # 是否端到端加密
    max_members: int = 500       # 最大成员数


@dataclass
class UserProfile:
    """用户资料（简化版）"""
    user_id: str
    display_name: str
    avatar_url: Optional[str] = None
    public_key: Optional[str] = None  # 用于签名验证

    # 设备管理
    devices: Dict[str, str] = field(default_factory=dict)  # device_id -> device_key

    # 状态
    is_online: bool = False
    last_seen: float = 0


# ═══════════════════════════════════════════════════════════════════════════════
# Gossip 协议
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class GossipMessage:
    """Gossip 协议消息"""
    msg_type: str                 # GOSSIP_ANNOUNCE / GOSSIP_REQUEST / GOSSIP_RESPONSE
    sender_node_id: str           # 发送节点ID
    tx_hashes: List[str] = field(default_factory=list)  # 消息 tx_hash 列表
    txs: List[EventTx] = field(default_factory=list)  # 完整的交易数据
    conversation_id: Optional[str] = None  # 关联的会话ID
    timestamp: float = field(default_factory=time.time)
    ttl: int = 3                  # 传播跳数


class GossipNode:
    """
    Gossip 协议节点

    负责：
    1. 与邻居节点建立连接
    2. 广播新消息
    3. 同步缺失的消息
    4. 恶意节点检测
    """

    def __init__(
        self,
        node_id: str,
        ledger: 'DistributedIM',
        max_neighbors: int = 5,
        gossip_interval: float = 1.0,
    ):
        self.node_id = node_id
        self.ledger = ledger
        self.max_neighbors = max_neighbors
        self.gossip_interval = gossip_interval

        # 邻居节点
        self.neighbors: Dict[str, Dict] = {}  # node_id -> {addr, last_seen, score}

        # 待传播队列
        self.pending_gossip: List[GossipMessage] = []
        self.seen_messages: Set[str] = set()  # 已传播过的 tx_hash

        # 统计
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
        }

        self._lock = RLock()
        self._running = False

    def add_neighbor(self, node_id: str, addr: str, port: int = 0):
        """添加邻居节点"""
        with self._lock:
            self.neighbors[node_id] = {
                "addr": addr,
                "port": port,
                "last_seen": time.time(),
                "score": 1.0,
            }
            # 保持邻居数量上限
            if len(self.neighbors) > self.max_neighbors:
                self._prune_neighbors()

    def _prune_neighbors(self):
        """修剪低评分邻居"""
        sorted_neighbors = sorted(
            self.neighbors.items(),
            key=lambda x: x[1]["score"],
            reverse=True
        )
        self.neighbors = dict(sorted_neighbors[:self.max_neighbors])

    def broadcast(self, tx: EventTx, conversation_id: Optional[str] = None):
        """广播消息到邻居节点"""
        with self._lock:
            if tx.tx_hash in self.seen_messages:
                return

            self.seen_messages.add(tx.tx_hash)

            gossip_msg = GossipMessage(
                msg_type="GOSSIP_ANNOUNCE",
                sender_node_id=self.node_id,
                tx_hashes=[tx.tx_hash],
                txs=[tx],
                conversation_id=conversation_id,
                ttl=3,
            )

            self.pending_gossip.append(gossip_msg)
            self.stats["messages_sent"] += 1

    def get_missing_txs(self, known_hashes: List[str]) -> List[str]:
        """获取缺失的交易"""
        missing = []
        for h in known_hashes:
            if h not in self.ledger.txs:
                missing.append(h)
        return missing

    def handle_gossip(self, msg: GossipMessage) -> List[EventTx]:
        """
        处理收到的 Gossip 消息

        Returns:
            需要继续传播的新的交易列表
        """
        new_txs = []

        with self._lock:
            self.stats["messages_received"] += 1

            for tx in msg.txs:
                if tx.tx_hash in self.seen_messages:
                    continue

                # 验证交易
                result = self.ledger.validate_tx(tx)
                if result.valid:
                    self.ledger.add_tx(tx)
                    new_txs.append(tx)
                    self.seen_messages.add(tx.tx_hash)

        # 继续传播
        if new_txs and msg.ttl > 0:
            msg.ttl -= 1
            self.pending_gossip.append(msg)

        return new_txs

    def run_gossip_round(self):
        """执行一轮 Gossip"""
        with self._lock:
            if not self.pending_gossip:
                return

            msg = self.pending_gossip.pop(0)
            msg.ttl -= 1

            if msg.ttl <= 0:
                return

            # 发送到所有邻居
            for neighbor_id, neighbor in self.neighbors.items():
                # 实际发送需要网络层，这里简化处理
                pass

    def get_status(self) -> Dict[str, Any]:
        """获取节点状态"""
        with self._lock:
            return {
                "node_id": self.node_id,
                "neighbor_count": len(self.neighbors),
                "pending_gossip": len(self.pending_gossip),
                "seen_messages": len(self.seen_messages),
                "stats": self.stats.copy(),
            }


# ═══════════════════════════════════════════════════════════════════════════════
# 分布式 IM 核心
# ═══════════════════════════════════════════════════════════════════════════════

class DistributedIM:
    """
    分布式 IM 核心类

    核心功能：
    1. 消息发送/接收/存储
    2. 会话管理（私聊/群聊）
    3. 消息签名验证
    4. Gossip 传播
    5. 消息回执

    使用示例：
    ```python
    from business.relay_chain import DistributedIM

    # 初始化（使用现有账本）
    im = DistributedIM(existing_ledger)

    # 创建私聊会话
    conv_id = im.create_conversation(
        conv_type=ConversationType.PRIVATE,
        name="Alice & Bob",
        owner="alice",
        members={"alice", "bob"}
    )

    # 发送消息
    msg = im.send_message(
        sender="alice",
        conversation_id=conv_id,
        content="你好 Bob！"
    )

    # Bob 收到消息并发送已读回执
    receipt = im.send_receipt(
        user_id="bob",
        msg_id=msg.msg_id,
        receipt_type=ReceiptType.READ
    )
    ```
    """

    def __init__(self, ledger: Optional[EventLedger] = None):
        """
        Args:
            ledger: 现有的 EventLedger 实例，如果为 None 则创建新的
        """
        self.ledger = ledger or EventLedger()

        # 会话存储
        self.conversations: Dict[str, Conversation] = {}
        self.user_conversations: Dict[str, Set[str]] = defaultdict(set)  # user_id -> {conv_id}

        # 用户存储
        self.users: Dict[str, UserProfile] = {}

        # 消息索引
        self.msg_index: Dict[str, EventTx] = {}  # msg_id -> EventTx
        self.conv_messages: Dict[str, List[str]] = defaultdict(list)  # conv_id -> [msg_id]

        # Gossip 节点
        self.gossip_node: Optional[GossipNode] = None

        # 回调
        self.on_message_received: Optional[Callable[[Message, EventTx], None]] = None
        self.on_receipt_received: Optional[Callable[[str, str, ReceiptType], None]] = None

        self._lock = RLock()

    # ═══════════════════════════════════════════════════════════════════════════
    # 核心操作
    # ═══════════════════════════════════════════════════════════════════════════

    def create_conversation(
        self,
        conv_type: ConversationType,
        name: str,
        owner: str,
        members: Set[str],
        is_encrypted: bool = False,
    ) -> str:
        """
        创建会话

        Args:
            conv_type: 会话类型
            name: 会话名称
            owner: 创建者
            members: 成员集合（包含创建者）
            is_encrypted: 是否端到端加密

        Returns:
            conv_id: 会话ID
        """
        with self._lock:
            conv_id = self._generate_conv_id(conv_type, owner, members)

            # 初始化成员链
            member_chains = {}
            for m in members:
                member_chains[m] = self.ledger.genesis_hash

            conv = Conversation(
                conv_id=conv_id,
                conv_type=conv_type,
                name=name,
                owner=owner,
                members=members,
                member_chains=member_chains,
                is_encrypted=is_encrypted,
            )

            self.conversations[conv_id] = conv

            # 更新用户会话索引
            for m in members:
                self.user_conversations[m].add(conv_id)

            return conv_id

    def _generate_conv_id(
        self,
        conv_type: ConversationType,
        owner: str,
        members: Set[str]
    ) -> str:
        """生成会话ID"""
        if conv_type == ConversationType.PRIVATE:
            # 私聊：按字典序拼接两个用户ID
            sorted_users = sorted(list(members))
            return f"p2p_{sorted_users[0]}_{sorted_users[1]}"
        else:
            # 群聊/频道：使用 UUID
            return f"{conv_type.value.lower()}_{uuid.uuid4().hex[:12]}"

    def send_message(
        self,
        sender: str,
        conversation_id: str,
        content: str,
        msg_type: MessageType = MessageType.TEXT,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict] = None,
        media_url: Optional[str] = None,
        media_hash: Optional[str] = None,
        media_size: int = 0,
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """
        发送消息

        Args:
            sender: 发送者 user_id
            conversation_id: 会话ID
            content: 消息内容
            msg_type: 消息类型
            reply_to: 回复的消息ID
            metadata: 扩展元数据
            media_url: 媒体URL
            media_hash: 媒体哈希
            media_size: 媒体大小

        Returns:
            (success, msg_id, tx)
        """
        with self._lock:
            # 验证会话
            if conversation_id not in self.conversations:
                return False, "会话不存在", None

            conv = self.conversations[conversation_id]

            # 验证发送者是否是成员
            if sender not in conv.members:
                return False, "不是会话成员", None

            # 生成消息ID
            msg_id = self._generate_msg_id(sender, conversation_id)

            # 创建消息
            msg = Message(
                msg_id=msg_id,
                sender=sender,
                conversation_id=conversation_id,
                conversation_type=conv.conv_type,
                content=content,
                msg_type=msg_type,
                reply_to=reply_to,
                metadata=metadata or {},
                media_url=media_url,
                media_hash=media_hash,
                media_size=media_size,
                created_at=time.time(),
            )

            # 获取发送者的链状态
            sender_state = self.ledger._get_account_state(sender)
            prev_hash = sender_state.last_tx_hash or self.ledger.genesis_hash
            nonce = sender_state.last_nonce + 1

            # 转换为 EventTx
            tx = msg.to_event_tx(sender, prev_hash, nonce)
            tx.tx_hash = tx.compute_hash()

            # 验证
            result = self.ledger.validate_tx(tx)
            if not result.valid:
                return False, result.error, None

            # 添加到账本
            self.ledger.add_tx(tx)

            # 更新索引
            self.msg_index[msg_id] = tx
            self.conv_messages[conversation_id].append(msg_id)

            # 更新会话统计
            conv.msg_count += 1
            conv.updated_at = time.time()
            conv.member_chains[sender] = tx.tx_hash

            # Gossip 广播
            if self.gossip_node:
                self.gossip_node.broadcast(tx, conversation_id)

            # 回调
            if self.on_message_received:
                self.on_message_received(msg, tx)

            return True, msg_id, tx

    def send_receipt(
        self,
        user_id: str,
        msg_id: str,
        receipt_type: ReceiptType = ReceiptType.DELIVERED,
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """
        发送消息回执

        Args:
            user_id: 发送回执的用户
            msg_id: 消息ID
            receipt_type: 回执类型

        Returns:
            (success, receipt_id, tx)
        """
        with self._lock:
            # 验证消息存在
            if msg_id not in self.msg_index:
                return False, "消息不存在", None

            orig_tx = self.msg_index[msg_id]

            # 发送者不能给自己发回执
            if orig_tx.user_id == user_id:
                return False, "不能给自己发回执", None

            receipt_id = f"receipt_{msg_id}_{user_id}_{receipt_type.value}"

            # 构造回执交易
            content_json = json.dumps({
                "receipt_id": receipt_id,
                "msg_id": msg_id,
                "original_sender": orig_tx.user_id,
                "receipt_type": receipt_type.value,
                "timestamp": time.time(),
            }, ensure_ascii=False)

            tx = EventTx(
                tx_hash="",
                prev_tx_hash=self.ledger._get_account_state(user_id).last_tx_hash or self.ledger.genesis_hash,
                user_id=user_id,
                op_type=OpType.MSG_RECEIPT,
                amount=1,
                biz_id=receipt_id,
                to_user_id=orig_tx.user_id,
                metadata=content_json,
            )
            tx.tx_hash = tx.compute_hash()

            # 验证
            result = self.ledger.validate_tx(tx)
            if not result.valid:
                return False, result.error, None

            # 添加到账本
            self.ledger.add_tx(tx)

            # 回调
            if self.on_receipt_received:
                self.on_receipt_received(user_id, msg_id, receipt_type)

            return True, receipt_id, tx

    def edit_message(
        self,
        user_id: str,
        msg_id: str,
        new_content: str,
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """
        编辑消息（只能编辑自己发的消息）

        Returns:
            (success, edit_id, tx)
        """
        with self._lock:
            if msg_id not in self.msg_index:
                return False, "消息不存在", None

            orig_tx = self.msg_index[msg_id]

            if orig_tx.user_id != user_id:
                return False, "只能编辑自己发的消息", None

            edit_id = f"edit_{msg_id}_{int(time.time())}"

            content_json = json.dumps({
                "edit_id": edit_id,
                "msg_id": msg_id,
                "original_sender": user_id,
                "new_content": new_content,
                "edited_at": time.time(),
            }, ensure_ascii=False)

            tx = EventTx(
                tx_hash="",
                prev_tx_hash=self.ledger._get_account_state(user_id).last_tx_hash or self.ledger.genesis_hash,
                user_id=user_id,
                op_type=OpType.MSG_EDIT,
                amount=1,
                biz_id=edit_id,
                metadata=content_json,
            )
            tx.tx_hash = tx.compute_hash()

            result = self.ledger.validate_tx(tx)
            if not result.valid:
                return False, result.error, None

            self.ledger.add_tx(tx)

            return True, edit_id, tx

    def delete_message(
        self,
        user_id: str,
        msg_id: str,
        soft_delete: bool = True,
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """
        删除消息（软删除，只追加删除标记）

        Returns:
            (success, delete_id, tx)
        """
        with self._lock:
            if msg_id not in self.msg_index:
                return False, "消息不存在", None

            orig_tx = self.msg_index[msg_id]

            # 发送者或会话所有者可以删除
            conv = self.conversations.get(orig_tx.metadata.get("conversation_id"))
            can_delete = (
                orig_tx.user_id == user_id or
                (conv and conv.owner == user_id)
            )

            if not can_delete:
                return False, "无权删除此消息", None

            delete_id = f"del_{msg_id}_{int(time.time())}"

            content_json = json.dumps({
                "delete_id": delete_id,
                "msg_id": msg_id,
                "deleted_by": user_id,
                "original_sender": orig_tx.user_id,
                "soft_delete": soft_delete,
                "deleted_at": time.time(),
            }, ensure_ascii=False)

            tx = EventTx(
                tx_hash="",
                prev_tx_hash=self.ledger._get_account_state(user_id).last_tx_hash or self.ledger.genesis_hash,
                user_id=user_id,
                op_type=OpType.MSG_DELETE,
                amount=1,
                biz_id=delete_id,
                metadata=content_json,
            )
            tx.tx_hash = tx.compute_hash()

            result = self.ledger.validate_tx(tx)
            if not result.valid:
                return False, result.error, None

            self.ledger.add_tx(tx)

            return True, delete_id, tx

    def add_reaction(
        self,
        user_id: str,
        msg_id: str,
        emoji: str,
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """
        添加消息反应

        Returns:
            (success, reaction_id, tx)
        """
        with self._lock:
            if msg_id not in self.msg_index:
                return False, "消息不存在", None

            reaction_id = f"react_{msg_id}_{user_id}_{int(time.time())}"

            content_json = json.dumps({
                "reaction_id": reaction_id,
                "msg_id": msg_id,
                "user_id": user_id,
                "emoji": emoji,
                "added_at": time.time(),
            }, ensure_ascii=False)

            tx = EventTx(
                tx_hash="",
                prev_tx_hash=self.ledger._get_account_state(user_id).last_tx_hash or self.ledger.genesis_hash,
                user_id=user_id,
                op_type=OpType.MSG_REACTION,
                amount=1,
                biz_id=reaction_id,
                metadata=content_json,
            )
            tx.tx_hash = tx.compute_hash()

            result = self.ledger.validate_tx(tx)
            if not result.valid:
                return False, result.error, None

            self.ledger.add_tx(tx)

            return True, reaction_id, tx

    # ═══════════════════════════════════════════════════════════════════════════
    # 查询操作
    # ═══════════════════════════════════════════════════════════════════════════

    def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int = 50,
        before_msg_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取会话消息（按时间倒序）

        Args:
            conversation_id: 会话ID
            limit: 返回数量
            before_msg_id: 之前看过最老的消息ID，用于分页

        Returns:
            消息列表
        """
        with self._lock:
            msg_ids = self.conv_messages.get(conversation_id, [])

            if not msg_ids:
                return []

            # 分页
            if before_msg_id:
                idx = msg_ids.index(before_msg_id) if before_msg_id in msg_ids else -1
                msg_ids = msg_ids[:idx] if idx >= 0 else msg_ids

            msg_ids = msg_ids[-limit:]

            # 获取消息详情
            messages = []
            for msg_id in msg_ids:
                if msg_id in self.msg_index:
                    tx = self.msg_index[msg_id]
                    messages.append(self._tx_to_message_dict(tx))

            return messages

    def get_message_chain(self, msg_id: str) -> List[EventTx]:
        """
        获取消息的完整链（包含编辑历史、删除记录）

        Args:
            msg_id: 消息ID

        Returns:
            相关交易列表
        """
        with self._lock:
            chain = []

            # 原始消息
            if msg_id in self.msg_index:
                chain.append(self.msg_index[msg_id])

            # 查找相关交易
            for tx_hash, tx in self.ledger.txs.items():
                if tx.op_type in (OpType.MSG_EDIT, OpType.MSG_DELETE, OpType.MSG_REACTION):
                    metadata = json.loads(tx.metadata) if tx.metadata else {}
                    if metadata.get("msg_id") == msg_id:
                        chain.append(tx)

            return chain

    def get_conversation_participants(self, conversation_id: str) -> List[str]:
        """获取会话参与者"""
        with self._lock:
            conv = self.conversations.get(conversation_id)
            return list(conv.members) if conv else []

    def verify_message_integrity(self, msg_id: str) -> Tuple[bool, str]:
        """
        验证消息完整性

        检查消息链是否被篡改：
        1. 消息交易哈希是否正确
        2. 是否存在后续的 EDIT/DELETE 交易

        Returns:
            (is_valid, message)
        """
        with self._lock:
            if msg_id not in self.msg_index:
                return False, "消息不存在"

            orig_tx = self.msg_index[msg_id]

            # 验证哈希
            if not orig_tx.verify_hash():
                return False, "消息哈希验证失败（可能被篡改）"

            # 检查是否有删除标记
            chain = self.get_message_chain(msg_id)
            for tx in chain:
                if tx.op_type == OpType.MSG_DELETE:
                    metadata = json.loads(tx.metadata) if tx.metadata else {}
                    return False, f"消息已被删除（by {metadata.get('deleted_by')}）"

            return True, "消息完整，未被篡改"

    # ═══════════════════════════════════════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════════════════════════════════════

    def _generate_msg_id(self, sender: str, conversation_id: str) -> str:
        """生成消息ID"""
        timestamp = str(time.time())
        random_suffix = secrets.token_hex(4)
        raw = f"{sender}:{conversation_id}:{timestamp}:{random_suffix}"
        return f"msg_{hashlib.sha256(raw.encode()).hexdigest()[:24]}"

    def _tx_to_message_dict(self, tx: EventTx) -> Dict[str, Any]:
        """将 EventTx 转换为消息字典"""
        try:
            metadata = json.loads(tx.metadata) if tx.metadata else {}
        except:
            metadata = {}

        return {
            "msg_id": metadata.get("msg_id", tx.biz_id),
            "sender": tx.user_id,
            "conversation_id": metadata.get("conversation_id"),
            "content": metadata.get("content", ""),
            "msg_type": metadata.get("msg_type", "TEXT"),
            "created_at": metadata.get("created_at", 0),
            "tx_hash": tx.tx_hash,
            "nonce": tx.nonce,
        }

    def init_gossip_node(self, node_id: str):
        """初始化 Gossip 节点"""
        self.gossip_node = GossipNode(
            node_id=node_id,
            ledger=self,
            max_neighbors=5,
        )

    def get_status(self) -> Dict[str, Any]:
        """获取 IM 状态"""
        return {
            "conversation_count": len(self.conversations),
            "user_count": len(self.users),
            "message_count": len(self.msg_index),
            "gossip_node": self.gossip_node.get_status() if self.gossip_node else None,
        }
