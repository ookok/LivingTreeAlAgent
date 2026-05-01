"""
会话管理系统
存储聊天历史、会话信息
"""
import json
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import List, Optional
from pathlib import Path


@dataclass
class Message:
    role: str
    content: str
    timestamp: float = 0.0


@dataclass
class Session:
    id: str
    title: str
    created_at: float = 0.0
    updated_at: float = 0.0


class SessionManager:
    """会话管理器"""
    
    def __init__(self, db_path: str = "livingtree_ng.db"):
        self.db_path = db_path
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def _init_db(self):
        """初始化数据库"""
        with self._get_connection() as conn:
            # 会话表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            
            # 消息表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            """)
            conn.commit()
    
    def create_session(self, title: str = "新会话") -> Session:
        """创建会话"""
        session_id = f"sess_{int(time.time() * 1000)}"
        now = time.time()
        
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, now, now)
            )
            conn.commit()
        
        return Session(id=session_id, title=title, created_at=now, updated_at=now)
    
    def list_sessions(self) -> List[Session]:
        """列出所有会话"""
        sessions = []
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, title, created_at, updated_at
                FROM sessions
                ORDER BY updated_at DESC
            """)
            
            for row in cursor:
                sessions.append(Session(id=row[0], title=row[1], created_at=row[2], updated_at=row[3]))
        
        return sessions
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
                (session_id,)
            )
            
            row = cursor.fetchone()
            if row:
                return Session(id=row[0], title=row[1], created_at=row[2], updated_at=row[3])
        
        return None
    
    def add_message(self, session_id: str, role: str, content: str) -> Message:
        """添加消息"""
        now = time.time()
        
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, role, content, now)
            )
            
            # 更新会话的最后更新时间
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id)
            )
            conn.commit()
        
        return Message(role=role, content=content, timestamp=now)
    
    def get_messages(self, session_id: str) -> List[Message]:
        """获取会话消息"""
        messages = []
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT role, content, timestamp
                FROM messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """, (session_id,))
            
            for row in cursor:
                messages.append(Message(role=row[0], content=row[1], timestamp=row[2]))
        
        return messages
    
    def update_session_title(self, session_id: str, title: str):
        """更新会话标题"""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title, time.time(), session_id)
            )
            conn.commit()
    
    def delete_session(self, session_id: str):
        """删除会话"""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()


# 全局单例
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """获取单例 SessionManager"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
