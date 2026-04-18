"""
Database Connection - 数据库连接管理

沃土库 (The Soil Bank)
"""

import sqlite3
import threading
from pathlib import Path
from typing import Optional, Any
from contextlib import contextmanager


class Database:
    """数据库单例"""

    _instance: Optional["Database"] = None
    _lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # 默认数据库路径
            home = Path.home()
            hermes_dir = home / ".hermes-desktop"
            hermes_dir.mkdir(exist_ok=True)
            db_path = hermes_dir / "hermes.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[sqlite3.Connection] = None

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> "Database":
        """获取数据库单例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db_path)
        return cls._instance

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            # 启用WAL模式
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys=ON")
        return self._connection

    @contextmanager
    def transaction(self):
        """事务上下文管理器"""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行SQL"""
        conn = self.get_connection()
        return conn.execute(sql, params)

    def executemany(self, sql: str, params_list: list) -> sqlite3.Cursor:
        """批量执行SQL"""
        conn = self.get_connection()
        return conn.executemany(sql, params_list)

    def close(self):
        """关闭数据库"""
        if self._connection:
            self._connection.close()
            self._connection = None


# 全局数据库实例
_db: Optional[Database] = None


def get_db(db_path: Optional[str] = None) -> Database:
    """获取数据库实例"""
    global _db
    if _db is None:
        _db = Database.get_instance(db_path)
    return _db
