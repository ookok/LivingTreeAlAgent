"""
数据库连接管理器
支持多数据库类型连接池管理
"""

import sqlite3
import threading
import queue
from typing import Dict, Optional, Any
from contextlib import contextmanager
import logging

from .models import DatabaseType, ConnectionConfig, ConnectionStatus

logger = logging.getLogger(__name__)


class ConnectionError(Exception):
    """连接错误"""
    pass


class ConnectionManager:
    """
    多数据库连接管理器
    采用线程池+队列的连接池模式
    """

    def __init__(self, pool_size: int = 5):
        self.pool_size = pool_size
        self._connections: Dict[str, tuple] = {}  # connection_id -> (conn, lock, config)
        self._pools: Dict[str, queue.Queue] = {}  # db_type -> connection queue
        self._status: Dict[str, ConnectionStatus] = {}
        self._error_msg: Dict[str, str] = {}

    def connect(self, config: ConnectionConfig) -> bool:
        """
        建立数据库连接
        Returns: 是否连接成功
        """
        conn_id = config.get_id()
        try:
            conn = self._create_connection(config)
            if conn is not None:
                self._connections[conn_id] = (conn, threading.Lock(), config)
                self._status[conn_id] = ConnectionStatus.CONNECTED
                self._error_msg.pop(conn_id, None)
                logger.info(f"数据库连接成功: {config.name} ({config.db_type.value})")
                return True
        except Exception as e:
            self._status[conn_id] = ConnectionStatus.ERROR
            self._error_msg[conn_id] = str(e)
            logger.error(f"数据库连接失败: {config.name} - {e}")
        return False

    def disconnect(self, connection_id: str) -> bool:
        """断开连接"""
        if connection_id in self._connections:
            conn, _, _ = self._connections.pop(connection_id)
            try:
                if hasattr(conn, 'close'):
                    conn.close()
            except Exception:
                pass
            self._status.pop(connection_id, None)
            self._error_msg.pop(connection_id, None)
            logger.info(f"数据库连接已断开: {connection_id}")
            return True
        return False

    def get_connection(self, connection_id: str) -> Optional[Any]:
        """获取连接对象"""
        if connection_id in self._connections:
            conn, lock, _ = self._connections[connection_id]
            return conn
        return None

    def test_connection(self, config: ConnectionConfig) -> Tuple[bool, str]:
        """
        测试连接是否可用
        Returns: (是否成功, 错误消息)
        """
        try:
            conn = self._create_connection(config)
            if conn:
                # 执行简单查询
                if config.db_type == DatabaseType.SQLITE:
                    cursor = conn.execute("SELECT 1")
                    cursor.fetchone()
                elif config.db_type == DatabaseType.MYSQL:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                    cursor.close()
                elif config.db_type == DatabaseType.POSTGRESQL:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                    cursor.close()
                conn.close()
                return True, ""
        except Exception as e:
            return False, str(e)
        return False, "未知错误"

    def is_connected(self, connection_id: str) -> bool:
        """检查连接状态"""
        if connection_id not in self._connections:
            return False
        conn, _, _ = self._connections[connection_id]
        try:
            if connection_id.startswith("sqlite"):
                conn.execute("SELECT 1")
                return True
            elif connection_id.startswith("mysql") or connection_id.startswith("postgresql"):
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                return True
        except Exception:
            return False
        return True

    def get_status(self, connection_id: str) -> ConnectionStatus:
        """获取连接状态"""
        return self._status.get(connection_id, ConnectionStatus.DISCONNECTED)

    def get_error(self, connection_id: str) -> str:
        """获取错误消息"""
        return self._error_msg.get(connection_id, "")

    def list_connections(self) -> List[str]:
        """列出所有连接ID"""
        return list(self._connections.keys())

    def _create_connection(self, config: ConnectionConfig):
        """创建数据库连接"""
        db_type = config.db_type

        if db_type == DatabaseType.SQLITE:
            return self._connect_sqlite(config)
        elif db_type == DatabaseType.MYSQL:
            return self._connect_mysql(config)
        elif db_type == DatabaseType.POSTGRESQL:
            return self._connect_postgresql(config)
        elif db_type == DatabaseType.REDIS:
            return self._connect_redis(config)
        elif db_type == DatabaseType.MONGODB:
            return self._connect_mongodb(config)
        elif db_type == DatabaseType.DUCKDB:
            return self._connect_duckdb(config)
        else:
            raise ConnectionError(f"不支持的数据库类型: {db_type.value}")

    def _connect_sqlite(self, config: ConnectionConfig):
        """连接 SQLite"""
        import os
        file_path = config.file_path
        if file_path:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
        conn = sqlite3.connect(file_path or ":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _connect_mysql(self, config: ConnectionConfig):
        """连接 MySQL"""
        try:
            import pymysql
            from pymysql.cursors import DictCursor
            return pymysql.connect(
                host=config.host or "localhost",
                port=config.port or 3306,
                user=config.username,
                password=config.password,
                database=config.database,
                charset=config.charset or "utf8mb4",
                connect_timeout=10,
                read_timeout=30,
                write_timeout=30,
            )
        except ImportError:
            raise ConnectionError("pymysql 未安装，请执行: pip install pymysql")

    def _connect_postgresql(self, config: ConnectionConfig):
        """连接 PostgreSQL"""
        try:
            import psycopg2
            return psycopg2.connect(
                host=config.host or "localhost",
                port=config.port or 5432,
                user=config.username,
                password=config.password,
                database=config.database,
                connect_timeout=10,
            )
        except ImportError:
            raise ConnectionError("psycopg2 未安装，请执行: pip install psycopg2-binary")

    def _connect_redis(self, config: ConnectionConfig):
        """连接 Redis"""
        try:
            import redis
            return redis.Redis(
                host=config.host or "localhost",
                port=config.port or 6379,
                db=config.db_index or 0,
                password=config.password_rd,
                decode_responses=True,
                socket_timeout=10,
                socket_connect_timeout=10,
            )
        except ImportError:
            raise ConnectionError("redis 未安装，请执行: pip install redis")

    def _connect_mongodb(self, config: ConnectionConfig):
        """连接 MongoDB"""
        try:
            from pymongo import MongoClient
            auth = f"{config.username}:{config.password}@" if config.username else ""
            host = config.host or "localhost"
            port = config.port or 27017
            uri = f"mongodb://{auth}{host}:{port}/{config.database or 'admin'}?authSource={config.auth_source}"
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            # 测试连接
            client.admin.command('ping')
            return client
        except ImportError:
            raise ConnectionError("pymongo 未安装，请执行: pip install pymongo")

    def _connect_duckdb(self, config: ConnectionConfig):
        """连接 DuckDB"""
        try:
            import duckdb
            if config.file_path:
                return duckdb.connect(config.file_path)
            return duckdb.connect(":memory:")
        except ImportError:
            raise ConnectionError("duckdb 未安装，请执行: pip install duckdb")

    @contextmanager
    def get_conn_context(self, connection_id: str):
        """上下文管理器获取连接"""
        if connection_id not in self._connections:
            raise ConnectionError(f"连接不存在: {connection_id}")
        conn, lock, config = self._connections[connection_id]
        with lock:
            yield conn

    def close_all(self):
        """关闭所有连接"""
        for conn_id in list(self._connections.keys()):
            self.disconnect(conn_id)


from typing import Tuple
