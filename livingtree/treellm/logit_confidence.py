"""logit_confidence.py — φ_first single-decode confidence for hallucination detection.

Implements arXiv:2605.05166 (Temple University):
  "The First Token Knows — Single-Decode Confidence for Hallucination Detection"
  φ_first = normalized entropy of top-K logits at first content-bearing answer token.

Key finding: much of multi-sample self-consistency signal is already in the
first token's logit distribution. φ_first AUROC 0.820 vs semantic agreement 0.793.

Usage:
    phi, info = compute_phi_first(logprobs, top_k=10, content_start_threshold=5)
    # phi ≈ 0.0 → model was very certain → likely truthful
    # phi ≈ 1.0 → model was very uncertain → potential hallucination
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FirstTokenResult:
    phi_first: float
    first_content_index: int
    first_content_token: str
    top_k_tokens: list[str]
    top_k_logprobs: list[float]
    top_k_probs: list[float]
    raw_entropy: float
    normalized_entropy: float
    is_uncertain: bool
    confidence: float

    def summary(self) -> str:
        return (
            f"φ={self.phi_first:.3f} token={self.first_content_token!r} "
            f"idx={self.first_content_index} "
            f"{'UNCERTAIN' if self.is_uncertain else 'confident'}"
        )


def compute_phi_first(
    logprobs: list[dict],
    top_k: int = 10,
    content_start_threshold: int = 5,
    uncertainty_threshold: float = 0.6,
) -> FirstTokenResult:
    """Compute φ_first: normalized entropy of first content-bearing token's top-K logits.

    Algorithm (paper Section 3.2):
    1. Skip leading special tokens (BOS, whitespace-only, byte tokens like '<|start|>')
    2. Find first token with visible content at position >= content_start_threshold
    3. Extract top-K log probabilities → convert to probabilities via softmax
    4. Compute Shannon entropy H = -Σ p_i * log_K(p_i)
    5. Normalize to [0, 1]: φ_first = H_norm = -Σ p_i * log_K(p_i)

    Args:
        logprobs: List[dict] from API response choice["logprobs"]["content"]
                  Each dict has {"token": str, "logprob": float, "top_logprobs": [...]}
        top_k: Use top-K logprobs (paper default: 10)
        content_start_threshold: Skip first N tokens (BOS/special), default 5
        uncertainty_threshold: φ_first values above this are "uncertain"

    Returns:
        FirstTokenResult with φ_first score and detailed diagnostics
    """
    if not logprobs:
        return FirstTokenResult(
            phi_first=0.5, first_content_index=-1, first_content_token="",
            top_k_tokens=[], top_k_logprobs=[], top_k_probs=[],
            raw_entropy=0.0, normalized_entropy=0.5,
            is_uncertain=False, confidence=0.5,
        )

    SPECIAL_PATTERNS = {
        "", "<|start|>", "<|end|>", "<|endoftext|>", "<s>", "</s>",
        "<pad>", "<unk>", "<|im_start|>", "<|im_end|>", "▁",
    }

    def _is_content(token: str) -> bool:
        return (token and token.strip() and token not in SPECIAL_PATTERNS
                and not token.startswith("<|") and not token.startswith("▁▁"))

    first_idx = -1
    first_token = ""
    for i, entry in enumerate(logprobs):
        if i < content_start_threshold:
            continue
        token = entry.get("token", "")
        if _is_content(token):
            first_idx = i
            first_token = token
            break

    if first_idx < 0:
        return FirstTokenResult(
            phi_first=0.5, first_content_index=len(logprobs) - 1 if logprobs else -1,
            first_content_token=logprobs[-1].get("token", "") if logprobs else "",
            top_k_tokens=[], top_k_logprobs=[], top_k_probs=[],
            raw_entropy=0.0, normalized_entropy=0.5,
            is_uncertain=False, confidence=0.5,
        )

    entry = logprobs[first_idx]
    top_candidates = entry.get("top_logprobs", [])

    if not top_candidates and "logprob" in entry:
        top_candidates = [{
            "token": entry["token"],
            "logprob": entry["logprob"],
        }]

    if not top_candidates:
        return FirstTokenResult(
            phi_first=0.5, first_content_index=first_idx,
            first_content_token=first_token,
            top_k_tokens=[first_token], top_k_logprobs=[0.0], top_k_probs=[1.0],
            raw_entropy=0.0, normalized_entropy=0.5,
            is_uncertain=False, confidence=0.5,
        )

    candidates = top_candidates[:top_k]
    tokens = [c.get("token", "") for c in candidates]
    logprobs_list = [c.get("logprob", -10.0) for c in candidates]

    probs = _logprobs_to_probs(logprobs_list)

    raw_entropy = _shannon_entropy(probs)
    k = len(probs)
    if k <= 1:
        phi_first = 0.0
    else:
        phi_first = raw_entropy / math.log(k)

    phi_first = max(0.0, min(1.0, phi_first))

    return FirstTokenResult(
        phi_first=phi_first,
        first_content_index=first_idx,
        first_content_token=first_token,
        top_k_tokens=tokens,
        top_k_logprobs=logprobs_list[:top_k],
        top_k_probs=[round(p, 4) for p in probs[:top_k]],
        raw_entropy=round(raw_entropy, 4),
        normalized_entropy=round(phi_first, 4),
        is_uncertain=phi_first > uncertainty_threshold,
        confidence=round(1.0 - phi_first, 4),
    )


def _logprobs_to_probs(logprobs: list[float]) -> list[float]:
    """Convert log probabilities to normalized probabilities: p_i = exp(l_i) / Σ exp(l_j)."""
    if not logprobs:
        return []
    lp = list(logprobs)
    max_lp = max(lp)
    exps = [math.exp(l - max_lp) for l in lp]
    total = sum(exps)
    if total <= 0:
        return [1.0 / len(lp)] * len(lp)
    return [e / total for e in exps]


def _shannon_entropy(probs: list[float]) -> float:
    """Shannon entropy: H = -Σ p_i * ln(p_i)."""
    h = 0.0
    for p in probs:
        if p > 1e-12:
            h -= p * math.log(p)
    return h


def phi_first_from_result(
    result, top_k: int = 10, content_start_threshold: int = 5
) -> Optional[FirstTokenResult]:
    """Convenience: compute φ_first from a ProviderResult if logprobs are present."""
    if result is None or not hasattr(result, "logprobs") or not result.logprobs:
        return None
    return compute_phi_first(result.logprobs, top_k=top_k,
                             content_start_threshold=content_start_threshold)


_confidence_singleton: Optional["LogitConfidenceGate"] = None
_confidence_lock = threading.Lock()


class LogitConfidenceGate:
    def __init__(self, threshold: float = 0.6, top_k: int = 10):
        self.threshold = threshold
        self.top_k = top_k
        self._total = 0
        self._uncertain = 0

    def check(self, logprobs: list[dict] | None) -> tuple[bool, Optional[FirstTokenResult]]:
        if not logprobs:
            return False, None
        r = compute_phi_first(logprobs, top_k=self.top_k)
        self._total += 1
        if r.is_uncertain:
            self._uncertain += 1
        return r.is_uncertain, r

    @property
    def uncertainty_ratio(self) -> float:
        if self._total == 0:
            return 0.0
        return self._uncertain / self._total


def get_confidence_gate(threshold: float = 0.6, top_k: int = 10) -> LogitConfidenceGate:
    global _confidence_singleton
    if _confidence_singleton is None:
        with _confidence_lock:
            if _confidence_singleton is None:
                _confidence_singleton = LogitConfidenceGate(threshold=threshold, top_k=top_k)
    return _confidence_singleton
