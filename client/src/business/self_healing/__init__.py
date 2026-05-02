"""
自修复容错系统 - 向后兼容层

⚠️ 已迁移至 livingtree.core.self_healing
本模块保留为兼容层，所有导入将自动重定向到新位置。
"""

from livingtree.core.self_healing import *

__all__ = [
    'HealthMonitor', 'HealthMetric', 'MetricType', 'MetricStatus',
    'ProblemDetector', 'ProblemReport', 'ProblemSeverity', 'ProblemCategory',
    'RepairEngine', 'RepairResult', 'RepairStatus',
    'RestartStrategy', 'CheckpointRestoreStrategy',
    'FallbackStrategy', 'ParameterOptimizationStrategy', 'RollbackStrategy',
    'HealingRouter', 'get_healing_router',
    'get_system_health', 'trigger_repair',
]
