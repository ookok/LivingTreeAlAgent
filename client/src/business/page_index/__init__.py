"""
PageIndex - 结构化文档索引系统

基于 Andrej Karpathy 的 LLM Wiki 架构，提供:
1. 文档自动分块
2. B-tree 风格索引树
3. 按目录翻书式精确定位
4. Hermes Agent Tool 集成

核心流程:
1. Ingest: 文档 → Chunks → 索引树
2. Query: 问题 → 树遍历 → 目标 Chunks
3. Answer: 上下文 + LLM → 精确答案

使用示例:
    from client.src.business.page_index import get_pageindex_tool

    tool = get_pageindex_tool()

    # 首次: 构建索引
    tool.build_index("manual.pdf", "api_doc")

    # 查询
    result = await tool.query_and_answer(
        "如何配置认证？",
        "api_doc"
    )
    print(result["answer"])
"""

from .models import (
    Chunk,
    ChunkType,
    DocumentLoaderResult,
    DocumentType,
    IndexedDocument,
    IndexNode,
    IndexStats,
    QueryResponse,
    QueryResult,
)
from .document_loader import DocumentLoader
from .index_builder import PageIndexBuilder
from .query_engine import QueryEngine
from .hermes_tool import (
    PageIndexTool,
    get_pageindex_tool,
    register_pageindex_tools,
)
from .ui.panel import PageIndexPanel

__all__ = [
    # 核心类
    "PageIndexBuilder",
    "QueryEngine",
    "PageIndexTool",
    # 数据模型
    "Chunk",
    "ChunkType",
    "DocumentType",
    "DocumentLoaderResult",
    "IndexedDocument",
    "IndexNode",
    "IndexStats",
    "QueryResult",
    "QueryResponse",
    # 工具函数
    "DocumentLoader",
    "get_pageindex_tool",
    "register_pageindex_tools",
    # UI
    "PageIndexPanel",
]

__version__ = "1.0.0"
