"""
SmartAIRouter — Compatibility Stub
====================================

已迁移至 livingtree.core.model.router。
三层算力池路由（Local/Edge/Cloud）的完整实现在 UnifiedModelRouter 中。
"""

from business.global_model_router import (
    UnifiedModelRouter as SmartAIRouter,
    ComputeTier,
    CostBudget,
    AIResponse,
    get_model_router,
)

__all__ = ["SmartAIRouter", "ComputeTier", "CostBudget", "AIResponse", "get_model_router"]
