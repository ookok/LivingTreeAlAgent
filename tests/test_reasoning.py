"""Reasoning layer integration tests — four logic types.

Tests cover:
  - Formal: RuleEngine forward/backward chain, conflict detection, Syllogism verification
  - Mathematical: FOL knowledge representation, Bayes updates
  - Dialectical: Contradiction tracking, phase transitions
  - Historical: Attribution loop, layering, consensus A/B testing
  - Integration: cross-logic reasoning pipeline
"""

from __future__ import annotations

import time
import pytest

from livingtree.reasoning.formal import (
    RuleEngine, Rule, Fact, FactStatus,
    SyllogismVerifier, CategoricalProposition, Quantifier, SyllogismFigure, SyllogismResult,
)
from livingtree.reasoning.mathematical import (
    KnowledgeRepresentation, Predicate, Axiom,
    BayesianReasoner, Hypothesis, Evidence,
)
from livingtree.reasoning.dialectical import (
    ContradictionTracker, PhaseTransitionMonitor, Phase,
)
from livingtree.reasoning.historical import (
    AttributionLoop, LayeringTracker, ConsensusMeasure, DecisionOutcome,
)


# ═══ Formal Logic ═══

class TestRuleEngine:
    def test_assert_and_query(self):
        engine = RuleEngine("test")
        engine.assert_fact("raining", True, confidence=0.9)
        assert engine.query("raining") == FactStatus.KNOWN
        assert engine.query("nonexistent") == FactStatus.UNCERTAIN

    def test_forward_chain_simple(self):
        engine = RuleEngine("test")
        engine.assert_fact("sensor_triggered", True)
        engine.add_rule(Rule(
            name="sensor_to_alarm",
            conditions=["sensor_triggered"],
            conclusion="alarm_active",
            conclusion_value=True,
        ))
        new_facts = engine.forward_chain()
        assert any(f.name == "alarm_active" and f.value for f in new_facts)

    def test_forward_chain_priority(self):
        engine = RuleEngine("test")
        engine.assert_fact("fire", True)
        engine.add_rule(Rule(
            name="high_priority",
            conditions=["fire"],
            conclusion="evacuate",
            priority=10,
        ))
        engine.add_rule(Rule(
            name="low_priority",
            conditions=["fire"],
            conclusion="log_event",
            priority=1,
        ))
        new_facts = engine.forward_chain()
        assert any(f.name == "evacuate" for f in new_facts)

    def test_backward_chain_provable(self):
        engine = RuleEngine("test")
        engine.assert_fact("battery_low", True)
        engine.add_rule(Rule(
            name="low_battery_alert",
            conditions=["battery_low"],
            conclusion="alert_user",
        ))
        provable, chain = engine.backward_chain("alert_user")
        assert provable
        assert "low_battery_alert" in chain

    def test_backward_chain_unprovable(self):
        engine = RuleEngine("test")
        provable, chain = engine.backward_chain("nonexistent_goal")
        assert not provable

    def test_conflict_detection(self):
        engine = RuleEngine("test")
        engine.assert_fact("condition_x", True)
        engine.add_rule(Rule(
            name="rule_to_b",
            conditions=["condition_x"],
            conclusion="result",
            conclusion_value=True,
        ))
        engine.add_rule(Rule(
            name="rule_to_not_b",
            conditions=["condition_x"],
            conclusion="result",
            conclusion_value=False,
        ))
        conflicts = engine.get_conflicts()
        assert len(conflicts) == 1

    def test_retraction(self):
        engine = RuleEngine("test")
        engine.assert_fact("temp_assertion", True)
        engine.retract_fact("temp_assertion")
        assert engine.query("temp_assertion") == FactStatus.RETRACTED

    def test_inference_trace(self):
        engine = RuleEngine("test")
        engine.assert_fact("input", True)
        engine.add_rule(Rule("r1", conditions=["input"], conclusion="output"))
        engine.forward_chain()
        trace = engine.get_inference_trace("output")
        assert trace["provable"]

    def test_fact_with_evidence(self):
        engine = RuleEngine("test")
        engine.assert_fact("diagnosed", True, source="test_lab")
        assert engine.query("diagnosed") == FactStatus.KNOWN


class TestSyllogism:
    def test_barbara(self):
        v = SyllogismVerifier()
        major = CategoricalProposition("M", "P", Quantifier.ALL)
        minor = CategoricalProposition("S", "M", Quantifier.ALL)
        result = v.verify(major, minor, SyllogismFigure.FIGURE_1)
        assert result.valid
        assert result.mood == "BARBARA"

    def test_celarent(self):
        v = SyllogismVerifier()
        major = CategoricalProposition("M", "P", Quantifier.NONE)
        minor = CategoricalProposition("S", "M", Quantifier.ALL)
        result = v.verify(major, minor, SyllogismFigure.FIGURE_1)
        assert result.valid
        assert result.mood == "CELARENT"

    def test_invalid_syllogism(self):
        v = SyllogismVerifier()
        major = CategoricalProposition("M", "P", Quantifier.SOME)
        minor = CategoricalProposition("S", "M", Quantifier.SOME)
        result = v.verify(major, minor, SyllogismFigure.FIGURE_1)
        assert not result.valid

    def test_simple_api(self):
        v = SyllogismVerifier()
        result = v.verify_simple(True, True, True, True)
        assert result.valid
        assert result.mood == "BARBARA"

    def test_explain(self):
        v = SyllogismVerifier()
        major = CategoricalProposition("M", "P", Quantifier.ALL)
        minor = CategoricalProposition("S", "M", Quantifier.ALL)
        result = v.verify(major, minor, SyllogismFigure.FIGURE_1)
        explanation = v.explain(result)
        assert "BARBARA" in explanation


# ═══ Mathematical Logic ═══

class TestKnowledgeRepresentation:
    def test_define_and_query_concept(self):
        kr = KnowledgeRepresentation("test")
        kr.define_concept("is_industrial", lambda p: p.get("type") == "industrial")
        kr.assert_individual("project_A", type="industrial", location="北京")
        kr.assert_individual("project_B", type="residential", location="上海")
        assert kr.assert_type("project_A", "is_industrial")
        assert not kr.assert_type("project_B", "is_industrial")

    def test_role_relation(self):
        kr = KnowledgeRepresentation("test")
        kr.define_role("located_in", lambda s, o: s.get("city") == o.get("city"))
        kr.assert_individual("A", city="北京")
        kr.assert_individual("B", city="北京")
        kr.assert_individual("C", city="上海")
        assert kr.assert_relation("A", "located_in", "B")
        assert not kr.assert_relation("A", "located_in", "C")

    def test_disjointness_check(self):
        kr = KnowledgeRepresentation("test")
        kr.define_concept("is_hot", lambda p: p.get("temp", 0) > 30)
        kr.define_concept("is_cold", lambda p: p.get("temp", 0) < 10)
        kr.declare_disjoint("is_hot", "is_cold")
        kr.assert_individual("test_entity", temp=35)
        kr.assert_type("test_entity", "is_hot")
        consistent, violations = kr.check_consistency()
        assert consistent

    def test_formula_evaluation(self):
        kr = KnowledgeRepresentation("test")
        kr.define_concept("is_large", lambda p: p.get("size", 0) > 100)
        kr.assert_individual("entity_X", size=200)
        kr.assert_type("entity_X", "is_large")
        val, conf = kr.evaluate_formula("is_large(entity_X)")
        assert val

    def test_predicate_definition(self):
        kr = KnowledgeRepresentation("test")
        kr.define_predicate("greater_than", 2, lambda a, b: float(a) > float(b))
        val, _ = kr.evaluate_formula("greater_than(5, 3)")
        assert val
        val2, _ = kr.evaluate_formula("greater_than(3, 5)")
        assert not val2


class TestBayesianReasoner:
    def test_hypothesis_update(self):
        b = BayesianReasoner("test")
        b.add_hypothesis("rain", prior=0.3)
        b.add_evidence("dark_clouds", lh=0.9, ln=0.1)
        posterior = b.update("rain", "dark_clouds")
        assert posterior > 0.3  # dark clouds increase rain probability

    def test_multi_evidence(self):
        b = BayesianReasoner("test")
        b.add_hypothesis("use_discard", prior=0.5)
        b.add_evidence("high_stale_ratio", lh=0.85, ln=0.15)
        b.add_evidence("low_write_amp", lh=0.7, ln=0.3)
        p1 = b.update("use_discard", "high_stale_ratio")
        p2 = b.update_multi("use_discard", ["high_stale_ratio", "low_write_amp"])
        assert p2 > p1

    def test_best_hypothesis(self):
        b = BayesianReasoner("test")
        b.add_hypothesis("discard", prior=0.6)
        b.add_hypothesis("compact", prior=0.4)
        name, prob = b.best_hypothesis()
        assert name == "discard"

    def test_reset(self):
        b = BayesianReasoner("test")
        b.add_hypothesis("test_h", prior=0.5)
        b.add_evidence("test_e", lh=0.9, ln=0.1)
        b.update("test_h", "test_e")
        assert b.belief("test_h") > 0.5
        b.reset_hypothesis("test_h")
        assert abs(b.belief("test_h") - 0.5) < 0.01

    def test_evidence_strength(self):
        b = BayesianReasoner("test")
        b.add_evidence("strong", lh=0.99, ln=0.01)
        b.add_evidence("weak", lh=0.51, ln=0.49)
        assert b.get_evidence_strength("strong") > b.get_evidence_strength("weak")

    def test_compare_hypotheses(self):
        b = BayesianReasoner("test")
        b.add_hypothesis("A", prior=0.7)
        b.add_hypothesis("B", prior=0.3)
        b.add_evidence("ev", lh=0.8, ln=0.2)
        b.update("A", "ev")
        b.update("B", "ev")
        comparison = b.compare_hypotheses(["A", "B"])
        assert comparison["A"] > comparison["B"]


# ═══ Dialectical Logic ═══

class TestContradictionTracker:
    def test_register_and_update(self):
        ct = ContradictionTracker("test")
        ct.register("speed_vs_quality", "speed", "quality")
        ct.update("speed_vs_quality", speed=0.8, quality=0.6)
        states = ct.get_all_states()
        assert "speed_vs_quality" in states
        assert states["speed_vs_quality"]["thesis_value"] == 0.8

    def test_dominant_pole(self):
        ct = ContradictionTracker("test")
        ct.register("test_contra", "A", "B")
        ct.update("test_contra", A=0.9, B=0.3)
        dominant, strength = ct.get_dominant_pole("test_contra")
        assert dominant == "A"

    def test_phase_transition(self):
        ct = ContradictionTracker("test")
        ct.register("test_pt", "precision", "speed")
        for i in range(10):
            ct.update("test_pt", precision=0.5 + i * 0.05, speed=0.5 + i * 0.05)
        result = ct.check_phase_transition("test_pt", intensity_threshold=0.8)
        assert result is not None

    def test_get_stats(self):
        ct = ContradictionTracker("test")
        ct.register("a", "x", "y")
        stats = ct.get_stats()
        assert stats["contradictions"] == 1


class TestPhaseTransitionMonitor:
    def test_register_and_record(self):
        ptm = PhaseTransitionMonitor("test")
        ptm.register_metric("stale_ratio", {
            "warning": (0.3, Phase.TRANSITIONING),
            "critical": (0.7, Phase.LEAPING),
        })
        ptm.record("stale_ratio", 0.1)
        assert ptm.get_phase("stale_ratio") == Phase.DORMANT

    def test_phase_leap(self):
        ptm = PhaseTransitionMonitor("test")
        ptm.register_metric("test_metric", {
            "threshold": (0.5, Phase.LEAPING),
        })
        transition = ptm.record("test_metric", 0.6)
        assert transition is not None
        assert transition.to_phase == Phase.LEAPING

    def test_trend_detection(self):
        ptm = PhaseTransitionMonitor("test")
        ptm.register_metric("growing", {
            "large": (50, Phase.LEAPING),
        })
        for i in range(10):
            ptm.record("growing", i * 0.1)
        trend = ptm.get_trend("growing")
        assert trend > 0

    def test_callback_on_transition(self):
        ptm = PhaseTransitionMonitor("test")
        triggered = []
        ptm.register_metric("cb_test", {"go": (0.3, Phase.TRANSITIONING)})
        ptm.on_transition("cb_test", lambda t: triggered.append(t.metric_name))
        ptm.record("cb_test", 0.5)
        assert len(triggered) == 1


# ═══ Historical Logic ═══

class TestAttributionLoop:
    def test_record_and_find_root_cause(self):
        al = AttributionLoop("test")
        al.record_incident("检索遗漏", "document_kb", confidence=0.7)
        al.record_fix("检索遗漏", "启用层次分块", success=True)
        causes = al.find_root_cause("检索遗漏")
        assert len(causes) > 0

    def test_convergence(self):
        al = AttributionLoop("test")
        al.record_incident("事件A", "module_X", confidence=0.5)
        al.record_fix("事件A", "修复X", success=True)
        al.record_incident("事件B", "module_Y", confidence=0.5)
        al.record_fix("事件B", "修复Y", success=True)
        assert al.get_convergence() > 0

    def test_top_problem_modules(self):
        al = AttributionLoop("test")
        al.record_incident("E1", "broken_module", confidence=0.8)
        al.record_fix("E1", "fix_attempt", success=False)
        broken = al.get_top_problem_modules(3)
        assert len(broken) >= 1


class TestLayeringTracker:
    def test_register_layer(self):
        lt = LayeringTracker("test")
        lt.register_layer("基础层", 0, ["tool_executor"])
        lt.register_layer("推理层", 1, ["rule_engine"], depends_on=["基础层"])
        stack = lt.get_layer_stack()
        assert len(stack) == 2
        assert stack[0]["level"] == 0
        assert stack[1]["level"] == 1

    def test_emergence_detection(self):
        lt = LayeringTracker("test")
        lt.register_layer("L0", 0, ["capability_x"])
        lt.register_layer("L1", 1, ["capability_x"], depends_on=["L0"])
        lt.register_layer("L2", 2, ["capability_x"], depends_on=["L1"])
        emergents = lt.check_emergence()
        assert len(emergents) == 1

    def test_total_capabilities(self):
        lt = LayeringTracker("test")
        lt.register_layer("L0", 0, ["a", "b"])
        lt.register_layer("L1", 1, ["b", "c"])
        assert lt.get_total_capabilities() == 3


class TestConsensusMeasure:
    def test_insufficient_data(self):
        cm = ConsensusMeasure("test")
        cm.start_experiment("test_exp", "A", "B")
        result = cm.evaluate("test_exp")
        assert result.outcome == DecisionOutcome.INSUFFICIENT_DATA

    def test_significant_winner(self):
        cm = ConsensusMeasure("test", significance_level=0.05)
        cm.start_experiment("chunk_method", "flat", "hierarchical")
        for _ in range(50):
            cm.record("chunk_method", "A", "precision", 0.70)
            cm.record("chunk_method", "B", "precision", 0.85)
        result = cm.evaluate("chunk_method")
        assert result.outcome == DecisionOutcome.B_WINS
        assert result.improvement > 0

    def test_no_significant_difference(self):
        cm = ConsensusMeasure("test")
        cm.start_experiment("tie_test", "A", "B")
        for _ in range(50):
            cm.record("tie_test", "A", "precision", 0.75)
            cm.record("tie_test", "B", "precision", 0.76)
        result = cm.evaluate("tie_test")
        assert result.outcome in (DecisionOutcome.TIE, DecisionOutcome.B_WINS)

    def test_adopt(self):
        cm = ConsensusMeasure("test", significance_level=0.05)
        cm.start_experiment("adopt_test", "old", "new")
        for _ in range(50):
            cm.record("adopt_test", "A", "metric", 0.5)
            cm.record("adopt_test", "B", "metric", 0.9)
        winner = cm.adopt("adopt_test")
        assert winner == "B"

    def test_all_experiments(self):
        cm = ConsensusMeasure("test")
        cm.start_experiment("exp1", "A", "B")
        cm.start_experiment("exp2", "C", "D")
        summary = cm.all_experiments()
        assert len(summary) == 2


# ═══ Integration ═══

class TestCrossLogicIntegration:
    def test_formal_to_bayesian(self):
        """Rule engine triggers Bayes update."""
        engine = RuleEngine("test")
        reasoner = BayesianReasoner("test")
        reasoner.add_hypothesis("alarm_is_real", prior=0.3)
        reasoner.add_evidence("rule_triggered", lh=0.9, ln=0.1)

        engine.assert_fact("motion_detected", True)
        engine.add_rule(Rule("motion_alarm", ["motion_detected"], conclusion="alarm"))

        engine.forward_chain()
        if engine.query("alarm") == FactStatus.KNOWN:
            reasoner.update("alarm_is_real", "rule_triggered")

        assert reasoner.belief("alarm_is_real") > 0.3

    def test_contradiction_triggers_attribution(self):
        """Contradiction detected → attribution loop starts."""
        ct = ContradictionTracker("test")
        al = AttributionLoop("test")

        ct.register("precision_speed", "precision", "speed")
        for i in range(10):
            precision = 0.5 + i * 0.05
            speed = 0.5 + i * 0.05
            ct.update("precision_speed", precision=precision, speed=speed)

        result = ct.check_phase_transition("precision_speed", intensity_threshold=0.7)
        if result:
            al.record_incident(
                "precision_speed矛盾激化",
                "tier_dispatcher",
                confidence=0.8,
            )

        causes = al.find_root_cause("precision_speed矛盾激化")
        assert len(causes) > 0

    def test_phase_layering(self):
        """Phase transitions tracked in layering system."""
        ptm = PhaseTransitionMonitor("test")
        lt = LayeringTracker("test")

        lt.register_layer("GC基础", 0, ["discard_gc"], description="基础GC")
        lt.register_layer("GC智能", 1, ["disco_gc"], depends_on=["GC基础"])

        ptm.register_metric("gc_intelligence", {
            "smart": (0.5, Phase.LEAPING),
        })

        # Simulate GC becoming smarter
        transition = ptm.record("gc_intelligence", 0.6)
        if transition:
            lt.mark_usage("GC智能")

        assert lt.get_stats()["layers"] == 2
