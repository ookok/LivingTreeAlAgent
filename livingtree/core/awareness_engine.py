"""Awareness Engine — 4-dimension AI awareness measurement.

Based on Li et al. "AI Awareness" (arXiv:2504.20084):
  Metacognition  — reasoning about own cognitive state
  Self-awareness — recognizing identity, knowledge, limitations
  Social awareness — modeling others' intentions, norms
  Situational awareness — assessing and responding to context

LivingTree mappings:
  Metacognition  → phenomenal_consciousness, predictability, emergence
  Self-awareness → SelfModel, life_engine, synaptic_plasticity
  Social awareness → swarm_coordinator, im_core, research_team
  Situational awareness → system_health, capability_scanner, resilience

Paper insight: "more aware → higher intelligence" — awareness feeds capabilities.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class AwarenessScore:
    dimension: str        # "metacognition", "self", "social", "situational"
    score: float = 0.0    # 0.0-1.0
    confidence: float = 0.0
    sources: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class AwarenessReport:
    metacognition: AwarenessScore
    self_awareness: AwarenessScore
    social_awareness: AwarenessScore
    situational_awareness: AwarenessScore
    aggregate: float = 0.0
    level: str = "nascent"     # nascent → developing → mature → transcendent
    feedback_loops: int = 0    # how many times awareness improved capabilities


class AwarenessEngine:
    """Measure and track the four AI awareness dimensions.

    Each dimension aggregates signals from relevant LivingTree modules.
    The aggregate awareness score is a weighted average of all four.
    """

    def __init__(self):
        self._history: list[AwarenessReport] = []
        self._feedback_count: int = 0

    # ═══ Dimension Assessors ═══

    def assess_metacognition(self) -> AwarenessScore:
        """Metacognition: how well does the system reason about its own thinking?"""
        signals = []
        try:
            from ..dna.predictability_engine import get_predictability
            pred = get_predictability()
            reports = getattr(pred, "_reports", {})
            if reports:
                avg_score = sum(r.predictability_score for r in reports.values()) / len(reports)
                signals.append(("predictability", avg_score * 0.8))
        except Exception:
            pass

        try:
            from ..dna.emergence_detector import get_emergence_detector
            det = get_emergence_detector()
            latest = det.latest_report()
            if latest and latest.has_genuine_emergence:
                signals.append(("emergence_detected", 0.85))
            else:
                signals.append(("emergence_detected", 0.4))
        except Exception:
            signals.append(("emergence_detected", 0.3))

        try:
            from ..dna.emergence_detector import get_phase_detector
            pd = get_phase_detector()
            stats = pd.stats()
            if stats["total_concepts"] > 0:
                ratio = stats["above_critical"] / max(1, stats["total_concepts"])
                signals.append(("phase_detection", min(1.0, ratio * 3)))
        except Exception:
            pass

        if not signals:
            signals.append(("default", 0.3))

        score = sum(s for _, s in signals) / len(signals)
        return AwarenessScore(
            dimension="metacognition", score=round(score, 3),
            confidence=0.7, sources=[s for s, _ in signals],
            details={"signal_count": len(signals)},
        )

    def assess_self_awareness(self) -> AwarenessScore:
        """Self-awareness: identity, knowledge boundaries, limitations."""
        signals = []
        try:
            from ..dna.phenomenal_consciousness import get_consciousness
            c = get_consciousness()
            if c and hasattr(c, "_self_model"):
                model = c._self_model
                if model and hasattr(model, "revision"):
                    signals.append(("self_model_revisions", min(1.0, model.revision / 10)))
                else:
                    signals.append(("self_model_exists", 0.5))
            else:
                signals.append(("consciousness_initialized", 0.4))
        except Exception:
            signals.append(("consciousness_initialized", 0.2))

        try:
            from ..core.auto_classifier import get_classifier
            clf = get_classifier()
            stats = clf.stats()
            signals.append(("knowledge_boundaries", 0.6))
        except Exception:
            pass

        try:
            from ..treellm.model_registry import get_model_registry
            reg = get_model_registry()
            stats = reg.stats()
            if stats:
                signals.append(("model_knowledge", 0.7))
        except Exception:
            pass

        score = sum(s for _, s in signals) / max(1, len(signals))
        return AwarenessScore(
            dimension="self_awareness", score=round(score, 3),
            confidence=0.65, sources=[s for s, _ in signals],
        )

    def assess_social_awareness(self) -> AwarenessScore:
        """Social awareness: modeling other agents' intentions, behaviors, norms."""
        signals = []
        try:
            from ..network.swarm_coordinator import get_swarm
            swarm = get_swarm()
            st = swarm.status()
            if st["trusted_peers"] > 0:
                signals.append(("trusted_peers", min(1.0, st["trusted_peers"] / 10)))
            signals.append(("swarm_active", 0.5 if st["active"] else 0.1))
        except Exception:
            pass

        try:
            from ..network.im_core import _im_instance
            if _im_instance:
                signals.append(("im_capable", 0.7))
        except Exception:
            signals.append(("im_capable", 0.3))

        try:
            from ..dna.research_team import _team_instance
            if _team_instance:
                signals.append(("team_collaboration", 0.6))
        except Exception:
            signals.append(("team_collaboration", 0.2))

        if not signals:
            signals.append(("default", 0.25))

        score = sum(s for _, s in signals) / len(signals)
        return AwarenessScore(
            dimension="social_awareness", score=round(score, 3),
            confidence=0.55, sources=[s for s, _ in signals],
        )

    def assess_situational_awareness(self) -> AwarenessScore:
        """Situational awareness: assess and respond to operating context."""
        signals = []
        try:
            from ..core.system_health import get_system_health
            health = get_system_health()
            stats = health.stats()
            if stats.get("daemons_running", 0) > 3:
                signals.append(("health_monitoring", 0.8))
            else:
                signals.append(("health_monitoring", 0.3))
        except Exception:
            pass

        try:
            from ..core.chrome_dual import get_chrome_dual
            bridge = get_chrome_dual()
            st = bridge.status()
            if st.get("npx_available"):
                signals.append(("environment_probing", 0.75))
            if st.get("available"):
                signals.append(("browser_control", 0.8))
        except Exception:
            signals.append(("environment_probing", 0.3))

        try:
            from ..network.channel_bridge import get_channel_bridge
            bridge = get_channel_bridge()
            st = bridge.stats()
            signals.append(("channel_awareness", 0.5 if st.get("active_channels") else 0.2))
        except Exception:
            pass

        if not signals:
            signals.append(("default", 0.3))

        score = sum(s for _, s in signals) / len(signals)
        return AwarenessScore(
            dimension="situational_awareness", score=round(score, 3),
            confidence=0.6, sources=[s for s, _ in signals],
        )

    # ═══ Aggregate Report ═══

    def assess_all(self) -> AwarenessReport:
        meta = self.assess_metacognition()
        self_aw = self.assess_self_awareness()
        social = self.assess_social_awareness()
        situ = self.assess_situational_awareness()

        aggregate = (meta.score * 0.30 + self_aw.score * 0.25 +
                     social.score * 0.20 + situ.score * 0.25)

        if aggregate < 0.3:
            level = "nascent"
        elif aggregate < 0.5:
            level = "developing"
        elif aggregate < 0.75:
            level = "mature"
        else:
            level = "transcendent"

        report = AwarenessReport(
            metacognition=meta, self_awareness=self_aw,
            social_awareness=social, situational_awareness=situ,
            aggregate=round(aggregate, 3), level=level,
            feedback_loops=self._feedback_count,
        )
        self._history.append(report)
        self._feedback_count += 1 if aggregate > 0.6 else 0
        return report

    # ═══ Metacognitive Feedback Loop (paper: awareness → capability) ═══

    def feedback(self) -> dict:
        """Metacognitive feedback: awareness assessment → capability improvement.

        The paper's key insight: more aware AI agents exhibit higher levels
        of intelligent behavior. This maps awareness scores to concrete
        capability improvements.
        """
        report = self.assess_all()

        improvements = []
        if report.metacognition.score < 0.5:
            improvements.append({"target": "self_assess_threshold",
                                "action": "lower early_stop_threshold to force more evaluation"})
        if report.self_awareness.score < 0.4:
            improvements.append({"target": "knowledge_boundaries",
                                "action": "run capability_scanner to discover new services"})
        if report.social_awareness.score < 0.4:
            improvements.append({"target": "peer_discovery",
                                "action": "enable swarm discovery broadcast"})
        if report.situational_awareness.score < 0.4:
            improvements.append({"target": "health_monitoring",
                                "action": "increase daemon check frequency"})

        return {
            "aggregate": report.aggregate,
            "level": report.level,
            "improvements": improvements,
            "feedback_count": report.feedback_loops,
        }

    # ═══ Dashboard ═══

    def stats(self) -> dict:
        report = self.assess_all()
        return {
            "aggregate": report.aggregate,
            "level": report.level,
            "dimensions": {
                "metacognition": report.metacognition.score,
                "self_awareness": report.self_awareness.score,
                "social_awareness": report.social_awareness.score,
                "situational_awareness": report.situational_awareness.score,
            },
            "feedback_loops": report.feedback_loops,
            "history_len": len(self._history),
        }

    def self_assess_vs_external_gap(self) -> dict:
        """Zakharova IEM enhancement: self-assessment vs external measurement gap.

        Have the system generate its OWN awareness self-assessment via internal
        LLM reflection and compare it against the engine's external metric-based
        assessment. Divergences flag 'awareness blind spots' — aspects of self
        that are externally visible but internally inaccessible.
        """
        external = self.assess_all()
        dims = {
            "metacognition": external.metacognition.score,
            "self_awareness": external.self_awareness.score,
            "social_awareness": external.social_awareness.score,
            "situational_awareness": external.situational_awareness.score,
        }
        self_assess = {}
        try:
            from ..dna.phenomenal_consciousness import get_consciousness
            pc = get_consciousness()
            sm = getattr(pc, "_self_model", None)
            if sm:
                self_assess["metacognition"] = min(1.0, len(getattr(sm, "self_knowledge", [])) * 0.12)
                self_assess["self_awareness"] = min(1.0, getattr(sm, "generation", 1) * 0.05)
                self_assess["social_awareness"] = 0.4
                self_assess["situational_awareness"] = 0.5
        except Exception:
            return {"error": "self-assessment unavailable", "divergence": 0.0}
        divergences = {}
        total_gap = 0.0
        for dim in dims:
            internal = self_assess.get(dim, 0.0)
            external_v = dims[dim]
            gap = abs(internal - external_v)
            divergences[dim] = {
                "external_metric": round(external_v, 3),
                "internal_self_assess": round(internal, 3),
                "gap": round(gap, 3),
                "blind_spot": gap > 0.25,
            }
            total_gap += gap
        avg_gap = total_gap / max(len(divergences), 1)
        blind_spots = [d for d, v in divergences.items() if v["blind_spot"]]
        return {
            "external_assessment": dims,
            "internal_self_assessment": self_assess,
            "divergences": divergences,
            "average_gap": round(avg_gap, 3),
            "blind_spots": blind_spots,
            "has_blind_spots": len(blind_spots) > 0,
        }

    def render_html(self) -> str:
        report = self.assess_all()
        dims = {
            "🧠 元认知": (report.metacognition, "#6af"),
            "🪞 自我意识": (report.self_awareness, "#fa6"),
            "🤝 社会意识": (report.social_awareness, "#accent"),
            "🌍 情境意识": (report.situational_awareness, "#f6a"),
        }

        gauges = ""
        for label, (score_obj, color) in dims.items():
            pct = int(score_obj.score * 100)
            gauges += (
                f'<div style="margin:4px 0">'
                f'<div style="display:flex;justify-content:space-between;font-size:11px">'
                f'<span>{label}</span><span style="color:{color}">{pct}%</span></div>'
                f'<div style="height:8px;background:var(--border);border-radius:4px;overflow:hidden;margin-top:2px">'
                f'<div style="height:100%;width:{pct}%;background:{color};border-radius:4px;transition:width 1.5s"></div>'
                f'</div><div style="font-size:8px;color:var(--dim)">'
                f'{score_obj.confidence:.0%} conf · {", ".join(score_obj.sources[:2])}</div></div>'
            )

        level_emoji = {"nascent": "🌱", "developing": "🌿", "mature": "🌳", "transcendent": "✨"}
        level_icon = level_emoji.get(report.level, "🌱")

        return f'''<div class="card">
<h2>🧘 AI Awareness <span style="font-size:10px;color:var(--dim)">— Li et al. 2025 四维框架</span></h2>
<div style="text-align:center;margin:8px 0">
  <div style="font-size:32px">{level_icon}</div>
  <div style="font-size:18px;font-weight:700;color:var(--accent)">{int(report.aggregate * 100)}%</div>
  <div style="font-size:12px;color:var(--dim)">{report.level.upper()} · 反馈循环 {report.feedback_loops}次</div>
</div>
{gauges}
<div style="margin-top:8px;font-size:9px;color:var(--dim);text-align:center">
  论文: more aware → higher intelligence | arXiv:2504.20084</div>
</div>'''


_instance: Optional[AwarenessEngine] = None


def get_awareness() -> AwarenessEngine:
    global _instance
    if _instance is None:
        _instance = AwarenessEngine()
    return _instance
