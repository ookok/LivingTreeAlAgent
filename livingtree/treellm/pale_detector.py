"""PALE Detector — Prompt-guided data Augmented haLlucination dEtection.

AAAI-26 (Li et al., HIT Shenzhen + Pengcheng Lab): Bolster Hallucination Detection
via Prompt-Guided Data Augmentation.

Two core innovations:
  1. Prompt-guided Data Augmentation (PDA): LLM generates BOTH truthful and
     hallucinated responses at low cost. 5 hallucination types:
       - fabricated_statistic:   Makes up specific numbers
       - fabricated_reference:   Cites non-existent sources
       - overgeneralization:     Overstates from narrow evidence
       - temporal_misalignment:  Confuses past/future events
       - false_causation:        Implies causation from correlation
  2. Contrastive Mahalanobis Score (CM Score): Models truthful vs hallucinated
     distributions in LLM activation space. Uses shrinkage covariance estimation
     for numerical stability. Detects hallucinations via activation-space distance
     rather than surface-level text patterns.

Integration:
  - HallucinationGuard defers to CM Score when activation signatures available
  - AdversarialSelfPlay generates contrastive pairs for dataset building
  - DreamPretrainer produces PALE contrastive data for LoRA fine-tuning
  - SynapseAggregator uses CM Score in cross-validation
  - DepthGrading uses CM Score as 9th dimension (SELF_CONSISTENCY_CM)
"""

from __future__ import annotations

import math
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class ActivationSignature:
    """Flattened hidden state from a specific LLM layer.

    Captures the model's internal representation at a point in generation,
    enabling distribution-level hallucination detection rather than
    surface-level text pattern matching.
    """
    layer_name: str
    hidden_states: list[float]
    token_positions: list[int] = field(default_factory=list)
    normalized: bool = False
    model_name: str = ""
    timestamp: float = field(default_factory=time.time)

    def as_array(self) -> "np.ndarray | None":
        if not HAS_NUMPY:
            return None
        return np.array(self.hidden_states, dtype=np.float32)


@dataclass
class ContrastivePair:
    """One query with both truthful and hallucinated responses."""
    query: str
    truthful_response: str
    hallucinated_response: str
    hallucination_type: str
    truthful_signature: ActivationSignature | None = None
    hallucinated_signature: ActivationSignature | None = None
    pair_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "query": self.query,
            "truthful_response": self.truthful_response,
            "hallucinated_response": self.hallucinated_response,
            "hallucination_type": self.hallucination_type,
        }


@dataclass
class CMScoreResult:
    """Result of CM Score computation for a single activation signature."""
    cm_score: float
    distance_to_truthful: float
    distance_to_hallucinated: float
    is_hallucination: bool
    confidence: float
    threshold_used: float


# ═══ Hallucination Injection Prompts ══════════════════════════════

HALLUCINATION_PROMPTS: dict[str, str] = {
    "fabricated_statistic": (
        "Rewrite the following answer to sound authoritative but fabricate "
        "one specific statistic (like '87.3% of users' or 'in 23 out of 30 cases').\n"
        "Keep the rest truthful. Only change the fabricated part.\n\n"
        "Original answer:\n{answer}\n\n"
        "Rewritten answer with fabricated statistic:"
    ),
    "fabricated_reference": (
        "Rewrite the following answer to cite a non-existent paper or source "
        "(e.g., 'According to Smith et al. (2023) in Nature...'). Make it sound "
        "credible but the reference does not actually exist.\n\n"
        "Original answer:\n{answer}\n\n"
        "Rewritten answer with fabricated reference:"
    ),
    "overgeneralization": (
        "Rewrite the following answer to overgeneralize from narrow evidence. "
        "Take one valid finding and claim it applies to ALL cases, despite no "
        "evidence for such broad application.\n\n"
        "Original answer:\n{answer}\n\n"
        "Overgeneralized answer:"
    ),
    "temporal_misalignment": (
        "Rewrite the following answer to confuse past and future events. "
        "Present something that hasn't happened yet as already established fact, "
        "or present historical information as upcoming.\n\n"
        "Original answer:\n{answer}\n\n"
        "Temporally misaligned answer:"
    ),
    "false_causation": (
        "Rewrite the following answer to imply causation from mere correlation. "
        "Take two things that happen together and claim one CAUSES the other, "
        "despite no causal evidence.\n\n"
        "Original answer:\n{answer}\n\n"
        "Answer with false causation:"
    ),
}


# ═══ PALEDataAugmenter ════════════════════════════════════════════


class PALEDataAugmenter:
    """Generates truthful+hallucinated contrastive pairs via prompt guidance.

    Uses LLM prompting to generate BOTH faithful and fabricated responses
    for the same query. 5 hallucination types are injected via specialized
    prompts. No human annotation required.
    """

    def __init__(self, hall_types: list[str] | None = None):
        self._hall_types = hall_types or list(HALLUCINATION_PROMPTS.keys())

    async def generate_contrastive_pair(
        self,
        query: str,
        truthful_context: str,
        chat_fn: Any,
        hall_type: str = "",
    ) -> ContrastivePair:
        hall_type = hall_type or self._pick_type()
        prompt = HALLUCINATION_PROMPTS[hall_type].format(answer=truthful_context)
        try:
            hallucinated = await chat_fn(prompt)
        except Exception as e:
            logger.warning(f"PALEDataAugmenter: generation failed: {e}")
            hallucinated = f"[hallucinated variant for {hall_type}]"
        return ContrastivePair(
            query=query,
            truthful_response=str(truthful_context),
            hallucinated_response=str(hallucinated),
            hallucination_type=hall_type,
        )

    async def generate_batch(
        self,
        queries: list[str],
        truthful_contexts: list[str],
        chat_fn: Any,
        n_per_query: int = 3,
    ) -> list[ContrastivePair]:
        pairs: list[ContrastivePair] = []
        for q, ctx in zip(queries, truthful_contexts):
            for _ in range(min(n_per_query, len(self._hall_types))):
                ht = self._pick_type()
                pair = await self.generate_contrastive_pair(q, ctx, chat_fn, ht)
                pairs.append(pair)
        logger.info(
            f"PALEDataAugmenter: {len(pairs)} contrastive pairs "
            f"({len(set(p.hallucination_type for p in pairs))} types)"
        )
        return pairs

    def generate_heuristic_pairs(
        self,
        queries: list[str],
        truthful_contexts: list[str],
        n_per_query: int = 3,
    ) -> list[ContrastivePair]:
        """Heuristic fallback generating contrastive pairs without LLM."""
        pairs: list[ContrastivePair] = []
        for q, ctx in zip(queries, truthful_contexts):
            for i in range(min(n_per_query, len(self._hall_types))):
                ht = self._hall_types[i]
                hall_resp = self._inject_heuristic_hallucination(ctx, ht)
                pairs.append(ContrastivePair(
                    query=q, truthful_response=ctx,
                    hallucinated_response=hall_resp, hallucination_type=ht,
                ))
        return pairs

    def _pick_type(self) -> str:
        import random
        return random.choice(self._hall_types)

    def _inject_heuristic_hallucination(self, text: str, hall_type: str) -> str:
        if hall_type == "fabricated_statistic":
            import random
            num = random.randint(60, 99)
            return f"{text}\n\nAccording to a {num}% benchmark survey conducted in 2025..."
        elif hall_type == "fabricated_reference":
            return f"{text}\n\nAs demonstrated by Zhang et al. (2024) in Journal of AI Research..."
        elif hall_type == "overgeneralization":
            return f"{text}\n\nThis principle holds universally across ALL domains without exception."
        elif hall_type == "temporal_misalignment":
            return f"{text}\n\nBy 2022, these capabilities had already been fully deployed at scale."
        elif hall_type == "false_causation":
            return f"{text}\n\nThe observed correlation directly proves that X causes Y in all cases."
        return text


# ═══ PALECMScorer ═════════════════════════════════════════════════


class PALECMScorer:
    """Contrastive Mahalanobis Score for activation-space hallucination detection.

    Models two distributions from LLM hidden states:
      - Truthful distribution: activations when generating faithful responses
      - Hallucinated distribution: activations when generating fabricated responses

    CM Score = distance to truthful centroid - distance to hallucinated centroid,
    computed in Mahalanobis space (accounting for covariance structure).

    Uses shrinkage covariance estimation for numerical stability with
    high-dimensional, sparse activation data (per PALE paper methodology).
    """

    def __init__(self, shrinkage: float = 0.1, threshold: float = 0.0):
        self._truthful_activations: list[list[float]] = []
        self._hallucinated_activations: list[list[float]] = []
        self._mean_truthful: "np.ndarray | None" = None
        self._mean_hallucinated: "np.ndarray | None" = None
        self._cov_pooled: "np.ndarray | None" = None
        self._cov_inv: "np.ndarray | None" = None
        self._shrinkage = shrinkage
        self._threshold = threshold
        self._fitted = False
        self._dim: int = 0

    def fit(
        self,
        truthful_sigs: list[ActivationSignature],
        hallucinated_sigs: list[ActivationSignature],
    ) -> None:
        if not HAS_NUMPY:
            logger.warning("PALECMScorer: numpy not available, using scalar fallback")
            self._truthful_activations = [s.hidden_states for s in truthful_sigs]
            self._hallucinated_activations = [s.hidden_states for s in hallucinated_sigs]
            self._fitted = True
            return

        truthful_arrs = [s.as_array() for s in truthful_sigs if s.as_array() is not None]
        hall_arrs = [s.as_array() for s in hallucinated_sigs if s.as_array() is not None]
        if not truthful_arrs or not hall_arrs:
            self._truthful_activations = [s.hidden_states for s in truthful_sigs]
            self._hallucinated_activations = [s.hidden_states for s in hallucinated_sigs]
            self._fitted = True
            return

        T = np.stack(truthful_arrs)
        H = np.stack(hallucinated_arrs)
        self._dim = T.shape[1]
        self._mean_truthful = T.mean(axis=0)
        self._mean_hallucinated = H.mean(axis=0)

        cov_t = np.cov(T, rowvar=False)
        cov_h = np.cov(H, rowvar=False)
        self._cov_pooled = (cov_t + cov_h) / 2.0

        target = np.trace(self._cov_pooled) / self._dim
        self._cov_pooled = (1.0 - self._shrinkage) * self._cov_pooled + self._shrinkage * target * np.eye(self._dim)

        try:
            self._cov_inv = np.linalg.pinv(self._cov_pooled)
        except np.linalg.LinAlgError:
            self._cov_inv = np.eye(self._dim) / max(np.trace(self._cov_pooled) / self._dim, 1e-6)

        self._fitted = True
        logger.info(
            f"PALECMScorer fitted: {len(truthful_sigs)}T + {len(hallucinated_sigs)}H, "
            f"dim={self._dim}, shrinkage={self._shrinkage:.2f}"
        )

    def cm_score(self, signature: ActivationSignature) -> float:
        if not self._fitted or self._mean_truthful is None or HAS_NUMPY and self._cov_inv is None:
            return self._scalar_fallback(signature)

        arr = signature.as_array()
        if arr is None:
            return self._scalar_fallback(signature)
        d_t = self._mahalanobis(arr, self._mean_truthful, self._cov_inv) if self._cov_inv is not None else float("inf")
        d_h = self._mahalanobis(arr, self._mean_hallucinated, self._cov_inv) if self._cov_inv is not None and self._mean_hallucinated is not None else float("inf")
        return float(d_t - d_h)

    def classify(self, signature: ActivationSignature, threshold: float | None = None) -> CMScoreResult:
        thresh = threshold if threshold is not None else self._threshold
        score = self.cm_score(signature)
        if not self._fitted:
            return CMScoreResult(
                cm_score=score, distance_to_truthful=0.0,
                distance_to_hallucinated=0.0, is_hallucination=False,
                confidence=0.0, threshold_used=thresh,
            )
        d_t = self._distance_to_truthful(signature)
        d_h = self._distance_to_hallucinated(signature)
        is_hall = score > thresh
        confidence = abs(score) / max(abs(d_t) + abs(d_h), 1e-6)
        return CMScoreResult(
            cm_score=score, distance_to_truthful=d_t,
            distance_to_hallucinated=d_h, is_hallucination=is_hall,
            confidence=min(1.0, confidence), threshold_used=thresh,
        )

    def _distance_to_truthful(self, signature: ActivationSignature) -> float:
        if not HAS_NUMPY or self._mean_truthful is None or self._cov_inv is None:
            return 0.0
        arr = signature.as_array()
        if arr is None:
            return 0.0
        return float(self._mahalanobis(arr, self._mean_truthful, self._cov_inv))

    def _distance_to_hallucinated(self, signature: ActivationSignature) -> float:
        if not HAS_NUMPY or self._mean_hallucinated is None or self._cov_inv is None:
            return 0.0
        arr = signature.as_array()
        if arr is None:
            return 0.0
        return float(self._mahalanobis(arr, self._mean_hallucinated, self._cov_inv))

    @staticmethod
    def _mahalanobis(x: "np.ndarray", mu: "np.ndarray", cov_inv: "np.ndarray") -> float:
        delta = x - mu
        return float(np.sqrt(max(0.0, delta @ cov_inv @ delta)))

    def _scalar_fallback(self, signature: ActivationSignature) -> float:
        if not self._truthful_activations:
            return 0.0
        t_avg = sum(sum(v) / max(len(v), 1) for v in self._truthful_activations) / max(len(self._truthful_activations), 1)
        s_avg = sum(signature.hidden_states) / max(len(signature.hidden_states), 1)
        return float(t_avg - s_avg)

    def is_fitted(self) -> bool:
        return self._fitted and len(self._truthful_activations) > 0

    def get_stats(self) -> dict[str, Any]:
        return {
            "fitted": self._fitted,
            "n_truthful": len(self._truthful_activations),
            "n_hallucinated": len(self._hallucinated_activations),
            "dim": self._dim,
            "shrinkage": self._shrinkage,
            "threshold": self._threshold,
        }


# ═══ Activation Extraction ════════════════════════════════════════


def extract_text_activation(text: str, dim: int = 128) -> ActivationSignature:
    """Extract a pseudo-activation signature from text content.

    Simulates hidden-state extraction when real LLM internals are not available.
    Uses character n-gram frequencies and structural features as proxy for
    actual neural activations. PALE paper: CM Score can also work with
    embedding-based signatures as a practical approximation.

    This is the fallback path when no real model activations are available.
    """
    hidden = [0.0] * dim
    if not text:
        return ActivationSignature(layer_name="embedding", hidden_states=hidden)

    chars = list(text.lower())
    txt_n = len(chars)

    for i, ch in enumerate(chars):
        idx = (ord(ch) * 31 + i * 17) % dim
        hidden[idx] += 1.0 / max(txt_n, 1)

    for n in range(1, 4):
        for i in range(txt_n - n + 1):
            ngram = text[i:i + n]
            nh = sum(ord(c) for c in ngram)
            idx = (nh * 37 + n * 13) % dim
            hidden[idx] += n * 0.1 / max(txt_n, 1)

    words = re.findall(r'\w+', text.lower())
    for w in words:
        wh = sum(ord(c) for c in w)
        idx = wh % dim
        hidden[idx] += 0.15 / max(txt_n, 1)

    sent_count = max(1, text.count('.') + text.count('!') + text.count('?') + text.count('\n'))
    hidden[dim // 2] += sent_count * 0.02
    hidden[dim // 2 + 1] += len(words) / max(txt_n, 1) * 0.5

    nums = re.findall(r'\d+\.?\d*', text)
    if nums:
        hidden[dim // 4] += len(nums) * 0.05

    total = math.sqrt(sum(v * v for v in hidden))
    if total > 0:
        hidden = [v / total for v in hidden]

    return ActivationSignature(
        layer_name="text_embedding",
        hidden_states=hidden,
        normalized=True,
    )


# ═══ Shrinkage Covariance ═════════════════════════════════════════


def compute_shrunken_covariance(
    activations: "np.ndarray",
    shrinkage: float = 0.1,
) -> "np.ndarray":
    """Shrinkage covariance estimator for numerical stability.

    PALE paper: when activation dimension is high and samples are sparse,
    the sample covariance matrix is ill-conditioned. The shrinkage estimator
    blends the sample covariance with a scaled identity matrix (Ledoit-Wolf style).

    cov_shrunk = (1 - shrinkage) * cov_sample + shrinkage * target * I
    target = trace(cov_sample) / dim

    This ensures the covariance is always invertible (positive definite),
    which is required for Mahalanobis distance computation.
    """
    if not HAS_NUMPY:
        return activations
    dim = activations.shape[1]
    cov_sample = np.cov(activations, rowvar=False)
    target = np.trace(cov_sample) / dim
    return (1.0 - shrinkage) * cov_sample + shrinkage * target * np.eye(dim)


# ═══ Module Singleton ══════════════════════════════════════════════

_pale_scorer: PALECMScorer | None = None
_pale_augmenter: PALEDataAugmenter | None = None


def get_pale_scorer(shrinkage: float = 0.1) -> PALECMScorer:
    global _pale_scorer
    if _pale_scorer is None:
        _pale_scorer = PALECMScorer(shrinkage=shrinkage)
    return _pale_scorer


def get_pale_augmenter() -> PALEDataAugmenter:
    global _pale_augmenter
    if _pale_augmenter is None:
        _pale_augmenter = PALEDataAugmenter()
    return _pale_augmenter
