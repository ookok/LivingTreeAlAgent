"""
SQL 生成器 - AI 自然语言转 SQL
基于本地 LLM 的 SQL 生成与解释
"""

import json
import re
from typing import List, Optional, Dict, Any, Tuple

from .models import DatabaseType, TableSchema, ColumnInfo


class SQLGenerator:
    """
    AI SQL 生成器
    核心能力：
    1. 自然语言 → SQL
    2. SQL 解释 → 中文说明
    3. SQL 优化建议
    4. 查询结果分析
    """

    def __init__(self):
        self._llm_client = None  # 延迟初始化，调用时获取

    def set_llm_client(self, client):
        """设置 LLM 客户端 (system_brain)"""
        self._llm_client = client

    def nl_to_sql(
        self,
        nl_query: str,
        tables: List[TableSchema],
        db_type: DatabaseType = DatabaseType.MYSQL,
        dialect: str = "SQL"
    ) -> str:
        """
        自然语言转 SQL
        Args:
            nl_query: 自然语言查询
            tables: 可用表结构列表
            db_type: 目标数据库类型
            dialect: SQL方言 (MySQL/PostgreSQL/SQLite)
        Returns:
            生成的 SQL 语句
        """
        if not tables:
            return f"-- 无法生成：未提供表结构信息"

        # 构建表结构描述
        schema_desc = self._build_schema_description(tables)

        prompt = f"""你是一个专业的 SQL 开发者。请根据用户的自然语言查询生成 **{dialect}** SQL。

## 可用表结构：
{schema_desc}

## 用户查询：
{nl_query}

## 要求：
1. 只返回 SQL 语句，不要返回其他内容
2. SQL 必须符合 {dialect} 语法
3. 如果查询涉及聚合、排序、分页，使用合适的子查询或窗口函数
4. 如果是统计分析，提供最优化查询
5. 只输出 SQL，不要加注释

生成的 SQL："""

        if self._llm_client:
            try:
                response = self._llm_client.generate(prompt, max_tokens=512)
                sql = response.strip()
                # 清理可能的 markdown 代码块
                sql = re.sub(r"^```sql\s*", "", sql, flags=re.IGNORECASE)
                sql = re.sub(r"^```\s*", "", sql)
                sql = re.sub(r"\s*```$", "", sql)
                return sql.strip()
            except Exception as e:
                return f"-- LLM 调用失败：{e}\n-- 请手动编写 SQL"

        return f"-- LLM 客户端未配置，请先设置 LLM 客户端"

    def explain_sql(
        self,
        sql: str,
        tables: List[TableSchema],
        db_type: DatabaseType = DatabaseType.MYSQL
    ) -> str:
        """
        解释 SQL 语句
        Returns: 中文解释
        """
        schema_desc = self._build_schema_description(tables)

        prompt = f"""你是一个专业的数据库工程师。请解释以下 SQL 语句的功能和工作原理。

## 表结构：
{schema_desc}

## SQL 语句：
```sql
{sql}
```

## 要求：
1. 用简洁的中文解释这条 SQL 的功能
2. 说明查询涉及哪些表和字段
3. 解释查询条件和排序方式（如有）
4. 指出性能注意事项（如有）

解释："""

        if self._llm_client:
            try:
                response = self._llm_client.generate(prompt, max_tokens=512)
                return response.strip()
            except Exception as e:
                return f"LLM 调用失败：{e}"

        return "-- LLM 客户端未配置"

    def optimize_sql(
        self,
        sql: str,
        db_type: DatabaseType = DatabaseType.MYSQL
    ) -> Dict[str, str]:
        """
        SQL 优化建议
        Returns: {{"优化后SQL": "...", "建议": "..."}}
        """
        prompt = f"""你是一个资深的数据库性能优化专家。请分析以下 SQL 并提供优化建议。

## 数据库类型：{db_type.value}

## SQL 语句：
```sql
{sql}
```

## 要求：
1. 提供优化后的 SQL
2. 列出具体的优化建议（索引、查询结构、避免全表扫描等）
3. 评估优化效果

请用 JSON 格式返回：
{{"optimized_sql": "...", "suggestions": ["建议1", "建议2", ...], "estimated_improvement": "..."}}"""

        if self._llm_client:
            try:
                response = self._llm_client.generate(prompt, max_tokens=768)
                # 尝试解析 JSON
                try:
                    result = json.loads(response)
                    return result
                except json.JSONDecodeError:
                    return {
                        "optimized_sql": sql,
                        "suggestions": [response],
                        "estimated_improvement": "未知"
                    }
            except Exception as e:
                return {
                    "optimized_sql": sql,
                    "suggestions": [f"LLM 调用失败：{e}"],
                    "estimated_improvement": "未知"
                }

        return {
            "optimized_sql": sql,
            "suggestions": ["LLM 客户端未配置"],
            "estimated_improvement": "未知"
        }

    def analyze_results(
        self,
        sql: str,
        columns: List[str],
        rows: List[Tuple],
        nl_question: str = ""
    ) -> str:
        """
        分析查询结果，用自然语言总结
        """
        if not rows:
            return "查询结果为空"

        # 取前10行作为样本
        sample_rows = rows[:10]
        row_count = len(rows)

        prompt = f"""你是一个数据分析助手。请分析以下查询结果并用自然语言总结。

## 查询：
{sql}

## 问题：
{nl_question or "这是什么数据？"}

## 结果概况：
- 总行数：{row_count}
- 列名：{columns}

## 数据样本（前 {min(10, row_count)} 行）：
{self._format_sample_data(columns, sample_rows)}

## 要求：
1. 总结数据的核心内容
2. 指出关键发现或规律
3. 用简洁易懂的语言描述"""

        if self._llm_client:
            try:
                response = self._llm_client.generate(prompt, max_tokens=512)
                return response.strip()
            except Exception as e:
                return f"分析失败：{e}"

        return "-- LLM 客户端未配置"

    def generate_insert(
        self,
        table: str,
        data: Dict[str, Any],
        db_type: DatabaseType = DatabaseType.MYSQL
    ) -> str:
        """生成 INSERT 语句"""
        columns = ", ".join(f"`{k}`" if db_type == DatabaseType.MYSQL else f'"{k}"' for k in data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        values = [str(v) for v in data.values()]

        if db_type == DatabaseType.MYSQL:
            return f"INSERT INTO `{table}` ({columns}) VALUES ({placeholders});"
        else:
            values_sql = ", ".join(["'" + v.replace("'", "''") + "'" for v in values])
            return f'INSERT INTO "{table}" ({columns}) VALUES ({values_sql});'

    def generate_update(
        self,
        table: str,
        data: Dict[str, Any],
        where: str,
        db_type: DatabaseType = DatabaseType.MYSQL
    ) -> str:
        """生成 UPDATE 语句"""
        set_clause = ", ".join(
            f"`{k}` = %s" if db_type == DatabaseType.MYSQL else f'"{k}" = %s'
            for k in data.keys()
        )
        if db_type == DatabaseType.MYSQL:
            return f"UPDATE `{table}` SET {set_clause} WHERE {where};"
        else:
            return f'UPDATE "{table}" SET {set_clause} WHERE {where};'

    def generate_ddl(
        self,
        table_name: str,
        columns: List[ColumnInfo],
        db_type: DatabaseType = DatabaseType.MYSQL,
        pk_columns: Optional[List[str]] = None,
        engine: str = "InnoDB"
    ) -> str:
        """根据列信息生成 DDL"""
        lines = []
        col_defs = []

        for col in columns:
            col_def = f"  `{col.name}` {col.data_type}"
            if col.character_maximum_length:
                col_def += f"({col.character_maximum_length})"
            if not col.nullable:
                col_def += " NOT NULL"
            if col.default_value:
                col_def += f" DEFAULT {col.default_value}"
            col_defs.append(col_def)

        if pk_columns:
            col_defs.append(f"  PRIMARY KEY ({', '.join(f'`{pk}`' for pk in pk_columns)})")

        if db_type == DatabaseType.MYSQL:
            lines.append(f"CREATE TABLE `{table_name}` (")
            lines.append(",\n".join(col_defs))
            lines.append(f") ENGINE={engine} DEFAULT CHARSET=utf8mb4;")
        elif db_type == DatabaseType.POSTGRESQL:
            lines.append(f'CREATE TABLE "{table_name}" (')
            lines.append(",\n".join(col_defs))
            lines.append(");")
        else:
            lines.append(f"CREATE TABLE {table_name} (")
            lines.append(",\n".join(col_defs))
            lines.append(");")

        return "\n".join(lines)

    def _build_schema_description(self, tables: List[TableSchema]) -> str:
        """构建表结构描述"""
        lines = []
        for table in tables:
            line = f"### {table.full_name()}\n"
            line += "| 字段 | 类型 | 可空 | 说明 |\n"
            line += "|------|------|------|------|\n"
            for col in table.columns:
                nullable = "否" if not col.nullable else "是"
                pk = "🔑" if col.is_primary_key else ""
                comment = col.comment or ""
                line += f"| {col.name} {pk} | {col.type_display()} | {nullable} | {comment} |\n"
            lines.append(line)
        return "\n".join(lines)

    def _format_sample_data(self, columns: List[str], rows: List[Tuple]) -> str:
        """格式化样本数据"""
        if not rows:
            return "(无数据)"

        lines = []
        header = "| " + " | ".join(columns) + " |"
        lines.append(header)
        lines.append("|" + "|".join(["---"] * len(columns)) + "|")

        for row in rows:
            row_str = "| " + " | ".join(str(v)[:30] if v is not None else "NULL" for v in row) + " |"
            lines.append(row_str)

        return "\n".join(lines)
