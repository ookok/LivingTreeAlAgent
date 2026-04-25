"""
会话管理器 - Session Manager
管理所有聊天会话: 私聊/群聊, 消息存储, 搜索, 已读未读

功能:
1. 会话列表管理
2. 消息存储与检索
3. 已读/未读状态
4. 会话置顶/免打扰
5. 消息搜索
"""

from core.logger import get_logger
logger = get_logger('unified_chat.session_manager')

import uuid
import time
import sqlite3
from typing import Optional, List, Dict, Callable, Any
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

from .models import (
    ChatSession, UnifiedMessage, MessageType, MessageStatus,
    SessionType, OnlineStatus, PeerInfo
)


class SearchScope(str, Enum):
    """搜索范围"""
    CURRENT_SESSION = "current"
    ALL_SESSIONS = "all"


@dataclass
class SearchResult:
    """搜索结果"""
    session_id: str
    session_name: str
    messages: List[UnifiedMessage] = field(default_factory=list)
    total_count: int = 0


class SessionManager:
    """
    会话管理器

    参考 Element/Telegram 的会话管理:
    - 左侧边栏显示所有会话
    - 按最后消息时间排序
    - 支持置顶/免打扰
    - 未读消息红点
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Args:
            db_path: 数据库路径, 默认 ~/.hermes-desktop/chat_sessions.db
        """
        if db_path is None:
            db_path = str(Path.home() / ".hermes-desktop" / "chat_sessions.db")

        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # 内存缓存
        self._sessions: Dict[str, ChatSession] = {}
        self._messages: Dict[str, Dict[str, UnifiedMessage]] = {}  # session_id -> msg_id -> msg

        # 当前会话
        self._current_session_id: Optional[str] = None

        # 回调
        self._callbacks: List[Callable] = []

        # 初始化数据库
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 会话表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT,
                peer_id TEXT,
                avatar TEXT,
                last_message_id TEXT,
                last_message_time REAL,
                unread_count INTEGER DEFAULT 0,
                is_pinned INTEGER DEFAULT 0,
                is_muted INTEGER DEFAULT 0,
                is_encrypted INTEGER DEFAULT 1,
                created_at REAL,
                updated_at REAL
            )
        """)

        # 消息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                msg_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT,
                sender_id TEXT,
                sender_name TEXT,
                sender_avatar TEXT,
                timestamp REAL,
                status TEXT,
                reply_to TEXT,
                reply_preview TEXT,
                encrypted INTEGER DEFAULT 0,
                encrypted_content BLOB,
                metadata TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)

        # 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_content ON messages(content)")

        conn.commit()
        conn.close()

    def add_callback(self, callback: Callable):
        """添加回调"""
        self._callbacks.append(callback)

    def _notify(self, event: str, data: Any):
        """通知回调"""
        for cb in self._callbacks:
            try:
                cb(event, data)
            except Exception as e:
                logger.info(f"[SessionManager] Callback error: {e}")

    # ============ 会话管理 ============

    def create_session(self,
                      session_type: SessionType,
                      peer_id: str = "",
                      name: str = "") -> ChatSession:
        """
        创建会话

        Args:
            session_type: 会话类型
            peer_id: 对端节点ID (私聊用)
            name: 会话名称

        Returns:
            ChatSession 对象
        """
        # 检查是否已存在私聊会话
        if session_type == SessionType.PRIVATE and peer_id:
            existing = self.get_session_by_peer(peer_id)
            if existing:
                return existing

        session = ChatSession(
            session_id=str(uuid.uuid4()),
            type=session_type,
            name=name,
            peer_id=peer_id,
            created_at=time.time()
        )

        # 存入数据库
        self._save_session(session)

        # 缓存
        self._sessions[session.session_id] = session
        self._messages[session.session_id] = {}

        self._notify("session_created", session)
        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """获取会话"""
        if session_id in self._sessions:
            return self._sessions[session_id]

        # 从数据库加载
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            session = self._row_to_session(row)
            self._sessions[session_id] = session
            return session
        return None

    def get_session_by_peer(self, peer_id: str) -> Optional[ChatSession]:
        """通过 peer_id 获取会话"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM sessions WHERE peer_id = ? AND type = ?",
            (peer_id, SessionType.PRIVATE.value)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            session = self._row_to_session(row)
            self._sessions[session.session_id] = session
            return session
        return None

    def get_all_sessions(self, include_hidden: bool = False) -> List[ChatSession]:
        """获取所有会话"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if include_hidden:
            cursor.execute("SELECT * FROM sessions ORDER BY is_pinned DESC, last_message_time DESC")
        else:
            cursor.execute("SELECT * FROM sessions ORDER BY is_pinned DESC, last_message_time DESC")

        rows = cursor.fetchall()
        conn.close()

        sessions = []
        for row in rows:
            session = self._row_to_session(row)
            self._sessions[session.session_id] = session
            sessions.append(session)

        return sessions

    def update_session(self, session: ChatSession):
        """更新会话"""
        session.updated_at = time.time()
        self._save_session(session)
        self._sessions[session.session_id] = session
        self._notify("session_updated", session)

    def delete_session(self, session_id: str):
        """删除会话"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

        if session_id in self._sessions:
            del self._sessions[session_id]
        if session_id in self._messages:
            del self._messages[session_id]

        self._notify("session_deleted", session_id)

    def pin_session(self, session_id: str, pinned: bool = True):
        """置顶/取消置顶会话"""
        session = self.get_session(session_id)
        if session:
            session.is_pinned = pinned
            self.update_session(session)

    def mute_session(self, session_id: str, muted: bool = True):
        """免打扰"""
        session = self.get_session(session_id)
        if session:
            session.is_muted = muted
            self.update_session(session)

    def set_current_session(self, session_id: Optional[str]):
        """设置当前会话"""
        self._current_session_id = session_id
        if session_id:
            self.mark_session_read(session_id)

    def get_current_session(self) -> Optional[str]:
        """获取当前会话ID"""
        return self._current_session_id

    def mark_session_read(self, session_id: str):
        """标记会话已读"""
        session = self.get_session(session_id)
        if session and session.unread_count > 0:
            session.unread_count = 0
            self.update_session(session)

    def get_total_unread_count(self) -> int:
        """获取总未读数"""
        return sum(s.unread_count for s in self._sessions.values())

    # ============ 消息管理 ============

    def add_message(self, message: UnifiedMessage) -> UnifiedMessage:
        """
        添加消息

        Args:
            message: UnifiedMessage 对象

        Returns:
            添加后的消息
        """
        # 确保会话存在
        if message.session_id not in self._messages:
            self._messages[message.session_id] = {}

        # 保存到数据库
        self._save_message(message)

        # 缓存
        self._messages[message.session_id][message.msg_id] = message

        # 更新会话
        session = self.get_session(message.session_id)
        if session:
            session.last_message = message
            session.last_message_time = message.timestamp
            if message.status == MessageStatus.DELIVERED or message.status == MessageStatus.READ:
                # 只有收到的消息才增加未读
                pass
            self._save_session(session)

        self._notify("message_added", message)
        return message

    def get_message(self, msg_id: str) -> Optional[UnifiedMessage]:
        """获取消息"""
        for session_msgs in self._messages.values():
            if msg_id in session_msgs:
                return session_msgs[msg_id]

        # 从数据库查找
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM messages WHERE msg_id = ?", (msg_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_message(row)
        return None

    def get_session_messages(self,
                            session_id: str,
                            before: float = 0,
                            limit: int = 50) -> List[UnifiedMessage]:
        """
        获取会话消息

        Args:
            session_id: 会话ID
            before: 时间戳, 获取此时间之前的消息 (0 表示最新)
            limit: 返回数量

        Returns:
            消息列表
        """
        # 先检查缓存
        if session_id in self._messages:
            cached = list(self._messages[session_id].values())
            cached.sort(key=lambda m: m.timestamp, reverse=True)
            if before == 0:
                return cached[:limit]
            return [m for m in cached if m.timestamp < before][:limit]

        # 从数据库加载
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if before > 0:
            cursor.execute(
                "SELECT * FROM messages WHERE session_id = ? AND timestamp < ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, before, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit)
            )

        rows = cursor.fetchall()
        conn.close()

        messages = []
        for row in rows:
            msg = self._row_to_message(row)
            if session_id not in self._messages:
                self._messages[session_id] = {}
            self._messages[session_id][msg.msg_id] = msg
            messages.append(msg)

        messages.sort(key=lambda m: m.timestamp, reverse=True)
        return messages

    def delete_message(self, msg_id: str):
        """删除消息"""
        message = self.get_message(msg_id)
        if message:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE msg_id = ?", (msg_id,))
            conn.commit()
            conn.close()

            if message.session_id in self._messages:
                if msg_id in self._messages[message.session_id]:
                    del self._messages[message.session_id][msg_id]

            self._notify("message_deleted", msg_id)

    def update_message_status(self, msg_id: str, status: MessageStatus):
        """更新消息状态"""
        message = self.get_message(msg_id)
        if message:
            message.status = status
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE messages SET status = ? WHERE msg_id = ?",
                (status.value, msg_id)
            )
            conn.commit()
            conn.close()
            self._notify("message_status_updated", (msg_id, status))

    # ============ 搜索 ============

    def search_messages(self,
                       query: str,
                       scope: SearchScope = SearchScope.ALL_SESSIONS,
                       session_id: str = "") -> SearchResult:
        """
        搜索消息

        Args:
            query: 搜索关键词
            scope: 搜索范围
            session_id: 指定会话 (scope=CURRENT_SESSION 时)

        Returns:
            SearchResult 对象
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if scope == SearchScope.CURRENT_SESSION and session_id:
            cursor.execute(
                "SELECT * FROM messages WHERE session_id = ? AND content LIKE ? ORDER BY timestamp DESC LIMIT 100",
                (session_id, f"%{query}%")
            )
        else:
            cursor.execute(
                "SELECT * FROM messages WHERE content LIKE ? ORDER BY timestamp DESC LIMIT 100",
                (f"%{query}%",)
            )

        rows = cursor.fetchall()
        conn.close()

        # 按会话分组
        session_messages: Dict[str, List[UnifiedMessage]] = {}
        for row in rows:
            msg = self._row_to_message(row)
            if msg.session_id not in session_messages:
                session_messages[msg.session_id] = []
            session_messages[msg.session_id].append(msg)

        results = []
        for sid, msgs in session_messages.items():
            session = self.get_session(sid)
            if session:
                results.append(SearchResult(
                    session_id=sid,
                    session_name=session.get_display_name(""),
                    messages=msgs[:5],  # 每个会话最多5条
                    total_count=len(msgs)
                ))

        return results

    # ============ 数据库操作 ============

    def _save_session(self, session: ChatSession):
        """保存会话到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO sessions (
                session_id, type, name, peer_id, avatar,
                last_message_id, last_message_time, unread_count,
                is_pinned, is_muted, is_encrypted, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.session_id,
            session.type.value,
            session.name,
            session.peer_id,
            session.avatar,
            session.last_message.msg_id if session.last_message else None,
            session.last_message_time,
            session.unread_count,
            int(session.is_pinned),
            int(session.is_muted),
            int(session.is_encrypted),
            session.created_at,
            getattr(session, 'updated_at', time.time())
        ))
        conn.commit()
        conn.close()

    def _save_message(self, message: UnifiedMessage):
        """保存消息到数据库"""
        import json
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO messages (
                msg_id, session_id, type, content, sender_id,
                sender_name, sender_avatar, timestamp, status,
                reply_to, reply_preview, encrypted, encrypted_content, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message.msg_id,
            message.session_id,
            message.type.value,
            str(message.content) if isinstance(message.content, (dict, list)) else message.content,
            message.sender_id,
            message.sender_name,
            message.sender_avatar,
            message.timestamp,
            message.status.value,
            message.reply_to,
            message.reply_preview,
            int(message.encrypted),
            message.encrypted_content,
            json.dumps(message.metadata) if message.metadata else None
        ))
        conn.commit()
        conn.close()

    def _row_to_session(self, row: tuple) -> ChatSession:
        """数据库行转 ChatSession"""
        return ChatSession(
            session_id=row[0],
            type=SessionType(row[1]),
            name=row[2] or "",
            peer_id=row[3] or "",
            avatar=row[4] or "",
            last_message_id=row[5],
            last_message_time=row[6] or 0,
            unread_count=row[7] or 0,
            is_pinned=bool(row[8]),
            is_muted=bool(row[9]),
            is_encrypted=bool(row[10]),
            created_at=row[11] or time.time()
        )

    def _row_to_message(self, row: tuple) -> UnifiedMessage:
        """数据库行转 UnifiedMessage"""
        import json

        metadata = None
        if row[14]:
            try:
                metadata = json.loads(row[14])
            except Exception:
                pass

        return UnifiedMessage(
            msg_id=row[0],
            session_id=row[1],
            type=MessageType(row[2]),
            content=row[3] or "",
            sender_id=row[4] or "",
            sender_name=row[5] or "",
            sender_avatar=row[6] or "",
            timestamp=row[7] or time.time(),
            status=MessageStatus(row[8]),
            reply_to=row[9],
            reply_preview=row[10] or "",
            encrypted=bool(row[11]),
            encrypted_content=row[12],
            metadata=metadata or {}
        )

    def close(self):
        """关闭数据库"""
        pass  # sqlite3 会自动关闭


# 单例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取会话管理器单例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
