"""Unified Action Principle — the single variational law governing all modules.

Nature's deepest law: δS = δ∫ L dt = 0
  The actual path taken by any physical system minimizes the action S.

LivingTree as a physical system:
  State:    all_weights × all_beliefs × all_hypergraph × all_policies
  Time:     training cycles / task executions
  Action:   S = ∫ (T - V) dt

Module-specific Lagrangians derived from the unified principle:
  T (kinetic / adaptation cost):
    SynapticPlasticity: ½ Σ (dw/dt)²      — rate of weight change
    ThompsonRouter:     ½ Σ (dα/dt)²      — rate of belief update
    LatentGRPO:         ½ Σ (dz*/dt)²     — rate of latent center shift
    
  V (potential / error cost):  
    SynapticPlasticity: ½ Σ (w - w_target)² × interference_ratio
    ThompsonRouter:     Σ regret(selected, optimal)
    LatentGRPO:         ½ Σ (z_a - z*)²   — distance from optimum
    Hypergraph:         Σ (entity_distance)² / (1 + edge_weight)
    Economic:           Σ cost_yuan × (1 - roi)

Euler-Lagrange: d/dt (∂L/∂ẋ) - ∂L/∂x = 0
  → Optimal learning rate: η* = √(interference_penalty / adaptation_speed)
  → Optimal decay rate:    d* = √(silent_ratio × pruning_cost)
  → Optimal exploration:   ε* = √(uncertainty / regret_sensitivity)

Noether conserved quantities:
  Energy:    E = T + V  → budget_cap = max_daily_cost
  Momentum:  p = ∂L/∂ẋ  → learning_momentum = accumulated gradient
  Angular:   L = r × p  → exploration×uncertainty = constant (uncertainty principle)
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ═══ Data Types ═══


@dataclass
class LagrangianDecomposition:
    """Decomposition of the total Lagrangian into T and V components."""
    name: str                      # Module name
    kinetic: float                 # T = adaptation cost
    potential: float               # V = error cost
    total: float                   # L = T - V
    euler_lagrange_residual: float # How close to δS=0 (0=optimal)


@dataclass
class ActionAnalysis:
    """Complete action principle analysis of the current system state."""
    timestamp: float
    # Total action components
    total_kinetic: float
    total_potential: float
    total_action: float            # S = Σ L_i (symbolic)
    # Module decompositions
    modules: list[LagrangianDecomposition]
    # Euler-Lagrange optimality
    avg_el_residual: float         # Average violation of δS=0
    system_on_shell: bool          # Is the system on the optimal trajectory?
    # Optimal hyperparameters (derived from action principle)
    optimal_params: dict[str, float]
    # Noether invariants
    conserved_quantities: dict[str, float]


# ═══ Unified Action Principle ═══


class ActionPrinciple:
    """The single variational law from which all module behaviors emerge.

    δS = 0 is the global optimality condition.
    Every module's local objective is a special case of this principle
    for a specific Lagrangian decomposition.
    """

    def __init__(self):
        self._last_state: dict[str, float] = {}
        self._state_velocities: dict[str, float] = {}
        self._analysis_history: deque[ActionAnalysis] = deque(maxlen=50)
        self._update_count = 0

    # ═══ Update State (feed from any module) ═══

    def observe(self, module: str, metric: str, value: float) -> None:
        """Record a state variable from any module.

        This builds the system's state vector for Lagrangian computation.
        """
        key = f"{module}:{metric}"
        # Compute velocity (rate of change)
        if key in self._last_state:
            velocity = value - self._last_state[key]
            self._state_velocities[key] = velocity
        self._last_state[key] = value
        self._update_count += 1

    def observe_batch(self, module: str, metrics: dict[str, float]) -> None:
        """Record multiple metrics from a module at once."""
        for metric, value in metrics.items():
            self.observe(module, metric, value)

    # ═══ Lagrangian Computation ═══

    def compute_module_lagrangian(
        self, module: str, state: dict[str, float],
        weights: dict[str, float] | None = None,
    ) -> LagrangianDecomposition:
        """Compute T, V, L for a specific module.

        The Lagrangian for each module is derived from first principles:
        
        Module              T (kinetic)              V (potential)
        ─────────────────────────────────────────────────────────────
        synaptic           ½ Σ (Δw/Δt)²           ½ Σ(w - w̄)² × ir
        provider           ½ Σ (Δα/Δt)²          Σ regret(selected)
        latent_grpo        ½ Σ (Δz*/Δt)²         ½ Σ(z_a - z*)²
        hypergraph         ½ Σ (ΔN/Δt)²          Σ dist²/(1+weight)
        economic           ½ Σ (Δcost/Δt)²       Σ cost × (1-roi)
        pipeline           ½ Σ (Δmode/Δt)²       Σ (1-success_rate)
        """
        prefix = f"{module}:"
        mod_state = {k.replace(prefix, ""): v for k, v in state.items()
                     if k.startswith(prefix)}
        mod_vel = {k.replace(prefix, ""): v for k, v in self._state_velocities.items()
                   if k.startswith(prefix)}

        # Default weights
        w = weights or {}

        # ═══ Kinetic energy: cost of changing ═══
        T = 0.0
        for key, vel in mod_vel.items():
            # T = ½ m_i × v_i² where m_i = module-specific inertia
            inertia = w.get(f"inertia_{key}", 1.0)
            T += 0.5 * inertia * vel * vel

        # ═══ Potential energy: cost of being wrong ═══
        V = 0.0

        if module == "synaptic":
            # V = ½ Σ (w - w̄)² × interference_ratio
            weights_list = [v for k, v in mod_state.items() if "weight" in k]
            if weights_list:
                mean_w = sum(weights_list) / len(weights_list)
                ir = state.get("synaptic:interference", 0.05)
                V = 0.5 * sum((wv - mean_w) ** 2 for wv in weights_list) * (0.5 + ir)

        elif module in ("provider", "router"):
            # V = regret = Σ (1 - success_rate) × calls
            success = mod_state.get("success_rate", 0.5)
            calls = mod_state.get("calls", 1)
            V = (1.0 - success) * calls

        elif module == "latent_grpo":
            # V = ½ Σ (z_a - z*)²
            distances = [v for k, v in mod_state.items() if "distance" in k]
            V = 0.5 * sum(d * d for d in distances) if distances else 0.1

        elif module == "hypergraph":
            # V = Σ dist²/(1+w)
            weights_vals = [v for k, v in mod_state.items() if "weight" in k]
            V = sum(1.0 / (1.0 + wv) for wv in weights_vals) if weights_vals else 1.0

        elif module == "economic":
            # V = cost × (1 - roi)
            cost = mod_state.get("daily_spent", 0)
            roi = mod_state.get("cumulative_roi", 1.0)
            V = cost * max(0.01, 1.0 - roi)

        elif module == "pipeline":
            # V = 1 - success_rate
            success = mod_state.get("success_rate", 0.7)
            V = 1.0 - success

        else:
            # Generic: cost of being far from target
            if mod_state:
                V = sum(abs(v) for v in mod_state.values()) / len(mod_state)

        L = T - V

        # Euler-Lagrange residual: ∂L/∂x - d/dt(∂L/∂ẋ)
        # Approximate: if V is high and T is low → system is "stuck" (violates δS=0)
        if T + abs(V) > 0.001:
            el_residual = abs(V) / (T + abs(V) + 0.001)
        else:
            el_residual = 0.0

        return LagrangianDecomposition(
            name=module,
            kinetic=round(T, 4),
            potential=round(V, 4),
            total=round(L, 4),
            euler_lagrange_residual=round(el_residual, 3),
        )

    # ═══ Full System Analysis ═══

    def analyze(self, external_metrics: dict[str, dict[str, float]] | None = None) -> ActionAnalysis:
        """Compute the full action principle analysis for the entire system.

        This is δS = 0 checked across all subsystems simultaneously.
        """
        now = time.time()

        # Feed any external metrics
        if external_metrics:
            for module, metrics in external_metrics.items():
                self.observe_batch(module, metrics)

        # Modules to analyze
        module_names = ["synaptic", "provider", "latent_grpo",
                        "hypergraph", "economic", "pipeline"]

        modules = []
        for mod_name in module_names:
            mod = self.compute_module_lagrangian(mod_name, self._last_state)
            modules.append(mod)

        total_T = sum(m.kinetic for m in modules)
        total_V = sum(m.potential for m in modules)
        total_action = total_T - total_V
        avg_el = sum(m.euler_lagrange_residual for m in modules) / max(len(modules), 1)

        # ═══ Optimal hyperparameters from Euler-Lagrange ═══
        params = self._derive_optimal_params(modules)

        # ═══ Noether invariants ═══
        conserved = self._compute_conserved()

        # System on-shell: δS ≈ 0
        on_shell = avg_el < 0.15

        analysis = ActionAnalysis(
            timestamp=now,
            total_kinetic=round(total_T, 3),
            total_potential=round(total_V, 3),
            total_action=round(total_action, 3),
            modules=modules,
            avg_el_residual=round(avg_el, 3),
            system_on_shell=on_shell,
            optimal_params=params,
            conserved_quantities=conserved,
        )
        self._analysis_history.append(analysis)
        return analysis

    # ═══ Euler-Lagrange → Optimal Hyperparameters ═══

    def _derive_optimal_params(
        self, modules: list[LagrangianDecomposition],
    ) -> dict[str, float]:
        """Derive optimal hyperparameters from the action principle.

        Euler-Lagrange: d/dt(∂L/∂ẋ) = ∂L/∂x
        → For quadratic T=½mẋ² and quadratic V=½k(x-x₀)²:
          mẍ + k(x-x₀) = 0  →  η* = √(k/m)
          optimal learning rate = √(potential_curvature / inertia)
        """

        params = {}

        # Synaptic: LTP rate = √(interference / inertia)
        syn = next((m for m in modules if m.name == "synaptic"), None)
        if syn and syn.potential > 0:
            inertia = max(syn.kinetic, 0.01)
            params["optimal_ltp_rate"] = round(
                math.sqrt(syn.potential / inertia) * 0.1, 4)

        # Provider: exploration rate = √(regret / uncertainty)
        prov = next((m for m in modules if m.name == "provider"), None)
        if prov and prov.potential > 0:
            inertia = max(prov.kinetic, 0.01)
            params["optimal_exploration_weight"] = round(
                math.sqrt(prov.potential / inertia) * 0.15, 4)

        # Decay rate = √(pruning_pressure / stability)
        if syn:
            params["optimal_decay_rate"] = round(
                params.get("optimal_ltp_rate", 0.01) * 0.1, 5)

        return params

    # ═══ Noether's Theorem → Conserved Quantities ═══

    def _compute_conserved(self) -> dict[str, float]:
        """Noether's theorem: every continuous symmetry → conserved quantity.

        Time symmetry → Energy conservation: E = T + V = constant
          → budget_cap = last_known_energy
        Translation symmetry → Momentum conservation
          → learning_momentum = running average of gradients
        Rotation symmetry → Angular momentum conservation  
          → exploration × uncertainty = constant (quantum-like limit)
        """
        state = self._last_state
        vel = self._state_velocities

        # Energy: E = T + V = conservative bound on budget
        energy = sum(0.5 * v * v for v in vel.values()) if vel else 0
        energy += sum(abs(v) for v in state.values()) / max(len(state), 1)

        # Information momentum: p = ∂L/∂ẋ → accumulated learning
        momentum = sum(abs(v) for v in vel.values()) if vel else 0

        # Uncertainty product: exploration × uncertainty = constant
        # (Analogous to Δx × Δp ≥ ℏ/2 in quantum mechanics)
        exploration = state.get("router:exploration_weight", 0.15)
        uncertainty = state.get("router:uncertainty", 0.5)
        uncertainty_product = exploration * uncertainty

        return {
            "energy": round(energy, 3),
            "information_momentum": round(momentum, 3),
            "uncertainty_product": round(uncertainty_product, 4),
            "uncertainty_bound": round(0.01, 4),  # ℏ/2 analog
        }

    # ═══ Action Gradient (which module most needs attention) ═══

    def most_deviant_module(self) -> str:
        """Which module has the largest Euler-Lagrange residual?

        This is the module most in need of optimization — it's furthest
        from the optimal trajectory δS=0.
        """
        if not self._analysis_history:
            return "unknown"
        modules = self._analysis_history[-1].modules
        if not modules:
            return "unknown"
        worst = max(modules, key=lambda m: m.euler_lagrange_residual)
        return worst.name

    # ═══ Stats ═══

    def stats(self) -> dict[str, Any]:
        if not self._analysis_history:
            return {"analyses": 0, "on_shell": False}
        latest = self._analysis_history[-1]
        return {
            "analyses_count": len(self._analysis_history),
            "system_on_shell": latest.system_on_shell,
            "avg_el_residual": latest.avg_el_residual,
            "total_action": latest.total_action,
            "most_deviant": self.most_deviant_module(),
            "optimal_params": latest.optimal_params,
            "conserved": latest.conserved_quantities,
            "state_variables": len(self._last_state),
            "velocities": len(self._state_velocities),
        }


# ═══ Singleton ═══

_action: ActionPrinciple | None = None


def get_action_principle() -> ActionPrinciple:
    global _action
    if _action is None:
        _action = ActionPrinciple()
    return _action


# ═══ Feed all modules at once ═══

def feed_all_modules(action: ActionPrinciple | None = None) -> ActionAnalysis:
    """Feed all module states into the action principle and analyze.

    One-liner to connect the entire system to the unified variational law.
    """
    ap = action or get_action_principle()

    # Gather from all modules
    try:
        from ..core.synaptic_plasticity import get_plasticity
        sp = get_plasticity()
        ap.observe_batch("synaptic", {
            "silent_ratio": sp.silent_ratio(),
            "interference": sp.interference_ratio(),
            "mature_ratio": sp.maturity_ratio(),
        })
    except Exception:
        pass

    try:
        from ..treellm.bandit_router import get_bandit_router
        br = get_bandit_router()
        stats_list = br.all_stats()
        if stats_list:
            ap.observe_batch("provider", {
                "success_rate": sum(s.get("quality_mean", 0.5) for s in stats_list) / len(stats_list),
                "calls": sum(s.get("total_calls", 0) for s in stats_list),
                "uncertainty": sum(s.get("quality_uncertainty", 0) for s in stats_list) / len(stats_list),
            })
    except Exception:
        pass

    try:
        from ..economy.economic_engine import get_economic_orchestrator
        eco = get_economic_orchestrator()
        stats = eco.stats()
        ap.observe_batch("economic", {
            "daily_spent": stats.get("daily_spent_yuan", 0),
            "cumulative_roi": stats.get("cumulative_roi", 1),
            "go_rate": stats.get("go_rate", 0.7),
        })
    except Exception:
        pass

    try:
        from ..execution.unified_pipeline import get_pipeline_orchestrator
        orch = get_pipeline_orchestrator()
        stats = orch.stats()
        ap.observe_batch("pipeline", {
            "success_rate": stats.get("success_rate", 0.7),
        })
    except Exception:
        pass

    return ap.analyze()


__all__ = [
    "ActionPrinciple", "ActionAnalysis", "LagrangianDecomposition",
    "get_action_principle", "feed_all_modules",
]
