"""Sticky Layer Election with Continuous Attractor stabilization.

Based on: Representation Transfer via Invariant Input-driven Continuous
  Attractors for Fast Domain Adaptation (Communications Biology, 2026)

Core insight: Provider election converges to stable attractor states.
  Same intent with different phrasing → same attractor basin.
  Small input perturbations don't cause unnecessary re-elections.

Architecture:
  L0 (primary)    → cheapest + fastest
  L1 (fallback)   → balanced
  L2 (reasoning)  → highest reasoning score
  L3 (creative)   → highest quality
  L4 (emergency)  → most survivable

Attractor Basin:
  Each elected provider creates an attractor basin — neighboring
  providers in the same family/tier that share similar characteristics.
  On failure, basin members are tried first before full re-election.
  Only when entire basin fails → re-elect the layer.

Flow:
  Startup → elect all 5 layers → compute attractor basins → lock
  Request → use L0; fail → try L0 basin → fail → try L1 → ... L4
  Layer fail → try basin members → all fail → re-elect layer → new basin

Integration:
  election = get_sticky_election()
  await election.elect_all()
  binding = election.get_for_request(0, intent="weather query")
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class LayerBinding:
    """A locked provider + its attractor basin."""
    layer: int
    provider_name: str
    model: str = ""
    elected_at: float = 0.0
    failure_count: int = 0
    success_count: int = 0
    last_error: str = ""
    degraded: bool = False
    # Continuous attractor basin: same-family providers that can substitute
    attractor_basin: list[str] = field(default_factory=list)
    basin_failures: dict[str, int] = field(default_factory=dict)


class StickyElection:
    """Startup-elected provider layers with attractor-based fallback.

    Each layer's provider forms an attractor basin — neighboring providers
    that share the same base family or tier. On failure, basin members
    are tried first (they're within the same attractor), avoiding unnecessary
    full re-elections for minor perturbations.
    """

    LAYER_COUNT = 5
    LAYER_NAMES = {0: "primary", 1: "fallback", 2: "reasoning", 3: "creative", 4: "emergency"}
    LAYER_DEFAULTS = {
        0: ("deepseek", "deepseek-v4-flash"),    # fast/cheap
        1: ("deepseek", "deepseek-v4-flash"),    # retry same model
        2: ("deepseek", "deepseek-v4-pro"),      # deep reasoning
        3: ("deepseek", "deepseek-v4-pro"),      # high quality
        4: ("deepseek", "deepseek-v4-flash"),    # reliable baseline
    }
    EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"
    LAYER_DOMAINS = {
        0: ["general", "chat", "conversation", "qa"],
        1: ["search", "knowledge", "retrieval", "lookup"],
        2: ["code", "analysis", "reasoning", "math", "debug", "planning"],
        3: ["creative", "writing", "generation", "translation", "summarization"],
        4: ["emergency", "long_context", "multimodal", "all"],
    }
    DOMAIN_TO_LAYER = {}
    for layer, domains in LAYER_DOMAINS.items():
        for domain in domains:
            DOMAIN_TO_LAYER[domain] = layer

    _instance: Optional["StickyElection"] = None
    _lock = threading.Lock()

    def __init__(self, tree_llm=None):
        self._tree = tree_llm
        self._layers: dict[int, LayerBinding] = {}
        self._lock = threading.RLock()
        self._initialized = False
        self._layer_prototypes: dict[int, list[float]] = {}  # layer → embedding

    @classmethod
    def instance(cls, tree_llm=None) -> "StickyElection":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = StickyElection(tree_llm)
        return cls._instance

    # ═══ Intent → Layer Mapping (unified: keyword + semantic) ═════

    def classify_intent(self, query: str) -> int:
        """Map a query to a layer (0-4) via embedding similarity.

        Uses text_to_embedding() from task_vector_geometry.
        Each layer has a prototype embedding (computed once on first call).
        Query embedding is compared to all prototypes via cosine similarity.
        Falls back to keyword matching if embedding unavailable.
        """
        q = (query or "").lower()

        # Primary: embedding-based classification
        try:
            from ..dna.task_vector_geometry import text_to_embedding
            q_emb = text_to_embedding(query)

            if not self._layer_prototypes:
                self._build_prototypes(text_to_embedding)

            best_layer = 0
            best_sim = -1.0
            for layer, proto_emb in self._layer_prototypes.items():
                sim = self._cosine_similarity(q_emb, proto_emb)
                if sim > best_sim:
                    best_sim = sim
                    best_layer = layer

            if best_sim > 0.1:
                return best_layer
        except Exception:
            pass

        # Fallback: keyword matching (fast, works without embedding model)
        return self._classify_keywords(q)

    def _build_prototypes(self, embed_fn):
        """Build prototype embeddings for each layer from domain descriptions."""
        prototypes = {}
        domain_descriptions = {
            0: "hello chat conversation general question help explain what is how to",
            1: "search find lookup query retrieve knowledge information web",
            2: "code debug fix implement refactor analyze reason compare evaluate algorithm function class import",
            3: "write create generate translate summarize rewrite compose poem story email report",
            4: "emergency critical urgent fallback any domain",
        }
        for layer, desc in domain_descriptions.items():
            self._layer_prototypes[layer] = embed_fn(desc)
        return prototypes

    def _classify_keywords(self, q: str) -> int:
        """Keyword-based fallback classification (CN + EN)."""
        import re
        scores = {l: 0.0 for l in range(self.LAYER_COUNT)}
        kw = {
            # L2 reasoning
            "fix": 2, "debug": 2, "refactor": 2, "implement": 2, "optimize": 2,
            "analyze": 2, "reason": 2, "compare": 2, "evaluate": 2,
            "修复": 2, "调试": 2, "实现": 2, "分析": 2, "优化": 2, "重构": 2,
            "排查": 2, "对比": 2, "评估": 2, "检查": 2, "测试": 2,
            # L1 fallback/search
            "search": 1, "find": 1, "lookup": 1, "retrieve": 1, "query": 1,
            "搜索": 1, "查找": 1, "检索": 1, "查询": 1, "寻找": 1,
            # L3 creative
            "write": 3, "create": 3, "generate": 3, "translate": 3,
            "summarize": 3, "rewrite": 3, "compose": 3,
            "写": 3, "创建": 3, "生成": 3, "翻译": 3, "总结": 3, "重写": 3,
            "创作": 3, "编写": 3, "作曲": 3, "报告": 3, "诗歌": 3, "文章": 3,
            # L0 primary/chat
            "chat": 0, "hello": 0, "help": 0, "explain": 0,
            "你好": 0, "帮助": 0, "解释": 0, "是什么": 0, "怎么": 0,
        }
        for k, layer in kw.items():
            if k in q:
                scores[layer] += 1.0
        code = re.findall(r'\b(def|class|import|function|api|http|sql|json|csv|xml|regex|代码|函数|接口)\b', q)
        if code:
            scores[2] += len(code) * 0.5
        best = max(scores.values())
        if best == 0:
            return 0
        return max((l for l, s in scores.items() if s == best))

    @staticmethod
    def _cosine_similarity(a, b) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def intent_name(self, query: str) -> str:
        """Human-readable intent name for a query."""
        layer = self.classify_intent(query)
        return self.LAYER_NAMES[layer]

    async def elect_all(self) -> dict[int, LayerBinding]:
        """Full L0-L4 election + attractor basin computation."""
        with self._lock:
            for layer in range(self.LAYER_COUNT):
                binding = await self._elect_layer(layer)
                binding.attractor_basin = self._compute_basin(binding)
                self._layers[layer] = binding
                logger.info(
                    f"StickyElection L{layer} ({self.LAYER_NAMES[layer]}): "
                    f"{binding.provider_name}/{binding.model} "
                    f"[basin={len(binding.attractor_basin)}]"
                )
            self._initialized = True
            return dict(self._layers)

    async def reelect_layer(self, layer: int) -> LayerBinding:
        """Re-elect a single layer + recompute its attractor basin."""
        with self._lock:
            old = self._layers.get(layer)
            binding = await self._elect_layer(layer, exclude=old.provider_name if old else "")
            binding.attractor_basin = self._compute_basin(binding)
            self._layers[layer] = binding
            if old:
                logger.warning(
                    f"StickyElection L{layer} re-elected: "
                    f"{old.provider_name}→{binding.provider_name} "
                    f"(old failures={old.failure_count}, basin exhausted={len(old.basin_failures)})"
                )
            return binding

    async def _elect_layer(self, layer: int, exclude: str = "") -> LayerBinding:
        """Elect provider for a layer using pre-configured defaults or scoring."""
        candidates = self._get_candidates()

        # Use LAYER_DEFAULTS if no runtime scoring data accumulated
        default = self.LAYER_DEFAULTS.get(layer, ("deepseek", ""))
        has_scoring = any(
            c.get("success_rate", 0.5) != 0.5 or c.get("reasoning_score", 0) > 0
            for c in candidates
        )

        if not has_scoring:
            provider_name, model = default
            return LayerBinding(layer=layer, provider_name=provider_name,
                               model=model, elected_at=time.time())

        # Scoring-based election (runs after history accumulated)
        if exclude:
            candidates = [c for c in candidates if c.get("name") != exclude]
        if not candidates:
            return LayerBinding(layer=layer, provider_name=default[0],
                               model=default[1], elected_at=time.time())
            best = min(candidates, key=lambda c: (c.get("cost", 999), c.get("avg_latency_ms", 9999)))
        elif layer == 1:
            scored = [(c, c.get("success_rate", 0) * 0.6 + (1 - c.get("avg_latency_ms", 0) / 10000) * 0.4) for c in candidates]
            best = max(scored, key=lambda x: x[1])[0]
        elif layer == 2:
            best = max(candidates, key=lambda c: c.get("reasoning_score", 0) or c.get("capability_score", 0))
        elif layer == 3:
            best = max(candidates, key=lambda c: c.get("quality_score", 0) or c.get("success_rate", 0))
        else:
            best = max(candidates, key=lambda c: c.get("survivability", 0) or c.get("success_rate", 0))

        return LayerBinding(
            layer=layer,
            provider_name=best.get("name", "unknown"),
            model=best.get("model", best.get("default_model", "")),
            elected_at=time.time(),
        )

    # ═══ Attractor Basin (continuous attractor network) ═══════════

    def _compute_basin(self, binding: LayerBinding) -> list[str]:
        """Compute attractor basin — providers in the same family/tier.

        Two providers share an attractor if:
          - Same base provider family (e.g., deepseek→deepseek-r1)
          - OR same tier (flash/pro/reasoning/small)
          - OR similar capability profile (<0.3 distance)

        Basin members can substitute for the elected provider
        without triggering a full layer re-election.
        """
        basin = []
        candidates = self._get_candidates()
        elected = next((c for c in candidates if c.get("name") == binding.provider_name), {})

        for c in candidates:
            name = c.get("name", "")
            if name == binding.provider_name:
                continue

            # Same base family (e.g., deepseek + deepseek-r1)
            elected_base = binding.provider_name.split("-")[0]
            candidate_base = name.split("-")[0]
            if elected_base == candidate_base and elected_base:
                basin.append(name)
                continue

            # Same tier (flash/reasoning/pro/small)
            elected_tier = binding.provider_name.split("-")[-1] if "-" in binding.provider_name else ""
            candidate_tier = name.split("-")[-1] if "-" in name else ""
            if elected_tier and elected_tier == candidate_tier:
                basin.append(name)
                continue

            # Similar capability (cosine distance < 0.3)
            if self._capability_distance(elected, c) < 0.3:
                basin.append(name)
                continue

        return basin[:5]  # max 5 basin members

    @staticmethod
    def _capability_distance(a: dict, b: dict) -> float:
        """Distance between two providers' capability profiles (0-1)."""
        dims = ["success_rate", "reasoning_score", "capability_score", "quality_score"]
        diff = sum(abs(a.get(d, 0) - b.get(d, 0)) for d in dims)
        return diff / max(len(dims), 1)

    # ═══ Provider Access ═══════════════════════════════════════════

    def get_for_request(self, layer: int | None = None,
                        intent: str = "") -> tuple[str, str, bool, int]:
        """Get provider for a request. Returns (provider_name, model, is_primary, layer).

        If layer is None: auto-classify intent → layer via keyword + semantic.
        Intent is the raw query string — same embedding used for both
        classification and provider matching.
        """
        if layer is None and intent:
            layer = self.classify_intent(intent)
        elif layer is None:
            layer = 0

        binding = self._layers.get(layer)
        if not binding:
            return "", "", False, layer

        # Primary: elected provider
        if not binding.degraded or binding.basin_failures.get(binding.provider_name, 0) < 2:
            return binding.provider_name, binding.model, True, layer

        # Basin fallback: try attractor neighbors
        for basin_name in binding.attractor_basin:
            basin_fails = binding.basin_failures.get(basin_name, 0)
            if basin_fails < 2:
                return basin_name, self._get_model(basin_name), False, layer

        # All basin members exhausted
        return "", "", False, layer

    def mark_failure(self, layer: int, provider_name: str = "", error: str = ""):
        """Mark a provider as failed at a layer."""
        with self._lock:
            if layer not in self._layers:
                return
            binding = self._layers[layer]
            binding.failure_count += 1
            binding.last_error = error

            if provider_name:
                fails = binding.basin_failures.get(provider_name, 0) + 1
                binding.basin_failures[provider_name] = fails

            # Degrade if primary provider has 2+ failures
            if binding.failure_count >= 2:
                binding.degraded = True
                logger.warning(
                    f"StickyElection L{layer} DEGRADED: {binding.provider_name} "
                    f"(basin exhausted={len([k for k,v in binding.basin_failures.items() if v>=2])}/{len(binding.attractor_basin)})"
                )

    def mark_success(self, layer: int, provider_name: str = ""):
        """Mark success — reduces failure count for recovery."""
        with self._lock:
            binding = self._layers.get(layer)
            if not binding:
                return
            binding.success_count += 1
            if binding.failure_count > 0:
                binding.failure_count = max(0, binding.failure_count - 1)
            if provider_name and provider_name in binding.basin_failures:
                binding.basin_failures[provider_name] = max(
                    0, binding.basin_failures[provider_name] - 1
                )
            # Auto-recover if failures dropped below threshold
            if binding.failure_count < 2 and binding.degraded:
                binding.degraded = False
                logger.info(f"StickyElection L{layer} RECOVERED: {binding.provider_name}")

    def is_degraded(self, layer: int) -> bool:
        binding = self._layers.get(layer)
        return binding.degraded if binding else False

    def needs_reelection(self, layer: int) -> bool:
        """Check if the layer needs re-election (all basin members exhausted)."""
        binding = self._layers.get(layer)
        if not binding:
            return True
        all_exhausted = all(
            binding.basin_failures.get(name, 0) >= 2
            for name in [binding.provider_name] + binding.attractor_basin
        )
        return binding.degraded and all_exhausted

    # ═══ Embedding ══════════════════════════════════════════════════

    def _get_embedding(self, text: str) -> list[float]:
        """Get text embedding. Tries bge-large-zh first, falls back to hash."""
        if not getattr(self, '_embed_model', None):
            try:
                from sentence_transformers import SentenceTransformer
                self._embed_model = SentenceTransformer(
                    self.EMBEDDING_MODEL, cache_folder="./models")
            except Exception:
                self._embed_model = None
        if self._embed_model:
            try:
                return self._embed_model.encode(text).tolist()
            except Exception:
                pass
        try:
            from ..dna.task_vector_geometry import text_to_embedding
            return text_to_embedding(text)
        except Exception:
            return [0.0] * 128

    # ═══ Internal ═══════════════════════════════════════════════════

    def _get_candidates(self) -> list[dict]:
        candidates = []
        try:
            if self._tree and hasattr(self._tree, '_providers'):
                for name, p in self._tree._providers.items():
                    candidates.append({
                        "name": name,
                        "model": getattr(p, 'default_model', ''),
                        "success_rate": getattr(p, 'success_rate', 0.5),
                        "avg_latency_ms": getattr(p, 'avg_latency_ms', 1000.0),
                        "cost": getattr(p, 'cost_per_1k', 0.0),
                        "reasoning_score": getattr(p, 'reasoning_score', 0.0),
                        "capability_score": getattr(p, 'capability_score', 0.0),
                        "quality_score": getattr(p, 'quality_score', 0.0),
                        "survivability": getattr(p, 'survivability', 0.5),
                    })
        except Exception as e:
            logger.debug(f"StickyElection candidates: {e}")
        return candidates

    def _get_model(self, provider_name: str) -> str:
        candidates = self._get_candidates()
        for c in candidates:
            if c.get("name") == provider_name:
                return c.get("model", "")
        return ""

    # ═══ Stats ═════════════════════════════════════════════════════

    def stats(self) -> dict:
        return {
            "initialized": self._initialized,
            "layers": {
                str(l): {
                    "provider": b.provider_name,
                    "model": b.model,
                    "degraded": b.degraded,
                    "failures": b.failure_count,
                    "successes": b.success_count,
                    "basin_size": len(b.attractor_basin),
                    "basin_exhausted": sum(1 for v in b.basin_failures.values() if v >= 2),
                    "last_error": b.last_error[:100],
                    "elected_at": b.elected_at,
                }
                for l, b in self._layers.items()
            },
        }


_sticky: Optional[StickyElection] = None


def get_sticky_election(tree_llm=None) -> StickyElection:
    global _sticky
    if _sticky is None or tree_llm:
        _sticky = StickyElection(tree_llm)
    return _sticky
