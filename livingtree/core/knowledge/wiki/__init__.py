"""
LivingTree Knowledge Wiki 模块
==============================

LLM 专用知识库系统，从 client/src/business/llm_wiki/ 迁移而来。

功能：
1. 文档解析（Markdown、reStructuredText、PDF）
2. 代码块提取
3. EvoRAG 反馈管理系统
4. 知识图谱自进化引擎
5. 混合优先级检索器
"""

from .models import DocumentChunk, PaperMetadata
from .parsers import LLMDocumentParser, PaperParser, CodeExtractor
from .feedback_manager import FeedbackManager, FeedbackRecord, TripletScore
from .kg_self_evolver import KnowledgeGraphSelfEvolver, ShortcutEdge
from .hybrid_retriever import HybridRetriever, RetrievalResult

__version__ = "1.0.0"
__author__ = "LivingTreeAI Team"

__all__ = [
    "DocumentChunk", "PaperMetadata",
    "LLMDocumentParser", "PaperParser", "CodeExtractor",
    "FeedbackManager", "FeedbackRecord", "TripletScore",
    "KnowledgeGraphSelfEvolver", "ShortcutEdge",
    "HybridRetriever", "RetrievalResult",
]
