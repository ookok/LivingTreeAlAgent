"""
数据库浏览器数据模型
借鉴 onetcli (feigeCode/onetcli) 多数据库管理架构
"""

import sqlite3
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import json
import hashlib
from datetime import datetime


class DatabaseType(Enum):
    """支持的数据库类型"""
    SQLITE = "sqlite"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLSERVER = "sqlserver"
    ORACLE = "oracle"
    CLICKHOUSE = "clickhouse"
    REDIS = "redis"
    MONGODB = "mongodb"
    DUCKDB = "duckdb"


class ConnectionStatus(Enum):
    """连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class QueryResultType(Enum):
    """查询结果类型"""
    TABLE = "table"          # 表格数据
    MESSAGE = "message"       # 成功/失败消息
    ERROR = "error"           # 错误信息
    SCHEMA = "schema"          # DDL结果


@dataclass
class ConnectionConfig:
    """数据库连接配置"""
    id: str = ""                                      # 唯一ID (UUID)
    name: str = ""                                    # 连接名称
    db_type: DatabaseType = DatabaseType.SQLITE      # 数据库类型
    host: str = "localhost"                            # 主机
    port: int = 0                                     # 端口
    database: str = ""                                # 数据库名
    username: str = ""                                # 用户名
    password: str = ""                                # 密码
    charset: str = "utf8mb4"                          # 字符集
    ssl_enabled: bool = False                         # SSL启用
    # SQLite 专用
    file_path: str = ""                               # SQLite 文件路径
    # Redis 专用
    db_index: int = 0                                 # Redis DB索引
    password_rd: Optional[str] = None                 # Redis密码
    # MongoDB 专用
    auth_source: str = "admin"                        # 认证数据库
    # 连接状态 (不存入数据库)
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    error_message: str = ""
    last_connected: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "db_type": self.db_type.value,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "charset": self.charset,
            "ssl_enabled": self.ssl_enabled,
            "file_path": self.file_path,
            "db_index": self.db_index,
            "password_rd": self.password_rd,
            "auth_source": self.auth_source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConnectionConfig":
        cfg = cls()
        cfg.id = data.get("id", "")
        cfg.name = data.get("name", "")
        cfg.db_type = DatabaseType(data.get("db_type", "sqlite"))
        cfg.host = data.get("host", "localhost")
        cfg.port = data.get("port", 0)
        cfg.database = data.get("database", "")
        cfg.username = data.get("username", "")
        cfg.charset = data.get("charset", "utf8mb4")
        cfg.ssl_enabled = data.get("ssl_enabled", False)
        cfg.file_path = data.get("file_path", "")
        cfg.db_index = data.get("db_index", 0)
        cfg.password_rd = data.get("password_rd")
        cfg.auth_source = data.get("auth_source", "admin")
        return cfg

    def get_id(self) -> str:
        """生成唯一ID"""
        if not self.id:
            raw = f"{self.db_type.value}:{self.host}:{self.port}:{self.database}:{self.username}"
            self.id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return self.id

    def get_display_port(self) -> int:
        """获取显示用端口"""
        if self.port:
            return self.port
        defaults = {
            DatabaseType.MYSQL: 3306,
            DatabaseType.POSTGRESQL: 5432,
            DatabaseType.SQLSERVER: 1433,
            DatabaseType.ORACLE: 1521,
            DatabaseType.CLICKHOUSE: 8123,
            DatabaseType.REDIS: 6379,
            DatabaseType.MONGODB: 27017,
            DatabaseType.DUCKDB: 5432,
        }
        return defaults.get(self.db_type, 0)

    def get_connection_string(self) -> str:
        """获取连接字符串（不包含密码）"""
        if self.db_type == DatabaseType.SQLITE:
            return f"sqlite:///{self.file_path}"
        elif self.db_type == DatabaseType.REDIS:
            return f"redis://:{self.password_rd or ''}@{self.host}:{self.port or 6379}/{self.db_index}"
        elif self.db_type == DatabaseType.MONGODB:
            auth = f"{self.username}:{self.password_rd}@" if self.username else ""
            return f"mongodb://{auth}{self.host}:{self.port or 27017}/{self.database}?authSource={self.auth_source}"
        else:
            return f"{self.db_type.value}://{self.username}@{self.host}:{self.port or self.get_display_port()}/{self.database}"


@dataclass
class TableSchema:
    """表结构信息"""
    schema_name: str = ""          # 所属schema (PostgreSQL)
    table_name: str = ""           # 表名
    table_type: str = "TABLE"      # TABLE / VIEW / MATERIALIZED VIEW
    columns: List["ColumnInfo"] = field(default_factory=list)
    primary_keys: List[str] = field(default_factory=list)
    foreign_keys: List["ForeignKeyInfo"] = field(default_factory=list)
    indexes: List["IndexInfo"] = field(default_factory=list)
    row_count: Optional[int] = None
    comment: str = ""
    ddl: str = ""                  # 建表DDL

    def full_name(self) -> str:
        if self.schema_name and self.schema_name != "public":
            return f"{self.schema_name}.{self.table_name}"
        return self.table_name


@dataclass
class ColumnInfo:
    """列信息"""
    ordinal: int = 0              # 序号
    name: str = ""                # 列名
    data_type: str = ""           # 数据类型
    nullable: bool = True         # 是否可空
    default_value: Optional[str] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_table: str = ""
    foreign_column: str = ""
    character_maximum_length: Optional[int] = None
    numeric_precision: Optional[int] = None
    numeric_scale: Optional[int] = None
    comment: str = ""

    def type_display(self) -> str:
        """类型显示"""
        if self.character_maximum_length:
            return f"{self.data_type}({self.character_maximum_length})"
        if self.numeric_precision is not None and self.numeric_scale is not None:
            return f"{self.data_type}({self.numeric_precision},{self.numeric_scale})"
        if self.numeric_precision is not None:
            return f"{self.data_type}({self.numeric_precision})"
        return self.data_type


@dataclass
class ForeignKeyInfo:
    """外键信息"""
    constraint_name: str = ""
    column: str = ""
    foreign_schema: str = ""
    foreign_table: str = ""
    foreign_column: str = ""
    on_update: str = "NO ACTION"
    on_delete: str = "NO ACTION"


@dataclass
class IndexInfo:
    """索引信息"""
    name: str = ""
    columns: List[str] = field(default_factory=list)
    is_unique: bool = False
    is_primary: bool = False
    index_type: str = "BTREE"


@dataclass
class QueryResult:
    """查询结果"""
    result_type: QueryResultType = QueryResultType.TABLE
    columns: List[str] = field(default_factory=list)          # 列名列表
    rows: List[Tuple[Any, ...]] = field(default_factory=list)  # 数据行
    row_count: int = 0
    affected_rows: int = 0                                    # 受影响行数
    execution_time: float = 0.0                              # 执行时间(秒)
    error_message: str = ""
    # 分页支持
    total_rows: Optional[int] = None
    page: int = 1
    page_size: int = 100
    # DDL信息
    ddl: str = ""

    def has_next_page(self) -> bool:
        if self.total_rows is None:
            return len(self.rows) >= self.page_size
        return self.page * self.page_size < self.total_rows

    def to_display_data(self) -> Tuple[List[str], List[List[str]]]:
        """转换为显示格式 [columns, [row1, row2, ...]]"""
        display_rows = []
        for row in self.rows:
            display_rows.append([str(v) if v is not None else "" for v in row])
        return self.columns, display_rows

    def summary(self) -> str:
        """结果摘要"""
        if self.result_type == QueryResultType.ERROR:
            return f"❌ 错误: {self.error_message}"
        elif self.result_type == QueryResultType.MESSAGE:
            return f"✅ {self.ddl or '执行成功'}"
        elif self.result_type == QueryResultType.SCHEMA:
            return f"📋 DDL ({len(self.rows)} 条语句)"
        else:
            return f"📊 {self.row_count} 行 × {len(self.columns)} 列 | {self.execution_time:.3f}s"


@dataclass
class DatabaseTreeNode:
    """数据库树节点"""
    id: str = ""                          # 唯一ID
    name: str = ""                        # 显示名
    node_type: str = ""                  # database/schema/table/column/view/function/procedure
    icon: str = ""                        # 图标
    parent_id: str = ""                  # 父节点ID
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外数据
    children_loaded: bool = False        # 子节点是否已加载
    children: List["DatabaseTreeNode"] = field(default_factory=list)

    def get_tree_id(self, prefix: str = "") -> str:
        return f"{prefix}{self.id}"


@dataclass
class HistoryItem:
    """查询历史项"""
    id: str = ""
    connection_id: str = ""
    sql: str = ""
    execution_time: float = 0.0
    row_count: int = 0
    timestamp: float = 0.0
    is_error: bool = False

    def timestamp_str(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")


@dataclass
class FavoriteQuery:
    """收藏的查询"""
    id: str = ""
    name: str = ""
    sql: str = ""
    connection_id: str = ""
    description: str = ""
    created_at: float = 0.0


# 默认端口配置
DEFAULT_PORTS = {
    DatabaseType.MYSQL: 3306,
    DatabaseType.POSTGRESQL: 5432,
    DatabaseType.SQLSERVER: 1433,
    DatabaseType.ORACLE: 1521,
    DatabaseType.CLICKHOUSE: 8123,
    DatabaseType.REDIS: 6379,
    DatabaseType.MONGODB: 27017,
    DatabaseType.DUCKDB: 5432,
    DatabaseType.SQLITE: 0,
}


# 驱动可用性检测
_DRIVER_AVAILABLE = {}


def check_driver_available(db_type: DatabaseType) -> bool:
    """检测数据库驱动是否可用"""
    if db_type in _DRIVER_AVAILABLE:
        return _DRIVER_AVAILABLE[db_type]

    available = False
    if db_type == DatabaseType.SQLITE:
        available = True  # 内置
    elif db_type == DatabaseType.MYSQL:
        try:
            import pymysql
            available = True
        except ImportError:
            pass
    elif db_type == DatabaseType.POSTGRESQL:
        try:
            import psycopg2
            available = True
        except ImportError:
            pass
    elif db_type == DatabaseType.REDIS:
        try:
            import redis
            available = True
        except ImportError:
            pass
    elif db_type == DatabaseType.MONGODB:
        try:
            import pymongo
            available = True
        except ImportError:
            pass

    _DRIVER_AVAILABLE[db_type] = available
    return available


def get_available_databases() -> List[DatabaseType]:
    """获取当前可用的数据库类型"""
    return [dt for dt in DatabaseType if check_driver_available(dt)]


def mask_password(config: ConnectionConfig) -> ConnectionConfig:
    """脱敏密码"""
    if config.password:
        config.password = "********"
    if config.password_rd:
        config.password_rd = "********"
    return config
