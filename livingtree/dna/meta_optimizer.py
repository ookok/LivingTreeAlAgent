"""Meta-Optimizer — the system optimizes its own optimizer.

Meta-learning applied to hyperparameter tuning: instead of manually setting
MemPO alpha, surprise thresholds, or habit compiler sensitivity, the system
learns which values work best per domain through experience.

Architecture:
  ┌──────────────┐     record_performance()     ┌──────────────────┐
  │  LifeEngine  │ ────────────────────────────→ │  MetaOptimizer   │
  │    cycle     │ ←──────────────────────────── │  suggest_value() │
  └──────────────┘     auto_tune() for domain    └──────────────────┘
                                                          │
                                              ┌───────────┴───────────┐
                                              │  ParamConfig per param │
                                              │  - optimal_by_domain   │
                                              │  - tuning_history      │
                                              └───────────────────────┘

Bayesian optimization variant: mean of top-K performing values,
weighted by recency (exponential decay over time). Simple but effective.

Integration:
  After each LifeEngine cycle: record performance delta for all tracked params.
  Before next cycle: get suggested values via auto_tune(current_domain).
  Domain classification comes from auto_classifier or context analysis.
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

OPTIMIZER_STORE = Path(".livingtree/meta_optimizer.json")

DEFAULT_PARAMS: dict[str, float] = {
    "mempo_alpha": 0.1,
    "surprise_threshold": 0.4,
    "habit_confidence_min": 0.7,
    "exploration_rate": 0.15,
    "temperature": 0.7,
    "context_compression_ratio": 0.5,
    "curiosity_bonus": 0.05,
    "safety_margin": 0.3,
    "learning_rate": 0.01,
    "dopamine_decay": 0.95,
}


@dataclass
class ParamConfig:
    """Tracked hyperparameter with per-domain optimization history."""
    param_name: str
    current_value: float
    optimal_by_domain: dict[str, float] = field(default_factory=dict)
    tuning_history: list[dict[str, Any]] = field(default_factory=list)

    def record(self, value: float, performance_delta: float, domain: str) -> None:
        entry = {
            "value": value,
            "performance_delta": round(performance_delta, 6),
            "domain": domain,
            "timestamp": time.time(),
        }
        self.tuning_history.append(entry)
        if len(self.tuning_history) > 200:
            self.tuning_history = self.tuning_history[-100:]

    def top_k_values(self, domain: str, k: int = 5) -> list[float]:
        """Get top-K best performing values for a domain, weighted by recency."""
        domain_entries = [e for e in self.tuning_history if e["domain"] == domain]
        if not domain_entries:
            domain_entries = self.tuning_history[:]

        now = time.time()
        scored = []
        for e in domain_entries:
            recency_weight = math.exp(-0.01 * (now - e["timestamp"]) / 3600)
            scored.append((e["value"], e["performance_delta"] * recency_weight))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [v for v, _ in scored[:k]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "param_name": self.param_name,
            "current_value": self.current_value,
            "optimal_by_domain": self.optimal_by_domain,
            "history_size": len(self.tuning_history),
        }


class MetaOptimizer:
    """Learns how to learn — optimizes its own hyperparameters per domain.

    Uses a simple Bayesian-style optimization: for each domain, maintain
    the top-K performing parameter values weighted by recency. The suggested
    value is the weighted mean of the top-K.

    This is intentionally simple: complex Bayesian optimization (GP-UCB, EI)
    would introduce its own hyperparameters to tune.
    """

    TOP_K = 5
    MAX_HISTORY_PER_PARAM = 200
    RECENCY_HALF_LIFE_HOURS = 72.0

    def __init__(self) -> None:
        self._params: dict[str, ParamConfig] = {}
        self._domain: str = "general"
        self._domains_seen: set[str] = {"general"}
        self._tuning_events: int = 0
        self._load()

    # ── parameter management ─────────────────────────────────────

    def register_param(self, name: str, initial_value: float) -> None:
        """Start tracking a hyperparameter."""
        if name not in self._params:
            self._params[name] = ParamConfig(
                param_name=name,
                current_value=initial_value,
            )
            logger.debug(f"MetaOptimizer: registered param '{name}' = {initial_value}")
        else:
            self._params[name].current_value = initial_value

    def record_performance(
        self, param_name: str, value: float, performance_delta: float, domain: str = "",
    ) -> None:
        """Record how well a parameter value performed after a cycle.

        Args:
            param_name: which parameter was tested
            value: the value that was used
            performance_delta: positive = improvement, negative = regression
            domain: the task domain this performance was measured in
        """
        if param_name not in self._params:
            self.register_param(param_name, value)

        d = domain or self._domain
        self._domains_seen.add(d)
        self._params[param_name].record(value, performance_delta, d)
        self._tuning_events += 1

        if performance_delta > 0 and d not in self._params[param_name].optimal_by_domain:
            self._params[param_name].optimal_by_domain[d] = value
        elif performance_delta > 0:
            old_opt = self._params[param_name].optimal_by_domain.get(d, value)
            self._params[param_name].optimal_by_domain[d] = old_opt * 0.7 + value * 0.3

        logger.debug(
            "MetaOptimizer: record {}={:.4f} delta={:+.4f} domain={}",
            param_name, value, performance_delta, d,
        )

    def suggest_value(self, param_name: str, domain: str = "") -> float:
        """Suggest the best parameter value for a given domain.

        Uses weighted mean of top-K performing values in that domain,
        with recency weighting applied.

        Args:
            param_name: which parameter to suggest for
            domain: the task domain (uses current domain if empty)

        Returns:
            suggested float value, or current value if no history
        """
        if param_name not in self._params:
            self.register_param(param_name, DEFAULT_PARAMS.get(param_name, 0.5))

        d = domain or self._domain
        config = self._params[param_name]

        top_values = config.top_k_values(d, self.TOP_K)
        if not top_values:
            return config.current_value

        suggested = sum(top_values) / len(top_values)
        config.current_value = suggested
        return suggested

    def auto_tune(self, domain: str = "") -> dict[str, float]:
        """Suggest optimal values for ALL registered parameters for a domain.

        This is the primary entry point: called before each LifeEngine
        cycle to get updated parameter values.

        Args:
            domain: the task domain (uses current domain if empty)

        Returns:
            dict of param_name → suggested_value
        """
        d = domain or self._domain
        results: dict[str, float] = {}
        for name in self._params:
            results[name] = self.suggest_value(name, d)
        logger.info(f"MetaOptimizer: auto_tune for domain '{d}' → {len(results)} params")
        return results

    def set_domain(self, domain: str) -> None:
        self._domain = domain
        self._domains_seen.add(domain)

    def introspect_domain(self, recent_queries: list[str] = None) -> dict:
        """Zakharova introspection: identify current domain from behavior patterns.

        Instead of having the domain passed in externally, the system introspects
        to identify what domain it's operating in based on conversation history.
        Maps self-observation to domain classification.
        """
        domain_signals = {
            "code": ["def ", "import ", "class ", "function", "bug", "error", "build", "test"],
            "analysis": ["analyze", "explain", "why", "compare", "trade", "breakdown"],
            "creative": ["write", "generate", "story", "poem", "idea", "design"],
            "decision": ["choose", "recommend", "should", "option", "best", "priority"],
        }
        if not recent_queries:
            return {"domain": self._domain, "method": "fallback", "confidence": 0.3}
        scores = {}
        for domain, keywords in domain_signals.items():
            score = sum(1 for q in recent_queries for kw in keywords if kw in q.lower())
            scores[domain] = min(1.0, score / max(len(recent_queries), 1))
        if not scores:
            return {"domain": self._domain, "method": "no_signals", "confidence": 0.0}
        best_domain = max(scores, key=scores.get)
        best_score = scores[best_domain]
        second_best = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0
        confidence = best_score - second_best
        if confidence > 0.2:
            self.set_domain(best_domain)
        return {
            "domain": best_domain if confidence > 0.2 else self._domain,
            "method": "introspection",
            "confidence": round(max(0.0, confidence), 3),
            "score_breakdown": {k: round(v, 3) for k, v in sorted(scores.items(), key=lambda x: -x[1])},
        }

    # ── stats ────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return statistical summary of the meta-optimizer."""
        params_detail = {}
        for name, config in self._params.items():
            params_detail[name] = {
                "current_value": round(config.current_value, 4),
                "domains_optimized": len(config.optimal_by_domain),
                "history_size": len(config.tuning_history),
                "best_domains": dict(list(config.optimal_by_domain.items())[:5]),
            }

        return {
            "params_tracked": len(self._params),
            "domains_seen": sorted(self._domains_seen),
            "tuning_events": self._tuning_events,
            "current_domain": self._domain,
            "params_detail": params_detail,
        }

    # ── persistence ──────────────────────────────────────────────

    def _save(self) -> None:
        try:
            OPTIMIZER_STORE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "params": {
                    name: {
                        "current_value": cfg.current_value,
                        "optimal_by_domain": cfg.optimal_by_domain,
                        "tuning_history": cfg.tuning_history[-100:],
                    }
                    for name, cfg in self._params.items()
                },
                "domain": self._domain,
                "domains_seen": sorted(self._domains_seen),
                "tuning_events": self._tuning_events,
                "saved_at": time.time(),
            }
            OPTIMIZER_STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"MetaOptimizer: failed to save: {e}")

    def _load(self) -> None:
        if not OPTIMIZER_STORE.exists():
            for name, val in DEFAULT_PARAMS.items():
                self.register_param(name, val)
            self._save()
            return

        try:
            data = json.loads(OPTIMIZER_STORE.read_text(encoding="utf-8"))
            for name, cfg_data in data.get("params", {}).items():
                self._params[name] = ParamConfig(
                    param_name=name,
                    current_value=cfg_data.get("current_value", 0.5),
                    optimal_by_domain=cfg_data.get("optimal_by_domain", {}),
                    tuning_history=cfg_data.get("tuning_history", []),
                )
            self._domain = data.get("domain", "general")
            self._domains_seen = set(data.get("domains_seen", ["general"]))
            self._tuning_events = data.get("tuning_events", 0)
            logger.info(
                f"MetaOptimizer: loaded {len(self._params)} params, "
                f"{len(self._domains_seen)} domains, {self._tuning_events} events"
            )
        except Exception as e:
            logger.warning(f"MetaOptimizer: failed to load, using defaults: {e}")
            for name, val in DEFAULT_PARAMS.items():
                self.register_param(name, val)


# ═══ Singleton ═══

_meta_optimizer: MetaOptimizer | None = None


def get_meta_optimizer() -> MetaOptimizer:
    global _meta_optimizer
    if _meta_optimizer is None:
        _meta_optimizer = MetaOptimizer()
        logger.info("MetaOptimizer singleton created")
    return _meta_optimizer


__all__ = [
    "ParamConfig",
    "MetaOptimizer",
    "get_meta_optimizer",
]
