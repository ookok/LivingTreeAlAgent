"""AdaptiveClassifier — embedding-based intent/domain/emotion classification.

Replaces ALL hardcoded keyword maps with a single embedding-based classifier.
Prototype embeddings are computed once from category description strings,
then updated adaptively from actual usage data via exponential moving average.

Architecture:
  classify(query, category_set) → best category name
  Each category has a prototype embedding (1024-dim from SiliconFlow API).
  Query embedding compared via cosine similarity to all prototypes.
  Prototypes adapt via EMA from successful classifications.

Usage:
  c = get_adaptive_classifier()
  task_type = c.classify("analyze this data", c.TASK_TYPES)
  domain = c.classify("GB/T 24001 standard", c.DOMAINS)
  layer = c.classify("fix the bug", c.LAYERS)
  emotion = c.classify("I'm so frustrated", c.EMOTIONS)
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class CategoryPrototype:
    """A learned category prototype embedding."""
    name: str
    description: str                    # initial description text
    embedding: list[float] = field(default_factory=list)
    sample_count: int = 0               # number of times this category was matched
    last_matched: float = 0.0
    confidence: float = 0.5             # EMA of classification confidence

    def adapt(self, query_embedding: list[float], alpha: float = 0.1):
        """Update prototype via EMA: new = (1-α)·old + α·query_embedding."""
        if not self.embedding:
            self.embedding = list(query_embedding)
        else:
            for i in range(min(len(self.embedding), len(query_embedding))):
                self.embedding[i] = self.embedding[i] * (1 - alpha) + query_embedding[i] * alpha
        self.sample_count += 1
        self.last_matched = time.time()


class AdaptiveClassifier:
    """Embedding-based universal classifier. No hardcoded keywords."""

    # Category sets
    TASK_TYPES = {
        "code": "code programming fix debug implement function class API algorithm",
        "reasoning": "analysis reasoning evaluate compare analyze logic mathematics proof",
        "search": "search find lookup retrieve query information knowledge web",
        "chat": "hello chat conversation general question help explain what how",
        "creative": "write create generate translate summarize compose poetry story",
    }
    LAYERS = {
        "fast": "general chat question answer help explain simple quick",
        "reasoning": "code debug fix implement analyze reason compare complex deep",
    }
    DOMAINS = {
        "ai": "artificial intelligence machine learning deep learning neural network LLM GPT transformer",
        "environment": "EIA ESIA environment assessment emission pollution ecology climate carbon",
        "engineering": "design architecture infrastructure construction mechanical electrical civil",
        "regulation": "GB standard regulation compliance law policy legal governance",
        "finance": "finance investment banking market trading stock cryptocurrency economy",
        "medical": "medical health clinical diagnosis treatment drug therapy disease",
        "programming": "programming software development code API database algorithm system",
    }
    EMOTIONS = {
        "joy": "happy delighted excited pleased joyful satisfied wonderful great amazing",
        "sadness": "sad unhappy depressed disappointed frustrated miserable sorrowful",
        "anger": "angry furious annoyed irritated frustrated rage upset",
        "fear": "afraid scared worried anxious nervous terrified fearful",
        "trust": "trust confident believe reliable dependable certain sure",
        "surprise": "surprised amazed astonished shocked unexpected wow",
        "disgust": "disgusted revolted repulsed horrible terrible awful",
        "neutral": "okay fine normal standard regular typical usual",
    }

    _instance: Optional["AdaptiveClassifier"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._prototypes: dict[str, dict[str, CategoryPrototype]] = {}
        self._initialized = False
        self._embedding_cache: dict[str, list[float]] = {}
        self._cache_hits = 0
        self._api_calls = 0

    @classmethod
    def instance(cls) -> "AdaptiveClassifier":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = AdaptiveClassifier()
        return cls._instance

    # ═══ Public API ════════════════════════════════════════════════

    def classify(self, query: str, category_set: dict[str, str],
                 set_name: str = "") -> tuple[str, float]:
        """Classify query into best category. Returns (category_name, confidence).

        Args:
            query: Text to classify
            category_set: {name: description_string} mapping
            set_name: Optional name for prototype caching

        Returns:
            (best_category, cosine_similarity_score)
        """
        if not query or not category_set:
            return list(category_set.keys())[0] if category_set else "", 0.0

        key = set_name or self._hash_set(category_set)
        prototypes = self._ensure_prototypes(key, category_set)
        q_emb = self._embed(query)

        if not q_emb or not prototypes:
            return list(category_set.keys())[0], 0.0

        best_cat = ""
        best_sim = -1.0
        for cat, proto in prototypes.items():
            if not proto.embedding:
                continue
            sim = self._cosine(q_emb, proto.embedding)
            if sim > best_sim:
                best_sim = sim
                best_cat = cat

        return best_cat or list(category_set.keys())[0], max(0.0, best_sim)

    def classify_and_adapt(self, query: str, category_set: dict[str, str],
                           correct_category: str, set_name: str = ""):
        """Classify AND update prototype for the correct category (supervised)."""
        key = set_name or self._hash_set(category_set)
        prototypes = self._ensure_prototypes(key, category_set)
        q_emb = self._embed(query)

        if q_emb and correct_category in prototypes:
            prototypes[correct_category].adapt(q_emb, alpha=0.15)
            logger.debug(f"AdaptiveClassifier: {set_name}/{correct_category} adapted (n={prototypes[correct_category].sample_count})")

        return self.classify(query, category_set, set_name)

    def stats(self) -> dict:
        return {
            "cache_hits": self._cache_hits,
            "api_calls": self._api_calls,
            "category_sets": len(self._prototypes),
            "total_categories": sum(len(p) for p in self._prototypes.values()),
        }

    # ═══ Internal ═══════════════════════════════════════════════════

    def _ensure_prototypes(self, key: str, category_set: dict[str, str]) -> dict[str, CategoryPrototype]:
        """Build or retrieve prototype embeddings for a category set."""
        if key in self._prototypes:
            return self._prototypes[key]

        prototypes = {}
        for name, desc in category_set.items():
            proto = CategoryPrototype(name=name, description=desc)
            emb = self._embed(desc)
            if emb:
                proto.embedding = emb
            prototypes[name] = proto

        self._prototypes[key] = prototypes
        return prototypes

    def _embed(self, text: str) -> list[float] | None:
        """Get embedding via SiliconFlow API with local cache."""
        if not text:
            return None

        # Check cache
        cache_key = text[:100].lower().strip()
        if cache_key in self._embedding_cache:
            self._cache_hits += 1
            return self._embedding_cache[cache_key]

        # API call
        emb = self._embed_api(text)
        if emb:
            self._api_calls += 1
            self._embedding_cache[cache_key] = emb
            if len(self._embedding_cache) > 500:
                # Evict oldest
                oldest = sorted(self._embedding_cache.keys(), key=lambda k: len(k))[:50]
                for k in oldest:
                    self._embedding_cache.pop(k, None)
            return emb

        # Hash fallback
        return self._embed_hash(text)

    def _embed_api(self, text: str) -> list[float] | None:
        try:
            import httpx
            from livingtree.config.secrets import get_secret_vault
            key = get_secret_vault()._cache.get("siliconflow_api_key", "")
            if not key:
                return None
            resp = httpx.post(
                "https://api.siliconflow.cn/v1/embeddings",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": "BAAI/bge-large-zh-v1.5", "input": text},
                timeout=10.0,
            )
            if resp.status_code == 200:
                return resp.json()["data"][0]["embedding"]
        except Exception:
            pass
        return None

    def _embed_hash(self, text: str) -> list[float]:
        try:
            from ..dna.task_vector_geometry import text_to_embedding
            return text_to_embedding(text)
        except Exception:
            return [0.0] * 128

    @staticmethod
    def _cosine(a, b) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = (sum(x * x for x in a) ** 0.5)
        nb = (sum(y * y for y in b) ** 0.5)
        return dot / (na * nb) if na and nb else 0.0

    @staticmethod
    def _hash_set(category_set: dict) -> str:
        return f"set_{hash(tuple(sorted(category_set.keys())))}"


# ═══ Singleton ═══

def get_adaptive_classifier() -> AdaptiveClassifier:
    return AdaptiveClassifier.instance()
