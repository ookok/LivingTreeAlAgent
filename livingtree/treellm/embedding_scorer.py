"""
RouteMoA-inspired lightweight embedding-based model scorer.

This module provides:
- ModelProfile: a dataclass describing a model/provider profile including a precomputed embedding.
- EmbeddingScorer: a simple, dependency-free scorer that represents texts as fixed-dim hash-based embeddings
  and scores query-model relevance via a dot-product followed by a sigmoid.
- get_embedding_scorer(): singleton factory for a global EmbeddingScorer instance.

Notes:
- No heavy ML libraries (no numpy, torch, sklearn). Embeddings are deterministic hashes-based TF-like averages.
- The scorer is designed to run before the ping phase in holistic_election.py to shrink candidate sets.
- Pre-seeded providers mimic the PROVIDER_CAPABILITIES from the existing codebase. Embeddings are computed
  from description + capabilities text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional
import math
import re


@dataclass
class ModelProfile:
    name: str
    description: str
    capabilities: List[str]
    embedding: List[float]
    cost_yuan_per_1k: float
    avg_latency_ms: float


class EmbeddingScorer:
    """Lightweight, deterministic embedding-based scorer.

    Embedding is produced via a hash-based TF-like weighted average over tokens.
    - Tokens are lowercased and split on non-alphanumeric characters.
    - Each token contributes a vector with a 1 at index = hash(token) mod dim, weighted by (1 + log(freq)).
    - The resulting vector is normalized (L2) and used for dot-product scoring.
    """

    def __init__(self, dim: int = 128) -> None:
        self.dim = dim
        # Seed 15 provider profiles with pre-computed embeddings
        self._profiles: List[ModelProfile] = self._seed_profiles()

    # --------- Text processing helpers ---------
    def _tokenize(self, text: str) -> List[str]:
        # simple, deterministic tokenizer: lowercase and split on non-alphanumeric
        s = text.lower()
        # keep alphanumeric sequences
        tokens = re.findall(r"[a-z0-9]+", s)
        return tokens

    def _encode(self, text: str) -> List[float]:
        tokens = self._tokenize(text)
        vec = [0.0] * self.dim
        if not tokens:
            return vec
        # term frequencies
        freqs = {}
        for t in tokens:
            freqs[t] = freqs.get(t, 0) + 1
        total_weight = 0.0
        for t, freq in freqs.items():
            idx = abs(hash(t)) % self.dim
            weight = 1.0 + math.log(float(freq))
            vec[idx] += weight
            total_weight += weight
        if total_weight > 0:
            vec = [v / total_weight for v in vec]
        # L2 normalization
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    @staticmethod
    def _dot(a: List[float], b: List[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

    # --------- Public API ---------
    def score(self, query: str, profiles: List[ModelProfile]) -> List[Tuple[str, float]]:
        """Compute sigmoid-scored dot-product between query embedding and each profile embedding."""
        q_vec = self._encode(query)
        results: List[Tuple[str, float]] = []
        for p in profiles:
            dot = self._dot(q_vec, p.embedding)
            score = 1.0 / (1.0 + math.exp(-dot))  # sigmoid
            results.append((p.name, score))
        results.sort(key=lambda kv: kv[1], reverse=True)
        return results

    def score_and_filter(self, query: str, profiles: List[ModelProfile], top_k: int = 5) -> List[Tuple[str, float]]:
        scored = self.score(query, profiles)
        return scored[:top_k]

    def update_profile(self, name: str, query: str, success: bool) -> None:
        """Online update: nudge the profile embedding toward (success) or away from (failure) the query embedding."""
        prof = next((p for p in self._profiles if p.name == name), None)
        if prof is None:
            return
        q_vec = self._encode(query)
        if not q_vec or len(q_vec) != self.dim:
            return
        lr = 0.05 if success else -0.01
        # Move embedding slightly toward/away from query embedding
        new_vec = [prof.embedding[i] + lr * q_vec[i] for i in range(self.dim)]
        # Normalize
        norm = math.sqrt(sum(v * v for v in new_vec))
        if norm > 0:
            prof.embedding = [v / norm for v in new_vec]
        else:
            prof.embedding = new_vec

    # --------- Internal helpers ---------
    def _seed_profiles(self) -> List[ModelProfile]:
        # Hard-coded seed providers (15 total: 13 named providers + 2 generic fallbacks)
        providers = [
            {
                "name": "modelscope",
                "description": "A versatile AI model provider offering general purpose capabilities across text, code, and data tasks.",
                "capabilities": ["text", "code", "data", "multi-domain", "fast", "scalable"],
                "cost": 1.0,
                "latency": 100.0,
            },
            {
                "name": "deepseek",
                "description": "Specializes in semantic search and retrieval augmented generation for complex queries.",
                "capabilities": ["semantic-search", "retrieval", "rlhf"],
                "cost": 0.9,
                "latency": 150.0,
            },
            {
                "name": "siliconflow",
                "description": "Hardware-accelerated model serving with low-latency inference and streaming support.",
                "capabilities": ["low-latency", "streaming", "scalability"],
                "cost": 1.1,
                "latency": 110.0,
            },
            {
                "name": "mofang",
                "description": "中文模型服务，覆盖文本生成与对话能力，支持多语言扩展。",
                "capabilities": ["text", "chat", "multilingual"],
                "cost": 0.95,
                "latency": 90.0,
            },
            {
                "name": "longcat",
                "description": "General purpose AI provider with broad capability coverage and robust API.",
                "capabilities": ["text", "code", "image"],
                "cost": 0.6,
                "latency": 180.0,
            },
            {
                "name": "zhipu",
                "description": "Chinese AI provider with strong NLP and translation capabilities.",
                "capabilities": ["nlp", "translation", "tokenization"],
                "cost": 0.8,
                "latency": 140.0,
            },
            {
                "name": "spark",
                "description": "Lightweight model serving for quick experiments and prototyping.",
                "capabilities": ["experimentation", "prototype", "flexible"],
                "cost": 0.7,
                "latency": 130.0,
            },
            {
                "name": "xiaomi",
                "description": "Consumer-grade AI models focusing on mobile-friendly workloads.",
                "capabilities": ["mobile", "on-device", "edge"],
                "cost": 0.9,
                "latency": 160.0,
            },
            {
                "name": "aliyun",
                "description": "Aliyun AI suite with robust cloud-scale capabilities.",
                "capabilities": ["cloud", "scaling", "storage"],
                "cost": 0.8,
                "latency": 100.0,
            },
            {
                "name": "dmxapi",
                "description": "API-first model access with modular components for building AI apps.",
                "capabilities": ["api", "modular", "integration"],
                "cost": 0.7,
                "latency": 120.0,
            },
            {
                "name": "nvidia",
                "description": "High-performance AI serving with CUDA-backed inference for large models.",
                "capabilities": ["cuda", "gpu", "scaling"],
                "cost": 2.0,
                "latency": 70.0,
            },
            {
                "name": "opencode-serve",
                "description": "OpenCode-based serving for code-centric tasks and experimentation.",
                "capabilities": ["code", "execution", "testing"],
                "cost": 0.85,
                "latency": 110.0,
            },
            {
                "name": "baidu",
                "description": "Baidu AI services with strong natural language capabilities.",
                "capabilities": ["nlp", "search", "speech"],
                "cost": 0.75,
                "latency": 140.0,
            },
            {
                "name": "generic-fallback-1",
                "description": "Fallback provider offering broad capabilities for general tasks.",
                "capabilities": ["text", "code", "image"],
                "cost": 0.5,
                "latency": 200.0,
            },
            {
                "name": "generic-fallback-2",
                "description": "Another generic fallback provider for resilience in routing decisions.",
                "capabilities": ["text", "code", "translation"],
                "cost": 0.5,
                "latency": 210.0,
            },
        ]
        profiles: List[ModelProfile] = []
        for p in providers:
            cap_text = ", ".join(p["capabilities"])
            full_text = f"{p['description']} {cap_text}"
            embedding = self._encode(full_text)
            profiles.append(
                ModelProfile(
                    name=p["name"],
                    description=p["description"],
                    capabilities=p["capabilities"],
                    embedding=embedding,
                    cost_yuan_per_1k=float(p["cost"]),
                    avg_latency_ms=float(p["latency"]),
                )
            )
        return profiles


# Singleton: a module-level scorer instance
_scorer: Optional[EmbeddingScorer] = None


def get_embedding_scorer() -> EmbeddingScorer:
    """Return a singleton EmbeddingScorer instance."""
    global _scorer
    if _scorer is None:
        _scorer = EmbeddingScorer(dim=128)
    return _scorer


__all__ = ["ModelProfile", "EmbeddingScorer", "get_embedding_scorer"]
