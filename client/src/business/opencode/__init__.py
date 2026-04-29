"""
OpenCode 模块 - LivingTree AI Agent 集成
========================================

提供与 OpenCode CLI 和 oh-my-opencode 插件的深度集成。

子模块:
- opencode_bridge: 核心桥接器
"""

from .opencode_bridge import (
    OpenCodeBridge,
    OpenCodeCLIWrapper,
    OpenCodePluginManager,
    EmbeddedRepoSyncer,
    OpenCodeMode,
    OpenCodeSession,
    OpenCodeMessage,
    get_bridge,
    quick_setup,
)

__all__ = [
    "OpenCodeBridge",
    "OpenCodeCLIWrapper",
    "OpenCodePluginManager",
    "EmbeddedRepoSyncer",
    "OpenCodeMode",
    "OpenCodeSession",
    "OpenCodeMessage",
    "get_bridge",
    "quick_setup",
]
