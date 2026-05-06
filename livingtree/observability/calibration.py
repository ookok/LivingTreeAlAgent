"""
Rollout Calibration Tracker with cross-component failure attribution.

Inspired by:
- foresight paper (arXiv:2601.03905): rollout calibration
- Agentic Harness paper: cross-component failure attribution chains

Records prediction vs actual outcomes, computes accuracy metrics, derives
trust scores, AND traces failures across components to identify root causes.

Design goals:
- Minimal dependencies
- Simple JSON persistence at: .livingtree/calibration.json + attribution.json
- Extensible, with a small API surface suitable for unit tests and quick integration
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict

from loguru import logger


@dataclass
class AttributionEntry:
    """A cross-component failure attribution record.

    Tracks which component was responsible for a failure, the failure chain
    (which components were called before it), and the specific root cause.

    Agentic Harness concept: "when something fails, trace backwards through
    all interacting components to find the true origin."
    """
    id: str
    timestamp: float
    simulation_id: str
    failed_component: str       # Component that ultimately failed
    root_cause_component: str   # Component determined to be the root cause
    failure_chain: list[str] = field(default_factory=list)  # Ordered component call chain
    error_message: str = ""
    severity: str = "warning"   # info, warning, error, critical
    resolved: bool = False
    resolution: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CalibrationEntry:
    """A record of one rollout prediction vs actual outcome."""
    timestamp: float
    simulation_id: str
    prediction: str
    actual: str
    was_correct: bool
    provider: str
    latency_ms: float
    category: str  # one of "provider_match", "quality", "latency", "cost"


class CalibrationTracker:
    """Tracker for rollout calibration entries and derived metrics."""

    def __init__(self) -> None:
        self.entries: List[CalibrationEntry] = []
        self.attributions: List[AttributionEntry] = []
        self._storage_path = self._default_storage_path()
        self._attribution_path = os.path.join(os.path.dirname(self._storage_path) if os.path.dirname(self._storage_path) else ".livingtree", "attribution.json")
        os.makedirs(os.path.dirname(self._attribution_path) or ".livingtree", exist_ok=True)
        self._load()
        self._load_attributions()

    # ── Storage ──

    @staticmethod
    def _default_storage_path() -> str:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".livingtree"))
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, "calibration.json")

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        if text is None:
            return []
        toks = []
        for word in str(text).split():
            w = word.strip(".,!?;:\"'()[]{}")
            if w:
                toks.append(w.lower())
        return toks

    @staticmethod
    def _jaccard(a: str, b: str) -> float:
        sa = set(CalibrationTracker._tokenize(a))
        sb = set(CalibrationTracker._tokenize(b))
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    def _load(self) -> None:
        path = self._storage_path
        if not os.path.exists(path):
            self.entries = []
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.entries = [CalibrationEntry(**e) for e in data]
        except Exception:
            self.entries = []

    def _save(self) -> None:
        path = self._storage_path
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump([asdict(e) for e in self.entries], f, indent=2)
        except Exception:
            pass

    # ── Recording ──

    def record(
        self,
        simulation_id: str,
        prediction: str,
        actual: str,
        provider: str = "",
        latency_ms: float = 0.0,
        category: str = "provider_match",
    ) -> None:
        """Record a single rollout attempt and its outcome.

        Auto-detects correctness. A fuzzy match improves provider_match correctness
        when exact equality fails but the tokens overlap by >50%.
        """
        pred = (prediction or "").strip()
        act = (actual or "").strip()

        # Basic exact match (case-insensitive for robustness)
        is_correct = pred.lower() == act.lower()

        # Fuzzy provider_match fallback: >50% word overlap implies correctness
        if not is_correct and category == "provider_match":
            j = self._jaccard(pred, act)
            if j > 0.5:
                is_correct = True

        entry = CalibrationEntry(
            timestamp=time.time(),
            simulation_id=simulation_id,
            prediction=pred,
            actual=act,
            was_correct=bool(is_correct),
            provider=provider,
            latency_ms=float(latency_ms),
            category=category,
        )
        self.entries.append(entry)
        logger.debug(f"Calibration recorded: {simulation_id} correct={is_correct}")

        # Persist every 10 records to keep I/O minimal yet reliable
        if len(self.entries) % 10 == 0:
            self._save()

    # ── Queries ──

    def get_accuracy(self, window: int = 100, category: Optional[str] = None) -> float:
        if window <= 0:
            return 0.0
        subset = self.entries[-window:]
        if category is not None:
            subset = [e for e in subset if e.category == category]
        if not subset:
            return 0.0
        correct = sum(1 for e in subset if e.was_correct)
        return correct / len(subset)

    def get_trust_score(self) -> float:
        total = len(self.entries)
        if total == 0:
            return 0.0
        acc_all = self.get_accuracy(window=total)
        acc_last20 = self.get_accuracy(window=min(20, total))
        extra = 1.0 if total > 10 else (total / 10.0)
        score = 0.5 * acc_all + 0.3 * acc_last20 + 0.2 * extra
        return max(0.0, min(1.0, score))

    def get_category_breakdown(self) -> dict:
        breakdown: dict = {}
        for e in self.entries:
            c = e.category
            if c not in breakdown:
                breakdown[c] = {"correct": 0, "total": 0}
            if e.was_correct:
                breakdown[c]["correct"] += 1
            breakdown[c]["total"] += 1
        result = {}
        for c, vals in breakdown.items():
            total = vals["total"]
            acc = vals["correct"] / total if total > 0 else 0.0
            result[c] = {"accuracy": acc, "count": total}
        return result

    def get_recent_misses(self, n: int = 10) -> List[CalibrationEntry]:
        if n <= 0:
            return []
        misses = [e for e in self.entries if not e.was_correct]
        return misses[-n:]

    # ── Cross-Component Failure Attribution (Agentic Harness) ──

    def attribute_failure(
        self,
        simulation_id: str,
        failed_component: str,
        root_cause_component: str,
        failure_chain: Optional[list[str]] = None,
        error_message: str = "",
        severity: str = "warning",
    ) -> str:
        """Record a failure attributed to a specific component chain.

        This builds the cross-component failure graph that enables
        root cause analysis across the entire agent pipeline.

        Args:
            simulation_id: Associated simulation/trace ID
            failed_component: Component that ultimately failed
            root_cause_component: Component determined to be the root cause
            failure_chain: Ordered list of components called before failure
            error_message: The error that occurred
            severity: info, warning, error, or critical

        Returns:
            Attribution entry ID
        """
        import uuid
        eid = f"attr_{uuid.uuid4().hex[:12]}"
        entry = AttributionEntry(
            id=eid,
            timestamp=time.time(),
            simulation_id=simulation_id,
            failed_component=failed_component,
            root_cause_component=root_cause_component,
            failure_chain=failure_chain or [root_cause_component, failed_component],
            error_message=error_message,
            severity=severity,
        )
        self.attributions.append(entry)
        logger.debug(f"Failure attributed: {failed_component} ← root: {root_cause_component} [{severity}]")
        self._save_attributions()
        return eid

    def resolve_attribution(self, attribution_id: str, resolution: str) -> bool:
        """Mark an attribution entry as resolved with a resolution note."""
        for a in self.attributions:
            if a.id == attribution_id:
                a.resolved = True
                a.resolution = resolution
                self._save_attributions()
                return True
        return False

    def get_attribution_chain(self, simulation_id: str) -> list[AttributionEntry]:
        """Get all attribution entries for a specific simulation/trace."""
        return [a for a in self.attributions if a.simulation_id == simulation_id]

    def get_root_causes(self, top_n: int = 10) -> list[dict]:
        """Find the most common root cause components across all failures.

        Returns top-N root cause components with failure counts and severity breakdown.
        """
        by_root: dict[str, dict] = {}
        for a in self.attributions:
            r = by_root.setdefault(a.root_cause_component, {"count": 0, "severity_info": 0,
                                                             "severity_warning": 0, "severity_error": 0,
                                                             "severity_critical": 0, "claimed": [],
                                                             "resolved": 0})
            r["count"] += 1
            sev_key = f"severity_{a.severity}"
            if sev_key in r:
                r[sev_key] += 1
            r["claimed"].append(a.failed_component)
            if a.resolved:
                r["resolved"] += 1

        sorted_roots = sorted(by_root.items(), key=lambda x: x[1]["count"], reverse=True)
        result = []
        for component, stats in sorted_roots[:top_n]:
            # Count most common downstream failed components
            downstream: dict[str, int] = {}
            for c in stats["claimed"]:
                downstream[c] = downstream.get(c, 0) + 1
            result.append({
                "component": component,
                "total_failures": stats["count"],
                "resolved": stats["resolved"],
                "unresolved": stats["count"] - stats["resolved"],
                "severity_info": stats["severity_info"],
                "severity_warning": stats["severity_warning"],
                "severity_error": stats["severity_error"],
                "severity_critical": stats["severity_critical"],
                "most_affected": sorted(downstream.items(), key=lambda x: x[1], reverse=True)[:3],
            })
        return result

    def get_component_health(self) -> dict:
        """Get health report for all components based on attribution data.

        Components with many unresolved failures are flagged as unhealthy.
        """
        by_component: dict[str, dict] = {}
        for a in self.attributions:
            for comp in [a.root_cause_component, a.failed_component]:
                c = by_component.setdefault(comp, {"as_root": 0, "as_failed": 0, "total": 0, "unresolved": 0})
                c["total"] += 1
                if not a.resolved:
                    c["unresolved"] += 1

        for a in self.attributions:
            by_component[a.root_cause_component]["as_root"] += 1
            by_component[a.failed_component]["as_failed"] += 1

        health = {}
        for comp, stats in by_component.items():
            unresolved_rate = stats["unresolved"] / stats["total"] if stats["total"] > 0 else 0
            if unresolved_rate > 0.5:
                status = "critical"
            elif unresolved_rate > 0.2:
                status = "degraded"
            elif stats["unresolved"] > 0:
                status = "warning"
            else:
                status = "healthy"
            health[comp] = {
                "status": status,
                "as_root_cause": stats["as_root"],
                "as_failed_component": stats["as_failed"],
                "total_incidents": stats["total"],
                "unresolved": stats["unresolved"],
                "unresolved_rate": round(unresolved_rate, 3),
            }
        return health

    def get_failure_hotspots(self) -> list[dict]:
        """Identify the most problematic failure chains (root→failed patterns)."""
        chains: dict[tuple, dict] = {}
        for a in self.attributions:
            chain = tuple(a.failure_chain)
            c = chains.setdefault(chain, {"count": 0, "unresolved": 0, "sample_error": ""})
            c["count"] += 1
            if not a.resolved:
                c["unresolved"] += 1
            if not c["sample_error"] and a.error_message:
                c["sample_error"] = a.error_message[:200]

        sorted_chains = sorted(chains.items(), key=lambda x: x[1]["count"], reverse=True)
        return [
            {"chain": list(chain), "count": stats["count"], "unresolved": stats["unresolved"],
             "sample_error": stats["sample_error"]}
            for chain, stats in sorted_chains[:10]
        ]

    # ── Persistence (attributions) ──

    def _save_attributions(self):
        try:
            with open(self._attribution_path, "w", encoding="utf-8") as f:
                json.dump([a.to_dict() for a in self.attributions], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save attributions: {e}")

    def _load_attributions(self):
        if os.path.exists(self._attribution_path):
            try:
                with open(self._attribution_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.attributions = [AttributionEntry(**e) for e in data]
            except Exception:
                self.attributions = []

    def get_summary(self) -> dict:
        total_entries = len(self.entries)
        overall_accuracy = self.get_accuracy(window=total_entries) if total_entries > 0 else 0.0
        trust_score = self.get_trust_score()
        category_breakdown = self.get_category_breakdown()
        recent_misses_count = len(self.get_recent_misses(n=9999))
        if trust_score > 0.8:
            recommendation = "trust_fully"
        elif trust_score > 0.5:
            recommendation = "trust_cautiously"
        elif trust_score < 0.3:
            recommendation = "distrust"
        else:
            recommendation = "neutral"

        # Attribution summary
        total_attributions = len(self.attributions)
        unresolved = sum(1 for a in self.attributions if not a.resolved)
        top_roots = self.get_root_causes(3)
        component_health = self.get_component_health()
        unhealthy = {k: v for k, v in component_health.items() if v["status"] != "healthy"}

        return {
            "total_entries": total_entries,
            "overall_accuracy": overall_accuracy,
            "trust_score": trust_score,
            "category_breakdown": category_breakdown,
            "recent_misses_count": recent_misses_count,
            "recommendation": recommendation,
            "attribution": {
                "total_incidents": total_attributions,
                "unresolved": unresolved,
                "resolution_rate": round((total_attributions - unresolved) / total_attributions, 3) if total_attributions > 0 else 1.0,
                "top_root_causes": top_roots,
                "unhealthy_components": unhealthy,
            },
        }


# ── Singleton ──

_tracker: Optional[CalibrationTracker] = None


def get_calibration_tracker() -> CalibrationTracker:
    """Return a global CalibrationTracker instance (singleton).

    Creates the instance on first access.
    """
    global _tracker
    if _tracker is None:
        _tracker = CalibrationTracker()
    return _tracker
