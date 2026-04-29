"""
LLM Wiki 模块 - Phase 1 & Phase 2 & Phase 3 & Phase 4 (EvoRAG集成版)
================================================

LLM 专用知识库系统，集成到现有 FusionRAG 和 KnowledgeGraph 模块。

功能：
1. LLM 文档解析（Markdown、reStructuredText） - Phase 1
2. 论文 PDF 解析（arXiv） - Phase 1
3. 代码块提取（Python、JavaScript、Bash 等） - Phase 1
4. 集成到现有 FusionRAG 系统 - Phase 1
5. **KnowledgeGraph 集成（章节结构导入） - Phase 2**
6. **KnowledgeGraph 集成（优化版 - 保留完整分块结构） - Phase 2+**
7. **KnowledgeGraph 集成（高级版 - 跨文档引用、实体链接、图谱推理） - Phase 3** ⭐
8. **EvoRAG 集成（反馈驱动、知识图谱自进化、混合优先级检索） - Phase 4** 🚀

作者: LivingTreeAI Team
日期: 2026-04-29
版本: 4.0.0 (Phase 1 + 2 + 2+ + 3 + 4(EvoRAG))
"""

from loguru import logger

# Phase 1: 数据模型和解析器
from .models import DocumentChunk, PaperMetadata
from .parsers import LLMDocumentParser, PaperParser, CodeExtractor

# Phase 1: FusionRAG 集成
from .integration import (
    LLMWikiIntegration,
    create_llm_wiki_integration,
    index_llm_document,
    search_llm_wiki
)

# Phase 2: KnowledgeGraph 集成
from .knowledge_graph_integrator import (
    LLMWikiKnowledgeGraphIntegrator,
    WikiNodeMapping,
    integrate_llm_wiki_to_graph,
    load_and_integrate_markdown
)

# Phase 2+ (优化版): KnowledgeGraph 集成（保留完整分块结构）
from .knowledge_graph_integrator_v2 import (
    LLMWikiKnowledgeGraphIntegratorV2,
    integrate_llm_wiki_to_graph_v2,
    load_and_integrate_markdown_v2
)

# Phase 3 (高级版): KnowledgeGraph 集成（跨文档引用、实体链接、图谱推理）⭐
from .knowledge_graph_integrator_v3 import (
    LLMWikiKnowledgeGraphIntegratorV3,
    integrate_llm_wiki_to_graph_v3,
    load_and_integrate_markdown_v3,
    load_and_integrate_multiple_v3
)

# Phase 4 (EvoRAG集成版): 反馈驱动、知识图谱自进化、混合优先级检索 🚀
from .knowledge_graph_integrator_v4 import (
    LLMWikiKnowledgeGraphIntegratorV4,
    EvoRAGConfig,
    integrate_llm_wiki_to_graph_v4
)
from .feedback_manager import FeedbackManager, FeedbackRecord
from .kg_self_evolver import KnowledgeGraphSelfEvolver
from .hybrid_retriever import HybridRetriever, RetrievalResult


__version__ = "4.0.0"
__author__ = "LivingTreeAI Team"
__module_name__ = "llm_wiki"


__all__ = [
    # 数据模型
    "DocumentChunk",
    "PaperMetadata",
    
    # Phase 1: 解析器
    "LLMDocumentParser",
    "PaperParser",
    "CodeExtractor",
    
    # Phase 1: FusionRAG 集成
    "LLMWikiIntegration",
    "create_llm_wiki_integration",
    "index_llm_document",
    "search_llm_wiki",
    
    # Phase 2: KnowledgeGraph 集成
    "LLMWikiKnowledgeGraphIntegrator",
    "WikiNodeMapping",
    "integrate_llm_wiki_to_graph",
    "load_and_integrate_markdown",
    
    # Phase 2+ (优化版): KnowledgeGraph 集成（保留完整分块结构）
    "LLMWikiKnowledgeGraphIntegratorV2",
    "integrate_llm_wiki_to_graph_v2",
    "load_and_integrate_markdown_v2",
    
    # Phase 3 (高级版): KnowledgeGraph 集成（跨文档引用、实体链接、图谱推理）⭐
    "LLMWikiKnowledgeGraphIntegratorV3",
    "integrate_llm_wiki_to_graph_v3",
    "load_and_integrate_markdown_v3",
    "load_and_integrate_multiple_v3",
    
    # Phase 4 (EvoRAG集成版): 反馈驱动、知识图谱自进化、混合优先级检索 🚀
    "LLMWikiKnowledgeGraphIntegratorV4",
    "EvoRAGConfig",
    "integrate_llm_wiki_to_graph_v4",
    "FeedbackManager",
    "FeedbackRecord",
    "KnowledgeGraphSelfEvolver",
    "HybridRetriever",
    "RetrievalResult"
]


logger.info(f"LLM Wiki 模块 v{__version__} 已加载 (Phase 1 + 2 + 2+ + 3 + 4(EvoRAG))")
