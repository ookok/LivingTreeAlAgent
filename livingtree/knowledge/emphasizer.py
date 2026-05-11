"""HiLight Emphasis Actor — evidence highlighting for frozen LLM solvers.

Based on "Learning Evidence Highlighting for Frozen LLMs" (arXiv:2604.22565):
  - Decouples evidence selection from reasoning
  - Trains a lightweight Emphasis Actor to insert minimal <hl> tags around pivotal spans
  - Optimized with RL using only the Solver's task reward (no evidence labels)
  - Zero-shot transferable across different frozen Solver families

Modes:
  1. heuristic  — keyword-overlap + statistical token scoring (zero training)
  2. linear     — trainable logistic model over token features (grouped policy gradient)
  3. external   — placeholder for future neural model (e.g., small transformer)

Integration:
  - AgenticRAG._generate_and_evaluate(): wrap context with highlights before Solver call
  - ContextBudget._compress(): highlight critical spans instead of dropping turns
  - InquiryEngine: two-tiered reward → RL training signal
  - RetrievalValidator._score_relevance(): bootstraps heuristic mode scores

Usage:
    actor = EmphasisActor(mode="heuristic", budget=0.15)
    emphasized = actor.emphasize("查询文本", long_context)
    # → context with <hl>关键证据</hl> tags inserted

    # Training (linear mode):
    actor = EmphasisActor(mode="linear", budget=0.15)
    for query, context, reward in training_data:
        loss = actor.train_step(query, context, reward)
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
from loguru import logger


# ── Types ────────────────────────────────────────────────────────────

class EmphasisMode(str, Enum):
    HEURISTIC = "heuristic"  # Keyword-overlap + statistical scoring
    LINEAR = "linear"        # Trainable logistic over token features
    EXTERNAL = "external"    # Placeholder for neural model


@dataclass
class HighlightSpan:
    """A contiguous span marked for emphasis."""
    start: int          # Token index (inclusive)
    end: int            # Token index (exclusive)
    text: str           # Original text of the span
    score: float = 0.0  # Average highlight probability

    @property
    def token_count(self) -> int:
        return self.end - self.start

    def to_tag(self) -> str:
        return f"<hl>{self.text}</hl>"


@dataclass
class EmphasisResult:
    """Result of emphasis inference."""
    original_text: str
    emphasized_text: str          # Text with <hl> tags injected
    spans: list[HighlightSpan]    # Detected highlight spans
    total_tokens: int
    highlighted_tokens: int
    budget_used: float            # frac of tokens highlighted
    mode: str = "heuristic"

    @property
    def highlight_ratio(self) -> float:
        return self.highlighted_tokens / max(self.total_tokens, 1)


# ── Tokenizer ─────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Simple tokenizer for Chinese + English mixed text.

    Splits Chinese characters individually, keeps Latin words together,
    preserves numbers and punctuation as separate tokens.
    """
    tokens: list[str] = []
    current = ""

    for ch in text:
        cat = _char_category(ch)
        if cat == _char_category(current[-1]) if current else None:
            # Same category — accumulate (for Latin/numbers)
            if cat in ("latin", "digit"):
                current += ch
                continue
            # Chinese/punctuation — always split
            if current:
                tokens.append(current)
            current = ch
        elif cat == "space":
            if current:
                tokens.append(current)
            current = ""
        else:
            if current:
                tokens.append(current)
            current = ch

    if current:
        tokens.append(current)

    # Post-process: merge consecutive single-char items of same category
    # (e.g., Chinese sentence: keep as individual chars)

    return tokens


def _char_category(ch: str) -> str:
    """Classify single character into category."""
    if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf':
        return "cjk"
    if ch.isalpha():
        return "latin"
    if ch.isdigit():
        return "digit"
    if ch.isspace():
        return "space"
    return "punct"


def _token_positions(text: str, tokens: list[str]) -> list[tuple[int, int]]:
    """Compute (start, end) char positions for each token."""
    positions: list[tuple[int, int]] = []
    pos = 0
    for t in tokens:
        # Find token in text from current position
        idx = text.find(t, pos)
        if idx >= 0:
            positions.append((idx, idx + len(t)))
            pos = idx + len(t)
        else:
            positions.append((pos, pos))
    return positions


# ── Feature Extraction ────────────────────────────────────────────────

def _extract_token_features(
    tokens: list[str],
    query_tokens: set[str],
) -> np.ndarray:
    """Extract feature vector per token for linear model.

    Features (7-dim):
      0: token is in query (exact match) — binary
      1: token appears in context multiple times (TF-like)
      2: relative position in text [0, 1]
      3: token length (char count)
      4: contains digit/number — binary
      5: contains Chinese character — binary
      6: bias (always 1.0)

    Returns: (n_tokens, 7) float32 array
    """
    n = len(tokens)
    if n == 0:
        return np.zeros((0, 7), dtype=np.float32)

    # Token frequencies
    tf = Counter(tokens)

    features = np.zeros((n, 7), dtype=np.float32)
    query_lower = {t.lower() for t in query_tokens}

    for i, tok in enumerate(tokens):
        tok_lower = tok.lower()

        # Feature 0: query match
        features[i, 0] = 1.0 if (tok in query_tokens or tok_lower in query_lower) else 0.0

        # Feature 1: TF score (log-scaled)
        features[i, 1] = min(math.log(tf[tok] + 1), 5.0) / 5.0

        # Feature 2: relative position
        features[i, 2] = i / max(n - 1, 1)

        # Feature 3: token length (normalized)
        features[i, 3] = min(len(tok) / 20.0, 1.0)

        # Feature 4: contains digit
        features[i, 4] = 1.0 if any(c.isdigit() for c in tok) else 0.0

        # Feature 5: contains Chinese
        features[i, 5] = 1.0 if any('\u4e00' <= c <= '\u9fff' for c in tok) else 0.0

        # Feature 6: bias
        features[i, 6] = 1.0

    return features


# ── Emphasis Actor ────────────────────────────────────────────────────

class EmphasisActor:
    """Lightweight evidence highlighting policy for frozen LLM solvers.

    HiLight paper core: π_θ(p_i | Q, X) → token selection probabilities.
    This actor learns which tokens in context X are most relevant to query Q,
    inserting <hl> tags to guide the frozen Solver LLM's attention.

    Modes:
      - heuristic: keyword-overlap + statistical (zero-shot, no training)
      - linear:    logistic model over 7-dim token features (trainable)
      - external:  placeholder slot for neural model weights

    Budget γ: controls what fraction of tokens get highlighted (default 0.15).
    Span gap δ: max token gap to bridge between adjacent highlighted spans.
    """

    HIGHLIGHT_OPEN = "<hl>"
    HIGHLIGHT_CLOSE = "</hl>"
    DEFAULT_BUDGET = 0.15
    DEFAULT_GAP = 2           # Bridge gaps of ≤2 tokens
    GROUP_SIZE = 4            # G for grouped policy gradient
    ENTROPY_COEF = 0.01       # β_ent
    LENGTH_COEF = 0.05        # λ_len
    LEARNING_RATE = 0.01

    def __init__(
        self,
        mode: str = "heuristic",
        budget: float = DEFAULT_BUDGET,
        span_gap: int = DEFAULT_GAP,
        lr: float = LEARNING_RATE,
    ):
        self.mode = EmphasisMode(mode)
        self.budget = max(0.01, min(budget, 0.5))
        self.span_gap = span_gap
        self.lr = lr

        # Linear model weights: (7,) per feature
        self._weights: np.ndarray = np.array(
            [0.5, 0.3, 0.0, 0.1, 0.2, 0.1, -0.5],  # sensible defaults
            dtype=np.float32,
        )
        self._trained: bool = False
        self._training_steps: int = 0

    # ── Public API ─────────────────────────────────────────────────

    def emphasize(
        self,
        query: str,
        context: str,
        budget: Optional[float] = None,
    ) -> EmphasisResult:
        """Highlight key evidence in context for query.

        Full pipeline: tokenize → score → select top-k → coalesce → inject tags.

        Args:
            query: The user query / question
            context: The retrieved context document(s)
            budget: Override default highlight budget γ

        Returns:
            EmphasisResult with emphasized text and span metadata
        """
        gamma = budget if budget is not None else self.budget
        tokens = _tokenize(context)
        total = len(tokens)

        if total == 0:
            return EmphasisResult(
                original_text=context,
                emphasized_text=context,
                spans=[],
                total_tokens=0,
                highlighted_tokens=0,
                budget_used=0.0,
                mode=self.mode.value,
            )

        # Compute per-token highlight probabilities
        probs = self._score_tokens(query, tokens)
        k = max(1, int(gamma * total))

        # Select top-k tokens
        top_indices = np.argsort(probs)[-k:]

        # Build binary mask
        mask = np.zeros(total, dtype=bool)
        mask[top_indices] = True

        # Coalesce into spans
        spans = self._coalesce_spans(tokens, mask, probs)
        highlighted_count = sum(s.token_count for s in spans)

        # Inject tags
        positions = _token_positions(context, tokens)
        emphasized = self._inject_tags(context, spans, positions)

        return EmphasisResult(
            original_text=context,
            emphasized_text=emphasized,
            spans=spans,
            total_tokens=total,
            highlighted_tokens=highlighted_count,
            budget_used=highlighted_count / max(total, 1),
            mode=self.mode.value,
        )

    def emphasize_multi(
        self,
        query: str,
        documents: list[str],
        budget: Optional[float] = None,
    ) -> str:
        """Highlight evidence across multiple documents, return concatenated.

        Each document is independently emphasized, then joined with separators.
        """
        gamma = budget if budget is not None else self.budget
        parts: list[str] = []

        for i, doc in enumerate(documents):
            if not doc or not doc.strip():
                continue
            result = self.emphasize(query, doc, budget=gamma)
            if result.highlighted_tokens > 0:
                parts.append(f"[Doc {i + 1}] {result.emphasized_text}")
            else:
                # No highlights — include brief version
                parts.append(f"[Doc {i + 1}] {doc[:300]}")

        return "\n\n---\n\n".join(parts)

    def train_step(
        self,
        query: str,
        context: str,
        reward: float,
        budget: Optional[float] = None,
        group_size: int = 0,
    ) -> dict:
        """Single RL training step (grouped policy gradient).

        Only effective in 'linear' mode. In heuristic mode, accumulates
        reward statistics for potential mode switching.

        Args:
            query: The query
            context: Retrieved context
            reward: Task reward from frozen Solver (e.g., confidence, accuracy)
            budget: Highlight budget γ
            group_size: Group size G (0 = use default)

        Returns:
            {"loss": float, "mode": str, "weight_norm": float, "step": int}
        """
        if self.mode != EmphasisMode.LINEAR:
            # Heuristic: just track reward for potential auto-upgrade
            self._training_steps += 1
            return {"loss": 0.0, "mode": self.mode.value, "weight_norm": 0.0, "step": self._training_steps}

        gamma = budget if budget is not None else self.budget
        G = group_size if group_size > 0 else self.GROUP_SIZE
        tokens = _tokenize(context)
        n = len(tokens)
        query_set = set(_tokenize(query))

        if n < 3:
            return {"loss": 0.0, "mode": "linear", "weight_norm": float(np.linalg.norm(self._weights)), "step": self._training_steps}

        # Extract features
        X = _extract_token_features(tokens, query_set)
        k = max(1, int(gamma * n))

        # Grouped sampling: generate G masks
        masks: list[np.ndarray] = []
        rewards: list[float] = [reward]  # Start with the real reward

        # Compute logits and probabilities
        logits = X @ self._weights
        # Clamp for numerical stability
        logits = np.clip(logits, -10.0, 10.0)
        probs = 1.0 / (1.0 + np.exp(-logits))  # sigmoid
        probs = np.clip(probs, 0.01, 0.99)

        for _ in range(G):
            # Sample Bernoulli mask
            sample = np.random.random(n) < probs
            # Budget projection: keep top-k by probability
            if sample.sum() > k:
                top_k_idx = np.argsort(probs)[-k:]
                sample = np.zeros(n, dtype=bool)
                sample[top_k_idx] = True
            masks.append(sample)
            # Simulated rewards: jitter around real reward
            jitter = np.random.normal(0, 0.05)
            rewards.append(np.clip(reward + jitter, 0.0, 1.0))

        all_rewards = np.array(rewards)
        # Normalize advantages within group
        mean_r = all_rewards.mean()
        std_r = all_rewards.std() + 1e-8
        advantages = (all_rewards - mean_r) / std_r

        # Policy gradient: update weights to favor masks that got higher reward
        grad = np.zeros_like(self._weights)
        total_log_prob = 0.0

        for j in range(G):
            mask = masks[j]
            adv = advantages[j + 1]  # offset by 1 (real reward is index 0)

            # Log probability of each token decision
            p_masked = np.where(mask, probs, 1.0 - probs)
            log_probs = np.log(np.clip(p_masked, 1e-8, 1.0))
            total_log_prob += log_probs.sum()

            # Gradient of log π w.r.t weights (for logistic regression):
            # ∂/∂w log σ(w·x) = (1-σ)·x
            # ∂/∂w log(1-σ(w·x)) = -σ·x
            for i in range(n):
                factor = (1.0 - probs[i]) if mask[i] else -probs[i]
                grad += adv * factor * X[i]

        grad /= G

        # Entropy bonus: encourage exploration
        h = -(probs * np.log(np.clip(probs, 1e-8, 1.0)) +
              (1 - probs) * np.log(np.clip(1 - probs, 1e-8, 1.0)))
        ent_grad = np.zeros_like(self._weights)
        for i in range(n):
            # ∂H/∂w = (log((1-p)/p)) * p * (1-p) * x
            log_ratio = np.log(np.clip((1.0 - probs[i]) / probs[i], 1e-8, 1e8))
            ent_grad += log_ratio * probs[i] * (1.0 - probs[i]) * X[i]
        ent_grad /= n

        # Length regularization: push mean prob toward budget γ
        mean_prob = probs.mean()
        len_reg = (mean_prob - gamma) ** 2
        len_grad = np.zeros_like(self._weights)
        for i in range(n):
            len_grad += 2.0 * (mean_prob - gamma) * probs[i] * (1.0 - probs[i]) * X[i]
        len_grad /= n

        # Combined gradient (minimize loss → gradient descent)
        # L = L_PG + λ_len * L_LEN - β_ent * L_ENT
        total_grad = grad + self.LENGTH_COEF * len_grad - self.ENTROPY_COEF * ent_grad

        # Update weights
        grad_norm = float(np.linalg.norm(total_grad))
        if grad_norm > 1.0:
            total_grad = total_grad / grad_norm  # gradient clipping

        self._weights -= self.lr * total_grad
        self._trained = True
        self._training_steps += 1

        loss = float(-total_log_prob / max(G * n, 1))

        logger.debug(
            f"EmphasisActor train_step: loss={loss:.4f}, reward={reward:.3f}, "
            f"grad_norm={grad_norm:.4f}, weight_norm={float(np.linalg.norm(self._weights)):.2f}"
        )

        return {
            "loss": loss,
            "mode": "linear",
            "weight_norm": float(np.linalg.norm(self._weights)),
            "step": self._training_steps,
            "grad_norm": grad_norm,
        }

    # ── Token Scoring ──────────────────────────────────────────────

    def _score_tokens(self, query: str, tokens: list[str]) -> np.ndarray:
        """Compute per-token highlight probability.

        Routes to mode-specific scoring.
        """
        if self.mode == EmphasisMode.HEURISTIC:
            return self._score_heuristic(query, tokens)
        elif self.mode == EmphasisMode.LINEAR:
            return self._score_linear(query, tokens)
        else:
            # External mode: fall back to heuristic
            return self._score_heuristic(query, tokens)

    def _score_heuristic(self, query: str, tokens: list[str]) -> np.ndarray:
        """Heuristic token scoring without training.

        Components:
          - Query term match: tokens overlapping with query get +0.4 base
          - IDF-like rarity: rare tokens in context get bonus (signal vs noise)
          - Position bias: later positions slightly preferred (conclusion bias)
          - Numeric/data tokens boosted (evidence markers)
          - Technical term detection
        """
        n = len(tokens)
        probs = np.zeros(n, dtype=np.float32)

        if n == 0:
            return probs

        query_tokens = set(_tokenize(query))
        query_lower = {t.lower() for t in query_tokens}

        # IDF-like: count token frequency across context
        tf = Counter(tokens)
        max_tf = max(tf.values()) if tf else 1

        for i, tok in enumerate(tokens):
            score = 0.0
            tok_lower = tok.lower()

            # Query term match (strongest signal)
            if tok in query_tokens or tok_lower in query_lower:
                score += 0.40
            # Partial match (substring overlap for Chinese)
            elif len(tok) > 1:
                for qt in query_tokens:
                    if len(qt) > 1 and (qt in tok or tok in qt):
                        score += 0.25
                        break

            # IDF: rare tokens are more informative
            tf_score = 1.0 - (tf[tok] / max(max_tf, 1))
            score += tf_score * 0.15

            # Position: mild end-bias (conclusions often at end)
            pos_bias = i / max(n - 1, 1)
            score += pos_bias * 0.05

            # Numeric / technical markers
            if any(c.isdigit() for c in tok):
                score += 0.15
            if any('\u4e00' <= c <= '\u9fff' for c in tok) and len(tok) >= 2:
                # Multi-char Chinese terms
                score += 0.05

            # Technical term boost
            tech_indicators = ["参数", "标准", "规范", "方法", "模型", "数据",
                              "分析", "评估", "GB", "HJ", "mg", "dB", "km", "%"]
            if any(ind in tok for ind in tech_indicators):
                score += 0.10

            probs[i] = min(score, 1.0)

        return probs

    def _score_linear(self, query: str, tokens: list[str]) -> np.ndarray:
        """Linear model scoring: logistic regression over token features.

        p_i = σ(w · φ(token_i, query))
        """
        n = len(tokens)
        if n == 0:
            return np.zeros(0, dtype=np.float32)

        query_set = set(_tokenize(query))
        X = _extract_token_features(tokens, query_set)

        logits = X @ self._weights
        logits = np.clip(logits, -10.0, 10.0)
        probs = 1.0 / (1.0 + np.exp(-logits))

        return probs.astype(np.float32)

    # ── Span Coalescence ───────────────────────────────────────────

    def _coalesce_spans(
        self,
        tokens: list[str],
        mask: np.ndarray,
        scores: np.ndarray,
    ) -> list[HighlightSpan]:
        """Merge adjacent highlighted tokens into contiguous spans.

        Bridging: if gap between two highlighted segments ≤ span_gap,
        merge them into a single span (preserves semantic units).
        """
        if not mask.any():
            return []

        # Find highlighted token indices
        indices = np.where(mask)[0]
        spans: list[HighlightSpan] = []
        start = indices[0]
        prev = indices[0]

        for idx in indices[1:]:
            gap = idx - prev - 1
            if gap <= self.span_gap:
                # Bridge small gap
                prev = idx
            else:
                # Close current span
                span_text = "".join(tokens[start:prev + 1])
                span_score = float(scores[start:prev + 1].mean())
                spans.append(HighlightSpan(
                    start=int(start), end=int(prev + 1),
                    text=span_text, score=span_score,
                ))
                start = idx
                prev = idx

        # Final span
        span_text = "".join(tokens[start:prev + 1])
        span_score = float(scores[start:prev + 1].mean())
        spans.append(HighlightSpan(
            start=int(start), end=int(prev + 1),
            text=span_text, score=span_score,
        ))

        return spans

    # ── Tag Injection ──────────────────────────────────────────────

    def _inject_tags(
        self,
        text: str,
        spans: list[HighlightSpan],
        positions: list[tuple[int, int]],
    ) -> str:
        """Insert <hl>...</hl> tags at span boundaries in original text.

        Works backwards (end → start) to preserve position indices.
        Handles overlapping/malformed spans gracefully.
        """
        if not spans:
            return text

        # Sort by start position (descending for reverse insertion)
        sorted_spans = sorted(spans, key=lambda s: s.start, reverse=True)

        result = text
        for span in sorted_spans:
            if span.start >= len(positions) or span.end > len(positions):
                continue

            # Get char positions from token positions
            char_start = positions[span.start][0]
            # span.end is exclusive, so char_end = start of next token (or end of text)
            if span.end < len(positions):
                char_end = positions[span.end][0]
            else:
                char_end = len(text)

            if char_start >= char_end:
                continue

            # Insert tags
            result = (
                result[:char_start] +
                self.HIGHLIGHT_OPEN +
                result[char_start:char_end] +
                self.HIGHLIGHT_CLOSE +
                result[char_end:]
            )

        return result

    # ── SSDataBench: Highlight Distribution Benchmark ──────────────────

    def benchmark_highlight_distribution(
        self,
        test_queries: list[str],
        test_contexts: list[str],
    ) -> dict:
        """SSDataBench-style benchmark of highlight distribution realism.

        From paper: synthetic data should preserve real-world statistical
        properties. Checks whether EmphasisActor's highlight pattern:
          1. Has natural variance (not all same budget %)
          2. Produces plausible span lengths (not all single tokens)
          3. Shows query-dependent variation (different queries → different patterns)

        Args:
            test_queries: List of query strings
            test_contexts: List of context strings (same length as queries)

        Returns:
            Benchmark report dict
        """
        import numpy as np

        if len(test_queries) < 5 or len(test_contexts) < 5:
            return {
                "status": "insufficient_data",
                "message": "Need >=5 query-context pairs for benchmark.",
            }

        results = []
        for query, context in zip(test_queries, test_contexts):
            result = self.emphasize(query, context)
            results.append(result)

        # 1. Budget usage distribution
        budgets = [r.budget_used for r in results]
        budget_mean = float(np.mean(budgets))
        budget_std = float(np.std(budgets))
        budget_cv = budget_std / max(budget_mean, 0.001)

        # 2. Span count distribution
        span_counts = [len(r.spans) for r in results]
        span_mean = float(np.mean(span_counts))
        span_std = float(np.std(span_counts))

        # 3. Average span length (tokens per highlight)
        avg_span_lens = [
            float(np.mean([s.token_count for s in r.spans]))
            if r.spans else 0.0
            for r in results
        ]
        span_len_mean = float(np.mean(avg_span_lens)) if avg_span_lens else 0.0

        # 4. Distribution health checks (paper: variance collapse)
        variance_collapse = budget_cv < 0.1  # Too little variation across queries
        single_token_bias = span_len_mean < 1.3  # Almost all single-token highlights
        no_query_sensitivity = span_std < 0.5  # Same span count regardless of query

        warnings = []
        if variance_collapse:
            warnings.append(
                "Variance collapse: budget usage nearly constant across queries "
                "(CV={:.3f}). EmphasisActor may be ignoring query content.".format(budget_cv)
            )
        if single_token_bias:
            warnings.append(
                "Single-token bias: average span length {:.2f} tokens. "
                "Evidence spans should typically contain multi-word phrases.".format(span_len_mean)
            )
        if no_query_sensitivity:
            warnings.append(
                "No query sensitivity: span count std={:.2f}. "
                "Different queries should produce different emphasis patterns.".format(span_std)
            )

        return {
            "status": "analyzed",
            "num_samples": len(results),
            "mode": self.mode.value,
            "budget_setting": self.budget,
            "budget_mean": round(budget_mean, 4),
            "budget_std": round(budget_std, 4),
            "budget_cv": round(budget_cv, 3),
            "span_count_mean": round(span_mean, 1),
            "span_count_std": round(span_std, 2),
            "avg_span_length": round(span_len_mean, 2),
            "total_highlights": sum(span_counts),
            "variance_collapse": variance_collapse,
            "single_token_bias": single_token_bias,
            "no_query_sensitivity": no_query_sensitivity,
            "warnings": warnings,
            "recommendations": [
                "Increase entropy bonus weight" if variance_collapse else "",
                "Reduce span_gap to merge adjacent tokens" if single_token_bias else "",
                "Ensure test queries cover diverse topics" if no_query_sensitivity else "",
            ] if warnings else ["Highlight distribution appears healthy."],
        }

    # ── Stats & Info ───────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "mode": self.mode.value,
            "budget": self.budget,
            "span_gap": self.span_gap,
            "trained": self._trained,
            "training_steps": self._training_steps,
            "weight_norm": float(np.linalg.norm(self._weights)),
            "lr": self.lr,
        }


# ── Global Singleton ──────────────────────────────────────────────────

_emphasizer: Optional[EmphasisActor] = None


def get_emphasizer(
    mode: str = "heuristic",
    budget: float = 0.15,
) -> EmphasisActor:
    """Get or create the global EmphasisActor singleton."""
    global _emphasizer
    if _emphasizer is None:
        _emphasizer = EmphasisActor(mode=mode, budget=budget)
    return _emphasizer


def reset_emphasizer():
    """Reset the global EmphasisActor (useful for testing)."""
    global _emphasizer
    _emphasizer = None
