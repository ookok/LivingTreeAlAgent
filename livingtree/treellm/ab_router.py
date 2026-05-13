"""ABRouter — Provider/model-level A/B testing for LLM routing strategies.

Allows defining experiments with control/treatment groups for provider selection.
Requests are randomly assigned to groups. After enough samples, auto-reports
which group is statistically better.

CLI: python -m livingtree ab-report [experiment_id]

Integration:
    ab = get_ab_router()
    ab.create("topk_vs_aggregate", {
        "A": {"top_k": 3, "aggregate": False},
        "B": {"top_k": 1, "aggregate": True},
    })
    group = ab.assign("topk_vs_aggregate")  # → "A" or "B"
    ab.record("topk_vs_aggregate", group, depth, latency, user_signal)
"""

from __future__ import annotations

import json
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from loguru import logger

EXPERIMENTS_FILE = Path(".livingtree/ab_experiments.json")


class ABRouter:
    """Provider/routing-level A/B testing framework."""

    _instance: Optional["ABRouter"] = None

    @classmethod
    def instance(cls) -> "ABRouter":
        if cls._instance is None:
            cls._instance = ABRouter()
        return cls._instance

    def __init__(self):
        self._experiments: dict[str, dict] = {}

    def create(self, exp_id: str, groups: dict[str, dict[str, Any]]) -> bool:
        """Create experiment with named groups.

        groups = {"control": {"top_k":3}, "treatment": {"top_k":1, "aggregate":True}}
        """
        if exp_id in self._experiments:
            return False
        self._experiments[exp_id] = {
            "groups": groups,
            "results": {g: [] for g in groups},
            "created": time.time(),
        }
        logger.info(f"ABRouter: created experiment '{exp_id}' ({len(groups)} groups)")
        return True

    def assign(self, exp_id: str) -> str:
        """Randomly assign to a group. Returns group name."""
        exp = self._experiments.get(exp_id)
        if not exp:
            return ""
        groups = list(exp["groups"].keys())
        return random.choice(groups)

    def get_params(self, exp_id: str, group: str) -> dict[str, Any]:
        """Get the configured parameters for an assigned group."""
        exp = self._experiments.get(exp_id)
        if not exp:
            return {}
        return dict(exp["groups"].get(group, {}))

    def record(self, exp_id: str, group: str, depth: float,
               latency_ms: float, user_signal: float) -> None:
        """Record outcome for an assigned group."""
        exp = self._experiments.get(exp_id)
        if not exp or group not in exp["results"]:
            return
        exp["results"][group].append({
            "depth": depth, "latency": latency_ms, "signal": user_signal,
        })

    def report(self, exp_id: str) -> dict[str, Any]:
        """Generate statistical comparison report."""
        exp = self._experiments.get(exp_id)
        if not exp:
            return {"error": f"Experiment '{exp_id}' not found"}

        report = {"experiment": exp_id, "groups": {}}
        for group, data in exp["results"].items():
            n = len(data)
            if n < 10:
                report["groups"][group] = {"n": n, "status": "insufficient_data"}
                continue
            avg_depth = sum(d["depth"] for d in data) / n
            avg_lat = sum(d["latency"] for d in data) / n
            avg_signal = sum(d["signal"] for d in data) / n
            report["groups"][group] = {
                "n": n, "avg_depth": round(avg_depth, 3),
                "avg_latency_ms": round(avg_lat, 0),
                "avg_signal": round(avg_signal, 3),
            }

        # Determine winner
        groups = list(report["groups"].keys())
        if len(groups) >= 2 and all(
            report["groups"][g].get("n", 0) >= 10 for g in groups
        ):
            best = max(groups, key=lambda g: report["groups"][g]["avg_depth"])
            report["winner"] = best

        return report

    def stop(self, exp_id: str) -> dict:
        """Stop an experiment and return final report."""
        report = self.report(exp_id)
        if exp_id in self._experiments:
            del self._experiments[exp_id]
        return report

    def list_experiments(self) -> list[str]:
        return list(self._experiments.keys())

    def stats(self) -> dict:
        return {"active_experiments": len(self._experiments)}


_ab: Optional[ABRouter] = None


def get_ab_router() -> ABRouter:
    global _ab
    if _ab is None:
        _ab = ABRouter()
    return _ab


__all__ = ["ABRouter", "get_ab_router"]
