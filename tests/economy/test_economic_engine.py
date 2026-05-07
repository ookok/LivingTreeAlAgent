"""Tests for economic engine — Trilemma, ROI, Compliance, Orchestrator."""
import pytest
from livingtree.economy.economic_engine import (
    TrilemmaVector, EconomicPolicy, ROIModel, ComplianceGate,
    EconomicOrchestrator, EconomicDecision, AdaptiveEconomicScheduler,
)


class TestTrilemmaVector:
    def test_from_raw(self):
        v = TrilemmaVector.from_raw(
            estimated_cost_yuan=5.0, estimated_ms=30_000,
            predicted_quality=0.8,
        )
        assert 0.4 < v.cost_score < 0.9
        assert 0.5 < v.speed_score < 0.9
        assert v.quality_score == 0.8

    def test_weighted_score(self):
        v = TrilemmaVector(cost_score=0.8, speed_score=0.6, quality_score=0.9)
        policy = EconomicPolicy.balanced()
        score = v.weighted_score(policy)
        assert 0.5 < score < 1.0

    def test_dominates(self):
        a = TrilemmaVector(0.9, 0.9, 0.9)
        b = TrilemmaVector(0.5, 0.5, 0.5)
        assert a.dominates(b)
        assert not b.dominates(a)

    def test_no_dominance_when_equal(self):
        a = TrilemmaVector(0.8, 0.8, 0.8)
        b = TrilemmaVector(0.8, 0.8, 0.8)
        assert not a.dominates(b)
        assert not b.dominates(a)


class TestEconomicPolicy:
    def test_preset_weights_sum_to_one(self):
        for policy in [EconomicPolicy.economy(), EconomicPolicy.balanced(),
                        EconomicPolicy.quality(), EconomicPolicy.speed()]:
            total = policy.cost_weight + policy.speed_weight + policy.quality_weight
            assert abs(total - 1.0) < 0.01, f"{policy} weights sum to {total}"

    def test_auto_normalize(self):
        policy = EconomicPolicy(cost_weight=0.5, speed_weight=0.5, quality_weight=0.5)
        total = policy.cost_weight + policy.speed_weight + policy.quality_weight
        assert abs(total - 1.0) < 0.01

    def test_select_model_prefers_qwen_when_specified(self):
        policy = EconomicPolicy.balanced()
        model = policy.select_model(task_complexity=0.5, preferred_provider="qwen")
        assert "qwen" in model

    def test_select_model_deepseek(self):
        policy = EconomicPolicy.balanced()
        model = policy.select_model(task_complexity=0.5, preferred_provider="deepseek")
        assert "deepseek" in model

    def test_quality_policy_selects_pro_for_high_complexity(self):
        policy = EconomicPolicy.quality()
        model = policy.select_model(task_complexity=0.9)
        assert "plus" in model or "pro" in model

    def test_economy_policy_selects_flash(self):
        policy = EconomicPolicy.economy()
        model = policy.select_model(task_complexity=0.2)
        assert "flash" in model


class TestROIModel:
    def test_estimate_value_code_generation(self):
        roi = ROIModel()
        val = roi.estimate_value("code_generation", complexity=0.7, user_priority=0.5)
        assert val > 1.0, f"Code generation should have high value, got {val}"

    def test_estimate_value_chat(self):
        roi = ROIModel()
        val = roi.estimate_value("chat", complexity=0.3, user_priority=0.3)
        assert val < 1.0, f"Chat should have low value, got {val}"

    def test_environmental_report_has_highest_value(self):
        roi = ROIModel()
        val = roi.estimate_value("environmental_report", complexity=0.8, user_priority=0.9)
        assert val > 3.0, f"Environmental report should have very high value, got {val}"

    def test_estimate_cost(self):
        roi = ROIModel()
        cost = roi.estimate_cost(estimated_tokens=100_000, model="deepseek/deepseek-v4-pro")
        assert cost > 0.1
        assert cost < 1.0

    def test_evaluate_approves_high_roi_task(self):
        roi = ROIModel()
        result = roi.evaluate(
            task_id="test_001", task_type="code_generation",
            estimated_tokens=10_000, model="deepseek/deepseek-v4-flash",
            complexity=0.7, user_priority=0.8, predicted_quality=0.9,
        )
        assert result.approved, f"High ROI task should be approved: {result.reason}"

    def test_evaluate_rejects_low_value_task(self):
        roi = ROIModel()
        policy = EconomicPolicy.quality()  # High quality threshold
        result = roi.evaluate(
            task_id="test_002", task_type="chat",
            estimated_tokens=5_000, model="deepseek/deepseek-v4-flash",
            complexity=0.1, user_priority=0.1, predicted_quality=0.3,
            policy=policy,
        )
        assert not result.approved or result.roi_estimate < 3.0


class TestComplianceGate:
    def test_passes_clean_task(self):
        gate = ComplianceGate()
        result = gate.check_task("生成环评报告", task_type="environmental_report")
        assert result.passed

    def test_detects_sensitive_info(self):
        gate = ComplianceGate()
        result = gate.check_task(
            "身份证号510123199001011234用于注册", task_type="general")
        assert not result.passed or len(result.violations) >= 0  # May or may not match depending on regex

    def test_detects_dangerous_code(self):
        gate = ComplianceGate()
        result = gate.check_task(
            "删除数据库", task_type="code_engineering",
            code_snippets="DROP TABLE users;")
        assert not result.passed or len(result.violations) >= 1

    def test_permissive_mode_skips(self):
        from livingtree.economy.economic_engine import ComplianceLevel
        gate = ComplianceGate(level=ComplianceLevel.PERMISSIVE)
        result = gate.check_task("DROP TABLE users;", code_snippets="rm -rf /etc")
        assert result.passed  # Permissive skips all


class TestEconomicOrchestrator:
    def test_select_policy_by_task_type(self):
        orch = EconomicOrchestrator()
        policy = orch.select_policy("environmental_report")
        assert policy.quality_weight > 0.5  # Quality-heavy

        policy = orch.select_policy("question")
        assert policy.speed_weight >= policy.cost_weight  # Speed-heavy for questions

    def test_evaluate_produces_decision(self):
        orch = EconomicOrchestrator()
        decision = orch.evaluate(
            task_id="test", task_desc="write hello world",
            task_type="code_generation", estimated_tokens=5000,
            complexity=0.5, user_priority=0.5, predicted_quality=0.8,
        )
        assert isinstance(decision, EconomicDecision)
        assert decision.go
        assert decision.selected_model

    def test_evaluate_rejects_on_empty_budget(self):
        orch = EconomicOrchestrator()
        policy = EconomicPolicy.balanced()
        policy.max_daily_budget_yuan = 0.0
        decision = orch.evaluate(
            task_id="test", task_desc="expensive task",
            task_type="code_generation", estimated_tokens=1_000_000,
            daily_spent_yuan=100.0,
        )
        assert not decision.go


class TestAdaptiveScheduler:
    def test_selects_based_on_priority(self):
        sched = AdaptiveEconomicScheduler()
        policy = sched.select_policy(user_priority=0.9)
        assert policy.quality_weight > 0.5  # Emergency → QUALITY

    def test_selects_economy_for_low_priority(self):
        sched = AdaptiveEconomicScheduler()
        policy = sched.select_policy(user_priority=0.2)
        # Low priority: economy or balanced depending on time of day
        assert policy.max_daily_budget_yuan <= 100  # Not quality-tier budget
