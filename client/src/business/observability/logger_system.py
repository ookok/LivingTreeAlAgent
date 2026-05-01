"""
结构化日志系统

支持结构化日志记录，包含：
- 日志级别
- 上下文信息
- 追踪关联
- 日志过滤
"""

import time
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

class LogLevel(Enum):
    """日志级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class LogRecord:
    """日志记录"""
    timestamp: float
    level: LogLevel
    message: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

class LoggerSystem:
    """
    结构化日志系统
    
    支持与追踪系统集成，记录任务链执行过程中的日志。
    """
    
    def __init__(self, service_name: str = "livingtree"):
        self.service_name = service_name
        self.log_records: list = []
        self.min_level = LogLevel.INFO
    
    def set_level(self, level: LogLevel):
        """设置最小日志级别"""
        self.min_level = level
    
    def _log(self, level: LogLevel, message: str, 
            trace_id: Optional[str] = None, span_id: Optional[str] = None,
            **kwargs):
        """
        记录日志
        
        Args:
            level: 日志级别
            message: 日志消息
            trace_id: 追踪ID
            span_id: 跨度ID
            **kwargs: 额外上下文
        """
        if level.value < self.min_level.value:
            return
        
        record = LogRecord(
            timestamp=time.time(),
            level=level,
            message=message,
            trace_id=trace_id,
            span_id=span_id,
            context=kwargs
        )
        
        self.log_records.append(record)
        
        # 输出到控制台
        self._console_output(record)
    
    def _console_output(self, record: LogRecord):
        """输出到控制台"""
        level_color = {
            LogLevel.DEBUG: "\033[94m",
            LogLevel.INFO: "\033[92m",
            LogLevel.WARNING: "\033[93m",
            LogLevel.ERROR: "\033[91m",
            LogLevel.CRITICAL: "\033[41m"
        }
        
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.timestamp))
        color = level_color.get(record.level, "\033[0m")
        
        print(f"{color}[{time_str}] [{record.level.value.upper()}] {record.message}\033[0m")
    
    def debug(self, message: str, **kwargs):
        """记录DEBUG级别日志"""
        self._log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """记录INFO级别日志"""
        self._log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """记录WARNING级别日志"""
        self._log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """记录ERROR级别日志"""
        self._log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """记录CRITICAL级别日志"""
        self._log(LogLevel.CRITICAL, message, **kwargs)
    
    def get_logs(self, limit: int = 100, level: Optional[LogLevel] = None) -> list:
        """
        获取日志记录
        
        Args:
            limit: 返回数量限制
            level: 日志级别过滤
        
        Returns:
            日志记录列表
        """
        logs = self.log_records
        
        if level:
            logs = [r for r in logs if r.level == level]
        
        logs.sort(key=lambda r: r.timestamp, reverse=True)
        
        return [{
            "timestamp": r.timestamp,
            "level": r.level.value,
            "message": r.message,
            "trace_id": r.trace_id,
            "span_id": r.span_id,
            "context": r.context
        } for r in logs[:limit]]
    
    def get_logs_by_trace(self, trace_id: str) -> list:
        """
        获取指定追踪的日志
        
        Args:
            trace_id: 追踪ID
        
        Returns:
            日志记录列表
        """
        logs = [r for r in self.log_records if r.trace_id == trace_id]
        logs.sort(key=lambda r: r.timestamp)
        
        return [{
            "timestamp": r.timestamp,
            "level": r.level.value,
            "message": r.message,
            "span_id": r.span_id,
            "context": r.context
        } for r in logs]
    
    def clear_logs(self):
        """清除日志"""
        self.log_records.clear()

# 全局日志系统实例
_logger_instance = None

def get_logger(service_name: str = "livingtree") -> LoggerSystem:
    """获取全局日志系统实例"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = LoggerSystem(service_name)
    return _logger_instance