"""
RAG-Anything 集成模块

参考 RAG-Anything 框架，实现：
- 多模态文档解析
- 跨模态知识图谱
- VLM 增强查询

增强本项目的 KnowledgeGraph 模块
"""

from .multimodal_parser import (
    ContentType,
    TextContent,
    ImageContent,
    TableContent,
    EquationContent,
    MultimodalContent,
    TextParser,
    ImageParser,
    TableParser,
    EquationParser,
    MultimodalDocumentParser,
)

from .cross_modal_kg import (
    EntityType,
    RelationType,
    Entity,
    Relation,
    CrossModalLink,
    CrossModalKnowledgeGraph,
    CrossModalGraphBuilder,
)

from .vlm_query import (
    QueryType,
    QueryContext,
    VLMQueryResult,
    QueryAnalyzer,
    ContextBuilder,
    VLMQueryProcessor,
    MultimodalRAGPipeline,
)

__all__ = [
    # 多模态解析
    "ContentType",
    "TextContent",
    "ImageContent",
    "TableContent",
    "EquationContent",
    "MultimodalContent",
    "TextParser",
    "ImageParser",
    "TableParser",
    "EquationParser",
    "MultimodalDocumentParser",
    # 跨模态知识图谱
    "EntityType",
    "RelationType",
    "Entity",
    "Relation",
    "CrossModalLink",
    "CrossModalKnowledgeGraph",
    "CrossModalGraphBuilder",
    # VLM 查询
    "QueryType",
    "QueryContext",
    "VLMQueryResult",
    "QueryAnalyzer",
    "ContextBuilder",
    "VLMQueryProcessor",
    "MultimodalRAGPipeline",
]
