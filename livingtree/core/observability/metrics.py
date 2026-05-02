"""
LivingTree 健康监控与指标收集
============================

指标维度：
- 请求量 QPS
- 成功率 / 失败率
- P50/P95/P99 延迟
- Token 消耗速率
- 模型调用失败次数
- 工具执行失败次数
- 自我修复尝试次数及成功率
"""

import time
import json
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from collections import deque


# ── 错误分级与自动恢复 ──────────────────────────────────────────────

class ErrorLevel:
    RETRYABLE = "retryable"
    DEGRADABLE = "degradable"
    FATAL = "fatal"
    IGNORABLE = "ignorable"


@dataclass
class ErrorRecord:
    timestamp: float = field(default_factory=time.time)
    module: str = ""
    error_type: str = ""
    message: str = ""
    level: str = ErrorLevel.IGNORABLE
    auto_recovered: bool = False


@dataclass
class RecoveryAttempt:
    timestamp: float = field(default_factory=time.time)
    error_type: str = ""
    strategy: str = ""
    success: bool = False
    duration_ms: float = 0.0


@dataclass
class APICallMetrics:
    provider: str = ""
    model: str = ""
    duration_ms: float = 0.0
    tokens_input: int = 0
    tokens_output: int = 0
    success: bool = True
    error: str = ""


class MetricsCollector:
    def __init__(self, window_seconds: int = 300):
        self._window = window_seconds
        self._lock = Lock()

        # 请求统计
        self._request_count: int = 0
        self._success_count: int = 0
        self._failure_count: int = 0
        self._durations: deque = deque(maxlen=10000)

        # 模型调用
        self._model_calls: deque = deque(maxlen=5000)
        self._model_failures: int = 0

        # Token 消耗
        self._total_tokens: int = 0
        self._tokens_history: deque = deque(maxlen=1000)

        # 工具执行
        self._tool_calls: int = 0
        self._tool_failures: int = 0

        # 自我修复
        self._repair_attempts: deque = deque(maxlen=500)

        # 错误记录
        self._errors: deque = deque(maxlen=500)

        # 会话
        self._active_sessions: int = 0
        self._total_sessions: int = 0

        # 构建
        self.build_version: str = "1.0.0"
        self.start_time: float = time.time()

    # ── 请求指标 ──

    def record_request(self, success: bool, duration_ms: float):
        with self._lock:
            self._request_count += 1
            if success:
                self._success_count += 1
            else:
                self._failure_count += 1
            self._durations.append((time.time(), duration_ms))

    @property
    def request_rate(self) -> float:
        recent = [d for t, d in self._durations if time.time() - t < 60]
        return len(recent) / 60.0 if recent else 0.0

    @property
    def success_rate(self) -> float:
        total = self._success_count + self._failure_count
        return self._success_count / total if total > 0 else 1.0

    def get_percentiles(self) -> Dict[str, float]:
        recent = [d for _, d in self._durations if time.time() - _ < self._window]
        if not recent:
            recent = [d for _, d in self._durations]
        if not recent:
            return {"p50": 0, "p95": 0, "p99": 0}
        recent.sort()
        def _pct(p):
            idx = int(len(recent) * p / 100)
            return recent[min(idx, len(recent) - 1)]
        return {"p50": _pct(50), "p95": _pct(95), "p99": _pct(99)}

    # ── 模型调用 ──

    def record_model_call(self, metrics: APICallMetrics):
        with self._lock:
            self._model_calls.append((time.time(), metrics))
            if metrics.success:
                self._total_tokens += metrics.tokens_input + metrics.tokens_output
                self._tokens_history.append((time.time(), metrics.tokens_input + metrics.tokens_output))
            else:
                self._model_failures += 1

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @property
    def tokens_per_minute(self) -> float:
        recent = [(t, tok) for t, tok in self._tokens_history if time.time() - t < 60]
        return sum(t for _, t in recent) if recent else 0.0

    # ── 工具执行 ──

    def record_tool_call(self, success: bool):
        with self._lock:
            self._tool_calls += 1
            if not success:
                self._tool_failures += 1

    @property
    def tool_failure_count(self) -> int:
        return self._tool_failures

    # ── 自我修复 ──

    def record_repair(self, attempt: RecoveryAttempt):
        with self._lock:
            self._repair_attempts.append(attempt)

    @property
    def repair_success_rate(self) -> float:
        total = len(self._repair_attempts)
        if total == 0:
            return 1.0
        return sum(1 for a in self._repair_attempts if a.success) / total

    # ── 错误管理 ──

    def record_error(self, error: ErrorRecord):
        with self._lock:
            self._errors.append(error)

    def get_recent_errors(self, limit: int = 50) -> List[ErrorRecord]:
        return list(self._errors)[-limit:]

    # ── 会话 ──

    def record_session_start(self):
        with self._lock:
            self._active_sessions += 1
            self._total_sessions += 1

    def record_session_end(self):
        with self._lock:
            if self._active_sessions > 0:
                self._active_sessions -= 1

    @property
    def active_sessions(self) -> int:
        return self._active_sessions

    # ── 快照 ──

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": time.time() - self.start_time,
                "version": self.build_version,
                "requests": {
                    "total": self._request_count,
                    "success": self._success_count,
                    "failure": self._failure_count,
                },
                "rate": self.request_rate,
                "success_rate": self.success_rate,
                "latency": self.get_percentiles(),
                "tokens": {
                    "total": self._total_tokens,
                    "per_minute": self.tokens_per_minute,
                },
                "tools": {
                    "total": self._tool_calls,
                    "failures": self._tool_failures,
                },
                "models": {
                    "failures": self._model_failures,
                },
                "repairs": {
                    "attempts": len(self._repair_attempts),
                    "success_rate": self.repair_success_rate,
                },
                "sessions": {
                    "active": self._active_sessions,
                    "total": self._total_sessions,
                },
                "errors_count": len(self._errors),
            }

    def to_json_snapshot(self) -> str:
        return json.dumps(self.snapshot(), ensure_ascii=False, indent=2)


class HealthMonitor:
    def __init__(self, collector: Optional[MetricsCollector] = None):
        self.collector = collector or MetricsCollector()

    def is_healthy(self) -> Tuple[bool, str]:
        s = self.collector.snapshot()
        if s["success_rate"] < 0.5:
            return False, "成功率 < 50%"
        if s["models"]["failures"] > 10:
            return False, "模型调用失败过多"
        return True, "OK"

    def collect(self):
        return self.collector.snapshot()


# ── 全局 ────────────────────────────────────────────────────────────

_default_collector: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    global _default_collector
    if _default_collector is None:
        _default_collector = MetricsCollector()
    return _default_collector


__all__ = [
    "MetricsCollector",
    "HealthMonitor",
    "ErrorLevel",
    "ErrorRecord",
    "RecoveryAttempt",
    "APICallMetrics",
    "get_metrics",
]
