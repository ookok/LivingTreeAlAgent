"""
本地邮件事件总线 (Local Mailbox & Event Bus)
============================================

单机模式下，"发邮件"本质是应用内的消息队列：
- 不走网络 Socket，直接 INSERT 进入本地 SQLite
- 通过 Observer Pattern 实现"秒级刷新"
- 附件使用 file:// 协议指向本地路径
"""

import asyncio
import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from .event_bus import Event, EventBus


class MessageStatus(Enum):
    """消息状态"""
    DRAFT = "draft"           # 草稿
    PENDING = "pending"       # 待发送
    SENT = "sent"            # 已发送
    DELIVERED = "delivered"  # 已送达
    READ = "read"            # 已读
    ARCHIVED = "archived"     # 已归档


@dataclass
class LocalMessage:
    """本地消息"""
    message_id: str
    from_node_id: str
    to_node_id: str           # 单机模式下 to 就是自己
    subject: str
    content: str
    attachments: list[str] = field(default_factory=list)  # 文件路径列表
    status: MessageStatus = MessageStatus.SENT
    created_at: datetime = field(default_factory=datetime.now)
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)
    is_external: bool = False  # 是否外部邮件


@dataclass
class MessageObserver:
    """消息观察者"""
    observer_id: str
    callback: Callable[[LocalMessage], None]
    filter_tags: Optional[list[str]] = None


class LocalMailbox:
    """
    本地邮件箱

    单机模式下的邮件系统：
    - 邮件发送降级为"本地事件总线"
    - 外部邮件显示"离线提示"
    - 附件使用 file:// 协议
    """

    def __init__(self, data_dir: Path, event_bus: EventBus):
        self.data_dir = data_dir / "mailbox"
        self.event_bus = event_bus
        self.db_path = self.data_dir / "messages.db"

        # 观察者
        self._observers: list[MessageObserver] = []
        self._observer_lock = threading.Lock()

        # 状态
        self._initialized = False

    async def init(self) -> bool:
        """初始化"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._init_database()
        self._initialized = True
        return True

    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 消息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                from_node_id TEXT NOT NULL,
                to_node_id TEXT NOT NULL,
                subject TEXT,
                content TEXT,
                attachments TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                delivered_at TEXT,
                read_at TEXT,
                tags TEXT,
                is_external INTEGER DEFAULT 0
            )
        """)

        # 草稿表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                draft_id TEXT PRIMARY KEY,
                from_node_id TEXT NOT NULL,
                to_node_id TEXT,
                subject TEXT,
                content TEXT,
                attachments TEXT,
                updated_at TEXT NOT NULL
            )
        """)

        # 索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_to_node
            ON messages(to_node_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_status
            ON messages(status)
        """)

        conn.commit()
        conn.close()

    def generate_message_id(self, content: str) -> str:
        """生成消息 ID"""
        raw = f"{content}{datetime.now().isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def send_local(
        self,
        to_node_id: str,
        subject: str,
        content: str,
        attachments: Optional[list[str]] = None,
        tags: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """
        发送本地邮件（单机模式）

        直接写入本地数据库，模拟"秒级送达"
        """
        from_node_id = "local"  # 本地节点

        message = LocalMessage(
            message_id=self.generate_message_id(content),
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            subject=subject,
            content=content,
            attachments=attachments or [],
            status=MessageStatus.DELIVERED,
            created_at=datetime.now(),
            delivered_at=datetime.now(),
            tags=tags or [],
            is_external=False
        )

        # 保存到数据库
        await self._save_message(message)

        # 通知观察者
        self._notify_observers(message)

        # 发布事件
        self.event_bus.publish(Event(
            type="mailbox.message_sent",
            source="local_mailbox",
            data={
                "message_id": message.message_id,
                "to": to_node_id,
                "subject": subject
            }
        ))

        return {
            "success": True,
            "message_id": message.message_id,
            "status": "delivered",
            "mode": "local"
        }

    async def send_external_draft(
        self,
        to: str,
        subject: str,
        content: str,
        attachments: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """
        发送外部邮件（仅保存草稿）

        单机模式下，外部邮件保存至草稿箱，不实际发送
        """
        message = LocalMessage(
            message_id=self.generate_message_id(content),
            from_node_id="local",
            to_node_id=to,
            subject=subject,
            content=content,
            attachments=attachments or [],
            status=MessageStatus.PENDING,  # 待发送状态
            created_at=datetime.now(),
            tags=["pending_external"],
            is_external=True
        )

        # 保存为草稿
        await self._save_message(message)

        # 发布事件
        self.event_bus.publish(Event(
            type="mailbox.external_queued",
            source="local_mailbox",
            data={
                "message_id": message.message_id,
                "to": to,
                "warning": "单机模式，外部邮件已保存至待发队列"
            }
        ))

        return {
            "success": True,
            "message_id": message.message_id,
            "status": "queued",
            "mode": "standalone",
            "warning": "单机模式下无法连接公网 SMTP，邮件已保存至草稿箱"
        }

    async def _save_message(self, message: LocalMessage):
        """保存消息到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO messages
            (message_id, from_node_id, to_node_id, subject, content,
             attachments, status, created_at, delivered_at, read_at,
             tags, is_external)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message.message_id,
            message.from_node_id,
            message.to_node_id,
            message.subject,
            message.content,
            json.dumps(message.attachments),
            message.status.value,
            message.created_at.isoformat(),
            message.delivered_at.isoformat() if message.delivered_at else None,
            message.read_at.isoformat() if message.read_at else None,
            ",".join(message.tags),
            1 if message.is_external else 0
        ))

        conn.commit()
        conn.close()

    async def get_messages(
        self,
        node_id: str,
        status: Optional[MessageStatus] = None,
        limit: int = 50
    ) -> list[LocalMessage]:
        """获取消息列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if status:
            cursor.execute("""
                SELECT * FROM messages
                WHERE to_node_id = ? AND status = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (node_id, status.value, limit))
        else:
            cursor.execute("""
                SELECT * FROM messages
                WHERE to_node_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (node_id, limit))

        rows = cursor.fetchall()
        conn.close()

        messages = []
        for row in rows:
            messages.append(self._row_to_message(row))

        return messages

    async def get_message(self, message_id: str) -> Optional[LocalMessage]:
        """获取单条消息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_message(row)
        return None

    def _row_to_message(self, row: tuple) -> LocalMessage:
        """数据库行转消息对象"""
        return LocalMessage(
            message_id=row[0],
            from_node_id=row[1],
            to_node_id=row[2],
            subject=row[3] or "",
            content=row[4] or "",
            attachments=json.loads(row[5]) if row[5] else [],
            status=MessageStatus(row[6]),
            created_at=datetime.fromisoformat(row[7]),
            delivered_at=datetime.fromisoformat(row[8]) if row[8] else None,
            read_at=datetime.fromisoformat(row[9]) if row[9] else None,
            tags=row[10].split(",") if row[10] else [],
            is_external=bool(row[11])
        )

    async def mark_read(self, message_id: str):
        """标记已读"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE messages
            SET status = ?, read_at = ?
            WHERE message_id = ?
        """, (MessageStatus.READ.value, datetime.now().isoformat(), message_id))

        conn.commit()
        conn.close()

        # 发布事件
        self.event_bus.publish(Event(
            type="mailbox.message_read",
            source="local_mailbox",
            data={"message_id": message_id}
        ))

    # ========== 观察者模式 ==========

    def add_observer(self, observer: MessageObserver):
        """添加观察者"""
        with self._observer_lock:
            self._observers.append(observer)

    def remove_observer(self, observer_id: str):
        """移除观察者"""
        with self._observer_lock:
            self._observers = [o for o in self._observers if o.observer_id != observer_id]

    def _notify_observers(self, message: LocalMessage):
        """通知观察者"""
        with self._observer_lock:
            for observer in self._observers:
                if observer.filter_tags:
                    # 根据标签过滤
                    if any(tag in message.tags for tag in observer.filter_tags):
                        observer.callback(message)
                else:
                    observer.callback(message)

    async def get_pending_external(self) -> list[LocalMessage]:
        """获取待发送的外部邮件"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM messages
            WHERE status = ? AND is_external = 1
            ORDER BY created_at ASC
        """, (MessageStatus.PENDING.value,))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_message(row) for row in rows]

    async def get_stats(self) -> dict[str, Any]:
        """获取邮件统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # 总消息数
        cursor.execute("SELECT COUNT(*) FROM messages")
        stats["total"] = cursor.fetchone()[0]

        # 未读数
        cursor.execute("""
            SELECT COUNT(*) FROM messages
            WHERE status != ? AND is_external = 0
        """, (MessageStatus.READ.value,))
        stats["unread"] = cursor.fetchone()[0]

        # 外部待发数
        cursor.execute("""
            SELECT COUNT(*) FROM messages
            WHERE status = ? AND is_external = 1
        """, (MessageStatus.PENDING.value,))
        stats["pending_external"] = cursor.fetchone()[0]

        conn.close()
        return stats

    async def shutdown(self):
        """关闭"""
        self._initialized = False


def create_local_mailbox(data_dir: Path, event_bus: EventBus) -> LocalMailbox:
    """创建本地邮件箱"""
    return LocalMailbox(data_dir=data_dir, event_bus=event_bus)