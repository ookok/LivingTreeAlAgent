"""
统一收件箱

功能：
- 聚合外部邮件（IMAP）+ 内部邮件（P2P/.tree）+ 中继邮件
- 统一排序展示
- 来源标签识别

作者：Living Tree AI 进化系统
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

logger = logging.getLogger(__name__)

# ============ 配置路径 ============

DATA_DIR = Path("~/.hermes-desktop/mailbox/unified").expanduser()


@dataclass
class UnifiedMailEntry:
    """
    统一邮件条目

    整合所有来源的邮件，统一格式
    """
    # 唯一标识
    message_id: str

    # 来源信息
    source: str  # "external" / "internal" / "relay"

    # 账号/节点信息
    account_id: str = ""        # 外部账号 ID
    provider: str = ""         # 提供商 (gmail/qq/internal/relay)

    # 邮件内容
    subject: str = ""
    body_text: str = ""
    body_html: str = ""

    # 地址
    from_addr: str = ""
    from_name: str = ""
    to_addrs: List[str] = field(default_factory=list)
    cc_addrs: List[str] = field(default_factory=list)

    # 时间
    date: float = 0

    # 状态
    is_read: bool = False
    is_starred: bool = False
    is_deleted: bool = False
    labels: List[str] = field(default_factory=list)

    # 附件
    has_attachments: bool = False
    attachment_count: int = 0

    # 线程
    thread_id: Optional[str] = None

    # 原始数据引用
    raw_ref: Any = None  # 可能是 ExternalMailMessage 或 MailMessage

    @property
    def display_source(self) -> str:
        """显示来源"""
        source_labels = {
            "external": "📧",
            "internal": "🌳",
            "relay": "🌐",
        }
        return source_labels.get(self.source, "📧")

    @property
    def display_label(self) -> str:
        """显示标签"""
        return f"{self.display_source} [{self.provider.upper()}]"

    @property
    def preview(self) -> str:
        """预览文本"""
        text = self.body_text or self.body_html
        preview = text[:100].replace("\n", " ").strip() if text else "[无正文]"
        return preview + ("..." if len(text) > 100 else "")

    @property
    def display_time(self) -> str:
        """显示时间"""
        from datetime import datetime
        dt = datetime.fromtimestamp(self.date)
        now = datetime.now()
        if dt.date() == now.date():
            return dt.strftime("%H:%M")
        elif (now - dt).days == 1:
            return "昨天"
        elif (now - dt).days < 7:
            return dt.strftime("%A")
        else:
            return dt.strftime("%Y-%m-%d")


class UnifiedInbox:
    """
    统一收件箱

    功能：
    - 聚合外部/内部/中继邮件
    - 统一排序
    - 增量同步
    """

    def __init__(self):
        self.data_dir = DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 外部邮件
        self.external_inbox_file = self.data_dir / "external.json"
        self.external_messages: Dict[str, UnifiedMailEntry] = {}

        # 内部邮件（引用已有的 MailboxHub）
        self.internal_messages: Dict[str, UnifiedMailEntry] = {}

        # 中继邮件（引用已有的 relay_sync）
        self.relay_messages: Dict[str, UnifiedMailEntry] = {}

        # 事件回调
        self._on_new_mail: Optional[Callable[[UnifiedMailEntry], None]] = None

        # 加载
        self._load_external()

    def set_on_new_mail(self, callback: Callable[[UnifiedMailEntry], None]):
        """设置新邮件回调"""
        self._on_new_mail = callback

    # ============ 加载邮件 ============

    def _load_external(self):
        """加载外部邮件"""
        if self.external_inbox_file.exists():
            try:
                with open(self.external_inbox_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for msg_id, entry_data in data.items():
                        self.external_messages[msg_id] = self._dict_to_entry(entry_data)
                logger.info(f"加载了 {len(self.external_messages)} 封外部邮件")
            except Exception as e:
                logger.error(f"加载外部邮件失败: {e}")

    def _save_external(self):
        """保存外部邮件"""
        data = {msg_id: self._entry_to_dict(entry) for msg_id, entry in self.external_messages.items()}
        with open(self.external_inbox_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _entry_to_dict(self, entry: UnifiedMailEntry) -> dict:
        """Entry 转 dict"""
        return {
            "message_id": entry.message_id,
            "source": entry.source,
            "account_id": entry.account_id,
            "provider": entry.provider,
            "subject": entry.subject,
            "body_text": entry.body_text,
            "body_html": entry.body_html,
            "from_addr": entry.from_addr,
            "from_name": entry.from_name,
            "to_addrs": entry.to_addrs,
            "cc_addrs": entry.cc_addrs,
            "date": entry.date,
            "is_read": entry.is_read,
            "is_starred": entry.is_starred,
            "is_deleted": entry.is_deleted,
            "labels": entry.labels,
            "has_attachments": entry.has_attachments,
            "attachment_count": entry.attachment_count,
            "thread_id": entry.thread_id,
        }

    def _dict_to_entry(self, data: dict) -> UnifiedMailEntry:
        """dict 转 Entry"""
        return UnifiedMailEntry(
            message_id=data["message_id"],
            source=data["source"],
            account_id=data.get("account_id", ""),
            provider=data.get("provider", ""),
            subject=data.get("subject", ""),
            body_text=data.get("body_text", ""),
            body_html=data.get("body_html", ""),
            from_addr=data.get("from_addr", ""),
            from_name=data.get("from_name", ""),
            to_addrs=data.get("to_addrs", []),
            cc_addrs=data.get("cc_addrs", []),
            date=data.get("date", 0),
            is_read=data.get("is_read", False),
            is_starred=data.get("is_starred", False),
            is_deleted=data.get("is_deleted", False),
            labels=data.get("labels", []),
            has_attachments=data.get("has_attachments", False),
            attachment_count=data.get("attachment_count", 0),
            thread_id=data.get("thread_id"),
        )

    # ============ 同步外部邮件 ============

    async def sync_external_account(self, account_id: str) -> int:
        """
        同步单个外部账号

        Returns:
            新增邮件数量
        """
        from .external_mail import get_imap_receiver

        receiver = get_imap_receiver()

        # 获取上次同步时间
        from .external_mail import get_external_account_manager
        manager = get_external_account_manager()
        account = manager.get_account(account_id)
        since_date = account.last_sync if account else None

        # 拉取新邮件
        new_messages = await receiver.fetch_new_emails(account_id, "INBOX", limit=50, since_date=since_date)

        new_count = 0
        for ext_msg in new_messages:
            entry = self._external_to_unified(ext_msg)
            if entry.message_id not in self.external_messages:
                self.external_messages[entry.message_id] = entry
                new_count += 1
                if self._on_new_mail:
                    self._on_new_mail(entry)

        if new_count > 0:
            self._save_external()

        logger.info(f"同步外部邮件: account={account_id}, 新增={new_count}")
        return new_count

    async def sync_all_external(self) -> int:
        """同步所有外部账号"""
        from .external_mail import get_external_account_manager

        manager = get_external_account_manager()
        accounts = manager.get_enabled_accounts()

        total_new = 0
        for account in accounts:
            try:
                new_count = await self.sync_external_account(account.id)
                total_new += new_count
            except Exception as e:
                logger.error(f"同步账号失败: {account.id}, {e}")

        return total_new

    def _external_to_unified(self, ext_msg) -> UnifiedMailEntry:
        """外部邮件转统一格式"""
        return UnifiedMailEntry(
            message_id=ext_msg.message_id,
            source="external",
            account_id=ext_msg.account_id,
            provider=self._get_provider_by_account(ext_msg.account_id),
            subject=ext_msg.subject,
            body_text=ext_msg.body_text,
            body_html=ext_msg.body_html,
            from_addr=ext_msg.from_addr,
            from_name=ext_msg.from_name,
            to_addrs=ext_msg.to_addrs,
            cc_addrs=ext_msg.cc_addrs,
            date=ext_msg.date,
            is_read=ext_msg.is_read,
            is_starred=ext_msg.is_starred,
            labels=ext_msg.labels,
            has_attachments=len(ext_msg.attachments) > 0,
            attachment_count=len(ext_msg.attachments),
            thread_id=ext_msg.thread_id,
            raw_ref=ext_msg,
        )

    def _get_provider_by_account(self, account_id: str) -> str:
        """通过账号 ID 获取提供商"""
        from .external_mail import get_external_account_manager
        account = get_external_account_manager().get_account(account_id)
        return account.provider if account else "unknown"

    # ============ 同步内部邮件 ============

    def load_internal_messages(self):
        """从 MailboxHub 加载内部邮件"""
        try:
            from . import get_mailbox_hub
            hub = get_mailbox_hub_sync()
            if not hub:
                return

            # 获取收件箱
            internal_msgs = hub.get_inbox(limit=100)

            for msg in internal_msgs:
                entry = self._internal_to_unified(msg)
                self.internal_messages[entry.message_id] = entry

            logger.info(f"加载了 {len(self.internal_messages)} 封内部邮件")
        except Exception as e:
            logger.error(f"加载内部邮件失败: {e}")

    def _internal_to_unified(self, msg) -> UnifiedMailEntry:
        """内部邮件转统一格式"""
        return UnifiedMailEntry(
            message_id=msg.message_id,
            source="internal",
            provider="internal",
            subject=msg.subject,
            body_text=msg.body_plain or "",
            from_addr=str(msg.from_addr) if msg.from_addr else "",
            to_addrs=[str(a) for a in msg.to_addrs],
            date=msg.created_at,
            is_read=msg.status.value in ("delivered", "read"),
            labels=msg.labels,
            has_attachments=msg.has_attachments,
            raw_ref=msg,
        )

    # ============ 中继邮件 ============

    def load_relay_messages(self):
        """从中继同步模块加载邮件"""
        try:
            from .relay_sync import get_relay_sync_client
            client = get_relay_sync_client()

            relay_entries = client.get_inbox(limit=100)

            for relay_entry in relay_entries:
                entry = self._relay_to_unified(relay_entry)
                self.relay_messages[entry.message_id] = entry

            logger.info(f"加载了 {len(self.relay_messages)} 封中继邮件")
        except Exception as e:
            logger.error(f"加载中继邮件失败: {e}")

    def _relay_to_unified(self, relay_entry) -> UnifiedMailEntry:
        """中继邮件转统一格式"""
        return UnifiedMailEntry(
            message_id=relay_entry.message_id,
            source="relay",
            provider="relay",
            subject=relay_entry.subject,
            body_text=relay_entry.body,
            from_addr=relay_entry.from_addr,
            date=relay_entry.date,
            is_read=relay_entry.is_read,
            labels=["relay"],
            raw_ref=relay_entry,
        )

    # ============ 查询 ============

    def get_inbox(self, limit: int = 50, offset: int = 0,
                  source: str = None, unread_only: bool = False) -> List[UnifiedMailEntry]:
        """
        获取统一收件箱

        Args:
            limit: 数量限制
            offset: 偏移
            source: 按来源过滤 (external/internal/relay)
            unread_only: 只看未读

        Returns:
            邮件列表（按时间倒序）
        """
        all_entries = []

        # 聚合所有来源
        if source is None or source == "external":
            all_entries.extend([e for e in self.external_messages.values() if not e.is_deleted])
        if source is None or source == "internal":
            all_entries.extend([e for e in self.internal_messages.values() if not e.is_deleted])
        if source is None or source == "relay":
            all_entries.extend([e for e in self.relay_messages.values() if not e.is_deleted])

        # 过滤未读
        if unread_only:
            all_entries = [e for e in all_entries if not e.is_read]

        # 按时间倒序
        all_entries.sort(key=lambda e: e.date, reverse=True)

        return all_entries[offset:offset + limit]

    def get_message(self, message_id: str) -> Optional[UnifiedMailEntry]:
        """获取单封邮件"""
        if message_id in self.external_messages:
            return self.external_messages[message_id]
        if message_id in self.internal_messages:
            return self.internal_messages[message_id]
        if message_id in self.relay_messages:
            return self.relay_messages[message_id]
        return None

    def get_unread_count(self) -> int:
        """获取未读数"""
        return sum(
            1 for entries in [self.external_messages, self.internal_messages, self.relay_messages]
            for e in entries.values()
            if not e.is_read and not e.is_deleted
        )

    def get_unread_by_source(self, source: str) -> int:
        """按来源获取未读数"""
        entries = getattr(self, f"{source}_messages", {})
        return sum(1 for e in entries.values() if not e.is_read and not e.is_deleted)

    # ============ 操作 ============

    def mark_as_read(self, message_id: str) -> bool:
        """标记为已读"""
        entry = self.get_message(message_id)
        if entry:
            entry.is_read = True
            # 同步到对应存储
            if entry.source == "external":
                self._save_external()
            logger.info(f"标记已读: {message_id}")
            return True
        return False

    def mark_as_unread(self, message_id: str) -> bool:
        """标记为未读"""
        entry = self.get_message(message_id)
        if entry:
            entry.is_read = False
            if entry.source == "external":
                self._save_external()
            return True
        return False

    def delete_message(self, message_id: str) -> bool:
        """删除邮件"""
        entry = self.get_message(message_id)
        if entry:
            entry.is_deleted = True
            if entry.source == "external":
                self._save_external()
            logger.info(f"删除邮件: {message_id}")
            return True
        return False

    def star_message(self, message_id: str) -> bool:
        """星标邮件"""
        entry = self.get_message(message_id)
        if entry:
            entry.is_starred = True
            if entry.source == "external":
                self._save_external()
            return True
        return False

    def unstar_message(self, message_id: str) -> bool:
        """取消星标"""
        entry = self.get_message(message_id)
        if entry:
            entry.is_starred = False
            if entry.source == "external":
                self._save_external()
            return True
        return False

    # ============ 搜索 ============

    def search(self, query: str, limit: int = 50) -> List[UnifiedMailEntry]:
        """搜索邮件"""
        query_lower = query.lower()
        results = []

        for entries in [self.external_messages, self.internal_messages, self.relay_messages]:
            for entry in entries.values():
                if entry.is_deleted:
                    continue
                # 简单匹配
                if (query_lower in entry.subject.lower() or
                    query_lower in entry.body_text.lower() or
                    query_lower in entry.from_addr.lower()):
                    results.append(entry)

        results.sort(key=lambda e: e.date, reverse=True)
        return results[:limit]

    # ============ 统计 ============

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total": len(self.external_messages) + len(self.internal_messages) + len(self.relay_messages),
            "external": {
                "total": len(self.external_messages),
                "unread": self.get_unread_by_source("external"),
            },
            "internal": {
                "total": len(self.internal_messages),
                "unread": self.get_unread_by_source("internal"),
            },
            "relay": {
                "total": len(self.relay_messages),
                "unread": self.get_unread_by_source("relay"),
            },
        }


# ============ 全局实例 ============

_unified_inbox: Optional[UnifiedInbox] = None


def get_unified_inbox() -> UnifiedInbox:
    """获取统一收件箱实例"""
    global _unified_inbox
    if _unified_inbox is None:
        _unified_inbox = UnifiedInbox()
    return _unified_inbox
