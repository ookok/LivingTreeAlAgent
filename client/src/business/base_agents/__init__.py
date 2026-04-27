"""
Base Agents 模块 (base_agents)
==============================

统一智能体架构的基础组件，提供工具层集成能力。

包结构：
- base_agent.py  : BaseToolAgent 基类，统一工具层集成
- hermes_agent.py : HermesAgent（工具层改造）
- ei_agent.py     : EIAgent（工具层改造）

注意：模块名 base_agents（区别于 agent/ 目录）
"""

from client.src.business.base_agents.base_agent import (
    BaseToolAgent,
    ToolCallResult,
    create_base_agent,
)

__all__ = [
    "BaseToolAgent",
    "ToolCallResult",
    "create_base_agent",
]
