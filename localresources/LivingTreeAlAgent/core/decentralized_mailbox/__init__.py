"""
去中心化邮箱系统

Decentralized Mailbox - P2P Email without SMTP

核心功能:
- user@nodeid.p2p 去中心化地址
- 端到端加密 (ECDH + AES-256-GCM)
- P2P直接投递 + 中继转发
- 大文件分片加密存储
- 离线消息队列
- 联系人信任级别管理
"""

from .models import (
    MailboxAddress,
    MailMessage,
    Attachment,
    Contact,
    InboxFolder,
    MessageStatus,
    AttachmentType,
    TrustLevel,
    DeliveryReceipt,
    DEFAULT_FOLDERS
)

from .address_manager import AddressManager
from .crypto import MailCrypto
from .message_store import MessageStore
from .message_router import MessageRouter, RouteResult, DeliveryStatus
from .attachment_handler import AttachmentHandler
from .mailbox_hub import MailboxHub, get_mailbox_hub, get_mailbox_hub_sync
from .relay_sync import (
    RelaySyncClient,
    RelaySyncConfig,
    RelaySyncStore,
    RelayEmailEntry,
    get_relay_sync_client,
)
from .external_mail import (
    ExternalMailAccount,
    ExternalAccountManager,
    get_external_account_manager,
    SMTPSender,
    SendResult,
    get_smtp_sender,
    IMAPReceiver,
    ExternalMailMessage,
    get_imap_receiver,
)
from .unified_inbox import (
    UnifiedInbox,
    UnifiedMailEntry,
    get_unified_inbox,
)

__all__ = [
    # 模型
    "MailboxAddress",
    "MailMessage",
    "Attachment",
    "Contact",
    "InboxFolder",
    "MessageStatus",
    "AttachmentType",
    "TrustLevel",
    "DeliveryReceipt",
    "DEFAULT_FOLDERS",
    # 管理器
    "AddressManager",
    "MailCrypto",
    "MessageStore",
    "MessageRouter",
    "AttachmentHandler",
    # 核心
    "MailboxHub",
    "get_mailbox_hub",
    "get_mailbox_hub_sync",
    # 路由
    "RouteResult",
    "DeliveryStatus",
    # 中继同步
    "RelaySyncClient",
    "RelaySyncConfig",
    "RelaySyncStore",
    "RelayEmailEntry",
    "get_relay_sync_client",
    # 外部邮件
    "ExternalMailAccount",
    "ExternalAccountManager",
    "get_external_account_manager",
    "SMTPSender",
    "SendResult",
    "get_smtp_sender",
    "IMAPReceiver",
    "ExternalMailMessage",
    "get_imap_receiver",
    # 统一收件箱
    "UnifiedInbox",
    "UnifiedMailEntry",
    "get_unified_inbox",
]
