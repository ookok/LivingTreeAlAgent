"""
OpenCode Integration Package
============================

提供 OpenCode CLI 和 oh-my-opencode 插件的集成功能。

Usage:
    from libs.opencode_integration import get_integration, quick_setup
    
    # 快速设置
    quick_setup()
    
    # 获取集成实例
    integration = get_integration()
    info = integration.get_info()
"""

from .opencode_manager import (
    OpenCodeIntegration,
    OpenCodeCLI,
    OhMyOpenCodeManager,
    EmbeddedRepoSync,
    OpenCodeConfig,
    OpenCodeStatus,
    OpenCodeStatusInfo,
    PluginInfo,
    get_integration,
    quick_setup,
)

__all__ = [
    "OpenCodeIntegration",
    "OpenCodeCLI",
    "OhMyOpenCodeManager", 
    "EmbeddedRepoSync",
    "OpenCodeConfig",
    "OpenCodeStatus",
    "OpenCodeStatusInfo",
    "PluginInfo",
    "get_integration",
    "quick_setup",
]
