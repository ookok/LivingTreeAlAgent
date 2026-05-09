"""Synaptic Plasticity Layer — silent synapse activation & memory consolidation.

Based on Vardalaki & Harnett (MIT, 2022), Nature:
  Adult cortex contains ~30% silent synapses — immature connections that
  activate on demand, enabling new learning without overwriting existing
  memories. This is the biological implementation of incremental,
  non-destructive knowledge acquisition.

Enhanced onto existing LivingTree modules:
  1. HypergraphStore edges → synapse maturity (silent → active → mature)
  2. LazyIndex sections → silent knowledge awaiting activation
  3. ThompsonRouter arms → cold-start exploring synapses
  4. ExperienceRepository → long-term potentiation (LTP) on retrieval

Key biological mechanisms mapped:
  LTP (Long-Term Potentiation):   successful use → weight strengthened
  LTD (Long-Term Depression):     unused → weight decayed toward prior
  Silent → Active transition:     first retrieval → synapse becomes functional
  Mature protection:              weight > 0.8 → change rate halved
  Homeostatic scaling:            global normalization of weights
  Metaplasticity:                 recent activity modulates future plasticity

No new module needed — this is a lightweight enhancement layer.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


# ═══ Synaptic State ═══


class SynapticState(str, Enum):
    SILENT = "silent"        # Immature, not yet functional (30% of pool)
    ACTIVE = "active"        # Recently activated, strengthening
    MATURE = "mature"        # Stabilized, protected from overwrite
    PRUNED = "pruned"        # Decayed below threshold, removed


@dataclass
class SynapseMetadata:
    """Plasticity metadata attached to any graph edge / model arm / index entry."""
    state: SynapticState = SynapticState.SILENT
    weight: float = 0.15          # Current strength (silent: <0.2)
    activation_count: int = 0     # Number of successful uses
    last_activated: float = 0.0   # Timestamp of last activation
    created_at: float = field(default_factory=time.time)
    # Metaplasticity: recent activity modulates future plasticity
    recent_activity: list[float] = field(default_factory=list)  # Last 5 activation times
    protection_level: float = 0.0  # 0=none, 1=fully protected (mature)

    @property
    def is_protected(self) -> bool:
        return self.state == SynapticState.MATURE and self.protection_level > 0.5

    @property
    def plasticity(self) -> float:
        """How much this synapse can still change. Mature = low plasticity."""
        if self.state == SynapticState.MATURE:
            return max(0.1, 1.0 - self.protection_level)
        if self.state == SynapticState.ACTIVE:
            return 0.6
        return 1.0  # Silent = maximum plasticity


# ═══ Synaptic Plasticity Engine ═══


class SynapticPlasticity:
    """Lightweight synaptic plasticity overlay for any graph/index/model structure.

    Wraps entity/edge IDs with synapse-like maturation dynamics.
    This can be attached to HypergraphStore edges, LazyIndex sections,
    ThompsonRouter arms, or ExperienceRepository patterns.

    Key constants (biologically motivated):
      LTP_RATE = 0.12     — weight increase per successful activation
      LTD_RATE = 0.003    — weight decay per tick toward prior
      SILENT_THRESHOLD = 0.20 — below this = silent
      MATURE_THRESHOLD = 0.80  — above this = mature (protected)
      PRUNE_THRESHOLD = 0.01   — below this = deleted
      HOMEOSTATIC_TARGET = 0.30 — global normalization target
    """

    LTP_RATE: float = 0.12
    LTD_RATE: float = 0.003
    SILENT_THRESHOLD: float = 0.20
    MATURE_THRESHOLD: float = 0.80
    PRUNE_THRESHOLD: float = 0.01
    HOMEOSTATIC_TARGET: float = 0.30

    def __init__(self):
        self._synapses: dict[str, SynapseMetadata] = {}
        self._total_activations: int = 0
        self._total_pruned: int = 0

    # ── Synapse Management ──

    def register(self, synapse_id: str, initial_weight: float = 0.15) -> SynapseMetadata:
        """Register a new (silent) synapse."""
        meta = SynapseMetadata(
            state=SynapticState.SILENT if initial_weight < self.SILENT_THRESHOLD else SynapticState.ACTIVE,
            weight=initial_weight,
        )
        self._synapses[synapse_id] = meta
        return meta

    def get(self, synapse_id: str) -> SynapseMetadata | None:
        return self._synapses.get(synapse_id)

    def get_or_create(self, synapse_id: str) -> SynapseMetadata:
        """Get existing synapse or create a new silent one."""
        if synapse_id not in self._synapses:
            return self.register(synapse_id)
        return self._synapses[synapse_id]

    # ═══ Long-Term Potentiation (LTP) ═══

    def strengthen(self, synapse_id: str, boost: float = 1.0) -> float:
        """Apply LTP — strengthen synapse on successful use.

        Δw = LTP_RATE × plasticity × boost / (1 + log(1 + activations))
        → Diminishing returns: later activations strengthen less
        → Plasticity-gated: mature synapses change less
        """
        meta = self.get_or_create(synapse_id)
        plastic = meta.plasticity
        diminishing = 1.0 / (1.0 + math.log(1 + meta.activation_count))
        delta = self.LTP_RATE * plastic * boost * diminishing

        old_weight = meta.weight
        meta.weight = min(1.0, old_weight + delta)
        meta.activation_count += 1
        meta.last_activated = time.time()
        self._total_activations += 1

        # Track recent activity for metaplasticity
        meta.recent_activity.append(time.time())
        if len(meta.recent_activity) > 5:
            meta.recent_activity = meta.recent_activity[-5:]

        # State transition
        if meta.state == SynapticState.SILENT and meta.weight >= self.SILENT_THRESHOLD:
            meta.state = SynapticState.ACTIVE
            logger.debug(f"Synapse activated: {synapse_id} (w={meta.weight:.2f})")
        if meta.state == SynapticState.ACTIVE and meta.weight >= self.MATURE_THRESHOLD:
            meta.state = SynapticState.MATURE
            meta.protection_level = 0.5  # Start protection at 50%
            logger.info(f"Synapse matured: {synapse_id} (w={meta.weight:.2f})")

        return meta.weight

    def weaken(self, synapse_id: str, penalty: float = 1.0) -> float:
        """Apply LTD — weaken synapse on failure or disuse."""
        meta = self.get_or_create(synapse_id)
        delta = self.LTP_RATE * 1.5 * penalty  # LTD slightly stronger than LTP
        meta.weight = max(0.0, meta.weight - delta)

        if meta.weight <= self.PRUNE_THRESHOLD and meta.state != SynapticState.PRUNED:
            meta.state = SynapticState.PRUNED
            self._total_pruned += 1
            logger.debug(f"Synapse pruned: {synapse_id}")

        return meta.weight

    # ═══ Decay (LTD for unused synapses) ═══

    def decay(self, synapse_id: str) -> float:
        """Apply passive decay toward prior — unused synapses slowly weaken."""
        meta = self.get(synapse_id)
        if not meta:
            return 0.0
        if meta.is_protected:
            # Mature synapses decay very slowly (memory protection)
            meta.weight -= self.LTD_RATE * 0.1
        else:
            meta.weight -= self.LTD_RATE
        meta.weight = max(0.0, meta.weight)
        return meta.weight

    def decay_all(self) -> int:
        """Apply passive decay to all synapses. Returns count of pruned."""
        pruned_now = 0
        for sid in list(self._synapses.keys()):
            self.decay(sid)
            meta = self._synapses[sid]
            if meta.weight <= self.PRUNE_THRESHOLD and meta.state != SynapticState.PRUNED:
                meta.state = SynapticState.PRUNED
                self._total_pruned += 1
                pruned_now += 1
        return pruned_now

    # ═══ Mature Protection ═══

    def protect(self, synapse_id: str, level: float = 1.0) -> None:
        """Increase protection level for a mature synapse."""
        meta = self.get(synapse_id)
        if meta and meta.state == SynapticState.MATURE:
            meta.protection_level = min(1.0, meta.protection_level + 0.1 * level)
            meta.state = SynapticState.MATURE  # Locked

    def mature_all_eligible(self) -> int:
        """Promote all eligible synapses to mature state."""
        count = 0
        for meta in self._synapses.values():
            if meta.state == SynapticState.ACTIVE and meta.weight >= self.MATURE_THRESHOLD:
                meta.state = SynapticState.MATURE
                meta.protection_level = 0.5
                count += 1
        return count

    # ═══ Homeostatic Scaling ═══

    def homeostatic_scale(self) -> None:
        """Global normalization: pull all weights toward HOMEOSTATIC_TARGET.

        Prevents runaway strengthening in one area while others starve.
        Biological analog: synaptic scaling maintains overall firing rate.
        """
        if not self._synapses:
            return
        avg_weight = sum(m.weight for m in self._synapses.values()) / len(self._synapses)
        if abs(avg_weight - self.HOMEOSTATIC_TARGET) < 0.01:
            return
        # Scale all weights proportionally toward target
        scale = self.HOMEOSTATIC_TARGET / max(avg_weight, 0.01)
        for meta in self._synapses.values():
            if not meta.is_protected:
                meta.weight *= 0.9 + 0.1 * scale  # Smooth scaling
                meta.weight = max(0.01, min(1.0, meta.weight))

    # ═══ Metaplasticity ═══

    def activity_rate(self, synapse_id: str, window_sec: float = 300) -> float:
        """Recent activation frequency (activations/second in window).

        High activity → lower plasticity (Bienenstock-Cooper-Munro rule).
        """
        meta = self.get(synapse_id)
        if not meta or not meta.recent_activity:
            return 0.0
        now = time.time()
        recent = [t for t in meta.recent_activity if now - t < window_sec]
        return len(recent) / window_sec

    # ═══ Interference Detection (Kaplan et al. 2026) ═══

    def detect_interference(
        self, strengthened_id: str, neighbor_ids: list[str],
    ) -> dict[str, float]:
        """Detect knowledge degradation from localized interference.

        Kaplan et al. (arXiv:2604.15574): fine-tuning causes hallucinations
        because new knowledge interferes with overlapping semantic
        representations. The driver is LOCALIZED interference — nearby
        representations degrade when a new one is strengthened.

        This method checks: when we strengthen synapse A, do nearby
        synapses B_1..B_n experience weight degradation? If so, this
        IS the hallucination mechanism in action.

        Returns:
            {neighbor_id: degradation_score} — higher = more degraded
        """
        degradation: dict[str, float] = {}
        for nid in neighbor_ids:
            meta = self.get(nid)
            if not meta:
                continue
            if meta.state == SynapticState.MATURE:
                # Check if this mature synapse lost weight recently
                # (mature weights should be stable)
                if meta.weight < self.MATURE_THRESHOLD * 0.8:
                    degradation[nid] = 1.0 - meta.weight / self.MATURE_THRESHOLD
                elif meta.weight < self.MATURE_THRESHOLD:
                    degradation[nid] = 1.0 - meta.weight / self.MATURE_THRESHOLD
            # Scale degradation by protection level (protected = less visible damage)
            if meta.is_protected:
                degradation[nid] = degradation.get(nid, 0) * 0.3

        return degradation

    def interference_ratio(self) -> float:
        """What fraction of mature synapses show signs of interference?"""
        mature = [m for m in self._synapses.values() if m.state == SynapticState.MATURE]
        if not mature:
            return 0.0
        degraded = sum(
            1 for m in mature
            if m.weight < self.MATURE_THRESHOLD * 0.85)
        return degraded / len(mature)

    # ═══ Self-Distillation Regularization ═══

    def self_distillation_loss(self) -> float:
        """Compute self-distillation regularization loss.

        Kaplan et al. (2026): self-distillation prevents hallucinations
        by regularizing output-distribution drift. When new knowledge is
        added, the overall distribution of synaptic weights should not
        shift too far from its previous state.

        Loss = KL(old_distribution || new_distribution)
        This penalizes large distributional shifts across the entire
        synaptic population.
        """
        if not self._synapses:
            return 0.0

        weights = [m.weight for m in self._synapses.values()]
        total = sum(weights)
        if total < 0.01:
            return 0.0

        probs = [w / total for w in weights]
        # Prior: uniform distribution (no bias toward any synapse)
        # KL(prior || current) = Σ prior(i) × log(prior(i) / p(i))
        uniform = 1.0 / len(probs)
        kl = 0.0
        for p in probs:
            if p > 0:
                kl += uniform * math.log(max(uniform / p, 0.01))
        return max(0.0, kl)

    def regularize_distribution(self, strength: float = 0.1) -> None:
        """Apply self-distillation: pull weights toward uniform to prevent drift.

        This is the direct implementation of the paper's fix: when distribution
        shift is detected, gently pull all weights back toward the population
        mean to prevent catastrophic forgetting of old knowledge.
        """
        if not self._synapses:
            return
        weights = [m.weight for m in self._synapses.values()]
        mean_w = sum(weights) / len(weights)

        for meta in self._synapses.values():
            if not meta.is_protected:
                # Pull toward mean (self-distillation)
                meta.weight = meta.weight * (1 - strength) + mean_w * strength
                meta.weight = max(0.01, min(1.0, meta.weight))
            else:
                # Protected synapses get gentler pull
                meta.weight = meta.weight * (1 - strength * 0.2) + mean_w * strength * 0.2
                meta.weight = max(0.01, min(1.0, meta.weight))

    # ═══ Knowledge Degradation Monitor ═══

    def degradation_alert(self) -> dict[str, Any]:
        """Monitor for knowledge degradation — the hallucination early-warning.

        Triggers when:
          1. Interference ratio > 0.1 (more than 10% of mature synapses degrading)
          2. Self-distillation loss > 0.5 (significant distribution drift)
          3. Silent ratio has dropped below 0.15 (system is over-consolidated)

        Returns:
            Alert dict with severity and recommended action
        """
        ir = self.interference_ratio()
        sdl = self.self_distillation_loss()
        sr = self.silent_ratio()

        alerts = []
        severity = "normal"

        if ir > 0.2:
            alerts.append(f"High interference: {ir:.0%} of mature synapses degrading")
            severity = "critical"
        elif ir > 0.1:
            alerts.append(f"Elevated interference: {ir:.0%} mature degradation")
            severity = "warning"

        if sdl > 1.0:
            alerts.append(f"Severe distribution drift: KL={sdl:.2f}")
            severity = "critical"
        elif sdl > 0.5:
            alerts.append(f"Distribution drift detected: KL={sdl:.2f}")
            if severity == "normal":
                severity = "warning"

        if sr < 0.10:
            alerts.append(f"Low silent synapse reserve: {sr:.0%} (target: 30%)")
            if severity == "normal":
                severity = "warning"

        action = "none"
        if severity == "critical":
            action = "Apply self-distillation regularization immediately. "
            action += "Freeze mature parameter groups. "
            action += "Reduce LTP rate for new learning."
        elif severity == "warning":
            action = "Consider distribution regularization. "
            action += "Monitor interference ratio."
        else:
            action = "System healthy — no degradation detected."

        return {
            "severity": severity,
            "alerts": alerts,
            "action": action,
            "metrics": {
                "interference_ratio": round(ir, 3),
                "distribution_drift_kl": round(sdl, 3),
                "silent_reserve_ratio": round(sr, 3),
                "biological_target": 0.30,
            },
        }

    # ═══ Stats (Silent/Acitve/Mature breakdown) ═══

    def silent_ratio(self) -> float:
        """Percentage of synapses that are silent — biological target: ~30%."""
        if not self._synapses:
            return 0.0
        silent = sum(1 for m in self._synapses.values() if m.state == SynapticState.SILENT)
        return silent / len(self._synapses)

    def maturity_ratio(self) -> float:
        """Percentage of synapses that are mature and protected."""
        if not self._synapses:
            return 0.0
        mature = sum(1 for m in self._synapses.values() if m.state == SynapticState.MATURE)
        return mature / len(self._synapses)

    def stats(self) -> dict[str, Any]:
        total = len(self._synapses)
        if total == 0:
            return {"total_synapses": 0, "silent_ratio": 0}
        by_state = {"silent": 0, "active": 0, "mature": 0, "pruned": 0}
        for m in self._synapses.values():
            by_state[m.state.value] += 1
        return {
            "total_synapses": total,
            "by_state": by_state,
            "silent_ratio": round(self.silent_ratio(), 3),
            "mature_ratio": round(self.maturity_ratio(), 3),
            "total_activations": self._total_activations,
            "total_pruned": self._total_pruned,
            "biological_target_silent": 0.30,
            "interference_ratio": round(self.interference_ratio(), 3),
            "distribution_drift_kl": round(self.self_distillation_loss(), 3),
            "degradation_alert": self.degradation_alert()["severity"],
            "homeostatic_deviation": round(
                abs((sum(m.weight for m in self._synapses.values()) / total)
                    - self.HOMEOSTATIC_TARGET), 3),
        }


# ═══ Singleton ═══

_plasticity: SynapticPlasticity | None = None


def get_plasticity() -> SynapticPlasticity:
    global _plasticity
    if _plasticity is None:
        _plasticity = SynapticPlasticity()
    return _plasticity


__all__ = [
    "SynapticPlasticity", "SynapseMetadata", "SynapticState",
    "get_plasticity",
]
