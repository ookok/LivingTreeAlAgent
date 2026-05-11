"""Score Matching Router — diffusion-based LLM provider routing.

Based on Ramachandran & Sra (TUM), ICML 2026, arXiv:2605.00414:
  The tree→flow unification inspires a smooth routing alternative:
    - Current: hard classifier → discrete provider tier → fixed model
    - Score matching: continuous score field → gradient descent → optimal provider

Physical analogy (tree ↔ flow):
  Decision tree routing: query → (type_classifier) → tier → model
    = discrete trajectory, brittle at boundaries

  Score matching routing: query → score_field(providers) → ∇score → optimum
    = continuous diffusion toward best provider, smooth at boundaries

Core formula (GTSM routing):
  score_matching(provider_i) = Σ_j relevance(j, task) × ∂log P(provider_i | task) 
  Provider selection = argmax_i score_matching(provider_i)

Intentional TD integration (Sharifnassab et al., arXiv:2604.19033):
  Instead of fixed learning rate _lr, use Intentional TD:
    η* = γ × |error| → reduces the score-to-target gap by fraction γ each update
  - γ=0.3: close 30% of gap per feedback → fast adaptation, smooth convergence
  - Auto-scales: large gap→large step, small gap→small step (no manual tuning)
  - Cold-start: rapid initialization; Converged: fine-grained adjustments

Integration:
  Replace or augment HolisticElection.get_best() with score-matched selection
  for tasks near decision boundaries (uncertain type_classifier output).
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ═══ Data Types ═══


@dataclass
class ScoreField:
    """Continuous score field over provider space.

    Analogous to the score function s(x) = ∇_x log p(x) in diffusion models.
    Each provider has a score gradient magnitude and direction.
    The optimal provider is the one that minimizes the score-matching loss.
    """
    provider: str
    base_score: float             # Static relevance score
    score_gradient: float         # ∇score — direction and magnitude of improvement
    diffusion_potential: float    # How much this provider can improve via diffusion steps
    boundary_distance: float      # Distance to the nearest decision boundary (0=uncertain)
    uncertainty: float            # Posterior uncertainty (exploration needed)


@dataclass
class ScoreMatchingResult:
    """Result of score-matching routing."""
    query: str
    task_type: str
    field: list[ScoreField]       # All scored providers
    top_provider: str
    top_score: float
    gradient_path: list[str]      # Sequence of providers along gradient descent
    convergence_steps: int        # Steps to converge
    boundary_crossing: bool       # Whether we crossed a decision boundary
    timestamp: float = field(default_factory=time.time)


# ═══ Score Matching Router ═══


class ScoreMatchingRouter:
    """Diffusion-style provider routing via score matching.

    Replaces discrete classifier-based routing with continuous score field.
    Smoothly interpolates between providers near decision boundaries,
    eliminating the brittle "wrong tier" problem of hard classifiers.

    Training: The score function is learned online from provider outcomes.
    In the GTSM framework, gradient boosting over provider scores is
    asymptotically optimal — each call updates the score field.

    Integration with existing routing:
      - For tasks far from boundaries → defer to existing HolisticElection
      - For tasks near boundaries → use score matching for smooth interpolation
      - Fallback: score matching always returns a valid provider
    """

    def __init__(self, learning_rate: float = 0.05, diffusion_steps: int = 5,
                 gamma: float = 0.3):
        """Initialize ScoreMatchingRouter with Intentional TD.

        Args:
            learning_rate: Fixed LR (legacy; superseded by gamma).
            diffusion_steps: Steps in the score diffusion process.
            gamma: Intentional TD error reduction fraction (0-1).
                   0.3 = close 30% of score-target gap per feedback.
                   Set to 0.0 to fall back to fixed learning_rate.
        """
        self._lr = learning_rate
        self._diffusion_steps = diffusion_steps
        self._gamma = gamma

        # Score function memory: (provider, condition) → learned score
        self._scores: dict[tuple[str, str], float] = defaultdict(lambda: 0.5)
        # Provider gradients (recent improvements)
        self._gradients: dict[str, list[float]] = defaultdict(list)
        # Task type → provider score distribution (for boundary detection)
        self._type_provider_scores: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(lambda: 0.5))

    # ── Score Computation ──

    def compute_field(
        self,
        query: str,
        providers: list[str],
        task_type: str = "general",
        existing_scores: dict[str, float] | None = None,
    ) -> list[ScoreField]:
        """Compute the continuous score field over provider space.

        Score(provider_i) = α×learned_score + β×existing_score + γ×gradient_bonus

        Args:
            query: The user's query
            providers: Available provider names
            task_type: Inferred task type
            existing_scores: Pre-computed scores from HolisticElection (optional)

        Returns:
            Sorted list of ScoreField objects (descending by base_score)
        """
        field: list[ScoreField] = []
        existing = existing_scores or {}

        for provider in providers:
            # Learned score from past outcomes
            learned = self._scores.get((provider, task_type), 0.5)

            # Existing score from static election
            static = existing.get(provider, 0.5)

            # Gradient bonus: providers with recent improvements get boost
            grad = self._provider_gradient(provider)

            # Blend: 60% learned, 20% static, 20% gradient
            base_score = 0.6 * learned + 0.2 * static + 0.2 * grad

            # Boundary distance: how far from decision boundary?
            boundary = self._boundary_distance(provider, task_type, providers)

            # Uncertainty: how much have we explored this provider?
            uncertainty = self._compute_uncertainty(provider, task_type)

            # Diffusion potential: room for improvement
            potential = 1.0 - learned  # If already high score, less room

            field.append(ScoreField(
                provider=provider,
                base_score=round(base_score, 4),
                score_gradient=round(grad, 4),
                diffusion_potential=round(potential, 4),
                boundary_distance=round(boundary, 4),
                uncertainty=round(uncertainty, 4),
            ))

        field.sort(key=lambda f: -f.base_score)
        return field

    def _provider_gradient(self, provider: str) -> float:
        """Recent improvement trend for a provider.

        Computes the score gradient ∇score(provider) from recent observations.
        Positive gradient = improving, negative = degrading.
        """
        grads = self._gradients.get(provider, [])
        if len(grads) < 3:
            return 0.5  # Neutral
        # Exponential moving average of recent gradients
        alpha = 0.7
        ema = grads[-1]
        for g in reversed(grads[:-1]):
            ema = alpha * ema + (1 - alpha) * g
        return max(0.0, min(1.0, (ema + 1.0) / 2.0))  # Normalize to [0,1]

    def _boundary_distance(
        self, provider: str, task_type: str, all_providers: list[str],
    ) -> float:
        """Distance to the nearest decision boundary in provider space.

        0 = right on boundary (ambiguous), 1 = far from boundary (confident).
        This identifies queries that benefit from score matching (smooth interpolation)
        vs standard hard routing.

        Boundary = point where two providers have similar scores.
        """
        if len(all_providers) < 2:
            return 1.0

        my_score = self._scores.get((provider, task_type), 0.5)
        # Find closest competitor score
        min_diff = float('inf')
        for other in all_providers:
            if other == provider:
                continue
            other_score = self._scores.get((other, task_type), 0.5)
            diff = abs(my_score - other_score)
            min_diff = min(min_diff, diff)

        # Map: diff=0 → boundary_distance=0, diff=1.0 → boundary_distance=1.0
        return min(1.0, min_diff * 3.0)  # Amplify — boundaries are narrow

    def _compute_uncertainty(self, provider: str, task_type: str) -> float:
        """Epistemic uncertainty: how much have we explored this provider for this task?"""
        # Count how many time steps we have data for
        type_scores = self._type_provider_scores.get(task_type, {})
        visits = sum(1 for p in type_scores if p == provider)
        # Normalize: uncertainty decays as 1/√(visits)
        if visits == 0:
            return 1.0
        return min(1.0, 1.0 / math.sqrt(visits))

    # ── Diffusion Routing ──

    def route(
        self,
        query: str,
        providers: list[str],
        task_type: str = "general",
        existing_scores: dict[str, float] | None = None,
    ) -> ScoreMatchingResult:
        """Main routing: score matching → gradient descent → optimal provider.

        The diffusion process (analogous to reverse SDE):
          1. Start from uniform provider distribution (noise)
          2. Apply score function gradient: provider_t+1 = provider_t + lr × ∇score
          3. After K steps, select the provider with highest score

        This smooths out the discrete tree-like routing into a continuous flow.
        """
        if not providers:
            raise ValueError("No providers available")

        field = self.compute_field(query, providers, task_type, existing_scores)
        gradient_path: list[str] = []

        # Diffusion: iterate toward optimal provider
        # Start from the current best (based on static scores)
        current = field[0]
        gradient_path.append(current.provider)

        for step in range(self._diffusion_steps):
            # Find provider with max (score + diffusion_potential × remaining_steps_factor)
            remaining_factor = (self._diffusion_steps - step) / self._diffusion_steps
            best_next = max(
                field,
                key=lambda f: f.base_score + f.diffusion_potential * remaining_factor * 0.1,
            )
            if best_next.provider != gradient_path[-1]:
                gradient_path.append(best_next.provider)
            current = best_next

        # Boundary crossing detection
        boundary_crossing = any(
            self._boundary_distance(p, task_type, providers) < 0.3
            for p in gradient_path)

        # Update scores
        for provider in gradient_path:
            self._type_provider_scores[task_type][provider] += 0.01

        return ScoreMatchingResult(
            query=query[:80],
            task_type=task_type,
            field=field,
            top_provider=current.provider,
            top_score=current.base_score,
            gradient_path=gradient_path,
            convergence_steps=len(gradient_path),
            boundary_crossing=boundary_crossing,
        )

    # ── Learning: Update Score Function ──

    def record_outcome(
        self, provider: str, task_type: str, success: bool,
        latency_ms: float = 0, cost_yuan: float = 0,
    ) -> None:
        """Update the learned score function via Intentional TD.

        Intentional TD (Sharifnassab et al., arXiv:2604.19033):
          1. Compute ideal target score based on reward signal
          2. Compute error = target_ideal - current_score
          3. Apply η* = γ × |error| → reduces gap by fraction γ
             (If γ=0 → fallback to fixed learning_rate)

        Benefit over fixed _lr:
          - Cold start (large error): γ × big_gap → rapid initialization
          - Converged (small error): γ × tiny_gap → fine-grained tuning
          - No manual tuning: γ is interpretable ("30% toward ideal each step")
        """
        key = (provider, task_type)
        current = self._scores[key]

        # ── Reward signal ──
        reward = 1.0 if success else -0.3
        latency_bonus = max(0, 1.0 - latency_ms / 10000) * 0.1
        cost_bonus = max(0, 1.0 - cost_yuan / 0.1) * 0.1

        # ── Ideal target: what perfect knowledge would set ──
        if success:
            target_ideal = min(1.0, current + reward + latency_bonus + cost_bonus)
        else:
            target_ideal = max(0.01, current + reward)

        # ── Intentional TD step ──
        error = target_ideal - current
        if self._gamma > 0:
            # η* = γ × |error| → reduces gap by fraction γ
            adjusted = current + self._gamma * error
            # Clamp to valid score range
            new_score = max(0.01, min(1.0, adjusted))
        else:
            # Fallback: fixed learning rate (legacy mode)
            new_score = max(0.01, min(1.0, current + self._lr * error))

        # ── Record gradient for trend analysis ──
        grad = new_score - current
        self._scores[key] = new_score
        self._gradients[provider].append(grad)
        if len(self._gradients[provider]) > 50:
            self._gradients[provider] = self._gradients[provider][-50:]

    # ── Boundary Analysis ──

    def detect_boundary_tasks(
        self, providers: list[str], threshold: float = 0.3,
    ) -> list[str]:
        """Find task types where providers are near decision boundaries.

        These tasks benefit most from score matching (smooth routing).
        """
        boundary_types = []
        for task_type, p_scores in self._type_provider_scores.items():
            scores = list(p_scores.values())
            if len(scores) < 2:
                continue
            # Find minimum pairwise score difference
            min_diff = float('inf')
            sorted_scores = sorted(scores, reverse=True)
            for i in range(len(sorted_scores) - 1):
                diff = sorted_scores[i] - sorted_scores[i + 1]
                min_diff = min(min_diff, diff)
            if min_diff < threshold:
                boundary_types.append(task_type)
        return boundary_types

    # ── Statistics ──

    def stats(self) -> dict[str, Any]:
        total_visits = sum(
            len(scores) for scores in self._type_provider_scores.values())
        return {
            "score_entries": len(self._scores),
            "providers_tracked": len(self._gradients),
            "task_types": list(self._type_provider_scores.keys())[:10],
            "total_visits": total_visits,
            "boundary_tasks": len(
                self.detect_boundary_tasks(list(self._gradients.keys()))[:5]),
        }


# ═══ Singleton ═══

_score_router: ScoreMatchingRouter | None = None


def get_score_matching_router() -> ScoreMatchingRouter:
    global _score_router
    if _score_router is None:
        _score_router = ScoreMatchingRouter()
    return _score_router


__all__ = [
    "ScoreMatchingRouter", "ScoreField", "ScoreMatchingResult",
    "get_score_matching_router",
]
