"""
Base Agents 模块 (base_agents)
==============================

统一智能体架构的基础组件，提供工具层集成能力。

包结构：
- base_agent.py      : BaseToolAgent 基类，统一工具层集成
- hermes_agent.py    : HermesToolAgent，通用智能体工具层特化
- ei_agent.py        : EIToolAgent，环评专家智能体工具层特化

注意：模块名 base_agents（区别于 agent/ 目录）
"""

from client.src.business.base_agents.base_agent import (
    BaseToolAgent,
    ToolCallResult,
    create_base_agent,
)

from client.src.business.base_agents.hermes_agent import (
    HermesToolAgent,
    create_hermes_tool_agent,
    get_hermes_tool_descriptions,
)

from client.src.business.base_agents.ei_agent import (
    EIToolAgent,
    create_ei_tool_agent,
    get_ei_tool_descriptions,
    EI_TOOLSETS,
)

__all__ = [
    # 基类
    "BaseToolAgent",
    "ToolCallResult",
    "create_base_agent",
    # HermesAgent
    "HermesToolAgent",
    "create_hermes_tool_agent",
    "get_hermes_tool_descriptions",
    # EIAgent
    "EIToolAgent",
    "create_ei_tool_agent",
    "get_ei_tool_descriptions",
    "EI_TOOLSETS",
]
