"""
自修复容错系统 (Self-Healing Fault Tolerance System)

核心能力：
1. 预测性监控 - 实时监控系统健康指标
2. 问题检测 - 自动发现异常和潜在问题
3. 修复策略 - 多种恢复策略支持
4. 健康管理 - 综合健康状态评估
"""

from .health_monitor import HealthMonitor, HealthMetric, MetricType, MetricStatus
from .problem_detector import ProblemDetector, ProblemReport, ProblemSeverity, ProblemCategory
from .repair_engine import RepairEngine, RepairResult, RepairStatus
from .recovery_strategies import (
    RestartStrategy, CheckpointRestoreStrategy,
    FallbackStrategy, ParameterOptimizationStrategy, RollbackStrategy,
)
from .healing_router import HealingRouter, get_healing_router

__all__ = [
    'HealthMonitor', 'HealthMetric', 'MetricType', 'MetricStatus',
    'ProblemDetector', 'ProblemReport', 'ProblemSeverity', 'ProblemCategory',
    'RepairEngine', 'RepairResult', 'RepairStatus',
    'RestartStrategy', 'CheckpointRestoreStrategy',
    'FallbackStrategy', 'ParameterOptimizationStrategy', 'RollbackStrategy',
    'HealingRouter', 'get_healing_router',
]


def get_system_health() -> dict:
    router = get_healing_router()
    return router.get_health_status()


def trigger_repair(component: str, issue: str = None) -> dict:
    router = get_healing_router()
    return router.trigger_repair(component, issue)
