"""
PageIndex 数据模型
Structured Document Indexing for Hermes

核心概念:
- IndexedDocument: 已索引的文档
- IndexNode: 索引树节点
- Chunk: 文本片段
- QueryResult: 查询结果
"""

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DocumentType(Enum):
    """支持的文档类型"""
    PDF = "pdf"
    HTML = "html"
    TXT = "txt"
    MARKDOWN = "markdown"
    DOCX = "docx"
    UNKNOWN = "unknown"


class ChunkType(Enum):
    """chunk 类型"""
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    CODE = "code"
    LIST = "list"


@dataclass
class Chunk:
    """文本片段"""
    chunk_id: str
    text: str
    chunk_type: ChunkType
    page_num: int
    position: int  # 在文档中的字符位置
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.chunk_type, str):
            self.chunk_type = ChunkType(self.chunk_type)
        if not self.chunk_id:
            self.chunk_id = self._generate_id()

    def _generate_id(self) -> str:
        content = f"{self.text[:100]}{self.page_num}{self.position}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "chunk_type": self.chunk_type.value,
            "page_num": self.page_num,
            "position": self.position,
            "metadata": self.metadata
        }


@dataclass
class IndexNode:
    """索引树节点 (B-tree 风格)"""
    node_id: str
    level: int  # 树层级 (0 = root)
    summary: str  # 本节点摘要
    chunk_ids: list[str] = field(default_factory=list)  # 包含的 chunk IDs
    children: list[str] = field(default_factory=list)  # 子节点 IDs
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.node_id:
            self.node_id = hashlib.md5(
                f"{self.summary}{self.level}{time.time()}".encode()
            ).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "level": self.level,
            "summary": self.summary,
            "chunk_ids": self.chunk_ids,
            "children": self.children,
            "metadata": self.metadata
        }


@dataclass
class IndexedDocument:
    """已索引的文档"""
    doc_id: str
    title: str
    file_path: str
    doc_type: DocumentType
    total_pages: int
    total_chunks: int
    tree_height: int
    root_node_id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    # 内存中的数据 (不持久化)
    _chunks: dict = field(default_factory=dict, repr=False)
    _nodes: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        if isinstance(self.doc_type, str):
            self.doc_type = DocumentType(self.doc_type)

    def add_chunk(self, chunk: Chunk):
        self._chunks[chunk.chunk_id] = chunk
        self.total_chunks = len(self._chunks)

    def add_node(self, node: IndexNode):
        self._nodes[node.node_id] = node

    def get_chunk(self, chunk_id: str) -> Chunk:
        return self._chunks.get(chunk_id)

    def get_node(self, node_id: str) -> IndexNode:
        return self._nodes.get(node_id)

    def get_chunks_by_ids(self, chunk_ids: list[str]) -> list[Chunk]:
        return [self._chunks[cid] for cid in chunk_ids if cid in self._chunks]

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "file_path": self.file_path,
            "doc_type": self.doc_type.value,
            "total_pages": self.total_pages,
            "total_chunks": self.total_chunks,
            "tree_height": self.tree_height,
            "root_node_id": self.root_node_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata
        }


@dataclass
class QueryResult:
    """查询结果"""
    chunk_id: str
    text: str
    page_num: int
    score: float  # 相关性得分
    section_title: str = ""
    section_path: list[str] = field(default_factory=list)  # 从根到当前节点的路径

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "page_num": self.page_num,
            "score": self.score,
            "section_title": self.section_title,
            "section_path": self.section_path
        }


@dataclass
class QueryResponse:
    """完整查询响应"""
    query: str
    results: list[QueryResult]
    context: str  # 拼接的上下文
    total_found: int
    response_time_ms: float

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "context": self.context,
            "total_found": self.total_found,
            "response_time_ms": self.response_time_ms
        }


@dataclass
class DocumentLoaderResult:
    """文档加载结果"""
    content: str
    doc_type: DocumentType
    metadata: dict

    def __post_init__(self):
        if isinstance(self.doc_type, str):
            self.doc_type = DocumentType(self.doc_type)


class IndexStats:
    """索引统计"""

    def __init__(self):
        self.total_documents = 0
        self.total_chunks = 0
        self.total_nodes = 0
        self.last_build_time = 0
        self.avg_query_time_ms = 0
        self.query_count = 0

    def to_dict(self) -> dict:
        return {
            "total_documents": self.total_documents,
            "total_chunks": self.total_chunks,
            "total_nodes": self.total_nodes,
            "last_build_time": self.last_build_time,
            "avg_query_time_ms": self.avg_query_time_ms,
            "query_count": self.query_count
        }
