"""AnalyticsStore — DuckDB-powered embedded analytical queries.

Zero-config analytical database for EIA monitoring data. DuckDB is embedded
(single file, no server), columnar, and can query CSV/Parquet directly.

Replaces the need for pandas/numpy on large tables (100K+ rows).
Purely additive — does not replace any existing component.

Usage:
    store = AnalyticsStore()
    store.ingest_csv("monitoring_2025.csv", "air_quality")
    result = store.query("SELECT station, AVG(pm25) FROM air_quality GROUP BY 1")
    result = store.export_parquet("air_quality", "clean.parquet")
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

ANALYTICS_DIR = Path(".livingtree/analytics")
ANALYTICS_DB = ANALYTICS_DIR / "analytics.db"


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    row_count: int
    elapsed_ms: float
    sql: str

    def to_dicts(self) -> list[dict]:
        return [dict(zip(self.columns, row)) for row in self.rows]

    def to_json(self) -> str:
        return json.dumps(self.to_dicts(), ensure_ascii=False, default=str)


class AnalyticsStore:
    """DuckDB embedded analytics engine.

    Zero dependencies beyond duckdb. Creates a single-file database
    at .livingtree/analytics/analytics.db. Supports direct CSV/Parquet
    querying without import.
    """

    def __init__(self, db_path: str = ""):
        self._db_path = db_path or str(ANALYTICS_DB)
        ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
        self._conn = None

    def _ensure_connection(self) -> bool:
        if self._conn is not None:
            return True
        try:
            import duckdb
            self._conn = duckdb.connect(str(self._db_path))
            self._conn.execute("INSTALL json; LOAD json;")
            self._conn.execute("INSTALL parquet; LOAD parquet;")
            self._conn.execute("INSTALL httpfs; LOAD httpfs;")
            return True
        except ImportError:
            logger.debug("DuckDB not installed — analytics unavailable")
            return False

    def query(self, sql: str, params: list | None = None) -> QueryResult | None:
        if not self._ensure_connection():
            return None
        start = time.time()
        if params:
            result = self._conn.execute(sql, params)
        else:
            result = self._conn.execute(sql)
        columns = [d[0] for d in result.description]
        rows = result.fetchall()
        elapsed = (time.time() - start) * 1000
        return QueryResult(
            columns=columns, rows=rows, row_count=len(rows),
            elapsed_ms=round(elapsed, 1), sql=sql,
        )

    def ingest_csv(self, path: str, table_name: str,
                    replace: bool = False) -> int:
        """Ingest a CSV file into a DuckDB table.

        Direct columnar load — no pandas, no row-by-row insert.
        """
        self._ensure_connection()
        action = "CREATE OR REPLACE TABLE" if replace else "CREATE TABLE IF NOT EXISTS"
        self._conn.execute(
            f"{action} {table_name} AS SELECT * FROM read_csv_auto('{path}')")
        count = self._conn.execute(
            f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        logger.info(f"DuckDB ingested {path} → {table_name} ({count} rows)")
        return count

    def query_file(self, path: str, sql: str) -> QueryResult:
        """Query a CSV/Parquet file directly without importing."""
        self._ensure_connection()
        ext = Path(path).suffix.lower()
        func = "read_csv_auto" if ext == ".csv" else "read_parquet"
        full_sql = sql.replace("FROM", f"FROM {func}('{path}') AS", 1)
        return self.query(full_sql)

    def export_parquet(self, table_name: str, output_path: str):
        self._ensure_connection()
        self._conn.execute(
            f"COPY {table_name} TO '{output_path}' (FORMAT PARQUET)")

    def create_table(self, table_name: str, columns: str):
        self._ensure_connection()
        self._conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({columns})")

    def insert_json(self, table_name: str, data: list[dict]):
        self._ensure_connection()
        import tempfile, os
        tmp = Path(tempfile.mktemp(suffix=".json"))
        tmp.write_text(json.dumps(data, ensure_ascii=False))
        self._conn.execute(
            f"INSERT INTO {table_name} SELECT * FROM read_json_auto('{tmp}')")
        tmp.unlink(missing_ok=True)

    def list_tables(self) -> list[str]:
        self._ensure_connection()
        result = self._conn.execute("SHOW TABLES").fetchall()
        return [r[0] for r in result]

    def table_info(self, table_name: str) -> dict:
        self._ensure_connection()
        count = self._conn.execute(
            f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        cols = self._conn.execute(
            f"DESCRIBE {table_name}").fetchall()
        return {
            "table": table_name, "row_count": count,
            "columns": [{"name": c[0], "type": c[1]} for c in cols],
        }

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


_analytics_store: AnalyticsStore | None = None


def get_analytics_store() -> AnalyticsStore:
    global _analytics_store
    if _analytics_store is None:
        _analytics_store = AnalyticsStore()
    return _analytics_store
