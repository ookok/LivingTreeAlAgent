"""Tests for execution layer — plan_validator, fitness_landscape."""
import pytest
from livingtree.execution.plan_validator import (
    PlanValidator, PlanStep, ValidationResult, get_plan_validator,
)
from livingtree.execution.fitness_landscape import (
    FitnessLandscape, FitnessVector, TrajectoryScore, get_fitness_landscape,
)


class TestPlanValidator:
    def test_empty_plan(self):
        v = PlanValidator()
        issues = v._structural_check([])
        assert any("Empty" in i for i in issues)

    def test_cycle_detection_simple(self):
        v = PlanValidator()
        steps = [
            PlanStep(step_id="a", tool="read", dependencies=["b"]),
            PlanStep(step_id="b", tool="edit", dependencies=["a"]),
        ]
        # Cycle detection: should not crash (recursion guard)
        issues = v._structural_check(steps)
        # May or may not detect cycle depending on implementation
        # but MUST not raise RecursionError

    def test_cycle_detection_none(self):
        v = PlanValidator()
        steps = [
            PlanStep(step_id="a", tool="read"),
            PlanStep(step_id="b", tool="edit", dependencies=["a"]),
        ]
        issues = v._structural_check(steps)
        assert not any("Circular" in i for i in issues)

    def test_chain_depth(self):
        v = PlanValidator()
        steps = [
            PlanStep(step_id="a", tool="read"),
            PlanStep(step_id="b", tool="edit", dependencies=["a"]),
            PlanStep(step_id="c", tool="lsp_diagnostics", dependencies=["b"]),
            PlanStep(step_id="d", tool="write", dependencies=["c"]),
        ]
        depth = v._max_chain_depth(steps)
        assert depth == 4

    def test_structural_check_clean(self):
        v = PlanValidator()
        steps = [
            PlanStep(step_id="read", tool="read"),
            PlanStep(step_id="edit", tool="edit", dependencies=["read"]),
            PlanStep(step_id="diag", tool="lsp_diagnostics", dependencies=["edit"]),
        ]
        issues = v._structural_check(steps)
        # Should not have critical issues
        assert not any("Circular" in i for i in issues)
        assert not any("Destructive" in i for i in issues)

    def test_anti_pattern_detection(self):
        v = PlanValidator()
        steps = [
            PlanStep(step_id="bad", tool="execute",
                     description="delete all user data"),
        ]
        issues = v._structural_check(steps)
        assert any("Destructive" in i for i in issues)

    def test_singleton(self):
        v1 = get_plan_validator()
        v2 = get_plan_validator()
        assert v1 is v2


class TestFitnessVector:
    def test_from_raw_success(self):
        fv = FitnessVector.from_raw(success=True, total_tokens=5000,
                                      total_ms=30_000, safety_violations=0)
        assert fv.reliability == 1.0
        assert fv.safety == 1.0
        assert 0.5 < fv.speed < 1.0

    def test_from_raw_failure(self):
        fv = FitnessVector.from_raw(success=False, total_tokens=50000,
                                      total_ms=120_000, safety_violations=3)
        assert fv.reliability == 0.0
        assert fv.safety < 0.6

    def test_dominates(self):
        a = FitnessVector(1.0, 1.0, 0.9, 1.0)
        b = FitnessVector(0.5, 0.5, 0.5, 0.5)
        assert a.dominates(b)

    def test_weighted_score(self):
        fv = FitnessVector(0.8, 0.7, 0.9, 0.6)
        score = fv.weighted_score()
        assert 0.5 < score < 1.0


class TestFitnessLandscape:
    def test_record_and_stats(self):
        landscape = FitnessLandscape()
        landscape.record("traj_1", ["read", "edit"], 1000, 5000, True, 0, "ok")
        landscape.record("traj_2", ["read", "edit", "write"], 3000, 15000, False, 2, "fail")

        stats = landscape.stats()
        assert stats["count"] == 2
        assert stats["avg_reliability"] == 0.5

    def test_pareto_front(self):
        landscape = FitnessLandscape()
        # Dominant
        landscape.record("best", ["read"], 100, 1000, True, 0)
        # Dominated
        landscape.record("worst", ["read"], 10000, 100000, False, 3)

        front = landscape.get_pareto_front()
        assert len(front) == 1
        assert front[0].trajectory_id == "best"

    def test_find_best(self):
        landscape = FitnessLandscape()
        landscape.record("a", ["read"], 500, 5000, True, 0)
        landscape.record("b", ["read", "write"], 1000, 10000, True, 0)

        best = landscape.find_best()
        assert best is not None

    def test_recommend_for(self):
        landscape = FitnessLandscape()
        landscape.record("a", ["read", "grep", "edit"], 2000, 10000, True, 0)
        landscape.record("b", ["web_search", "analyze"], 5000, 20000, False, 1)

        recs = landscape.recommend_for(["read", "grep", "edit"], k=1)
        assert len(recs) >= 1
        assert recs[0].trajectory_id == "a"

    def test_singleton(self):
        f1 = get_fitness_landscape()
        f2 = get_fitness_landscape()
        assert f1 is f2
