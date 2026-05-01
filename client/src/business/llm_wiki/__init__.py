"""
LLM Wiki 模块 - Phase 1 & Phase 2 & Phase 3 & Phase 4 (EvoRAG集成版) + Phase 5 (功能对等版) + Phase 6 (智能向量存储) + Phase 7 (重构版)
=====================================================================================================================================

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
9. **FusionRAG 功能对等（行业治理、分层检索、三重链验证） - Phase 5** ✨
10. **智能向量存储集成（混合模式、自动降级、免配置） - Phase 6** 🎯
11. **重构版（Wiki Core + 智能编辑器 + 实体探索器 + 时间线 + 推荐引擎 + RAG桥接） - Phase 7** 🌟

FusionRAG 功能对等：
- 行业治理（数据准入、元数据tagging、术语归一化）
- 动态知识分层（L1/L2/L3三层架构）
- 行业过滤器（领域过滤、重排序、查询改写）
- 多维度相关性打分（领域匹配度、时效性、权威性、置信度）
- 负反馈学习（持续进化机制）
- 行业方言词典（本地术语管理）
- 三重链验证（思维链、因果链、证据链）

智能向量存储（SmartVectorStore）：
- 混合模式（HydraCore V1.5 / FAISS / Chroma / Memory）
- 四级自动降级策略
- 免配置自动检测
- 性能自适应

重构版组件：
- WikiCore: 核心页面管理（CRUD、版本控制、搜索）
- SmartWikiEditor: 智能页面编辑器（链接建议、摘要生成、实体高亮）
- EntityExplorer: 实体探索器（关系图遍历、路径查找）
- KnowledgeTimeline: 知识时间线（页面历史追踪、版本对比）
- RecommendationEngine: 推荐引擎（个性化推荐、链接建议）
- WikiRAGBridge: RAG-Wiki桥接（双向数据同步、统一搜索）

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 7.0.0 (Phase 1 + 2 + 2+ + 3 + 4(EvoRAG) + 5(功能对等) + 6(智能向量存储) + 7(重构版))
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

# Phase 7 (重构版): 新架构组件 🌟
from .wiki_core import WikiCore, WikiPage, PageRevision, get_wiki_core
from .editor import SmartWikiEditor, EditSuggestion, EditorState, get_smart_wiki_editor
from .explorer import EntityExplorer, EntityNode, RelationEdge, ExplorationResult, get_entity_explorer
from .timeline import KnowledgeTimeline, TimelineEvent, TimelineEntry, get_knowledge_timeline
from .recommender import RecommendationEngine, Recommendation, get_recommendation_engine
from .bridge import WikiRAGBridge, WikiRAGResult, get_wiki_rag_bridge


__version__ = "7.0.0"
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
    "RetrievalResult",
    
    # Phase 7 (重构版): 新架构组件 🌟
    "WikiCore",
    "WikiPage",
    "PageRevision",
    "SmartWikiEditor",
    "EditSuggestion",
    "EditorState",
    "EntityExplorer",
    "EntityNode",
    "RelationEdge",
    "ExplorationResult",
    "KnowledgeTimeline",
    "TimelineEvent",
    "TimelineEntry",
    "RecommendationEngine",
    "Recommendation",
    "WikiRAGBridge",
    "WikiRAGResult",
    
    # Phase 7: 工具函数
    "get_wiki_core",
    "get_smart_wiki_editor",
    "get_entity_explorer",
    "get_knowledge_timeline",
    "get_recommendation_engine",
    "get_wiki_rag_bridge",
]


logger.info(f"LLM Wiki 模块 v{__version__} 已加载 (Phase 1 + 2 + 2+ + 3 + 4(EvoRAG) + 5(功能对等) + 6(智能向量存储) + 7(重构版))")
