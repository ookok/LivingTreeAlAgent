"""Knowledge layer exports for LivingTree.

This package exposes the lightweight knowledge layer components:
- KnowledgeBase: central knowledge management and search
- VectorStore: pluggable vector backends for semantic search
- KnowledgeGraph: graph-based relationships between concepts
- FormatDiscovery: auto-discovery of document formats and templates
- GapDetector: identify and plan learning gaps
"""

from .knowledge_base import KnowledgeBase, Document  # type: ignore
from .vector_store import VectorStore, EmbeddingBackend  # type: ignore
from .knowledge_graph import KnowledgeGraph, Entity  # type: ignore
from .format_discovery import FormatDiscovery, Template  # type: ignore
from .gap_detector import GapDetector, Gap  # type: ignore

__all__ = [
    "KnowledgeBase",
    "Document",
    "VectorStore",
    "EmbeddingBackend",
    "KnowledgeGraph",
    "Entity",
    "FormatDiscovery",
    "Template",
    "GapDetector",
    "Gap",
]
