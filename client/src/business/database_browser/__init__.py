"""
数据库浏览器 (Database Browser)
借鉴 onetcli (feigeCode/onetcli) 多数据库管理架构

支持：
- 8 种数据库：SQLite, MySQL, PostgreSQL, SQL Server, Oracle, ClickHouse, Redis, MongoDB, DuckDB
- 数据库树浏览（表/列/索引/视图/存储过程）
- SQL 查询执行与结果分页
- AI 自然语言生成 SQL / 解释 SQL
- 表结构设计与 DDL 预览
- 查询历史与收藏
- Redis 键值浏览
- MongoDB 集合浏览
"""

import sqlite3
import threading
import json
import time
import hashlib
import logging
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

from .models import (
    DatabaseType, ConnectionConfig, ConnectionStatus,
    TableSchema, ColumnInfo, QueryResult, QueryResultType,
    DatabaseTreeNode, HistoryItem, FavoriteQuery,
    DEFAULT_PORTS, check_driver_available, get_available_databases
)
from .connection_manager import ConnectionManager, ConnectionError
from .schema_explorer import SchemaExplorer
from .query_executor import QueryExecutor
from .sql_generator import SQLGenerator

logger = logging.getLogger(__name__)


class DatabaseBrowser:
    """
    数据库浏览器主系统
    统一入口，管理连接、查询、AI 生成
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: str = ""):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._initialized = True
        self._db_path = db_path or self._get_default_db_path()

        # 核心组件
        self.conn_manager = ConnectionManager()
        self.schema_explorer = SchemaExplorer(self.conn_manager)
        self.query_executor = QueryExecutor(self.conn_manager)
        self.sql_generator = SQLGenerator()

        # 连接池
        self._connections: Dict[str, ConnectionConfig] = {}
        self._active_connection_id: Optional[str] = None

        # 历史记录（内存+持久化）
        self._history: List[HistoryItem] = []
        self._favorites: List[FavoriteQuery] = []
        self._max_history = 200
        self._max_favorites = 100

        # 初始化数据库
        self._init_db()

        # 加载保存的连接
        self._load_saved_connections()

        # 设置 SQL 生成器的 LLM 客户端
        self._setup_llm_client()

    def _get_default_db_path(self) -> str:
        """获取默认数据库路径"""
        import os
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_dir = os.path.join(base, "database")
        os.makedirs(db_dir, exist_ok=True)
        return os.path.join(db_dir, "database_browser.db")

    def _init_db(self):
        """初始化存储数据库"""
        self._db_conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._db_conn.row_factory = sqlite3.Row

        self._db_conn.executescript("""
            CREATE TABLE IF NOT EXISTS db_connections (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                config_json TEXT NOT NULL,
                created_at REAL DEFAULT (julianday('now')),
                last_used_at REAL
            );

            CREATE TABLE IF NOT EXISTS query_history (
                id TEXT PRIMARY KEY,
                connection_id TEXT,
                sql TEXT NOT NULL,
                execution_time REAL,
                row_count INTEGER,
                is_error INTEGER DEFAULT 0,
                timestamp REAL DEFAULT (julianday('now'))
            );

            CREATE TABLE IF NOT EXISTS favorite_queries (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                sql TEXT NOT NULL,
                connection_id TEXT,
                description TEXT,
                created_at REAL DEFAULT (julianday('now'))
            );

            CREATE TABLE IF NOT EXISTS query_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                sql TEXT NOT NULL,
                description TEXT,
                db_types TEXT DEFAULT '[]',
                created_at REAL DEFAULT (julianday('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_history_timestamp ON query_history(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_history_connection ON query_history(connection_id);
            CREATE INDEX IF NOT EXISTS idx_favorites_created ON favorite_queries(created_at DESC);
        """)

    def _load_saved_connections(self):
        """加载保存的连接"""
        try:
            cursor = self._db_conn.execute(
                "SELECT id, config_json FROM db_connections"
            )
            for row in cursor.fetchall():
                conn_id, config_json = row
                try:
                    data = json.loads(config_json)
                    config = ConnectionConfig.from_dict(data)
                    self._connections[conn_id] = config
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"加载保存的连接失败: {e}")

    def _setup_llm_client(self):
        """设置 LLM 客户端"""
        try:
            from client.src.business.system_brain import SystemBrain
            brain = SystemBrain()
            self.sql_generator.set_llm_client(brain)
            logger.info("DatabaseBrowser LLM 客户端已设置")
        except Exception as e:
            logger.warning(f"DatabaseBrowser LLM 客户端设置失败: {e}")

    # ========== 连接管理 ==========

    def add_connection(self, config: ConnectionConfig) -> Tuple[bool, str]:
        """添加连接配置"""
        conn_id = config.get_id()

        # 测试连接
        success, error = self.conn_manager.test_connection(config)
        if not success:
            return False, f"连接失败: {error}"

        # 保存
        self._connections[conn_id] = config
        self._save_connection(conn_id, config)
        return True, conn_id

    def remove_connection(self, connection_id: str) -> bool:
        """删除连接"""
        # 断开
        self.conn_manager.disconnect(connection_id)

        # 删除
        if connection_id in self._connections:
            del self._connections[connection_id]

        # 从数据库删除
        try:
            self._db_conn.execute("DELETE FROM db_connections WHERE id = ?", (connection_id,))
            self._db_conn.commit()
        except Exception:
            pass

        if self._active_connection_id == connection_id:
            self._active_connection_id = None

        return True

    def connect(self, connection_id: str) -> Tuple[bool, str]:
        """建立连接"""
        config = self._connections.get(connection_id)
        if not config:
            return False, "连接配置不存在"

        success = self.conn_manager.connect(config)
        if success:
            self._active_connection_id = connection_id
            # 更新最后使用时间
            self._db_conn.execute(
                "UPDATE db_connections SET last_used_at = julianday('now') WHERE id = ?",
                (connection_id,)
            )
            self._db_conn.commit()
            return True, ""
        else:
            error = self.conn_manager.get_error(connection_id)
            return False, error

    def disconnect(self, connection_id: str) -> bool:
        """断开连接"""
        return self.conn_manager.disconnect(connection_id)

    def get_connection(self, connection_id: str) -> Optional[ConnectionConfig]:
        """获取连接配置"""
        return self._connections.get(connection_id)

    def list_connections(self) -> List[ConnectionConfig]:
        """列出所有连接"""
        return list(self._connections.values())

    def get_active_connection(self) -> Optional[ConnectionConfig]:
        """获取当前活动连接"""
        if self._active_connection_id:
            return self._connections.get(self._active_connection_id)
        return None

    def set_active_connection(self, connection_id: str):
        """设置当前活动连接"""
        self._active_connection_id = connection_id

    def _save_connection(self, conn_id: str, config: ConnectionConfig):
        """保存连接配置"""
        config_json = json.dumps(config.to_dict(), ensure_ascii=False)
        try:
            self._db_conn.execute("""
                INSERT OR REPLACE INTO db_connections (id, name, config_json, created_at)
                VALUES (?, ?, ?, julianday('now'))
            """, (conn_id, config.name, config_json))
            self._db_conn.commit()
        except Exception as e:
            logger.warning(f"保存连接失败: {e}")

    # ========== 查询执行 ==========

    def execute(self, sql: str, page: int = 1, page_size: int = 100) -> QueryResult:
        """执行 SQL"""
        if not self._active_connection_id:
            return QueryResult(
                result_type=QueryResultType.ERROR,
                error_message="未选择数据库连接"
            )

        result = self.query_executor.execute(
            self._active_connection_id, sql, page, page_size
        )

        # 记录历史
        self._add_history(self._active_connection_id, sql, result)

        return result

    def execute_batch(self, sql: str) -> QueryResult:
        """批量执行"""
        if not self._active_connection_id:
            return QueryResult(result_type=QueryResultType.ERROR, error_message="未选择数据库连接")

        result = self.query_executor.execute_batch(self._active_connection_id, sql)
        self._add_history(self._active_connection_id, sql, result)
        return result

    def explain(self, sql: str) -> QueryResult:
        """执行计划"""
        if not self._active_connection_id:
            return QueryResult(result_type=QueryResultType.ERROR, error_message="未选择数据库连接")
        return self.query_executor.get_explain(self._active_connection_id, sql)

    def _add_history(self, connection_id: str, sql: str, result: QueryResult):
        """添加历史记录"""
        item = HistoryItem(
            id=hashlib.md5(f"{time.time()}{sql}".encode()).hexdigest()[:16],
            connection_id=connection_id,
            sql=sql[:500],  # 截断
            execution_time=result.execution_time,
            row_count=result.row_count if result.result_type == QueryResultType.TABLE else 0,
            timestamp=time.time(),
            is_error=result.result_type == QueryResultType.ERROR
        )

        self._history.insert(0, item)
        if len(self._history) > self._max_history:
            self._history = self._history[:self._max_history]

        # 持久化
        try:
            self._db_conn.execute("""
                INSERT INTO query_history (id, connection_id, sql, execution_time, row_count, is_error, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (item.id, item.connection_id, item.sql, item.execution_time, item.row_count, item.is_error, item.timestamp))
            self._db_conn.commit()
        except Exception:
            pass

    def get_history(self, connection_id: Optional[str] = None, limit: int = 50) -> List[HistoryItem]:
        """获取查询历史"""
        if connection_id:
            return [h for h in self._history if h.connection_id == connection_id][:limit]
        return self._history[:limit]

    # ========== AI SQL ==========

    def nl_to_sql(self, nl_query: str) -> str:
        """自然语言转 SQL"""
        if not self._active_connection_id:
            return "-- 请先选择一个数据库连接"

        config = self._connections[self._active_connection_id]

        # 获取当前数据库的表
        tables = []
        try:
            tree = self.schema_explorer.build_database_tree(self._active_connection_id)
            for node in tree:
                for child in getattr(node, 'children', []):
                    if hasattr(child, 'metadata') and child.metadata.get('table_name'):
                        table_name = child.metadata['table_name']
                        schema = self.schema_explorer._get_config(self._active_connection_id)
                        schema_name = getattr(schema, 'database', '')
                        ts = TableSchema(schema_name=schema_name, table_name=table_name)
                        # 尝试获取列信息
                        cols = self.schema_explorer._get_columns(self._active_connection_id, table_name)
                        for col in cols:
                            if hasattr(col, 'metadata'):
                                m = col.metadata
                                ts.columns.append(ColumnInfo(
                                    name=m.get('column_name', ''),
                                    data_type=m.get('data_type', 'TEXT'),
                                    nullable=m.get('nullable', True),
                                    is_primary_key=m.get('primary_key', False)
                                ))
                        tables.append(ts)
        except Exception:
            pass

        return self.sql_generator.nl_to_sql(nl_query, tables, config.db_type)

    def explain_sql(self, sql: str) -> str:
        """解释 SQL"""
        if not self._active_connection_id:
            return "请先选择一个数据库连接"

        config = self._connections[self._active_connection_id]
        tables = []  # 可扩展：获取当前表结构

        return self.sql_generator.explain_sql(sql, tables, config.db_type)

    def analyze_results(self, sql: str, columns: List[str], rows: List[Tuple], question: str = "") -> str:
        """分析查询结果"""
        return self.sql_generator.analyze_results(sql, columns, rows, question)

    # ========== 结构浏览 ==========

    def build_tree(self) -> List[DatabaseTreeNode]:
        """构建数据库树"""
        if not self._active_connection_id:
            return []
        return self.schema_explorer.build_database_tree(self._active_connection_id)

    def get_table_schema(self, table_name: str, schema: str = "") -> Optional[TableSchema]:
        """获取表结构"""
        if not self._active_connection_id:
            return None
        return self.schema_explorer.get_table_schema(
            self._active_connection_id, table_name, schema
        )

    def generate_ddl(self, table_name: str, columns: List[ColumnInfo],
                      db_type: DatabaseType = DatabaseType.MYSQL) -> str:
        """生成 DDL"""
        return self.sql_generator.generate_ddl(table_name, columns, db_type)

    # ========== 收藏 ==========

    def add_favorite(self, name: str, sql: str, description: str = "") -> FavoriteQuery:
        """添加收藏"""
        fav = FavoriteQuery(
            id=hashlib.md5(f"{time.time()}{sql}".encode()).hexdigest()[:16],
            name=name,
            sql=sql,
            connection_id=self._active_connection_id or "",
            description=description,
            created_at=time.time()
        )
        self._favorites.insert(0, fav)
        if len(self._favorites) > self._max_favorites:
            self._favorites = self._favorites[:self._max_favorites]

        try:
            self._db_conn.execute("""
                INSERT INTO favorite_queries (id, name, sql, connection_id, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (fav.id, fav.name, fav.sql, fav.connection_id, fav.description, fav.created_at))
            self._db_conn.commit()
        except Exception:
            pass

        return fav

    def remove_favorite(self, fav_id: str) -> bool:
        """删除收藏"""
        self._favorites = [f for f in self._favorites if f.id != fav_id]
        try:
            self._db_conn.execute("DELETE FROM favorite_queries WHERE id = ?", (fav_id,))
            self._db_conn.commit()
        except Exception:
            pass
        return True

    def get_favorites(self) -> List[FavoriteQuery]:
        """获取收藏列表"""
        return self._favorites

    # ========== 工具 ==========

    def format_sql(self, sql: str) -> str:
        """格式化 SQL"""
        if self._active_connection_id:
            config = self._connections[self._active_connection_id]
            return self.query_executor.format_sql(sql, config.db_type)
        return self.query_executor.format_sql(sql)

    def get_available_db_types(self) -> List[Tuple[DatabaseType, bool]]:
        """获取可用的数据库类型列表 (类型, 是否可用)"""
        return [(dt, check_driver_available(dt)) for dt in DatabaseType]

    def close(self):
        """关闭所有连接"""
        self.conn_manager.close_all()
        if hasattr(self, '_db_conn'):
            self._db_conn.close()


# 全局单例
_browser_instance: Optional[DatabaseBrowser] = None
_browser_lock = threading.Lock()


def get_database_browser(db_path: str = "") -> DatabaseBrowser:
    """获取数据库浏览器单例"""
    global _browser_instance
    if _browser_instance is None:
        with _browser_lock:
            if _browser_instance is None:
                _browser_instance = DatabaseBrowser(db_path)
    return _browser_instance
