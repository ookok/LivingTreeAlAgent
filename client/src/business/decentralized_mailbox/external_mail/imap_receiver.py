"""
外部邮件 IMAP 接收器

功能：
- 通过 IMAP 接收外部邮件
- 转换为统一内部格式
- 增量获取（只拉新邮件）

作者：Living Tree AI 进化系统
from __future__ import annotations
"""


import asyncio
import imaplib
import email
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from email.header import decode_header
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

from .external_account_manager import get_external_account_manager, ExternalMailAccount

logger = logging.getLogger(__name__)


@dataclass
class ExternalMailMessage:
    """外部邮件消息（统一格式）"""
    message_id: str
    account_id: str
    subject: str
    body_html: str = ""
    body_text: str = ""
    from_addr: str = ""
    from_name: str = ""
    to_addrs: List[str] = field(default_factory=list)
    cc_addrs: List[str] = field(default_factory=list)
    date: float = 0
    is_read: bool = False
    is_starred: bool = False
    labels: List[str] = field(default_factory=list)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    thread_id: Optional[str] = None
    raw_headers: Dict[str, str] = field(default_factory=dict)

    @property
    def source(self) -> str:
        return "external"


class IMAPReceiver:
    """
    IMAP 接收器

    功能：
    - IMAP 连接管理
    - 邮件拉取
    - 邮件解析
    - 增量同步
    """

    def __init__(self):
        self.account_manager = get_external_account_manager()
        self._connections: Dict[str, imaplib.IMAP4_SSL] = {}
        self._last_used: Dict[str, float] = {}
        self._connection_timeout = 60

    async def fetch_new_emails(
        self,
        account_id: str,
        folder: str = "INBOX",
        limit: int = 50,
        since_date: float = None,
    ) -> List[ExternalMailMessage]:
        """
        获取新邮件

        Args:
            account_id: 账号 ID
            folder: 文件夹 (INBOX/Sent/Drafts 等)
            limit: 最大数量
            since_date: 只获取此日期后的邮件 (Unix timestamp)

        Returns:
            邮件列表
        """
        account = self.account_manager.get_account(account_id)
        if not account or not account.imap:
            logger.error(f"账号不存在或未配置 IMAP: {account_id}")
            return []

        try:
            server = await self._get_connection(account)
            return await self._fetch_folder(server, account_id, folder, limit, since_date)
        except Exception as e:
            logger.error(f"获取邮件失败: {account_id}, {e}")
            self._connections.pop(account_id, None)
            return []

    async def _fetch_folder(
        self,
        server,
        account_id: str,
        folder: str,
        limit: int,
        since_date: float = None,
    ) -> List[ExternalMailMessage]:
        """获取指定文件夹的邮件"""
        messages = []

        try:
            # 选择文件夹
            status, _ = server.select(folder)
            if status != "OK":
                logger.warning(f"选择文件夹失败: {folder}")
                return []

            # 构建搜索条件
            search_criteria = ["UNSEEN"] if since_date is None else [f"SINCE {self._format_date(since_date)}"]

            # 搜索邮件
            status, msg_ids = server.search(None, *search_criteria)
            if status != "OK":
                return []

            # 获取邮件 ID 列表
            id_list = msg_ids[0].split() if msg_ids[0] else []
            logger.info(f"发现 {len(id_list)} 封新邮件")

            # 限制数量
            id_list = id_list[-limit:]

            # 逐个获取
            for msg_id in id_list:
                try:
                    msg = await self._fetch_single_message(server, account_id, msg_id)
                    if msg:
                        messages.append(msg)
                except Exception as e:
                    logger.error(f"获取邮件失败: {msg_id}, {e}")

            # 更新最后同步时间
            if messages:
                self.account_manager.update_last_sync(account_id)

        except Exception as e:
            logger.error(f"获取文件夹邮件失败: {folder}, {e}")

        return messages

    async def _fetch_single_message(self, server, account_id: str, msg_id: bytes) -> Optional[ExternalMailMessage]:
        """获取单封邮件"""
        try:
            # 获取原始邮件
            status, msg_data = server.fetch(msg_id, "(RFC822)")
            if status != "OK":
                return None

            raw_email = msg_data[0][1]
            if isinstance(raw_email, bytes):
                raw_email = raw_email.decode("utf-8", errors="replace")

            # 解析邮件
            msg = email.message_from_string(raw_email)

            # 提取信息
            message_id = self._get_message_id(msg)
            subject = self._decode_header(msg.get("Subject", ""))
            from_addr = msg.get("From", "")
            from_name = self._get_sender_name(msg)
            to_addrs = self._parse_address_list(msg.get("To", ""))
            cc_addrs = self._parse_address_list(msg.get("Cc", ""))
            date = self._parse_date(msg.get("Date", ""))

            # 提取正文
            body_html, body_text = self._extract_body(msg)

            # 提取附件
            attachments = self._extract_attachments(msg)

            # 解析邮件头
            raw_headers = dict(msg.items())

            return ExternalMailMessage(
                message_id=message_id or f"ext_{account_id}_{msg_id.decode()}",
                account_id=account_id,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                from_addr=from_addr,
                from_name=from_name,
                to_addrs=to_addrs,
                cc_addrs=cc_addrs,
                date=date,
                is_read=True,
                labels=[folder],
                attachments=attachments,
                raw_headers=raw_headers,
            )

        except Exception as e:
            logger.error(f"解析邮件失败: {e}")
            return None

    async def _get_connection(self, account: ExternalMailAccount):
        """获取或创建 IMAP 连接"""
        now = time.time()

        if account.id in self._connections:
            last_used = self._last_used.get(account.id, 0)
            if now - last_used < self._connection_timeout:
                self._last_used[account.id] = now
                return self._connections[account.id]

        if account.id in self._connections:
            try:
                self._connections[account.id].logout()
            except Exception:
                pass

        logger.info(f"建立 IMAP 连接: {account.imap.host}:{account.imap.port}")

        if account.imap.ssl:
            server = imaplib.IMAP4_SSL(account.imap.host, account.imap.port)
        else:
            server = imaplib.IMAP4(account.imap.host, account.imap.port)

        server.login(account.encrypted_username, account.encrypted_password)

        self._connections[account.id] = server
        self._last_used[account.id] = now
        return server

    def _decode_header(self, header: str) -> str:
        """解码邮件头"""
        if not header:
            return ""
        try:
            parts = decode_header(header)
            result = []
            for content, charset in parts:
                if isinstance(content, bytes):
                    charset = charset or "utf-8"
                    try:
                        result.append(content.decode(charset, errors="replace"))
                    except Exception:
                        result.append(content.decode("utf-8", errors="replace"))
                else:
                    result.append(content)
            return " ".join(result)
        except Exception:
            return header

    def _get_sender_name(self, msg) -> str:
        """获取发件人姓名"""
        from_addr = msg.get("From", "")
        try:
            name, addr = email.utils.parseaddr(from_addr)
            return name or addr
        except Exception:
            return from_addr

    def _get_message_id(self, msg) -> str:
        """获取消息 ID"""
        msg_id = msg.get("Message-ID", "")
        if msg_id:
            msg_id = msg_id.strip("<>").replace("<", "").replace(">", "")
        return msg_id

    def _parse_address_list(self, header: str) -> List[str]:
        """解析地址列表"""
        if not header:
            return []
        try:
            addrs = email.utils.getaddresses([header])
            return [addr for name, addr in addrs if addr]
        except Exception:
            return []

    def _parse_date(self, date_str: str) -> float:
        """解析日期"""
        if not date_str:
            return time.time()
        try:
            dt = email.utils.parsedate_to_datetime(date_str)
            return dt.timestamp()
        except Exception:
            try:
                return email.utils.mktime_tz(email.utils.parsedate_tz(date_str))
            except Exception:
                return time.time()

    def _format_date(self, timestamp: float) -> str:
        """格式化日期为 IMAP 搜索格式"""
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%d-%b-%Y")

    def _extract_body(self, msg) -> tuple[str, str]:
        """提取邮件正文"""
        body_html = ""
        body_text = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/html":
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body_html = part.get_payload(decode=True).decode(charset, errors="replace")
                    except Exception:
                        pass
                elif content_type == "text/plain":
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body_text = part.get_payload(decode=True).decode(charset, errors="replace")
                    except Exception:
                        pass
        else:
            content_type = msg.get_content_type()
            charset = msg.get_content_charset() or "utf-8"
            try:
                payload = msg.get_payload(decode=True).decode(charset, errors="replace")
                if content_type == "text/html":
                    body_html = payload
                else:
                    body_text = payload
            except Exception:
                pass

        return body_html, body_text

    def _extract_attachments(self, msg) -> List[Dict[str, Any]]:
        """提取附件"""
        attachments = []

        for part in msg.walk():
            content_disposition = part.get("Content-Disposition", "")
            if "attachment" in content_disposition.lower():
                filename = part.get_filename()
                if filename:
                    filename = self._decode_header(filename)
                else:
                    filename = "attachment"

                attachments.append({
                    "filename": filename,
                    "content_type": part.get_content_type(),
                    "size": len(part.get_payload(decode=True) or b""),
                })

        return attachments

    async def mark_as_read(self, account_id: str, message_id: str, folder: str = "INBOX"):
        """标记邮件为已读"""
        try:
            account = self.account_manager.get_account(account_id)
            if not account:
                return False

            server = await self._get_connection(account)
            server.select(folder)
            server.store(message_id, "+FLAGS", "\\Seen")
            return True
        except Exception as e:
            logger.error(f"标记已读失败: {e}")
            return False

    async def close_all(self):
        """关闭所有连接"""
        for account_id, server in self._connections.items():
            try:
                server.logout()
            except Exception:
                pass
        self._connections.clear()
        self._last_used.clear()

    async def test_connection(self, account_id: str) -> tuple[bool, str]:
        """测试连接"""
        try:
            account = self.account_manager.get_account(account_id)
            if not account or not account.imap:
                return False, "账号不存在或未配置 IMAP"
            await self._get_connection(account)
            return True, "IMAP 连接成功"
        except Exception as e:
            return False, f"连接失败: {e}"


_receiver: Optional[IMAPReceiver] = None


def get_imap_receiver() -> IMAPReceiver:
    global _receiver
    if _receiver is None:
        _receiver = IMAPReceiver()
    return _receiver
