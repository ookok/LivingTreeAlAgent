"""Unit tests for Economy & Routing layer."""
import pytest
from livingtree.economy.spatial_reward import (
    SpatialGRPOOptimizer, SpatialContext, get_sgrpo)
from livingtree.economy.tdm_reward import (
    TDMRewardOptimizer, SurrogateRewardModel, get_tdm_optimizer)
from livingtree.economy.thermo_budget import (
    ThermodynamicBudget, get_thermo_budget)
from livingtree.economy.latent_grpo import (
    LatentGRPO, LatentEncoder, get_latent_grpo)
from livingtree.economy.economic_engine import EconomicPolicy, ROIModel


class TestSpatialGRPO:
    def test_baseline_scoring(self):
        sgrpo = SpatialGRPOOptimizer()
        score = sgrpo.score_baseline("test_action",
            {"capability": 0.7, "latency_norm": 0.5, "cost_norm": 0.6, "reliability": 0.8})
        assert 0.4 < score < 0.9

    def test_total_scoring_with_spatial(self):
        sgrpo = SpatialGRPOOptimizer()
        spatial = SpatialContext(avg_centrality=0.5, graph_density=0.3,
                                  precedence_depth=0.6, has_cycles=True)
        score = sgrpo.score_total("action",
            {"capability": 0.7}, spatial)
        assert score > 0

    def test_optimize_group(self):
        sgrpo = SpatialGRPOOptimizer()
        spatial = SpatialContext(avg_centrality=0.4)
        group = [("a", {"capability": 0.8}), ("b", {"capability": 0.5})]
        outcomes = {"a": 0.9, "b": 0.6}
        result = sgrpo.optimize(group, spatial, outcomes)
        assert result.round_id > 0


class TestTDMReward:
    def test_surrogate_training(self):
        sm = SurrogateRewardModel(learning_rate=0.01)
        loss = sm.train_step({"f1": 0.5, "f2": 0.3}, 0.7)
        assert loss >= 0

    def test_surrogate_predict(self):
        sm = SurrogateRewardModel()
        sm.train_batch([
            ({"f1": 0.5}, 0.7), ({"f1": 0.8}, 0.9), ({"f1": 0.2}, 0.3)])
        pred = sm.predict({"f1": 0.6})
        assert 0 < pred < 1

    def test_distribute_rewards(self):
        tdm = TDMRewardOptimizer()
        traj = tdm.distribute_rewards(
            "t1", ["perceive", "cognize", "execute"],
            [{"d": 0.5}, {"d": 0.6}, {"d": 0.8}], 0.85)
        assert traj.trajectory_length == 3
        assert len(traj.steps) == 3

    def test_train_surrogate(self):
        tdm = TDMRewardOptimizer()
        traj = tdm.distribute_rewards(
            "t2", ["plan", "execute"],
            [{"c": 0.3}, {"c": 0.7}], 0.9)
        tdm._history.append(traj)
        loss = tdm.train_surrogate()
        assert loss < float('inf')


class TestThermoBudget:
    def test_initial_state(self):
        tb = ThermodynamicBudget(daily_budget_yuan=50)
        assert tb._state.remaining_budget == 50
        assert 0 <= tb._state.temperature <= 1

    def test_record_spending(self):
        tb = ThermodynamicBudget(daily_budget_yuan=100)
        tb.record_spending(5.0)
        assert tb._state.remaining_budget <= 100

    def test_evaluate(self):
        tb = ThermodynamicBudget(daily_budget_yuan=50)
        decision = tb.evaluate("task1", estimated_cost=1.0, task_priority=0.5)
        assert decision.proceed is True  # Low cost should pass

    def test_entropy_ratio(self):
        tb = ThermodynamicBudget(daily_budget_yuan=100)
        tb.record_spending(1.0)
        ratio = tb.entropy_budget_ratio()
        assert ratio > 0

    def test_phase_detection(self):
        tb = ThermodynamicBudget()
        phase = tb.detect_phase_transition()
        assert phase in ("frozen", "ordered", "critical", "chaotic")


class TestLatentGRPO:
    def test_encoder_encode(self):
        enc = LatentEncoder(input_dim=5, latent_dim=3)
        z = enc.encode({"f1": 0.5, "f2": 0.3}, ["f1", "f2"])
        assert len(z) == 3

    def test_feedback_align(self):
        enc = LatentEncoder(input_dim=3, latent_dim=2)
        loss = enc.feedback_align(
            {"f1": 0.5}, ["f1"], error_signal=[0.3, -0.2], lr=0.01)
        assert loss >= 0
        assert hasattr(enc, '_alignment')

    def test_latent_score(self):
        lg = LatentGRPO(latent_dim=4)
        lg.encode_action("a1", {"f1": 0.5})
        score = lg.latent_score("a1")
        assert 0 < score <= 1

    def test_optimize(self):
        lg = LatentGRPO(latent_dim=4)
        group = [("a1", {"f1": 0.7, "f2": 0.5}), ("a2", {"f1": 0.3, "f2": 0.8})]
        outcomes = {"a1": 0.9, "a2": 0.5}
        result = lg.optimize(group, outcomes)
        assert result.round_id > 0


class TestEconomicEngineCoverage:
    def test_sensetime_pricing(self):
        roi = ROIModel()
        cost_in = roi.MODEL_PRICE_INPUT.get("sensetime/SenseChat-Turbo", -1)
        cost_out = roi.MODEL_PRICE_OUTPUT.get("sensetime/SenseChat-Turbo", -1)
        assert cost_in == 0.0  # Should be free
        assert cost_out == 0.0

    def test_select_model_no_dead_code(self):
        policy = EconomicPolicy.balanced()
        model = policy.select_model(task_complexity=0.5)
        assert model is not None
        # Verify no duplicate return after fix
        assert isinstance(model, str)
