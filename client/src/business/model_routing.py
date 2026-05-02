"""
ModelRouting — Compatibility Stub
==================================

已迁移至 livingtree.core.model.router.UnifiedModelRouter。

Import redirect:
    Old: from business.model_routing import SmartModelSelector
    New: from livingtree.core.model.router import UnifiedModelRouter
"""

from business.global_model_router import UnifiedModelRouter, ComputeTier


class SmartModelSelector(UnifiedModelRouter):
    pass


class DynamicModelComposer:
    pass


class CostQualityRouter:
    pass


__all__ = ["SmartModelSelector", "DynamicModelComposer", "CostQualityRouter"]
