"""
知识图谱模块 - 向后兼容层

⚠️ 已迁移至 livingtree.core.knowledge.graph
本模块保留为兼容层，所有导入将自动重定向到新位置。
"""

from livingtree.core.knowledge.graph import *

__all__ = [
    'KnowledgeGraph', 'KnowledgeNode', 'KnowledgeRelation', 'KnowledgeBase',
    'ConceptNode', 'MarkdownExporter', 'ModelIndependentExporter',
]
