"""RouteLearner — Cross-session knowledge distillation for model routing.

Transfers knowledge from models.dev capabilities + execution history into
TreeLLM routing weights. Learns which models perform best for each task type
over time, enabling data-driven provider selection.

Architecture:
  1. Capability Distillation: models.dev → StructuredLearnedProfile
  2. Performance Learning: FitnessLandscape history → per-model success rates
  3. Weight Computation: capability score × success rate → routing priority
  4. Route Optimization: inject weights into TreeLLM provider selection

Usage:
    learner = get_route_learner()
    await learner.distill_from_models_dev()
    weights = learner.get_routing_weights(domain="code_engineering")
    # Auto-updates TreeLLM provider priority based on learned performance
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

LEARNER_DIR = Path(".livingtree/meta")
LEARNER_FILE = LEARNER_DIR / "route_weights.json"


# ── Data Types ─────────────────────────────────────────────────────

@dataclass
class LearnedProfile:
    """Distilled model capability profile from models.dev."""
    model_id: str
    provider: str
    context_length: int = 4096
    reasoning: bool = False
    tool_call: bool = False
    structured_output: bool = False
    supports_images: bool = False
    is_free: bool = False
    cost_score: float = 0.5         # 0-1, higher=cheaper
    capability_score: float = 0.5   # 0-1, higher=more capable

    @property
    def composite_score(self) -> float:
        return round(
            self.capability_score * 0.4 +
            (1.0 - self.cost_score) * 0.3 +  # lower cost = higher weight
            (self.context_length / 1_000_000) * 0.3, 4)


@dataclass
class RoutingWeight:
    """Per-task-type per-model routing weight."""
    model_id: str
    task_type: str
    weight: float = 1.0             # Base weight
    success_rate: float = 0.5       # Historical success rate
    avg_latency_ms: float = 0.0
    sample_count: int = 0
    last_used: float = 0.0
    last_updated: float = field(default_factory=time.time)


class RouteLearner:
    """Cross-session route optimization through capability + performance learning.

    Integration:
      - models_dev_sync: source model capability data
      - fitness_landscape: source execution performance data
      - TreeLLM.route_layered: consumer of routing weights
    """

    # Domain-specific capability bonuses
    DOMAIN_CAPABILITY_BONUS: dict[str, dict[str, float]] = {
        "code_engineering": {"tool_call": 0.3, "structured_output": 0.2, "context_length": 0.2},
        "environmental_report": {"structured_output": 0.3, "context_length": 0.3},
        "data_analysis": {"tool_call": 0.2, "reasoning": 0.3},
        "question": {"cost_score": 0.4},  # Cheap is best for Q&A
        "general": {},
    }

    def __init__(self):
        self._profiles: dict[str, LearnedProfile] = {}
        self._weights: dict[str, dict[str, RoutingWeight]] = defaultdict(dict)
        self._loaded = False
        self._load()

    # ── Capability Distillation ────────────────────────────────────

    async def distill_from_models_dev(self) -> int:
        """Extract model capabilities from models.dev into LearnedProfiles.

        Returns number of profiles distilled.
        """
        try:
            from .models_dev_sync import get_models_dev_sync
            sync = get_models_dev_sync()
            if not sync._models:
                await sync.refresh()

            count = 0
            for model_id, model in sync._models.items():
                profile = LearnedProfile(
                    model_id=model_id,
                    provider=model.provider_id,
                    context_length=model.limit.context,
                    reasoning=model.reasoning,
                    tool_call=model.tool_call,
                    structured_output=model.structured_output,
                    supports_images=model.modalities.supports_images,
                    is_free=model.cost.is_free,
                    cost_score=self._compute_cost_score(model.cost.input_cny),
                    capability_score=self._compute_capability_score(model),
                )
                self._profiles[model_id] = profile
                count += 1

            logger.info(f"RouteLearner: distilled {count} model profiles from models.dev")
            self._save()
            return count
        except Exception as e:
            logger.debug(f"RouteLearner distill: {e}")
            return 0

    # ── Performance Learning ──────────────────────────────────────

    def learn_from_fitness(self, trajectories: list[dict] | None = None) -> int:
        """Update routing weights from fitness landscape execution history.

        Each trajectory provides: model_id, task_type, success, latency_ms.
        Uses EMA (exponential moving average) for smooth weight updates.

        Returns number of weights updated.
        """
        if trajectories is None:
            try:
                from ..execution.fitness_landscape import get_fitness_landscape
                landscape = get_fitness_landscape()
                trajectories = [
                    {
                        "model_id": ts.trajectory_id,
                        "task_type": "general",
                        "success": ts.fitness.reliability > 0.5,
                        "latency_ms": ts.total_ms,
                    }
                    for ts in landscape._trajectories.values()
                ]
            except Exception:
                return 0

        updated = 0
        for t in trajectories:
            model_id = t.get("model_id", "")
            task_type = t.get("task_type", "general")
            success = 1.0 if t.get("success") else 0.0
            latency = t.get("latency_ms", 0)

            if not model_id:
                continue

            w = self._weights[task_type].get(model_id)
            if w is None:
                w = RoutingWeight(model_id=model_id, task_type=task_type)
                self._weights[task_type][model_id] = w

            # EMA update: 80% old + 20% new
            w.success_rate = round(0.8 * w.success_rate + 0.2 * success, 3)
            w.avg_latency_ms = round(
                0.8 * w.avg_latency_ms + 0.2 * latency, 1) if w.avg_latency_ms else latency
            w.sample_count += 1
            w.last_used = time.time()
            w.last_updated = time.time()

            # Update weight: base × success_rate × recency_boost
            profile = self._profiles.get(model_id)
            base = profile.composite_score if profile else 0.5
            recency = min(1.5, 1.0 + w.sample_count * 0.05)
            w.weight = round(base * w.success_rate * recency, 4)

            updated += 1

        if updated:
            logger.info(f"RouteLearner: learned from {updated} trajectory samples")
            self._save()

        return updated

    # ── Routing Weights ───────────────────────────────────────────

    def get_routing_weights(
        self, task_type: str = "general", top_n: int = 10,
    ) -> list[tuple[str, float, LearnedProfile | None]]:
        """Get ranked routing weights for a task type.

        Returns list of (model_id, weight, profile) sorted by weight descending.
        """
        task_weights = self._weights.get(task_type, {})
        general_weights = self._weights.get("general", {})
        merged: dict[str, float] = {}

        for mid, w in general_weights.items():
            merged[mid] = w.weight

        for mid, w in task_weights.items():
            # Task-specific weights override general with higher priority
            merged[mid] = w.weight * 1.2  # +20% boost for task-specific

        # Boost by domain capability bonus
        bonuses = self.DOMAIN_CAPABILITY_BONUS.get(task_type, {})
        for mid in merged:
            profile = self._profiles.get(mid)
            if profile and bonuses:
                for cap, bonus in bonuses.items():
                    if getattr(profile, cap, False) or cap == "context_length":
                        if cap == "context_length":
                            merged[mid] += bonus * (profile.context_length / 1_000_000)
                        else:
                            merged[mid] += bonus

        ranked = sorted(merged.items(), key=lambda x: x[1], reverse=True)
        return [(mid, w, self._profiles.get(mid)) for mid, w in ranked[:top_n]]

    def best_model_for(self, task_type: str = "general") -> str | None:
        """Return the best model for a given task type."""
        ranked = self.get_routing_weights(task_type, top_n=1)
        return ranked[0][0] if ranked else None

    def inject_weights_to_registry(self) -> int:
        """Inject learned weights into ModelRegistry provider models.

        Updates the enabled flag and adds weight metadata to provider models.
        Returns number of models updated.
        """
        try:
            from .model_registry import get_model_registry
            registry = get_model_registry()
            updated = 0

            for task_type in self._weights:
                weights = self.get_routing_weights(task_type, top_n=50)
                for mid, w, _profile in weights:
                    # Find this model in any provider
                    for pid in registry.get_all_providers():
                        for m in registry.get_models(pid):
                            if m.id == mid or m.id.endswith(mid.split("/")[-1]):
                                m.enabled = w > 0.3
                                updated += 1

            if updated:
                logger.info(f"RouteLearner: injected weights for {updated} models")
            return updated
        except Exception as e:
            logger.debug(f"RouteLearner inject: {e}")
            return 0

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _compute_cost_score(input_cny: float) -> float:
        """Normalize cost to 0-1 score (higher = cheaper)."""
        if input_cny <= 0:
            return 1.0
        if input_cny <= 1.0:
            return 0.9
        if input_cny <= 5.0:
            return 0.7
        if input_cny <= 10.0:
            return 0.5
        if input_cny <= 20.0:
            return 0.3
        return 0.1

    @staticmethod
    def _compute_capability_score(model: Any) -> float:
        """Compute composite capability score (0-1)."""
        score = 0.3  # baseline
        if model.reasoning:
            score += 0.2
        if model.tool_call:
            score += 0.15
        if model.structured_output:
            score += 0.1
        if model.modalities.supports_images:
            score += 0.1
        # Context length bonus
        ctx = model.limit.context
        if ctx >= 1_000_000:
            score += 0.15
        elif ctx >= 128_000:
            score += 0.1
        elif ctx >= 32_000:
            score += 0.05
        return min(1.0, score)

    # ── Persistence ────────────────────────────────────────────────

    def _save(self):
        try:
            LEARNER_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "profiles": {
                    mid: {
                        "model_id": p.model_id,
                        "provider": p.provider,
                        "context_length": p.context_length,
                        "reasoning": p.reasoning,
                        "tool_call": p.tool_call,
                        "capability_score": p.capability_score,
                        "cost_score": p.cost_score,
                    }
                    for mid, p in self._profiles.items()
                },
                "weights": {
                    tt: {
                        mid: {
                            "model_id": w.model_id,
                            "task_type": w.task_type,
                            "weight": w.weight,
                            "success_rate": w.success_rate,
                            "sample_count": w.sample_count,
                            "last_updated": w.last_updated,
                        }
                        for mid, w in task_weights.items()
                    }
                    for tt, task_weights in self._weights.items()
                },
            }
            LEARNER_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"RouteLearner save: {e}")

    def _load(self):
        try:
            if not LEARNER_FILE.exists():
                return
            data = json.loads(LEARNER_FILE.read_text())
            for mid, pd in data.get("profiles", {}).items():
                self._profiles[mid] = LearnedProfile(**pd)
            for tt, td in data.get("weights", {}).items():
                for mid, wd in td.items():
                    self._weights[tt][mid] = RoutingWeight(**wd)
            self._loaded = True
            logger.info(f"RouteLearner: loaded {len(self._profiles)} profiles, "
                        f"{sum(len(w) for w in self._weights.values())} weights")
        except Exception as e:
            logger.debug(f"RouteLearner load: {e}")

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        total_weights = sum(len(w) for w in self._weights.values())
        total_samples = sum(
            w.sample_count for tw in self._weights.values() for w in tw.values())
        return {
            "profiles": len(self._profiles),
            "weights": total_weights,
            "task_types": len(self._weights),
            "total_samples": total_samples,
            "best_code_model": self.best_model_for("code_engineering"),
            "best_environmental_model": self.best_model_for("environmental_report"),
        }

    # ── Dynamic Capabilities Injection ───────────────────────────

    def update_provider_capabilities(self) -> int:
        """Dynamically update PROVIDER_CAPABILITIES from learned profiles.

        Replaces the static capability dict with live data: if a model
        performs well at coding tasks, its capabilities automatically
        include "code". This closes the gap between hardcoded labels
        and actual model behavior.
        """
        try:
            from .holistic_election import PROVIDER_CAPABILITIES
            updated = 0
            # Map learned weight patterns to capability keywords
            domain_to_cap: dict[str, str] = {
                "code_engineering": "代码",
                "reasoning": "推理",
                "question": "对话",
                "data_analysis": "分析",
                "environmental_report": "分析",
            }
            for model_id, profile in self._profiles.items():
                # Find this model in PROVIDER_CAPABILITIES
                for provider_name in PROVIDER_CAPABILITIES:
                    if provider_name in model_id.lower() or model_id.lower() in provider_name:
                        caps = PROVIDER_CAPABILITIES[provider_name]
                        # Add learned capabilities
                        if profile.reasoning and "推理" not in caps:
                            caps.append("推理"); updated += 1
                        if profile.tool_call and "工具" not in caps:
                            caps.append("工具"); updated += 1
                        if profile.structured_output and "结构化" not in caps:
                            caps.append("结构化"); updated += 1
                        break
            if updated:
                logger.info(f"RouteLearner: updated {updated} dynamic capabilities")
            return updated
        except ImportError:
            return 0


# ── Singleton ──────────────────────────────────────────────────────

_route_learner: RouteLearner | None = None


def get_route_learner() -> RouteLearner:
    global _route_learner
    if _route_learner is None:
        _route_learner = RouteLearner()
    return _route_learner


def reset_route_learner() -> None:
    global _route_learner
    _route_learner = None
