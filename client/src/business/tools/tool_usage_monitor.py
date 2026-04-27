"""
ToolUsageMonitor - 工具使用统计与监控系统

功能：
- 记录每次工具调用的耗时、成功/失败、参数摘要
- 聚合统计（调用次数、成功率、平均耗时、最慢调用）
- 持久化到 SQLite（跨会话保留）
- 可选回调通知（超时告警、失败告警）
"""

import json
import sqlite3
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolCallRecord:
    """单次工具调用记录"""
    tool_name: str
    caller: str = ""                # 调用者（智能体名称）
    success: bool = True
    error: str = ""
    start_time: float = 0.0         # time.time()
    end_time: float = 0.0
    duration_ms: float = 0.0
    args_summary: str = ""          # 参数摘要（截断）

    @property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.start_time)


@dataclass
class ToolAggregatedStats:
    """工具聚合统计"""
    tool_name: str
    total_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0
    last_called: str = ""
    last_error: str = ""
    top_callers: Dict[str, int] = field(default_factory=dict)


class ToolUsageMonitor:
    """
    工具使用统计与监控（单例模式）

    特性：
    - 线程安全
    - SQLite 持久化
    - 超时/失败告警回调
    - 内存 + 磁盘双层存储

    用法：
        monitor = ToolUsageMonitor.get_instance()
        monitor.record_call("web_crawler", caller="HermesAgent", success=True, duration_ms=150)
        stats = monitor.get_stats("web_crawler")
        all_stats = monitor.get_all_stats()
    """

    _instance = None
    _lock = threading.Lock()

    # 默认超时阈值（毫秒）
    DEFAULT_TIMEOUT_MS = 30_000  # 30秒

    def __init__(self, db_path: Optional[str] = None):
        if ToolUsageMonitor._instance is not None:
            raise RuntimeError("请使用 ToolUsageMonitor.get_instance()")

        self._db_path = Path(db_path) if db_path else (
            Path.home() / ".livingtree" / "tool_usage_monitor.db"
        )
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # 内存缓存
        self._call_records: List[ToolCallRecord] = []
        self._max_memory_records = 10_000
        self._stats_cache: Dict[str, ToolAggregatedStats] = {}

        # 告警回调
        self._on_timeout: Optional[Callable[[str, float], None]] = None
        self._on_failure: Optional[Callable[[str, str], None]] = None
        self._timeout_threshold_ms = self.DEFAULT_TIMEOUT_MS

        # 线程锁
        self._write_lock = threading.Lock()

        # 初始化数据库
        self._init_db()

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> "ToolUsageMonitor":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db_path)
        return cls._instance

    # ── 数据库 ───────────────────────────────────────────────────

    def _init_db(self):
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT NOT NULL,
                    caller TEXT DEFAULT '',
                    success INTEGER DEFAULT 1,
                    error TEXT DEFAULT '',
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    duration_ms REAL DEFAULT 0.0,
                    args_summary TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tool_calls_name
                ON tool_calls(tool_name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tool_calls_time
                ON tool_calls(created_at)
            """)
            conn.commit()

    def _write_to_db(self, record: ToolCallRecord):
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    """INSERT INTO tool_calls
                       (tool_name, caller, success, error, start_time,
                        end_time, duration_ms, args_summary)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.tool_name,
                        record.caller,
                        int(record.success),
                        record.error,
                        record.start_time,
                        record.end_time,
                        record.duration_ms,
                        record.args_summary,
                    )
                )
                conn.commit()
        except Exception as e:
            # 数据库写入失败不应影响主流程
            pass

    # ── 记录调用 ─────────────────────────────────────────────────

    def record_call(
        self,
        tool_name: str,
        caller: str = "",
        success: bool = True,
        error: str = "",
        duration_ms: float = 0.0,
        args_summary: str = "",
    ) -> ToolCallRecord:
        """
        记录一次工具调用。

        Args:
            tool_name: 工具名称
            caller: 调用者（智能体名称）
            success: 是否成功
            error: 错误信息
            duration_ms: 调用耗时（毫秒）
            args_summary: 参数摘要

        Returns:
            ToolCallRecord
        """
        now = time.time()
        record = ToolCallRecord(
            tool_name=tool_name,
            caller=caller,
            success=success,
            error=error,
            start_time=now - duration_ms / 1000.0,
            end_time=now,
            duration_ms=duration_ms,
            args_summary=args_summary[:500] if args_summary else "",
        )

        with self._write_lock:
            # 内存缓存
            self._call_records.append(record)
            if len(self._call_records) > self._max_memory_records:
                self._call_records = self._call_records[-self._max_memory_records // 2:]

            # 更新聚合缓存
            self._update_stats_cache(record)

            # 持久化
            self._write_to_db(record)

        # 告警
        if not success and self._on_failure:
            self._on_failure(tool_name, error)
        elif duration_ms > self._timeout_threshold_ms and success:
            self._on_timeout(tool_name, duration_ms) if self._on_timeout else None

        return record

    def record_call_with_timing(
        self,
        tool_name: str,
        caller: str = "",
        func: Optional[Callable] = None,
        args_summary: str = "",
    ) -> tuple:
        """
        带自动计时的调用记录。

        用法：
            result, record = monitor.record_call_with_timing(
                "web_crawler", caller="Hermes", func=crawl, args_summary="url=xxx"
            )

        Args:
            tool_name: 工具名称
            caller: 调用者
            func: 要执行的函数（可选，若提供则自动计时）
            args_summary: 参数摘要

        Returns:
            (result, ToolCallRecord) - result 可能为 None
        """
        start = time.time()
        result = None
        error = ""
        success = True

        if func is not None:
            try:
                result = func()
            except Exception as e:
                success = False
                error = str(e)

        duration_ms = (time.time() - start) * 1000.0
        record = self.record_call(
            tool_name=tool_name,
            caller=caller,
            success=success,
            error=error,
            duration_ms=duration_ms,
            args_summary=args_summary,
        )
        return result, record

    # ── 统计查询 ─────────────────────────────────────────────────

    def _update_stats_cache(self, record: ToolCallRecord):
        name = record.tool_name
        if name not in self._stats_cache:
            self._stats_cache[name] = ToolAggregatedStats(tool_name=name)

        s = self._stats_cache[name]
        s.total_calls += 1
        if record.success:
            s.success_count += 1
        else:
            s.failure_count += 1
            s.last_error = record.error

        s.success_rate = s.success_count / s.total_calls if s.total_calls > 0 else 0.0

        if record.duration_ms > 0:
            # 增量更新平均
            s.avg_duration_ms = (
                (s.avg_duration_ms * (s.total_calls - 1) + record.duration_ms)
                / s.total_calls
            )
            s.min_duration_ms = min(s.min_duration_ms, record.duration_ms)
            s.max_duration_ms = max(s.max_duration_ms, record.duration_ms)

        s.last_called = datetime.fromtimestamp(record.start_time).isoformat()

        if record.caller:
            s.top_callers[record.caller] = s.top_callers.get(record.caller, 0) + 1

    def get_stats(self, tool_name: str) -> Optional[ToolAggregatedStats]:
        """获取单个工具的聚合统计"""
        return self._stats_cache.get(tool_name)

    def get_all_stats(self) -> Dict[str, ToolAggregatedStats]:
        """获取所有工具的聚合统计"""
        return dict(self._stats_cache)

    def get_top_tools(
        self,
        sort_by: str = "total_calls",
        limit: int = 10,
    ) -> List[ToolAggregatedStats]:
        """
        获取排行工具列表。

        Args:
            sort_by: 排序字段 (total_calls / success_rate / avg_duration_ms / failure_count)
            limit: 最大返回数

        Returns:
            排序后的统计列表
        """
        stats = list(self._stats_cache.values())
        reverse = sort_by in ("total_calls", "success_rate", "avg_duration_ms")
        stats.sort(key=lambda s: getattr(s, sort_by, 0), reverse=reverse)
        return stats[:limit]

    def get_recent_calls(
        self,
        tool_name: Optional[str] = None,
        limit: int = 50,
        success_only: bool = False,
    ) -> List[ToolCallRecord]:
        """
        获取最近的调用记录。

        Args:
            tool_name: 可选，按工具名过滤
            limit: 最大返回数
            success_only: 仅返回成功记录
        """
        records = self._call_records
        if tool_name:
            records = [r for r in records if r.tool_name == tool_name]
        if success_only:
            records = [r for r in records if r.success]

        return list(reversed(records[-limit:]))

    def get_historical_stats(
        self,
        tool_name: str,
        days: int = 7,
    ) -> ToolAggregatedStats:
        """
        从数据库读取历史统计。

        Args:
            tool_name: 工具名称
            days: 查询天数

        Returns:
            聚合统计
        """
        stats = ToolAggregatedStats(tool_name=tool_name)
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                cursor = conn.execute(
                    """SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures,
                        AVG(duration_ms) as avg_dur,
                        MIN(duration_ms) as min_dur,
                        MAX(duration_ms) as max_dur,
                        MAX(created_at) as last_time
                       FROM tool_calls
                       WHERE tool_name = ?
                         AND created_at >= datetime('now', ?, 'localtime')""",
                    (tool_name, f"-{days} days"),
                )
                row = cursor.fetchone()
                if row and row[0] > 0:
                    stats.total_calls = row[0]
                    stats.success_count = row[1] or 0
                    stats.failure_count = row[2] or 0
                    stats.success_rate = stats.success_count / stats.total_calls
                    stats.avg_duration_ms = row[3] or 0.0
                    stats.min_duration_ms = row[4] or 0.0
                    stats.max_duration_ms = row[5] or 0.0
                    stats.last_called = row[6] or ""
        except Exception:
            pass
        return stats

    # ── 告警配置 ─────────────────────────────────────────────────

    def on_timeout(self, callback: Callable[[str, float], None], threshold_ms: float = 30_000):
        """设置超时告警回调"""
        self._on_timeout = callback
        self._timeout_threshold_ms = threshold_ms

    def on_failure(self, callback: Callable[[str, str], None]):
        """设置失败告警回调"""
        self._on_failure = callback

    # ── 清理 ─────────────────────────────────────────────────────

    def clear_memory(self):
        """清空内存缓存"""
        with self._write_lock:
            self._call_records.clear()
            self._stats_cache.clear()

    def cleanup_old_records(self, days: int = 30) -> int:
        """清理数据库中的旧记录，返回删除行数"""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                cursor = conn.execute(
                    """DELETE FROM tool_calls
                       WHERE created_at < datetime('now', ?, 'localtime')""",
                    (f"-{days} days",),
                )
                conn.commit()
                return cursor.rowcount
        except Exception:
            return 0

    def to_summary_dict(self) -> Dict[str, Any]:
        """生成汇总字典（供 UI 使用）"""
        all_stats = self.get_all_stats()
        total_calls = sum(s.total_calls for s in all_stats.values())
        total_success = sum(s.success_count for s in all_stats.values())
        return {
            "total_tools": len(all_stats),
            "total_calls": total_calls,
            "total_success": total_success,
            "total_failures": total_calls - total_success,
            "overall_success_rate": total_success / total_calls if total_calls > 0 else 0.0,
            "tools": {
                name: {
                    "calls": s.total_calls,
                    "success_rate": round(s.success_rate, 3),
                    "avg_ms": round(s.avg_duration_ms, 1),
                    "last_called": s.last_called,
                }
                for name, s in sorted(
                    all_stats.items(),
                    key=lambda x: x[1].total_calls,
                    reverse=True,
                )
            },
        }
