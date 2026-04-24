#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Error Logger - 错误日志管理系统
=================================

功能：
1. 错误日志分类和结构化存储
2. 自动诊断错误原因
3. 提供修复建议
4. 错误统计和分析
5. 与智能诊断引擎集成

使用方式：
    from core.error_management import get_error_logger
    
    error_logger = get_error_logger()
    try:
        # 可能出错的代码
        pass
    except Exception as e:
        error_logger.log_error(e, component="main_window", context={"action": "initialize"})
"""

import os
import sys
import json
import traceback
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, List, Tuple
from pathlib import Path

# 导入现有的日志系统
from core.intelligent_diagnosis.structured_logger import get_logger, ErrorCategory
from core.intelligent_diagnosis.diagnosis_engine import get_diagnosis_engine, DiagnosisResult

# 全局错误日志目录
_ERROR_LOG_DIR = Path.home() / ".living_tree_ai" / "errors"
_ERROR_LOG_DIR.mkdir(parents=True, exist_ok=True)

# 错误分类
class ErrorType(Enum):
    """错误类型枚举"""
    UI_INIT = "UI_INIT"  # UI初始化错误
    MODEL_LOAD = "MODEL_LOAD"  # 模型加载错误
    NETWORK = "NETWORK"  # 网络错误
    CONFIG = "CONFIG"  # 配置错误
    DEPENDENCY = "DEPENDENCY"  # 依赖错误
    RUNTIME = "RUNTIME"  # 运行时错误
    UNKNOWN = "UNKNOWN"  # 未知错误

# 错误严重程度
class ErrorSeverity(Enum):
    """错误严重程度"""
    CRITICAL = "CRITICAL"  # 严重错误，系统无法运行
    ERROR = "ERROR"  # 错误，功能无法使用
    WARNING = "WARNING"  # 警告，功能受限
    INFO = "INFO"  # 信息，仅记录

class ErrorLogger:
    """错误日志管理器"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.logger = get_logger("error_management")
        self.diagnosis_engine = get_diagnosis_engine()
        self.error_history = []
        self.error_stats = {}
        
        # 生成会话ID（基于时间戳）
        import platform
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._system_info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "python_version": platform.python_version(),
            "machine": platform.machine()
        }
        
        # 记录会话启动
        self._log_session_start()
        
        # 错误模式映射
        self.error_patterns = {
            "UI_INIT": {
                "patterns": [r"AttributeError.*GlobalColor", r"QWidget.*init", r"paintEvent.*error"],
                "severity": ErrorSeverity.ERROR,
                "suggestions": ["检查Qt版本兼容性", "确保UI组件正确初始化", "检查颜色常量名称"]
            },
            "MODEL_LOAD": {
                "patterns": [r"ModelBackend.*GGUF", r"model.*load.*failed", r"Ollama.*error"],
                "severity": ErrorSeverity.CRITICAL,
                "suggestions": ["检查模型路径", "确保Ollama服务运行", "尝试使用不同的模型"]
            },
            "NETWORK": {
                "patterns": [r"Connection.*timeout", r"Connection.*refused", r"HTTP.*error"],
                "severity": ErrorSeverity.WARNING,
                "suggestions": ["检查网络连接", "确保服务地址正确", "增加超时时间"]
            },
            "CONFIG": {
                "patterns": [r"Config.*missing", r"Config.*invalid", r"KeyError.*config"],
                "severity": ErrorSeverity.ERROR,
                "suggestions": ["检查配置文件", "恢复默认配置", "确保配置键存在"]
            },
            "DEPENDENCY": {
                "patterns": [r"ImportError", r"ModuleNotFoundError", r"No module named"],
                "severity": ErrorSeverity.CRITICAL,
                "suggestions": ["安装缺失的依赖", "检查依赖版本", "重新安装依赖"]
            }
        }
        
        self._initialized = True
    
    def _log_session_start(self):
        """记录会话启动信息"""
        session_start_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self._session_id,
            "event": "session_start",
            "system_info": self._system_info,
            "message": f"客户端会话启动 - {self._session_id}"
        }
        
        # 保存会话启动日志
        session_file = _ERROR_LOG_DIR / f"session_{self._session_id}_start.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_start_entry, f, ensure_ascii=False, indent=2)
        
        # 保存到汇总文件
        summary_file = _ERROR_LOG_DIR / "errors_summary.json"
        summary_data = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "session_id": self._session_id,
            "error_count": 0,
            "error_stats": {},
            "recent_errors": [],
            "session_start": session_start_entry
        }
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)
    
    def log_error(self, error: Exception, component: str = "unknown", context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        记录错误并自动诊断
        
        Args:
            error: 异常对象
            component: 出错的组件
            context: 上下文信息
            
        Returns:
            错误日志条目
        """
        # 构建错误信息
        error_message = str(error)
        stack_trace = traceback.format_exc()
        
        # 分类错误
        error_type = self._classify_error(error_message, stack_trace)
        severity = self._get_severity(error_type)
        
        # 构建错误条目
        error_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": component,
            "error_type": error_type.value,
            "severity": severity.value,
            "message": error_message,
            "stack_trace": stack_trace,
            "context": context or {},
            "error_code": self._generate_error_code(error_type)
        }
        
        # 诊断错误
        diagnosis = self._diagnose_error(error_entry)
        error_entry["diagnosis"] = diagnosis
        
        # 保存错误日志
        self._save_error_log(error_entry)
        
        # 更新统计
        self._update_stats(error_type, severity)
        
        # 记录到结构化日志
        self.logger.error(
            error_message,
            error_code=error_entry["error_code"],
            error_category=self._map_to_error_category(error_type),
            component=component,
            context=context,
            diagnosis=diagnosis
        )
        
        return error_entry
    
    def _classify_error(self, message: str, stack_trace: str) -> ErrorType:
        """分类错误"""
        import re
        
        for error_type, pattern_info in self.error_patterns.items():
            for pattern in pattern_info["patterns"]:
                if re.search(pattern, message) or re.search(pattern, stack_trace):
                    return ErrorType(error_type)
        
        return ErrorType.UNKNOWN
    
    def _get_severity(self, error_type: ErrorType) -> ErrorSeverity:
        """获取错误严重程度"""
        if error_type in self.error_patterns:
            return self.error_patterns[error_type.value]["severity"]
        return ErrorSeverity.ERROR
    
    def _generate_error_code(self, error_type: ErrorType) -> str:
        """生成错误代码"""
        type_code = error_type.value[:3].upper()
        return f"{type_code}_{len(self.error_history):03d}"
    
    def _map_to_error_category(self, error_type: ErrorType) -> ErrorCategory:
        """映射到ErrorCategory"""
        mapping = {
            ErrorType.UI_INIT: ErrorCategory.RESOURCE,
            ErrorType.MODEL_LOAD: ErrorCategory.AI_MODEL,
            ErrorType.NETWORK: ErrorCategory.NETWORK,
            ErrorType.CONFIG: ErrorCategory.CONFIG,
            ErrorType.DEPENDENCY: ErrorCategory.DEPENDENCY,
            ErrorType.RUNTIME: ErrorCategory.BUSINESS,
            ErrorType.UNKNOWN: ErrorCategory.UNKNOWN
        }
        return mapping.get(error_type, ErrorCategory.UNKNOWN)
    
    def _diagnose_error(self, error_entry: Dict[str, Any]) -> Dict[str, Any]:
        """诊断错误"""
        try:
            diagnosis_result = self.diagnosis_engine.diagnose(error_entry)
            return {
                "probable_cause": diagnosis_result.probable_cause,
                "confidence": diagnosis_result.confidence,
                "suggested_fix": diagnosis_result.suggested_fix,
                "auto_fix_possible": diagnosis_result.auto_fix_possible
            }
        except Exception as e:
            # 诊断失败时的默认诊断
            error_type = error_entry.get("error_type", "UNKNOWN")
            suggestions = []
            if error_type in self.error_patterns:
                suggestions = self.error_patterns[error_type]["suggestions"]
            
            return {
                "probable_cause": f"{error_type} error",
                "confidence": 0.5,
                "suggested_fix": suggestions[0] if suggestions else "查看详细日志",
                "auto_fix_possible": False
            }
    
    def _save_error_log(self, error_entry: Dict[str, Any]):
        """保存错误日志"""
        # 保存到历史记录
        self.error_history.append(error_entry)
        
        # 只保留最新的5条错误日志
        if len(self.error_history) > 5:
            # 删除最旧的错误日志文件
            oldest_error = self.error_history.pop(0)
            oldest_file = _ERROR_LOG_DIR / f"error_{self._session_id}_{1:03d}.json"
            if oldest_file.exists():
                oldest_file.unlink()
            
            # 重命名剩余的错误日志文件
            for i, error in enumerate(self.error_history, 1):
                old_file = _ERROR_LOG_DIR / f"error_{self._session_id}_{i+1:03d}.json"
                new_file = _ERROR_LOG_DIR / f"error_{self._session_id}_{i:03d}.json"
                if old_file.exists():
                    old_file.rename(new_file)
        
        # 保存到文件（使用会话ID和序号）
        error_count = len(self.error_history)
        error_file = _ERROR_LOG_DIR / f"error_{self._session_id}_{error_count:03d}.json"
        with open(error_file, 'w', encoding='utf-8') as f:
            json.dump(error_entry, f, ensure_ascii=False, indent=2)
        
        # 保存到汇总文件
        summary_file = _ERROR_LOG_DIR / "errors_summary.json"
        summary_data = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "session_id": self._session_id,
            "error_count": len(self.error_history),
            "error_stats": self.error_stats,
            "recent_errors": self.error_history[-5:] if self.error_history else []
        }
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)
    
    def _update_stats(self, error_type: ErrorType, severity: ErrorSeverity):
        """更新错误统计"""
        type_key = error_type.value
        if type_key not in self.error_stats:
            self.error_stats[type_key] = {
                "count": 0,
                "severities": {}
            }
        
        self.error_stats[type_key]["count"] += 1
        
        severity_key = severity.value
        if severity_key not in self.error_stats[type_key]["severities"]:
            self.error_stats[type_key]["severities"][severity_key] = 0
        self.error_stats[type_key]["severities"][severity_key] += 1
    
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计"""
        return self.error_stats
    
    def get_recent_errors(self, limit: int = 5) -> List[Dict[str, Any]]:
        """获取最近的错误"""
        return self.error_history[-limit:]
    
    def analyze_error_trends(self) -> Dict[str, Any]:
        """分析错误趋势"""
        trends = {
            "total_errors": len(self.error_history),
            "errors_by_type": {},
            "errors_by_severity": {},
            "most_common_error": None
        }
        
        # 按类型统计
        for error in self.error_history:
            error_type = error.get("error_type", "UNKNOWN")
            if error_type not in trends["errors_by_type"]:
                trends["errors_by_type"][error_type] = 0
            trends["errors_by_type"][error_type] += 1
        
        # 按严重程度统计
        for error in self.error_history:
            severity = error.get("severity", "ERROR")
            if severity not in trends["errors_by_severity"]:
                trends["errors_by_severity"][severity] = 0
            trends["errors_by_severity"][severity] += 1
        
        # 最常见的错误
        if trends["errors_by_type"]:
            most_common = max(trends["errors_by_type"].items(), key=lambda x: x[1])
            trends["most_common_error"] = {
                "type": most_common[0],
                "count": most_common[1]
            }
        
        return trends

# 单例
_error_logger_instance = None


def get_error_logger() -> ErrorLogger:
    """获取错误日志实例"""
    global _error_logger_instance
    if _error_logger_instance is None:
        _error_logger_instance = ErrorLogger()
    return _error_logger_instance


def setup_exception_handler():
    """设置异常处理器，捕获系统异常退出"""
    import sys
from core.logger import get_logger
logger = get_logger('error_management.error_logger')

    original_excepthook = sys.excepthook
    
    def exception_handler(exc_type, exc_value, exc_traceback):
        """捕获未处理的异常"""
        # 记录错误日志
        error_logger = get_error_logger()
        error_logger.log_error(
            exc_value,
            component="system",
            context={"action": "unhandled_exception", "exc_type": str(exc_type)}
        )
        
        # 调用原始的异常处理器
        original_excepthook(exc_type, exc_value, exc_traceback)
    
    sys.excepthook = exception_handler


# 自动设置异常处理器
setup_exception_handler()

# 错误捕获装饰器
def catch_and_log_errors(component: str = "unknown"):
    """
    错误捕获和日志记录装饰器
    
    Usage:
        @catch_and_log_errors("main_window")
        def some_function():
            # 可能出错的代码
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_logger = get_error_logger()
                error_entry = error_logger.log_error(e, component=component, context={"function": func.__name__})
                # 重新抛出异常，以便上层处理
                raise
        return wrapper
    return decorator

# 示例用法
if __name__ == "__main__":
    error_logger = get_error_logger()
    
    # 测试错误日志
    try:
        # 模拟UI初始化错误
        raise AttributeError("type object 'GlobalColor' has no attribute 'lightBlue'")
    except Exception as e:
        error_entry = error_logger.log_error(e, component="main_window", context={"action": "initialize"})
        logger.info(f"Error logged: {error_entry['error_code']}")
        logger.info(f"Diagnosis: {error_entry['diagnosis']}")
    
    # 测试统计
    logger.info("\nError stats:")
    logger.info(json.dumps(error_logger.get_error_stats(), indent=2))
    
    logger.info("\nError trends:")
    logger.info(json.dumps(error_logger.analyze_error_trends(), indent=2))
