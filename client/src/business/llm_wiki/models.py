"""
LLM Wiki 模块 - 数据模型
==========================

定义 LLM Wiki 模块使用的数据结构。

作者: LivingTreeAI Team
日期: 2026-04-29
版本: 1.0.0 (Phase 1)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class DocumentChunk:
    """文档块数据结构"""
    content: str
    metadata: Dict[str, Any]
    chunk_type: str  # "text", "code", "api", "example", "equation"
    source: str = ""
    title: str = ""
    section: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "content": self.content,
            "metadata": self.metadata,
            "chunk_type": self.chunk_type,
            "source": self.source,
            "title": self.title,
            "section": self.section
        }


@dataclass
class PaperMetadata:
    """论文元数据"""
    arxiv_id: str = ""
    title: str = ""
    authors: List[str] = field(default_factory=list)
    abstract: str = ""
    categories: List[str] = field(default_factory=list)
    published_date: str = ""
    updated_date: str = ""
    references: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "categories": self.categories,
            "published_date": self.published_date,
            "updated_date": self.updated_date,
            "references": self.references
        }
