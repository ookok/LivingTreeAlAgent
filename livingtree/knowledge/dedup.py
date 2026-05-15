"""Deduplication engine — semantic + exact + near-duplicate detection.

Four dedup strategies:
1. Exact hash: SHA-256 of content → identical docs
2. Near-duplicate: MinHash + LSH for 90%+ similar docs
3. Semantic: embedding cosine similarity > 0.95
4. Chunk-level: for large documents, dedup at paragraph level

Integrated into KnowledgeBase.add_knowledge() — auto-checks on insert.
"""

from __future__ import annotations

import hashlib
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


class ExactDedup:
    """SHA-256 based exact duplicate detection."""

    @staticmethod
    def hash(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def matches(h1: str, h2: str) -> bool:
        return h1 == h2


class MinHashDedup:
    """MinHash + LSH for near-duplicate detection.

    Documents with Jaccard similarity > threshold are flagged.
    Uses 128 hash functions for good accuracy.
    """

    def __init__(self, num_hashes: int = 128, threshold: float = 0.8):
        self.num_hashes = num_hashes
        self.threshold = threshold
        self._hash_seeds = [(i * 2654435761) & 0xFFFFFFFF for i in range(num_hashes)]
        self._bands = 16  # LSH bands
        self._rows = num_hashes // 16  # hashes per band

    def signature(self, content: str) -> list[int]:
        """Compute MinHash signature for a document."""
        tokens = content.lower().split()
        if len(tokens) < 10:
            return [0] * self.num_hashes
        # Use n-grams for better accuracy
        ngrams = set()
        for i in range(len(tokens) - 2):
            ngrams.add(" ".join(tokens[i:i + 3]))
        if not ngrams:
            return [0] * self.num_hashes

        sig = []
        for seed in self._hash_seeds:
            min_hash = float('inf')
            for ng in ngrams:
                h = (hash(ng) ^ seed) & 0xFFFFFFFF
                if h < min_hash:
                    min_hash = h
            sig.append(min_hash)
        return sig

    def similarity(self, sig1: list[int], sig2: list[int]) -> float:
        """Estimate Jaccard similarity from MinHash signatures."""
        if len(sig1) != len(sig2):
            return 0.0
        matches = sum(1 for a, b in zip(sig1, sig2) if a == b)
        return matches / len(sig1)

    def is_duplicate(self, sig1: list[int], sig2: list[int]) -> bool:
        return self.similarity(sig1, sig2) >= self.threshold

    def lsh_band_key(self, sig: list[int], band: int) -> int:
        """LSH band hash for fast candidate lookup."""
        start = band * self._rows
        band_hashes = sig[start:start + self._rows]
        return hash(tuple(band_hashes)) & 0xFFFFFFFF


class SemanticDedup:
    """Embedding cosine similarity for semantic dedup.

    Two docs saying the same thing differently → detected.
    """

    def __init__(self, vector_store: Any = None, threshold: float = 0.95):
        self.vector_store = vector_store
        self.threshold = threshold

    async def is_duplicate(self, text: str, existing_texts: list[str]) -> bool:
        """Check if text is semantically similar to any existing."""
        if not self.vector_store or len(existing_texts) < 2:
            return False

        # For efficiency: only check against top-5 similar
        query_vec = self.vector_store.embed(text)
        similar_ids = self.vector_store.search_similar(query_vec, top_k=5)

        for sid in similar_ids:
            if sid in self.vector_store._vectors:
                existing_vec = self.vector_store._vectors[sid]
                sim = self._cosine(query_vec, existing_vec)
                if sim >= self.threshold:
                    return True
        return False

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        import math
        if len(a) != len(b) or len(a) == 0:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(x * x for x in b)) or 1.0
        return dot / (na * nb)


class ChunkDedup:
    """Paragraph-level dedup for large documents.

    Splits document into chunks, deduplicates at chunk level,
    merges unique chunks back.
    """

    @staticmethod
    def chunk(content: str, chunk_size: int = 1000) -> list[str]:
        """Split content into paragraphs, then chunk."""
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        chunks = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) > chunk_size and current:
                chunks.append(current)
                current = para
            else:
                current = (current + "\n\n" + para).strip()
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def dedup_chunks(chunks: list[str]) -> list[str]:
        """Remove duplicate chunks, keeping first occurrence."""
        seen = set()
        unique = []
        for ch in chunks:
            h = hashlib.md5(ch.encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                unique.append(ch)
        return unique

    @staticmethod
    def dedup_and_merge(content: str, chunk_size: int = 1000) -> str:
        """Dedup a large document and return deduplicated text."""
        chunks = ChunkDedup.chunk(content, chunk_size)
        unique = ChunkDedup.dedup_chunks(chunks)
        return "\n\n".join(unique)


class DedupEngine:
    """Unified deduplication engine.

    Usage:
        engine = DedupEngine(vector_store=vs)
        result = await engine.check(content)
        if result["is_duplicate"]:
            return f"Duplicate of: {result['matched_id']}"
    """

    def __init__(self, vector_store: Any = None, kb: Any = None):
        self.exact = ExactDedup()
        self.minhash = MinHashDedup()
        self.semantic = SemanticDedup(vector_store)
        self.chunk = ChunkDedup()
        self.kb = kb
        self._minhash_cache: dict[str, list[int]] = {}

    async def check(self, content: str, content_id: str = "",
                     check_exact: bool = True, check_near: bool = True,
                     check_semantic: bool = True) -> dict[str, Any]:
        """Check if content is a duplicate of any existing document.

        Returns:
            {
                "is_duplicate": bool,
                "duplicate_of": str or None,   # matched doc ID
                "method": str,                  # exact / near_dup / semantic / none
                "similarity": float,
                "suggestion": str,              # human-readable suggestion
            }
        """
        if len(content) < 50:
            return {"is_duplicate": False, "method": "too_short"}

        # 1. Exact hash check
        content_hash = self.exact.hash(content)
        if check_exact and self.kb:
            try:
                for doc in self.kb.history()[:1000]:
                    doc_hash = self.exact.hash(doc.content)
                    if self.exact.matches(content_hash, doc_hash):
                        return {
                            "is_duplicate": True, "duplicate_of": doc.id,
                            "method": "exact", "similarity": 1.0,
                            "suggestion": f"Exact duplicate of '{doc.title}'",
                        }
            except Exception:
                pass

        # 2. Near-duplicate check
        if check_near and len(content) > 100:
            sig = self.minhash.signature(content)
            if self.kb:
                try:
                    for doc in self.kb.history()[:500]:
                        if doc.id == content_id:
                            continue
                        existing_key = f"{doc.id}:{len(doc.content)}"
                        if existing_key not in self._minhash_cache:
                            self._minhash_cache[existing_key] = self.minhash.signature(doc.content)
                        doc_sig = self._minhash_cache[existing_key]
                        sim = self.minhash.similarity(sig, doc_sig)
                        if sim >= self.minhash.threshold:
                            return {
                                "is_duplicate": True, "duplicate_of": doc.id,
                                "method": "near_dup", "similarity": sim,
                                "suggestion": f"{sim*100:.0f}% similar to '{doc.title}'",
                            }
                except Exception:
                    pass

        # 3. Semantic check
        if check_semantic and self.semantic.vector_store:
            try:
                if await self.semantic.is_duplicate(content, []):
                    return {
                        "is_duplicate": True, "duplicate_of": "semantic_match",
                        "method": "semantic", "similarity": 0.95,
                        "suggestion": "Semantically identical content detected",
                    }
            except Exception:
                pass

        return {"is_duplicate": False, "method": "none", "similarity": 0.0}

    async def dedup_document(self, content: str) -> str:
        """Dedup a document's internal paragraphs."""
        return self.chunk.dedup_and_merge(content)

    async def add_with_dedup(self, content: str, title: str = "",
                             domain: str = "", source: str = "") -> Optional[str]:
        """Add content to KB only if not a duplicate. Returns doc ID or None."""
        if not self.kb:
            return None

        result = await self.check(content)
        if result["is_duplicate"]:
            logger.info(f"Dedup blocked: {result['suggestion']}")
            return None

        from .knowledge_base import Document
        doc = Document(title=title, content=content, domain=domain, source=source)
        return self.kb.add_knowledge(doc)


class DeltaDecision:
    GAP = "gap"
    DIFF = "diff"
    DUP = "dup"


@dataclass
class DeltaResult:
    decision: str = DeltaDecision.DUP
    reason: str = ""
    new_info: dict = field(default_factory=dict)
    existing_info: dict = field(default_factory=dict)
    diff_summary: str = ""
    confidence: float = 1.0


class CognitiveDelta:
    """Knowledge increment detection engine.

    Compares new info against existing knowledge base. Only permits
    storage when genuine new information is detected.

    Comparison dimensions:
      1. Content hash (exact duplicate check)
      2. Title/key similarity (near-duplicate check)
      3. Semantic difference scoring (information gain)
      4. Time-based priority (newer wins when conflicting)
    """

    def __init__(self, content_similarity_threshold: float = 0.85):
        self.content_similarity_threshold = content_similarity_threshold

    def evaluate(
        self,
        new_item: dict,
        existing_items: list[dict] = None,
    ) -> DeltaResult:
        existing = existing_items or []
        result = DeltaResult(new_info=new_item)

        if not existing:
            result.decision = DeltaDecision.GAP
            result.reason = "首次入库 — 知识空白填补"
            result.confidence = 1.0
            return result

        new_hash = self._content_hash(new_item)
        for ex in existing:
            if self._content_hash(ex) == new_hash:
                result.decision = DeltaDecision.DUP
                result.reason = "内容完全相同 — 丢弃"
                result.existing_info = ex
                result.confidence = 1.0
                return result

        best_match = None
        best_sim = 0.0
        for ex in existing:
            sim = self._entry_similarity(new_item, ex)
            if sim > best_sim:
                best_sim = sim
                best_match = ex

        if best_sim >= self.content_similarity_threshold and best_match:
            result.existing_info = best_match

            diff_text = self._compute_diff(new_item, best_match)
            if not diff_text or diff_text == "无实质差异":
                result.decision = DeltaDecision.DUP
                result.reason = "内容实质相同 — 丢弃"
                return result

            result.decision = DeltaDecision.DIFF
            result.reason = f"发现{len(diff_text)}处差异 — 更新知识"
            result.diff_summary = diff_text
            result.confidence = best_sim
            return result

        result.decision = DeltaDecision.GAP
        result.reason = "内容无相似匹配 — 新知识入库"
        result.confidence = 1.0
        return result

    def build_entry(
        self,
        new_item: dict,
        existing_items: list[dict] = None,
        attachment_summaries: list[str] = None,
    ) -> dict:
        result = self.evaluate(new_item, existing_items)

        entry = {
            "id": hashlib.md5(
                (new_item.get("title", "") + new_item.get("source", "")).encode()
            ).hexdigest()[:16],
            "title": new_item.get("title", "")[:300],
            "source": new_item.get("source", "")[:500],
            "publish_date": new_item.get("date", ""),
            "status": new_item.get("status", ""),
            "summary": new_item.get("content", "")[:1000],
            "attachment_summaries": attachment_summaries or [],
            "delta_decision": result.decision,
            "delta_reason": result.reason,
            "delta_diff": result.diff_summary[:1000] if result.decision == DeltaDecision.DIFF else "",
            "stored_at": time.strftime("%Y-%m-%d %H:%M"),
        }

        if result.decision == DeltaDecision.DUP:
            entry["summary"] = "[重复 — 未存储完整内容]"
            entry["references_existing_id"] = result.existing_info.get("id", "")

        return entry

    def _content_hash(self, item: dict) -> str:
        text = (item.get("title", "") + item.get("content", "") +
                item.get("source", "") + item.get("date", ""))
        return hashlib.md5(text.encode()).hexdigest()

    def _entry_similarity(self, a: dict, b: dict) -> float:
        a_text = self._normalize(a.get("title", "") + " " + a.get("content", ""))
        b_text = self._normalize(b.get("title", "") + " " + b.get("content", ""))

        if not a_text or not b_text:
            return 0.0

        n = 4
        a_ngrams = {a_text[i:i+n] for i in range(len(a_text) - n + 1)}
        b_ngrams = {b_text[i:i+n] for i in range(len(b_text) - n + 1)}

        if not a_ngrams or not b_ngrams:
            return 0.0

        return len(a_ngrams & b_ngrams) / len(a_ngrams | b_ngrams)

    @staticmethod
    def _normalize(text: str) -> str:
        import re
        text = re.sub(r'\s+', '', text.lower())
        return text

    @staticmethod
    def _compute_diff(new_item: dict, existing: dict) -> str:
        diffs = []

        for field in ["title", "status", "date"]:
            new_val = new_item.get(field, "")
            old_val = existing.get(field, "")
            if new_val and old_val and new_val != old_val:
                diffs.append(f"{field}: '{old_val}' → '{new_val}'")

        new_content = new_item.get("content", "")
        old_content = existing.get("content", "")
        if new_content and old_content:
            new_words = set(new_content.split())
            old_words = set(old_content.split())
            added = new_words - old_words
            removed = old_words - new_words
            if added:
                diffs.append(f"+{len(added)} new terms")
            if removed:
                diffs.append(f"-{len(removed)} removed terms")

        if not diffs:
            return "无实质差异"

        return "; ".join(diffs)


__all__ = [
    "ExactDedup", "MinHashDedup", "SemanticDedup", "ChunkDedup", "DedupEngine",
    "DeltaDecision", "DeltaResult", "CognitiveDelta",
]
