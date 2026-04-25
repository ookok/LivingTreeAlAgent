"""
ProgressiveUnderstanding 集成模块
============================

提供与 Agent Chat、知识库、深度搜索、技能进化的深度集成。
"""

from .unified_agent import (
    # 集成配置
    IntegrationMode,
    IntegrationConfig,

    # 集成结果
    IntegratedResult,

    # 统一智能体
    UnifiedAgent,

    # 工厂函数
    create_unified_agent,
)

__all__ = [
    # 配置
    "IntegrationMode",
    "IntegrationConfig",

    # 结果
    "IntegratedResult",

    # 智能体
    "UnifiedAgent",

    # 工厂
    "create_unified_agent",
]
