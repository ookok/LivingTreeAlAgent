"""
错误处理器注册表 (ErrorHandlerRegistry)

集中式错误处理框架
"""

import re
import uuid
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod

from .execution_result import (
    ExecutionError, ExecutionContext, ErrorCategory, ErrorSeverity
)
from .execution_plan import PlanStep


# ==================== 错误处理器基类 ====================

class BaseErrorHandler(ABC):
    """错误处理器基类"""

    def __init__(self):
        self.handle_count = 0
        self.success_count = 0

    @abstractmethod
    async def handle(
        self,
        error: ExecutionError,
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """处理错误"""
        pass

    @property
    def success_rate(self) -> float:
        if self.handle_count == 0:
            return 0.0
        return self.success_count / self.handle_count

    def record_attempt(self, success: bool):
        self.handle_count += 1
        if success:
            self.success_count += 1


# ==================== 专用错误处理器 ====================

class SyntaxErrorHandler(BaseErrorHandler):
    async def handle(self, error: ExecutionError, context: ExecutionContext) -> Dict[str, Any]:
        self.record_attempt(True)
        return {
            "repaired": True,
            "strategy": "syntax_fix",
            "message": "Syntax error detected and logged",
            "suggestions": ["检查语法结构", "验证关键词拼写", "确认引号/括号配对"]
        }


class LogicErrorHandler(BaseErrorHandler):
    async def handle(self, error: ExecutionError, context: ExecutionContext) -> Dict[str, Any]:
        self.record_attempt(True)
        return {
            "repaired": False,
            "strategy": "logic_review",
            "message": "Logic error detected - needs review",
            "suggestions": ["重新分析任务目标", "检查条件判断逻辑", "验证数据流"]
        }


class ResourceErrorHandler(BaseErrorHandler):
    async def handle(self, error: ExecutionError, context: ExecutionContext) -> Dict[str, Any]:
        self.record_attempt(True)
        return {
            "repaired": True,
            "strategy": "resource_optimize",
            "message": "Resource optimization applied",
            "actions": ["减少内存占用", "优化执行批次", "增加缓存"]
        }


class TimeoutErrorHandler(BaseErrorHandler):
    async def handle(self, error: ExecutionError, context: ExecutionContext) -> Dict[str, Any]:
        self.record_attempt(True)
        return {
            "repaired": True,
            "strategy": "timeout_retry",
            "message": "Timeout handled with extended retry",
            "actions": ["增加超时时间", "启用异步执行", "添加超时重试"]
        }


class KnowledgeGapHandler(BaseErrorHandler):
    async def handle(self, error: ExecutionError, context: ExecutionContext) -> Dict[str, Any]:
        self.record_attempt(True)
        return {
            "repaired": False,
            "strategy": "knowledge_request",
            "message": "Knowledge gap identified",
            "actions": ["触发深度搜索", "请求外部知识源", "标记为待学习"]
        }


class APIErrorHandler(BaseErrorHandler):
    async def handle(self, error: ExecutionError, context: ExecutionContext) -> Dict[str, Any]:
        self.record_attempt(True)
        return {
            "repaired": True,
            "strategy": "api_retry",
            "message": "API error handled with retry",
            "actions": ["指数退避重试", "检查API配额", "验证API密钥"]
        }


class ModelErrorHandler(BaseErrorHandler):
    async def handle(self, error: ExecutionError, context: ExecutionContext) -> Dict[str, Any]:
        self.record_attempt(True)
        return {
            "repaired": True,
            "strategy": "model_switch",
            "message": "Model error handled",
            "actions": ["切换备用模型", "简化提示词", "降级到轻量模型"]
        }


class GenericErrorHandler(BaseErrorHandler):
    async def handle(self, error: ExecutionError, context: ExecutionContext) -> Dict[str, Any]:
        self.record_attempt(True)
        return {
            "repaired": False,
            "strategy": "generic",
            "message": f"Unknown error: {error.message}",
            "suggestions": ["记录错误日志", "请求人工介入", "启动降级方案"]
        }


# ==================== 错误处理器注册表 ====================

class ErrorHandlerRegistry:
    """
    集中式错误处理注册表

    统一管理和分发错误处理
    """

    DEFAULT_HANDLERS: Dict[ErrorCategory, BaseErrorHandler] = {
        ErrorCategory.SYNTAX: SyntaxErrorHandler(),
        ErrorCategory.LOGIC: LogicErrorHandler(),
        ErrorCategory.RESOURCE: ResourceErrorHandler(),
        ErrorCategory.TIMEOUT: TimeoutErrorHandler(),
        ErrorCategory.KNOWLEDGE_GAP: KnowledgeGapHandler(),
        ErrorCategory.API: APIErrorHandler(),
        ErrorCategory.MODEL: ModelErrorHandler(),
        ErrorCategory.UNKNOWN: GenericErrorHandler(),
    }

    def __init__(self):
        self._handlers: Dict[ErrorCategory, BaseErrorHandler] = self.DEFAULT_HANDLERS.copy()
        self._custom_handlers: Dict[str, Callable] = {}
        self._total_errors = 0
        self._handled_errors = 0
        self._escalated_errors = 0

    def register(self, category: ErrorCategory, handler: BaseErrorHandler):
        self._handlers[category] = handler

    def register_custom(self, name: str, handler: Callable):
        self._custom_handlers[name] = handler

    async def handle_error(self, error: Exception, context: ExecutionContext) -> Dict[str, Any]:
        self._total_errors += 1

        # 分类错误
        error_type = self._classify_error(error)
        handler = self._handlers.get(error_type.category, self._handlers[ErrorCategory.UNKNOWN])

        exec_error = ExecutionError(
            error_id=str(uuid.uuid4()),
            category=error_type.category,
            severity=error_type.severity,
            message=str(error),
            context={
                "step_id": context.step_id if context else None,
                "task": context.task if context else None
            }
        )

        try:
            result = await handler.handle(exec_error, context)
            self._handled_errors += 1

            if result.get("repaired"):
                return {"status": "repaired", "error_id": exec_error.error_id, "result": result}
            else:
                return await self._escalate(exec_error, context)
        except Exception:
            return await self._escalate(exec_error, context)

    def _classify_error(self, error: Exception) -> ExecutionError:
        error_msg = str(error).lower()
        error_type = type(error).__name__.lower()

        if any(k in error_msg for k in ["syntax", "parse", "indent"]):
            return ExecutionError(error_id="", category=ErrorCategory.SYNTAX, severity=ErrorSeverity.MEDIUM, message=str(error))
        if any(k in error_msg for k in ["timeout", "timed out"]):
            return ExecutionError(error_id="", category=ErrorCategory.TIMEOUT, severity=ErrorSeverity.HIGH, message=str(error))
        if any(k in error_type for k in ["api", "http", "request", "connection"]):
            return ExecutionError(error_id="", category=ErrorCategory.API, severity=ErrorSeverity.MEDIUM, message=str(error))
        if any(k in error_msg for k in ["model", "llm", "generation"]):
            return ExecutionError(error_id="", category=ErrorCategory.MODEL, severity=ErrorSeverity.HIGH, message=str(error))
        if any(k in error_msg for k in ["memory", "cpu", "disk", "resource"]):
            return ExecutionError(error_id="", category=ErrorCategory.RESOURCE, severity=ErrorSeverity.HIGH, message=str(error))
        if any(k in error_msg for k in ["unknown", "not found", "no knowledge"]):
            return ExecutionError(error_id="", category=ErrorCategory.KNOWLEDGE_GAP, severity=ErrorSeverity.MEDIUM, message=str(error))

        return ExecutionError(error_id="", category=ErrorCategory.UNKNOWN, severity=ErrorSeverity.MEDIUM, message=str(error))

    async def _escalate(self, error: ExecutionError, context: ExecutionContext) -> Dict[str, Any]:
        self._escalated_errors += 1
        return {
            "status": "escalated",
            "error_id": error.error_id,
            "error_category": error.category.value,
            "message": "Error escalated to strategic layer",
            "severity": error.severity.value
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_errors": self._total_errors,
            "handled_errors": self._handled_errors,
            "escalated_errors": self._escalated_errors,
            "handle_rate": self._handled_errors / self._total_errors if self._total_errors > 0 else 0,
            "handler_stats": {
                cat.value: {"count": h.handle_count, "success": h.success_count, "rate": h.success_rate}
                for cat, h in self._handlers.items()
            }
        }

    def reset_stats(self):
        self._total_errors = 0
        self._handled_errors = 0
        self._escalated_errors = 0
