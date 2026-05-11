"""Thermodynamic Budget Controller — entropy-driven adaptive budget allocation.

Based on Jacobson (1995) "Thermodynamics of spacetime":
  dQ = T dS  —  heat flow is proportional to temperature × entropy change
  Budget flow = urgency × entropy_delta

Based on Verlinde (2011) "Entropic gravity":
  F = T ΔS / Δx   —  gravity is an entropic force
  Spending rate = entropy_temperature × entropy_gradient

Intentional PG KL budget cascade (Sharifnassab et al., arXiv:2604.19033):
  Model tier selection replaces hard entropy thresholds with a KL budget:
    - KL budget accumulates from entropy generation (ΔS > 0 → add to budget)
    - KL budget is consumed by model tier upgrades (flash→pro→ultra costs budget)
    - When budget is high → system explores higher tiers freely
    - When budget is depleted → system conserves, sticks to proven tiers
  This creates a self-regulating cascade: high uncertainty builds exploration
  budget, which gets spent to resolve uncertainty, which reduces entropy.

Core analogy:
  - Temperature T → system urgency (how fast we need responses)
  - Entropy S → budget uncertainty (how unpredictable spending is)
  - Heat flow dQ → budget allocation rate
  - Entropic force F → spending pressure toward cheap/expensive providers
  - Entropy gradient ΔS/Δx → spending velocity toward equilibrium
  - KL budget → accumulated exploration allowance (entropy savings account)

Integration:
    thermo = ThermodynamicBudget(orchestrator)
    decision = thermo.evaluate(task)  # replaces static budget check
    thermo.record_spending(cost)       # update thermal state
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ═══ Thermodynamic Types ═══


@dataclass
class ThermalState:
    """Thermodynamic state of the budget system.

    Analogous to (T, S, P, V) in classical thermodynamics:
      temperature → urgency (average task priority × response demand)
      entropy → budget uncertainty (volatility of spending pattern)
      pressure → spending velocity (cost/time ratio)
      volume → remaining budget capacity
    """
    temperature: float = 0.5         # Urgency: 0=cold/slow, 1=hot/urgent
    entropy: float = 0.5             # Uncertainty: 0=ordered, 1=chaotic
    pressure: float = 0.5            # Spending pressure: 0=idle, 1=burst
    remaining_budget: float = 50.0   # Remaining daily budget (yuan)
    heat_flow: float = 0.0           # Current spending rate (yuan/hour)
    diffusion_coefficient: float = 0.0  # SDE diffusion: σ(T) — volatility of thermal state
    equilibrium_temp: float = 0.4    # Natural resting temperature
    timestamp: float = field(default_factory=time.time)


@dataclass
class ThermoDecision:
    """Thermodynamic budget decision for a single task.

    Analogous to a phase space trajectory in (T, S, P) space.
    """
    task_id: str
    proceed: bool                     # Whether to execute
    model_tier: str = "flash"        # flash, pro, or ultra
    allocated_budget: float = 0.0     # Yuan allocated
    temperature_now: float = 0.5      # Current system temperature
    entropy_now: float = 0.5          # Current budget entropy
    entropy_after: float = 0.5        # Predicted entropy after execution
    free_energy: float = 0.0          # F = U - TS (available budget energy)
    prediction_lower: float = 0.0     # SDE prediction interval lower bound (cost)
    prediction_upper: float = 0.0     # SDE prediction interval upper bound (cost)
    recommendation: str = ""


# ═══ Thermodynamic Budget Controller ═══


class ThermodynamicBudget:
    """Entropy-driven adaptive budget controller.

    Replaces static time-based scheduling (AdaptiveEconomicScheduler) with
    continuous thermodynamic state tracking. Budget policy emerges from
    the system's thermal equilibrium rather than hardcoded rules.

    Jacobson (1995): dQ = T dS
      → spending_decision = urgency × entropy_change

    Verlinde (2011): F = T ΔS / Δx
      → model_selection_pressure = temperature × entropy_gradient
      → higher entropy → more exploration (try new providers)
      → lower entropy → more exploitation (stick to proven providers)
    """

    def __init__(
        self,
        daily_budget_yuan: float = 50.0,
        lookback_window: int = 50,
        kl_budget_max: float = 1.0,
        kl_budget_decay: float = 0.98,
    ):
        self._state = ThermalState(remaining_budget=daily_budget_yuan)
        self._daily_budget = daily_budget_yuan
        self._history: deque[ThermoDecision] = deque(maxlen=lookback_window)
        self._spending_velocity: deque[float] = deque(maxlen=lookback_window)
        self._total_spent = 0.0
        self._day_start = time.time()

        # ── KL budget: accumulated exploration allowance ──
        # Accumulates from entropy generation (ΔS > 0 → budget += γ×ΔS)
        # Consumed by model tier upgrades (flash→pro costs 0.3, pro→ultra costs 0.5)
        # Decays over time (unused budget gradually fades)
        self._kl_budget: float = kl_budget_max * 0.3  # Start with 30% budget
        self._kl_budget_max: float = kl_budget_max
        self._kl_budget_decay: float = kl_budget_decay
        self._kl_budget_history: deque[float] = deque(maxlen=100)

    # ── Thermal State Update ──

    def record_spending(self, cost_yuan: float) -> None:
        """Record a spending event — updates thermal state.

        dQ =cost_yuan → affects entropy, temperature, and pressure.
        """
        self._total_spent += cost_yuan
        self._state.remaining_budget = max(0, self._daily_budget - self._total_spent)
        self._spending_velocity.append(cost_yuan)
        self._update_thermal_state()
        self._state.timestamp = time.time()

    def _update_thermal_state(self) -> None:
        """Recalculate thermal state from observations.

        Temperature ∝ urgency (recent priority-weighted spending rate)
        Entropy ∝ volatility of spending (std dev of recent costs)
        Pressure ∝ spending rate relative to remaining budget
        """
        # Temperature: urgency-driven
        if len(self._spending_velocity) >= 5:
            recent = list(self._spending_velocity)[-10:]
            avg_spend = sum(recent) / len(recent)
            # Temperature rises with spending rate
            max_expected = self._daily_budget / 24.0  # hourly expected
            self._state.temperature = min(1.0, avg_spend / max(max_expected, 0.01))

        # Entropy: spending volatility
        if len(self._spending_velocity) >= 5:
            recent = list(self._spending_velocity)[-20:]
            if recent:
                mean = sum(recent) / len(recent)
                var = sum((v - mean) ** 2 for v in recent) / len(recent)
                std = math.sqrt(var)
                # Normalize: entropy = volatility / mean (coefficient of variation)
                if mean > 0.001:
                    cv = std / mean
                    self._state.entropy = min(1.0, cv)
                else:
                    self._state.entropy = 0.0

        # Pressure: spending rate vs remaining budget
        time_left = max(1, 86400 - (time.time() - self._day_start))
        budget_rate = self._state.remaining_budget / time_left if time_left > 0 else 0
        recent_rate = sum(list(self._spending_velocity)[-5:]) / 300 if self._spending_velocity else 0  # per 5 min
        if budget_rate > 0.0001:
            self._state.pressure = min(1.0, recent_rate / budget_rate)
        else:
            self._state.pressure = 0.5

        # Heat flow: estimate current spending rate (yuan/hour)
        if len(self._spending_velocity) >= 5:
            recent = list(self._spending_velocity)[-10:]
            hours = max(0.1, (time.time() - self._day_start) / 3600)
            self._state.heat_flow = sum(recent) / hours

    # ── Decision Making ──

    def evaluate(
        self,
        task_id: str,
        estimated_cost: float,
        task_priority: float = 0.5,
        predicted_quality: float = 0.5,
    ) -> ThermoDecision:
        """Make a thermodynamic budget decision.

        Physically motivated decision rules:
          1. Free energy check: F = budget - T×S ≥ estimated_cost
             → F is the "available useful budget" after entropy penalty
          2. KL-budget-modulated model tier (replaces hard entropy thresholds):
             - Entropy generation (ΔS > 0) adds KL budget: entropy savings account
             - KL budget spent on tier upgrades: flash→pro costs 0.3, pro→ultra costs 0.5
             - When budget is high → system invests in exploration (higher tiers)
             - When budget is depleted → system conserves, sticks to proven tier
          3. Temperature-driven urgency: high T → bypass checks for critical tasks
        """
        state = self._state

        # ── KL budget: decay and accumulate from entropy ──
        self._kl_budget *= self._kl_budget_decay  # Gradual decay of unused budget
        if state.entropy > 0.4:
            # Entropy generation → add to KL budget (exploration savings)
            entropy_contribution = (state.entropy - 0.4) * 0.05
            self._kl_budget = min(self._kl_budget_max,
                                  self._kl_budget + entropy_contribution)

        # Free energy: F = U - TS (available budget energy)
        F = (state.remaining_budget
             - state.temperature * state.entropy * estimated_cost * 2)
        can_afford = F >= estimated_cost

        # ── KL-budget-modulated model tier ──
        # Base tier from entropy (conservative default)
        if state.entropy > 0.7:
            base_tier = "flash"  # High entropy → conservative
        elif state.entropy > 0.3:
            base_tier = "pro"    # Moderate → balanced
        else:
            base_tier = "ultra"  # Low entropy → confident

        # KL budget enables tier upgrades
        model_tier = base_tier
        if base_tier == "flash" and self._kl_budget >= 0.3:
            model_tier = "pro"
            self._kl_budget -= 0.3  # Spend budget on upgrade
        elif base_tier == "pro" and self._kl_budget >= 0.5:
            model_tier = "ultra"
            self._kl_budget -= 0.5  # Spend budget on upgrade

        # Temperature override: critical tasks bypass budget check
        urgency_threshold = max(0.2, 1.0 - state.temperature)
        if task_priority > urgency_threshold:
            can_afford = True
            model_tier = "ultra"
            # Refund KL budget for urgent tasks (don't penalize emergencies)
            self._kl_budget = min(self._kl_budget_max, self._kl_budget + 0.2)

        # Quality consideration: don't waste budget on likely-failing tasks
        if predicted_quality < 0.3 and model_tier == "ultra":
            model_tier = "pro"
            self._kl_budget = min(self._kl_budget_max, self._kl_budget + 0.2)

        self._kl_budget_history.append(self._kl_budget)

        # Predicted entropy after this task
        after_entropy = self._predict_entropy_after(estimated_cost)
        entropy_delta = after_entropy - state.entropy

        decision = ThermoDecision(
            task_id=task_id,
            proceed=can_afford,
            model_tier=model_tier,
            allocated_budget=estimated_cost,
            temperature_now=round(state.temperature, 3),
            entropy_now=round(state.entropy, 3),
            entropy_after=round(after_entropy, 3),
            free_energy=round(F, 4),
            recommendation=(
                f"{'GO' if can_afford else 'HOLD'} | "
                f"T={state.temperature:.2f} S={state.entropy:.2f} "
                f"ΔS={entropy_delta:+.3f} F=¥{F:.2f} | "
                f"tier={model_tier} KL={self._kl_budget:.3f}"
            ),
        )
        self._history.append(decision)
        return decision

    def _predict_entropy_after(self, cost: float) -> float:
        """Predict entropy after a hypothetical spending event.

        Uses the spending velocity to estimate whether this cost increases
        or decreases overall entropy (regular ≡ low entropy, irregular ≡ high).
        """
        if not self._spending_velocity:
            return self._state.entropy

        recent = list(self._spending_velocity)[-10:]
        mean = sum(recent) / len(recent)
        if mean < 0.0001:
            return self._state.entropy

        # Predict: how much does this cost deviate from recent pattern?
        deviation = abs(cost - mean) / mean
        # Large deviations increase entropy, regular patterns decrease it
        delta = (deviation - 1.0) * 0.1  # Small damping
        return max(0.0, min(1.0, self._state.entropy + delta))

    # ── KL Budget Cascade ──

    @property
    def kl_budget(self) -> float:
        """Current KL budget balance (exploration allowance)."""
        return self._kl_budget

    def consume_kl_budget(self, amount: float) -> bool:
        """Attempt to consume KL budget for an external decision.

        Used by EconomicOrchestrator to cascade budget to provider routing,
        model selection, and other exploration decisions.

        Returns True if sufficient budget was available.
        """
        if self._kl_budget >= amount:
            self._kl_budget -= amount
            self._kl_budget_history.append(self._kl_budget)
            return True
        return False

    def contribute_kl_budget(self, amount: float) -> None:
        """Add to KL budget (e.g., from successful low-cost routing)."""
        self._kl_budget = min(self._kl_budget_max, self._kl_budget + amount)

    # ── Entropy-Driven Policy ──

    def optimal_spending_rate(self) -> float:
        """Compute the optimal spending rate that maximizes free energy.

        Solve: dF/dt = 0 → find rate that balances spending and conservation.
        F = budget - T×S → optimal when marginal benefit = marginal cost.
        """
        state = self._state
        time_remaining = max(1, 86400 - (time.time() - self._day_start))
        # Steady spending: distribute remaining budget over remaining time
        steady = state.remaining_budget / (time_remaining / 3600)  # yuan/hour
        # Adjust by entropy: chaotic periods → slow down
        adjusted = steady * (1.0 - 0.5 * state.entropy)
        return max(0.0, adjusted)

    def entropy_budget_ratio(self) -> float:
        """Budget-to-entropy ratio — system health indicator.

        > 1: budget is abundant relative to uncertainty → healthy
        < 0.5: uncertainty dominates budget → danger zone
        """
        if self._state.entropy < 0.01:
            return float('inf')
        return self._state.remaining_budget / self._state.entropy

    # ── Phase Transitions (Ising Model analogy) ──

    def detect_phase_transition(self) -> str:
        """Detect budget phase transitions (Ising model analog).

        Returns state: 'frozen' (no spending), 'ordered' (steady),
        'critical' (near phase boundary), 'chaotic' (uncontrolled).
        """
        s = self._state
        if s.entropy < 0.2 and s.pressure < 0.2:
            return "frozen"
        if s.entropy < 0.4 and s.pressure < 0.5:
            return "ordered"
        if 0.4 <= s.entropy <= 0.7:
            return "critical"
        return "chaotic"

    # ── Daily Reset ──

    def reset_daily(self) -> None:
        """Reset budget for a new day."""
        self._total_spent = 0.0
        self._state = ThermalState(remaining_budget=self._daily_budget)
        self._day_start = time.time()
        self._history.clear()

    # ── Stats ──

    def stats(self) -> dict[str, Any]:
        return {
            "temperature": round(self._state.temperature, 3),
            "entropy": round(self._state.entropy, 3),
            "pressure": round(self._state.pressure, 3),
            "remaining_budget": round(self._state.remaining_budget, 2),
            "total_spent": round(self._total_spent, 4),
            "heat_flow_yuan_per_hour": round(self._state.heat_flow, 4),
            "entropy_budget_ratio": (
                round(self.entropy_budget_ratio(), 2)
                if self._state.entropy > 0.01 else float('inf')
            ),
            "phase": self.detect_phase_transition(),
            "optimal_rate_yuan_per_hour": round(self.optimal_spending_rate(), 4),
        }

    @property
    def state(self) -> ThermalState:
        """Current thermal state (read-only copy)."""
        return ThermalState(
            temperature=self._state.temperature,
            entropy=self._state.entropy,
            pressure=self._state.pressure,
            remaining_budget=self._state.remaining_budget,
            heat_flow=self._state.heat_flow,
            equilibrium_temp=self._state.equilibrium_temp,
        )


# ═══ Singleton ═══

_thermo_budget: ThermodynamicBudget | None = None


def get_thermo_budget(daily_budget: float = 50.0) -> ThermodynamicBudget:
    global _thermo_budget
    if _thermo_budget is None:
        _thermo_budget = ThermodynamicBudget(daily_budget_yuan=daily_budget)
    return _thermo_budget


__all__ = [
    "ThermodynamicBudget", "ThermalState", "ThermoDecision",
    "get_thermo_budget",
]
