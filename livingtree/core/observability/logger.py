"""
LivingTree 结构化日志系统
========================

每条日志包含：trace_id、span_id、时间戳、级别、模块、操作、输入摘要、
输出摘要、耗时、Token消耗、错误详情、扩展字段。
"""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from threading import Lock
import sys
import os


class LogLevel(Enum):
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3
    FATAL = 4


@dataclass
class LogEntry:
    trace_id: str = ""
    span_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    level: str = "INFO"
    module: str = ""
    action: str = ""
    input_summary: str = ""
    output_summary: str = ""
    duration_ms: float = 0.0
    tokens_used: int = 0
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class StructuredLogger:
    def __init__(self, module: str = "livingtree", log_dir: str = "",
                 level: str = "INFO", trace_id: str = ""):
        self.module = module
        self.log_level = LogLevel[level.upper()] if level.upper() in LogLevel.__members__ else LogLevel.INFO
        self.trace_id = trace_id or str(uuid.uuid4())[:8]
        self._lock = Lock()

        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            self._log_path = os.path.join(log_dir, f"livingtree_{datetime.now():%Y%m%d}.jsonl")
        else:
            self._log_path = ""

    def _should_log(self, level: LogLevel) -> bool:
        return level.value >= self.log_level.value

    def _create_entry(self, level: str, action: str, **kwargs) -> LogEntry:
        d = {
            "trace_id": self.trace_id,
            "span_id": kwargs.pop("span_id", ""),
            "level": level,
            "module": kwargs.pop("module", self.module),
            "action": action,
        }
        d.update({k: v for k, v in kwargs.items() if k in LogEntry.__dataclass_fields__})
        return LogEntry(**d)

    def _emit(self, entry: LogEntry):
        line = entry.to_json()
        with self._lock:
            # 控制台输出
            print(line, file=sys.stderr)
            # 文件输出
            if self._log_path:
                try:
                    with open(self._log_path, "a", encoding="utf-8") as f:
                        f.write(line + "\n")
                except Exception:
                    pass

    def _log(self, level: LogLevel, action: str, **kwargs):
        if not self._should_log(level):
            return
        entry = self._create_entry(level.name, action, **kwargs)
        self._emit(entry)

    def debug(self, action: str, **kwargs): self._log(LogLevel.DEBUG, action, **kwargs)

    def info(self, action: str, **kwargs): self._log(LogLevel.INFO, action, **kwargs)

    def warn(self, action: str, **kwargs): self._log(LogLevel.WARN, action, **kwargs)

    def error(self, action: str, error: Union[str, Exception] = "", **kwargs):
        err_str = str(error) if isinstance(error, Exception) else error
        self._log(LogLevel.ERROR, action, error=err_str, **kwargs)

    def fatal(self, action: str, error: Union[str, Exception] = "", **kwargs):
        err_str = str(error) if isinstance(error, Exception) else error
        self._log(LogLevel.FATAL, action, error=err_str, **kwargs)


# ── 全局日志器 ─────────────────────────────────────────────────────

_default_logger: Optional[StructuredLogger] = None


def get_logger(module: str = "livingtree") -> StructuredLogger:
    global _default_logger
    if _default_logger is None:
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "logs"
        )
        _default_logger = StructuredLogger(module=module, log_dir=log_dir)
    return _default_logger


__all__ = ["StructuredLogger", "LogEntry", "LogLevel", "get_logger"]
