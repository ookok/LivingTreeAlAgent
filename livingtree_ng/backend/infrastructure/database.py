"""
数据库系统 - SQLite 轻量级数据库
"""

import sqlite3
import json
import logging
import time
from pathlib import Path
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Generator

logger = logging.getLogger(__name__)


class Database:
    """SQLite 数据库管理"""
    
    def __init__(self, db_path: str = "data/db.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        
        # 初始化表
        self._init_tables()
    
    @contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.commit()
            conn.close()
    
    def _init_tables(self):
        """初始化数据库表"""
        with self._get_conn() as conn:
            # 会话表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    created_at REAL DEFAULT (strftime('%s', 'now')),
                    updated_at REAL DEFAULT (strftime('%s', 'now')),
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            # 消息表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp REAL DEFAULT (strftime('%s', 'now')),
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            
            # 知识表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    content TEXT,
                    embedding TEXT,
                    metadata TEXT DEFAULT '{}',
                    created_at REAL DEFAULT (strftime('%s', 'now')),
                    updated_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            # 配置表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS configs (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            logger.debug("Database tables initialized")
    
    # ========================================
    # 会话操作
    # ========================================
    
    def create_session(self, name: str = "New Session") -> str:
        """创建新会话"""
        import uuid
        session_id = str(uuid.uuid4())
        
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO sessions (id, name) VALUES (?, ?)",
                (session_id, name)
            )
        
        logger.info(f"Created session: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None
    
    def list_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取会话列表"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def update_session(self, session_id: str, name: Optional[str] = None, metadata: Optional[Dict] = None):
        """更新会话"""
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))
        
        if updates:
            updates.append("updated_at = strftime('%s', 'now')")
            params.append(session_id)
            
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?",
                    tuple(params)
                )
    
    # ========================================
    # 消息操作
    # ========================================
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> str:
        """添加消息"""
        import uuid
        msg_id = str(uuid.uuid4())
        
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO messages (id, session_id, role, content) VALUES (?, ?, ?, ?)",
                (msg_id, session_id, role, content)
            )
            
            # 更新会话更新时间
            conn.execute(
                "UPDATE sessions SET updated_at = strftime('%s', 'now') WHERE id = ?",
                (session_id,)
            )
        
        logger.debug(f"Added message: {msg_id}")
        return msg_id
    
    def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取会话消息"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT ? OFFSET ?",
                (session_id, limit, offset)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # ========================================
    # 知识操作
    # ========================================
    
    def add_knowledge(
        self,
        knowledge_type: str,
        content: str,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """添加知识"""
        import uuid
        knowledge_id = str(uuid.uuid4())
        
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO knowledge (id, type, content, embedding, metadata) VALUES (?, ?, ?, ?, ?)",
                (
                    knowledge_id,
                    knowledge_type,
                    content,
                    json.dumps(embedding) if embedding else None,
                    json.dumps(metadata) if metadata else None
                )
            )
        
        logger.debug(f"Added knowledge: {knowledge_id}")
        return knowledge_id
    
    def search_knowledge(
        self,
        content_query: str,
        knowledge_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """搜索知识（简单版）"""
        with self._get_conn() as conn:
            if knowledge_type:
                cursor = conn.execute(
                    "SELECT * FROM knowledge WHERE type = ? AND content LIKE ? ORDER BY updated_at DESC LIMIT ?",
                    (knowledge_type, f"%{content_query}%", limit)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM knowledge WHERE content LIKE ? ORDER BY updated_at DESC LIMIT ?",
                    (f"%{content_query}%", limit)
                )
            
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                if data['embedding']:
                    data['embedding'] = json.loads(data['embedding'])
                if data['metadata']:
                    data['metadata'] = json.loads(data['metadata'])
                results.append(data)
            
            return results


# 全局单例
_db_instance: Optional[Database] = None


def get_database() -> Database:
    """获取数据库单例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
