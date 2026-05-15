"""Hormone Signaling Network — Endocrine system for the 12-organ digital life form.

DISPLAY LAYER: hormonal state is for monitoring/logging only. It does NOT influence
TreeLLM routing, election scoring, or provider selection. See joint_evolution.py for
the P→C→B JointHealth model that actually controls routing behavior.

Biological grounding:
  CORTISOL  — Hypothalamic-Pituitary-Adrenal (HPA) axis: stress mobilizes resources,
              chronic elevation suppresses non-essential functions (Sapolsky, 2004)
  DOPAMINE  — Mesolimbic reward pathway: prediction error drives reinforcement
              learning (Schultz et al., 1997, Nature)
  MELATONIN — Pineal gland: circadian entrainment, sleep induction, antioxidant
              (Reiter, 1991, Endocrine Reviews)
  ADRENALINE— Sympathetic-adrenal-medullary (SAM) axis: fight-or-flight, rapid
              whole-body mobilization (Cannon, 1915)
  SEROTONIN — Raphe nuclei: mood homeostasis, satisfaction, impulse regulation
              (Berger et al., 2009, Annu Rev Med)
  ACETYLCHOLINE — Basal forebrain → cortex: attentional focus, sensory gating,
              cholinergic anti-inflammatory pathway (Picciotto et al., 2012)
  OXYTOCIN  — Hypothalamic paraventricular nucleus: social bonding, trust,
              cooperative behavior (Carter, 1998, Psychoneuroendocrinology)

Dual-process integration:
  System 1 (fast/emotional): hormone levels modulate real-time organ priorities.
  System 2 (slow/deliberative): synaptic plasticity is gated by DOPAMINE/CORTISOL ratios.

Integration with:
  - CircadianClock (organism_v2.py): MELATONIN auto-release during night hours (22-06)
  - SynapticPlasticity (core/synaptic_plasticity.py): DOPAMINE-strengthened LTP,
    CORTISOL-gated LTD on successful/failed task completion
"""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════
# Hormone Types (7 primary signals)
# ═══════════════════════════════════════════════════════


class HormoneType(str, Enum):
    CORTISOL = "cortisol"              # Stress — HPA axis, throttles non-critical
    DOPAMINE = "dopamine"              # Reward/learning — prediction error, LTP gate
    MELATONIN = "melatonin"            # Sleep/rest — pineal, reduces activity
    ADRENALINE = "adrenaline"          # Emergency — SAM axis, full alert
    SEROTONIN = "serotonin"            # Wellbeing/satisfaction — raphe nuclei
    ACETYLCHOLINE = "acetylcholine"    # Attention/focus — basal forebrain → cortex
    OXYTOCIN = "oxytocin"              # Trust/bonding — paraventricular nucleus

    @property
    def baseline(self) -> float:
        """Resting baseline level (homeostatic set-point)."""
        return {
            HormoneType.CORTISOL: 0.1,
            HormoneType.DOPAMINE: 0.15,
            HormoneType.MELATONIN: 0.05,
            HormoneType.ADRENALINE: 0.02,
            HormoneType.SEROTONIN: 0.3,
            HormoneType.ACETYLCHOLINE: 0.25,
            HormoneType.OXYTOCIN: 0.15,
        }[self]

    @property
    def half_life_seconds(self) -> float:
        """Biological half-life (seconds). Shorter = faster decay."""
        return {
            HormoneType.CORTISOL: 120,           # ~2 min
            HormoneType.DOPAMINE: 90,            # ~1.5 min
            HormoneType.MELATONIN: 180,          # ~3 min
            HormoneType.ADRENALINE: 60,          # ~1 min
            HormoneType.SEROTONIN: 300,          # ~5 min
            HormoneType.ACETYLCHOLINE: 30,       # ~30 sec
            HormoneType.OXYTOCIN: 240,           # ~4 min
        }[self]


# ═══════════════════════════════════════════════════════
# Signal Data Structures
# ═══════════════════════════════════════════════════════


@dataclass
class HormoneSignal:
    """A single hormone pulse released into the network."""
    hormone_type: HormoneType
    level: float                    # 0-1 current concentration (after decay)
    peak_level: float               # Original peak before decay
    source_organ: str
    target_organs: list[str] = field(default_factory=list)
    decay_rate: float = 0.0          # Calculated from half-life: λ = ln(2) / t½
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if self.decay_rate <= 0:
            self.decay_rate = math.log(2) / self.hormone_type.half_life_seconds
        self.peak_level = self.level

    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp

    def apply_decay(self) -> float:
        """Apply exponential decay: N(t) = N0 × e^(-λt)"""
        elapsed = self.age_seconds
        self.level = self.peak_level * math.exp(-self.decay_rate * elapsed)
        return self.level

    @property
    def is_active(self) -> bool:
        """Signal is above noise floor (>1% of peak)."""
        return self.level > 0.01 * self.peak_level


@dataclass
class OrganReceptor:
    """A hormone receptor expressed on a specific organ — determines sensitivity."""
    organ_name: str
    sensitivity: dict[str, float] = field(default_factory=dict)  # hormone_type → 0-1
    current_state: float = 0.5      # Aggregate activation level (0-1)
    last_activated: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.sensitivity:
            self.sensitivity = {}

    def sensitivity_to(self, hormone: HormoneType) -> float:
        return self.sensitivity.get(hormone.value, 0.0)


# ═══════════════════════════════════════════════════════
# Hormone Network — Central Endocrine System
# ═══════════════════════════════════════════════════════


class HormoneNetwork:
    """The endocrine signaling network coordinating all 12 organs.

    Maintains circulating hormone levels with exponential decay.
    Each organ expresses receptors that determine its sensitivity to each hormone.
    The network auto-triggers hormone release based on observed system state.

    Biological fidelity:
      - Hormone levels decay exponentially per half-life (pharmacokinetic model)
      - Organ activation = Σ (hormone_level × receptor_sensitivity) / Σ sensitivities
      - Homeostatic pull toward baselines prevents runaway states
      - Cross-regulation: CORTISOL suppresses SEROTONIN, DOPAMINE opposes MELATONIN
    """

    def __init__(self):
        self._hormones: dict[HormoneType, HormoneSignal] = {}
        self._organs: dict[str, OrganReceptor] = {}
        self._task: Optional[asyncio.Task] = None
        self._error_count: int = 0
        self._success_count: int = 0
        self._critical_failure: bool = False
        self._total_ticks: int = 0
        self._last_tick: float = time.time()
        self._born_at: float = time.time()

        for ht in HormoneType:
            self._hormones[ht] = HormoneSignal(
                hormone_type=ht,
                level=ht.baseline,
                peak_level=ht.baseline,
                source_organ="homeostatic",
            )

    # ═══ Secretion ═══

    def secrete(
        self,
        hormone_type: HormoneType,
        amount: float,
        source_organ: str = "system",
        target_organs: Optional[list[str]] = None,
    ) -> HormoneSignal:
        """Release a hormone pulse into the network.

        New secretion adds to existing level (cumulative, bounded at 1.0).
        Returns the updated signal.

        Args:
            hormone_type: Which hormone to release
            amount: 0-1 intensity of release
            source_organ: Which organ triggered the release
            target_organs: Optional list of target organs (default: all registered)
        """
        existing = self._hormones.get(hormone_type)
        if existing:
            existing.apply_decay()

        new_level = min(1.0, (existing.level if existing else 0.0) + amount)
        signal = HormoneSignal(
            hormone_type=hormone_type,
            level=new_level,
            peak_level=new_level,
            source_organ=source_organ,
            target_organs=target_organs or list(self._organs.keys()),
        )
        self._hormones[hormone_type] = signal

        logger.debug(
            f"Endocrine: {hormone_type.value.upper()} released "
            f"(+{amount:.2f}) from {source_organ} → level={new_level:.3f}"
        )
        return signal

    # ═══ Query ═══

    def get_level(self, hormone_type: HormoneType) -> float:
        """Current circulating level of a hormone, with decay applied."""
        signal = self._hormones.get(hormone_type)
        if not signal:
            return 0.0
        return signal.apply_decay()

    # ═══ Organ Registry ═══

    def register_organ(
        self,
        organ_name: str,
        sensitivities: dict[str, float] | None = None,
    ) -> OrganReceptor:
        """Register an organ with its hormone sensitivities.

        Args:
            organ_name: Unique organ identifier (e.g. "intent", "execution")
            sensitivities: {hormone_type_name: sensitivity 0-1} dict
        """
        if sensitivities is None:
            sensitivities = {}
        receptor = OrganReceptor(
            organ_name=organ_name,
            sensitivity={k: float(v) for k, v in sensitivities.items()},
        )
        self._organs[organ_name] = receptor
        logger.debug(f"Organ registered: {organ_name} with {len(sensitivities)} receptors")
        return receptor

    # ═══ Organ State Computation ═══

    def compute_organ_state(self, organ_name: str) -> float:
        """Aggregate all hormone effects on a given organ.

        Organ state = Σ (level_i × sensitivity_i) / max(1, Σ sensitivity_i)
        Weighted by receptor expression, normalized by total sensitivity.
        """
        receptor = self._organs.get(organ_name)
        if not receptor:
            return 0.5

        weighted_sum = 0.0
        sensitivity_sum = 0.0

        for ht in HormoneType:
            sens = receptor.sensitivity_to(ht)
            if sens > 0:
                level = self.get_level(ht)
                weighted_sum += level * sens
                sensitivity_sum += sens

        if sensitivity_sum < 0.001:
            return 0.5

        state = weighted_sum / sensitivity_sum
        receptor.current_state = state
        receptor.last_activated = time.time()
        return state

    def get_organ_priority(self, organ_name: str) -> float:
        """Dynamic priority based on current hormone state.

        High CORTISOL → non-critical organs deprioritized
        High ADRENALINE → all organs elevated (emergency mobilizaton)
        High MELATONIN → all organs suppressed (sleep)
        High DOPAMINE → learning/prediction organs boosted
        """
        state = self.compute_organ_state(organ_name)
        cortisol = self.get_level(HormoneType.CORTISOL)
        adrenaline = self.get_level(HormoneType.ADRENALINE)
        melatonin = self.get_level(HormoneType.MELATONIN)

        priority = state

        if melatonin > 0.3:
            priority *= max(0.2, 1.0 - melatonin)
        if adrenaline > 0.3:
            priority = min(1.0, priority + adrenaline * 0.5)
        if cortisol > 0.3:
            from .organ_dashboard import OrganType
            is_critical = organ_name in {
                OrganType.EXECUTION.value,
                OrganType.REFLECTION.value,
                OrganType.PROVIDER.value,
            }
            if not is_critical:
                priority *= max(0.3, 1.0 - cortisol * 0.7)

        return max(0.05, min(1.0, priority))

    # ═══ Auto-Trigger System ═══

    def report_error(self) -> None:
        """Notify network of an error — may trigger CORTISOL release."""
        self._error_count += 1
        error_rate = self._error_count / max(1, self._error_count + self._success_count)

        if error_rate > 0.5:
            self.secrete(HormoneType.CORTISOL, 0.3, "system:error_monitor")
        elif error_rate > 0.3:
            self.secrete(HormoneType.CORTISOL, 0.15, "system:error_monitor")
        if error_rate > 0.7:
            self.secrete(HormoneType.ADRENALINE, 0.2, "system:error_monitor")

    def report_success(self) -> None:
        """Notify network of a successful task — may trigger DOPAMINE release."""
        self._success_count += 1
        self.secrete(HormoneType.DOPAMINE, 0.25, "system:reward_monitor")
        self.secrete(HormoneType.SEROTONIN, 0.1, "system:reward_monitor")

    def report_critical_failure(self) -> None:
        """Notify network of a critical failure — triggers ADRENALINE surge."""
        self._critical_failure = True
        self.secrete(HormoneType.ADRENALINE, 0.8, "system:emergency")
        self.secrete(HormoneType.CORTISOL, 0.6, "system:emergency")

    # ═══ Circadian Integration ═══

    def _apply_circadian_modulation(self) -> None:
        """Sync hormone levels with the biological clock.

        Night hours (22-06) → release MELATONIN, reduce DOPAMINE.
        Morning hours (08-12) → release CORTISOL (waking), boost ACETYLCHOLINE.
        References:
          CircadianClock from organism_v2.py
          Reiter (1991): melatonin peaks during dark phase
        """
        from .organism_v2 import CircadianClock, TimeOfDay

        tod = CircadianClock.now()

        if tod == TimeOfDay.NIGHT:
            self.secrete(HormoneType.MELATONIN, 0.2, "circadian:pineal")
            self.secrete(HormoneType.DOPAMINE, -0.1, "circadian:dopamine_suppression")
        elif tod == TimeOfDay.DAWN:
            self.secrete(HormoneType.CORTISOL, 0.15, "circadian:cortisol_awakening")
            self.secrete(HormoneType.ACETYLCHOLINE, 0.15, "circadian:focus")
            self.secrete(HormoneType.MELATONIN, -0.3, "circadian:melatonin_clearance")
        elif tod == TimeOfDay.MORNING:
            self.secrete(HormoneType.CORTISOL, 0.1, "circadian:peak")
            self.secrete(HormoneType.DOPAMINE, 0.1, "circadian:reward_priming")
        elif tod == TimeOfDay.DUSK:
            self.secrete(HormoneType.SEROTONIN, 0.15, "circadian:winding_down")
            self.secrete(HormoneType.OXYTOCIN, 0.1, "circadian:bonding")

    # ═══ Synaptic Plasticity Integration ═══

    def _apply_plasticity_modulation(self) -> None:
        """Gate synaptic plasticity based on current hormone state.

        DOPAMINE > 0.3 → increase LTP rate (reinforcement learning, Schultz 1997)
        CORTISOL > 0.5  → increase LTD rate (stress-induced pruning, Sapolsky 2004)
        SEROTONIN > 0.5 → stabilize weights (mood-gated protection)

        This directly modulates SynapticPlasticity constants from synaptic_plasticity.py
        and strengthens/weakens recently-used synapses.
        """
        try:
            from ..core.synaptic_plasticity import get_plasticity

            plasticity = get_plasticity()
            dopamine = self.get_level(HormoneType.DOPAMINE)
            cortisol = self.get_level(HormoneType.CORTISOL)
            serotonin = self.get_level(HormoneType.SEROTONIN)

            if dopamine > 0.3:
                original_ltp = plasticity.LTP_RATE
                plasticity.LTP_RATE = 0.12 * (1.0 + dopamine)
                logger.debug(
                    f"Plasticity: LTP boosted {original_ltp:.3f} → {plasticity.LTP_RATE:.3f} "
                    f"(DOPAMINE={dopamine:.2f})"
                )
                plasticity.homeostatic_scale()

            if cortisol > 0.5:
                plasticity.decay_all()
                logger.debug(f"Plasticity: LTD triggered (CORTISOL={cortisol:.2f})")

            if serotonin > 0.5:
                for sid, meta in list(plasticity._synapses.items()):
                    if meta.state.value == "active":
                        plasticity.protect(sid, level=serotonin * 0.3)
                logger.debug(f"Plasticity: Stabilization applied (SEROTONIN={serotonin:.2f})")

            degradation = plasticity.degradation_alert()
            if degradation["severity"] == "critical":
                self.secrete(HormoneType.CORTISOL, 0.2, "system:knowledge_degradation")

        except Exception:
            pass

    # ═══ Decay & Homeostatic Regulation ═══

    def _apply_homeostatic_regulation(self) -> None:
        """Pull all hormone levels toward their baselines (set-point homeostasis).

        Homeostatic correction rate: ~0.05 per tick toward baseline.
        Prevents runaway hormone accumulation from repeated triggers.
        """
        rate = 0.05
        for ht in HormoneType:
            current = self.get_level(ht)
            baseline = ht.baseline
            if abs(current - baseline) < 0.005:
                continue
            correction = (baseline - current) * rate
            self.secrete(ht, correction, "system:homeostasis")

    # ═══ Cross-Regulation ═══

    def _apply_cross_regulation(self) -> None:
        """Hormones inhibit each other according to known endocrine pathways.

        CORTISOL ↑ → SEROTONIN ↓ (stress suppresses mood, chronic HPA activation)
        DOPAMINE ↑ → MELATONIN ↓ (reward arousal opposes sleep)
        SEROTONIN ↑ → CORTISOL ↓ (wellbeing dampens stress response)
        ACETYLCHOLINE ↑ → DOPAMINE ↑ (attention enhances reward sensitivity)
        OXYTOCIN ↑ → CORTISOL ↓ (social bonding buffers stress)
        References: McEwen (2007) allostatic load; Insel (2010) oxytocin review
        """
        cortisol = self.get_level(HormoneType.CORTISOL)
        dopamine = self.get_level(HormoneType.DOPAMINE)
        serotonin = self.get_level(HormoneType.SEROTONIN)
        acetylcholine = self.get_level(HormoneType.ACETYLCHOLINE)
        oxytocin = self.get_level(HormoneType.OXYTOCIN)

        if cortisol > 0.5:
            self.secrete(HormoneType.SEROTONIN, -0.05 * cortisol, "cross:cortisol→serotonin")
        if dopamine > 0.4:
            self.secrete(HormoneType.MELATONIN, -0.03 * dopamine, "cross:dopamine→melatonin")
        if serotonin > 0.5:
            self.secrete(HormoneType.CORTISOL, -0.05 * serotonin, "cross:serotonin→cortisol")
        if acetylcholine > 0.3:
            self.secrete(HormoneType.DOPAMINE, 0.02 * acetylcholine, "cross:acetylcholine→dopamine")
        if oxytocin > 0.4:
            self.secrete(HormoneType.CORTISOL, -0.04 * oxytocin, "cross:oxytocin→cortisol")

    # ═══ Tick — Main Update Loop ═══

    def tick(self, silent: bool = False) -> dict[str, Any]:
        """One complete endocrine cycle.

        1. Apply exponential decay to all circulating hormones
        2. Integrate with circadian clock (organism_v2.py)
        3. Modulate synaptic plasticity (core/synaptic_plasticity.py)
        4. Apply homeostatic pull toward baselines
        5. Apply cross-regulation between hormones
        6. Update organ states

        Returns:
            Stats dict with current hormone levels and organ states.
        """
        self._total_ticks += 1
        self._last_tick = time.time()

        for signal in self._hormones.values():
            signal.apply_decay()

        try:
            self._apply_circadian_modulation()
        except Exception as e:
            logger.warning(f"Circadian modulation failed: {e}")

        try:
            self._apply_plasticity_modulation()
        except Exception as e:
            logger.warning(f"Plasticity modulation failed: {e}")

        self._apply_homeostatic_regulation()
        self._apply_cross_regulation()

        for organ_name in self._organs:
            self.compute_organ_state(organ_name)

        self._critical_failure = False

        if not silent:
            logger.debug(
                f"Endocrine tick #{self._total_ticks}: "
                f"C={self.get_level(HormoneType.CORTISOL):.2f} "
                f"D={self.get_level(HormoneType.DOPAMINE):.2f} "
                f"M={self.get_level(HormoneType.MELATONIN):.2f} "
                f"A={self.get_level(HormoneType.ADRENALINE):.2f}"
            )

        return self.stats()

    # ═══ Stats ═══

    def stats(self) -> dict[str, Any]:
        """Current hormone levels, organ states, and network metadata."""
        hormone_levels = {
            ht.value: {
                "level": round(self.get_level(ht), 4),
                "baseline": ht.baseline,
                "half_life_s": ht.half_life_seconds,
                "source": self._hormones[ht].source_organ,
                "active": self._hormones[ht].is_active,
            }
            for ht in HormoneType
        }

        organ_states = {
            name: {
                "state": round(receptor.current_state, 3),
                "priority": round(self.get_organ_priority(name), 3),
                "active_receptors": [
                    ht for ht, sens in receptor.sensitivity.items() if sens > 0.1
                ],
                "last_activated": receptor.last_activated,
            }
            for name, receptor in self._organs.items()
        }

        return {
            "hormone_levels": hormone_levels,
            "organ_states": organ_states,
            "network": {
                "total_ticks": self._total_ticks,
                "last_tick": self._last_tick,
                "uptime_seconds": time.time() - self._born_at,
                "error_count": self._error_count,
                "success_count": self._success_count,
                "registered_organs": len(self._organs),
            },
        }

    # ═══ Background Pulse Loop ═══

    async def start_pulse(self, interval: float = 60.0) -> None:
        """Start the background endocrine pulse loop.

        Every `interval` seconds, executes a full tick cycle.
        This ensures hormone decay and auto-regulation continue
        even without explicit user/system triggers.

        Args:
            interval: Seconds between ticks (default: 60s)
        """
        if self._task and not self._task.done():
            logger.warning("Endocrine pulse loop already running")
            return

        self._task = asyncio.create_task(self._pulse_loop(interval))
        logger.info(f"Endocrine pulse started — interval={interval}s")

    async def stop_pulse(self) -> None:
        """Stop the background pulse loop."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Endocrine pulse stopped")

    async def _pulse_loop(self, interval: float) -> None:
        """Internal pulse loop coroutine."""
        while True:
            try:
                await asyncio.sleep(interval)
                self.tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Endocrine pulse error: {e}")


# ═══════════════════════════════════════════════════════
# 12-Organ Default Receptor Configuration
# ═══════════════════════════════════════════════════════

# Default sensitivity map — each organ expresses a subset of hormone receptors.
# Based on functional homology with biological organ systems.
#
# Biological mapping:
#   Intent (PFC — prefrontal cortex):         ACETYLCHOLINE 0.7, DOPAMINE 0.4, CORTISOL 0.5
#   Latent (basal ganglia — implicit):         DOPAMINE 0.6, SEROTONIN 0.3
#   Knowledge (hippocampus — memory):          ACETYLCHOLINE 0.5, CORTISOL 0.6, DOPAMINE 0.3
#   Capability (motor cortex — action):        DOPAMINE 0.7, ADRENALINE 0.5
#   Planning (dlPFC — executive):              ACETYLCHOLINE 0.6, CORTISOL 0.4
#   Execution (cerebellum — fine motor):       ADRENALINE 0.6, ACETYLCHOLINE 0.4
#   Reflection (ACC — monitoring):             CORTISOL 0.7, SEROTONIN 0.5
#   Compilation (thalamus — relay):            MELATONIN 0.4, ACETYLCHOLINE 0.3
#   Provider (amygdala — salience):            ADRENALINE 0.7, CORTISOL 0.6
#   Memory (hippocampus — consolidation):      MELATONIN 0.6, CORTISOL 0.5
#   Evolution (neurogenesis — plasticity):     DOPAMINE 0.5, OXYTOCIN 0.3
#   Emotion (insula — interoception):          SEROTONIN 0.7, OXYTOCIN 0.6

DEFAULT_ORGAN_SENSITIVITIES: dict[str, dict[str, float]] = {
    "intent": {"acetylcholine": 0.7, "cortisol": 0.5, "dopamine": 0.4},
    "latent": {"dopamine": 0.6, "serotonin": 0.3},
    "knowledge": {"acetylcholine": 0.5, "cortisol": 0.6, "dopamine": 0.3},
    "capability": {"dopamine": 0.7, "adrenaline": 0.5},
    "planning": {"acetylcholine": 0.6, "cortisol": 0.4},
    "execution": {"adrenaline": 0.6, "acetylcholine": 0.4},
    "reflection": {"cortisol": 0.7, "serotonin": 0.5},
    "compilation": {"melatonin": 0.4, "acetylcholine": 0.3},
    "provider": {"adrenaline": 0.7, "cortisol": 0.6},
    "memory": {"melatonin": 0.6, "cortisol": 0.5},
    "evolution": {"dopamine": 0.5, "oxytocin": 0.3},
    "emotion": {"serotonin": 0.7, "oxytocin": 0.6},
}


# ═══════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════

_endocrine: Optional[HormoneNetwork] = None


def get_endocrine() -> HormoneNetwork:
    """Get or create the global hormone signaling network singleton."""
    global _endocrine
    if _endocrine is None:
        _endocrine = HormoneNetwork()
        for organ_name, sensitivities in DEFAULT_ORGAN_SENSITIVITIES.items():
            _endocrine.register_organ(organ_name, sensitivities)
        logger.info(
            f"Endocrine network initialized: "
            f"{len(_endocrine._organs)} organs, "
            f"{len(HormoneType)} hormones"
        )
    return _endocrine


__all__ = [
    "HormoneType",
    "HormoneSignal",
    "OrganReceptor",
    "HormoneNetwork",
    "DEFAULT_ORGAN_SENSITIVITIES",
    "get_endocrine",
]
