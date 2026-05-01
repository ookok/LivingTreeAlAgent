"""
大脑启发记忆系统 (Brain-Inspired Memory System)

核心能力：
1. 海马体编码 - 快速记忆编码和线索检索
2. 新皮层存储 - 长期语义记忆和知识图谱
3. 记忆巩固 - Hebbian学习和睡眠模拟

三层记忆模型：
- 短期记忆 (< 1小时) - 海马体
- 中期记忆 (1小时~30天) - 向量检索
- 长期记忆 (> 30天) - 新皮层/知识图谱
"""

from .hippocampus import Hippocampus, MemoryTrace, MemoryType
from .neocortex import Neocortex, SemanticNode
from .memory_consolidation import MemoryConsolidator, ConsolidationStrategy
from .memory_router import BrainMemoryRouter, get_brain_memory_router

__all__ = [
    # 海马体
    'Hippocampus',
    'MemoryTrace',
    'MemoryType',
    
    # 新皮层
    'Neocortex',
    'SemanticNode',
    
    # 记忆巩固
    'MemoryConsolidator',
    'ConsolidationStrategy',
    
    # 记忆路由
    'BrainMemoryRouter',
    'get_brain_memory_router',
]


def query_memory(query: str, context: dict = None) -> dict:
    """
    统一记忆查询接口
    
    Args:
        query: 查询内容
        context: 上下文信息
    
    Returns:
        查询结果字典
    """
    router = get_brain_memory_router()
    return router.query(query, context or {})


def store_memory(content: str, memory_type: str = "short_term", **kwargs) -> str:
    """
    统一记忆存储接口
    
    Args:
        content: 要存储的内容
        memory_type: 记忆类型 (short_term/mid_term/long_term)
        **kwargs: 额外参数
    
    Returns:
        存储的ID
    """
    router = get_brain_memory_router()
    return router.store(content, memory_type, **kwargs)