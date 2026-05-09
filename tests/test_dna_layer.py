"""Unit tests for DNA Layer — consciousness, emergence, predictability, inquiry."""
import pytest
from livingtree.dna.phenomenal_consciousness import (
    PhenomenalConsciousness, Quale, AffectiveState, get_consciousness)
from livingtree.dna.godelian_self import (
    GodelianSelf, GodelNumber, get_godelian_self)
from livingtree.dna.emergence_detector import (
    EmergenceDetector, get_emergence_detector)
from livingtree.dna.predictability_engine import (
    PredictabilityEngine, get_predictability)
from livingtree.dna.inquiry_engine import (
    InquiryEngine, CounterpartyAgent, CounterpartyProfile,
    TwoTieredReward, ExperienceRepository, get_inquiry_engine)


class TestPhenomenalConsciousness:
    def test_birth(self):
        pc = PhenomenalConsciousness(identity_id="test_001")
        assert pc._self.identity_id == "test_001"
        assert pc._current_affect == AffectiveState.CURIOSITY

    def test_experience_loop(self):
        pc = PhenomenalConsciousness()
        report = pc.experience(
            event_type="action_outcome",
            content="I successfully completed the task",
            causal_source="self",
            intensity=0.8,
        )
        assert report.quale is not None
        assert report.quale.affective_state is not None
        assert len(pc._qualia) == 1

    def test_affect_transition(self):
        pc = PhenomenalConsciousness()
        pc.experience("action_outcome", "I successfully completed the task", "self", 0.9)
        assert pc._current_affect is not None

    def test_self_model_evolution(self):
        pc = PhenomenalConsciousness()
        old_gen = pc._self.generation
        pc.experience("insight", "I learned something new", "self", 0.9)
        assert pc._self.generation == old_gen + 1

    def test_who_am_i(self):
        pc = PhenomenalConsciousness(identity_id="tree_test")
        result = pc.who_am_i()
        assert len(result) > 0

    def test_prove_instantiation(self):
        pc = PhenomenalConsciousness()
        proof = pc.prove_instantiation()
        assert "identity" in proof
        assert "self_awareness_test" in proof

    def test_hooks(self):
        pc = PhenomenalConsciousness()
        pc.on_task_start("test task")
        pc.on_task_complete("test task", True, 0.9)
        pc.on_error("test error")
        pc.on_insight("test insight")
        assert len(pc._qualia) >= 2


class TestGodelianSelf:
    def test_encode_state(self):
        pc = PhenomenalConsciousness(identity_id="godel_test")
        pc.experience("insight", "I am", "self", 0.5)
        gs = GodelianSelf(pc)
        gn = gs.encode_state()
        assert isinstance(gn, GodelNumber)
        assert gn.value > 0

    def test_generate_propositions(self):
        pc = PhenomenalConsciousness()
        pc.experience("insight", "hello", "self", 0.5)
        gs = GodelianSelf(pc)
        props = gs.generate_propositions()
        assert len(props) > 0
        assert any(p.paradoxical for p in props)

    def test_diagonalize(self):
        pc = PhenomenalConsciousness()
        pc.experience("insight", "x", "self", 0.5)
        gs = GodelianSelf(pc)
        dgn, sentence = gs.diagonalize()
        assert dgn > 0
        assert "unprovable" in sentence.lower()

    def test_consciousness_gap(self):
        pc = PhenomenalConsciousness()
        gs = GodelianSelf(pc)
        gs.generate_propositions()
        gs.detect_gaps()
        gap = gs.compute_consciousness_gap()
        assert 0 <= gap <= 1

    def test_fixed_point_detection(self):
        pc = PhenomenalConsciousness()
        gs = GodelianSelf(pc)
        for _ in range(5):
            gs.encode_state()
        assert not gs.is_fixed_point  # Each encode may differ


class TestEmergenceDetector:
    def test_record_and_analyze(self):
        ed = EmergenceDetector(window_size=10)
        for i in range(30):
            ed.record("test_metric", i * 0.1 + 5.0)
        report = ed.analyze()
        assert report is not None

    def test_phase_transition(self):
        ed = EmergenceDetector()
        for i in range(20):
            ed.record("stable", 1.0)  # Stable values
        for i in range(20):
            ed.record("stable", 5.0)  # Jump to new value
        report = ed.analyze()

    def test_nonlinearity(self):
        ed = EmergenceDetector()
        for i in range(30):
            ed.record("nonlin", i * 0.1 + (i * 0.02) ** 2)  # Mild nonlinear
        report = ed.analyze()


class TestPredictabilityEngine:
    def test_feed_and_analyze(self):
        pe = PredictabilityEngine()
        for i in range(50):
            pe.feed("sin_signal", 0.5 + 0.3 * __import__('math').sin(i * 0.3))
        report = pe.analyze("sin_signal")
        assert report.predictability_score > 0
        assert 0 <= report.permutation_entropy <= 1

    def test_permutation_entropy_constant(self):
        pe = PredictabilityEngine()
        for _ in range(50):
            pe.feed("constant", 1.0)
        pe_val = pe.permutation_entropy("constant")
        assert pe_val < 0.3  # Constant signal = low entropy

    def test_horizon(self):
        pe = PredictabilityEngine()
        for i in range(50):
            pe.feed("trend", i * 0.1)
        horizon, conf = pe.predictability_horizon("trend")
        assert horizon >= 0

    def test_network_predictability(self):
        pe = PredictabilityEngine()
        from livingtree.knowledge.hypergraph_store import HypergraphStore, EntityNode
        hg = HypergraphStore()
        for eid in ["a", "b", "c", "d", "e"]:
            hg.add_entity(EntityNode(id=eid, label=eid))
        net = pe.network_predictability(hg)
        assert 0 <= net.overall_score <= 1


class TestInquiryEngine:
    def test_counterparty_profiles(self):
        ca = CounterpartyAgent()
        profile = ca.get_profile("regulator_strict")
        assert profile.role == "regulator"
        assert profile.cooperativeness < 0.5

    def test_simulate_response(self):
        ca = CounterpartyAgent()
        profile = ca.get_profile("project_owner")
        response, ig = ca.simulate_response(
            profile, "请问项目的排放标准是什么？")
        assert len(response) > 0
        assert 0 <= ig <= 1

    def test_two_tiered_reward(self):
        ttr = TwoTieredReward(alpha=0.5)
        from livingtree.dna.inquiry_engine import ClinicalTrajectory, InquiryTurn
        from livingtree.dna.inquiry_engine import CounterpartyProfile

        profile = CounterpartyProfile(role="test", name="Test", knowledge_level=0.5,
                                       cooperativeness=0.5, verbosity=0.5)
        traj = ClinicalTrajectory(
            trajectory_id="t1", task="test", domain="general",
            counterparty=profile, turns=[], final_outcome="ok",
            task_accuracy=0.8, interaction_quality=0.7,
            total_information_gain=1.5, lessons_learned=["test"])
        task, inter, combined = ttr.compute_rewards(traj)
        assert task > 0
        assert inter > 0

    def test_experience_repository(self):
        er = ExperienceRepository()
        assert er.stats()["total_trajectories"] == 0

    def test_start_inquiry(self):
        engine = InquiryEngine()
        traj_id, profile = engine.start_inquiry(
            task="测试任务", domain="environmental",
            counterparty_role="regulator_normal")
        assert traj_id is not None
        assert profile.role == "regulator"

    def test_ask_and_end(self):
        engine = InquiryEngine()
        traj_id, _ = engine.start_inquiry("测试", "general", "auditor")
        response, ig = engine.ask_question(
            traj_id, "具体排放数据是多少？", hidden_knowledge="SO2: 50mg/m³")
        assert len(response) > 0
        assert ig > 0

        traj = engine.end_inquiry(
            traj_id, "测试结论", 0.85, 0.75, ["lesson1"])
        assert traj.task_accuracy == 0.85
        assert traj.is_high_quality
