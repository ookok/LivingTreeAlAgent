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
        logger.debug(
            f"Consciousness diffusion level set to {self._diffusion_level:.2f} "
            f"({'deterministic' if self._diffusion_level < 0.3 else 'balanced' if self._diffusion_level < 0.7 else 'exploratory'})"
        )

    @property
    def diffusion_level(self) -> float:
        """Current diffusion level (0=deterministic, 1=maximally stochastic)."""
        return getattr(self, '_diffusion_level', 0.5)


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
        """Identify knowledge gaps through self-questioning."""
        return [
            f"What domain knowledge is needed for '{context[:30]}'?",
            "Are there edge cases not yet considered?",
            "What assumptions am I making?",
        ]
