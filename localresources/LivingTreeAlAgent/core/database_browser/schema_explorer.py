"""
数据库结构浏览器
探索数据库/Schema/表/列/索引/视图/存储过程
"""

import re
import time
from typing import List, Dict, Optional, Any, Tuple

from .models import (
    DatabaseType, ConnectionConfig, TableSchema, ColumnInfo,
    ForeignKeyInfo, IndexInfo, DatabaseTreeNode
)
from .connection_manager import ConnectionManager


class SchemaExplorer:
    """
    数据库结构浏览器
    支持多数据库的元数据查询
    """

    def __init__(self, conn_manager: ConnectionManager):
        self.conn_manager = conn_manager

    # ========== 数据库树 ==========

    def build_database_tree(self, connection_id: str) -> List[DatabaseTreeNode]:
        """构建完整数据库树"""
        config = self._get_config(connection_id)
        if config is None:
            return []

        db_type = config.db_type

        if db_type == DatabaseType.SQLITE:
            return self._build_sqlite_tree(connection_id, config)
        elif db_type == DatabaseType.MYSQL:
            return self._build_mysql_tree(connection_id, config)
        elif db_type == DatabaseType.POSTGRESQL:
            return self._build_postgresql_tree(connection_id, config)
        elif db_type == DatabaseType.REDIS:
            return self._build_redis_tree(connection_id, config)
        elif db_type == DatabaseType.MONGODB:
            return self._build_mongodb_tree(connection_id, config)
        elif db_type == DatabaseType.DUCKDB:
            return self._build_duckdb_tree(connection_id, config)
        else:
            return []

    def get_children(self, connection_id: str, node_id: str) -> List[DatabaseTreeNode]:
        """获取子节点"""
        parts = node_id.split("::")
        if len(parts) < 2:
            return []

        node_type = parts[0]
        parent_path = parts[1]

        if node_type == "database":
            return self._get_schemas(connection_id, parent_path)
        elif node_type == "schema":
            return self._get_tables(connection_id, parent_path)
        elif node_type == "table":
            return self._get_columns(connection_id, parent_path)
        elif node_type == "redis":
            return self._get_redis_keys(connection_id, parent_path)
        elif node_type == "mongodb":
            return self._get_mongodb_collections(connection_id, parent_path)
        return []

    # ========== SQLite ==========

    def _build_sqlite_tree(self, conn_id: str, config: ConnectionConfig) -> List[DatabaseTreeNode]:
        """构建 SQLite 数据库树"""
        nodes = []
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return nodes

        # 获取所有表
        tables = conn.execute("""
            SELECT name, type, sql FROM sqlite_master
            WHERE type IN ('table', 'view')
            AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name
        """).fetchall()

        tables_node = DatabaseTreeNode(
            id="type::tables",
            name="📋 表",
            node_type="folder",
            parent_id="database"
        )

        views_node = DatabaseTreeNode(
            id="type::views",
            name="👁️ 视图",
            node_type="folder",
            parent_id="database"
        )

        for row in tables:
            table_name, table_type, sql = row
            is_view = table_type == "view"
            parent = views_node if is_view else tables_node

            # 获取行数
            try:
                count_row = conn.execute(f"SELECT COUNT(*) FROM \"{table_name}\"").fetchone()
                row_count = count_row[0] if count_row else 0
            except Exception:
                row_count = 0

            node = DatabaseTreeNode(
                id=f"table::{table_name}",
                name=f"{'📄' if is_view else '🗃️'} {table_name} ({row_count})",
                node_type=table_type,
                parent_id=parent.id,
                metadata={"table_name": table_name, "is_view": is_view, "row_count": row_count, "sql": sql or ""}
            )
            parent.children.append(node)

        nodes = [tables_node, views_node]

        # 索引
        indexes_node = DatabaseTreeNode(
            id="type::indexes",
            name="🔍 索引",
            node_type="folder",
            parent_id="database"
        )
        indexes = conn.execute("""
            SELECT name, tbl_name, sql FROM sqlite_master
            WHERE type = 'index' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()
        for idx_name, tbl_name, sql in indexes:
            idx_node = DatabaseTreeNode(
                id=f"index::{idx_name}",
                name=f"⚡ {idx_name} → {tbl_name}",
                node_type="index",
                parent_id=indexes_node.id,
                metadata={"table_name": tbl_name, "sql": sql or ""}
            )
            indexes_node.children.append(idx_node)
        nodes.append(indexes_node)

        return nodes

    def _get_columns(self, conn_id: str, table_name: str) -> List[DatabaseTreeNode]:
        """获取表的列"""
        nodes = []
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return nodes

        pragma_result = conn.execute(f"PRAGMA table_info(\"{table_name}\")").fetchall()
        for col in pragma_result:
            col_id, name, col_type, notnull, default, pk = col
            icon = "🔑" if pk else "📌"
            node = DatabaseTreeNode(
                id=f"column::{table_name}.{name}",
                name=f"{icon} {name}: {col_type or 'ANY'}",
                node_type="column",
                parent_id=f"table::{table_name}",
                metadata={
                    "column_name": name,
                    "data_type": col_type,
                    "nullable": not notnull,
                    "default": default,
                    "primary_key": bool(pk),
                    "ordinal": col_id
                }
            )
            nodes.append(node)
        return nodes

    # ========== MySQL ==========

    def _build_mysql_tree(self, conn_id: str, config: ConnectionConfig) -> List[DatabaseTreeNode]:
        """构建 MySQL 数据库树"""
        nodes = []
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return nodes

        db_name = config.database
        root = DatabaseTreeNode(id=f"database::{db_name}", name=f"🗄️ {db_name}", node_type="database")

        cursor = conn.cursor()

        # 数据库信息
        db_node = DatabaseTreeNode(id=f"database::{db_name}", name=f"🗄️ {db_name}", node_type="database", parent_id="")

        # 表
        tables_node = DatabaseTreeNode(id=f"schema::{db_name}", name="📋 表", node_type="folder", parent_id=db_node.id)
        cursor.execute(f"""
            SELECT TABLE_NAME, TABLE_TYPE, TABLE_ROWS, CREATE_TIME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME
        """, (db_name,))
        for tbl_name, tbl_type, row_count, create_time in cursor.fetchall():
            is_view = tbl_type == "VIEW"
            icon = "🗃️" if not is_view else "👁️"
            node = DatabaseTreeNode(
                id=f"table::{db_name}.{tbl_name}",
                name=f"{icon} {tbl_name} ({row_count or '?'})",
                node_type="VIEW" if is_view else "TABLE",
                parent_id=tables_node.id,
                metadata={"schema": db_name, "table_name": tbl_name, "row_count": row_count}
            )
            tables_node.children.append(node)

        # 视图
        views_node = DatabaseTreeNode(id=f"views::{db_name}", name="👁️ 视图", node_type="folder", parent_id=db_node.id)

        # 存储过程
        procs_node = DatabaseTreeNode(id=f"procs::{db_name}", name="⚙️ 存储过程", node_type="folder", parent_id=db_node.id)
        cursor.execute("""
            SELECT ROUTINE_NAME, ROUTINE_TYPE
            FROM information_schema.ROUTINES
            WHERE ROUTINE_SCHEMA = %s
            ORDER BY ROUTINE_NAME
        """, (db_name,))
        for proc_name, proc_type in cursor.fetchall():
            icon = "⚡" if proc_type == "FUNCTION" else "⚙️"
            node = DatabaseTreeNode(
                id=f"{proc_type.lower()}::{db_name}.{proc_name}",
                name=f"{icon} {proc_name}",
                node_type=proc_type,
                parent_id=procs_node.id,
                metadata={"schema": db_name, "routine_name": proc_name}
            )
            procs_node.children.append(node)

        cursor.close()
        return [db_node, tables_node, views_node, procs_node]

    # ========== PostgreSQL ==========

    def _build_postgresql_tree(self, conn_id: str, config: ConnectionConfig) -> List[DatabaseTreeNode]:
        """构建 PostgreSQL 数据库树"""
        nodes = []
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return nodes

        cursor = conn.cursor()

        # Schema 列表
        cursor.execute("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY schema_name
        """)
        schemas = cursor.fetchall()

        for (schema_name,) in schemas:
            schema_node = DatabaseTreeNode(
                id=f"schema::{schema_name}",
                name=f"📁 {schema_name}",
                node_type="schema",
                parent_id="database"
            )

            # 表
            tables_node = DatabaseTreeNode(
                id=f"folder::tables::{schema_name}",
                name="📋 表",
                node_type="folder",
                parent_id=schema_node.id
            )
            cursor.execute("""
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = %s
                ORDER BY table_name
            """, (schema_name,))
            for tbl_name, tbl_type in cursor.fetchall():
                is_view = tbl_type == "VIEW"
                node = DatabaseTreeNode(
                    id=f"table::{schema_name}.{tbl_name}",
                    name=f"{'👁️' if is_view else '🗃️'} {tbl_name}",
                    node_type="VIEW" if is_view else "TABLE",
                    parent_id=tables_node.id,
                    metadata={"schema": schema_name, "table_name": tbl_name}
                )
                tables_node.children.append(node)

            schema_node.children = [tables_node]
            nodes.append(schema_node)

        cursor.close()
        return nodes

    # ========== Redis ==========

    def _build_redis_tree(self, conn_id: str, config: ConnectionConfig) -> List[DatabaseTreeNode]:
        """构建 Redis 数据库树"""
        nodes = []
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return nodes

        root = DatabaseTreeNode(id="redis::root", name=f"🔴 Redis ({config.host})", node_type="database")

        # 获取数据库数量
        try:
            info = conn.info("keyspace")
            db_nodes = []
            for key, value in info.items():
                if key.startswith("db"):
                    keys_count = value.get("keys", 0) if isinstance(value, dict) else 0
                    db_node = DatabaseTreeNode(
                        id=f"redis::{key}",
                        name=f"📁 {key} ({keys_count} keys)",
                        node_type="folder",
                        parent_id=root.id,
                        metadata={"db": key, "keys_count": keys_count}
                    )
                    db_nodes.append(db_node)
            root.children = db_nodes
        except Exception:
            root.children = [DatabaseTreeNode(id="redis::db0", name="📁 db0", node_type="folder", parent_id=root.id)]

        return [root]

    def _get_redis_keys(self, conn_id: str, db_key: str) -> List[DatabaseTreeNode]:
        """获取 Redis keys（限制100条）"""
        nodes = []
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return nodes

        try:
            db_index = int(db_key.replace("redis::db", ""))
            conn.select(db_index)
            keys = conn.scan(match="*", count=100)
            for key in keys:
                key_type = conn.type(key)
                icon_map = {"string": "📝", "list": "📋", "set": "🔵", "zset": "🟢", "hash": "📦", "none": "❓"}
                node = DatabaseTreeNode(
                    id=f"key::{db_key}.{key}",
                    name=f"{icon_map.get(key_type, '📌')} {key} [{key_type}]",
                    node_type="key",
                    parent_id=f"redis::{db_key}",
                    metadata={"key": key, "key_type": key_type, "db": db_key}
                )
                nodes.append(node)
        except Exception:
            pass
        return nodes

    # ========== MongoDB ==========

    def _build_mongodb_tree(self, conn_id: str, config: ConnectionConfig) -> List[DatabaseTreeNode]:
        """构建 MongoDB 数据库树"""
        nodes = []
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return nodes

        try:
            db_names = conn.list_database_names()
            root = DatabaseTreeNode(id="mongodb::root", name="🍃 MongoDB", node_type="database")
            for db_name in db_names:
                if db_name in ("admin", "local", "config"):
                    continue
                db_node = DatabaseTreeNode(
                    id=f"mongodb::{db_name}",
                    name=f"📁 {db_name}",
                    node_type="folder",
                    parent_id=root.id,
                    metadata={"db_name": db_name}
                )
                root.children.append(db_node)
            return [root]
        except Exception:
            return []

    def _get_mongodb_collections(self, conn_id: str, db_key: str) -> List[DatabaseTreeNode]:
        """获取 MongoDB 集合"""
        nodes = []
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return nodes

        try:
            db_name = db_key.replace("mongodb::", "")
            db = conn[db_name]
            coll_names = db.list_collection_names()
            for coll_name in coll_names:
                count = db[coll_name].estimated_document_count()
                node = DatabaseTreeNode(
                    id=f"coll::{db_key}.{coll_name}",
                    name=f"📋 {coll_name} ({count})",
                    node_type="collection",
                    parent_id=f"mongodb::{db_name}",
                    metadata={"collection": coll_name, "db": db_name, "count": count}
                )
                nodes.append(node)
        except Exception:
            pass
        return nodes

    # ========== DuckDB ==========

    def _build_duckdb_tree(self, conn_id: str, config: ConnectionConfig) -> List[DatabaseTreeNode]:
        """构建 DuckDB 数据库树"""
        return self._build_sqlite_tree(conn_id, config)

    # ========== 表结构信息 ==========

    def get_table_schema(self, connection_id: str, table_name: str, schema: str = "") -> Optional[TableSchema]:
        """获取表结构信息"""
        config = self._get_config(connection_id)
        if not config:
            return None

        db_type = config.db_type
        if db_type == DatabaseType.SQLITE:
            return self._get_sqlite_table_schema(connection_id, table_name)
        elif db_type == DatabaseType.MYSQL:
            return self._get_mysql_table_schema(connection_id, schema or config.database, table_name)
        elif db_type == DatabaseType.POSTGRESQL:
            return self._get_postgresql_table_schema(connection_id, schema or "public", table_name)
        elif db_type == DatabaseType.DUCKDB:
            return self._get_duckdb_table_schema(connection_id, table_name)
        return None

    def _get_sqlite_table_schema(self, conn_id: str, table_name: str) -> Optional[TableSchema]:
        """获取 SQLite 表结构"""
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return None

        schema = TableSchema(table_name=table_name)

        # 列信息
        pragma_cols = conn.execute(f"PRAGMA table_info(\"{table_name}\")").fetchall()
        for col in pragma_cols:
            col_id, name, col_type, notnull, default, pk = col
            schema.columns.append(ColumnInfo(
                ordinal=col_id,
                name=name,
                data_type=col_type or "ANY",
                nullable=not bool(notnull),
                default_value=default,
                is_primary_key=bool(pk)
            ))
            if pk:
                schema.primary_keys.append(name)

        # 外键
        pragma_fks = conn.execute(f"PRAGMA foreign_key_list(\"{table_name}\")").fetchall()
        for fk in pragma_fks:
            _, seq, col, ref_table, ref_col, on_update, on_delete = fk
            schema.foreign_keys.append(ForeignKeyInfo(
                column=col,
                foreign_table=ref_table,
                foreign_column=ref_col,
                on_update=on_update,
                on_delete=on_delete
            ))

        # 索引
        pragma_indexes = conn.execute(f"PRAGMA index_list(\"{table_name}\")").fetchall()
        for idx in pragma_indexes:
            idx_name, unique, origin = idx
            pragma_info = conn.execute(f"PRAGMA index_info(\"{idx_name}\")").fetchall()
            idx_cols = [r[2] for r in pragma_info]
            schema.indexes.append(IndexInfo(
                name=idx_name,
                columns=idx_cols,
                is_unique=bool(unique),
                is_primary=origin == "pk"
            ))

        # 行数
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM \"{table_name}\"").fetchone()
            schema.row_count = row[0] if row else 0
        except Exception:
            schema.row_count = 0

        # DDL
        ddl_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        ).fetchone()
        schema.ddl = ddl_row[0] if ddl_row else ""

        return schema

    def _get_mysql_table_schema(self, conn_id: str, db: str, table: str) -> Optional[TableSchema]:
        """获取 MySQL 表结构"""
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return None

        cursor = conn.cursor()
        schema = TableSchema(schema_name=db, table_name=table)

        # 列信息
        cursor.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT,
                   COLUMN_KEY, EXTRA, COLUMN_COMMENT, CHARACTER_MAXIMUM_LENGTH,
                   NUMERIC_PRECISION, NUMERIC_SCALE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """, (db, table))
        for row in cursor.fetchall():
            (col_name, data_type, col_type, nullable, default,
             col_key, extra, comment, char_len, num_prec, num_scale) = row
            is_pk = col_key == "PRI"
            schema.columns.append(ColumnInfo(
                name=col_name,
                data_type=data_type,
                nullable=nullable == "YES",
                default_value=default,
                is_primary_key=is_pk,
                character_maximum_length=char_len,
                numeric_precision=num_prec,
                numeric_scale=num_scale,
                comment=comment or ""
            ))
            if is_pk:
                schema.primary_keys.append(col_name)

        # 索引
        cursor.execute(f"""
            SELECT INDEX_NAME, COLUMN_NAME, NON_UNIQUE, INDEX_TYPE
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY INDEX_NAME, SEQ_IN_INDEX
        """, (db, table))
        idx_map = {}
        for idx_name, col_name, non_unique, idx_type in cursor.fetchall():
            if idx_name not in idx_map:
                idx_map[idx_name] = IndexInfo(name=idx_name, is_unique=not non_unique, index_type=idx_type or "BTREE")
            idx_map[idx_name].columns.append(col_name)
        schema.indexes = list(idx_map.values())

        # 行数
        cursor.execute(f"SELECT COUNT(*) FROM `{db}`.`{table}`")
        schema.row_count = cursor.fetchone()[0]

        cursor.close()
        return schema

    def _get_postgresql_table_schema(self, conn_id: str, schema: str, table: str) -> Optional[TableSchema]:
        """获取 PostgreSQL 表结构"""
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return None

        cursor = conn.cursor()
        schema_obj = TableSchema(schema_name=schema, table_name=table)

        # 列信息
        cursor.execute("""
            SELECT a.attname, t.typname, format_type(a.atttypid, a.atttypmod),
                   NOT a.attnotnull, adef.adsrc, a.attnum
            FROM pg_attribute a
            JOIN pg_type t ON a.atttypid = t.oid
            LEFT JOIN pg_attrdef adef ON a.attrelid = adef.adrelid AND a.attnum = adef.adnum
            WHERE a.attrelid = %s::regclass AND a.attnum > 0
            ORDER BY a.attnum
        """, (f"{schema}.{table}",))
        for col_name, typname, fmt_type, not_null, default, attnum in cursor.fetchall():
            schema_obj.columns.append(ColumnInfo(
                ordinal=attnum,
                name=col_name,
                data_type=typname,
                nullable=not not_null,
                default_value=default
            ))

        cursor.close()
        return schema_obj

    def _get_duckdb_table_schema(self, conn_id: str, table: str) -> Optional[TableSchema]:
        """获取 DuckDB 表结构"""
        return self._get_sqlite_table_schema(conn_id, table)

    def _get_config(self, connection_id: str) -> Optional[ConnectionConfig]:
        """获取连接配置"""
        conn, _, config = self.conn_manager._connections.get(connection_id, (None, None, None))
        return config



