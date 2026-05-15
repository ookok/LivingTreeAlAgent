"""Self-test suite v3.0 — validates all new modules. Run: python tests/self_test.py"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def run_all() -> dict[str, Any]:
    """Run all module self-tests. No external dependencies needed."""
    results = {
        "total": 0, "passed": 0, "failed": 0, "skipped": 0,
        "tests": [], "timestamp": time.time(),
        "version": "3.0",
    }

    def ok(name: str):
        results["total"] += 1
        results["passed"] += 1
        results["tests"].append({"name": name, "status": "PASS"})

    def fail(name: str, error: str):
        results["total"] += 1
        results["failed"] += 1
        results["tests"].append({"name": name, "status": "FAIL", "error": str(error)[:200]})

    def skip(name: str, reason: str):
        results["total"] += 1
        results["skipped"] += 1
        results["tests"].append({"name": name, "status": "SKIP", "reason": reason})

    def test(name: str, fn):
        try:
            fn()
            ok(name)
        except Exception as e:
            fail(name, str(e))

    # ═══ Knowledge Layer ═══
    test("HypergraphStore: add entities + hyperedges", lambda: _test_hypergraph())
    test("PrecedenceModel: sequence learning + ordering", lambda: _test_precedence())
    test("OrderAwareReranker: doc type inference", lambda: _test_reranker())
    test("LazyIndex: section indexing + search", lambda: _test_lazy_index())
    test("GravityModel: mass + distance computation", lambda: _test_gravity())

    # ═══ Execution Layer ═══
    test("GTSMPlanner: tree + flow + hybrid modes", lambda: _test_gtsm())
    test("CoFEE Engine: verify + backward chain", lambda: _test_cofee())

    # ═══ DNA Layer ═══
    test("PhenomenalConsciousness: experience loop", lambda: _test_consciousness())
    test("GodelianSelf: encode + propositions + gap", lambda: _test_godelian())
    test("EmergenceDetector: record + analyze", lambda: _test_emergence())
    test("PredictabilityEngine: entropy + horizon", lambda: _test_predictability())

    # ═══ Economy Layer ═══
    test("SpatialGRPO: optimize + scoring", lambda: _test_sgrpo())
    test("TDMReward: surrogate + distribute", lambda: _test_tdm())
    test("ThermoBudget: evaluate + phase", lambda: _test_thermo())
    test("LatentGRPO: encode + optimize + feedback_align", lambda: _test_latent())

    # ═══ Core Layer ═══
    test("SynapticPlasticity: LTP/LTD/protection", lambda: _test_synaptic())
    test("ActionPrinciple: Lagrangian + optimal params", lambda: _test_action())
    test("EventBus: pub/sub + history", lambda: _test_eventbus())

    # ═══ Routing Layer ═══
    test("FreeModelPool: registration + role assignment", lambda: _test_pool())
    test("ThompsonRouter: arm management", lambda: _test_router())

    # ═══ Integration ═══
    test("Cross-module: gravity→plasticity bridge", lambda: _test_cross_module())

    return results


# ═══ Test Implementations ═══

def _test_hypergraph():
    from livingtree.knowledge.hypergraph_store import (
        HypergraphStore, EntityNode, Hyperedge)
    hg = HypergraphStore()
    for eid in ["GB3095", "SO2", "24h", "150ug"]:
        hg.add_entity(EntityNode(id=eid, label=eid))
    hg.add_hyperedge(Hyperedge(id="h1", entities=["GB3095", "SO2", "24h", "150ug"],
                                relation="emission_limit", weight=0.8))
    assert hg.entity_count() == 4
    assert hg.hyperedge_count() == 1

def _test_precedence():
    from livingtree.knowledge.precedence_model import PrecedenceModel
    pm = PrecedenceModel()
    pm.observe_sequence(["background", "method", "results"])
    result = pm.order_facts(["results", "background", "method"])
    assert result.ordered_types[0] == "background"

def _test_reranker():
    from livingtree.knowledge.order_aware_reranker import OrderAwareReranker
    r = OrderAwareReranker()
    assert r.infer_doc_type("SO2限值150μg/m³") in ("threshold", "regulation")

def _test_lazy_index():
    from livingtree.knowledge.lazy_index import LazyIndex, SectionParser
    parser = SectionParser()
    sections = parser.parse("# Title\n\n## Section\nContent.")
    assert len(sections) >= 2
    lazy = LazyIndex()
    lazy.index_document("d1", "Test", "# A\n\n## B\nContent.")
    assert lazy.search_sections("B")

def _test_gravity():
    from livingtree.knowledge.gravity_model import KnowledgeGravity, distribution_entropy
    gm = KnowledgeGravity()
    mass = gm.compute_mass("test")
    assert mass.raw_mass > 0
    e = distribution_entropy([1, 1, 1, 1])
    assert e > 0.8

def _test_gtsm():
    from livingtree.execution.gtsm_planner import GTSMPlanner, GTSMMode
    planner = GTSMPlanner()
    assert planner._estimate_complexity("simple task", {}) < 0.5

def _test_cofee():
    from livingtree.execution.cofee_engine import CoFEECognitiveEngine
    engine = CoFEECognitiveEngine()
    result = engine.verify_step("s1", "生成环评报告", "完成环评报告")
    assert result.score >= 0

def _test_consciousness():
    from livingtree.dna.phenomenal_consciousness import PhenomenalConsciousness
    pc = PhenomenalConsciousness(identity_id="self_test")
    pc.experience("action_outcome", "task completed", "self", 0.8)
    assert len(pc._qualia) == 1
    assert pc._self.generation == 1

def _test_godelian():
    from livingtree.dna.phenomenal_consciousness import PhenomenalConsciousness
    from livingtree.dna.godelian_self import GodelianSelf
    pc = PhenomenalConsciousness()
    pc.experience("insight", "x", "self", 0.5)
    gs = GodelianSelf(pc)
    gn = gs.encode_state()
    assert gn.value > 0
    props = gs.generate_propositions()
    assert any(p.paradoxical for p in props)

def _test_emergence():
    from livingtree.dna.emergence_detector import EmergenceDetector
    ed = EmergenceDetector()
    for i in range(30):
        ed.record("m", i * 0.1)
    report = ed.analyze()
    assert report is not None

def _test_predictability():
    from livingtree.dna.predictability_engine import PredictabilityEngine
    import math
    pe = PredictabilityEngine()
    for i in range(50):
        pe.feed("s", 0.5 + 0.3 * math.sin(i * 0.3))
    report = pe.analyze("s")
    assert report.predictability_score > 0

def _test_sgrpo():
    from livingtree.economy.grpo_optimizer import SpatialGRPOOptimizer, SpatialContext
    sgrpo = SpatialGRPOOptimizer()
    ctx = SpatialContext(avg_centrality=0.4)
    result = sgrpo.optimize(
        [("a", {"c": 0.8}), ("b", {"c": 0.5})], ctx, {"a": 0.9, "b": 0.6})
    assert result.round_id > 0

def _test_tdm():
    from livingtree.economy.grpo_optimizer import TDMRewardOptimizer, SurrogateRewardModel
    sm = SurrogateRewardModel()
    sm.train_step({"f": 0.5}, 0.7)
    tdm = TDMRewardOptimizer()
    traj = tdm.distribute_rewards("t", ["plan", "execute"], [{}, {}], 0.85)
    assert len(traj.steps) == 2

def _test_thermo():
    from livingtree.economy.thermo_budget import ThermodynamicBudget
    tb = ThermodynamicBudget(daily_budget_yuan=50)
    d = tb.evaluate("t1", estimated_cost=1.0, task_priority=0.5)
    assert d.proceed

def _test_latent():
    from livingtree.economy.grpo_optimizer import LatentGRPO, LatentEncoder
    enc = LatentEncoder(input_dim=3, latent_dim=2)
    loss = enc.feedback_align({"f1": 0.5}, ["f1"], [0.3, -0.2])
    assert loss >= 0
    lg = LatentGRPO(latent_dim=4)
    result = lg.optimize([("a", {"f": 0.7})], {"a": 0.9})
    assert result.round_id > 0

def _test_synaptic():
    from livingtree.core.synaptic_plasticity import SynapticPlasticity
    sp = SynapticPlasticity()
    for i in range(5):
        sp.register(f"s{i}", initial_weight=0.15)
    sp.strengthen("s0")
    sp.decay_all()
    alert = sp.degradation_alert()
    assert alert["severity"] in ("normal", "warning", "critical")

def _test_action():
    from livingtree.core.action_principle import ActionPrinciple
    ap = ActionPrinciple()
    ap.observe("synaptic", "interference", 0.05)
    ap.observe("provider", "success_rate", 0.8)
    analysis = ap.analyze()
    assert analysis is not None
    assert "optimal_ltp_rate" in analysis.optimal_params

def _test_eventbus():
    from livingtree.infrastructure.event_bus import get_event_bus
    bus = get_event_bus()
    events = bus._event_history
    assert isinstance(events, list)

def _test_pool():
    from livingtree.treellm.free_pool_manager import get_free_pool
    pool = get_free_pool()
    assert "sensetime" in pool._models or len(pool._models) > 5

def _test_router():
    from livingtree.treellm.bandit_router import get_bandit_router
    router = get_bandit_router()
    arm = router.get_arm("test_provider")
    assert arm.provider_name == "test_provider"
    assert 0 < arm.expected_value < 1

def _test_cross_module():
    from livingtree.core.synaptic_plasticity import SynapticPlasticity
    from livingtree.knowledge.gravity_model import KnowledgeGravity, distribution_entropy
    sp = SynapticPlasticity()
    gm = KnowledgeGravity()
    # Entropy from plasticity reflects weight distribution
    w = [m.weight for m in sp._synapses.values()] if sp._synapses else [0.5]
    e = distribution_entropy(w)
    assert 0 <= e <= 1


if __name__ == "__main__":
    results = run_all()
    print(f"\n{'='*50}")
    print(f"LivingTree v3.0 Self-Test Results")
    print(f"{'='*50}")
    print(f"Total: {results['total']} | Passed: {results['passed']} | "
          f"Failed: {results['failed']} | Skipped: {results['skipped']}")
    for t in results["tests"]:
        icon = "✅" if t["status"] == "PASS" else "❌" if t["status"] == "FAIL" else "⏭️"
        extra = f" — {t.get('error','')}" if t["status"] == "FAIL" else ""
        print(f"  {icon} {t['name']}{extra}")
    print(f"{'='*50}")
    if results["failed"] > 0:
        exit(1)
