"""Ising Model — binary spin Hamiltonian + Metropolis-Hastings for discrete optimization.

Washington University Discovery Machine (Nature Communications, 2026):
  Higher-order Ising machine with ON-OFF neurons.
  - Binary spin states {-1, +1} for providers, strategies, pipeline stages
  - Hamiltonian: H = -sum J_ij * s_i * s_j - sum h_i * s_i
  - Metropolis-Hastings acceptance: P(accept flip) = min(1, exp(-dH / T))
  - Ground state search = global optimum finding

LivingTree applications:
  - Provider selection: each provider = one spin, couplings = compatibility
  - Strategy selection: each strategy = one spin, external field = task fitness
  - Organ configuration: each organ = one spin, couplings = cross-organ synergies
  - Pipeline stage ordering: each stage = one spin, couplings = dependency strength

Usage:
    from livingtree.optimization.ising_model import IsingModel, IsingOptimizer

    model = IsingModel(num_spins=12)
    model.set_external_field(0, 0.8)     # provider 0 highly favored
    model.set_coupling(0, 1, -0.5)       # providers 0 and 1 conflict (anti-ferromagnetic)

    optimizer = IsingOptimizer(model)
    result = optimizer.find_ground_state(temperature=1.0, max_steps=500)
    print(result.spin_config)            # optimal configuration
    print(result.energy)                 # minimum energy
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ═══════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════

@dataclass
class IsingConfig:
    """An Ising model configuration (spin assignment)."""
    spins: list[int]  # {-1, +1} per spin
    energy: float = float('inf')
    magnetization: float = 0.0  # average spin = order parameter


@dataclass
class IsingOptimizationResult:
    """Full optimization result with convergence data."""
    spin_config: list[int]
    energy: float
    steps_taken: int
    converged: bool
    energy_trace: list[float] = field(default_factory=list)
    magnetization_trace: list[float] = field(default_factory=list)
    phase_transitions: list[dict[str, Any]] = field(default_factory=list)
    acceptance_ratio: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Ising Model
# ═══════════════════════════════════════════════════════════════════

class IsingModel:
    """N-spin Ising model with external fields and pairwise couplings.

    H(s) = -sum_i h_i * s_i - sum_{i<j} J_ij * s_i * s_j

    where s_i ∈ {-1, +1}, h_i is external field on spin i,
    J_ij is coupling between spins i and j.

    Physical interpretation:
      - h_i > 0: spin i prefers +1 (ON neuron)
      - h_i < 0: spin i prefers -1 (OFF neuron)
      - J_ij > 0: ferromagnetic — spins prefer to align (cooperation)
      - J_ij < 0: anti-ferromagnetic — spins prefer to oppose (competition)

    LivingTree mappings:
      - Providers as spins: J_ij encodes pairwise synergy/conflict
      - Strategies as spins: h_i encodes task-specific fitness
      - Pipeline stages as spins: J_ij encodes dependency strength
    """

    def __init__(self, num_spins: int = 12, random_field: float = 0.3):
        self.num_spins = num_spins
        self._h: list[float] = [
            random.uniform(-random_field, random_field)
            for _ in range(num_spins)
        ]
        self._J: list[list[float]] = [
            [0.0] * num_spins for _ in range(num_spins)
        ]
        self._spin_labels: dict[int, str] = {}
        self._config_count: int = 0

    # ── Configuration ──

    def set_external_field(self, spin_index: int, field: float) -> None:
        """Set external field h_i on spin i.

        This biases individual spins toward +1 or -1.
        In LivingTree: field = provider quality or strategy fitness.
        """
        if 0 <= spin_index < self.num_spins:
            self._h[spin_index] = field

    def set_coupling(self, i: int, j: int, coupling: float) -> None:
        """Set coupling J_ij between spins i and j (symmetric).

        This models pairwise interactions.
        In LivingTree: coupling = provider compatibility or strategy synergy.
        """
        if 0 <= i < self.num_spins and 0 <= j < self.num_spins and i != j:
            self._J[i][j] = coupling
            self._J[j][i] = coupling

    def set_label(self, spin_index: int, label: str) -> None:
        """Assign a semantic label to a spin (e.g., provider name)."""
        self._spin_labels[spin_index] = label

    def get_label(self, spin_index: int) -> str:
        return self._spin_labels.get(spin_index, f"spin_{spin_index}")

    def configure_from_scores(self, scores: dict[str, float]) -> None:
        """Configure external fields from named scores.

        Usage:
            model.configure_from_scores({
                "deepseek": 0.8, "longcat": 0.5, "zhipu": 0.3
            })
        Sets field = tanh(score) and assigns labels.
        """
        spin_index = 0
        for name, score in sorted(scores.items(), key=lambda x: -x[1]):
            if spin_index >= self.num_spins:
                break
            self._h[spin_index] = math.tanh(score)
            self._spin_labels[spin_index] = name
            spin_index += 1

    def configure_from_affinity_matrix(self, affinity: dict[tuple[str, str], float]) -> None:
        """Configure couplings from pairwise affinity scores.

        Usage:
            model.configure_from_affinity_matrix({
                ("deepseek", "longcat"): 0.5,  # positive = synergize
                ("deepseek", "zhipu"): -0.3    # negative = compete
            })
        """
        label_to_idx = {v: k for k, v in self._spin_labels.items()}
        for (a, b), affinity_val in affinity.items():
            i = label_to_idx.get(a)
            j = label_to_idx.get(b)
            if i is not None and j is not None:
                self._J[i][j] = affinity_val
                self._J[j][i] = affinity_val

    # ── Energy Computation ──

    def energy(self, spins: list[int]) -> float:
        """H(s) = -sum h_i*s_i - sum_{i<j} J_ij*s_i*s_j."""
        E = 0.0
        for i in range(self.num_spins):
            E -= self._h[i] * spins[i]
        for i in range(self.num_spins):
            for j in range(i + 1, self.num_spins):
                E -= self._J[i][j] * spins[i] * spins[j]
        return E

    def local_field(self, spins: list[int], i: int) -> float:
        """Effective field on spin i: h_i + sum_j J_ij * s_j."""
        field = self._h[i]
        for j in range(self.num_spins):
            if j != i:
                field += self._J[i][j] * spins[j]
        return field

    def energy_delta(self, spins: list[int], i: int) -> float:
        """Energy change from flipping spin i: dE = 2 * s_i * local_field_i."""
        return 2.0 * spins[i] * self.local_field(spins, i)

    def magnetization(self, spins: list[int]) -> float:
        """Order parameter: m = (1/N) * sum s_i ∈ [-1, +1]."""
        return sum(spins) / self.num_spins

    # ── Sampling ──

    def random_config(self) -> list[int]:
        """Generate random spin configuration."""
        return [1 if random.random() > 0.5 else -1 for _ in range(self.num_spins)]

    def all_up(self) -> list[int]:
        """All +1 configuration (ferromagnetic ground state candidate)."""
        return [1] * self.num_spins

    def all_down(self) -> list[int]:
        """All -1 configuration."""
        return [-1] * self.num_spins

    def flip_spin(self, spins: list[int], i: int) -> list[int]:
        """Return new config with spin i flipped."""
        new_spins = list(spins)
        new_spins[i] = -new_spins[i]
        return new_spins

    # ── Phase Detection ──

    def detect_phase(self, spins: list[int], T: float) -> str:
        """Classify the Ising phase based on magnetization and temperature.

        Returns:
            "ferromagnetic"   — |m| ≈ 1, spins aligned (ordered)
            "paramagnetic"    — m ≈ 0, high T, random (disordered)
            "spin_glass"      — intermediate T, frozen disorder
            "critical"        — near phase transition boundary
        """
        m = abs(self.magnetization(spins))
        tc_estimate = self.num_spins * 0.3  # rough critical temp

        if T < 0.1 * tc_estimate and m > 0.8:
            return "ferromagnetic"
        elif T > tc_estimate and m < 0.3:
            return "paramagnetic"
        elif T < 0.5 * tc_estimate and m < 0.5:
            return "spin_glass"
        return "critical"


# ═══════════════════════════════════════════════════════════════════
# Ising Optimizer — Metropolis-Hastings Monte Carlo
# ═══════════════════════════════════════════════════════════════════

class IsingOptimizer:
    """Metropolis-Hastings Monte Carlo optimizer for Ising ground state search.

    Simulated annealing with Fowler-Nordheim tunneling:
      1. Start at high T → explore config space randomly (paramagnetic phase)
      2. Cool T(t) = T0 / log(e + t) → gradually settle (critical → ordered)
      3. At low T, Metropolis acceptance rejects most uphill moves
      4. Fowler-Nordheim tunneling escapes local minima when stuck

    Usage:
        model = IsingModel(num_spins=8)
        optimizer = IsingOptimizer(model)
        result = optimizer.find_ground_state(temperature=1.0, max_steps=1000)
    """

    def __init__(
        self,
        model: IsingModel,
        enable_tunneling: bool = True,
        tunnel_threshold: int = 30,
    ):
        self.model = model
        self._enable_tunneling = enable_tunneling
        self._tunnel_threshold = tunnel_threshold

    def metropolis_step(self, spins: list[int], T: float) -> tuple[list[int], bool, float]:
        """Single Metropolis-Hastings Monte Carlo step.

        1. Randomly select a spin
        2. Compute energy change dE if flipped
        3. Accept with P = min(1, exp(-dE / T)) (Metropolis criterion)

        Returns: (new_spins, accepted, dE)
        """
        i = random.randrange(self.model.num_spins)
        dE = self.model.energy_delta(spins, i)

        accept = False
        if dE <= 0:
            accept = True
        elif T > 0:
            p_accept = math.exp(-dE / T)
            accept = random.random() < p_accept

        new_spins = self.model.flip_spin(spins, i) if accept else list(spins)
        return new_spins, accept, dE

    def find_ground_state(
        self,
        temperature: float = 1.0,
        min_temperature: float = 0.001,
        max_steps: int = 1000,
        log_interval: int = 100,
    ) -> IsingOptimizationResult:
        """Run simulated annealing to find the Ising ground state.

        Returns IsingOptimizationResult with optimal configuration.
        """
        spins = self.model.random_config()
        best_spins = list(spins)
        best_energy = self.model.energy(spins)

        energy_trace: list[float] = []
        mag_trace: list[float] = []
        phase_transitions: list[dict[str, Any]] = []
        accept_count = 0
        stagnation = 0
        last_phase = ""

        for step in range(1, max_steps + 1):
            T = temperature / math.log(math.e + step)
            T = max(T, min_temperature)

            spins, accepted, dE = self.metropolis_step(spins, T)
            if accepted:
                accept_count += 1

            current_E = self.model.energy(spins)
            energy_trace.append(current_E)
            mag_trace.append(self.model.magnetization(spins))

            if current_E < best_energy:
                best_energy = current_E
                best_spins = list(spins)
                stagnation = 0
            else:
                stagnation += 1

            # Phase transition detection
            phase = self.model.detect_phase(spins, T)
            if phase != last_phase:
                phase_transitions.append({
                    "step": step, "from": last_phase, "to": phase,
                    "temperature": T, "energy": current_E,
                })
                last_phase = phase

            # Fowler-Nordheim tunneling escape
            if self._enable_tunneling and stagnation >= self._tunnel_threshold:
                tunnel_spins = self.model.random_config()
                tunnel_E = self.model.energy(tunnel_spins)
                dE_tunnel = tunnel_E - current_E
                if dE_tunnel <= 0 or (T > min_temperature and random.random() < math.exp(-dE_tunnel / (T * 0.5))):
                    spins = tunnel_spins
                    stagnation = 0

            if step % log_interval == 0:
                logger.debug(
                    f"Ising step {step}: T={T:.4f}, E={current_E:.4f}, "
                    f"best_E={best_energy:.4f}, m={self.model.magnetization(spins):.3f}, "
                    f"phase={phase}"
                )

        acceptance_ratio = accept_count / max_steps if max_steps > 0 else 0.0

        result = IsingOptimizationResult(
            spin_config=best_spins,
            energy=best_energy,
            steps_taken=max_steps,
            converged=stagnation >= self._tunnel_threshold * 2,
            energy_trace=energy_trace,
            magnetization_trace=mag_trace,
            phase_transitions=phase_transitions,
            acceptance_ratio=acceptance_ratio,
        )
        return result

    def config_to_labels(self, spins: list[int]) -> dict[str, int]:
        """Map spin config back to named labels: {name: +1/-1}."""
        return {
            self.model.get_label(i): spins[i]
            for i in range(min(len(spins), self.model.num_spins))
        }

    def config_to_active_set(self, spins: list[int]) -> list[str]:
        """Return labels of ON neurons (spin = +1) only."""
        return [
            self.model.get_label(i)
            for i in range(min(len(spins), self.model.num_spins))
            if spins[i] == 1
        ]

    def compute_spin_correlations(self, config: list[int]) -> dict[tuple[int, int], float]:
        """Correlation matrix: <s_i * s_j> for the configuration."""
        corr = {}
        n = min(len(config), self.model.num_spins)
        for i in range(n):
            for j in range(i + 1, n):
                corr[(i, j)] = config[i] * config[j]
        return corr


# ═══════════════════════════════════════════════════════════════════
# LivingTree-Specific Ising Builders
# ═══════════════════════════════════════════════════════════════════

def build_provider_ising(provider_scores: dict[str, float]) -> tuple[IsingModel, IsingOptimizer]:
    """Build Ising model for provider selection optimization.

    Each provider = one spin. High score → ON (+1). Competition → anti-ferromagnetic coupling.

    Usage:
        model, optimizer = build_provider_ising({
            "deepseek": 0.85, "longcat": 0.72, "zhipu": 0.50
        })
    """
    providers = list(provider_scores.keys())
    model = IsingModel(num_spins=max(len(providers), 4))
    for i, name in enumerate(providers):
        model.set_label(i, name)
        model.set_external_field(i, provider_scores[name])
    # Anti-ferromagnetic coupling between similar-capability providers
    for i in range(len(providers)):
        for j in range(i + 1, len(providers)):
            diff = abs(provider_scores[providers[i]] - provider_scores[providers[j]])
            model.set_coupling(i, j, -0.3 + diff * 0.5)  # competition if similar
    optimizer = IsingOptimizer(model, enable_tunneling=True, tunnel_threshold=20)
    return model, optimizer


def build_strategy_ising(strategy_scores: dict[str, float]) -> tuple[IsingModel, IsingOptimizer]:
    """Build Ising model for strategy selection optimization.

    Each strategy = one spin. High fitness → ON. Complementary strategies → ferromagnetic.

    Usage:
        model, optimizer = build_strategy_ising({
            "enumeration": 0.8, "counterfactual": 0.6, "self_challenge": 0.4
        })
    """
    strategies = list(strategy_scores.keys())
    model = IsingModel(num_spins=max(len(strategies), 4))
    for i, name in enumerate(strategies):
        model.set_label(i, name)
        model.set_external_field(i, strategy_scores[name])
    # Ferromagnetic coupling between complementary strategies
    for i in range(len(strategies)):
        for j in range(i + 1, len(strategies)):
            avg = (strategy_scores[strategies[i]] + strategy_scores[strategies[j]]) / 2
            model.set_coupling(i, j, 0.2 * avg)  # synergy
    optimizer = IsingOptimizer(model, enable_tunneling=True, tunnel_threshold=15)
    return model, optimizer
