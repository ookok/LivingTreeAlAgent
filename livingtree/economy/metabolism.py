"""Metabolism Engine — Unified resource consumption across all 12 organs.

DISPLAY LAYER: Metabolic ATP/Glucose/O2/NADPH tracking is for monitoring only.
Routing is controlled by SurvivalMode (budget/error/memory-driven), not by
Krebs cycle metabolic rates. Token budgets are enforced by BudgetRouter + SurvivalMode.

Biological grounding:
  Krebs cycle (citric acid cycle): ATP production via oxidative phosphorylation —
    organs consume ATP proportional to their metabolic rate. The Metabolism Engine
    models this as a resource allocation problem: each organ draws ATP, glucose
    (tokens), oxygen (memory), and NADPH (model quality) from a shared pool.

  Kleiber's law (1932): BMR ∝ M^(3/4) — metabolic rate scales with body mass.
    Applied here: basal rates scale with organ complexity (cerebrum > memory > economy).

  Cahill (1970) "Starvation and Ketosis": When glucose is depleted, the body enters
    ketosis — switching to alternative energy (fatty acids/ketone bodies). The engine
    models ketosis as ultra-low-power mode where only essential organs remain active.

  Owen et al. (1967) "Brain Metabolism during Fasting": The cerebrum gradually
    adapts to ketone bodies during prolonged starvation, reducing glucose demand
    by up to 60%. The engine simulates this as progressive metabolic suppression.

Integration:
  - thermo_budget.py: MetabolismEngine supplies starvation_level for thermal state
  - token_accountant.py: MetabolismEngine enforces per-organ glucose (token) budgets
  - economic_engine.py: MetabolicCost informs ROIModel cost estimates
  - hormone_signaling.py: CORTISOL secretion when starvation_level > 0.5

Default organ metabolic rates (basal ATP/s, active multiplier):
  cerebrum: 5/4.0, memory: 2/2.0, knowledge: 3/3.0, execution: 2/4.0,
  perception: 1/2.0, reflection: 1/1.5, immune: 1/3.0, economy: 1/2.0,
  planning: 2/3.0, compilation: 1/2.0, evolution: 1/2.5, social: 1/1.5
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from loguru import logger

# ── Daily budget reset (seconds) ──
_DAY_SECONDS = 86400


# ═══════════════════════════════════════════════════════════════════
# Metabolite Types (4 primary energy/substrate currencies)
# ═══════════════════════════════════════════════════════════════════


class Metabolite(StrEnum):
    ATP = "atp"           # Computation/energy budget — the universal energy currency
    GLUCOSE = "glucose"   # Tokens — the fuel for LLM inference
    OXYGEN = "oxygen"     # Memory — the oxidative capacity (MB available)
    NADPH = "nadph"       # Model quality/cost — reducing power for biosynthesis


# ═══════════════════════════════════════════════════════════════════
# Organ Operability — operation types
# ═══════════════════════════════════════════════════════════════════


class OperationType(StrEnum):
    BASAL = "basal"       # Resting/idle consumption — always active
    ACTIVE = "active"     # Under-load — processing a request
    PEAK = "peak"         # Burst — maximum intensity


# ═══════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════


@dataclass
class MetabolicCost:
    """The resource cost of a single metabolic operation."""
    organ_name: str
    operation: OperationType
    atp: float = 0.0
    glucose: float = 0.0       # Tokens consumed
    oxygen_mb: float = 0.0     # Memory consumed (MB)
    nadph: float = 0.0         # Quality/cost impact [0-1]
    intensity: float = 1.0
    timestamp: float = field(default_factory=time.time)

    @property
    def total_energy(self) -> float:
        """Weighted total metabolic cost (ATP-equivalent)."""
        return (
            self.atp * 1.0
            + self.glucose * 0.8
            + self.oxygen_mb * 0.01
            + self.nadph * 2.0
        )


@dataclass
class OrganMetabolism:
    """Metabolic profile for a single organ.

    Analogous to a tissue's metabolic rate in physiology: each organ has
    a basal metabolic rate (resting) and an active multiplier (under load).
    """
    organ_name: str
    basal_rate: float             # Resting ATP/s consumption
    active_rate: float            # Active multiplier (× basal for active ops)
    current_consumption: float = 0.0   # Running ATP consumption
    atp_per_second: float = 0.0        # Instantaneous ATP draw
    glucose_per_request: float = 0.0   # Tokens per typical request
    oxygen_mb: float = 0.0             # Memory footprint (MB)
    total_atp_spent: float = 0.0       # Cumulative ATP consumed
    request_count: int = 0
    suppressed: bool = False           # True when auto-throttled
    priority: int = 5                  # 1=critical, 10=dispensable

    @property
    def active_draw(self) -> float:
        """Current ATP draw if active (basal × active_rate × intensity)."""
        return self.basal_rate * self.active_rate

    @property
    def basal_draw(self) -> float:
        """Resting ATP consumption."""
        return self.basal_rate


@dataclass
class MetabolicState:
    """Global metabolic state of the entire digital organism.

    Analogous to whole-body metabolic panel: blood glucose, oxygen saturation,
    core temperature, starvation markers.
    """
    total_atp: float = 500.0         # Total ATP pool available
    total_glucose: float = 1_000_000.0  # Token budget remaining
    total_oxygen_mb: float = 4096.0  # Memory available (MB)
    current_temperature: float = 0.3  # System load [0-1]
    starvation_level: float = 0.0     # 0=well-fed, 1=starving
    ketosis: bool = False             # Alternative energy mode
    cumulative_atp_spent: float = 0.0
    cumulative_glucose_spent: float = 0.0
    daily_cost_yuan: float = 0.0
    last_updated: float = field(default_factory=time.time)
    budget_day_start: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════════
# Default Organ Metabolic Profiles
# ═══════════════════════════════════════════════════════════════════

DEFAULT_ORGAN_METABOLISM: dict[str, tuple[float, float, float, float, int]] = {
    # organ_name: (basal_atp_s, active_mult, glucose_per_req, oxygen_mb, priority)
    "cerebrum":    (5.0, 4.0, 2000.0, 512.0, 1),
    "memory":      (2.0, 2.0, 500.0,  256.0, 2),
    "knowledge":   (3.0, 3.0, 1500.0, 384.0, 2),
    "execution":   (2.0, 4.0, 3000.0, 256.0, 1),
    "perception":  (1.0, 2.0, 200.0,  128.0, 4),
    "reflection":  (1.0, 1.5, 1000.0, 192.0, 3),
    "immune":      (1.0, 3.0, 500.0,  128.0, 2),
    "economy":     (1.0, 2.0, 300.0,  96.0,  5),
    "planning":    (2.0, 3.0, 2000.0, 256.0, 3),
    "compilation": (1.0, 2.0, 800.0,  128.0, 4),
    "evolution":   (1.0, 2.5, 600.0,  192.0, 5),
    "social":      (1.0, 1.5, 300.0,  96.0,  5),
}

# Organs that remain active during ketosis (priority <= 3)
_KETOSIS_ORGANS = {"cerebrum", "memory", "knowledge", "execution", "immune"}

# Starvation threshold for auto-throttling low-priority organs
_STARVATION_THRESHOLD = 0.7

# Decay multiplier per tick (5-second interval)
_DECAY_RATE = 0.001


# ═══════════════════════════════════════════════════════════════════
# Metabolism Engine
# ═══════════════════════════════════════════════════════════════════


class MetabolismEngine:
    """Unified resource metabolism across all 12 organs.

    Models the digital organism's resource consumption as a metabolic
    network: each organ draws from a shared ATP/glucose/oxygen pool.
    Auto-throttles low-priority organs during starvation, simulates
    ketosis as an ultra-low-power survival mode, and integrates with
    thermo_budget.py and token_accountant.py for cross-module coherence.

    Background loop: runs every 5 seconds to decay glucose, update
    starvation levels, and auto-throttle organs.
    """

    def __init__(self):
        self._state = MetabolicState()
        self._organs: dict[str, OrganMetabolism] = {}
        self._cost_history: list[MetabolicCost] = []
        self._background_task: asyncio.Task | None = None
        self._running = False

        for name, (basal, active, glc, oxy, pri) in DEFAULT_ORGAN_METABOLISM.items():
            self._organs[name] = OrganMetabolism(
                organ_name=name,
                basal_rate=basal,
                active_rate=active,
                glucose_per_request=glc,
                oxygen_mb=oxy,
                priority=pri,
            )

        logger.info(
            f"MetabolismEngine: {len(self._organs)} organs initialized | "
            f"ATP={self._state.total_atp:.0f} Glucose={self._state.total_glucose:.0f} "
            f"O2={self._state.total_oxygen_mb:.0f}MB"
        )

    # ── Background Loop ──

    async def start_background(self) -> None:
        """Start the 5-second metabolic update loop."""
        if self._running:
            return
        self._running = True
        self._background_task = asyncio.create_task(self._metabolic_loop())
        logger.info("MetabolismEngine: background loop started (5s tick)")

    async def stop_background(self) -> None:
        """Stop the background loop."""
        self._running = False
        if self._background_task:
            self._background_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._background_task
            self._background_task = None
        logger.info("MetabolismEngine: background loop stopped")

    async def _metabolic_loop(self) -> None:
        """Main metabolic tick: decay, starvation check, auto-throttle."""
        while self._running:
            await asyncio.sleep(5.0)
            try:
                self._tick()
            except Exception as exc:
                logger.error(f"MetabolismEngine tick error: {exc}")

    def _tick(self) -> None:
        """Single metabolic tick: update state and enforce policies."""
        state = self._state
        now = time.time()

        # Decay glucose (basal consumption by all active organs)
        total_basal_glucose = 0.0
        for organ in self._organs.values():
            if organ.suppressed:
                continue
            total_basal_glucose += organ.glucose_per_request * _DECAY_RATE

        state.total_glucose = max(0.0, state.total_glucose - total_basal_glucose)
        state.cumulative_glucose_spent += total_basal_glucose

        # Decay ATP (basal ATP consumption)
        total_basal_atp = 0.0
        for organ in self._organs.values():
            if organ.suppressed:
                continue
            basal_draw = organ.basal_rate * 5.0  # 5-second tick
            total_basal_atp += basal_draw
            organ.total_atp_spent += basal_draw
            organ.atp_per_second = basal_draw / 5.0

        state.total_atp = max(0.0, state.total_atp - total_basal_atp)
        state.cumulative_atp_spent += total_basal_atp

        # Update starvation level
        glucose_ratio = state.total_glucose / max(DEFAULT_ORGAN_METABOLISM["cerebrum"][2] * 100, 1.0)
        atp_ratio = state.total_atp / max(100.0, 1.0)
        oxygen_ratio = state.total_oxygen_mb / max(1024.0, 1.0)

        state.starvation_level = min(1.0, max(0.0,
            1.0 - (glucose_ratio * 0.4 + atp_ratio * 0.35 + oxygen_ratio * 0.25)
        ))

        # Update temperature based on current metabolic activity
        total_draw = sum(o.atp_per_second for o in self._organs.values())
        max_draw = sum(o.basal_rate * o.active_rate for o in self._organs.values())
        state.current_temperature = min(1.0, total_draw / max(max_draw, 0.01))

        # Auto-throttle: suppress low-priority organs when starving
        if state.starvation_level > _STARVATION_THRESHOLD and not state.ketosis:
            self._auto_throttle()
        elif state.starvation_level < 0.3:
            self._release_throttle()

        state.last_updated = now

        # Check if daily budget needs reset
        if now - state.budget_day_start > _DAY_SECONDS:
            self._reset_daily()

    def _auto_throttle(self) -> None:
        """Suppress low-priority organs to conserve resources."""
        state = self._state
        suppressed = 0
        for organ in sorted(self._organs.values(), key=lambda o: -o.priority):
            if organ.priority > 6 and not organ.suppressed:
                organ.suppressed = True
                suppressed += 1
                logger.debug(
                    f"Metabolism: throttled {organ.organ_name} "
                    f"(priority={organ.priority}, starvation={state.starvation_level:.2f})"
                )
        if suppressed:
            logger.warning(
                f"Metabolism: auto-throttled {suppressed} organs "
                f"(starvation={state.starvation_level:.2f})"
            )

    def _release_throttle(self) -> None:
        """Re-enable all suppressed organs."""
        for organ in self._organs.values():
            if organ.suppressed:
                organ.suppressed = False

    def _reset_daily(self) -> None:
        """Reset daily budgets at midnight."""
        self._state.budget_day_start = time.time()
        self._state.daily_cost_yuan = 0.0
        if self._last_total_tokens and self._last_total_cost:
            self.allocate_daily_budget(self._last_total_tokens, self._last_total_cost)
        logger.info("MetabolismEngine: daily budget reset")

    # ── Core API ──

    def consume(
        self,
        organ_name: str,
        operation_type: OperationType = OperationType.ACTIVE,
        intensity: float = 1.0,
    ) -> tuple[bool, MetabolicCost]:
        """Attempt to consume resources for an organ operation.

        Args:
            organ_name: Which organ is requesting resources.
            operation_type: basal, active, or peak.
            intensity: Operation intensity [0-1], modulates cost.

        Returns:
            (allowed: bool, cost: MetabolicCost) — whether sufficient
            resources were available and the computed cost.
        """
        organ = self._organs.get(organ_name)
        if organ is None:
            logger.warning(f"Metabolism: unknown organ '{organ_name}'")
            return False, MetabolicCost(
                organ_name=organ_name, operation=operation_type)

        if organ.suppressed:
            logger.debug(f"Metabolism: organ '{organ_name}' is suppressed (starvation)")
            return False, MetabolicCost(
                organ_name=organ_name, operation=operation_type)

        state = self._state
        intensity_clamped = max(0.1, min(1.0, intensity))

        # Compute costs
        if operation_type == OperationType.BASAL:
            atp_cost = organ.basal_rate * intensity_clamped
            mult = 1.0
        elif operation_type == OperationType.PEAK:
            atp_cost = organ.basal_rate * organ.active_rate * 1.5 * intensity_clamped
            mult = organ.active_rate * 1.5
        else:  # ACTIVE
            atp_cost = organ.basal_rate * organ.active_rate * intensity_clamped
            mult = organ.active_rate

        glucose_cost = organ.glucose_per_request * intensity_clamped * (mult / max(organ.active_rate, 0.1))
        oxygen_cost = organ.oxygen_mb * 0.1 * intensity_clamped
        nadph_cost = 0.05 * intensity_clamped * (mult / max(organ.active_rate, 0.1))

        # Ketosis mode: reduced glucose, increased ATP from alternative pathway
        if state.ketosis:
            glucose_cost *= 0.3
            atp_cost *= 0.6
            if organ_name not in _KETOSIS_ORGANS:
                return False, MetabolicCost(
                    organ_name=organ_name, operation=operation_type,
                    atp=atp_cost, glucose=glucose_cost,
                    oxygen_mb=oxygen_cost, nadph=nadph_cost, intensity=intensity_clamped)

        cost = MetabolicCost(
            organ_name=organ_name,
            operation=operation_type,
            atp=round(atp_cost, 3),
            glucose=round(glucose_cost, 1),
            oxygen_mb=round(oxygen_cost, 2),
            nadph=round(nadph_cost, 3),
            intensity=round(intensity_clamped, 3),
        )

        # Check affordability
        if not self.can_afford(organ_name, operation_type):
            return False, cost

        # Deduct resources
        state.total_atp = max(0.0, state.total_atp - atp_cost)
        state.total_glucose = max(0.0, state.total_glucose - glucose_cost)
        state.total_oxygen_mb = max(0.0, state.total_oxygen_mb - oxygen_cost)
        state.cumulative_atp_spent += atp_cost
        state.cumulative_glucose_spent += glucose_cost

        organ.current_consumption += atp_cost
        organ.total_atp_spent += atp_cost
        organ.atp_per_second = atp_cost
        organ.request_count += 1

        # Estimate cost in yuan (NADPH-based proxy)
        est_yuan = nadph_cost * 0.02 * organ.basal_rate
        state.daily_cost_yuan += est_yuan

        self._cost_history.append(cost)
        if len(self._cost_history) > 500:
            self._cost_history = self._cost_history[-500:]

        return True, cost

    def can_afford(
        self,
        organ_name: str,
        operation_type: OperationType = OperationType.ACTIVE,
    ) -> bool:
        """Check if an operation can proceed without actually deducting.

        Uses estimated costs from consume()'s cost model.
        """
        organ = self._organs.get(organ_name)
        if organ is None or organ.suppressed:
            return False

        state = self._state
        if operation_type == OperationType.BASAL:
            atp_needed = organ.basal_rate
        elif operation_type == OperationType.PEAK:
            atp_needed = organ.basal_rate * organ.active_rate * 1.5
        else:
            atp_needed = organ.basal_rate * organ.active_rate

        glucose_needed = organ.glucose_per_request

        if state.ketosis and organ_name not in _KETOSIS_ORGANS:
            return False

        atp_ok = state.total_atp >= atp_needed * 0.5
        glucose_ok = state.total_glucose >= glucose_needed * 0.3
        oxygen_ok = state.total_oxygen_mb >= organ.oxygen_mb * 0.05

        return atp_ok and glucose_ok and oxygen_ok

    # ── Starvation & Ketosis ──

    def get_starvation_level(self) -> float:
        """Current starvation level: 0=well-fed, 1=starving.

        Used by thermo_budget.py to modulate spending aggressiveness.
        """
        return round(self._state.starvation_level, 4)

    def enter_ketosis(self) -> None:
        """Switch to ultra-low-power mode — only essential organs active.

        Ketosis (Cahill, 1970): When glucose is depleted beyond a critical
        threshold, the organism switches to ketone body metabolism. The
        cerebrum gradually adapts, reducing glucose demand ~60%. Non-essential
        organs enter dormancy.

        Essential organs during ketosis: cerebrum, memory, knowledge,
        execution, immune.
        """
        if self._state.ketosis:
            return
        self._state.ketosis = True
        # Suppress all non-essential organs
        for name, organ in self._organs.items():
            if name not in _KETOSIS_ORGANS:
                organ.suppressed = True
        logger.warning(
            f"Metabolism: ENTERED KETOSIS — {len(_KETOSIS_ORGANS)} organs active, "
            f"{len(self._organs) - len(_KETOSIS_ORGANS)} suppressed | "
            f"starvation={self._state.starvation_level:.2f}"
        )

    def exit_ketosis(self) -> None:
        """Resume normal metabolism — re-enable all organs."""
        if not self._state.ketosis:
            return
        self._state.ketosis = False
        for organ in self._organs.values():
            organ.suppressed = False
        logger.info("Metabolism: EXITED KETOSIS — all organs resumed")

    # ── Budget Allocation ──

    def allocate_daily_budget(
        self,
        total_tokens: float,
        total_cost_yuan: float,
    ) -> None:
        """Initialize daily resource budgets.

        Called at session start or daily reset. Distributes the allocated
        token budget as glucose and estimates ATP/oxygen from cost.

        Args:
            total_tokens: Total token budget for the day (e.g. 1M).
            total_cost_yuan: Maximum daily cost in yuan (e.g. 50.0).
        """
        self._last_total_tokens = total_tokens
        self._last_total_cost = total_cost_yuan
        state = self._state
        state.total_glucose = total_tokens
        # ATP estimate: 1 ATP per 1000 tokens at baseline
        state.total_atp = total_tokens / 500.0
        # Oxygen: memory allocated as ~20% of token budget in MB estimate
        state.total_oxygen_mb = max(1024.0, total_tokens / 250.0)
        state.daily_cost_yuan = 0.0
        state.starvation_level = 0.0
        state.budget_day_start = time.time()
        state.last_updated = time.time()

        # Reset organ cumulative stats
        for organ in self._organs.values():
            organ.current_consumption = 0.0
            organ.total_atp_spent = 0.0
            organ.request_count = 0
            organ.suppressed = False

        logger.info(
            f"Metabolism: daily budget allocated | "
            f"tokens={total_tokens:,.0f} cost=¥{total_cost_yuan:.2f} | "
            f"ATP={state.total_atp:.0f} O2={state.total_oxygen_mb:.0f}MB"
        )

    # ── Query & Diagnosis ──

    def is_organ_suppressed(self, organ_name: str) -> bool:
        """Check if a specific organ has been auto-throttled."""
        organ = self._organs.get(organ_name)
        return organ.suppressed if organ else False

    def is_in_ketosis(self) -> bool:
        """Whether the organism is currently in ketosis survival mode."""
        return self._state.ketosis

    def organ_utilization(self) -> dict[str, float]:
        """Per-organ utilization: ATP spent / total system ATP spent."""
        total = max(sum(o.total_atp_spent for o in self._organs.values()), 0.001)
        return {
            name: round(organ.total_atp_spent / total, 4)
            for name, organ in self._organs.items()
        }

    # ── Stats ──

    def stats(self) -> dict[str, Any]:
        """Current metabolic state and per-organ consumption breakdown."""
        state = self._state
        organ_breakdown = {}
        for name, organ in self._organs.items():
            organ_breakdown[name] = {
                "basal_atp_s": organ.basal_rate,
                "active_multiplier": organ.active_rate,
                "atp_spent": round(organ.total_atp_spent, 2),
                "requests": organ.request_count,
                "suppressed": organ.suppressed,
                "priority": organ.priority,
                "current_atp_s": round(organ.atp_per_second, 3),
            }

        recent_costs = self._cost_history[-20:]
        avg_cost = (
            sum(c.total_energy for c in recent_costs) / max(len(recent_costs), 1)
        )

        return {
            "starvation_level": round(state.starvation_level, 4),
            "ketosis": state.ketosis,
            "total_atp": round(state.total_atp, 1),
            "total_glucose": round(state.total_glucose, 0),
            "total_oxygen_mb": round(state.total_oxygen_mb, 1),
            "temperature": round(state.current_temperature, 3),
            "cumulative_atp_spent": round(state.cumulative_atp_spent, 1),
            "cumulative_glucose_spent": round(state.cumulative_glucose_spent, 0),
            "daily_cost_yuan": round(state.daily_cost_yuan, 4),
            "avg_recent_energy_cost": round(avg_cost, 3),
            "suppressed_organs": sum(1 for o in self._organs.values() if o.suppressed),
            "active_organs": sum(1 for o in self._organs.values() if not o.suppressed),
            "organs": organ_breakdown,
            "cost_history_size": len(self._cost_history),
        }

    # ── Integration Hooks ──

    def notify_token_spent(self, tokens: int, cost_yuan: float = 0.0) -> None:
        """Called by token_accountant.py when tokens are consumed.

        Deducts from glucose pool and updates daily cost tracking.
        """
        self._state.total_glucose = max(0.0, self._state.total_glucose - tokens)
        self._state.cumulative_glucose_spent += tokens
        self._state.daily_cost_yuan += cost_yuan

    def notify_budget_event(self, cost_yuan: float) -> None:
        """Called by thermo_budget.py when a spending event occurs.

        Updates daily cost tracker for cross-module coherence.
        """
        self._state.daily_cost_yuan += cost_yuan

    @property
    def state(self) -> MetabolicState:
        """Current metabolic state (read-only copy)."""
        return MetabolicState(
            total_atp=self._state.total_atp,
            total_glucose=self._state.total_glucose,
            total_oxygen_mb=self._state.total_oxygen_mb,
            current_temperature=self._state.current_temperature,
            starvation_level=self._state.starvation_level,
            ketosis=self._state.ketosis,
            cumulative_atp_spent=self._state.cumulative_atp_spent,
            cumulative_glucose_spent=self._state.cumulative_glucose_spent,
            daily_cost_yuan=self._state.daily_cost_yuan,
            last_updated=self._state.last_updated,
            budget_day_start=self._state.budget_day_start,
        )


# ═══════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════

_metabolism_engine: MetabolismEngine | None = None
_metabolism_lock = __import__('threading').Lock()


def get_metabolism() -> MetabolismEngine:
    global _metabolism_engine
    if _metabolism_engine is None:
        with _metabolism_lock:
            if _metabolism_engine is None:
                _metabolism_engine = MetabolismEngine()
    return _metabolism_engine


def reset_metabolism() -> None:
    """Reset the metabolism singleton (for testing)."""
    global _metabolism_engine
    _metabolism_engine = None


__all__ = [
    "Metabolite",
    "OperationType",
    "MetabolicCost",
    "OrganMetabolism",
    "MetabolicState",
    "MetabolismEngine",
    "DEFAULT_ORGAN_METABOLISM",
    "get_metabolism",
    "reset_metabolism",
]
