"""
去中心化邮箱数据模型

定义邮箱地址、消息、附件、联系人等核心数据结构
from __future__ import annotations
"""


import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class MessageStatus(Enum):
    """消息状态"""
    DRAFT = "draft"           # 草稿
    SENDING = "sending"       # 发送中
    SENT = "sent"             # 已发送
    DELIVERED = "delivered"   # 已送达
    READ = "read"             # 已读
    FAILED = "failed"         # 发送失败


class AttachmentType(Enum):
    """附件类型"""
    FILE = "file"             # 普通文件
    LARGE_FILE = "large_file" # 大文件(分片存储)
    ENCRYPTED_CHUNK = "encrypted_chunk"  # 加密分片


class TrustLevel(Enum):
    """信任级别 (反垃圾)"""
    BLOCKED = 0      # 黑名单
    UNKNOWN = 1      # 未知
    WHITELISTED = 2  # 白名单
    TRUSTED = 3      # 可信


@dataclass
class MailboxAddress:
    """
    邮箱地址 (user@nodeid.p2p)
    """
    username: str           # 用户名
    node_id: str            # P2P节点ID
    public_key: Optional[str] = None  # 公钥 (Base64)
    
    @property
    def full_address(self) -> str:
        """完整地址"""
        return f"{self.username}@{self.node_id}.p2p"
    
    @property
    def short_address(self) -> str:
        """短地址 (用于显示)"""
        return f"{self.username}@{self.node_id[:8]}..."
    
    def __str__(self) -> str:
        return self.full_address
    
    def __eq__(self, other) -> bool:
        if isinstance(other, MailboxAddress):
            return self.full_address == other.full_address
        return False
    
    def __hash__(self) -> int:
        return hash(self.full_address)


@dataclass
class Attachment:
    """
    附件
    """
    chunk_id: str                    # 分片ID
    filename: str                   # 原始文件名
    file_size: int                  # 文件大小 (字节)
    content_type: str               # MIME类型
    checksum: str                   # SHA256校验和
    total_chunks: int = 1           # 总分片数
    chunk_index: int = 0           # 当前分片索引
    storage_path: Optional[str] = None  # 存储路径
    upload_progress: float = 0.0   # 上传进度
    status: AttachmentType = AttachmentType.FILE


@dataclass
class MailMessage:
    """
    邮件消息
    """
    message_id: str                 # 消息ID (UUID)
    subject: str                    # 主题
    body: str                       # 正文 (加密存储)
    body_plain: str = ""            # 明文预览
    
    # 地址
    from_addr: Optional[MailboxAddress] = None
    to_addrs: list[MailboxAddress] = field(default_factory=list)
    cc_addrs: list[MailboxAddress] = field(default_factory=list)
    bcc_addrs: list[MailboxAddress] = field(default_factory=list)
    
    # 时间
    created_at: float = field(default_factory=time.time)
    sent_at: Optional[float] = None
    delivered_at: Optional[float] = None
    read_at: Optional[float] = None
    
    # 状态
    status: MessageStatus = MessageStatus.DRAFT
    is_encrypted: bool = True       # 是否端到端加密
    is_signed: bool = False         # 是否数字签名
    
    # 附件
    attachments: list[Attachment] = field(default_factory=list)
    has_large_attachment: bool = False  # 是否有大附件
    
    # 元数据
    thread_id: Optional[str] = None  # 会话线程ID
    reply_to_id: Optional[str] = None  # 回复的消息ID
    priority: int = 0               # 优先级 (0=普通, 1=重要, 2=紧急)
    
    # 标签
    labels: list[str] = field(default_factory=list)  # 标签列表
    is_starred: bool = False
    is_deleted: bool = False
    
    @property
    def display_time(self) -> str:
        """显示时间"""
        dt = datetime.fromtimestamp(self.created_at)
        now = datetime.now()
        if dt.date() == now.date():
            return dt.strftime("%H:%M")
        elif (now - dt).days == 1:
            return "昨天"
        elif (now - dt).days < 7:
            return dt.strftime("%A")
        else:
            return dt.strftime("%Y-%m-%d")
    
    @property
    def preview(self) -> str:
        """预览文本"""
        preview = self.body_plain[:100] if self.body_plain else "[加密内容]"
        return preview + ("..." if len(self.body_plain) > 100 else "")
    
    @property
    def has_attachments(self) -> bool:
        """是否有附件"""
        return len(self.attachments) > 0


@dataclass
class Contact:
    """
    联系人
    """
    address: MailboxAddress
    display_name: str = ""          # 显示名称
    avatar: Optional[str] = None     # 头像 (Base64)
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    
    # 统计
    total_sent: int = 0             # 发送消息数
    total_received: int = 0         # 接收消息数
    last_contact_at: Optional[float] = None
    
    # 标签
    tags: list[str] = field(default_factory=list)
    is_blocked: bool = False
    is_muted: bool = False
    
    # 备注
    notes: str = ""
    
    @property
    def trust_display(self) -> str:
        """信任级别显示"""
        return {
            TrustLevel.BLOCKED: "已拉黑",
            TrustLevel.UNKNOWN: "陌生人",
            TrustLevel.WHITELISTED: "白名单",
            TrustLevel.TRUSTED: "可信"
        }.get(self.trust_level, "未知")


@dataclass
class InboxFolder:
    """
    收件箱文件夹
    """
    folder_id: str
    name: str
    icon: str = "📁"
    parent_id: Optional[str] = None
    unread_count: int = 0
    total_count: int = 0
    
    # 内置文件夹
    @staticmethod
    def inbox() -> InboxFolder:
        return InboxFolder(folder_id="inbox", name="收件箱", icon="📥")
    
    @staticmethod
    def sent() -> InboxFolder:
        return InboxFolder(folder_id="sent", name="已发送", icon="📤")
    
    @staticmethod
    def drafts() -> InboxFolder:
        return InboxFolder(folder_id="drafts", name="草稿箱", icon="📝")
    
    @staticmethod
    def trash() -> InboxFolder:
        return InboxFolder(folder_id="trash", name="垃圾箱", icon="🗑️")
    
    @staticmethod
    def outbox() -> InboxFolder:
        return InboxFolder(folder_id="outbox", name="发件箱", icon="📬")


@dataclass
class DeliveryReceipt:
    """
    投递回执
    """
    message_id: str
    recipient: str                  # 收件人地址
    status: MessageStatus
    delivered_at: Optional[float] = None
    read_at: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class BlockProof:
    """
    存证区块 (可选的区块链存证)
    """
    block_hash: str                 # 区块哈希
    message_hash: str               # 消息哈希
    timestamp: float
    prev_block_hash: str            # 前一个区块哈希
    nonce: int = 0
    signature: Optional[str] = None  # 签名


# 内置文件夹
DEFAULT_FOLDERS = [
    InboxFolder.inbox(),
    InboxFolder.sent(),
    InboxFolder.drafts(),
    InboxFolder.trash(),
    InboxFolder.outbox(),
]
