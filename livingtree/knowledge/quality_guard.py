"""QualityGuard — Unified retrieval validation + hallucination detection.

Consolidates two previously separate quality modules:
  - RetrievalValidator: relevance filtering, citation injection, retrieval quality
  - HallucinationGuard: sentence-level factuality verification, hallucination stats

Both are post-retrieval quality checks in the RAG pipeline. This module
provides a unified import path while keeping original implementations intact.

Usage:
    from livingtree.knowledge.quality_guard import (
        RetrievalValidator, ValidatedHit, ValidationResult,
        HallucinationGuard, HallucinationReport, SentenceCheck, HallucinationStats,
    )
"""

from .retrieval_validator import RetrievalValidator, ValidatedHit, ValidationResult
from .hallucination_guard import (
    HallucinationGuard, HallucinationReport, SentenceCheck, HallucinationStats,
)

__all__ = [
    "RetrievalValidator", "ValidatedHit", "ValidationResult",
    "HallucinationGuard", "HallucinationReport", "SentenceCheck", "HallucinationStats",
]
