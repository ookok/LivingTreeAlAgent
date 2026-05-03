"""
Legacy shim — 重定向到 livingtree.core.model.enhanced_router

EnhancedModelRouter 已迁移至 livingtree/core/model/enhanced_router.py
"""

from livingtree.core.model.enhanced_router import (  # noqa: F401, E402
    EnhancedModelRouter,
    EnhancedResponse,
    RoutingStrategy,
    ModelCapability,
    get_enhanced_model_router,
    call_model,
)

__all__ = [
    "EnhancedModelRouter",
    "EnhancedResponse",
    "RoutingStrategy",
    "ModelCapability",
    "get_enhanced_model_router",
    "call_model",
]
