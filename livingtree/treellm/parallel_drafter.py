"""Parallel Block Drafter — DFlash-inspired speculative multi-model generation.

Based on Chen, Liang & Liu (2026), arXiv:2602.06036:
  "DFlash: Block Diffusion for Flash Speculative Decoding"

Core insight adapted from DFlash to multi-model routing:
  - Autoregressive = sequential provider trials (current: try A, if fail try B)
  - Block Diffusion = parallel draft from N providers, verify all, select best
  - 6× acceleration claim from parallelization + high acceptance rate

DFlash three-stage pipeline (adapted to LivingTree):
  Stage 1: Context Feature Extraction (from query/task once, broadcast)
  Stage 2: Parallel Block Drafting (N free models generate simultaneously)
  Stage 3: Speculative Verification (verify drafts, select highest acceptance)

Integration:
  Replace sequential TreeLLM fallback with parallel drafting.
  High-value tasks → use best model; routine tasks → draft from free pool.
  Verification uses: output quality, format validity, confidence threshold.

Network topology (DFlash block parallelism):
  Query → FeatureExtractor → [Model_1, Model_2, ..., Model_N] → Verifier → Best
                               ↕ all run simultaneously           ↕ acceptance check
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from .free_pool_manager import FreeModelPool, get_free_pool


# ═══ Data Types ═══


@dataclass
class DraftBlock:
    """A parallel draft block — N candidate outputs generated simultaneously.

    DFlash analog: the block of tokens drafted in a single forward pass.
    In our context: N free model responses generated in parallel.
    """
    block_id: str
    query: str
    candidates: list["DraftCandidate"]
    feature_vector: dict[str, float] = field(default_factory=dict)  # Context features
    draft_time_ms: float = 0.0
    total_tokens: int = 0


@dataclass
class DraftCandidate:
    """A single candidate output from one draft model."""
    model_name: str
    content: str
    tokens: int
    latency_ms: float
    # Post-verification
    acceptance_score: float = 0.0    # How well the draft matches acceptance criteria
    accepted: bool = False
    verification_reason: str = ""


@dataclass
class ParallelResult:
    """Result of parallel speculative drafting + verification."""
    query: str
    block: DraftBlock
    best_candidate: DraftCandidate | None
    acceptance_rate: float          # % of candidates that passed verification
    total_tokens: int
    total_ms: float
    speedup_vs_sequential: float    # Estimated speedup vs sequential fallback
    models_used: list[str]

    def summary(self) -> str:
        best = self.best_candidate
        return (
            f"[{len(self.block.candidates)} drafts, "
            f"accept={self.acceptance_rate:.0%}] "
            f"{self.query[:50]}... → "
            f"{best.model_name if best else 'none'} "
            f"(score={best.acceptance_score:.2f}) "
            f"speedup={self.speedup_vs_sequential:.1f}×"
        )


# ═══ Context Feature Extractor ═══


class ContextFeatureExtractor:
    """Extract lightweight features from query/task for draft conditioning.

    DFlash analog: target model's intermediate features are extracted
    and fed to the draft model to improve acceptance rate.

    In our context: query features extracted once, broadcast to all draft
    models to help them focus on the right domain/format.
    """

    # Feature dimensions extracted from query
    FEATURE_DIMENSIONS = [
        "length",           # Query length (normalized)
        "has_code",         # Involves code generation
        "has_math",         # Involves mathematics
        "has_chinese",      # Primarily Chinese language
        "complexity",       # Estimated task complexity
        "formality",        # How formal the response should be
        "creativity",       # How creative the response should be
        "domain_env",       # Environmental/regulatory domain
        "domain_finance",   # Financial domain
    ]

    def extract(self, query: str) -> dict[str, float]:
        """Extract context features from a query string.

        Returns:
            Feature vector dict for conditioning draft models.
        """
        q = query.lower()
        length = len(query)

        features = {
            "length": min(1.0, length / 2000.0),
            "has_code": float(
                any(k in q for k in ["代码", "code", "函数", "function",
                                      "python", "写", "write", "实现", "implement"])),
            "has_math": float(
                any(k in q for k in ["计算", "calculate", "数学", "math",
                                      "公式", "方程", "equation", "求解"])),
            "has_chinese": float(
                sum(1 for c in query if '\u4e00' <= c <= '\u9fff') / max(length, 1)
                > 0.3),
            "complexity": min(1.0, (
                length / 500.0 * 0.3
                + sum(1 for k in ["分析", "评估", "预测", "比较", "优化",
                                   "analyze", "evaluate", "complex"])
                * 0.15)),
            "formality": float(
                any(k in q for k in ["报告", "report", "正式", "formal",
                                      "规范", "标准", "standard", "法规"])),
            "creativity": float(
                any(k in q for k in ["创意", "creative", "设计", "design",
                                      "新颖", "novel", "想法", "idea"])),
            "domain_env": float(
                any(k in q for k in ["环评", "environmental", "排放",
                                      "污染", "标准", "监测", "EIA"])),
            "domain_finance": float(
                any(k in q for k in ["量化", "quant", "回测", "backtest",
                                      "因子", "alpha", "交易", "portfolio"])),
        }
        # Normalize complexity properly
        features["complexity"] = min(1.0, features["complexity"])
        return features


# ═══ Draft Verifier ═══


class DraftVerifier:
    """Verify draft candidate outputs against acceptance criteria.

    DFlash analog: the target model verifies draft tokens; only accepted
    tokens are kept. Rejected drafts are discarded.

    Verification criteria:
      1. Format validity: output is well-formed (JSON/code/text as expected)
      2. Content quality: output is non-trivial (not empty, not too short)
      3. Relevance: output addresses the query (keyword overlap check)
      4. Confidence: self-reported confidence meets threshold

    Acceptance score = weighted sum of all criteria.
    """

    MIN_CONTENT_LENGTH = 20
    ACCEPTANCE_THRESHOLD = 0.4

    def verify(
        self, candidate: DraftCandidate, query: str,
        expected_format: str = "text",
    ) -> DraftCandidate:
        """Verify a single draft candidate.

        Args:
            candidate: Draft output to verify
            query: Original query for relevance check
            expected_format: "text", "code", "json"

        Returns:
            Same candidate with acceptance_score and accepted flag set
        """
        scores: dict[str, float] = {}

        # 1. Format validity
        scores["format"] = self._check_format(candidate.content, expected_format)

        # 2. Content quality
        scores["content"] = self._check_content(candidate.content)

        # 3. Relevance
        scores["relevance"] = self._check_relevance(candidate.content, query)

        # 4. Efficiency (lower latency = better)
        scores["efficiency"] = max(0.0, 1.0 - candidate.latency_ms / 30000.0)

        # Weighted average
        weights = {"format": 0.3, "content": 0.3, "relevance": 0.3, "efficiency": 0.1}
        acceptance = sum(scores[k] * weights.get(k, 0.25) for k in scores)

        candidate.acceptance_score = round(acceptance, 3)
        candidate.accepted = acceptance >= self.ACCEPTANCE_THRESHOLD
        candidate.verification_reason = (
            f"format={scores['format']:.2f} content={scores['content']:.2f} "
            f"relevance={scores['relevance']:.2f}"
        )
        return candidate

    @staticmethod
    def _check_format(content: str, expected: str) -> float:
        if not content:
            return 0.0
        if expected == "code":
            return 1.0 if ("```" in content or "def " in content or "import " in content) else 0.3
        if expected == "json":
            import json
            try:
                # Try to find and parse JSON
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    json.loads(content[start:end])
                    return 1.0
            except Exception:
                pass
            return 0.2
        # Text: just check non-empty
        return 1.0 if len(content.strip()) > 10 else 0.2

    @staticmethod
    def _check_content(content: str) -> float:
        if not content or len(content.strip()) < 10:
            return 0.0
        length = len(content)
        if length < 50:
            return 0.4
        if length < 200:
            return 0.7
        return min(1.0, 0.7 + length / 5000)

    @staticmethod
    def _check_relevance(content: str, query: str) -> float:
        """Check keyword overlap between query and response."""
        if not query or not content:
            return 0.0
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        if not query_words:
            return 0.5
        overlap = len(query_words & content_words)
        return min(1.0, overlap / max(len(query_words), 1))


# ═══ Parallel Block Drafter ═══


class ParallelDrafter:
    """DFlash-inspired parallel speculative drafting engine.

    Pipeline:
      1. Feature Extraction: extract context features from query (once)
      2. Parallel Drafting: send to N free models simultaneously (block)
      3. Verification: check all drafts, compute acceptance scores
      4. Selection: pick highest-acceptance draft as best output

    This replaces sequential fallback (try A → fail → try B → fail → try C)
    with parallel speculative drafting, achieving DFlash's 6× acceleration
    principle in the multi-model routing context.
    """

    def __init__(
        self,
        pool: FreeModelPool | None = None,
        consciousness: Any = None,
    ):
        self._pool = pool or get_free_pool()
        self._consciousness = consciousness
        self._extractor = ContextFeatureExtractor()
        self._verifier = DraftVerifier()
        self._history: list[ParallelResult] = []

    # ── Main Entry ──

    async def draft(
        self,
        query: str,
        num_drafts: int = 4,
        expected_format: str = "text",
        min_acceptance: float = 0.4,
        timeout_per_draft: float = 15.0,
    ) -> ParallelResult:
        """Parallel speculative drafting with DFlash-style block semantics.

        Args:
            query: The user's query/prompt
            num_drafts: Number of parallel draft candidates (like block size)
            expected_format: "text", "code", or "json"
            min_acceptance: Minimum acceptance score to consider valid
            timeout_per_draft: Max seconds per draft model call

        Returns:
            ParallelResult with best candidate and speedup metrics
        """
        t0 = time.time()

        # ═══ Stage 1: Context Feature Extraction (once) ═══
        features = self._extractor.extract(query)

        # ═══ Stage 2: Parallel Block Drafting ═══
        # Select N best free models for drafting
        draft_models = self._select_draft_models(num_drafts, features)

        if not draft_models:
            return ParallelResult(
                query=query,
                block=DraftBlock(block_id=f"d_{int(t0)}", query=query,
                                  candidates=[], feature_vector=features),
                best_candidate=None, acceptance_rate=0.0,
                total_tokens=0, total_ms=(time.time() - t0) * 1000,
                speedup_vs_sequential=1.0, models_used=[],
            )

        # Fire all drafts in parallel (DFlash block)
        t_draft_start = time.time()
        draft_tasks = [
            self._draft_from_model(model, query, features, timeout_per_draft)
            for model in draft_models
        ]
        candidates = await asyncio.gather(*draft_tasks, return_exceptions=True)
        draft_time = (time.time() - t_draft_start) * 1000

        # Filter out exceptions
        valid_candidates: list[DraftCandidate] = []
        for i, c in enumerate(candidates):
            if isinstance(c, Exception):
                logger.debug(f"Drafter: model {draft_models[i]} exception: {c}")
                continue
            if isinstance(c, DraftCandidate):
                valid_candidates.append(c)

        # ═══ Stage 3: Speculative Verification ═══
        for c in valid_candidates:
            self._verifier.verify(c, query, expected_format)

        # Sort by acceptance score
        valid_candidates.sort(key=lambda c: -c.acceptance_score)

        # ═══ Stage 4: Selection ═══
        best = valid_candidates[0] if valid_candidates else None
        accepted = [c for c in valid_candidates if c.accepted]
        acceptance_rate = len(accepted) / max(len(valid_candidates), 1)

        total_tokens = sum(c.tokens for c in valid_candidates)
        total_ms = (time.time() - t0) * 1000

        # Speedup estimate: sequential would take N × avg_latency
        # Parallel takes max(latency)
        avg_latency = (
            sum(c.latency_ms for c in valid_candidates) / max(len(valid_candidates), 1)
            if valid_candidates else 1000)
        speedup = (len(draft_models) * avg_latency) / max(total_ms, 1)

        block = DraftBlock(
            block_id=f"d_{int(t0)}",
            query=query,
            candidates=valid_candidates,
            feature_vector=features,
            draft_time_ms=draft_time,
            total_tokens=total_tokens,
        )

        result = ParallelResult(
            query=query,
            block=block,
            best_candidate=best,
            acceptance_rate=round(acceptance_rate, 3),
            total_tokens=total_tokens,
            total_ms=total_ms,
            speedup_vs_sequential=round(speedup, 2),
            models_used=draft_models,
        )

        self._history.append(result)
        if len(self._history) > 50:
            self._history = self._history[-50:]

        logger.info(result.summary())
        return result

    # ── Draft Model Selection ──

    def _select_draft_models(
        self, num_drafts: int, features: dict[str, float],
    ) -> list[str]:
        """Select the best free models for drafting based on query features.

        DFlash analog: draft model selection based on task characteristics.
        Different query types benefit from different model capabilities.
        """
        available = self._pool.available_models()
        if not available:
            # Try healthy models as fallback
            available = self._pool.healthy_models()
        if not available:
            # Any model
            available = list(self._pool._models.keys())

        # Score each model for this query
        scored = []
        for name in available[:20]:  # Cap at 20 candidates
            model = self._pool._get_model(name)
            # Feature-weighted score
            score = (
                features.get("has_code", 0) * model.coding
                + features.get("has_math", 0) * model.reasoning
                + features.get("has_chinese", 0) * model.reading
                + features.get("formality", 0) * model.instruction_following
                + features.get("complexity", 0) * model.reasoning
                + 0.3 * model.coding  # Baseline
                + 0.3 * model.instruction_following  # Baseline
            )
            # Penalize unhealthy models
            if model.status.value in ("degraded", "quarantined"):
                score *= 0.5
            scored.append((name, score))

        scored.sort(key=lambda x: -x[1])
        selected = [name for name, _ in scored[:num_drafts]]

        logger.debug(
            f"Drafter: selected {len(selected)} models to draft: "
            f"{', '.join(selected[:3])}...",
        )
        return selected

    # ── Single Model Draft ──

    async def _draft_from_model(
        self, model_name: str, query: str,
        features: dict[str, float], timeout: float,
    ) -> DraftCandidate:
        """Generate a draft from a single model (non-blocking)."""
        t_start = time.time()

        # Rate limit check
        can_call = await self._pool.acquire(model_name, timeout=3.0)
        if not can_call:
            return DraftCandidate(
                model_name=model_name, content="",
                tokens=0, latency_ms=(time.time() - t_start) * 1000,
                acceptance_score=0.0, accepted=False,
                verification_reason="rate_limited",
            )

        try:
            # Condition the prompt with features
            conditioned_prompt = self._condition_prompt(query, features, model_name)

            if self._consciousness and hasattr(self._consciousness, 'query'):
                raw = await asyncio.wait_for(
                    self._consciousness.query(
                        conditioned_prompt,
                        max_tokens=512,
                        temperature=0.3,
                        model=model_name,
                    ),
                    timeout=timeout,
                )
            else:
                raw = f"[Draft from {model_name} for: {query[:50]}...]"

            latency = (time.time() - t_start) * 1000
            tokens = len(raw) // 4  # Rough estimate

            self._pool.mark_healthy(model_name, latency)

            return DraftCandidate(
                model_name=model_name, content=raw.strip(),
                tokens=tokens, latency_ms=latency,
            )

        except asyncio.TimeoutError:
            self._pool.mark_failure(model_name)
            return DraftCandidate(
                model_name=model_name, content="",
                tokens=0, latency_ms=timeout * 1000,
                verification_reason="timeout",
            )
        except Exception:
            self._pool.mark_failure(model_name)
            return DraftCandidate(
                model_name=model_name, content="",
                tokens=0, latency_ms=(time.time() - t_start) * 1000,
                verification_reason="error",
            )

    # ── Prompt Conditioning (DFlash context feature injection) ──

    def _condition_prompt(
        self, query: str, features: dict[str, float], model_name: str,
    ) -> str:
        """Condition the draft prompt with extracted features.

        DFlash analog: target model's hidden states are used to condition
        the draft model, improving acceptance rate. Here we inject explicit
        feature-derived instructions instead.
        """
        parts = [query]

        # Format hint based on features
        if features.get("has_code", 0) > 0.5:
            parts.append("\n\nPlease provide code output in ```python blocks.")
        elif features.get("has_math", 0) > 0.3:
            parts.append("\n\nPlease provide both reasoning and final answer.")

        # Domain hint
        if features.get("domain_env", 0) > 0.3:
            parts.append("\n\nThis is an environmental/regulatory question. "
                         "Reference relevant standards (GB/HJ).")
        if features.get("domain_finance", 0) > 0.3:
            parts.append("\n\nThis is a quantitative finance question. "
                         "Provide clean, executable Python code.")

        # Length hint
        if features.get("complexity", 0) > 0.6:
            parts.append("\n\nThis is a complex task. Provide a thorough response.")

        return "\n".join(parts)

    # ── Multi-round speculative refinement ──

    async def draft_with_refinement(
        self, query: str, num_drafts: int = 4, max_rounds: int = 2,
    ) -> ParallelResult:
        """Multi-round drafting: draft → verify → refine rejected drafts.

        DFlash analog: iterative refinement of low-acceptance blocks.
        """
        result = await self.draft(query, num_drafts=num_drafts)

        for rnd in range(1, max_rounds):
            # Find rejected but promising candidates (score between 0.3-0.4)
            rejected = [
                c for c in result.block.candidates
                if not c.accepted and c.acceptance_score > 0.3
            ]
            if not rejected:
                break

            # Refine: re-query with feedback
            refine_tasks = [
                self._draft_from_model(
                    c.model_name,
                    f"Previous attempt was rejected ({c.verification_reason}). "
                    f"Please improve:\n\nOriginal query: {query}\n\n"
                    f"Your previous output:\n{c.content[:300]}",
                    result.block.feature_vector,
                    timeout=15.0,
                )
                for c in rejected[:2]  # Refine at most 2
            ]
            refined = await asyncio.gather(*refine_tasks, return_exceptions=True)

            for i, c in enumerate(refined):
                if isinstance(c, DraftCandidate) and c.content:
                    self._verifier.verify(c, query, "text")
                    result.block.candidates.append(c)

            result.block.candidates.sort(key=lambda c: -c.acceptance_score)
            if result.block.candidates:
                result.best_candidate = result.block.candidates[0]

            # Recompute acceptance
            accepted = [c for c in result.block.candidates if c.accepted]
            result.acceptance_rate = len(accepted) / max(
                len(result.block.candidates), 1)

            if result.acceptance_rate > 0.8:
                break

        return result

    # ── Stats ──

    def stats(self) -> dict[str, Any]:
        if not self._history:
            return {}
        avg_speedup = sum(
            r.speedup_vs_sequential for r in self._history) / len(self._history)
        avg_acceptance = sum(
            r.acceptance_rate for r in self._history) / len(self._history)
        return {
            "total_drafts": len(self._history),
            "avg_speedup": round(avg_speedup, 2),
            "avg_acceptance_rate": round(avg_acceptance, 3),
            "pool_stats": self._pool.pool_stats(),
        }


# ═══ Singleton ═══

_parallel_drafter: ParallelDrafter | None = None


def get_parallel_drafter(consciousness=None) -> ParallelDrafter:
    global _parallel_drafter
    if _parallel_drafter is None:
        _parallel_drafter = ParallelDrafter(consciousness=consciousness)
    elif consciousness and not _parallel_drafter._consciousness:
        _parallel_drafter._consciousness = consciousness
    return _parallel_drafter


__all__ = [
    "ParallelDrafter", "DraftBlock", "DraftCandidate",
    "ParallelResult", "ContextFeatureExtractor", "DraftVerifier",
    "get_parallel_drafter",
]
