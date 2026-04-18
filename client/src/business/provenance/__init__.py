# =================================================================
# 溯源体系 - Provenance System
# =================================================================
# "让每一段知识、每一件商品、每一项服务，都能讲出它的前世今生"
#
# 三层溯源架构：
# 1. 数据指纹层 - SHA256 哈希，防篡改
# 2. 事件日志层 - Event Sourcing，行为追踪
# 3. 图谱关系层 - 时序关系，全链路可视化
#
# 核心模块：
# - content_hasher: 数据指纹层
# - event_logger: 事件日志层
# - traceable_node: 可溯源节点
# - provenance_graph: 图谱关系层
# - report_generator: 溯源报告生成
# =================================================================

from .content_hasher import ContentHasher, HashType, HashResult
from .event_logger import EventLogger, ProvenanceEvent, EventType
from .traceable_node import (
    TraceableNode,
    NodeType,
    NodeVersion,
    ProvenanceChain,
)
from .provenance_graph import ProvenanceGraph, GraphQuery, RelationType
from .report_generator import ProvenanceReport, ReportTemplate

__all__ = [
    # ContentHasher
    'ContentHasher',
    'HashType',
    'HashResult',

    # EventLogger
    'EventLogger',
    'ProvenanceEvent',
    'EventType',

    # TraceableNode
    'TraceableNode',
    'NodeType',
    'NodeVersion',
    'ProvenanceChain',

    # ProvenanceGraph
    'ProvenanceGraph',
    'GraphQuery',
    'RelationType',

    # ReportGenerator
    'ProvenanceReport',
    'ReportTemplate',
]
