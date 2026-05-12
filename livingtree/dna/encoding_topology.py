"""Encoding Topology Analyzer — measure HOW, not just WHAT.

Based on: "Decoding Alignment without Encoding Alignment" (arXiv:2605.05907, 2026)

Core critique: Popular alignment metrics (RSA, CKA, cosine similarity) measure
WHAT a system does (decoding), but are BLIND to HOW it does it (encoding).

LivingTree application: Every existing metric (fitness score, success rate, latency,
relevance) is a DECODING metric. We add ENCODING topology measurement:
  - HOW is computation distributed across components?
  - HOW are decisions organized internally?
  - Is the encoding manifold continuous or clustered?
  - Are two systems with equal scores structurally different?

Encoding Topology captures:
  1. Function Distribution — how widely is computation spread?
  2. Component Coupling — how interdependent are components?
  3. Topology Type — continuous, clustered, hierarchical, modular
  4. Structural Invariance — does structure persist across sessions?
  5. Gromov-Wasserstein distance — principled comparison of encoding manifolds
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════
# Encoding Topology Types
# ═══════════════════════════════════════════════════════

class TopologyType(str, Enum):
    CONTINUOUS = "continuous"      # Smooth gradient — distributed computation
    CLUSTERED = "clustered"        # Localized groups — specialized modules
    HIERARCHICAL = "hierarchical"  # Tree structure — layered processing
    MODULAR = "modular"            # Independent components — low coupling
    CENTRALIZED = "centralized"    # Hub-and-spoke — one dominant component
    FRAGMENTED = "fragmented"      # Many tiny pieces — high entropy


@dataclass
class EncodingProfile:
    """HOW a component computes — the encoding topology.

    Complements existing metrics (WHAT) with structural understanding (HOW).
    """
    component_name: str
    # Function distribution: how is work spread?
    participation_count: int = 0         # How many times this component was involved
    contribution_share: float = 0.0       # Fraction of total computation
    specialization_index: float = 0.0     # 1.0 = highly specialized, 0.0 = generalist

    # Component coupling: how interdependent?
    dependency_count: int = 0             # How many other components depend on this
    coupled_components: list[str] = field(default_factory=list)
    coupling_strength: float = 0.0        # Average dependency strength

    # Topology classification
    topology_type: TopologyType = TopologyType.CONTINUOUS
    topology_confidence: float = 0.5

    # Structural invariance
    session_consistency: float = 0.0      # How stable is this profile across sessions?
    drift_rate: float = 0.0               # How fast is the profile changing?

    # Raw data for manifold comparison
    activation_trace: list[float] = field(default_factory=list)  # Activity over time


# ═══════════════════════════════════════════════════════
# Encoding Topology Analyzer
# ═══════════════════════════════════════════════════════

class EncodingTopologyAnalyzer:
    """Measure HOW components compute — not just WHAT they produce.

    The paper's key insight: two systems with identical output metrics
    can have fundamentally different internal organization.
    This analyzer captures that internal structure.
    """

    def __init__(self):
        self._profiles: dict[str, EncodingProfile] = defaultdict(
            lambda: EncodingProfile(component_name="")
        )
        self._history: dict[str, list[dict]] = defaultdict(list)

    def record_activation(self, component: str, activity: float,
                          dependencies: list[str] = None,
                          contribution: float = 0.0) -> None:
        """Record one activation event for a component.

        This builds the encoding profile over time.
        Each event adds to the trace that reveals the component's true topology.
        """
        profile = self._profiles[component]
        profile.component_name = component
        profile.participation_count += 1
        profile.contribution_share = (
            0.9 * profile.contribution_share + 0.1 * contribution
        )
        profile.activation_trace.append(activity)

        if dependencies:
            profile.coupled_components = list(
                set(profile.coupled_components + dependencies)
            )
            profile.dependency_count = len(profile.coupled_components)
            profile.coupling_strength = (
                0.9 * profile.coupling_strength + 0.1 * len(dependencies)
            )

        # Keep trace manageable
        if len(profile.activation_trace) > 100:
            profile.activation_trace = profile.activation_trace[-100:]

        # Re-classify topology
        self._classify_topology(profile)

    def analyze_session(self, session_id: str, component_activities: dict[str, float],
                        dependency_graph: dict[str, list[str]]) -> dict:
        """Analyze encoding topology for a full session.

        Returns both decoding metrics (existing) AND encoding topology (new).
        """
        total_activity = sum(component_activities.values()) or 1

        for component, activity in component_activities.items():
            deps = dependency_graph.get(component, [])
            contribution = activity / total_activity
            self.record_activation(component, activity, deps, contribution)

        # Compute global encoding metrics
        profiles = {
            comp: self._profiles[comp]
            for comp in component_activities
        }

        return {
            "session_id": session_id,
            # Decoding metrics (WHAT — existing)
            "decoding": {
                "total_activity": total_activity,
                "component_count": len(component_activities),
                "activity_distribution": {
                    comp: round(act / total_activity, 3)
                    for comp, act in component_activities.items()
                },
            },
            # Encoding topology (HOW — NEW)
            "encoding": {
                "topology_type": self._global_topology(profiles),
                "specialization_entropy": self._specialization_entropy(profiles),
                "coupling_density": self._coupling_density(profiles),
                "component_profiles": {
                    name: {
                        "topology": p.topology_type.value,
                        "specialization": round(p.specialization_index, 3),
                        "coupling_strength": round(p.coupling_strength, 3),
                        "contribution_share": round(p.contribution_share, 3),
                        "session_consistency": round(p.session_consistency, 3),
                    }
                    for name, p in profiles.items()
                },
            },
            # Paper's key insight: decoding ≠ encoding
            "alignment_gap": self._compute_alignment_gap(profiles),
        }

    def compare_sessions(self, session_a: str, session_b: str) -> dict:
        """Compare encoding topology between two sessions.

        The paper's key question: do two sessions that LOOK the same
        (same output quality) actually COMPUTE the same way?
        """
        # Simplified Gromov-Wasserstein-like comparison
        profiles_a = {
            k: v for k, v in self._profiles.items()
            if k in self._history.get(session_a, [])
        }
        profiles_b = {
            k: v for k, v in self._profiles.items()
            if k in self._history.get(session_b, [])
        }

        if not profiles_a or not profiles_b:
            return {"similarity": 0.0, "note": "insufficient data"}

        # Compare: topology type distribution
        types_a = defaultdict(int)
        types_b = defaultdict(int)
        for p in profiles_a.values():
            types_a[p.topology_type.value] += 1
        for p in profiles_b.values():
            types_b[p.topology_type.value] += 1

        # Cosine similarity of topology distributions
        all_types = set(list(types_a.keys()) + list(types_b.keys()))
        vec_a = [types_a.get(t, 0) for t in all_types]
        vec_b = [types_b.get(t, 0) for t in all_types]

        dot = sum(vec_a[i] * vec_b[i] for i in range(len(vec_a)))
        na = math.sqrt(sum(x*x for x in vec_a))
        nb = math.sqrt(sum(x*x for x in vec_b))
        topo_sim = dot / max(1e-9, na * nb)

        return {
            "topology_similarity": round(topo_sim, 3),
            "session_a_topology": dict(types_a),
            "session_b_topology": dict(types_b),
            "structurally_equivalent": topo_sim > 0.8,
            "warning": (
                "Sessions have different encoding topologies — "
                "similar outputs may come from different computation paths."
            ) if topo_sim < 0.5 else None,
        }

    def detect_tricksters(self) -> list[dict]:
        """Detect components that score well on DECODING but have SUSPICIOUS encoding.

        The paper's warning: small non-representative subpopulations can
        reproduce full population alignment metrics.

        Trickster detection: high success rate + low specialization + low coupling
        = likely taking shortcuts rather than doing real computation.
        """
        tricksters = []
        for name, profile in self._profiles.items():
            if profile.participation_count < 3:
                continue

            # High output quality (decoding) with suspicious structure (encoding)
            if (profile.contribution_share > 0.3 and      # High contribution
                profile.specialization_index < 0.2 and     # Not specialized
                profile.coupling_strength < 0.3 and        # Low coupling
                profile.participation_count < 20):          # Limited data
                tricksters.append({
                    "component": name,
                    "suspicion": "HIGH — high contribution but low specialization and coupling",
                    "likely_behavior": "Taking shortcuts or exploiting dataset bias",
                    "recommendation": "Investigate encoding topology more deeply",
                })

        return tricksters

    # ── Internal ──

    def _classify_topology(self, profile: EncodingProfile) -> None:
        """Classify a component's encoding topology from its trace."""
        if profile.participation_count < 5:
            return

        specialization = profile.specialization_index
        coupling = profile.coupling_strength
        contribution = profile.contribution_share

        if contribution > 0.5:
            profile.topology_type = TopologyType.CENTRALIZED
            profile.topology_confidence = 0.8
        elif specialization > 0.7:
            profile.topology_type = TopologyType.CLUSTERED
            profile.topology_confidence = 0.7
        elif coupling > 0.6:
            profile.topology_type = TopologyType.HIERARCHICAL
            profile.topology_confidence = 0.6
        elif coupling < 0.2 and specialization < 0.3:
            profile.topology_type = TopologyType.FRAGMENTED
            profile.topology_confidence = 0.5
        elif coupling < 0.4:
            profile.topology_type = TopologyType.MODULAR
            profile.topology_confidence = 0.6
        else:
            profile.topology_type = TopologyType.CONTINUOUS
            profile.topology_confidence = 0.5

        # Compute specialization index from activation variance
        if profile.activation_trace:
            mean = sum(profile.activation_trace) / len(profile.activation_trace)
            variance = sum((x - mean)**2 for x in profile.activation_trace) / len(profile.activation_trace)
            profile.specialization_index = min(1.0, variance / max(0.01, mean))

        # Update consistency
        profile.session_consistency = profile.participation_count / (profile.participation_count + 5)

    def _global_topology(self, profiles: dict[str, EncodingProfile]) -> str:
        """Determine overall topology type for a set of components."""
        type_counts = defaultdict(int)
        for p in profiles.values():
            if p.participation_count > 0:
                type_counts[p.topology_type.value] += 1
        if not type_counts:
            return "unknown"
        return max(type_counts, key=type_counts.get)

    def _specialization_entropy(self, profiles: dict[str, EncodingProfile]) -> float:
        """Shannon entropy of specialization distribution — higher = more diverse."""
        specs = [p.specialization_index for p in profiles.values() if p.participation_count > 0]
        if not specs:
            return 0.0
        bins = [0] * 5
        for s in specs:
            bins[min(4, int(s * 5))] += 1
        total = sum(bins)
        entropy = -sum((b/total) * math.log2(max(1e-9, b/total)) for b in bins if b > 0)
        return round(entropy, 3)

    def _coupling_density(self, profiles: dict[str, EncodingProfile]) -> float:
        """How densely coupled are the components?"""
        pairs = 0
        total = 0
        for p in profiles.values():
            total += 1
            pairs += len(p.coupled_components)
        return pairs / max(1, total * (total - 1))

    def _compute_alignment_gap(self, profiles: dict[str, EncodingProfile]) -> dict:
        """Measure the gap between decoding and encoding metrics.

        This is the paper's core contribution: decoding ≠ encoding.
        A large gap means the component looks good on output metrics
        but its internal structure tells a different story.
        """
        gaps = {}
        for name, p in profiles.items():
            if p.participation_count < 3:
                continue
            # Decoding score = contribution share (higher = better output)
            # Encoding score = specialization × coupling (higher = real computation)
            decoding = p.contribution_share
            encoding = p.specialization_index * p.coupling_strength
            gap = abs(decoding - encoding)
            gaps[name] = round(gap, 3)

        return {
            "per_component": gaps,
            "avg_gap": round(sum(gaps.values()) / max(1, len(gaps)), 3),
            "interpretation": (
                "LARGE GAP: components produce good outputs but encoding "
                "suggests shallow computation — potential tricksters."
            ) if sum(gaps.values()) / max(1, len(gaps)) > 0.3 else (
                "SMALL GAP: decoding and encoding are consistent — "
                "components compute what they appear to compute."
            ),
        }


# ═══════════════════════════════════════════════════════
# Dual Metric Dashboard — WHAT + HOW for every component
# ═══════════════════════════════════════════════════════

class DualMetricDashboard:
    """Every component now reports BOTH decoding AND encoding metrics.

    Decoding (WHAT): traditional metrics — success rate, latency, relevance.
    Encoding (HOW): topology type, specialization, coupling, consistency.

    The paper's prescription: the appropriate unit of comparison is a PAIR
    of measurements — what a system does AND how it is organized to do it.
    """

    def __init__(self):
        self.topology = EncodingTopologyAnalyzer()

    def full_report(self, component: str) -> dict:
        """Get both decoding and encoding metrics for a component."""
        profile = self.topology._profiles.get(component,
            EncodingProfile(component_name=component))

        return {
            "component": component,
            # Decoding (WHAT)
            "decoding": {
                "activity": len(profile.activation_trace),
                "contribution": round(profile.contribution_share, 3),
                "recent_activity": (
                    round(sum(profile.activation_trace[-10:]) / max(1, len(profile.activation_trace[-10:])), 3)
                    if profile.activation_trace else 0
                ),
            },
            # Encoding (HOW)
            "encoding": {
                "topology_type": profile.topology_type.value,
                "topology_confidence": round(profile.topology_confidence, 2),
                "specialization": round(profile.specialization_index, 3),
                "coupling_strength": round(profile.coupling_strength, 3),
                "dependency_count": profile.dependency_count,
                "consistency": round(profile.session_consistency, 3),
                "drift_rate": round(profile.drift_rate, 3),
            },
            # Gap analysis
            "alignment_gap": round(
                abs(profile.contribution_share - profile.specialization_index * profile.coupling_strength), 3
            ),
        }

    def compare_two_components(self, comp_a: str, comp_b: str) -> dict:
        """Compare HOW two components compute — not just their output scores.

        The paper's key experiment: two components with equal output scores
        can have completely different encoding topologies.
        """
        profile_a = self.topology._profiles.get(comp_a)
        profile_b = self.topology._profiles.get(comp_b)

        if not profile_a or not profile_b:
            return {"error": "insufficient data"}

        # Decoding comparison
        decoding_similar = (
            abs(profile_a.contribution_share - profile_b.contribution_share) < 0.1
        )

        # Encoding comparison
        encoding_similar = profile_a.topology_type == profile_b.topology_type

        return {
            "decoding_output_similar": decoding_similar,
            "encoding_topology_similar": encoding_similar,
            "paper_insight": (
                "⚠️ CRITICAL: Same output, DIFFERENT computation. "
                "Decoding metrics are blind to this difference."
            ) if decoding_similar and not encoding_similar else (
                "✅ Consistent: both output and computation are similar."
            ) if decoding_similar and encoding_similar else (
                "Different outputs with different computation — expected."
            ),
            "component_a": {
                "topology": profile_a.topology_type.value,
                "output_share": round(profile_a.contribution_share, 3),
            },
            "component_b": {
                "topology": profile_b.topology_type.value,
                "output_share": round(profile_b.contribution_share, 3),
            },
        }


# ── Singleton ──

_analyzer: Optional[EncodingTopologyAnalyzer] = None
_dashboard: Optional[DualMetricDashboard] = None


def get_encoding_analyzer() -> EncodingTopologyAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = EncodingTopologyAnalyzer()
    return _analyzer


def get_dual_metric_dashboard() -> DualMetricDashboard:
    global _dashboard
    if _dashboard is None:
        _dashboard = DualMetricDashboard()
    return _dashboard
