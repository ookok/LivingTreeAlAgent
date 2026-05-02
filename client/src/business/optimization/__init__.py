"""
优化模块

集成 Entroly 风格的优化功能：
1. PRISM 优化器 - 4维评估体系
2. 0/1 背包上下文选择器
3. 实时监控仪表盘
4. Entraly 综合优化器
"""

from .prism_optimizer import (
    PRISMOptimizer,
    PRISMConfig,
    FragmentManager,
    FragmentMetrics,
    CodeFragment,
    ShannonEntropyCalculator,
    CovarianceMatrixBuilder,
    get_prism_optimizer,
)

from .knapsack_selector import (
    KnapsackContextSelector,
    AdaptiveContextSelector,
    ContextItem,
    SelectionResult,
    get_knapsack_selector,
    get_adaptive_selector,
)

from .realtime_dashboard import (
    RealtimeDashboard,
    MetricsCollector,
    CostCalculator,
    MetricType,
    SessionStats,
    get_dashboard,
)

from .entroly_optimizer import (
    EntralyOptimizer,
    OptimizationConfig as EntralyConfig,
    OptimizationResult as EntralyResult,
    get_entroly_optimizer,
)

from .unified_optimizer import (
    UnifiedOptimizer,
    UnifiedConfig,
    UnifiedOptimizationResult,
    OptimizerType,
    TaskType,
    get_unified_optimizer,
)

__all__ = [
    # PRISM
    "PRISMOptimizer",
    "PRISMConfig",
    "FragmentManager",
    "FragmentMetrics",
    "CodeFragment",
    "ShannonEntropyCalculator",
    "CovarianceMatrixBuilder",
    "get_prism_optimizer",

    # Knapsack
    "KnapsackContextSelector",
    "AdaptiveContextSelector",
    "ContextItem",
    "SelectionResult",
    "get_knapsack_selector",
    "get_adaptive_selector",

    # Dashboard
    "RealtimeDashboard",
    "MetricsCollector",
    "CostCalculator",
    "MetricType",
    "SessionStats",
    "get_dashboard",

    # Entraly
    "EntralyOptimizer",
    "EntralyConfig",
    "EntralyResult",
    "get_entroly_optimizer",

    # Unified
    "UnifiedOptimizer",
    "UnifiedConfig",
    "UnifiedOptimizationResult",
    "OptimizerType",
    "TaskType",
    "get_unified_optimizer",
]
