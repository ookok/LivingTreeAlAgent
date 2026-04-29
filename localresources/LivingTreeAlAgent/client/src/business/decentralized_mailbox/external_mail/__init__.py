"""
外部邮件模块

功能：
- 外部邮箱账号管理
- SMTP 发送
- IMAP 接收
- 统一外部邮件接口

作者：Living Tree AI 进化系统
"""

from .external_account_manager import (
    ExternalMailAccount,
    ExternalAccountManager,
    get_external_account_manager,
)

from .smtp_sender import (
    SMTPSender,
    SendResult,
    get_smtp_sender,
)

from .imap_receiver import (
    IMAPReceiver,
    ExternalMailMessage,
    get_imap_receiver,
)

__all__ = [
    "ExternalMailAccount",
    "ExternalAccountManager",
    "get_external_account_manager",
    "SMTPSender",
    "SendResult",
    "get_smtp_sender",
    "IMAPReceiver",
    "ExternalMailMessage",
    "get_imap_receiver",
]
