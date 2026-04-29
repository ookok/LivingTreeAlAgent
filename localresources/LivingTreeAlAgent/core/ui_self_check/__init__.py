"""
AI驱动式界面自检与优化系统 - Intelligent UI Self-Check System

双模态智能分析引擎：
1. ReactiveErrorAnalyzer - 反应式错误分析通道（救火队）
2. ProactiveSourceAnalyzer - 主动式静默分析通道（巡检员）

核心特性：
- 非侵入式、低功耗
- 分级处理与异步化
- 双通道互不阻塞
- 智能缓存与防抖
"""

from .context_collector import (
    ContextCollector, ErrorContext, SilentContext, ContextLevel
)
from .analysis_cache import AnalysisCache, CachedAnalysis
from .async_task_queue import AsyncTaskQueue, TaskPriority, Debouncer
from .reactive_error_analyzer import (
    ReactiveErrorAnalyzer, DiagnosisResult, ErrorSeverity, ErrorPattern
)
from .proactive_source_analyzer import (
    ProactiveSourceAnalyzer, SourceAnalysisResult, SourceIssue, IssueSeverity
)
from .ai_diagnosis_service import AIDiagnosisService, AIDiagnosisResult
from .source_mapper import SourceMapper, SourceLocation
from .intelligent_analysis_engine import (
    IntelligentAnalysisEngine, EngineStats, AnalysisEvent, engine
)

__all__ = [
    # 核心组件
    'ContextCollector',
    'ErrorContext',
    'SilentContext',
    'ContextLevel',
    'AnalysisCache',
    'CachedAnalysis',
    'AsyncTaskQueue',
    'TaskPriority',
    'Debouncer',
    'ReactiveErrorAnalyzer',
    'DiagnosisResult',
    'ErrorSeverity',
    'ErrorPattern',
    'ProactiveSourceAnalyzer',
    'SourceAnalysisResult',
    'SourceIssue',
    'IssueSeverity',
    'AIDiagnosisService',
    'AIDiagnosisResult',
    'SourceMapper',
    'SourceLocation',
    'IntelligentAnalysisEngine',
    'EngineStats',
    'AnalysisEvent',
    'engine',
]

# 全局引擎实例
default_engine = engine
