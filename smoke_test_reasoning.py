#!/usr/bin/env python3
"""Quick smoke test for Reasoning Layer (four logics).

Usage: python smoke_test_reasoning.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from livingtree.reasoning.formal import RuleEngine, Rule, SyllogismVerifier, CategoricalProposition, Quantifier, SyllogismFigure
from livingtree.reasoning.mathematical import KnowledgeRepresentation, BayesianReasoner
from livingtree.reasoning.dialectical import ContradictionTracker, PhaseTransitionMonitor, Phase
from livingtree.reasoning.historical import AttributionLoop, LayeringTracker, ConsensusMeasure, DecisionOutcome


def test_formal_rule_engine():
    print("1. RuleEngine...", end=" ")
    e = RuleEngine("smoke")
    e.assert_fact("fire", True)
    e.add_rule(Rule("r1", ["fire"], conclusion="evacuate", priority=10))
    facts = e.forward_chain()
    assert any(f.name == "evacuate" for f in facts)
    provable, chain = e.backward_chain("evacuate")
    assert provable
    print(f"OK ({len(facts)} derived)")

def test_formal_syllogism():
    print("2. Syllogism...", end=" ")
    v = SyllogismVerifier()
    r = v.verify_simple(True, True, True, True)
    assert r.valid and r.mood == "BARBARA"
    r2 = v.verify_simple(False, True, False, True)
    assert not r2.valid
    print("OK")

def test_mathematical_kr():
    print("3. KnowledgeRepresentation...", end=" ")
    kr = KnowledgeRepresentation("smoke")
    kr.define_concept("industrial", lambda p: p.get("type") == "industrial")
    kr.assert_individual("proj_A", type="industrial")
    assert kr.assert_type("proj_A", "industrial")
    assert not kr.evaluate_formula("industrial(proj_B)")[0]
    print("OK")

def test_mathematical_bayes():
    print("4. BayesianReasoner...", end=" ")
    b = BayesianReasoner("smoke")
    b.add_hypothesis("rain", 0.3)
    b.add_evidence("clouds", 0.9, 0.1)
    p = b.update("rain", "clouds")
    assert p > 0.3
    print(f"OK (P={p:.3f})")

def test_dialectical_contradiction():
    print("5. ContradictionTracker...", end=" ")
    ct = ContradictionTracker("smoke")
    ct.register("prec_speed", "precision", "speed")
    ct.update("prec_speed", precision=0.9, speed=0.95)
    r = ct.check_phase_transition("prec_speed", intensity_threshold=0.8)
    print(f"OK (transition={r is not None})")

def test_dialectical_phase():
    print("6. PhaseTransition...", end=" ")
    ptm = PhaseTransitionMonitor("smoke")
    ptm.register_metric("stale", {"warn": (0.3, Phase.TRANSITIONING), "crit": (0.7, Phase.LEAPING)})
    ptm.record("stale", 0.2)
    assert ptm.get_phase("stale") == Phase.DORMANT
    t = ptm.record("stale", 0.4)
    assert t is not None
    assert ptm.get_phase("stale") == Phase.TRANSITIONING
    print(f"OK ({t.to_phase.value})")

def test_historical_attribution():
    print("7. AttributionLoop...", end=" ")
    al = AttributionLoop("smoke")
    al.record_incident("检索遗漏", "document_kb", 0.7)
    al.record_fix("检索遗漏", "升级层次分块", True)
    causes = al.find_root_cause("检索遗漏")
    assert len(causes) > 0
    print(f"OK (top={causes[0][0]})")

def test_historical_layering():
    print("8. LayeringTracker...", end=" ")
    lt = LayeringTracker("smoke")
    lt.register_layer("L0工具层", 0, ["tool"])
    lt.register_layer("L1学习层", 1, ["learn"], depends_on=["L0工具层"])
    lt.register_layer("L2推理层", 2, ["reason", "tool"], depends_on=["L1学习层"])
    emergents = lt.check_emergence()
    print(f"OK (layers={lt.get_stats()['layers']}, emergent={len(emergents)})")

def test_historical_consensus():
    print("9. ConsensusMeasure...", end=" ")
    cm = ConsensusMeasure("smoke")
    cm.start_experiment("chunk_method", "flat", "hierarchical")
    for _ in range(50):
        cm.record("chunk_method", "A", "precision", 0.72)
        cm.record("chunk_method", "B", "precision", 0.85)
    r = cm.evaluate("chunk_method")
    assert r.outcome == DecisionOutcome.B_WINS
    winner = cm.adopt("chunk_method")
    assert winner == "B"
    print(f"OK (B wins, +{r.improvement:.1%})")

def test_integration():
    print("10. Cross-logic...", end=" ")
    e = RuleEngine("smoke")
    b = BayesianReasoner("smoke")
    b.add_hypothesis("alarm_real", 0.3)
    b.add_evidence("rule_fired", 0.85, 0.15)
    e.assert_fact("motion", True)
    e.add_rule(Rule("motion_alarm", ["motion"], conclusion="alarm"))
    e.forward_chain()
    b.update("alarm_real", "rule_fired")
    assert b.belief("alarm_real") > 0.3
    print("OK")


def main():
    print("=" * 60)
    print("  Reasoning Layer Smoke Test (Four Logics)")
    print("=" * 60)

    tests = [
        test_formal_rule_engine,
        test_formal_syllogism,
        test_mathematical_kr,
        test_mathematical_bayes,
        test_dialectical_contradiction,
        test_dialectical_phase,
        test_historical_attribution,
        test_historical_layering,
        test_historical_consensus,
        test_integration,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 60)
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
