"""
邮件账户与数据模型
==================

定义邮箱账户配置和邮件数据结构。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import imaplib
import time


class EmailProvider(Enum):
    """邮件服务商"""
    CUSTOM = "custom"
    QQ = "qq"
    Netease163 = "163"
    Netease126 = "126"
    Gmail = "gmail"
    Outlook = "outlook"


@dataclass
class EmailAccount:
    """
    邮件账户配置

    用于连接邮箱服务器的配置信息。
    """
    account_id: str                         # 账户唯一ID
    email: str                              # 邮箱地址
    display_name: str = ""                  # 显示名称
    provider: EmailProvider = EmailProvider.CUSTOM  # 邮件服务商

    # 连接配置
    imap_host: str = ""                     # IMAP服务器地址
    imap_port: int = 993                    # IMAP端口（默认993）
    smtp_host: str = ""                     # SMTP服务器地址（用于发送）
    smtp_port: int = 465                    # SMTP端口
    use_ssl: bool = True                    # 是否使用SSL

    # 认证
    username: str = ""                      # 用户名（通常是邮箱地址）
    auth_code: str = ""                    # 授权码/密码

    # 监听配置
    folder: str = "INBOX"                   # 监听文件夹
    idle_timeout: int = 600                 # IDLE超时时间（秒）
    poll_interval: int = 30                 # 轮询间隔（秒，IDLE失败时使用）

    # 通知配置
    notify_enabled: bool = True            # 是否启用通知
    notify_sound: bool = True               # 是否播放声音
    max_preview_length: int = 100           # 预览最大长度

    # 过滤规则
    filter_senders: List[str] = field(default_factory=list)  # 只提醒这些发件人（空=全部）
    block_senders: List[str] = field(default_factory=list)    # 屏蔽这些发件人
    keywords: List[str] = field(default_factory=list)        # 关键词过滤

    # 状态
    is_active: bool = False                 # 是否激活
    last_check: float = 0                  # 上次检查时间
    last_new_mail: float = 0               # 上次收到新邮件时间

    # 元数据
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_imap_url(self) -> str:
        """获取IMAP连接URL"""
        if self.use_ssl:
            return f"{self.imap_host}:{self.imap_port}"
        return self.imap_host

    @classmethod
    def from_qq_email(cls, email: str, auth_code: str, account_id: str = "") -> 'EmailAccount':
        """创建QQ邮箱账户"""
        return cls(
            account_id=account_id or f"qq_{email}",
            email=email,
            provider=EmailProvider.QQ,
            imap_host="imap.qq.com",
            imap_port=993,
            smtp_host="smtp.qq.com",
            smtp_port=465,
            username=email,
            auth_code=auth_code,
        )

    @classmethod
    def from_163_email(cls, email: str, auth_code: str, account_id: str = "") -> 'EmailAccount':
        """创建163邮箱账户"""
        return cls(
            account_id=account_id or f"163_{email}",
            email=email,
            provider=EmailProvider.Netease163,
            imap_host="imap.163.com",
            imap_port=993,
            smtp_host="smtp.163.com",
            smtp_port=465,
            username=email,
            auth_code=auth_code,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "email": self.email,
            "display_name": self.display_name,
            "provider": self.provider.value,
            "imap_host": self.imap_host,
            "imap_port": self.imap_port,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "use_ssl": self.use_ssl,
            "username": self.username,
            # 注意：不保存 auth_code 明文，应加密存储
            "folder": self.folder,
            "idle_timeout": self.idle_timeout,
            "poll_interval": self.poll_interval,
            "notify_enabled": self.notify_enabled,
            "notify_sound": self.notify_sound,
            "max_preview_length": self.max_preview_length,
            "filter_senders": self.filter_senders,
            "block_senders": self.block_senders,
            "keywords": self.keywords,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmailAccount':
        return cls(
            account_id=data["account_id"],
            email=data["email"],
            display_name=data.get("display_name", ""),
            provider=EmailProvider(data.get("provider", "custom")),
            imap_host=data.get("imap_host", ""),
            imap_port=data.get("imap_port", 993),
            smtp_host=data.get("smtp_host", ""),
            smtp_port=data.get("smtp_port", 465),
            use_ssl=data.get("use_ssl", True),
            username=data.get("username", data["email"]),
            auth_code=data.get("auth_code", ""),
            folder=data.get("folder", "INBOX"),
            idle_timeout=data.get("idle_timeout", 600),
            poll_interval=data.get("poll_interval", 30),
            notify_enabled=data.get("notify_enabled", True),
            notify_sound=data.get("notify_sound", True),
            max_preview_length=data.get("max_preview_length", 100),
            filter_senders=data.get("filter_senders", []),
            block_senders=data.get("block_senders", []),
            keywords=data.get("keywords", []),
            is_active=data.get("is_active", False),
        )


@dataclass
class EmailMessage:
    """
    邮件消息

    从IMAP服务器获取的邮件信息。
    """
    message_id: str                         # 邮件唯一ID（IMAP UID）
    account_id: str                         # 所属账户ID
    subject: str = ""                       # 主题
    sender: str = ""                        # 发件人
    sender_email: str = ""                  # 发件人邮箱
    recipients: List[str] = field(default_factory=list)  # 收件人
    date: float = 0                         # 收到时间戳
    flags: List[str] = field(default_factory=list)  # 标志（SEEN, UNREAD等）

    # 内容预览
    preview: str = ""                       # 内容预览
    has_attachments: bool = False           # 是否有附件
    attachment_count: int = 0               # 附件数量

    # 原始数据
    raw_headers: Dict[str, str] = field(default_factory=dict)  # 原始头信息

    @property
    def is_unread(self) -> bool:
        return "UNREAD" in self.flags

    @property
    def date_str(self) -> str:
        """格式化日期"""
        from datetime import datetime
        dt = datetime.fromtimestamp(self.date)
        return dt.strftime("%Y-%m-%d %H:%M")

    def should_notify(self, account: EmailAccount) -> bool:
        """
        检查是否应该发送通知

        根据账户的过滤规则判断。
        """
        if not account.notify_enabled:
            return False

        # 检查黑名单
        if self.sender_email in account.block_senders:
            return False
        if self.sender in account.block_senders:
            return False

        # 检查白名单（如果设置了，只通知白名单）
        if account.filter_senders:
            if self.sender_email not in account.filter_senders:
                if self.sender not in account.filter_senders:
                    return False

        # 检查关键词
        if account.keywords:
            matched = False
            for kw in account.keywords:
                if kw.lower() in self.subject.lower():
                    matched = True
                    break
                if kw.lower() in self.preview.lower():
                    matched = True
                    break
            if not matched:
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "account_id": self.account_id,
            "subject": self.subject,
            "sender": self.sender,
            "sender_email": self.sender_email,
            "recipients": self.recipients,
            "date": self.date,
            "flags": self.flags,
            "preview": self.preview,
            "has_attachments": self.has_attachments,
            "attachment_count": self.attachment_count,
            "is_unread": self.is_unread,
        }
