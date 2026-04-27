# -*- coding: utf-8 -*-
"""
Adaptive Quality Assurance Module - 自适应质量保障模块
====================================================

提供动态质量感知 + 智能模型升级 + 成本优化的完整解决方案。

核心组件：
1. EnhancedQualityEvaluator - 增强型质量评估器
2. UpgradeDecisionEngine - 智能升级决策引擎
3. AdaptiveQualitySystem - 自适应质量保障系统

使用示例：
```python
from client.src.business.adaptive_quality import (
    AdaptiveQualitySystem,
    EnhancedQualityEvaluator,
    UpgradeDecisionEngine,
    QualityLevel,
    quick_execute,
)

# 方式1：完整系统
system = AdaptiveQualitySystem()
result = await system.execute(
    query="解释量子计算",
    task_func=lambda level: ollama.chat(prompts, model=f"qwen3.5:{levels[level]}")
)

# 方式2：快速评估
score, needs_upgrade, suggested_level = quick_evaluate(response, query)

# 方式3：单独使用评估器
evaluator = EnhancedQualityEvaluator()
report = evaluator.evaluate(response, query)
print(f"质量评分: {report.overall_score}")
print(f"维度详情: {report.dimensions_summary}")
```

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

from __future__ import annotations

# 版本信息
__version__ = "1.0.0"
__author__ = "LivingTreeAI Agent"

# ═══════════════════════════════════════════════════════════════════════════════
# 导出主要组件
# ═══════════════════════════════════════════════════════════════════════════════

# 增强型质量评估器
try:
    from .enhanced_evaluator import (
        EnhancedQualityEvaluator,
        QualityLevel,
        QualityDimension,
        QualityReport,
        DimensionScore,
        get_enhanced_evaluator,
        quick_evaluate,
    )
except ImportError as e:
    # 备用导入（相对路径失败时）
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from enhanced_evaluator import (
            EnhancedQualityEvaluator,
            QualityLevel,
            QualityDimension,
            QualityReport,
            DimensionScore,
            get_enhanced_evaluator,
            quick_evaluate,
        )
    except ImportError:
        raise ImportError(f"无法导入 enhanced_evaluator: {e}")

# 升级决策引擎
try:
    from .upgrade_engine import (
        UpgradeDecisionEngine,
        UpgradeStrategy,
        UpgradeReason,
        EnhancementProcessor,
        get_upgrade_engine,
        quick_decide,
    )
except ImportError:
    try:
        from upgrade_engine import (
            UpgradeDecisionEngine,
            UpgradeStrategy,
            UpgradeReason,
            EnhancementProcessor,
            get_upgrade_engine,
            quick_decide,
        )
    except ImportError:
        pass

# 自适应质量保障系统
try:
    from .adaptive_quality_system import (
        AdaptiveQualitySystem,
        SyncAdaptiveQualitySystem,
        ModelConfig,
        QualityBudget,
        ExecutionResult,
        get_adaptive_system,
        quick_execute,
    )
except ImportError:
    try:
        from adaptive_quality_system import (
            AdaptiveQualitySystem,
            SyncAdaptiveQualitySystem,
            ModelConfig,
            QualityBudget,
            ExecutionResult,
            get_adaptive_system,
            quick_execute,
        )
    except ImportError:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# 模块元数据
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # 版本
    "__version__",
    "__author__",
    
    # 评估器
    "EnhancedQualityEvaluator",
    "QualityLevel",
    "QualityDimension",
    "QualityReport",
    "DimensionScore",
    "get_enhanced_evaluator",
    "quick_evaluate",
    
    # 升级引擎
    "UpgradeDecisionEngine",
    "UpgradeStrategy",
    "UpgradeReason",
    "EnhancementProcessor",
    "get_upgrade_engine",
    "quick_decide",
    
    # 自适应系统
    "AdaptiveQualitySystem",
    "SyncAdaptiveQualitySystem",
    "ModelConfig",
    "QualityBudget",
    "ExecutionResult",
    "get_adaptive_system",
    "quick_execute",
]
