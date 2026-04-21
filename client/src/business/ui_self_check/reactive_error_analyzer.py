"""
反应式错误分析通道 - ReactiveErrorAnalyzer
核心理念：救火队 - 立即捕获、高优先级、AI诊断根因

触发条件：操作失败、API异常、状态异常
特点：高优先级，但频率低
"""

import threading
import time
import logging
from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import re

from .context_collector import ContextCollector, ErrorContext, ContextLevel
from .analysis_cache import AnalysisCache
from .async_task_queue import AsyncTaskQueue, TaskPriority

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """错误严重程度"""
    INFO = 0
    WARNING = 1
    ERROR = 2
    CRITICAL = 3


@dataclass
class ErrorPattern:
    """错误模式"""
    pattern: str
    error_type: str
    description: str
    severity: ErrorSeverity
    likely_causes: List[str]
    quick_fixes: List[str]


@dataclass
class DiagnosisResult:
    """诊断结果"""
    error_context: ErrorContext
    severity: ErrorSeverity
    root_cause: str
    likely_causes: List[str]
    fix_suggestions: List[str]
    code_diff: Optional[str] = None
    doc_links: List[str] = field(default_factory=list)
    confidence: float = 0.0
    cached: bool = False


class KnownErrorPatterns:
    """已知错误模式库"""

    PATTERNS: List[ErrorPattern] = [
        ErrorPattern(
            pattern=r"Connection.*refused|ECONNREFUSED",
            error_type="ConnectionError",
            description="网络连接被拒绝",
            severity=ErrorSeverity.ERROR,
            likely_causes=["服务器未启动", "防火墙阻止", "端口配置错误"],
            quick_fixes=["检查服务状态", "验证防火墙规则", "核对地址配置"]
        ),
        ErrorPattern(
            pattern=r"Timeout|timed out|ETIMEDOUT",
            error_type="TimeoutError",
            description="请求超时",
            severity=ErrorSeverity.WARNING,
            likely_causes=["网络延迟", "服务端处理慢", "超时设置过短"],
            quick_fixes=["增加超时时间", "检查网络", "优化服务端"]
        ),
        ErrorPattern(
            pattern=r"404|Not Found|ENOENT",
            error_type="NotFoundError",
            description="资源不存在",
            severity=ErrorSeverity.WARNING,
            likely_causes=["资源已删除", "路径错误", "ID不正确"],
            quick_fixes=["核对路径", "确认资源ID", "检查资源状态"]
        ),
        ErrorPattern(
            pattern=r"401|Unauthorized|Authentication failed",
            error_type="AuthError",
            description="认证失败",
            severity=ErrorSeverity.ERROR,
            likely_causes=["Token过期", "凭证错误", "权限不足"],
            quick_fixes=["刷新Token", "核对凭证", "检查权限"]
        ),
        ErrorPattern(
            pattern=r"500|Internal Server Error",
            error_type="ServerError",
            description="服务器内部错误",
            severity=ErrorSeverity.ERROR,
            likely_causes=["服务端异常", "资源不足", "依赖不可用"],
            quick_fixes=["查看服务端日志", "检查资源", "联系技术支持"]
        ),
        ErrorPattern(
            pattern=r"JSON.*decode|json.decoder|Parse error",
            error_type="ParseError",
            description="JSON解析错误",
            severity=ErrorSeverity.WARNING,
            likely_causes=["数据格式错误", "编码问题", "格式不匹配"],
            quick_fixes=["检查数据编码", "验证JSON", "添加错误处理"]
        ),
        ErrorPattern(
            pattern=r"Permission denied|Access denied|EACCES",
            error_type="PermissionError",
            description="权限不足",
            severity=ErrorSeverity.ERROR,
            likely_causes=["用户权限不够", "文件权限错误", "安全策略阻止"],
            quick_fixes=["确认用户权限", "检查文件权限", "联系管理员"]
        ),
        ErrorPattern(
            pattern=r"Disk full|ENOSPC|No space left",
            error_type="DiskSpaceError",
            description="磁盘空间不足",
            severity=ErrorSeverity.CRITICAL,
            likely_causes=["磁盘已满", "日志占用大", "临时文件未清理"],
            quick_fixes=["清理磁盘", "删除日志", "清理临时文件"]
        ),
    ]

    @classmethod
    def match(cls, error_message: str, error_type: str) -> Optional[ErrorPattern]:
        """匹配错误模式"""
        for pattern in cls.PATTERNS:
            if re.search(pattern.pattern, error_message, re.IGNORECASE):
                return pattern
            if pattern.error_type.lower() == error_type.lower():
                return pattern
        return None


class ReactiveErrorAnalyzer:
    """
    反应式错误分析器

    工作流程：
    1. 捕获错误上下文
    2. 检查缓存
    3. 模式匹配
    4. AI诊断
    5. 返回诊断结果
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._collector = ContextCollector()
        self._cache = AnalysisCache()
        self._task_queue = AsyncTaskQueue()
        self._ai_diagnosis_callback: Optional[Callable] = None
        self._listeners: List[Callable] = []
        self._enabled = True
        self._pattern_match_count = 0
        self._ai_diagnosis_count = 0

    def set_ai_diagnosis_callback(self, callback: Callable):
        """设置AI诊断回调"""
        self._ai_diagnosis_callback = callback

    def add_listener(self, listener: Callable):
        """添加诊断结果监听器"""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable):
        """移除监听器"""
        self._listeners.remove(listener)

    def analyze_error(
        self,
        error: Exception,
        component_name: str = "Unknown",
        action: str = "unknown_action",
        input_params: Optional[Dict[str, Any]] = None
    ) -> DiagnosisResult:
        """同步分析错误"""
        if not self._enabled:
            return None

        context = self._collector.collect_error_context(
            error=error,
            component_name=component_name,
            action=action,
            level=ContextLevel.STANDARD,
            input_params=input_params
        )

        return self._process_context(context)

    def analyze_error_async(
        self,
        error: Exception,
        component_name: str = "Unknown",
        action: str = "unknown_action",
        input_params: Optional[Dict[str, Any]] = None,
        callback: Optional[Callable] = None
    ) -> str:
        """异步分析错误"""
        if not self._enabled:
            return ""

        context = self._collector.collect_error_context(
            error=error,
            component_name=component_name,
            action=action,
            level=ContextLevel.LIGHTWEIGHT,
            input_params=input_params
        )

        task_context = {
            "context": context,
            "callback": callback
        }

        def handler(ctx: Dict) -> DiagnosisResult:
            return self._process_context(ctx["context"])

        task_id = self._task_queue.submit_error_analysis(
            context=task_context,
            callback=lambda r: self._handle_async_result(r, callback),
            handler=handler
        )

        return task_id

    def analyze_error_from_info(
        self,
        error_type: str,
        error_message: str,
        component_name: str = "Unknown",
        action: str = "unknown_action",
        stack_trace: Optional[str] = None
    ) -> DiagnosisResult:
        """从已知信息分析错误"""
        if not self._enabled:
            return None

        context = self._collector.collect_error_from_info(
            error_type=error_type,
            error_message=error_message,
            component_name=component_name,
            action=action,
            stack_trace=stack_trace
        )

        return self._process_context(context)

    def _process_context(self, context: ErrorContext) -> DiagnosisResult:
        """处理错误上下文"""
        # 检查缓存
        cached = self._cache.get(
            error_type=context.error_type,
            component_name=context.component_name,
            stack_hash=context.stack_hash
        )

        if cached:
            return DiagnosisResult(
                error_context=context,
                severity=ErrorSeverity.WARNING,
                root_cause=cached.diagnosis,
                likely_causes=[cached.suggestion],
                fix_suggestions=[cached.suggestion],
                code_diff=cached.code_diff,
                doc_links=cached.doc_links,
                confidence=cached.confidence,
                cached=True
            )

        # 模式匹配
        pattern = KnownErrorPatterns.match(context.error_message, context.error_type)

        if pattern:
            self._pattern_match_count += 1
            result = DiagnosisResult(
                error_context=context,
                severity=pattern.severity,
                root_cause=pattern.description,
                likely_causes=pattern.likely_causes,
                fix_suggestions=pattern.quick_fixes,
                code_diff=None,
                doc_links=[],
                confidence=0.85,
                cached=False
            )
        else:
            result = self._ai_diagnosis(context)

        # 存入缓存
        self._cache.put(
            error_type=context.error_type,
            component_name=context.component_name,
            stack_hash=context.stack_hash,
            diagnosis=result.root_cause,
            suggestion="\n".join(result.fix_suggestions) if result.fix_suggestions else "",
            code_diff=result.code_diff,
            doc_links=result.doc_links,
            confidence=result.confidence
        )

        self._notify_listeners(result)

        return result

    def _ai_diagnosis(self, context: ErrorContext) -> DiagnosisResult:
        """AI诊断"""
        if self._ai_diagnosis_callback:
            try:
                return self._ai_diagnosis_callback(context)
            except Exception as e:
                logger.error(f"AI diagnosis failed: {e}")

        return self._default_diagnosis(context)

    def _default_diagnosis(self, context: ErrorContext) -> DiagnosisResult:
        """默认诊断"""
        severity = ErrorSeverity.ERROR

        if context.error_type in ("TimeoutError", "ConnectionError"):
            severity = ErrorSeverity.WARNING
        elif context.error_type in ("PermissionError", "DiskSpaceError"):
            severity = ErrorSeverity.CRITICAL

        root_cause = f"{context.error_type}: {context.error_message[:100]}"
        fix_suggestions = [f"检查 {context.component_name} 组件状态"]

        if context.file_path:
            fix_suggestions.append(f"检查文件: {context.file_path}:{context.line_number}")

        return DiagnosisResult(
            error_context=context,
            severity=severity,
            root_cause=root_cause,
            likely_causes=["代码逻辑错误", "外部依赖异常", "配置问题"],
            fix_suggestions=fix_suggestions,
            code_diff=None,
            doc_links=[],
            confidence=0.6,
            cached=False
        )

    def _handle_async_result(self, result: Any, callback: Optional[Callable]):
        """处理异步结果"""
        if callback and result:
            callback(result)
        if result:
            self._notify_listeners(result)

    def _notify_listeners(self, result: DiagnosisResult):
        """通知监听器"""
        for listener in self._listeners:
            try:
                listener(result)
            except Exception as e:
                logger.error(f"Listener error: {e}")

    def enable(self):
        """启用"""
        self._enabled = True

    def disable(self):
        """禁用"""
        self._enabled = False

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "pattern_match": self._pattern_match_count,
            "ai_diagnosis": self._ai_diagnosis_count,
            "cache_stats": self._cache.get_stats()
        }


reactive_analyzer = ReactiveErrorAnalyzer()
