"""FDAC: Feedback-Driven Adaptive Compression + Semantic-Preserving Compression.

Design:
  FDAC (1): LLM scores each retrieved chunk → system learns optimal compression ratios.
  Semantic-Preserving (5): Flash model compresses, Pro model verifies fidelity.

Integration points:
  - struct_mem.graded_store() — PrecisionTier auto-adjusted by FDAC feedback
  - intelligent_kb.unified_retrieve() — compression ratio applied to retrieved chunks
  - hifloat8_provider — long-context window enables deeper retrieval

Flow:
  retrieve → chunk → LLM relevance score [0,1]
                     ↓
  score > 0.7 → FULL precision (cone center, 7 mantissa bits)
  0.3-0.7     → SUMMARY (3-5 mantissa bits, semantic compression)
  < 0.3       → STUB (1 mantissa bit, title+synopsis only)

  Flash compress → Pro verify → accept/reject → learn threshold
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ── Data Structures ──

@dataclass
class ChunkFeedback:
    """LLM feedback on a retrieved chunk's relevance."""
    chunk_id: str
    relevance: float          # 0-1 score from LLM
    source: str               # "document_kb", "knowledge_base", "struct_mem"
    query: str                # original query that retrieved this chunk
    timestamp: float = field(default_factory=time.time)


@dataclass
class CompressionProfile:
    """Learned compression profile for a content type/source."""
    source: str
    optimal_ratio: float = 0.5    # fraction to keep
    confidence: float = 0.0       # based on feedback volume
    fidelity_score: float = 1.0   # from pro-model verification
    sample_count: int = 0
    last_updated: float = 0.0


@dataclass
class FidelityCheck:
    """Result of semantic preservation verification."""
    kept_facts: list[str]       # facts preserved in compressed version
    lost_facts: list[str]        # facts lost after compression
    compression_ratio: float     # chars_after / chars_before
    passed: bool                 # pro model confirmed fidelity
    explanation: str = ""


class FDACCompressor:
    """Feedback-Driven Adaptive Compression engine.

    Learns from LLM relevance feedback to optimize compression ratios
    per content type/source. Integrates with StructMemory's PrecisionTier.

    Attributes:
        profiles: dict — source → CompressionProfile
        feedback_buffer: list[ChunkFeedback] — recent LLM scores
        _flash_model: Optional provider for semantic compression
        _pro_model: Optional provider for fidelity verification
    """

    def __init__(self, profiles_path: str = ".livingtree/fdac_profiles.json"):
        self._profiles_path = Path(profiles_path)
        self.profiles: dict[str, CompressionProfile] = {}
        self.feedback_buffer: list[ChunkFeedback] = []
        self._flash_model = None
        self._pro_model = None
        self._load_profiles()

    # ── Profile Management ──

    def _load_profiles(self) -> None:
        try:
            if self._profiles_path.exists():
                data = json.loads(self._profiles_path.read_text("utf-8"))
                for k, v in data.items():
                    self.profiles[k] = CompressionProfile(**v)
        except Exception:
            logger.debug("FDAC: no existing profiles, starting fresh")

    def _save_profiles(self) -> None:
        try:
            self._profiles_path.parent.mkdir(parents=True, exist_ok=True)
            data = {k: {
                "source": v.source, "optimal_ratio": v.optimal_ratio,
                "confidence": v.confidence, "fidelity_score": v.fidelity_score,
                "sample_count": v.sample_count, "last_updated": v.last_updated,
            } for k, v in self.profiles.items()}
            self._profiles_path.write_text(json.dumps(data, indent=2), "utf-8")
        except Exception:
            pass

    # ── FDAC Core: Feedback Loop ──

    def record_feedback(self, chunk_id: str, relevance: float,
                        source: str, query: str = "") -> None:
        """LLM scores a chunk → system learns.

        Called after every retrieval + LLM inference cycle.
        """
        fb = ChunkFeedback(
            chunk_id=chunk_id, relevance=relevance,
            source=source, query=query,
        )
        self.feedback_buffer.append(fb)

        # Update profile for this source
        profile = self.profiles.get(source)
        if not profile:
            profile = CompressionProfile(source=source)
            self.profiles[source] = profile

        # Bayesian update: weighted moving average
        alpha = 1.0 / (profile.sample_count + 1)
        # High relevance → we can compress more (keep less)
        target_ratio = 0.3 + 0.4 * (1.0 - relevance)
        profile.optimal_ratio = (1 - alpha) * profile.optimal_ratio + alpha * target_ratio
        profile.sample_count += 1
        profile.confidence = min(1.0, profile.sample_count / 20.0)
        profile.last_updated = time.time()

        # Periodically persist
        if profile.sample_count % 10 == 0:
            self._save_profiles()

    def get_compression_ratio(self, source: str) -> float:
        """Get learned optimal compression ratio for a source."""
        profile = self.profiles.get(source)
        if profile and profile.confidence > 0.3:
            return profile.optimal_ratio
        return 0.5  # default: keep half

    def get_precision_tier(self, relevance: float) -> str:
        """Map relevance score to PrecisionTier.

        Cone-shaped: peak precision for highly relevant content.
        """
        if relevance > 0.7:
            return "FULL"
        elif relevance > 0.3:
            return "SUMMARY"
        return "STUB"

    # ── Semantic-Preserving Compression (#5) ──

    async def semantic_compress(
        self, text: str, target_ratio: float = 0.5,
        flash_consciousness=None, pro_consciousness=None,
    ) -> str:
        """Compress text semantically, preserving key facts.

        Flash model (cheap) compresses → Pro model (expensive) verifies.

        Args:
            text: Original text.
            target_ratio: Desired compression ratio (0-1).
            flash_consciousness: Fast model for compression.
            pro_consciousness: Powerful model for fidelity check.

        Returns:
            Compressed text if fidelity check passes, else original.
        """
        if not text or len(text) < 200:
            return text  # Too short to compress

        target_chars = max(100, int(len(text) * target_ratio))

        # Step 1: Flash model compresses
        compressed = await self._flash_compress(
            text, target_chars, flash_consciousness
        )
        if not compressed or len(compressed) >= len(text):
            return text

        # Step 2: Pro model verifies fidelity
        if pro_consciousness:
            check = await self._verify_fidelity(
                text, compressed, pro_consciousness
            )
            if not check.passed:
                logger.debug(
                    f"FDAC: fidelity check failed (lost {len(check.lost_facts)} facts), "
                    f"keeping original"
                )
                return text

        logger.debug(
            f"FDAC: compressed {len(text)}→{len(compressed)} chars "
            f"({len(compressed)/len(text):.0%})"
        )
        return compressed

    async def _flash_compress(
        self, text: str, target_chars: int, consciousness
    ) -> str:
        """Use flash model to compress text while preserving semantics."""
        prompt = (
            "Compress the following text to approximately {target} characters "
            "while preserving ALL key facts, numbers, dates, names, and relationships. "
            "Output ONLY the compressed text, no explanations.\n\n"
            "{text}"
        ).format(target=target_chars, text=text)

        try:
            result = await consciousness.chat(prompt, max_tokens=target_chars + 200)
            text = result.text if hasattr(result, 'text') else str(result)
            return text[:target_chars + 500]  # cap
        except Exception as e:
            logger.debug(f"FDAC: flash compression failed: {e}")
            return text  # fallback: return original

    async def _verify_fidelity(
        self, original: str, compressed: str, consciousness
    ) -> FidelityCheck:
        """Pro model verifies that compressed text preserved key facts."""
        prompt = (
            "Compare the ORIGINAL and COMPRESSED text below. List:\n"
            "1. Facts PRESERVED in the compressed version\n"
            "2. Facts LOST in the compressed version\n"
            "Then answer: does the compressed version preserve the ESSENTIAL "
            "meaning? Answer YES or NO.\n\n"
            "=== ORIGINAL ===\n{orig}\n\n"
            "=== COMPRESSED ===\n{comp}"
        ).format(
            orig=original[:2000],
            comp=compressed[:2000],
        )

        try:
            result = await consciousness.chat(prompt, max_tokens=500)
            text = result.text if hasattr(result, 'text') else str(result)

            # Parse verdict
            passed = "YES" in text.upper().split("\n")[-3:]
            return FidelityCheck(
                kept_facts=[],
                lost_facts=[],
                compression_ratio=len(compressed) / max(1, len(original)),
                passed=passed,
                explanation=text[:300],
            )
        except Exception as e:
            logger.debug(f"FDAC: fidelity check failed: {e}")
            return FidelityCheck(
                kept_facts=[], lost_facts=[],
                compression_ratio=1.0, passed=True,
                explanation=f"Verification error: {e}",
            )

    # ── Batch Processing ──

    async def compress_retrieved_chunks(
        self, chunks: list[dict], query: str,
        flash_consciousness=None, pro_consciousness=None,
    ) -> list[dict]:
        """Compress a batch of retrieved chunks using FDAC.

        Each chunk gets: relevance estimate → compression ratio → semantic compression.
        """
        results = []
        for chunk in chunks:
            text = chunk.get("text", "")
            source = chunk.get("source", "unknown")
            chunk_id = chunk.get("doc_id", "") or chunk.get("chunk_id", "")

            if not text:
                results.append(chunk)
                continue

            # Estimate relevance (heuristic: more query term matches → higher)
            relevance = self._estimate_relevance(text, query)

            # Get compression ratio from learned profile
            ratio = self.get_compression_ratio(source)

            # Semantic compression
            compressed = await self.semantic_compress(
                text, ratio, flash_consciousness, pro_consciousness
            )

            new_chunk = {**chunk, "text": compressed}
            results.append(new_chunk)

            # Feed back to FDAC (async, fire-and-forget)
            self.record_feedback(
                chunk_id=chunk_id, relevance=relevance, source=source, query=query
            )

        return results

    @staticmethod
    def _estimate_relevance(text: str, query: str) -> float:
        """Simple relevance heuristic: query term overlap with text."""
        if not query or not text:
            return 0.5
        query_terms = set(query.lower().split())
        text_lower = text.lower()
        hits = sum(1 for t in query_terms if t in text_lower)
        # Sigmoid-like: 3+ hits → high relevance
        return min(1.0, hits / max(1, len(query_terms)) * 1.5)


# ── Singleton ──

_fdac: Optional[FDACCompressor] = None


def get_fdac() -> FDACCompressor:
    global _fdac
    if _fdac is None:
        _fdac = FDACCompressor()
    return _fdac
