"""
自修复容错系统 (Self-Healing Fault Tolerance System)

核心能力：
1. 预测性监控 - 实时监控系统健康指标
2. 问题检测 - 自动发现异常和潜在问题
3. 修复策略 - 多种恢复策略支持
4. 健康管理 - 综合健康状态评估

健康指标体系：
- 性能指标：CPU/内存/IO/网络
- 业务指标：请求成功率/延迟/吞吐量
- 组件健康：各模块状态监控
"""

from .health_monitor import HealthMonitor, HealthMetric, MetricType, MetricStatus
from .problem_detector import ProblemDetector, ProblemReport, ProblemSeverity, ProblemCategory
from .repair_engine import RepairEngine, RepairStrategy, RepairResult
from .recovery_strategies import (
    RestartStrategy,
    CheckpointRestoreStrategy,
    FallbackStrategy,
    ParameterOptimizationStrategy,
    RollbackStrategy
)
from .healing_router import HealingRouter, get_healing_router

__all__ = [
    # 健康监控
    'HealthMonitor',
    'HealthMetric',
    'MetricType',
    'MetricStatus',
    
    # 问题检测
    'ProblemDetector',
    'ProblemReport',
    'ProblemSeverity',
    'ProblemCategory',
    
    # 修复引擎
    'RepairEngine',
    'RepairStrategy',
    'RepairResult',
    
    # 恢复策略
    'RestartStrategy',
    'CheckpointRestoreStrategy',
    'FallbackStrategy',
    'ParameterOptimizationStrategy',
    'RollbackStrategy',
    
    # 自愈路由器
    'HealingRouter',
    'get_healing_router',
]


def get_system_health() -> dict:
    """获取系统健康状态"""
    router = get_healing_router()
    return router.get_health_status()


def trigger_repair(component: str, issue: str = None) -> dict:
    """触发修复"""
    router = get_healing_router()
    return router.trigger_repair(component, issue)