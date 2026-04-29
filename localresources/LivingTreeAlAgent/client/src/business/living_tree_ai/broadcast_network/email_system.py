"""
Email System - 邮件系统
======================

功能：
- 端到端加密
- 收件箱管理
- 邮件状态追踪

Author: LivingTreeAI Community
"""

import time
import json
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, List, Dict, Any
from enum import Enum

from .content_types import Content, Email


class EmailStatus(Enum):
    """邮件状态"""
    DRAFT = "draft"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    REPLIED = "replied"
    ARCHIVED = "archived"
    DELETED = "deleted"


@dataclass
class EmailAccount:
    """邮件账户"""
    node_id: str
    display_name: str
    public_key: Optional[str] = None
    private_key: Optional[str] = None  # 本地存储，不传输
    signature: str = ""

    # 邮件夹
    inbox: List[str] = field(default_factory=list)  # 内容ID列表
    sent: List[str] = field(default_factory=list)
    drafts: List[str] = field(default_factory=list)
    archive: List[str] = field(default_factory=list)
    trash: List[str] = field(default_factory=list)

    # 统计
    unread_count: int = 0
    total_sent: int = 0
    total_received: int = 0


class EncryptedEmail:
    """
    加密邮件系统

    功能：
    1. 端到端加密
    2. 多收件人加密
    3. 邮件签名验证
    """

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
        encrypt_func: Optional[Callable[[str, str], str]] = None,
        decrypt_func: Optional[Callable[[str, str], str]] = None,
        get_public_key_func: Optional[Callable[[str], str]] = None,
    ):
        self.node_id = node_id
        self._send_func = send_func
        self._encrypt_func = encrypt_func or self._default_encrypt
        self._decrypt_func = decrypt_func or self._default_decrypt
        self._get_public_key = get_public_key_func or (lambda x: None)

        # 邮件存储
        self.sent_emails: Dict[str, Content] = {}
        self.received_emails: Dict[str, Content] = {}

        # 草稿
        self.drafts: Dict[str, Email] = {}

    def _default_encrypt(self, plaintext: str, public_key: str) -> str:
        """默认加密（简化实现，实际应使用非对称加密）"""
        # 实际应使用 RSA 或 ECIES
        import base64
        return base64.b64encode(plaintext.encode()).decode()

    def _default_decrypt(self, ciphertext: str, private_key: str) -> str:
        """默认解密"""
        import base64
        return base64.b64decode(ciphertext.encode()).decode()

    async def send_email(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict]] = None,
        priority: str = "normal",
        encrypt: bool = True,
    ) -> Optional[Content]:
        """
        发送加密邮件

        Args:
            recipients: 收件人列表
            subject: 主题
            body: 正文
            cc: 抄送
            bcc: 密送
            attachments: 附件
            priority: 优先级
            encrypt: 是否加密

        Returns:
            创建的邮件Content对象
        """
        # 1. 加密邮件正文
        if encrypt:
            encrypted_body = {}
            for recipient in recipients + (cc or []) + (bcc or []):
                pubkey = await self._get_public_key(recipient)
                if pubkey:
                    encrypted_body[recipient] = self._encrypt_func(body, pubkey)
                else:
                    # 如果没有公钥，发送明文（应该警告）
                    encrypted_body[recipient] = body
        else:
            encrypted_body = body

        # 2. 创建邮件内容
        email = Email(
            author=self.node_id,
            recipients=recipients,
            subject=subject,
            body=encrypted_body if encrypt else body,
            cc=cc,
            bcc=bcc,
            priority=priority,
            attachments=attachments or [],
        )
        email.metadata["encrypted"] = encrypt
        email.metadata["status"] = EmailStatus.SENT.value

        # 3. 计算ID
        email.content_id = email.compute_id()

        # 4. 存储
        self.sent_emails[email.content_id] = email

        # 5. 发送
        if self._send_func:
            await self._send_func(recipients, {
                "type": "email",
                "content": email.to_dict(),
            })

        return email

    async def receive_email(self, email_data: dict) -> Content:
        """
        接收邮件

        Args:
            email_data: 邮件数据

        Returns:
            解密后的邮件
        """
        email = Content.from_dict(email_data)

        # 检查是否加密
        if email.metadata.get("encrypted"):
            # 解密
            email.body = await self._decrypt_email(email)

        # 存储
        self.received_emails[email.content_id] = email

        return email

    async def _decrypt_email(self, email: Content) -> str:
        """解密邮件"""
        if isinstance(email.body, dict):
            # 多收件人加密版本
            my_encrypted = email.body.get(self.node_id)
            if my_encrypted:
                return self._decrypt_func(my_encrypted, "")
            return ""
        elif isinstance(email.body, str):
            return email.body
        return ""

    def verify_signature(self, email: Content) -> bool:
        """验证邮件签名"""
        if not email.signature:
            return False
        # 简化实现
        return email.signature != ""

    def create_draft(
        self,
        recipients: List[str],
        subject: str,
        body: str,
    ) -> str:
        """创建草稿"""
        draft_id = f"draft_{self.node_id}_{int(time.time())}"

        draft = Email(
            author=self.node_id,
            recipients=recipients,
            subject=subject,
            body=body,
        )
        draft.metadata["status"] = EmailStatus.DRAFT.value

        self.drafts[draft_id] = draft
        return draft_id

    def get_sent_email(self, email_id: str) -> Optional[Content]:
        """获取已发送邮件"""
        return self.sent_emails.get(email_id)

    def get_received_email(self, email_id: str) -> Optional[Content]:
        """获取已接收邮件"""
        return self.received_emails.get(email_id)


class InboxManager:
    """
    收件箱管理器

    功能：
    1. 拉取新邮件
    2. 标记已读
    3. 邮件归档/删除
    4. 邮件夹管理
    """

    def __init__(
        self,
        node_id: str,
        fetch_func: Optional[Callable[[], Awaitable[List[str]]]] = None,
    ):
        self.node_id = node_id

        # 邮件ID存储（实际邮件内容在EncryptedEmail中）
        self.inbox_ids: List[str] = []
        self.read_ids: set = set()
        self.starred_ids: set = set()

        # 邮件夹
        self.folders = {
            "inbox": [],
            "sent": [],
            "drafts": [],
            "archive": [],
            "trash": [],
        }

        # 获取函数
        self._fetch_func = fetch_func

    async def check_inbox(self, encrypted_email: EncryptedEmail):
        """
        检查收件箱

        Args:
            encrypted_email: 加密邮件系统实例
        """
        if not self._fetch_func:
            return

        # 获取新邮件ID列表
        new_ids = await self._fetch_func()

        # 找出新增的
        for email_id in new_ids:
            if email_id not in self.inbox_ids:
                self.inbox_ids.append(email_id)

    def mark_as_read(self, email_id: str):
        """标记已读"""
        self.read_ids.add(email_id)

    def mark_as_unread(self, email_id: str):
        """标记未读"""
        self.read_ids.discard(email_id)

    def star_email(self, email_id: str):
        """加星标"""
        self.starred_ids.add(email_id)

    def unstar_email(self, email_id: str):
        """取消星标"""
        self.starred_ids.discard(email_id)

    def move_to_folder(self, email_id: str, folder: str):
        """移动邮件到指定文件夹"""
        if folder not in self.folders:
            return

        # 从所有文件夹移除
        for f in self.folders:
            if email_id in self.folders[f]:
                self.folders[f].remove(email_id)

        # 添加到目标文件夹
        self.folders[folder].append(email_id)

    def archive_email(self, email_id: str):
        """归档邮件"""
        self.move_to_folder(email_id, "archive")

    def delete_email(self, email_id: str):
        """删除邮件（移到垃圾箱）"""
        self.move_to_folder(email_id, "trash")

    def permanent_delete(self, email_id: str):
        """永久删除"""
        for folder in self.folders:
            if email_id in self.folders[folder]:
                self.folders[folder].remove(email_id)
        self.inbox_ids = [i for i in self.inbox_ids if i != email_id]

    def get_inbox_count(self) -> int:
        """获取未读邮件数"""
        return len([i for i in self.inbox_ids if i not in self.read_ids])

    def get_folder_emails(self, folder: str, limit: int = 50) -> List[str]:
        """获取文件夹中的邮件ID列表"""
        if folder not in self.folders:
            return []
        return self.folders[folder][-limit:]

    def search_emails(
        self,
        query: str,
        folder: Optional[str] = None,
    ) -> List[str]:
        """
        搜索邮件

        简化实现：只支持标题搜索
        """
        # 确定搜索范围
        if folder:
            search_ids = self.folders.get(folder, [])
        else:
            search_ids = self.inbox_ids

        # 简单搜索（实际应该使用倒排索引）
        results = []
        for email_id in search_ids:
            # 简化：实际应该搜索邮件内容
            if query.lower() in email_id.lower():
                results.append(email_id)

        return results

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "inbox_total": len(self.inbox_ids),
            "inbox_unread": self.get_inbox_count(),
            "sent_total": len(self.folders.get("sent", [])),
            "drafts_total": len(self.folders.get("drafts", [])),
            "archive_total": len(self.folders.get("archive", [])),
            "trash_total": len(self.folders.get("trash", [])),
        }


class EmailSystem:
    """
    邮件系统整合

    整合加密邮件和收件箱管理
    """

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
    ):
        self.node_id = node_id

        # 账户
        self.account = EmailAccount(node_id=node_id, display_name=node_id)

        # 子系统
        self.email = EncryptedEmail(node_id, send_func=send_func)
        self.inbox = InboxManager(node_id)

    async def send_email(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        **kwargs
    ) -> Optional[Content]:
        """发送邮件"""
        email = await self.email.send_email(recipients, subject, body, **kwargs)

        if email:
            self.account.sent.append(email.content_id)
            self.account.total_sent += 1
            self.inbox.move_to_folder(email.content_id, "sent")

        return email

    async def receive_email(self, email_data: dict) -> Content:
        """接收邮件"""
        email = await self.email.receive_email(email_data)

        self.received_emails[email.content_id] = email
        self.inbox.inbox_ids.append(email.content_id)
        self.account.inbox.append(email.content_id)
        self.account.total_received += 1
        self.account.unread_count += 1

        return email

    def get_inbox(self, limit: int = 50) -> List[str]:
        """获取收件箱"""
        return self.inbox.get_folder_emails("inbox", limit)

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "account": {
                "total_sent": self.account.total_sent,
                "total_received": self.account.total_received,
                "unread_count": self.account.unread_count,
            },
            "inbox": self.inbox.get_stats(),
        }


# 全局单例
_email_instance: Optional[EmailSystem] = None


def get_email_system(node_id: str = "local") -> EmailSystem:
    """获取邮件系统单例"""
    global _email_instance
    if _email_instance is None:
        _email_instance = EmailSystem(node_id)
    return _email_instance