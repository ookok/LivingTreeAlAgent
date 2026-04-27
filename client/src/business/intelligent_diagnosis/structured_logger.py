#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Structured Logger - 结构化日志记录器
======================================

三层日志架构：
1. 技术层 - 开发者视角，详细技术细节 (TECHNICAL)
2. 诊断层 - 系统自诊断视角，结构化问题分析 (DIAGNOSTIC)
3. 用户层 - 普通用户视角，自然语言描述 (USER)

统一日志格式：
{
    "timestamp": "ISO8601",
    "trace_id": "全局追踪ID",
    "level": "ERROR/WARN/INFO/DEBUG",
    "component": "模块名",
    "error_code": "标准错误码",
    "error_category": "错误分类",
    "message": "日志消息",
    "context": {...},
    "technical_details": {...},
    "diagnosis": {...}
}

技术选型：
- loguru: 增强日志功能
- structlog: 结构化日志（可选）

Usage:
    from client.src.business.intelligent_diagnosis import get_logger

    logger = get_logger("network")
    logger.error("Connection failed",
        error_code="NET_001",
        error_category=ErrorCategory.NETWORK,
        probable_cause="超时",
        suggested_fix="检查网络连接"
    )
"""

import os
import sys
import json
import uuid
import traceback
import threading
import functools
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Callable
from pathlib import Path

# 尝试导入 loguru，如果不可用则使用标准库
try:
    from loguru import logger as _loguru_logger
    _HAS_LOGURU = True
except ImportError:
    _HAS_LOGURU = False
    _loguru_logger = None


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorCategory(Enum):
    """错误分类体系"""
    # 系统级错误
    RESOURCE = "RESOURCE"           # 资源不足 (内存/CPU/存储)
    DEPENDENCY = "DEPENDENCY"       # 依赖服务不可用
    CONFIG = "CONFIG"               # 配置错误

    # 应用级错误
    VALIDATION = "VALIDATION"        # 输入验证失败
    BUSINESS = "BUSINESS"           # 业务逻辑错误
    DATA = "DATA"                   # 数据一致性错误

    # 网络级错误
    NETWORK = "NETWORK"             # 网络连接错误
    TIMEOUT = "TIMEOUT"             # 操作超时
    PROTOCOL = "PROTOCOL"           # 协议错误

    # 用户级错误
    PERMISSION = "PERMISSION"       # 权限不足
    INPUT_FORMAT = "INPUT_FORMAT"   # 输入格式错误
    INVALID_OP = "INVALID_OP"       # 无效操作

    # AI相关错误
    AI_MODEL = "AI_MODEL"           # AI模型错误
    AI_INFERENCE = "AI_INFERENCE"   # AI推理错误
    AI_CONTEXT = "AI_CONTEXT"       # 上下文错误

    # 未知
    UNKNOWN = "UNKNOWN"


# 错误码前缀映射
_ERROR_CODE_PREFIX = {
    ErrorCategory.RESOURCE: "RES",
    ErrorCategory.DEPENDENCY: "DEP",
    ErrorCategory.CONFIG: "CFG",
    ErrorCategory.VALIDATION: "VAL",
    ErrorCategory.BUSINESS: "BSN",
    ErrorCategory.DATA: "DAT",
    ErrorCategory.NETWORK: "NET",
    ErrorCategory.TIMEOUT: "TMO",
    ErrorCategory.PROTOCOL: "PRO",
    ErrorCategory.PERMISSION: "PRM",
    ErrorCategory.INPUT_FORMAT: "FMT",
    ErrorCategory.INVALID_OP: "OPR",
    ErrorCategory.AI_MODEL: "AIM",
    ErrorCategory.AI_INFERENCE: "INF",
    ErrorCategory.AI_CONTEXT: "CTX",
    ErrorCategory.UNKNOWN: "UNK",
}

# 标准错误码库
STANDARD_ERROR_CODES = {
    # RESOURCE
    "RES_001": {"name": "内存不足", "auto_fix": True},
    "RES_002": {"name": "CPU过载", "auto_fix": False},
    "RES_003": {"name": "磁盘空间不足", "auto_fix": True},
    "RES_004": {"name": "文件句柄耗尽", "auto_fix": True},
    # NETWORK
    "NET_001": {"name": "连接超时", "auto_fix": True},
    "NET_002": {"name": "连接被拒绝", "auto_fix": False},
    "NET_003": {"name": "DNS解析失败", "auto_fix": True},
    "NET_004": {"name": "地址不可达", "auto_fix": False},
    # DEPENDENCY
    "DEP_001": {"name": "服务不可用", "auto_fix": True},
    "DEP_002": {"name": "依赖模块加载失败", "auto_fix": True},
    "DEP_003": {"name": "数据库连接失败", "auto_fix": True},
    # AI
    "AIM_001": {"name": "模型加载失败", "auto_fix": True},
    "AIM_002": {"name": "模型推理超时", "auto_fix": True},
    "AIM_003": {"name": "上下文长度超限", "auto_fix": True},
    "INF_001": {"name": "推理结果无效", "auto_fix": False},
    "INF_002": {"name": "推理过程异常", "auto_fix": True},
    # CONFIG
    "CFG_001": {"name": "配置项缺失", "auto_fix": True},
    "CFG_002": {"name": "配置项无效", "auto_fix": True},
    "CFG_003": {"name": "配置文件损坏", "auto_fix": True},
}

# 全局日志目录
_LOG_DIR = Path.home() / ".living_tree_ai" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)


def generate_trace_id() -> str:
    """生成全局唯一追踪ID"""
    return f"tr_{uuid.uuid4().hex[:16]}"


def generate_session_id() -> str:
    """生成会话ID"""
    return f"se_{uuid.uuid4().hex[:12]}"


class StructuredLogger:
    """
    结构化日志记录器

    支持三层日志：
    1. TECHNICAL - 技术层（开发者）
    2. DIAGNOSTIC - 诊断层（系统）
    3. USER - 用户层（普通用户）
    """

    _instance: Optional['StructuredLogger'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        component: str = "app",
        log_dir: Optional[Path] = None,
        max_files: int = 30,
        json_format: bool = True
    ):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.component = component
        self.log_dir = log_dir or _LOG_DIR
        self.max_files = max_files
        self.json_format = json_format

        # 当前线程的上下文
        self._context: Dict[str, Any] = {}
        self._session_id: Optional[str] = None
        self._trace_id: Optional[str] = None

        # 设置 loguru
        if _HAS_LOGURU:
            self._setup_loguru()

        self._initialized = True

    def _setup_loguru(self):
        """配置 loguru"""
        # 移除默认处理器
        _loguru_logger.remove()

        # 添加文件处理器 - 技术层
        tech_file = self.log_dir / f"{self.component}_technical.log"
        _loguru_logger.add(
            tech_file,
            rotation="00:00",  # 每天轮转
            retention=self.max_files,
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            encoding="utf-8",
            enqueue=True
        )

        # 添加 JSON 文件处理器 - 诊断层
        diag_file = self.log_dir / f"{self.component}_diagnostic.jsonl"
        _loguru_logger.add(
            diag_file,
            rotation="00:00",
            retention=self.max_files,
            level="INFO",
            format="{message}",
            encoding="utf-8",
            enqueue=True,
            serialize=True  # JSON 格式
        )

        # 添加错误文件处理器
        error_file = self.log_dir / f"{self.component}_errors.jsonl"
        _loguru_logger.add(
            error_file,
            rotation="10 MB",
            retention=90,  # 保留更长时间
            level="ERROR",
            format="{message}",
            encoding="utf-8",
            enqueue=True,
            serialize=True
        )

        # 添加标准输出
        _loguru_logger.add(
            sys.stderr,
            level="INFO",
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
            colorize=True
        )

    def set_context(self, **kwargs):
        """设置日志上下文（线程安全）"""
        self._context.update(kwargs)

    def clear_context(self):
        """清除日志上下文"""
        self._context.clear()

    def set_session(self, session_id: str):
        """设置会话ID"""
        self._session_id = session_id

    def new_trace(self) -> str:
        """创建新的追踪ID"""
        self._trace_id = generate_trace_id()
        return self._trace_id

    def get_trace_id(self) -> Optional[str]:
        """获取当前追踪ID"""
        return self._trace_id or generate_trace_id()

    def _build_log_entry(
        self,
        level: str,
        message: str,
        error_code: Optional[str] = None,
        error_category: Optional[ErrorCategory] = None,
        context: Optional[Dict[str, Any]] = None,
        diagnosis: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: Optional[Exception] = None
    ) -> Dict[str, Any]:
        """构建结构化日志条目"""
        # 合并上下文
        log_context = {**self._context}
        if context:
            log_context.update(context)

        # 技术详情
        technical = {
            "component": self.component,
            "function": None,  # 会在 decorated 函数中填充
            "line": None,
        }

        # 异常信息
        if exc_info:
            technical["stack_trace"] = traceback.format_exception(type(exc_info), exc_info, exc_info.__traceback__)

        # 诊断信息
        diag = diagnosis or {}

        # 错误码处理
        if error_code:
            if error_code in STANDARD_ERROR_CODES:
                err_info = STANDARD_ERROR_CODES[error_code]
                diag.setdefault("error_name", err_info["name"])
                diag.setdefault("auto_fix_possible", err_info.get("auto_fix", False))

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": self.get_trace_id(),
            "session_id": self._session_id,
            "level": level,
            "component": self.component,
            "message": message,
            "error_code": error_code,
            "error_category": error_category.value if error_category else None,
            "context": log_context,
            "diagnosis": diag,
            "extra": extra or {}
        }

        if technical.get("stack_trace"):
            entry["technical_details"] = technical

        return entry

    def _log(
        self,
        level: str,
        message: str,
        error_code: Optional[str] = None,
        error_category: Optional[ErrorCategory] = None,
        context: Optional[Dict[str, Any]] = None,
        diagnosis: Optional[Dict[str, Any]] = None,
        exc_info: Optional[Exception] = None,
        **kwargs
    ):
        """内部日志方法"""
        entry = self._build_log_entry(
            level=level,
            message=message,
            error_code=error_code,
            error_category=error_category,
            context=context,
            diagnosis=diagnosis,
            exc_info=exc_info
        )

        if _HAS_LOGURU:
            # 使用 loguru
            log_msg = json.dumps(entry, ensure_ascii=False) if self.json_format else str(entry)
            getattr(_loguru_logger, level.lower())(log_msg)
        else:
            # 标准输出
            print(json.dumps(entry, ensure_ascii=False), file=sys.stderr)

    def debug(self, message: str, **kwargs):
        """DEBUG 级别日志"""
        self._log("DEBUG", message, **kwargs)

    def info(self, message: str, **kwargs):
        """INFO 级别日志"""
        self._log("INFO", message, **kwargs)

    def warn(self, message: str, **kwargs):
        """WARN 级别日志"""
        self._log("WARNING", message, **kwargs)

    def warning(self, message: str, **kwargs):
        """WARNING 级别日志"""
        self._log("WARNING", message, **kwargs)

    def error(
        self,
        message: str,
        error_code: Optional[str] = None,
        error_category: Optional[ErrorCategory] = None,
        diagnosis: Optional[Dict[str, Any]] = None,
        exc_info: Optional[Exception] = None,
        **kwargs
    ):
        """ERROR 级别日志"""
        self._log(
            "ERROR",
            message,
            error_code=error_code,
            error_category=error_category,
            diagnosis=diagnosis,
            exc_info=exc_info,
            **kwargs
        )

    def critical(
        self,
        message: str,
        error_code: Optional[str] = None,
        error_category: Optional[ErrorCategory] = None,
        diagnosis: Optional[Dict[str, Any]] = None,
        exc_info: Optional[Exception] = None,
        **kwargs
    ):
        """CRITICAL 级别日志"""
        self._log(
            "CRITICAL",
            message,
            error_code=error_code,
            error_category=error_category,
            diagnosis=diagnosis,
            exc_info=exc_info,
            **kwargs
        )

    def log_diagnostic(
        self,
        level: str,
        component: str,
        error_code: str,
        category: ErrorCategory,
        message: str,
        context: Dict[str, Any],
        diagnosis: Dict[str, Any],
        metrics: Optional[Dict[str, Any]] = None
    ):
        """
        诊断层日志 - 系统自诊断视角

        Args:
            level: 日志级别
            component: 组件名
            error_code: 标准错误码
            category: 错误分类
            message: 诊断消息
            context: 上下文信息
            diagnosis: 诊断结果
            metrics: 性能指标
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": self.get_trace_id(),
            "level": level,
            "component": component,
            "error_code": error_code,
            "error_category": category.value,
            "message": message,
            "context": context,
            "diagnosis": diagnosis,
            "metrics": metrics or {}
        }

        if _HAS_LOGURU:
            diag_file = self.log_dir / f"{component}_diagnostic.jsonl"
            _loguru_logger.info(json.dumps(entry, ensure_ascii=False))

    def log_user(
        self,
        level: str,
        user_message: str,
        system_context: Optional[Dict[str, Any]] = None,
        recovery_action: Optional[str] = None
    ):
        """
        用户层日志 - 普通用户视角

        Args:
            level: 日志级别
            user_message: 用户友好的消息
            system_context: 系统上下文（可选）
            recovery_action: 系统采取的恢复动作
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": self.get_trace_id(),
            "session_id": self._session_id,
            "level": level,
            "user_message": user_message,
            "system_context": system_context or {},
            "recovery_action": recovery_action,
            "user_facing": True
        }

        user_file = self.log_dir / "user_facing.jsonl"
        with open(user_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_logger(component: str = "app") -> StructuredLogger:
    """获取结构化日志记录器"""
    return StructuredLogger(component=component)


# 便捷函数
def log_error(
    component: str,
    message: str,
    error_code: str,
    error_category: ErrorCategory,
    **kwargs
):
    """便捷的错误日志函数"""
    logger = get_logger(component)
    logger.error(message, error_code=error_code, error_category=error_category, **kwargs)


def log_diagnosis(
    component: str,
    error_code: str,
    category: ErrorCategory,
    message: str,
    context: Dict[str, Any],
    diagnosis: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None
):
    """便捷的诊断日志函数"""
    logger = get_logger(component)
    logger.log_diagnostic(
        level="INFO",
        component=component,
        error_code=error_code,
        category=category,
        message=message,
        context=context,
        diagnosis=diagnosis,
        metrics=metrics
    )


class log_with_trace:
    """
    装饰器：自动追踪函数调用

    Usage:
        @log_with_trace("network")
        def connect(host, port):
            ...
    """

    def __init__(self, component: str, log_level: str = "DEBUG"):
        self.component = component
        self.log_level = log_level

    def __call__(self, func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(self.component)
            trace_id = logger.new_trace()

            # 脱敏处理
            safe_kwargs = self._sanitize_params(func, kwargs)

            logger.debug(
                f"→ {func.__name__} called",
                extra={"trace_id": trace_id, "params": safe_kwargs}
            )

            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()

                logger.debug(
                    f"✓ {func.__name__} completed",
                    extra={
                        "trace_id": trace_id,
                        "duration": duration,
                        "result_type": type(result).__name__
                    }
                )
                return result

            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error(
                    f"✗ {func.__name__} failed: {str(e)}",
                    exc_info=e,
                    extra={
                        "trace_id": trace_id,
                        "duration": duration,
                        "exception_type": type(e).__name__
                    }
                )
                raise

        return wrapper

    def _sanitize_params(self, func: Callable, params: Dict) -> Dict:
        """脱敏敏感参数"""
        # 敏感字段列表
        sensitive_fields = {'password', 'token', 'secret', 'api_key', 'auth'}
        sanitized = {}

        for key, value in params.items():
            if any(s in key.lower() for s in sensitive_fields):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, str) and len(value) > 100:
                sanitized[key] = value[:50] + "..."
            else:
                sanitized[key] = value

        return sanitized


# 示例用法
if __name__ == "__main__":
    logger = get_logger("test")

    # 基本日志
    logger.info("Application started")
    logger.set_context(user_id="user123", request_id="req456")

    # 错误日志
    logger.error(
        "Connection to AI service failed",
        error_code="NET_001",
        error_category=ErrorCategory.NETWORK,
        diagnosis={
            "probable_cause": "服务地址不可达",
            "confidence": 0.85,
            "suggested_fix": "检查服务地址和网络连接",
            "auto_fix_possible": True
        }
    )

    # 带追踪的函数调用
    @log_with_trace("test")
    def example_function(x, y):
        return x + y

    example_function(1, 2)

    print("StructuredLogger test completed!")
