"""
大脑启发记忆系统 - 向后兼容层

⚠️ 已迁移至 livingtree.core.memory.brain_memory
本模块保留为兼容层，所有导入将自动重定向到新位置。
"""

from livingtree.core.memory.brain_memory import (
    Hippocampus, MemoryTrace, MemoryType,
    Neocortex, SemanticNode,
    MemoryConsolidator, ConsolidationStrategy,
    BrainMemoryRouter, get_brain_memory_router,
    query_memory, store_memory,
)

__all__ = [
    'Hippocampus', 'MemoryTrace', 'MemoryType',
    'Neocortex', 'SemanticNode',
    'MemoryConsolidator', 'ConsolidationStrategy',
    'BrainMemoryRouter', 'get_brain_memory_router',
    'query_memory', 'store_memory',
]
