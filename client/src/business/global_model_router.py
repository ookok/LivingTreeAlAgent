"""
GlobalModelRouter — Compatibility Shim
=======================================

This module has been migrated to livingtree.core.model.router.
Importing from here will redirect to the new location.

Migration:
    Old: from business.global_model_router import GlobalModelRouter, ModelCapability
    New: from livingtree.core.model.router import UnifiedModelRouter, ComputeTier as ModelCapability
"""

import sys
import os

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from livingtree.core.model.router import (
    UnifiedModelRouter,
    UnifiedModelClient,
    ModelRegistry,
    ModelInfo,
    ComputeTier,
    TaskCategory,
    AIResponse,
    CostBudget,
    TierEndpoint,
    get_model_router,
    get_model_client,
)


class GlobalModelRouter(UnifiedModelRouter):
    pass


class ModelCapability:
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"
    LOCAL = "local"
    EDGE = "edge"
    CLOUD = "cloud"
    SPECIAL = "special"


def get_global_router() -> UnifiedModelRouter:
    return get_model_router()


def call_model_sync(prompt: str, model: str = "",
                    temperature: float = 0.7, max_tokens: int = 2048,
                    capability: str = None) -> str:
    client = get_model_client()
    response = client.chat_sync(prompt, model, temperature, max_tokens)
    return response.content


def get_model_router():
    return get_global_router()


__all__ = [
    "GlobalModelRouter",
    "UnifiedModelRouter",
    "ModelCapability",
    "get_global_router",
    "call_model_sync",
    "get_model_router",
    "get_model_client",
    "AIResponse",
    "CostBudget",
    "ComputeTier",
    "TierEndpoint",
]
