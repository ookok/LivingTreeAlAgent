"""
SQL 查询执行器
支持多数据库查询、结果格式化、分页、执行计划
"""

import re
import time
from typing import List, Optional, Dict, Any, Tuple

from .models import DatabaseType, ConnectionConfig, QueryResult, QueryResultType
from .connection_manager import ConnectionManager


class QueryExecutor:
    """
    SQL 查询执行器
    支持跨数据库的查询执行、格式化、执行计划
    """

    def __init__(self, conn_manager: ConnectionManager):
        self.conn_manager = conn_manager

    def execute(self, connection_id: str, sql: str, page: int = 1, page_size: int = 100) -> QueryResult:
        """
        执行 SQL 查询
        Returns: QueryResult
        """
        config = self._get_config(connection_id)
        if not config:
            return QueryResult(
                result_type=QueryResultType.ERROR,
                error_message="连接不存在"
            )

        start_time = time.time()

        try:
            db_type = config.db_type

            if db_type == DatabaseType.SQLITE:
                return self._execute_sqlite(connection_id, sql, page, page_size, start_time)
            elif db_type == DatabaseType.MYSQL:
                return self._execute_mysql(connection_id, sql, page, page_size, start_time)
            elif db_type == DatabaseType.POSTGRESQL:
                return self._execute_postgresql(connection_id, sql, page, page_size, start_time)
            elif db_type == DatabaseType.REDIS:
                return self._execute_redis(connection_id, sql, start_time)
            elif db_type == DatabaseType.MONGODB:
                return self._execute_mongodb(connection_id, sql, start_time)
            elif db_type == DatabaseType.DUCKDB:
                return self._execute_duckdb(connection_id, sql, page, page_size, start_time)
            else:
                return QueryResult(
                    result_type=QueryResultType.ERROR,
                    error_message=f"不支持的数据库类型: {db_type.value}"
                )
        except Exception as e:
            return QueryResult(
                result_type=QueryResultType.ERROR,
                error_message=str(e),
                execution_time=time.time() - start_time
            )

    def execute_batch(self, connection_id: str, sql: str) -> QueryResult:
        """批量执行 SQL（用于 DDL）"""
        config = self._get_config(connection_id)
        if not config:
            return QueryResult(result_type=QueryResultType.ERROR, error_message="连接不存在")

        start_time = time.time()
        conn = self.conn_manager.get_connection(connection_id)
        if not conn:
            return QueryResult(result_type=QueryResultType.ERROR, error_message="连接不可用")

        try:
            # 分割多条 SQL
            statements = self._split_sql_statements(sql)
            total_affected = 0
            results = []

            for stmt in statements:
                stmt = stmt.strip()
                if not stmt:
                    continue

                if config.db_type == DatabaseType.MYSQL:
                    cursor = conn.cursor()
                    cursor.execute(stmt)
                    total_affected += cursor.rowcount
                    cursor.close()
                elif config.db_type == DatabaseType.POSTGRESQL:
                    cursor = conn.cursor()
                    cursor.execute(stmt)
                    total_affected += cursor.rowcount
                    cursor.close()
                else:
                    cursor = conn.cursor()
                    cursor.execute(stmt)
                    total_affected += cursor.rowcount if hasattr(cursor, 'rowcount') else 0
                    cursor.close()

            execution_time = time.time() - start_time
            return QueryResult(
                result_type=QueryResultType.MESSAGE,
                ddl=f"执行成功，影响 {total_affected} 行",
                affected_rows=total_affected,
                execution_time=execution_time
            )
        except Exception as e:
            return QueryResult(
                result_type=QueryResultType.ERROR,
                error_message=str(e),
                execution_time=time.time() - start_time
            )

    def get_explain(self, connection_id: str, sql: str) -> QueryResult:
        """获取执行计划"""
        config = self._get_config(connection_id)
        if not config:
            return QueryResult(result_type=QueryResultType.ERROR, error_message="连接不存在")

        conn = self.conn_manager.get_connection(connection_id)
        if not conn:
            return QueryResult(result_type=QueryResultType.ERROR, error_message="连接不可用")

        try:
            if config.db_type == DatabaseType.MYSQL:
                explain_sql = f"EXPLAIN FORMAT=JSON {sql}"
                cursor = conn.cursor()
                cursor.execute(explain_sql)
                rows = cursor.fetchall()
                columns = [d[0] for d in cursor.description]
                cursor.close()
                return QueryResult(
                    result_type=QueryResultType.TABLE,
                    columns=columns,
                    rows=rows,
                    row_count=len(rows)
                )
            elif config.db_type == DatabaseType.POSTGRESQL:
                explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}"
                cursor = conn.cursor()
                cursor.execute(explain_sql)
                rows = [(str(cursor.fetchall()),)]
                columns = ["Query Plan"]
                cursor.close()
                return QueryResult(
                    result_type=QueryResultType.TABLE,
                    columns=columns,
                    rows=rows,
                    row_count=1
                )
            elif config.db_type == DatabaseType.SQLITE:
                explain_sql = f"EXPLAIN QUERY PLAN {sql}"
                cursor = conn.execute(explain_sql)
                rows = cursor.fetchall()
                columns = [d[0] for d in cursor.description]
                return QueryResult(
                    result_type=QueryResultType.TABLE,
                    columns=columns,
                    rows=rows,
                    row_count=len(rows)
                )
            else:
                return QueryResult(
                    result_type=QueryResultType.ERROR,
                    error_message=f"暂不支持 {config.db_type.value} 的执行计划"
                )
        except Exception as e:
            return QueryResult(result_type=QueryResultType.ERROR, error_message=str(e))

    def format_sql(self, sql: str, db_type: DatabaseType = DatabaseType.MYSQL) -> str:
        """格式化 SQL"""
        # 简单格式化
        keywords = ["SELECT", "FROM", "WHERE", "AND", "OR", "JOIN", "LEFT JOIN", "RIGHT JOIN",
                    "INNER JOIN", "ON", "GROUP BY", "HAVING", "ORDER BY", "LIMIT", "OFFSET",
                    "INSERT INTO", "VALUES", "UPDATE", "SET", "DELETE FROM", "CREATE TABLE",
                    "ALTER TABLE", "DROP TABLE", "CREATE INDEX", "UNION", "IN", "BETWEEN"]

        result = sql.strip()
        for kw in keywords:
            result = re.sub(rf"\b{kw}\b", f"\n{kw}", result, flags=re.IGNORECASE)

        lines = [l.strip() for l in result.split("\n") if l.strip()]
        return "\n".join(f"    {l}" if lines.index(l) > 0 and not l.startswith(",") else l for l in lines)

    # ========== SQLite 执行 ==========

    def _execute_sqlite(self, conn_id: str, sql: str, page: int, page_size: int, start: float) -> QueryResult:
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return QueryResult(result_type=QueryResultType.ERROR, error_message="连接不可用")

        sql = sql.strip()
        is_select = sql.upper().startswith("SELECT") or sql.upper().startswith("PRAGMA")

        if is_select:
            cursor = conn.execute(sql)
            # 分页
            offset = (page - 1) * page_size
            all_rows = cursor.fetchall()
            total = len(all_rows)
            columns = [d[0] for d in cursor.description]
            page_rows = all_rows[offset:offset + page_size]
            execution_time = time.time() - start
            return QueryResult(
                result_type=QueryResultType.TABLE,
                columns=columns,
                rows=[tuple(r) for r in page_rows],
                row_count=len(page_rows),
                total_rows=total,
                page=page,
                page_size=page_size,
                execution_time=execution_time
            )
        else:
            conn.execute(sql)
            conn.commit()
            execution_time = time.time() - start
            return QueryResult(
                result_type=QueryResultType.MESSAGE,
                affected_rows=conn.total_changes,
                execution_time=execution_time,
                ddl=f"执行成功，影响 {conn.total_changes} 行"
            )

    def _execute_mysql(self, conn_id: str, sql: str, page: int, page_size: int, start: float) -> QueryResult:
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return QueryResult(result_type=QueryResultType.ERROR, error_message="连接不可用")

        cursor = conn.cursor()
        sql_upper = sql.strip().upper()
        is_select = sql_upper.startswith("SELECT") or sql_upper.startswith("SHOW") or sql_upper.startswith("DESCRIBE")

        if is_select:
            cursor.execute(sql)
            all_rows = cursor.fetchall()
            total = len(all_rows)
            columns = [d[0] for d in cursor.description]
            offset = (page - 1) * page_size
            page_rows = all_rows[offset:offset + page_size]
            cursor.close()
            execution_time = time.time() - start
            return QueryResult(
                result_type=QueryResultType.TABLE,
                columns=columns,
                rows=[tuple(r) for r in page_rows],
                row_count=len(page_rows),
                total_rows=total,
                page=page,
                page_size=page_size,
                execution_time=execution_time
            )
        else:
            cursor.execute(sql)
            affected = cursor.rowcount
            conn.commit()
            cursor.close()
            execution_time = time.time() - start
            return QueryResult(
                result_type=QueryResultType.MESSAGE,
                affected_rows=affected,
                execution_time=execution_time,
                ddl=f"执行成功，影响 {affected} 行"
            )

    def _execute_postgresql(self, conn_id: str, sql: str, page: int, page_size: int, start: float) -> QueryResult:
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return QueryResult(result_type=QueryResultType.ERROR, error_message="连接不可用")

        cursor = conn.cursor()
        sql_upper = sql.strip().upper()
        is_select = sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")

        if is_select:
            cursor.execute(sql)
            all_rows = cursor.fetchall()
            total = len(all_rows)
            columns = [d[0] for d in cursor.description]
            offset = (page - 1) * page_size
            page_rows = all_rows[offset:offset + page_size]
            cursor.close()
            execution_time = time.time() - start
            return QueryResult(
                result_type=QueryResultType.TABLE,
                columns=columns,
                rows=[tuple(r) for r in page_rows],
                row_count=len(page_rows),
                total_rows=total,
                page=page,
                page_size=page_size,
                execution_time=execution_time
            )
        else:
            cursor.execute(sql)
            affected = cursor.rowcount
            conn.commit()
            cursor.close()
            execution_time = time.time() - start
            return QueryResult(
                result_type=QueryResultType.MESSAGE,
                affected_rows=affected,
                execution_time=execution_time,
                ddl=f"执行成功，影响 {affected} 行"
            )

    def _execute_redis(self, conn_id: str, sql: str, start: float) -> QueryResult:
        """执行 Redis 命令"""
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return QueryResult(result_type=QueryResultType.ERROR, error_message="连接不可用")

        try:
            # 简单的 Redis 命令执行
            parts = sql.strip().split()
            if not parts:
                return QueryResult(result_type=QueryResultType.ERROR, error_message="空命令")

            cmd = parts[0].upper()
            args = parts[1:]

            result = conn.execute_command(cmd, *args)
            execution_time = time.time() - start

            if isinstance(result, list):
                columns = ["Result"]
                rows = [[r] for r in result]
            else:
                columns = ["Result"]
                rows = [[result]]

            return QueryResult(
                result_type=QueryResultType.TABLE,
                columns=columns,
                rows=[tuple(r) for r in rows],
                row_count=len(rows),
                execution_time=execution_time
            )
        except Exception as e:
            return QueryResult(
                result_type=QueryResultType.ERROR,
                error_message=str(e),
                execution_time=time.time() - start
            )

    def _execute_mongodb(self, conn_id: str, sql: str, start: float) -> QueryResult:
        """执行 MongoDB 命令 (JSON 格式)"""
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return QueryResult(result_type=QueryResultType.ERROR, error_message="连接不可用")

        try:
            import json
            cmd = json.loads(sql)
            result = conn.admin.command(cmd)
            execution_time = time.time() - start

            def flatten(d, parent_key=''):
                items = []
                for k, v in d.items():
                    new_key = f"{parent_key}.{k}" if parent_key else k
                    if isinstance(v, dict):
                        items.extend(flatten(v, new_key))
                    else:
                        items.append((new_key, str(v)[:200]))
                return items

            items = flatten(result)
            if items:
                columns = [k for k, _ in items]
                rows = [[v for _, v in items]]
            else:
                columns = ["Result"]
                rows = [[str(result)[:500]]]

            return QueryResult(
                result_type=QueryResultType.TABLE,
                columns=columns,
                rows=[tuple(r) for r in rows],
                row_count=len(rows),
                execution_time=execution_time
            )
        except Exception as e:
            return QueryResult(
                result_type=QueryResultType.ERROR,
                error_message=str(e),
                execution_time=time.time() - start
            )

    def _execute_duckdb(self, conn_id: str, sql: str, page: int, page_size: int, start: float) -> QueryResult:
        """DuckDB 执行"""
        conn = self.conn_manager.get_connection(conn_id)
        if not conn:
            return QueryResult(result_type=QueryResultType.ERROR, error_message="连接不可用")

        sql_upper = sql.strip().upper()
        is_select = sql_upper.startswith("SELECT") or sql_upper.startswith("WITH") or sql_upper.startswith("SHOW")

        if is_select:
            cursor = conn.cursor()
            cursor.execute(sql)
            all_rows = cursor.fetchall()
            total = len(all_rows)
            columns = [d[0] for d in cursor.description]
            offset = (page - 1) * page_size
            page_rows = all_rows[offset:offset + page_size]
            cursor.close()
            return QueryResult(
                result_type=QueryResultType.TABLE,
                columns=columns,
                rows=[tuple(r) for r in page_rows],
                row_count=len(page_rows),
                total_rows=total,
                page=page,
                page_size=page_size,
                execution_time=time.time() - start
            )
        else:
            cursor = conn.cursor()
            cursor.execute(sql)
            affected = cursor.rowcount if hasattr(cursor, 'rowcount') else 0
            cursor.close()
            return QueryResult(
                result_type=QueryResultType.MESSAGE,
                affected_rows=affected,
                execution_time=time.time() - start,
                ddl=f"执行成功，影响 {affected} 行"
            )

    def _split_sql_statements(self, sql: str) -> List[str]:
        """分割 SQL 语句"""
        # 简单实现，处理分号分割
        statements = []
        current = ""
        in_string = False
        string_char = ""

        for char in sql:
            if char in ("'", '"') and (not in_string or string_char == char):
                if not in_string:
                    string_char = char
                in_string = not in_string
            if char == ";" and not in_string:
                if current.strip():
                    statements.append(current)
                current = ""
            else:
                current += char

        if current.strip():
            statements.append(current)

        return statements

    def _get_config(self, connection_id: str) -> Optional[ConnectionConfig]:
        """获取连接配置"""
        entry = self.conn_manager._connections.get(connection_id)
        if entry:
            return entry[2]
        return None
