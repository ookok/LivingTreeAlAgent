"""Test data modules: lineage, trust, binding, practice, domain transfer."""
import time
from pathlib import Path

import pytest


class TestDataLineage:
    def test_record_and_trace(self):
        from livingtree.capability.data_lineage import get_data_lineage, DataLineage
        dl = DataLineage()
        dl.record("sec1.1", "capacity", 300, unit="吨/日", derivation="user_provided")
        dl.record("sec3.1", "emission", 1.2, source="sec1.1_capacity", derivation="computed",
                  derived_from=["sec1.1_capacity"])
        descent = dl.trace_forward("sec1.1_capacity")
        assert len(descent) >= 1, f"Expected >=1 downstream, got {len(descent)}"

    def test_propagate(self):
        from livingtree.capability.data_lineage import get_data_lineage, DataLineage
        dl = DataLineage()
        dl.record("sec1", "x", 100, derivation="user_provided")
        dl.record("sec2", "y", 100, source="sec1_x", derivation="direct_copy")
        result = dl.propagate("sec1_x", 200)
        assert result["total_affected"] >= 1

    def test_summary(self):
        from livingtree.capability.data_lineage import get_data_lineage
        dl = get_data_lineage()
        dl.record("sec1", "a", 1, derivation="user_provided")
        dl.record("sec2", "b", 2, derivation="assumed", confidence=0.3)
        s = dl.summary()
        assert s["total_nodes"] >= 1


class TestTrustScoring:
    def test_record_and_score(self):
        from livingtree.observability.trust_scoring import get_trust_scorer
        ts = get_trust_scorer()
        for _ in range(10):
            ts.record("test_agent", success=True, latency_ms=100)
        score = ts.score("test_agent")
        assert score >= 70, f"Expected high trust score, got {score}"

    def test_failures_lower_score(self):
        from livingtree.observability.trust_scoring import get_trust_scorer, TrustScorer
        ts = TrustScorer()
        for _ in range(5):
            ts.record("flaky_agent", success=False)
        score = ts.score("flaky_agent")
        assert score < 50, f"Expected low trust score, got {score}"

    def test_trust_level(self):
        from livingtree.observability.trust_scoring import get_trust_scorer, TrustScorer
        ts = TrustScorer()
        for _ in range(20):
            ts.record("expert", success=True)
        level = ts.trust_level("expert")
        assert level in ("🟢 trusted", "🟡 reliable")


class TestSessionBinding:
    def test_stickiness_bonus(self):
        from livingtree.treellm.session_binding import SessionBinding
        sb = SessionBinding()
        sb.bind("sid1", "deepseek")
        bonus = sb.stickiness_score("sid1", "deepseek")
        assert bonus > 0, f"Expected sticky bonus, got {bonus}"
        bonus_diff = sb.stickiness_score("sid1", "other_model")
        assert bonus_diff == 0.0

    def test_should_switch_rate_limit(self):
        from livingtree.treellm.session_binding import SessionBinding
        sb = SessionBinding()
        sb.bind("sid1", "deepseek")
        should, reason = sb.should_switch("sid1", "nvidia", "429 rate limited")
        assert should is True

    def test_should_not_switch_sticky(self):
        from livingtree.treellm.session_binding import SessionBinding
        sb = SessionBinding()
        sb.bind("sid1", "deepseek")
        should, reason = sb.should_switch("sid1", "nvidia", "")
        assert should is False, f"Should stay sticky, got: {reason}"

    def test_preference_lock(self):
        from livingtree.treellm.session_binding import SessionBinding
        sb = SessionBinding()
        sb.set_preference("sid1", "deepseek")
        should, _ = sb.should_switch("sid1", "nvidia", "cost saving")
        assert should is False  # locked


class TestAdaptivePractice:
    def test_record_and_detect(self):
        from livingtree.capability.adaptive_practice import AdaptivePractice
        ap = AdaptivePractice()
        for _ in range(5):
            ap.record_modification("环评报告", "sec4.2", modified_chars=200, total_chars=500)
        for _ in range(5):
            ap.record_modification("安全评价", "sec2.1", modified_chars=50, total_chars=500)
        weak = ap.detect_weaknesses(3)
        assert len(weak) >= 1


class TestDomainTransfer:
    def test_extract_principles(self):
        from livingtree.capability.domain_transfer import get_domain_transfer
        dt = get_domain_transfer()
        principles = dt.extract_principles(min_confidence=0.0)
        assert isinstance(principles, list)


class TestProgressiveTrust:
    def test_record_and_profile(self):
        from livingtree.capability.progressive_trust import get_progressive_trust
        pt = get_progressive_trust()
        for _ in range(10):
            pt.record_interaction("user_test", "大气预测", user_confirmed=True)
        profile = pt.get_user_profile("user_test")
        assert profile is not None
        assert "大气预测" in str(profile.get("expertise", {}))
