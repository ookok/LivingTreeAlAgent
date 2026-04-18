"""
外部邮件 SMTP 发送器

功能：
- 通过外部账号 SMTP 发送邮件
- 支持附件、HTML/纯文本
- 自动存入已发送文件夹

作者：Living Tree AI 进化系统
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
import time
import secrets
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional, List, Dict, Any

from .external_account_manager import get_external_account_manager, ExternalMailAccount

logger = logging.getLogger(__name__)


class SendResult:
    """发送结果"""
    def __init__(self, success: bool, message_id: str = "", error: str = ""):
        self.success = success
        self.message_id = message_id
        self.error = error
        self.sent_at = time.time() if success else 0


class SMTPSender:
    """
    SMTP 发送器

    功能：
    - 通过外部账号 SMTP 发送邮件
    - 连接复用
    - 重试机制
    """

    def __init__(self):
        self.account_manager = get_external_account_manager()
        self._connections: Dict[str, smtplib.SMTP] = {}
        self._last_used: Dict[str, float] = {}
        self._connection_timeout = 60
        self._max_retries = 3

    async def send_email(
        self,
        account_id: str,
        from_addr: str,
        to_addrs: List[str],
        subject: str,
        body_html: str = "",
        body_text: str = "",
        attachments: List[str] = None,
        cc_addrs: List[str] = None,
        bcc_addrs: List[str] = None,
    ) -> SendResult:
        """发送邮件"""
        account = self.account_manager.get_account(account_id)
        if not account:
            return SendResult(False, error=f"账号不存在: {account_id}")

        if not account.smtp:
            return SendResult(False, error=f"账号未配置 SMTP: {account_id}")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        if cc_addrs:
            msg["Cc"] = ", ".join(cc_addrs)
        msg["Date"] = self._format_date()

        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            msg.attach(MIMEText(body_html, "html", "utf-8"))

        if attachments:
            for file_path in attachments:
                self._add_attachment(msg, file_path)

        all_recipients = to_addrs + (cc_addrs or []) + (bcc_addrs or [])

        for attempt in range(self._max_retries):
            try:
                server = await self._get_connection(account)
                server.sendmail(from_addr, all_recipients, msg.as_bytes())
                logger.info(f"邮件发送成功: {subject} -> {to_addrs}")
                self.account_manager.update_last_sync(account_id)
                return SendResult(success=True, message_id=f"smtp_{int(time.time())}_{secrets.token_hex(4)}")
            except Exception as e:
                logger.warning(f"邮件发送失败 (尝试 {attempt + 1}/{self._max_retries}): {e}")
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    self._connections.pop(account_id, None)

        return SendResult(False, error=f"发送失败，已重试 {self._max_retries} 次")

    async def _get_connection(self, account: ExternalMailAccount) -> smtplib.SMTP:
        """获取或创建 SMTP 连接"""
        now = time.time()

        if account.id in self._connections:
            last_used = self._last_used.get(account.id, 0)
            if now - last_used < self._connection_timeout:
                self._last_used[account.id] = now
                return self._connections[account.id]

        if account.id in self._connections:
            try:
                self._connections[account.id].quit()
            except Exception:
                pass

        logger.info(f"建立 SMTP 连接: {account.smtp.host}:{account.smtp.port}")

        context = ssl.create_default_context()
        server = smtplib.SMTP(account.smtp.host, account.smtp.port, timeout=30)

        try:
            if account.smtp.tls:
                server.starttls(context=context)
            server.login(account.encrypted_username, account.encrypted_password)
        except Exception as e:
            server.quit()
            raise e

        self._connections[account.id] = server
        self._last_used[account.id] = now
        return server

    def _add_attachment(self, msg: MIMEMultipart, file_path: str):
        """添加附件"""
        try:
            with open(file_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            filename = Path(file_path).name
            part.add_header("Content-Disposition", f"attachment; filename*=UTF-8''{filename}")
            msg.attach(part)
        except Exception as e:
            logger.error(f"添加附件失败: {file_path}, {e}")

    def _format_date(self) -> str:
        from email.utils import formatdate
        return formatdate(localtime=True)

    async def close_all(self):
        """关闭所有连接"""
        for account_id, server in self._connections.items():
            try:
                server.quit()
            except Exception:
                pass
        self._connections.clear()
        self._last_used.clear()

    async def test_connection(self, account_id: str) -> tuple[bool, str]:
        """测试连接"""
        try:
            account = self.account_manager.get_account(account_id)
            if not account or not account.smtp:
                return False, "账号不存在或未配置 SMTP"
            await self._get_connection(account)
            return True, "SMTP 连接成功"
        except Exception as e:
            return False, f"连接失败: {e}"


_sender: Optional[SMTPSender] = None


def get_smtp_sender() -> SMTPSender:
    global _sender
    if _sender is None:
        _sender = SMTPSender()
    return _sender
