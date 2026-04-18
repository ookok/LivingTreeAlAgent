"""
Database Connection - 数据库连接管理
=================================
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional
import threading

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .models import Base


class DatabaseManager:
    """数据库管理器"""
    
    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        
        self._engine = None
        self._session_factory = None
        self._sqlite_path = None
    
    def initialize(self, db_path: Optional[str] = None, use_sqlite: bool = True):
        """初始化数据库"""
        if use_sqlite:
            self._init_sqlite(db_path)
        else:
            self._init_postgresql(db_path)
    
    def _init_sqlite(self, db_path: Optional[str] = None):
        """初始化 SQLite"""
        if db_path is None:
            db_dir = Path.home() / ".hermes-desktop" / "relay_server" / "data"
            db_dir.mkdir(parents=True, exist_ok=True)
            self._sqlite_path = db_dir / "relay.db"
        
        # 使用 check_same_thread=False 支持多线程
        self._engine = create_engine(
            f"sqlite:///{self._sqlite_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        
        # 启用外键约束
        @event.listens_for(self._engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
        
        self._session_factory = sessionmaker(bind=self._engine)
        
        # 创建表
        Base.metadata.create_all(self._engine)
    
    def _init_postgresql(self, db_path: Optional[str] = None):
        """初始化 PostgreSQL"""
        # 从环境变量或配置获取连接字符串
        connection_string = os.environ.get(
            "HERMES_DB_URL",
            "postgresql://user:password@localhost:5432/hermes"
        )
        
        self._engine = create_engine(connection_string, pool_size=10, max_overflow=20)
        self._session_factory = sessionmaker(bind=self._engine)
        
        # 创建表
        Base.metadata.create_all(self._engine)
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """获取数据库会话"""
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_session_without_commit(self) -> Session:
        """获取数据库会话（不自动提交）"""
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._session_factory()
    
    @property
    def engine(self):
        """获取 SQLAlchemy 引擎"""
        return self._engine
    
    def close(self):
        """关闭数据库连接"""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None


# 全局实例
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """获取数据库管理器单例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        _db_manager.initialize()
    return _db_manager


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """获取数据库会话的便捷函数"""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        yield session


# 独立的 SQLite 辅助函数（不依赖 SQLAlchemy）

def get_sqlite_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """获取独立的 SQLite 连接（用于简单操作）"""
    if db_path is None:
        db_dir = Path.home() / ".hermes-desktop" / "relay_server" / "data"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "relay.db"
    
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # 启用外键
    conn.execute("PRAGMA foreign_keys=ON")
    
    return conn


@contextmanager
def sqlite_session(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """独立的 SQLite 会话上下文管理器"""
    conn = get_sqlite_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_sqlite_tables(db_path: Optional[str] = None):
    """初始化 SQLite 表结构"""
    conn = get_sqlite_connection(db_path)
    cursor = conn.cursor()
    
    # 用户表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT,
            token TEXT,
            token_expires_at TIMESTAMP,
            display_name TEXT,
            avatar_url TEXT,
            bio TEXT,
            is_active INTEGER DEFAULT 1,
            is_verified INTEGER DEFAULT 0,
            auth_provider TEXT DEFAULT 'local',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login_at TIMESTAMP
        )
    """)
    
    # 会话表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            title TEXT DEFAULT '新会话',
            session_type TEXT DEFAULT 'chat',
            context TEXT DEFAULT '{}',
            metadata TEXT DEFAULT '{}',
            is_active INTEGER DEFAULT 1,
            is_pinned INTEGER DEFAULT 0,
            is_archived INTEGER DEFAULT 0,
            message_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_message_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    # 消息表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT UNIQUE NOT NULL,
            session_id INTEGER NOT NULL,
            user_id INTEGER,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            content_type TEXT DEFAULT 'text',
            model TEXT,
            tokens_used INTEGER DEFAULT 0,
            metadata TEXT DEFAULT '{}',
            related_memories TEXT DEFAULT '[]',
            related_skills TEXT DEFAULT '[]',
            related_docs TEXT DEFAULT '[]',
            is_hidden INTEGER DEFAULT 0,
            is_edited INTEGER DEFAULT 0,
            edit_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            edited_at TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    
    # 用户配置表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            config_key TEXT NOT NULL,
            config_data TEXT DEFAULT '{}',
            client_id TEXT,
            platform TEXT DEFAULT 'unknown',
            version TEXT DEFAULT '2.0.0',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, config_key)
        )
    """)
    
    # 中继统计表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relay_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_id TEXT NOT NULL,
            client_id TEXT,
            user_id INTEGER,
            patches TEXT DEFAULT '[]',
            pain_points TEXT DEFAULT '[]',
            total_patches INTEGER DEFAULT 0,
            total_pain_points INTEGER DEFAULT 0,
            aggregated INTEGER DEFAULT 0,
            client_version TEXT DEFAULT '2.0.0',
            platform TEXT DEFAULT 'unknown',
            generated_at TIMESTAMP NOT NULL,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    
    # API Key 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key_id TEXT UNIQUE NOT NULL,
            key_hash TEXT UNIQUE NOT NULL,
            key_name TEXT,
            scopes TEXT DEFAULT '[]',
            rate_limit INTEGER DEFAULT 60,
            daily_limit INTEGER DEFAULT 10000,
            expires_at TIMESTAMP,
            total_calls INTEGER DEFAULT 0,
            today_calls INTEGER DEFAULT 0,
            last_used_at TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            is_revoked INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    # WebSocket 连接表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ws_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            channel TEXT DEFAULT 'default',
            client_ip TEXT,
            user_agent TEXT,
            is_active INTEGER DEFAULT 1,
            messages_sent INTEGER DEFAULT 0,
            messages_received INTEGER DEFAULT 0,
            bytes_transferred INTEGER DEFAULT 0,
            connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            disconnected_at TIMESTAMP,
            last_ping_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    
    # 创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_token ON users(token)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_active ON sessions(user_id, is_active)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_time ON messages(session_id, created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_relay_stats_week ON relay_stats(week_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_apikeys_user ON api_keys(user_id, is_active)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ws_channel ON ws_connections(channel, is_active)")
    
    conn.commit()
    conn.close()
