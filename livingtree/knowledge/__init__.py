"""Knowledge layer exports for LivingTree.

MultiDocFusion-enhanced (Shin et al., EMNLP 2025):
  - HierarchicalChunker: DSHP-LLM section-boundary-aware chunking
  - DocumentTree: hierarchical document structure representation
  - MultiDocFusionEngine: cross-document synthesis + conflict resolution
  - DocumentLayoutAnalyzer: vision-based region detection + figure-caption binding
  - ModernOCR: multi-backend OCR (Paddle/TrOCR/EasyOCR/Tesseract)
"""

from .knowledge_base import KnowledgeBase, Document, RetrievalResult, MergedCandidate, ScoredResult, FusionResult, SchemaInferrer, InferredSchema, InferredField, InferredFieldType, SCHEMA_INFERRER
from .vector_store import VectorStore, EmbeddingBackend
from .knowledge_graph import KnowledgeGraph, Entity
from .format_discovery import FormatDiscovery, Template
from .gap_detector import GapDetector, Gap
from .learning_engine import TemplateLearner, SkillDiscoverer, RoleGenerator
from .struct_mem import StructMemory, EventEntry, SynthesisBlock, MemoryBuffer, Opinion, MentalModel, TemporalCompressor, SignalCleaner, MemoryTier, CleanStage, CompressedEntry
from .provenance import ProvenanceTracker, ProvenanceEntry
from .context_glossary import DomainTerm, ContextGlossary, GLOSSARY
from .onto_bridge import OntoBridge, ExternalBinding, SchemaOrgMapper, WikidataMapper, IndustryOntology, ONTO_BRIDGE, get_onto_bridge
from .relation_engine import RelationEngine, RelationRule, RELATION_ENGINE, get_relation_engine
from .document_tree import DocumentTree, DocSection
from .hierarchical_chunker import HierarchicalChunker, DocumentChunk, build_document_tree, chunk_document, SemanticChunker, TableAwareSplitter
from .multidoc_fusion import MultiDocFusionEngine, CrossReference, DocumentConflict, FusionResult as MDFusionResult
from .layout_analyzer import DocumentLayoutAnalyzer, LayoutRegion, PageLayout, FigureCaption
from .modern_ocr import ModernOCR, OCRResult, OCRRegion
from .intelligent_kb import (
    unified_retrieve, hierarchical_retrieve, format_hierarchical_context,
    fact_check, detect_hallucination, FactCheckResult, KnowledgeGap,
    detect_semantic_gaps, fill_knowledge_gap, user_feedback,
    expand_query,
    accurate_retrieve, verify_generation, get_hallucination_dashboard,
)
from .query_decomposer import QueryDecomposer, DecomposedQuery, SubQuery, DecomposedResult
from .retrieval_validator import RetrievalValidator, ValidatedHit, ValidationResult
from .hallucination_guard import HallucinationGuard, HallucinationReport, SentenceCheck, HallucinationStats
from .quality_guard import KnowledgeQualityTest, run_quality_tests, QUALITY_TEMPLATES
from .content_quality import ContentQuality, QualityScore, ContentLabel
from .cognitive_delta import CognitiveDelta, DeltaResult, DeltaDecision
from .engram_store import EngramStore, EngramEntry, get_engram_store
from .pii_redactor import PIIRedactor, PIIFinding, RedactionResult, get_pii_redactor, redact_text, has_pii
from .knowledge_router import KnowledgeRouter, RouteDecision, RouteTarget, get_knowledge_router
from .ideablock_enricher import IdeaBlockEnricher, IdeaBlockMeta, get_ideablock_enricher
from .agentic_rag import AgenticRAG, AgenticResult, RetrievalRound, RAGMode, get_agentic_rag
from .reranker import Reranker, RankedDocument, RerankResult, get_reranker
from .context_wiki import ContextWiki, WikiPage, WikiSection, WikiTool, get_context_wiki, reset_context_wiki
from .learning_sources import LearningSourceRegistry, LearningSource, ResearchDirection, get_learning_sources

__all__ = [
    "KnowledgeBase", "Document", "RetrievalResult", "MergedCandidate", "ScoredResult", "FusionResult",
    "SchemaInferrer", "InferredSchema", "InferredField", "InferredFieldType", "SCHEMA_INFERRER",
    "VectorStore", "EmbeddingBackend",
    "KnowledgeGraph", "Entity",
    "FormatDiscovery", "Template",
    "GapDetector", "Gap",
    "TemplateLearner", "SkillDiscoverer", "RoleGenerator",
    "StructMemory", "EventEntry", "SynthesisBlock", "MemoryBuffer", "Opinion", "MentalModel",
    "TemporalCompressor", "SignalCleaner", "MemoryTier", "CleanStage", "CompressedEntry",
    "ProvenanceTracker", "ProvenanceEntry",
    "DomainTerm", "ContextGlossary", "GLOSSARY",
    "OntoBridge", "ExternalBinding", "SchemaOrgMapper", "WikidataMapper", "IndustryOntology", "ONTO_BRIDGE", "get_onto_bridge",
    "RelationEngine", "RelationRule", "RELATION_ENGINE", "get_relation_engine",
    "DocumentTree", "DocSection",
    "HierarchicalChunker", "DocumentChunk", "build_document_tree", "chunk_document",
    "SemanticChunker", "TableAwareSplitter",
    "MultiDocFusionEngine", "CrossReference", "DocumentConflict", "MDFusionResult",
    "DocumentLayoutAnalyzer", "LayoutRegion", "PageLayout", "FigureCaption",
    "ModernOCR", "OCRResult", "OCRRegion",
    "unified_retrieve", "hierarchical_retrieve", "format_hierarchical_context",
    "fact_check", "detect_hallucination", "FactCheckResult", "KnowledgeGap",
    "detect_semantic_gaps", "fill_knowledge_gap", "user_feedback",
    "expand_query",
    "accurate_retrieve", "verify_generation", "get_hallucination_dashboard",
    "QueryDecomposer", "DecomposedQuery", "SubQuery", "DecomposedResult",
    "RetrievalValidator", "ValidatedHit", "ValidationResult",
    "HallucinationGuard", "HallucinationReport", "SentenceCheck", "HallucinationStats",
    "ContentQuality", "QualityScore", "ContentLabel",
    "CognitiveDelta", "DeltaResult", "DeltaDecision",
    "EngramStore", "EngramEntry", "get_engram_store",
    "PIIRedactor", "PIIFinding", "RedactionResult", "get_pii_redactor", "redact_text", "has_pii",
    "KnowledgeRouter", "RouteDecision", "RouteTarget", "get_knowledge_router",
    "IdeaBlockEnricher", "IdeaBlockMeta", "get_ideablock_enricher",
    "AgenticRAG", "AgenticResult", "RetrievalRound", "RAGMode", "get_agentic_rag",
    "Reranker", "RankedDocument", "RerankResult", "get_reranker",
    "ContextWiki", "WikiPage", "WikiSection", "WikiTool", "get_context_wiki", "reset_context_wiki",
    "LearningSourceRegistry", "LearningSource", "ResearchDirection", "get_learning_sources",
]
