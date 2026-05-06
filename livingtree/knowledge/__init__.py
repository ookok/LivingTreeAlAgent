"""Knowledge layer exports for LivingTree.

This package exposes the lightweight knowledge layer components:
- KnowledgeBase: central knowledge management and search
- VectorStore: pluggable vector backends for semantic search
- KnowledgeGraph: graph-based relationships between concepts
- FormatDiscovery: auto-discovery of document formats and templates
- GapDetector: identify and plan learning gaps
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
]
