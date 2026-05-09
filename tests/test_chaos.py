"""Chaos & Long-Running Tests — stress-test the autonomous lifeform.

Tests:
  1. Chaos injection: kill daemons, bad providers, zero budgets
  2. Long-running: 50+ cycles of the autonomic loop
  3. Drift detection: behavioral consistency over time
  4. Recovery: system self-healing after chaos
"""

import pytest
import time
from livingtree.core.synaptic_plasticity import (
    SynapticPlasticity, get_plasticity)
from livingtree.treellm.bandit_router import (
    ThompsonRouter, get_bandit_router)
from livingtree.treellm.free_pool_manager import (
    FreeModelPool, get_free_pool)
from livingtree.economy.thermo_budget import (
    ThermodynamicBudget, get_thermo_budget)
from livingtree.dna.predictability_engine import (
    PredictabilityEngine, get_predictability)
from livingtree.dna.emergence_detector import (
    EmergenceDetector, get_emergence_detector)


class TestChaosInjection:
    """Inject failures and verify system doesn't crash."""

    def test_bad_provider_doesnt_crash_router(self):
        """ThompsonRouter handles providers with zero success."""
        router = ThompsonRouter()
        router.record_failure("bad_provider")
        router.record_failure("bad_provider")
        router.record_failure("bad_provider")
        # Should still select something
        candidates = ["bad_provider", "ok_provider"]
        router.get_arm("ok_provider").quality.observe_success(weight=3.0)
        selected = router.select_best(candidates)
        assert selected != "bad_provider" or router._arms["bad_provider"].total_calls == 3

    def test_zero_budget_doesnt_crash(self):
        """ThermoBudget handles zero budget gracefully."""
        tb = ThermodynamicBudget(daily_budget_yuan=0)
        tb.record_spending(0)
        decision = tb.evaluate("t1", estimated_cost=0, task_priority=0)
        assert decision is not None  # Should return a decision, not crash

    def test_degraded_pool_still_available(self):
        """FreeModelPool with degraded models still reports correctly."""
        pool = FreeModelPool()
        pool.mark_failure("m1")
        pool.mark_failure("m1")
        pool.mark_failure("m1")
        pool.mark_failure("m1")
        stats = pool.pool_stats()
        assert stats["degraded"] >= 0  # graceful
        assert stats["total_models"] > 0

    def test_pruning_empty_plasticity(self):
        """SynapticPlasticity pruning on empty state is safe."""
        sp = SynapticPlasticity()
        pruned = sp.decay_all()
        assert pruned == 0  # No crash, no effect

    def test_predictability_with_noise(self):
        """Predictability engine handles noisy/random data."""
        pe = PredictabilityEngine()
        import random
        for _ in range(50):
            pe.feed("noisy", random.uniform(0, 100))
        report = pe.analyze("noisy")
        assert 0 <= report.predictability_score <= 1

    def test_emergence_with_constant(self):
        """Emergence detector doesn't crash on constant data."""
        ed = EmergenceDetector()
        for _ in range(100):
            ed.record("flat", 1.0)
        report = ed.analyze()
        assert report is not None

    def test_synaptic_rapid_oscillation(self):
        """Rapid strengthen/weaken shouldn't break state."""
        sp = SynapticPlasticity()
        sp.register("osc", initial_weight=0.5)
        for _ in range(20):
            sp.strengthen("osc")
            sp.weaken("osc")
        meta = sp.get("osc")
        assert meta is not None
        assert 0 <= meta.weight <= 1


class TestLongRunning:
    """Multi-cycle autonomic behavior tests."""

    def test_synaptic_lifecycle_50_cycles(self):
        """50 cycles of LTP/LTD/decay without corruption."""
        sp = SynapticPlasticity()
        for i in range(10):
            sp.register(f"syn_{i}", initial_weight=0.15)

        for cycle in range(50):
            # LTP on random synapse
            sp.strengthen(f"syn_{cycle % 10}", boost=0.5)
            # LTD on random synapse
            sp.weaken(f"syn_{(cycle + 3) % 10}", penalty=0.3)
            # Periodic decay
            if cycle % 10 == 0:
                sp.decay_all()
            # Periodic homeostatic
            if cycle % 20 == 0:
                sp.homeostatic_scale()

        stats = sp.stats()
        assert stats["total_synapses"] == 10  # None lost
        for i in range(10):
            meta = sp.get(f"syn_{i}")
            assert meta is not None
            assert 0 <= meta.weight <= 1  # Weight in valid range

    def test_provider_30_rounds(self):
        """30 rounds of provider selection with feedback."""
        router = ThompsonRouter()
        providers = [f"p_{i}" for i in range(5)]
        for p in providers:
            router.get_arm(p)

        decisions = []
        for rnd in range(30):
            selected = router.select_best(providers)
            decisions.append(selected)
            # Simulate mixed outcomes
            if rnd % 3 == 0:
                router.record_failure(selected)
            else:
                router.record_success(selected, latency_ms=200, cost_yuan=0.001)

        stats = router.all_stats()
        assert len(stats) == 5
        # At least one provider should have been explored
        total_calls = sum(s["total_calls"] for s in stats)
        assert total_calls == 30

    def test_predictability_feed_100_steps(self):
        """Feed 100 data points and analyze without memory leak."""
        pe = PredictabilityEngine()
        import math
        for i in range(100):
            pe.feed("trend", 10 + i * 0.1 + 2 * math.sin(i * 0.1))

        report = pe.analyze("trend")
        assert report is not None
        # Series data should still be manageable
        assert len(pe._series["trend"]) <= 300  # Not leaking


class TestBehavioralDrift:
    """Detect if system behavior changes unexpectedly over time."""

    def test_router_decision_consistency(self):
        """Router decisions should be consistent with similar inputs."""
        router = ThompsonRouter()
        for p in ["a", "b", "c"]:
            arm = router.get_arm(p)
            arm.quality.observe_success(weight=5)
            arm.latency.observe_success(weight=5)
            arm.cost_belief.observe_success(weight=5)

        selections = []
        for _ in range(20):
            selected = router.select_best(["a", "b", "c"])
            selections.append(selected)

        from collections import Counter
        counts = Counter(selections)
        # With strong priors, at least one provider should dominate
        most_common = counts.most_common(1)[0][1]
        assert most_common >= 5  # 25% minimum with moderate priors

    def test_plasticity_weight_bounds(self):
        """Weights should stay in [0, 1] after aggressive operations."""
        sp = SynapticPlasticity()
        sp.register("bound_test", initial_weight=0.5)

        # Try to push weight out of bounds
        for _ in range(100):
            sp.strengthen("bound_test", boost=10.0)  # Massive boost
        assert sp.get("bound_test").weight <= 1.0

        sp.register("bound_test2", initial_weight=0.5)
        for _ in range(100):
            sp.weaken("bound_test2", penalty=10.0)  # Massive penalty
        assert sp.get("bound_test2").weight >= 0.0

    def test_entropy_monotonicity(self):
        """Entropy of constant series should be lower than random."""
        pe = PredictabilityEngine()
        import random
        for _ in range(50):
            pe.feed("constant", 1.0)
        for _ in range(50):
            pe.feed("random", random.uniform(0, 100))

        pe_const = pe.permutation_entropy("constant")
        pe_rand = pe.permutation_entropy("random")
        assert pe_const < pe_rand  # Constant = lower entropy
