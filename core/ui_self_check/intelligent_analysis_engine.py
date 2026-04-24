"""
双模态智能分析引擎 - IntelligentAnalysisEngine
核心理念：统一入口，协调两个分析通道

架构：
1. ReactiveErrorAnalyzer - 错误分析通道（救火队）
2. ProactiveSourceAnalyzer - 静默分析通道（巡检员）

特点：
1. 双通道互不阻塞
2. 统一的状态管理
3. 事件驱动的监听器
4. 性能监控
"""

import threading
import time
import logging
from typing import Callable, Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field

from .context_collector import ContextCollector, ErrorContext, SilentContext, ContextLevel
from .analysis_cache import AnalysisCache
from .async_task_queue import AsyncTaskQueue, TaskPriority
from .reactive_error_analyzer import (
    ReactiveErrorAnalyzer, DiagnosisResult, ErrorSeverity
)
from .proactive_source_analyzer import (
    ProactiveSourceAnalyzer, SourceAnalysisResult, SourceIssue, IssueSeverity
)
from .ai_diagnosis_service import AIDiagnosisService, AIDiagnosisResult
from .source_mapper import SourceMapper

logger = logging.getLogger(__name__)


@dataclass
class EngineStats:
    """引擎统计"""
    error_analysis_count: int = 0
    source_analysis_count: int = 0
    cache_hit_count: int = 0
    avg_error_analysis_time_ms: float = 0.0
    avg_source_analysis_time_ms: float = 0.0
    active_listeners: int = 0
    queue_size: int = 0


@dataclass
class AnalysisEvent:
    """分析事件"""
    event_type: str            # 'error' | 'source'
    timestamp: float
    component_name: str
    result: Any               # DiagnosisResult or SourceAnalysisResult


class IntelligentAnalysisEngine:
    """
    双模态智能分析引擎

    统一入口，管理两个分析通道：
    1. 错误分析通道（ReactiveErrorAnalyzer）
    2. 静默分析通道（ProactiveSourceAnalyzer）

    使用方式：

    # 初始化
    engine = IntelligentAnalysisEngine()
    engine.initialize(project_root="/path/to/project")

    # 设置回调
    engine.set_error_callback(lambda r: logger.info(f"Error: {r.root_cause}"))
    engine.set_source_callback(lambda r: logger.info(f"Issues: {len(r.issues)}"))

    # 触发分析
    engine.report_error(error, component_name="MainWindow", action="button_click")
    engine.report_operation(component_name="ChatPanel", action="send_message", duration_ms=500)
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

        # 两个分析通道
        self._error_analyzer = ReactiveErrorAnalyzer()
        self._source_analyzer = ProactiveSourceAnalyzer()
        self._ai_service = AIDiagnosisService()
        self._source_mapper: Optional[SourceMapper] = None

        # 回调
        self._error_callbacks: List[Callable] = []
        self._source_callbacks: List[Callable] = []
        self._event_listeners: List[Callable] = []

        # 配置
        self._enabled = True
        self._error_channel_enabled = True
        self._source_channel_enabled = True
        self._project_root = ""

        # 统计
        self._stats = EngineStats()
        self._stats_lock = threading.Lock()

    def initialize(self, project_root: str, enable_error_channel: bool = True, enable_source_channel: bool = True):
        """
        初始化引擎

        Args:
            project_root: 项目根目录
            enable_error_channel: 是否启用错误分析通道
            enable_source_channel: 是否启用静默分析通道
        """
        self._project_root = project_root
        self._source_mapper = SourceMapper(project_root)
        self._source_analyzer.set_project_root(project_root)
        self._error_channel_enabled = enable_error_channel
        self._source_channel_enabled = enable_source_channel

        # 设置AI诊断回调
        def ai_diagnosis(context: ErrorContext) -> DiagnosisResult:
            ai_result = self._ai_service.diagnose(context)
            if ai_result:
                from .reactive_error_analyzer import DiagnosisResult as DR, ErrorSeverity
from core.logger import get_logger
logger = get_logger('ui_self_check.intelligent_analysis_engine')

                return DR(
                    error_context=context,
                    severity=ErrorSeverity.ERROR,
                    root_cause=ai_result.root_cause,
                    likely_causes=ai_result.likely_causes,
                    fix_suggestions=ai_result.fix_suggestions,
                    code_diff=ai_result.code_diff,
                    doc_links=ai_result.doc_links,
                    confidence=ai_result.confidence,
                    cached=False
                )
            return None

        self._error_analyzer.set_ai_diagnosis_callback(ai_diagnosis)

        # 设置源码分析回调
        def ai_source_analysis(context: SilentContext, issues: List[SourceIssue]) -> List[SourceIssue]:
            # 可以调用AI服务增强分析
            return issues

        self._source_analyzer.set_ai_suggestion_callback(ai_source_analysis)

        # 注册监听器
        self._error_analyzer.add_listener(self._on_error_result)
        self._source_analyzer.add_listener(self._on_source_result)

        logger.info(f"Engine initialized: project_root={project_root}, "
                   f"error_channel={enable_error_channel}, "
                   f"source_channel={enable_source_channel}")

    def report_error(
        self,
        error: Exception,
        component_name: str,
        action: str,
        input_params: Optional[Dict[str, Any]] = None,
        callback: Optional[Callable] = None
    ):
        """
        报告错误（触发错误分析通道）

        这会立即捕获错误上下文并开始分析

        Args:
            error: 异常对象
            component_name: 组件名
            action: 操作描述
            input_params: 输入参数（会脱敏）
            callback: 分析完成回调
        """
        if not self._enabled or not self._error_channel_enabled:
            return

        # 异步执行，不阻塞
        self._error_analyzer.analyze_error_async(
            error=error,
            component_name=component_name,
            action=action,
            input_params=input_params,
            callback=callback
        )

        # 更新统计
        with self._stats_lock:
            self._stats.error_analysis_count += 1

    def report_operation(
        self,
        component_name: str,
        action: str,
        duration_ms: float,
        response_status: str = "success",
        callback: Optional[Callable] = None
    ):
        """
        报告操作（触发静默分析通道）

        带3秒防抖，只有用户空闲时才分析

        Args:
            component_name: 组件名
            action: 操作描述
            duration_ms: 操作持续时间
            response_status: 响应状态
            callback: 分析完成回调
        """
        if not self._enabled or not self._source_channel_enabled:
            return

        # 更新静默分析统计
        with self._stats_lock:
            self._stats.source_analysis_count += 1

        self._source_analyzer.submit_analysis(
            component_name=component_name,
            action=action,
            duration_ms=duration_ms,
            response_status=response_status,
            callback=callback
        )

    def report_no_response(
        self,
        component_name: str,
        action: str,
        expected_duration_ms: float,
        callback: Optional[Callable] = None
    ):
        """
        报告无响应（触发静默分析通道）

        当操作成功但超过预期时间时调用

        Args:
            component_name: 组件名
            action: 操作描述
            expected_duration_ms: 预期持续时间
            callback: 分析完成回调
        """
        self.report_operation(
            component_name=component_name,
            action=action,
            duration_ms=expected_duration_ms,
            response_status="timeout",
            callback=callback
        )

    def set_error_callback(self, callback: Callable):
        """设置错误分析回调"""
        if callback not in self._error_callbacks:
            self._error_callbacks.append(callback)

    def set_source_callback(self, callback: Callable):
        """设置源码分析回调"""
        if callback not in self._source_callbacks:
            self._source_callbacks.append(callback)

    def add_event_listener(self, listener: Callable):
        """添加事件监听器"""
        if listener not in self._event_listeners:
            self._event_listeners.append(listener)

    def remove_event_listener(self, listener: Callable):
        """移除事件监听器"""
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)

    def _on_error_result(self, result: DiagnosisResult):
        """错误分析结果回调"""
        # 通知所有回调
        for callback in self._error_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Error callback failed: {e}")

        # 发送事件
        event = AnalysisEvent(
            event_type="error",
            timestamp=time.time(),
            component_name=result.error_context.component_name,
            result=result
        )
        self._notify_event_listeners(event)

    def _on_source_result(self, result: SourceAnalysisResult):
        """源码分析结果回调"""
        # 通知所有回调
        for callback in self._source_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Source callback failed: {e}")

        # 发送事件
        event = AnalysisEvent(
            event_type="source",
            timestamp=time.time(),
            component_name=result.context.component_name,
            result=result
        )
        self._notify_event_listeners(event)

    def _notify_event_listeners(self, event: AnalysisEvent):
        """通知事件监听器"""
        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Event listener failed: {e}")

    def get_error_context(
        self,
        error: Exception,
        component_name: str,
        action: str
    ) -> ErrorContext:
        """获取错误上下文（同步）"""
        return self._collector.collect_error_context(
            error=error,
            component_name=component_name,
            action=action,
            level=ContextLevel.STANDARD
        )

    def get_source_snippet(
        self,
        component_name: str,
        line_number: int,
        context_lines: int = 5
    ) -> Optional[str]:
        """获取源码片段"""
        if not self._source_mapper:
            return None

        location = self._source_mapper.get_source_location(component_name)
        if not location:
            return None

        return self._source_mapper.get_source_snippet(
            location.file_path,
            line_number,
            context_lines
        )

    def enable(self):
        """启用引擎"""
        self._enabled = True

    def disable(self):
        """禁用引擎"""
        self._enabled = False

    def enable_error_channel(self):
        """启用错误通道"""
        self._error_channel_enabled = True

    def disable_error_channel(self):
        """禁用错误通道"""
        self._error_channel_enabled = False

    def enable_source_channel(self):
        """启用静默通道"""
        self._source_channel_enabled = True

    def disable_source_channel(self):
        """禁用静默通道"""
        self._source_channel_enabled = False

    def get_stats(self) -> Dict[str, Any]:
        """获取引擎统计"""
        with self._stats_lock:
            cache_stats = self._cache.get_stats()
            queue_stats = self._task_queue.get_stats()

            return {
                "enabled": self._enabled,
                "error_channel": self._error_channel_enabled,
                "source_channel": self._source_channel_enabled,
                "error_analysis_count": self._stats.error_analysis_count,
                "source_analysis_count": self._stats.source_analysis_count,
                "cache_stats": cache_stats,
                "queue_stats": queue_stats,
                "ai_service_stats": self._ai_service.get_stats(),
                "error_callbacks": len(self._error_callbacks),
                "source_callbacks": len(self._source_callbacks),
                "event_listeners": len(self._event_listeners)
            }

    def shutdown(self):
        """关闭引擎"""
        self._enabled = False
        self._task_queue.shutdown()
        logger.info("Engine shutdown")


# 全局单例
engine = IntelligentAnalysisEngine()


# 便捷函数
def init_engine(project_root: str):
    """初始化引擎"""
    engine.initialize(project_root)


def report_error(error: Exception, component_name: str, action: str, **kwargs):
    """报告错误"""
    engine.report_error(error, component_name, action, **kwargs)


def report_operation(component_name: str, action: str, duration_ms: float, **kwargs):
    """报告操作"""
    engine.report_operation(component_name, action, duration_ms, **kwargs)


def report_no_response(component_name: str, action: str, duration_ms: float, **kwargs):
    """报告无响应"""
    engine.report_no_response(component_name, action, duration_ms, **kwargs)
