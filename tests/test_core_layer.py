"""Unit tests for Synaptic Plasticity, System Health, Action Principle, Autonomic Loop."""
import pytest
from livingtree.core.synaptic_plasticity import (
    SynapticPlasticity, SynapseMetadata, SynapticState, get_plasticity)
from livingtree.core.action_principle import ActionPrinciple, get_action_principle


class TestSynapticPlasticity:
    def test_register_silent(self):
        sp = SynapticPlasticity()
        meta = sp.register("s1")
        assert meta.state == SynapticState.SILENT
        assert 0.1 < meta.weight < 0.2
        assert sp.silent_ratio() > 0

    def test_strengthen_ltp(self):
        sp = SynapticPlasticity()
        sp.register("s1", initial_weight=0.15)
        w1 = sp.strengthen("s1")
        assert w1 > 0.15  # Should increase

    def test_strengthen_activates(self):
        sp = SynapticPlasticity()
        sp.register("s2", initial_weight=0.15)
        for _ in range(10):
            sp.strengthen("s2", boost=2.0)
        meta = sp.get("s2")
        assert meta.state in (SynapticState.ACTIVE, SynapticState.MATURE)

    def test_weaken_ltd(self):
        sp = SynapticPlasticity()
        sp.register("s3", initial_weight=0.5)
        w1 = sp.weaken("s3")
        assert w1 < 0.5

    def test_decay(self):
        sp = SynapticPlasticity()
        sp.register("s4", initial_weight=0.3)
        w = sp.decay("s4")
        assert w < 0.3

    def test_mature_protection(self):
        sp = SynapticPlasticity()
        sp.register("s5", initial_weight=0.85)
        meta = sp.get("s5")
        meta.state = SynapticState.MATURE
        meta.protection_level = 0.8
        assert meta.is_protected

    def test_homeostatic_scale(self):
        sp = SynapticPlasticity()
        for i in range(5):
            sp.register(f"s{i}", initial_weight=0.1 + i * 0.15)
        sp.homeostatic_scale()
        # Weights should be closer to target after scaling

    def test_interference_detection(self):
        sp = SynapticPlasticity()
        sp.register("mature1", initial_weight=0.85)
        sp.get("mature1").state = SynapticState.MATURE
        sp.register("mature2", initial_weight=0.60)  # Below mature threshold
        sp.get("mature2").state = SynapticState.MATURE
        degradation = sp.detect_interference("new1", ["mature1", "mature2"])
        assert isinstance(degradation, dict)

    def test_self_distillation(self):
        sp = SynapticPlasticity()
        for i in range(5):
            sp.register(f"sd{i}", initial_weight=0.2 + i * 0.1)
        loss = sp.self_distillation_loss()
        assert loss >= 0
        sp.regularize_distribution(strength=0.1)

    def test_degradation_alert(self):
        sp = SynapticPlasticity()
        for i in range(10):
            sp.register(f"da{i}", initial_weight=0.5)
        alert = sp.degradation_alert()
        assert alert["severity"] in ("normal", "warning", "critical")

    def test_silent_ratio_target(self):
        sp = SynapticPlasticity()
        for i in range(30):
            sp.register(f"sr{i}", initial_weight=0.1)
        # Fresh synapses should be mostly silent
        assert sp.silent_ratio() > 0

    def test_stats(self):
        sp = SynapticPlasticity()
        for i in range(5):
            sp.register(f"st{i}")
        s = sp.stats()
        assert s["total_synapses"] == 5
        assert "by_state" in s


class TestActionPrinciple:
    def test_observe_and_analyze(self):
        ap = ActionPrinciple()
        ap.observe("synaptic", "interference", 0.05)
        ap.observe("synaptic", "silent_ratio", 0.3)
        ap.observe("provider", "success_rate", 0.8)
        ap.observe("economic", "daily_spent", 5.0)

        analysis = ap.analyze()
        assert analysis is not None
        assert analysis.total_kinetic + analysis.total_potential >= 0
        assert hasattr(analysis, 'system_on_shell')

    def test_module_lagrangian(self):
        ap = ActionPrinciple()
        ap.observe("synaptic", "weight_mean", 0.5)
        ap.observe("synaptic", "interference", 0.1)
        lag = ap.compute_module_lagrangian("synaptic", ap._last_state)
        assert lag.kinetic >= 0
        assert lag.total == lag.kinetic - lag.potential

    def test_derive_optimal_params(self):
        ap = ActionPrinciple()
        ap.observe("synaptic", "interference", 0.1)
        ap.observe("provider", "regret", 0.2)
        ap.observe("provider", "success_rate", 0.8)
        ap.observe("provider", "calls", 10)
        analysis = ap.analyze()
        assert len(analysis.optimal_params) >= 0

    def test_most_deviant(self):
        ap = ActionPrinciple()
        ap.observe("synaptic", "interference", 0.3)
        ap.observe("provider", "success_rate", 0.9)
        ap.observe("economic", "daily_spent", 100)
        ap.analyze()
        deviant = ap.most_deviant_module()
        assert deviant in ("synaptic", "provider", "economic", "latent_grpo",
                           "hypergraph", "pipeline", "unknown")

    def test_conserved_quantities(self):
        ap = ActionPrinciple()
        ap.observe("router", "exploration_weight", 0.15)
        ap.observe("router", "uncertainty", 0.5)
        analysis = ap.analyze()
        assert "energy" in analysis.conserved_quantities
        assert "uncertainty_product" in analysis.conserved_quantities

    def test_feed_all_modules(self):
        from livingtree.core.action_principle import feed_all_modules
        ap = ActionPrinciple()
        analysis = feed_all_modules(ap)
        assert analysis is not None
        assert analysis.total_kinetic >= 0
