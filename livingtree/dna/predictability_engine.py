"""Predictability Engine — fundamental limits of complex system prediction.

Based on Xu et al. (2026), Physics Reports 1166, 1-107:
  "Predictability of Complex Systems"
  107-page review of predictability across time series, network structures,
  and dynamical processes.

Three core concepts mapped to LivingTree:
  1. Time Series Predictability:
     - Permutation entropy → how predictable are LifeEngine stage outcomes?
     - Predictability horizon → when does forward planning degrade to random?
     - Lyapunov analog → do similar queries produce diverging outcomes?

  2. Network Structure Predictability:
     - Link prediction accuracy → how predictable are new hypergraph edges?
     - Structure determinism → how much of the graph is locked in?
     - Evolution entropy → is the knowledge graph stabilizing or chaotically growing?

  3. Dynamical Process Predictability:
     - Cascade predictability → can we predict impact propagation?
     - Process horizon → how many steps ahead can we predict retrieval quality?

Practical applications:
  - LifeEngine: "how confident should I be about stage N+1 given stage N?"
  - TreeLLM: "is this provider's performance predictable or random?"
  - EconomicOrchestrator: "can I predict tomorrow's cost based on today's?"
  - HypergraphStore: "which new edges are about to emerge?"
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Sequence

from loguru import logger


# ═══ Data Types ═══


@dataclass
class PredictabilityReport:
    """Complete predictability analysis for a time series."""
    name: str
    # Entropy measures
    permutation_entropy: float          # 0=highly predictable, 1=random
    sample_entropy: float               # Lower = more predictable
    # Predictability horizon
    horizon_steps: int                  # Steps ahead before baseline accuracy
    horizon_confidence: float            # Confidence in horizon estimate
    # Divergence
    lyapunov_analog: float              # 0=stable, high=chaotic trajectories
    # Summary
    predictability_score: float          # 0=chaotic, 1=fully deterministic
    recommendation: str = ""

    def summary(self) -> str:
        return (
            f"Predictability[{self.name}]: score={self.predictability_score:.2f} "
            f"horizon={self.horizon_steps} steps, "
            f"entropy={self.permutation_entropy:.2f}, "
            f"lyapunov={self.lyapunov_analog:.3f} "
            f"→ {self.recommendation}"
        )


@dataclass
class NetworkPredictability:
    """Predictability analysis for network/graph structures."""
    name: str
    link_prediction_accuracy: float     # How accurately can we predict new edges?
    structure_stability: float          # How stable is the current structure?
    growth_predictability: float        # Can we predict where the graph will grow?
    cascade_predictability: float       # Can we predict propagation paths?
    emergence_likelihood: float         # Likelihood of unexpected emergent structure
    overall_score: float


# ═══ Time Series Predictability ═══


class PredictabilityEngine:
    """Quantify predictability limits of LivingTree's complex subsystems.

    Based on Xu et al. (2026) — integrates entropy-based, Lyapunov-like,
    and horizon-based predictability measures for time series, networks,
    and dynamical processes.
    """

    def __init__(self, history_size: int = 200):
        self._history_size = history_size
        self._series: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=history_size))
        self._reports: dict[str, PredictabilityReport] = {}

    # ── Data Feeds ──

    def feed(self, name: str, value: float) -> None:
        """Feed a new data point into a time series."""
        self._series[name].append(value)

    def feed_batch(self, name: str, values: Sequence[float]) -> None:
        """Feed multiple values at once."""
        self._series[name].extend(values)

    # ═══ Permutation Entropy (Bandt & Pompe) ═══

    def permutation_entropy(
        self, name: str, order: int = 3, delay: int = 1,
    ) -> float:
        """Compute permutation entropy — key predictability measure.

        Bandt & Pompe (2002): maps time series to ordinal patterns.
        Low entropy = highly structured = predictable.
        High entropy = random patterns = unpredictable.

        H = -Σ p(π) × log₂ p(π)  normalized to [0,1]
        """
        values = list(self._series.get(name, []))
        n = len(values)
        if n < order * delay:
            return 1.0  # Not enough data → assume unpredictable

        # Extract ordinal patterns
        patterns: dict[tuple, int] = {}
        total = 0
        for i in range(n - (order - 1) * delay):
            # Get the embedded vector
            embedded = tuple(
                values[i + j * delay] for j in range(order))
            # Rank: sort indices by value
            sorted_indices = tuple(
                sorted(range(order), key=lambda k: embedded[k]))
            # Count pattern frequency
            patterns[sorted_indices] = patterns.get(sorted_indices, 0) + 1
            total += 1

        if total == 0:
            return 1.0

        # Shannon entropy
        entropy = 0.0
        for count in patterns.values():
            p = count / total
            entropy -= p * math.log2(p)

        # Normalize by maximum entropy log₂(order!)
        max_entropy = math.log2(math.factorial(order))
        return entropy / max_entropy if max_entropy > 0 else 1.0

    # ═══ Sample Entropy (Richman & Moorman) ═══

    def sample_entropy(
        self, name: str, m: int = 2, r_factor: float = 0.2,
    ) -> float:
        """Compute sample entropy — regularity measure.

        Lower SampEn = more regular = more predictable.
        Higher SampEn = more irregular = less predictable.

        SampEn = -ln(A/B) where A=matches at m+1, B=matches at m
        """
        values = list(self._series.get(name, []))
        n = len(values)
        if n < m + 2:
            return 2.0  # Insufficient data

        # Tolerance r = r_factor × std
        mean = sum(values) / n
        std = math.sqrt(sum((v - mean) ** 2 for v in values) / n)
        r = r_factor * std if std > 0 else 0.01

        # Count template matches at length m
        def count_matches(template_len: int) -> int:
            count = 0
            for i in range(n - template_len):
                for j in range(i + 1, n - template_len):
                    # Check if templates match within tolerance r
                    match = True
                    for k in range(template_len):
                        if abs(values[i + k] - values[j + k]) > r:
                            match = False
                            break
                    if match:
                        count += 1
            return count

        b = count_matches(m)
        a = count_matches(m + 1)

        if b == 0:
            return 2.0

        return -math.log(a / b) if a > 0 else 2.0

    # ═══ Predictability Horizon ═══

    def predictability_horizon(
        self, name: str, max_lag: int = 20, threshold: float = 0.5,
    ) -> tuple[int, float]:
        """Find the predictability horizon — steps ahead before accuracy
        drops below the threshold.

        Uses autocorrelation decay: when |autocorr(lag)| < threshold,
        the series is no longer predictable at that lag.

        Returns:
            (horizon_steps, confidence)
        """
        values = list(self._series.get(name, []))
        n = len(values)
        if n < max_lag * 2:
            return (0, 0.0)

        mean = sum(values) / n
        var = sum((v - mean) ** 2 for v in values) / n
        if var < 1e-9:
            return (max_lag, 1.0)  # Constant series = perfectly predictable

        # Autocorrelation for each lag
        horizon = 0
        for lag in range(1, min(max_lag + 1, n // 2)):
            n_pairs = n - lag
            if n_pairs < 5:
                break
            cov = sum(
                (values[i] - mean) * (values[i + lag] - mean)
                for i in range(n_pairs)) / n_pairs
            acf = cov / var
            if abs(acf) < threshold:
                horizon = lag
                break
            horizon = lag

        # Confidence: strong ACF at lag=1 = high confidence
        if n > 1:
            acf1 = sum(
                (values[i] - mean) * (values[i + 1] - mean)
                for i in range(n - 1)) / (n - 1) / var
        else:
            acf1 = 0.0
        confidence = min(1.0, abs(acf1) * 1.5)

        return (horizon, confidence)

    # ═══ Lyapunov Analog ═══

    def lyapunov_analog(self, name: str, max_lag: int = 10) -> float:
        """Approximate Lyapunov exponent — trajectory divergence rate.

        Measures how fast nearby trajectories diverge.
        λ > 0 = chaotic (small differences amplify)
        λ ≈ 0 = stable
        λ < 0 = convergent

        Approximation: mean pairwise distance growth over lags.
        """
        values = list(self._series.get(name, []))
        n = len(values)
        if n < 20:
            return 0.0

        # Normalize
        mean = sum(values) / n
        std = math.sqrt(sum((v - mean) ** 2 for v in values) / n)
        if std < 1e-9:
            return 0.0
        norm = [(v - mean) / std for v in values]

        # Compute divergence at each lag
        divergences = []
        for lag in range(1, min(max_lag + 1, n // 3)):
            diffs = []
            for i in range(n - lag):
                diffs.append(abs(norm[i + lag] - norm[i]))
            if diffs:
                divergences.append(sum(diffs) / len(diffs))

        if not divergences:
            return 0.0

        # Linear fit of log(divergence) vs lag
        # λ = slope of log(d_t) vs t
        x = list(range(1, len(divergences) + 1))
        y = [math.log(max(d, 1e-9)) for d in divergences]
        n_pts = len(x)
        mean_x = sum(x) / n_pts
        mean_y = sum(y) / n_pts
        cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        var_x = sum((xi - mean_x) ** 2 for xi in x)
        if var_x < 1e-9:
            return 0.0
        return cov / var_x  # Slope = Lyapunov analog

    # ═══ Full Report ═══

    def analyze(self, name: str) -> PredictabilityReport:
        """Generate a complete predictability report for a time series.

        Combines entropy, horizon, and Lyapunov measures into a single
        predictability score and actionable recommendation.
        """
        values = self._series.get(name, [])
        if len(values) < 20:
            report = PredictabilityReport(
                name=name, permutation_entropy=1.0, sample_entropy=2.0,
                horizon_steps=0, horizon_confidence=0.0,
                lyapunov_analog=0.0, predictability_score=0.0,
                recommendation="Insufficient data for analysis",
            )
        else:
            pe = self.permutation_entropy(name)
            se = self.sample_entropy(name)
            horizon, h_conf = self.predictability_horizon(name)
            lyap = self.lyapunov_analog(name, max_lag=10)

            # Composite score: 0=chaotic, 1=deterministic
            pe_score = 1.0 - pe
            se_score = max(0.0, 1.0 - se)
            lyap_score = max(0.0, 1.0 - min(lyap * 5, 1.0))
            horizon_score = min(1.0, horizon / 10.0)

            score = (0.35 * pe_score + 0.25 * se_score
                     + 0.25 * lyap_score + 0.15 * horizon_score)
            score = max(0.0, min(1.0, score))

            if score > 0.7:
                rec = "Highly predictable — safe to automate decisions"
            elif score > 0.4:
                rec = "Moderately predictable — use confidence thresholds"
            else:
                rec = "Low predictability — expect surprises, use fallbacks"

            report = PredictabilityReport(
                name=name, permutation_entropy=round(pe, 3),
                sample_entropy=round(se, 3),
                horizon_steps=horizon,
                horizon_confidence=round(h_conf, 3),
                lyapunov_analog=round(lyap, 4),
                predictability_score=round(score, 3),
                recommendation=rec,
            )

        self._reports[name] = report
        logger.info(report.summary())
        return report

    # ═══ Network Structure Predictability ═══

    def network_predictability(
        self, hypergraph_store=None, knowledge_graph=None,
    ) -> NetworkPredictability:
        """Analyze how predictable the knowledge graph structure is.

        Based on Xu et al. (2026) §Network Structure Predictability.
        """
        if not hypergraph_store:
            return NetworkPredictability(
                name="empty", link_prediction_accuracy=0.0,
                structure_stability=1.0, growth_predictability=0.0,
                cascade_predictability=0.0, emergence_likelihood=1.0,
                overall_score=0.0)

        hg = hypergraph_store
        n_e = len(hg._entities)
        n_h = len(hg._hyperedges)
        if n_e < 10:
            return NetworkPredictability(
                name="graph", link_prediction_accuracy=0.0,
                structure_stability=1.0, growth_predictability=0.0,
                cascade_predictability=0.0, emergence_likelihood=1.0,
                overall_score=0.0)

        # Link prediction accuracy: based on node degree distribution
        degrees = [hg._graph.degree(eid) for eid in hg._entities
                   if eid in hg._graph]
        avg_deg = sum(degrees) / len(degrees) if degrees else 0
        max_possible = n_e * (n_e - 1) / 2
        density = hg._graph.number_of_edges() / max(max_possible, 1)

        # Structure stability: lower variance in degree = more stable
        if degrees and avg_deg > 0:
            var_deg = sum((d - avg_deg) ** 2 for d in degrees) / len(degrees)
            cv_deg = math.sqrt(var_deg) / avg_deg  # Coefficient of variation
            stability = max(0.0, 1.0 - min(cv_deg, 2.0) / 2.0)
        else:
            stability = 1.0

        # Growth predictability: how regular is the rate of new edges?
        growth = 1.0 - density  # Sparse → more room to grow, but less predictable

        # Cascade predictability: based on average path length
        try:
            import networkx as nx
            if nx.is_connected(hg._graph):
                avg_path = nx.average_shortest_path_length(hg._graph)
                cascade = 1.0 / max(avg_path, 1.0)
            else:
                cascade = 0.3
        except Exception:
            cascade = 0.5

        # Emergence likelihood: how likely are unexpected structures?
        emergence = max(0.0, 1.0 - stability)

        overall = (0.3 * stability + 0.3 * growth
                   + 0.2 * cascade + 0.2 * (1.0 - emergence))

        return NetworkPredictability(
            name="hypergraph",
            link_prediction_accuracy=round(growth, 3),
            structure_stability=round(stability, 3),
            growth_predictability=round(growth, 3),
            cascade_predictability=round(cascade, 3),
            emergence_likelihood=round(emergence, 3),
            overall_score=round(overall, 3),
        )

    # ═══ Dynamical Process Predictability ═══

    def process_predictability(
        self, process_name: str, quality_series: Sequence[float],
    ) -> float:
        """How predictable is a dynamical process (e.g. retrieval quality)?"""
        self.feed_batch(process_name, quality_series)
        report = self.analyze(process_name)
        return report.predictability_score

    # ═══ SDE Model Fitting (Bosso et al. 2025) ═══

    def fit_sde_model(
        self, name: str, dt: float = 1.0,
    ) -> dict[str, Any]:
        r"""Fit a simplified SDE model to a time series and estimate drift/diffusion.

        Bosso et al. (2025) framework: from noisy data {X_t}, estimate both
        the deterministic drift f(X) and stochastic diffusion g(X) in:

            dX_t = f(X_t) dt + g(X_t) dW_t

        This provides a COMPLETE model of the system's dynamics — not just
        "how predictable" but "HOW it evolves" and "WHERE the noise comes from."

        Method (Euler-Maruyama discretization):
            1. Compute increments ΔX_i = X_{i+1} - X_i at each step
            2. Drift estimate: μ(x) = E[ΔX | X ≈ x] / dt  (conditional mean of increments)
            3. Diffusion estimate: σ²(x) = Var[ΔX | X ≈ x] / dt  (conditional variance)

        Returns:
            dict with:
                drift_values: list of μ(x_i) estimates
                diffusion_values: list of σ(x_i) estimates
                drift_rms: RMS drift magnitude
                diffusion_rms: RMS diffusion magnitude
                signal_to_noise: |drift| / diffusion ratio (higher = more deterministic)
                noise_type: "additive" (constant σ), "multiplicative" (σ ∝ x), or "mixed"
                prediction_interval_95: (lower, upper) 95% confidence bound for next step
        """
        values = list(self._series.get(name, []))
        n = len(values)
        if n < 20:
            return {
                "error": "insufficient data (need ≥20 points)",
                "drift_values": [], "diffusion_values": [],
                "drift_rms": 0.0, "diffusion_rms": 0.0,
                "signal_to_noise": 0.0, "noise_type": "unknown",
                "prediction_interval_95": (0.0, 0.0),
            }

        # Step 1: Compute increments
        increments = [values[i + 1] - values[i] for i in range(n - 1)]
        m = len(increments)

        # Step 2: Bin the state space for conditional statistics
        # Use equal-frequency binning (~sqrt(N) bins)
        n_bins = max(3, int(math.sqrt(m)))
        sorted_vals = sorted(values[:-1])  # X_t for each increment
        bin_size = m // n_bins

        drift_estimates: list[float] = []
        diffusion_estimates: list[float] = []
        x_midpoints: list[float] = []

        for b in range(n_bins):
            start_idx = b * bin_size
            end_idx = start_idx + bin_size if b < n_bins - 1 else m
            # Get the values in this bin (using sorted order for bin boundaries)
            bin_mask = sorted_vals[start_idx:end_idx]
            if not bin_mask:
                continue
            bin_min = bin_mask[0]
            bin_max = bin_mask[-1]

            # Find increments whose X_t falls in this bin
            bin_incs = [
                increments[i] for i in range(m)
                if bin_min <= values[i] <= bin_max
            ]
            bin_xs = [
                values[i] for i in range(m)
                if bin_min <= values[i] <= bin_max
            ]
            if len(bin_incs) < 3:
                continue

            # Conditional mean → drift μ(x)
            mu = sum(bin_incs) / len(bin_incs) / dt
            # Conditional variance → diffusion σ²(x)
            var = sum((inc - sum(bin_incs) / len(bin_incs)) ** 2
                      for inc in bin_incs) / len(bin_incs) / dt
            sigma = math.sqrt(max(0.0, var))

            x_mid = sum(bin_xs) / len(bin_xs)
            drift_estimates.append(mu)
            diffusion_estimates.append(sigma)
            x_midpoints.append(x_mid)

        if not drift_estimates:
            return {
                "error": "binning failed — data range too narrow",
                "drift_values": [], "diffusion_values": [],
                "drift_rms": 0.0, "diffusion_rms": 0.0,
                "signal_to_noise": 0.0, "noise_type": "unknown",
                "prediction_interval_95": (0.0, 0.0),
            }

        # Step 3: Compute summary statistics
        drift_rms = math.sqrt(
            sum(d ** 2 for d in drift_estimates) / len(drift_estimates))
        diffusion_rms = math.sqrt(
            sum(s ** 2 for s in diffusion_estimates) / len(diffusion_estimates))

        signal_to_noise = (
            drift_rms / diffusion_rms if diffusion_rms > 1e-9 else float('inf'))

        # Noise type classification
        # Check if σ(x) is constant (additive) or scales with x (multiplicative)
        if len(x_midpoints) >= 3 and len(diffusion_estimates) >= 3:
            # Linear regression: σ ~ α·x + β
            n_pts = len(x_midpoints)
            mean_x = sum(x_midpoints) / n_pts
            mean_s = sum(diffusion_estimates) / n_pts
            cov_xs = sum(
                (x - mean_x) * (s - mean_s)
                for x, s in zip(x_midpoints, diffusion_estimates)) / n_pts
            var_x = sum((x - mean_x) ** 2 for x in x_midpoints) / n_pts
            if var_x > 1e-9:
                slope = cov_xs / var_x
                # If σ scales with x → multiplicative noise (intrinsic)
                # If σ is constant → additive noise (extrinsic)
                if abs(slope) > 0.1 * diffusion_rms:
                    noise_type = "multiplicative"  # Intrinsic — noise from parameters
                else:
                    noise_type = "additive"  # Extrinsic — measurement noise
            else:
                noise_type = "additive"
        else:
            noise_type = "additive"

        # Step 4: Prediction interval (95%)
        # Next-step prediction: X_{t+1} = X_t + μ(X_t)·dt + σ(X_t)·√dt·Z
        # 95% CI: X_t + μ·dt ± 1.96·σ·√dt
        if drift_estimates and diffusion_estimates and dt > 0:
            last_x = values[-1]
            # Use the drift/diffusion estimate closest to the current state
            best_idx = 0
            best_dist = float('inf')
            for i, xm in enumerate(x_midpoints):
                d = abs(xm - last_x)
                if d < best_dist:
                    best_dist = d
                    best_idx = i
            mu_now = drift_estimates[best_idx]
            sigma_now = diffusion_estimates[best_idx]
            pred_mean = last_x + mu_now * dt
            half_width = 1.96 * sigma_now * math.sqrt(dt)
            prediction_interval = (pred_mean - half_width, pred_mean + half_width)
        else:
            prediction_interval = (values[-1], values[-1])

        return {
            "drift_values": [round(d, 6) for d in drift_estimates],
            "diffusion_values": [round(s, 6) for s in diffusion_estimates],
            "x_midpoints": [round(x, 6) for x in x_midpoints],
            "drift_rms": round(drift_rms, 6),
            "diffusion_rms": round(diffusion_rms, 6),
            "signal_to_noise": round(signal_to_noise, 3) if signal_to_noise != float('inf') else "inf",
            "noise_type": noise_type,
            "prediction_interval_95": tuple(round(v, 6) for v in prediction_interval),
            "sample_size": n,
            "n_bins": n_bins,
        }

    # ═══ Stats ═══

    def stats(self) -> dict[str, Any]:
        return {
            "series_tracked": len(self._series),
            "reports_generated": len(self._reports),
            "avg_predictability": round(
                sum(r.predictability_score for r in self._reports.values())
                / max(len(self._reports), 1), 3),
            "most_predictable": max(
                self._reports.values(),
                key=lambda r: r.predictability_score,
                default=PredictabilityReport(name="none", permutation_entropy=1.0,
                    sample_entropy=0, horizon_steps=0, horizon_confidence=0,
                    lyapunov_analog=0, predictability_score=0)).name,
            "least_predictable": min(
                self._reports.values(),
                key=lambda r: r.predictability_score,
                default=PredictabilityReport(name="none", permutation_entropy=1.0,
                    sample_entropy=0, horizon_steps=0, horizon_confidence=0,
                    lyapunov_analog=0, predictability_score=1)).name,
        }


# ═══ LivingTree Integration Helpers ═══

def feed_life_engine_metrics(
    engine: "PredictabilityEngine", life_engine=None,
) -> None:
    """Feed LifeEngine stage outcomes into the predictability engine."""
    if not life_engine or not life_engine.stages:
        return
    for stage in life_engine.stages:
        engine.feed(f"stage_{stage.stage}_duration", stage.duration_ms)
        status_val = 1.0 if stage.status == "completed" else 0.0
        engine.feed(f"stage_{stage.stage}_success", status_val)


def feed_economic_metrics(
    engine: "PredictabilityEngine", eco_orch=None,
) -> None:
    """Feed economic metrics for predictability analysis."""
    if not eco_orch:
        return
    stats = eco_orch.stats()
    engine.feed("economic_roi", stats.get("cumulative_roi", 0))
    engine.feed("economic_spent", stats.get("daily_spent_yuan", 0))
    engine.feed("economic_go_rate", stats.get("go_rate", 0))


def feed_provider_metrics(
    engine: "PredictabilityEngine", election_engine=None,
) -> None:
    """Feed TreeLLM provider performance metrics."""
    if not election_engine:
        return
    stats = election_engine.get_all_stats()
    for name, s in stats.items():
        engine.feed(f"provider_{name}_success_rate", s.get("success_rate", 0))
        engine.feed(f"provider_{name}_latency", s.get("avg_latency_ms", 0))


# ═══ Singleton ═══

_predictability: PredictabilityEngine | None = None


def get_predictability() -> PredictabilityEngine:
    global _predictability
    if _predictability is None:
        _predictability = PredictabilityEngine()
    return _predictability


__all__ = [
    "PredictabilityEngine", "PredictabilityReport",
    "NetworkPredictability",
    "feed_life_engine_metrics", "feed_economic_metrics",
    "feed_provider_metrics", "get_predictability",
]


# ═══ Linguistic Horizon (Portsmouth paper inspired) ═══

@dataclass
class HorizonEstimate:
    """Time-decay confidence for language/knowledge predictions.

    Maps the Portsmouth paper's concept of "linguistic forecast horizon":
    - Like weather: 3-day forecast is reliable, 14-day is not
    - Each generation of learners introduces new variables → entropy grows
    - Exponential decay: confidence(t) = confidence_0 * e^(-t / horizon)
    """
    concept: str
    confidence_now: float                     # current prediction confidence (0-1)
    horizon_steps: int                        # steps before confidence drops to 0.37
    decay_rate: float                         # lambda in e^(-lambda * t)
    generation_noise: float                   # entropy introduced per "generation" of change
    forecast: list[float] = field(default_factory=list)  # confidence at t=1,2,3,5,10,20

    def confidence_at(self, steps: int) -> float:
        """Confidence at given steps into the future."""
        import math
        return max(0.0, self.confidence_now * math.exp(-self.decay_rate * steps))

    def reliable_steps(self, threshold: float = 0.6) -> int:
        """How many steps ahead can we predict with >threshold confidence?"""
        import math
        if self.decay_rate <= 0:
            return self.horizon_steps
        return int(math.log(threshold / self.confidence_now) / -self.decay_rate)


class LinguisticHorizonEngine:
    """Time-decay confidence calculator for knowledge diffusion predictions.

    Portsmouth paper insight: linguistic predictions degrade exponentially
    with forecast horizon, analogous to weather forecasting. Each
    "generation" of knowledge propagation introduces entropy.
    """

    def __init__(self, noise_per_generation: float = 0.15):
        self._noise = noise_per_generation
        self._estimates: dict[str, HorizonEstimate] = {}

    def estimate(self, concept: str, confidence: float, horizon: int = 10) -> HorizonEstimate:
        """Calculate confidence decay curve for a concept.

        Args:
            concept: Knowledge concept name
            confidence: Current prediction confidence (0-1)
            horizon: Baseline horizon (steps to e^-1 decay)
        """
        import math
        decay = 1.0 / max(1, horizon) if horizon > 0 else 0.1
        gen_noise = self._noise * (1.0 - confidence)
        effective_decay = decay + gen_noise

        forecast = []
        for t in [1, 2, 3, 5, 10, 20]:
            c = confidence * math.exp(-effective_decay * t)
            forecast.append(round(c, 4))

        est = HorizonEstimate(
            concept=concept,
            confidence_now=confidence,
            horizon_steps=horizon,
            decay_rate=round(effective_decay, 4),
            generation_noise=round(gen_noise, 4),
            forecast=forecast,
        )
        self._estimates[concept] = est
        return est

    def compare_concepts(self, *concepts: str) -> list[dict]:
        """Compare forecast horizons across multiple concepts."""
        result = []
        for c in concepts:
            est = self._estimates.get(c)
            if est:
                result.append({
                    "concept": c,
                    "confidence": est.confidence_now,
                    "reliable_steps": est.reliable_steps(),
                    "decay_rate": est.decay_rate,
                    "forecast_3steps": est.forecast[2] if len(est.forecast) > 2 else 0,
                    "forecast_10steps": est.forecast[4] if len(est.forecast) > 4 else 0,
                    "noise": est.generation_noise,
                })
        result.sort(key=lambda x: -x["reliable_steps"])
        return result

    def stats(self) -> dict:
        return {
            "concepts_tracked": len(self._estimates),
            "noise_per_generation": self._noise,
            "comparisons": self.compare_concepts(*list(self._estimates.keys())[:6]),
        }


_horizon_engine: LinguisticHorizonEngine | None = None


def get_horizon_engine() -> LinguisticHorizonEngine:
    global _horizon_engine
    if _horizon_engine is None:
        _horizon_engine = LinguisticHorizonEngine()
    return _horizon_engine

_predictability_engine: PredictabilityEngine | None = None


def get_predictability_engine(history_size: int = 200) -> PredictabilityEngine:
    """Get or create the singleton PredictabilityEngine instance."""
    global _predictability_engine
    if _predictability_engine is None:
        _predictability_engine = PredictabilityEngine(history_size=history_size)
    return _predictability_engine
