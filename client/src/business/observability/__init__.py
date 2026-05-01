"""
可观测性模块

提供任务链的完整可观测性支持，包括：
- 分布式追踪系统
- 指标收集系统
- 结构化日志系统
- 统一观察者接口
- 告警系统

核心组件：
1. Tracer - 分布式追踪，记录任务链执行路径
2. MetricsSystem - 指标收集，统计关键性能指标
3. LoggerSystem - 结构化日志，记录执行日志
4. Observer - 观察者管理器，整合以上所有组件
"""

from .trace_system import (
    Tracer,
    Span,
    Trace,
    SpanKind,
    SpanStatus,
    get_tracer
)

from .metrics_system import (
    MetricsSystem,
    Counter,
    Gauge,
    Histogram,
    Summary,
    get_metrics_system
)

from .logger_system import (
    LoggerSystem,
    LogRecord,
    LogLevel,
    get_logger
)

from .observer import (
    Observer,
    Alert,
    AlertLevel,
    get_observer
)

from .dashboard import (
    ObservabilityDashboard,
    MetricCard,
    TraceNode,
    get_dashboard
)

__all__ = [
    # 追踪系统
    'Tracer',
    'Span',
    'Trace',
    'SpanKind',
    'SpanStatus',
    'get_tracer',
    
    # 指标系统
    'MetricsSystem',
    'Counter',
    'Gauge',
    'Histogram',
    'Summary',
    'get_metrics_system',
    
    # 日志系统
    'LoggerSystem',
    'LogRecord',
    'LogLevel',
    'get_logger',
    
    # 观察者
    'Observer',
    'Alert',
    'AlertLevel',
    'get_observer',
    
    # 仪表盘
    'ObservabilityDashboard',
    'MetricCard',
    'TraceNode',
    'get_dashboard'
]