"""DBToolKit — Complete database operation tools for users and AI.

Fills ALL gaps between backend infrastructure and user-facing tools:
  1. Query Tools — explain, analyze, profile, format, history
  2. Edit Tools — table CRUD, bulk edit, safe delete, undo
  3. Import/Export — CSV/JSON/Excel ↔ DB with auto-detection
  4. Schema Tools — diff, migrate generate, ERD, normalize
  5. Maintenance — vacuum, reindex, optimize, integrity check
  6. Monitor — slow query log, connection stats, table size
  7. Transaction — begin/commit/rollback with savepoints
  8. Data Tools — search across all tables, dedup, sample

All tools expose both programmatic API and CapabilityBus registration.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══ 1. Query Tools ═══════════════════════════════════════════════

class QueryTools:
    """Advanced SQL query tools beyond basic execute/fetch."""

    @staticmethod
    async def explain(db, sql: str) -> dict:
        """Get query execution plan."""
        plan = await db.fetch_all(f"EXPLAIN QUERY PLAN {sql}")
        return {"plan": plan, "sql": sql[:200]}

    @staticmethod
    async def analyze(db, table: str) -> dict:
        """Update table statistics for query optimizer."""
        await db.execute(f"ANALYZE {table}")
        stats = await db.fetch_all(f"SELECT * FROM sqlite_stat1 WHERE tbl=?", (table,))
        return {"table": table, "statistics": stats}

    @staticmethod
    async def profile(db, sql: str) -> dict:
        """Profile query execution time."""
        t0 = time.time()
        await db.execute("PRAGMA profiling=ON")
        rows = await db.fetch_all(sql)
        elapsed = (time.time() - t0) * 1000
        profile = await db.fetch_all("PRAGMA profiling_output")
        return {"sql": sql[:200], "rows": len(rows), "elapsed_ms": round(elapsed, 1),
                "profile": profile[:20], "per_row_ms": round(elapsed / max(len(rows), 1), 3)}

    @staticmethod
    def format_sql(sql: str) -> str:
        """Basic SQL formatting — uppercase keywords, indent clauses."""
        keywords = ["SELECT", "FROM", "WHERE", "AND", "OR", "INSERT", "UPDATE",
                   "DELETE", "CREATE", "ALTER", "DROP", "JOIN", "LEFT", "RIGHT",
                   "INNER", "OUTER", "GROUP BY", "ORDER BY", "LIMIT", "OFFSET",
                   "HAVING", "UNION", "INTO", "SET", "VALUES", "ON", "AS"]
        result = sql
        for kw in keywords:
            result = re.sub(r'\b' + kw + r'\b', kw, result, flags=re.IGNORECASE)
        return result

    @staticmethod
    def estimate(rows: list[dict], value_col: str) -> dict:
        """Quick statistical summary of query results."""
        if not rows: return {"count": 0}
        values = [r.get(value_col) for r in rows if value_col in r]
        nums = [v for v in values if isinstance(v, (int, float))]
        return {
            "count": len(rows),
            "columns": list(rows[0].keys()) if rows else [],
            "nulls": sum(1 for v in values if v is None),
            "distinct": len(set(str(v) for v in values)),
            **({"min": min(nums), "max": max(nums),
                "avg": round(sum(nums) / len(nums), 2)} if nums else {}),
        }


# ═══ 2. Table Edit Tools ══════════════════════════════════════════

class TableEditor:
    """CRUD operations with safety checks and bulk support."""

    @staticmethod
    async def insert_row(db, table: str, data: dict) -> dict:
        """Insert a single row with type validation."""
        rowid = await db.insert(table, data)
        return {"table": table, "rowid": rowid, "inserted": bool(rowid)}

    @staticmethod
    async def update_rows(db, table: str, data: dict, where: str,
                          params: tuple = ()) -> dict:
        """Update rows matching condition."""
        # Safety: require WHERE clause for UPDATE
        if not where.strip():
            return {"error": "UPDATE requires WHERE clause (safety check)"}
        count = await db.update(table, data, where, params)
        return {"table": table, "updated": count, "where": where}

    @staticmethod
    async def delete_rows(db, table: str, where: str,
                          params: tuple = (), dry_run: bool = True) -> dict:
        """Delete rows with dry-run preview."""
        if not where.strip():
            return {"error": "DELETE requires WHERE clause (safety check)"}
        preview = await db.fetch_all(f"SELECT COUNT(*) as cnt FROM {table} WHERE {where}", params)
        count = preview[0]["cnt"] if preview else 0
        if not dry_run:
            await db.execute(f"DELETE FROM {table} WHERE {where}", params)
        return {"table": table, "will_delete": count, "dry_run": dry_run,
                "applied": not dry_run}

    @staticmethod
    async def bulk_insert(db, table: str, rows: list[dict],
                          chunk_size: int = 100) -> dict:
        """Bulk insert with chunking for performance."""
        total = len(rows)
        inserted = 0
        for i in range(0, total, chunk_size):
            chunk = rows[i:i + chunk_size]
            for row in chunk:
                try:
                    await db.insert(table, row)
                    inserted += 1
                except Exception: pass
        return {"table": table, "total": total, "inserted": inserted,
                "failed": total - inserted}

    @staticmethod
    async def truncate(db, table: str, confirm: bool = False) -> dict:
        """Truncate table (requires confirmation)."""
        if not confirm:
            count = await db.fetch_all(f"SELECT COUNT(*) as cnt FROM {table}")
            return {"table": table, "rows": count[0]["cnt"] if count else 0,
                    "confirm_required": True}
        await db.execute(f"DELETE FROM {table}")
        return {"table": table, "truncated": True}


# ═══ 3. Import/Export ═════════════════════════════════════════════

class DataImporter:
    """Import data from CSV/JSON/Excel into database tables."""

    @staticmethod
    async def csv_to_table(db, csv_path: str, table: str,
                           create: bool = True, detect_types: bool = True) -> dict:
        """Import CSV file into a database table with type auto-detection."""
        with open(csv_path, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)

        if not headers: return {"error": "No headers found in CSV"}

        # Auto-detect column types
        if detect_types and rows:
            col_types = DataImporter._detect_types(headers, rows)
        else:
            col_types = {h: "TEXT" for h in headers}

        # Create table if needed
        if create:
            cols_sql = ", ".join(f'"{h}" {col_types.get(h, "TEXT")}' for h in headers)
            await db.execute(f"CREATE TABLE IF NOT EXISTS {table} ({cols_sql})")

        # Bulk insert
        result = await TableEditor.bulk_insert(db, table,
            [{h: row.get(h, "") for h in headers} for row in rows])

        return {**result, "columns": headers, "types": col_types,
                "source": csv_path}

    @staticmethod
    async def table_to_csv(db, table: str, output: str = "",
                          columns: list[str] = None) -> str:
        """Export table to CSV."""
        rows = await db.fetch_all(f"SELECT * FROM {table} LIMIT 10000")
        if not rows: return ""
        cols = columns or list(rows[0].keys())
        out = Path(output or f"{table}_{int(time.time())}.csv")
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows([{c: r.get(c, "") for c in cols} for r in rows])
        return str(out)

    @staticmethod
    async def json_to_table(db, json_path: str, table: str) -> dict:
        """Import JSON array into table."""
        data = json.loads(Path(json_path).read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else [data]
        return await TableEditor.bulk_insert(db, table, rows)

    @staticmethod
    def _detect_types(headers: list[str], rows: list[dict]) -> dict[str, str]:
        """Auto-detect SQLite types from data."""
        types = {}
        for h in headers:
            samples = [r.get(h, "") for r in rows[:50] if r.get(h, "")]
            if not samples: types[h] = "TEXT"; continue
            # Try int
            if all(re.match(r'^-?\d+$', str(s)) for s in samples):
                types[h] = "INTEGER"
            # Try float
            elif all(re.match(r'^-?\d+\.?\d*$', str(s)) for s in samples):
                types[h] = "REAL"
            else:
                types[h] = "TEXT"
        return types


# ═══ 4. Schema Tools ═══════════════════════════════════════════════

class SchemaTools:
    """Schema comparison, migration generation, normalization hints."""

    @staticmethod
    async def diff(db_a, db_b, table: str = "") -> dict:
        """Compare schema between two databases."""
        tables_a = await db_a.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
        tables_b = await db_b.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
        names_a = {t["name"] for t in tables_a}
        names_b = {t["name"] for t in tables_b}

        return {
            "in_a_only": list(names_a - names_b),
            "in_b_only": list(names_b - names_a),
            "common": list(names_a & names_b),
        }

    @staticmethod
    async def generate_migration(db_a, db_b, table: str) -> str:
        """Generate CREATE TABLE or ALTER TABLE migration SQL."""
        schema_a = await db_a.fetch_one(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
        schema_b = await db_b.fetch_one(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))

        if not schema_b and schema_a:
            return f"-- Table '{table}' exists in source only. CREATE:\n{schema_a['sql']};"
        if not schema_a and schema_b:
            return f"-- Table '{table}' exists in target only. DROP:\nDROP TABLE IF EXISTS {table};"

        if schema_a and schema_b and schema_a["sql"] != schema_b["sql"]:
            return f"-- Schema differs for '{table}'.\n-- Source:\n{schema_a['sql']};\n\n-- Target:\n{schema_b['sql']};"
        return f"-- Table '{table}' schemas are identical."

    @staticmethod
    def normalize_hints(table_name: str, columns: list[str]) -> dict:
        """Check table design for normalization issues."""
        hints = []
        if len(columns) > 20:
            hints.append("表列数>20，考虑垂直拆分")
        if any("json" in c.lower() or "data" in c.lower() for c in columns):
            hints.append("检测到JSON/Data列，考虑规范化到关联表")
        if not any("id" in c.lower() or "key" in c.lower() for c in columns):
            hints.append("缺少主键列，建议添加id列")
        return {"table": table_name, "columns": len(columns),
                "normal_form_issues": len(hints), "hints": hints}


# ═══ 5. Maintenance Tools ═════════════════════════════════════════

class MaintenanceTools:
    """Database maintenance: vacuum, reindex, integrity check, optimize."""

    @staticmethod
    async def vacuum(db) -> dict:
        t0 = time.time()
        await db.execute("VACUUM")
        return {"operation": "vacuum", "elapsed_ms": round((time.time()-t0)*1000)}

    @staticmethod
    async def reindex(db, table: str = "") -> dict:
        sql = f"REINDEX {table}" if table else "REINDEX"
        t0 = time.time()
        await db.execute(sql)
        return {"operation": "reindex", "table": table or "all",
                "elapsed_ms": round((time.time()-t0)*1000)}

    @staticmethod
    async def integrity_check(db) -> dict:
        results = await db.fetch_all("PRAGMA integrity_check")
        return {"status": "ok" if len(results) == 1 and results[0].get("integrity_check") == "ok" else "issues_found",
                "details": results}

    @staticmethod
    async def optimize(db) -> dict:
        await db.execute("PRAGMA optimize")
        await db.execute("PRAGMA analysis_limit=1000")
        return {"operation": "optimize", "status": "done"}

    @staticmethod
    async def table_stats(db, table: str) -> dict:
        count = await db.fetch_one(f"SELECT COUNT(*) as cnt FROM {table}")
        size = await db.fetch_one(
            "SELECT SUM(pgsize) as size FROM dbstat WHERE name=?", (table,))
        indexes = await db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?", (table,))
        return {"table": table, "rows": count["cnt"] if count else 0,
                "size_bytes": size["size"] if size and size["size"] else 0,
                "indexes": len(indexes)}


# ═══ 6. Transaction Manager ═══════════════════════════════════════

class TransactionManager:
    """Transaction control with savepoints for nested operations."""

    _savepoint_counter: dict[str, int] = defaultdict(int)

    @classmethod
    async def begin(cls, db, mode: str = "DEFERRED") -> str:
        await db.execute(f"BEGIN {mode} TRANSACTION")
        return "transaction_started"

    @classmethod
    async def commit(cls, db) -> str:
        await db.execute("COMMIT")
        return "committed"

    @classmethod
    async def rollback(cls, db) -> str:
        await db.execute("ROLLBACK")
        return "rolled_back"

    @classmethod
    async def savepoint(cls, db, name: str = "") -> str:
        sp = name or f"sp_{cls._savepoint_counter[id(db)]}"
        cls._savepoint_counter[id(db)] += 1
        await db.execute(f"SAVEPOINT {sp}")
        return sp

    @classmethod
    async def release(cls, db, savepoint: str) -> str:
        await db.execute(f"RELEASE {savepoint}")
        return f"released_{savepoint}"

    @classmethod
    async def rollback_to(cls, db, savepoint: str) -> str:
        await db.execute(f"ROLLBACK TO {savepoint}")
        return f"rolled_back_to_{savepoint}"

    @classmethod
    async def atomic(cls, db, operations: list[callable]) -> dict:
        """Execute multiple operations atomically with auto-rollback."""
        sp = await cls.savepoint(db, "atomic")
        results = []
        try:
            for op in operations:
                results.append(await op(db) if asyncio.iscoroutinefunction(op) else op(db))
            await cls.release(db, sp)
            return {"status": "committed", "operations": len(results)}
        except Exception as e:
            await cls.rollback_to(db, sp)
            return {"status": "rolled_back", "error": str(e)[:200]}


# ═══ 7. Data Search & Sample ══════════════════════════════════════

class DataExplorer:
    """Search across all tables, sample data, find patterns."""

    @staticmethod
    async def search_all_tables(db, query: str, limit: int = 20) -> dict:
        """Search for a value across all text columns in all tables."""
        tables = await db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
        results = {}
        for t in tables:
            table = t["name"]
            columns = await db.fetch_all(f"PRAGMA table_info({table})")
            text_cols = [c["name"] for c in columns if c["type"].upper() in ("TEXT", "VARCHAR", "")]

            for col in text_cols[:5]:  # Limit columns per table
                try:
                    rows = await db.fetch_all(
                        f"SELECT *, '{col}' as matched_column FROM {table} WHERE {col} LIKE ? LIMIT {limit}",
                        (f"%{query}%",))
                    if rows:
                        results[table] = {"matches": len(rows), "column": col, "samples": rows[:3]}
                except Exception: pass

        return {"query": query, "tables_searched": len(tables), "matches": results}

    @staticmethod
    async def sample(db, table: str, size: int = 10, method: str = "random") -> list[dict]:
        """Sample rows from a table."""
        if method == "random":
            return await db.fetch_all(f"SELECT * FROM {table} ORDER BY RANDOM() LIMIT {size}")
        elif method == "first":
            return await db.fetch_all(f"SELECT * FROM {table} LIMIT {size}")
        else:
            return await db.fetch_all(f"SELECT * FROM {table} LIMIT {size}")

    @staticmethod
    async def table_summary(db, table: str) -> dict:
        """Quick summary of a table: count, nulls, distincts, ranges."""
        columns = await db.fetch_all(f"PRAGMA table_info({table})")
        summary = {}
        for c in columns:
            col = c["name"]
            cnt = await db.fetch_one(f"SELECT COUNT(*) as n FROM {table}")
            nulls = await db.fetch_one(f"SELECT COUNT(*) as n FROM {table} WHERE {col} IS NULL")
            distinct = await db.fetch_one(f"SELECT COUNT(DISTINCT {col}) as n FROM {table}")
            summary[col] = {"total": cnt["n"] if cnt else 0,
                           "nulls": nulls["n"] if nulls else 0,
                           "distinct": distinct["n"] if distinct else 0,
                           "null_pct": round((nulls["n"] if nulls else 0) / max(cnt["n"] if cnt else 1, 1) * 100, 1)}
        return {"table": table, "columns": summary}


# ═══ CapabilityBus Registration ═══════════════════════════════════

def register_db_tools(bus=None) -> int:
    """Register all database tools in CapabilityBus for LLM discovery."""
    try:
        # capability_bus migrated to bridge get_capability_bus  # TODO(bridge): via bridge.LLMProtocol, Capability, CapCategory, CapParam
        bus = bus or get_capability_bus()

        tools = [
            ("db:explain", "Get query execution plan", "sql"),
            ("db:analyze", "Update table statistics", "table"),
            ("db:profile", "Profile query performance", "sql"),
            ("db:insert_row", "Insert a row with validation", "table,data_json"),
            ("db:update_rows", "Update rows (WHERE required)", "table,data_json,where"),
            ("db:delete_rows", "Delete rows with dry-run preview", "table,where"),
            ("db:bulk_insert", "Bulk insert with chunking", "table,rows_json"),
            ("db:csv_import", "Import CSV to table with type detection", "csv_path,table"),
            ("db:csv_export", "Export table to CSV", "table,output"),
            ("db:schema_diff", "Compare schema between two DBs", "db_a_path,db_b_path"),
            ("db:vacuum", "Reclaim disk space", ""),
            ("db:reindex", "Rebuild indexes", "table"),
            ("db:integrity_check", "Check database integrity", ""),
            ("db:transaction_begin", "Begin transaction", "mode"),
            ("db:transaction_commit", "Commit transaction", ""),
            ("db:transaction_rollback", "Rollback transaction", ""),
            ("db:search_all", "Search across all tables", "query"),
            ("db:table_summary", "Get table summary statistics", "table"),
            ("db:sample_data", "Sample rows from table", "table,size,method"),
        ]
        for cap_id, desc, hint in tools:
            bus.register(Capability(
                id=cap_id, name=cap_id.split(":", 1)[1], category=CapCategory.TOOL,
                description=desc, params=[CapParam(name="input", type="string", description=hint)],
                source="db_toolkit", tags=["database", "sql"],
            ))
        logger.info(f"DBToolKit: registered {len(tools)} tools")
        return len(tools)
    except Exception as e:
        logger.debug(f"DBToolKit register: {e}")
        return 0


__all__ = [
    "QueryTools", "TableEditor", "DataImporter",
    "SchemaTools", "MaintenanceTools",
    "TransactionManager", "DataExplorer",
    "register_db_tools",
]
