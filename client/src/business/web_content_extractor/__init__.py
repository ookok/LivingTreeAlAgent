"""
Web Content Extractor - 网页内容提取模块

使用 Jina AI Reader API 将网页内容转换为 LLM 友好的结构化文本。
可集成到 Deep Search、FusionRAG 等模块中。

用法：
    from client.src.business.web_content_extractor import extract_content
    
    # 快速提取
    content = await extract_content("https://example.com")
    
    # 使用 Jina Reader（推荐）
    from client.src.business.web_content_extractor import JinaReader
    reader = JinaReader()
    content = await reader.extract("https://example.com")
"""

from .jina_reader import JinaReader
from .extractor import (
    extract_content,
    batch_extract,
    ContentExtractor,
)

__all__ = [
    "JinaReader",
    "extract_content",
    "batch_extract",
    "ContentExtractor",
]
