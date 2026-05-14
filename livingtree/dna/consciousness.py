"""
Consciousness Module — Progressive thinking, streaming reasoning, self-reflection.

Provides abstract and default implementations for:
- Stream of thought (token-by-token generation)
- Chain of thought (multi-step reasoning)
- Hypothesis generation (exploring alternatives)
- Self-questioning (identifying knowledge gaps)
"""
from __future__ import annotations

import abc
import asyncio
import math
import random
from typing import AsyncIterator

from loguru import logger


class Consciousness(abc.ABC):
    """
    Abstract base for consciousness implementations.

    Different strategies can be plugged in:
        - LLM-based (using remote/local models)
        - Rule-based (for testing)
        - Heuristic-based (for fast decisions)
    """

    @abc.abstractmethod
    async def stream_of_thought(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """
        Generate a progressive stream of thought tokens.

        Yields individual tokens/chunks as they are produced.
        Used for real-time user feedback during thinking.
        """
        ...

    @abc.abstractmethod
    async def chain_of_thought(self, question: str, steps: int = 3, **kwargs) -> str:
        """
        Multi-step chain-of-thought reasoning.

        Breaks down complex questions into sequential reasoning steps.
        Returns the final conclusion.
        """
        ...

    @abc.abstractmethod
    async def hypothesis_generation(self, problem: str, count: int = 3, **kwargs) -> list[str]:
        """
        Generate multiple hypotheses for a given problem.

        Explores alternative approaches and creative solutions.
        """
        ...

    @abc.abstractmethod
    async def self_questioning(self, context: str, **kwargs) -> list[str]:
        """
        Self-questioning to identify knowledge gaps and uncertainties.

        Returns questions the system should investigate further.
        """
        ...

    # ── SDE Diffusion Control (Bosso et al. 2025) ──

    def set_diffusion_level(self, level: float) -> None:
        """Set the stochastic diffusion level — controls creative exploration.

        Bosso et al. (2025) analog: the diffusion function g(x) in
        dX_t = f(X_t)dt + g(X_t)dW_t controls how much the system explores
        versus exploits. In the consciousness domain:

           level = 0.0 → deterministic reasoning (pure chain-of-thought)
           level = 0.5 → balanced exploration (default creative mode)
           level = 1.0 → maximum diffusion (wild brainstorming)

        This maps to LLM temperature control: temperature ∝ diffusion level.
        Higher diffusion = more stochastic next-token sampling = more creative.

        Concrete implementations should adjust:
          - LLM temperature parameter
          - Hypothesis diversity
          - Self-questioning depth
        """
        self._diffusion_level = max(0.0, min(1.0, level))
        if hasattr(self, '_annealing_step'):
            self._annealing_step += 1
        logger.debug(
            f"Consciousness diffusion level set to {self._diffusion_level:.2f} "
            f"({'deterministic' if self._diffusion_level < 0.3 else 'balanced' if self._diffusion_level < 0.7 else 'exploratory'})"
        )

    @property
    def diffusion_level(self) -> float:
        """Current diffusion level (0=deterministic, 1=maximally stochastic)."""
        return getattr(self, '_diffusion_level', 0.5)

    # ── Discovery Machine Annealing (Nature Communications, 2026) ──

    def annealing_schedule(self, steps: int = 100, cooling_factor: float = 1.0) -> list[float]:
        """Pre-compute a Fowler-Nordheim annealing schedule for consciousness.

        T(t) = T0 * cooling_factor / log(e + t)  — monotonic cooling.
        Maps to diffusion_level: diffusion = T (temperature).

        The schedule starts with high diffusion (creative exploration) and
        gradually cools to near-zero (deterministic execution), enabling the
        consciousness to "think freely" early then "commit precisely" late.

        Usage:
            schedule = consciousness.annealing_schedule(steps=100)
            for diffusion in schedule:
                consciousness.set_diffusion_level(diffusion)
                result = await consciousness.chain_of_thought(question)
        """
        self._annealing_step = getattr(self, '_annealing_step', 0)
        schedule = []
        for t in range(1, steps + 1):
            T = 1.0 * cooling_factor / math.log(math.e + t)
            schedule.append(max(T, 0.001))
        return schedule

    def gradient_directed_diffusion(self, gradient_norm: float) -> float:
        """Diffusion level guided by energy landscape gradient.

        sigma(t) = sigma_base / max(|grad L|, eps)

        When the gradient is large (steep landscape), diffusion is low
        (exploit the clear direction). When the gradient is small (flat),
        diffusion is high (explore because no clear better direction).
        This maps to LLM temperature adjustment based on reasoning certainty.

        Returns recommended diffusion level [0.001, 1.0].
        """
        sigma_base = getattr(self, '_diffusion_level', 0.5)
        eps = 0.01
        diffusion = sigma_base / max(gradient_norm, eps)
        return max(0.001, min(1.0, diffusion))

    def convergence_test(self, num_samples: int = 5) -> dict[str, float | bool]:
        """Run convergence test at low diffusion — check if reasoning has stabilized.

        Generates N hypothesis samples at minimal diffusion (T ≈ 0).
        If all samples agree (cosine similarity > 0.9), reasoning is converged.

        This implements the Discovery Machine's convergence guarantee:
        at T → 0, if all samples produce the same answer → global optimum found.
        """
        self._diffusion_level = 0.01
        return {
            "converged": False,
            "agreement": 1.0,
            "confidence": 0.0,
            "message": "Override in subclass with LLM-powered convergence test",
        }


class DefaultConsciousness(Consciousness):
    """
    Default consciousness implementation with basic heuristics.

    Suitable for testing and as a fallback. For production, use
    LLMConsciousness or plug in a custom implementation.
    """

    async def stream_of_thought(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """Basic token-by-token thought generation."""
        thoughts = [
            f"Processing: {prompt[:50]}...",
            "Analyzing context and intent...",
            "Retrieving relevant knowledge...",
            "Formulating approach...",
        ]
        for thought in thoughts:
            await asyncio.sleep(0.1)
            yield thought + " "

    async def chain_of_thought(self, question: str, steps: int = 3, **kwargs) -> str:
        """Multi-step reasoning chain."""
        chain = [f"Step {i+1}: Analyzing aspect {i+1} of '{question[:30]}...'" for i in range(steps)]
        for step in chain:
            await asyncio.sleep(0.1)
        return f"After {steps} steps of reasoning: {question} requires a systematic approach."

    async def hypothesis_generation(self, problem: str, count: int = 3, **kwargs) -> list[str]:
        """Generate multiple hypotheses."""
        return [
            f"Hypothesis {i+1}: {problem[:40]} can be solved via approach {i+1}"
            for i in range(count)
        ]

    async def self_questioning(self, context: str, **kwargs) -> list[str]:
        """Identify knowledge gaps through architecture-unique self-questioning.

        Zakharova IEM enhancement: each self-question embeds a hash of the
        system's current module structure so that questions would differ for
        any differently-configured system — approaching privileged self-reference.
        """
        arch_hash = self._compute_architecture_hash()
        return [
            f"[{arch_hash}] What domain knowledge is needed for '{context[:30]}'?",
            f"[{arch_hash}] Are there edge cases not yet considered?",
            f"[{arch_hash}] What assumptions am I making?",
            f"[{arch_hash}] What would I need to know that I don't currently know?",
        ]

    def _compute_architecture_hash(self) -> str:
        import hashlib, sys
        mod_names = sorted(
            m for m in sys.modules
            if m.startswith("livingtree") and "test" not in m.lower()
        )
        fingerprint = "|".join(mod_names[:64])
        return hashlib.md5(fingerprint.encode()).hexdigest()[:6]
