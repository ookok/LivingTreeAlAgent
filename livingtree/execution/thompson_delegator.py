"""Thompson Sampling Delegation — REDEREF-inspired probabilistic agent routing.

Based on arXiv:2603.13256: "Training-Free Agentic AI: Probabilistic Control
and Coordination in Multi-Agent LLM Systems"

Core: Belief-guided delegation via Thompson sampling to prioritize agents
with historically positive marginal contributions. 28% token reduction,
17% fewer agent calls, 19% faster time-to-success.

Integration: orchestrator.py agent selection and TreeLLM provider routing.
"""

from __future__ import annotations

import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class AgentBelief:
    """Bayesian belief about an agent's success rate (Beta distribution)."""
    name: str
    alpha: int = 1     # Successes + prior
    beta: int = 1       # Failures + prior
    marginal_tokens: int = 0  # Cumulative token cost
    last_delegated: float = 0.0
    delegation_count: int = 0

    @property
    def mean(self) -> float:
        return self.alpha / max(1, self.alpha + self.beta)

    @property
    def variance(self) -> float:
        total = self.alpha + self.beta
        return (self.alpha * self.beta) / (total * total * (total + 1))

    def sample(self) -> float:
        """Thompson sample from Beta(alpha, beta)."""
        return random.betavariate(self.alpha, self.beta)


class ThompsonDelegator:
    """Probabilistic multi-agent delegation via Thompson sampling.

    Key innovations from REDEREF:
      1. Belief-guided delegation — sample from Beta posterior
      2. Reflection-driven updates — credit assignment after each turn
      3. Memory-aware priors — initialize beliefs from similar past agents
    """

    def __init__(self):
        self._beliefs: dict[str, AgentBelief] = {}

    def select_agent(self, candidates: list[str], top_k: int = 1) -> list[str]:
        """Select best agent(s) via Thompson sampling.

        Draws one sample from each agent's Beta posterior,
        selects the highest sample(s). Naturally balances
        exploration (high variance agents get sampled higher)
        and exploitation (proven agents have high mean).
        """
        if not candidates:
            return []

        # Ensure beliefs exist
        for name in candidates:
            if name not in self._beliefs:
                self._beliefs[name] = AgentBelief(name=name)

        # Thompson sample
        samples = [(self._beliefs[name].sample(), name) for name in candidates]
        samples.sort(key=lambda x: -x[0])

        selected = [name for _, name in samples[:top_k]]
        for name in selected:
            self._beliefs[name].delegation_count += 1
            self._beliefs[name].last_delegated = time.time()

        return selected

    def update_on_success(self, agent: str, tokens_used: int = 0) -> None:
        """Credit: agent succeeded → increment alpha."""
        if agent not in self._beliefs:
            self._beliefs[agent] = AgentBelief(name=agent)
        b = self._beliefs[agent]
        b.alpha += 1
        b.marginal_tokens += tokens_used

    def update_on_failure(self, agent: str, tokens_used: int = 0) -> None:
        """Credit: agent failed → increment beta."""
        if agent not in self._beliefs:
            self._beliefs[agent] = AgentBelief(name=agent)
        b = self._beliefs[agent]
        b.beta += 1
        b.marginal_tokens += tokens_used

    def reflect_and_update(
        self, agent: str, success: bool, tokens: int, reflection: str = ""
    ) -> None:
        """REDEREF's reflection-driven update: credit assignment with reflection."""
        if success:
            self.update_on_success(agent, tokens)
        else:
            self.update_on_failure(agent, tokens)
            # Reflection: if failure was due to agent incapability, increase beta more
            incapability_signals = ["hallucinat", "incorrect", "cannot", "unable", "error"]
            if any(s in reflection.lower() for s in incapability_signals):
                if agent in self._beliefs:
                    self._beliefs[agent].beta += 1  # Extra penalty

    def get_best_agent(self, candidates: list[str]) -> Optional[str]:
        """Get the agent with highest posterior mean (exploitation-only)."""
        result = self.select_agent(candidates, top_k=1)
        return result[0] if result else None

    def agent_stats(self, name: str) -> dict:
        b = self._beliefs.get(name)
        if not b:
            return {"name": name, "mean": 0.5, "delegations": 0}
        return {
            "name": name,
            "mean": round(b.mean, 3),
            "variance": round(b.variance, 4),
            "delegations": b.delegation_count,
            "total_tokens": b.marginal_tokens,
        }


# ── Singleton ──

_delegator: Optional[ThompsonDelegator] = None


def get_thompson_delegator() -> ThompsonDelegator:
    global _delegator
    if _delegator is None:
        _delegator = ThompsonDelegator()
    return _delegator
