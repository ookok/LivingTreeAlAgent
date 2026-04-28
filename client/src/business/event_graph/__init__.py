"""
Event Graph Module - 事件图谱模块

实现"以史为鉴"能力：
- 构建事件图谱（主体-事件-结果）
- 扫描图谱，归纳因果规则
- 验证规则的置信度

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from .event_node import (
    EventGraph,
    EventNode,
    EventType,
    CausalLink,
    CausalRule,
    CausalConfidence,
    event_graph,
    get_event_graph
)

__all__ = [
    "EventGraph",
    "EventNode",
    "EventType",
    "CausalLink",
    "CausalRule",
    "CausalConfidence",
    "event_graph",
    "get_event_graph"
]