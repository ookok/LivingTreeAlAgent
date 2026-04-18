"""
知识库插件

功能：
- 文档管理、检索、标注、关联
- 知识图谱可视化
- 标签管理

视图模式：标签页（Tabbed）- 适合深度编辑
"""

from .knowledge_base_plugin import KnowledgeBasePlugin

__all__ = ['KnowledgeBasePlugin']