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
6. KG 整合器（实体链接 + 跨文档引用 + EvoRAG 反馈进化）
7. 外部系统集成桥接（FusionRAG / VimRAG / DeepKE-LLM）
"""

from .models import DocumentChunk, PaperMetadata
from .parsers import LLMDocumentParser, PaperParser, CodeExtractor
from .feedback_manager import FeedbackManager, FeedbackRecord, TripletScore
from .kg_self_evolver import KnowledgeGraphSelfEvolver, ShortcutEdge
from .hybrid_retriever import HybridRetriever, RetrievalResult
from .kg_integrator import (
    WikiKGIntegrator,
    IntegratorConfig,
    ChunkNodeMapping,
    EntityExtractor,
    RegexEntityExtractor,
    create_wiki_kg_integrator,
)
from .wiki_core import WikiCore, WikiPage, PageRevision, get_wiki_core

__version__ = "2.0.0"
__author__ = "LivingTreeAI Team"

__all__ = [
    # 数据模型
    "DocumentChunk", "PaperMetadata",
    # 解析器
    "LLMDocumentParser", "PaperParser", "CodeExtractor",
    # EvoRAG
    "FeedbackManager", "FeedbackRecord", "TripletScore",
    "KnowledgeGraphSelfEvolver", "ShortcutEdge",
    "HybridRetriever", "RetrievalResult",
    # Wiki 核心
    "WikiCore", "WikiPage", "PageRevision", "get_wiki_core",
    # KG 整合器 (V5 合并增强版)
    "WikiKGIntegrator", "IntegratorConfig", "ChunkNodeMapping",
    "EntityExtractor", "RegexEntityExtractor",
    "create_wiki_kg_integrator",
]
