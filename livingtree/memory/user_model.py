"""UserModel — unified user memory integrating 6 scattered modules.

Previously fragmented across:
  persona_memory.py  — 6-domain structured facts (biography/preferences/work/...)
  advanced.py        — implicit habits (DigitalTwin: peak hours, verbosity, negation)
  struct_mem.py      — LLM-extracted opinions and preferences
  session_binding.py — /prefer model lock
  meta_memory.py     — strategy preference tracking
  progressive_trust.py — user trust scoring

Now: single UserModel.inject_into_prompt() builds compact user profile for
system prompt injection. All sources merged, no duplicates, priority-ordered.

Three memory layers:
  L1 指令: user corrections, explicit /prefer, named preferences
  L2 习惯: implicit patterns (verbosity, active hours, domain affinity)
  L3 环境: project context, working directory, model binding

v2.6 PersonaVLM (CVPR 2026): PEM momentum-based user personality evolution.
  - UserTraitVector: 7 latent user traits inferred from conversation
  - MomentumPersonalityUpdater: P_t = beta * P_{t-1} + (1-beta) * inferred
  - 10+ behavior signals for trait inference in observe_message()
  - Auto-wires to TraitEvolutionTree for longitudinal tracking

v2.7 Theory of Mind (ToM): cognitive empathy — what the user knows, wants, expects.
  - UserBeliefState: what the agent believes the user knows/doesn't know
  - KnowledgeGap: what the user is missing that they need for their task
  - ExpectationModel: what the user expects to happen next
  - EmpathySignal: emotional-cognitive state inference from conversation

Usage:
    model = get_user_model()
    model.record_correction("不要用高斯烟羽，用AERSCREEN")  # L1
    model.observe_message("帮我分析水质")                     # L2
    profile = model.inject_into_prompt()                      # → system prompt
    traits = model.get_user_traits()                          # PEM trait vector
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

USER_MODEL_DIR = Path(".livingtree/user")
USER_MODEL_FILE = USER_MODEL_DIR / "user_model.json"

MOMENTUM_BETA = 0.85

DEFAULT_TRAITS = {
    "engagement_depth": 0.50,
    "technical_sophistication": 0.50,
    "patience_tolerance": 0.70,
    "feedback_directness": 0.50,
    "topic_breadth": 0.40,
    "interaction_regularity": 0.50,
    "delegation_comfort": 0.50,
}

TRAIT_SIGNALS = {
    "engagement_depth": {
        "inc": ["追问", "深入", "详细", "原理", "为什么", "how does", "explain", "deep"],
        "dec": ["简单", "快速", "简短", "概述", "summary", "brief"],
    },
    "technical_sophistication": {
        "inc": ["框架", "架构", "优化", "部署", "Docker", "K8s", "API", "GPU"],
        "dec": ["基础", "入门", "初级", "新手", "beginner"],
    },
    "patience_tolerance": {
        "inc": ["再试", "继续", "没事", "重来", "retry", "again"],
        "dec": ["怎么又", "还是错", "不对", "还是不行", "wrong", "still"],
    },
    "feedback_directness": {
        "inc": ["不对", "错误", "不要", "改", "fix", "correct", "wrong"],
        "dec": ["建议", "也许", "可能", "maybe", "perhaps", "suggest"],
    },
    "topic_breadth": {"inc": [], "dec": []},
    "interaction_regularity": {"inc": [], "dec": []},
    "delegation_comfort": {
        "inc": ["帮我", "你来", "交给你", "你来处理", "handle", "delegate"],
        "dec": ["我自己", "我来改", "我看看", "let me check", "I'll do"],
    },
}

HABIT_SIGNALS = {
    "response_length_pref": ["简洁", "简单", "简短", "详细", "详细点", "长一点"],
    "question_frequency": ["?", "？", "怎么", "如何", "what", "how"],
    "emoji_usage": [],
    "technical_jargon_ratio": ["架构", "流水线", "优化", "延迟", "吞吐"],
    "decisiveness_score": ["确定", "直接", "就这个", "用这个"],
    "gratitude_frequency": ["谢谢", "感谢", "thanks", "thank"],
    "urgency_language_ratio": ["紧急", "快点", "尽快", "马上", "urgent", "ASAP"],
}


@dataclass
class UserBeliefState:
    """Theory of Mind: what the agent believes the user currently knows/wants.

    Models the user's mental state from observable conversation signals.
    Updated every turn — tracks the evolving "shared mental model."
    """
    known_topics: list[str] = field(default_factory=list)
    unknown_topics: list[str] = field(default_factory=list)
    stated_goals: list[str] = field(default_factory=list)
    implied_wants: list[str] = field(default_factory=list)
    frustration_level: float = 0.0
    satisfaction_level: float = 0.5
    attention_span: str = "normal"

    def gap_ratio(self) -> float:
        total = len(self.known_topics) + len(self.unknown_topics)
        if total == 0:
            return 0.0
        return len(self.unknown_topics) / total


@dataclass
class KnowledgeGap:
    """A specific knowledge gap: what the user doesn't know but needs for their task."""
    topic: str
    evidence: str
    severity: float = 0.5
    timestamp: float = field(default_factory=time.time)


@dataclass
class ExpectationModel:
    """What the user likely expects to happen next — based on conversation trajectory."""
    next_action_expected: str = ""
    expected_response_type: str = "answer"
    expected_detail_level: str = "medium"
    deadline_pressure: float = 0.0
    implicit_question: str = ""


@dataclass
class EmpathySignal:
    """Cognitive empathy: inferred emotional-cognitive state of the user."""
    primary_emotion: str = "neutral"
    secondary_emotion: str = ""
    confidence_level: float = 0.0
    cognitive_load: float = 0.3
    time_pressure: float = 0.0
    social_tone: str = "neutral"
    inferred_need: str = ""


@dataclass
class UserCorrection:
    """A user correction: 'don't do X, do Y instead'."""
    trigger: str
    correction: str
    category: str = "general"
    count: int = 1
    last_seen: float = field(default_factory=time.time)
    source: str = "explicit"

    def to_rule(self) -> str:
        return f"用户偏好: {self.correction} (而非{self.trigger})"


@dataclass
class UserHabit:
    """Implicitly learned user habit."""
    name: str
    value: float
    threshold: float = 0.0
    signal: str = ""


@dataclass
class UserTraitVector:
    """PersonaVLM PEM: 7 latent user personality traits from conversation behavior.

    Updated via momentum: P_t = beta * P_{t-1} + (1-beta) * inferred_trait
    """
    engagement_depth: float = 0.50
    technical_sophistication: float = 0.50
    patience_tolerance: float = 0.70
    feedback_directness: float = 0.50
    topic_breadth: float = 0.40
    interaction_regularity: float = 0.50
    delegation_comfort: float = 0.50
    generation: int = 0

    def to_dict(self) -> dict[str, float]:
        return {
            "engagement_depth": self.engagement_depth,
            "technical_sophistication": self.technical_sophistication,
            "patience_tolerance": self.patience_tolerance,
            "feedback_directness": self.feedback_directness,
            "topic_breadth": self.topic_breadth,
            "interaction_regularity": self.interaction_regularity,
            "delegation_comfort": self.delegation_comfort,
        }

    def trait_list(self) -> list[float]:
        return list(self.to_dict().values())

    def dominant_traits(self, threshold: float = 0.65) -> list[str]:
        return [k for k, v in self.to_dict().items() if v >= threshold]

    def low_traits(self, threshold: float = 0.35) -> list[str]:
        return [k for k, v in self.to_dict().items() if v <= threshold]


@dataclass
class UserProfile:
    corrections: list[UserCorrection] = field(default_factory=list)
    habits: list[UserHabit] = field(default_factory=list)
    domain_affinity: dict[str, int] = field(default_factory=dict)
    preferred_model: str = ""
    verbosity_avg: int = 0
    peak_hour: int = 9
    negation_ratio: float = 0.0
    project_context: str = ""
    last_updated: float = 0.0
    traits: UserTraitVector = field(default_factory=UserTraitVector)
    habit_signals: dict[str, float] = field(default_factory=dict)
    # v2.7 Theory of Mind
    belief_state: UserBeliefState = field(default_factory=UserBeliefState)
    knowledge_gaps: list[KnowledgeGap] = field(default_factory=list)
    expectation: ExpectationModel = field(default_factory=ExpectationModel)
    empathy_signal: EmpathySignal = field(default_factory=EmpathySignal)


class UserModel:
    """Unified user memory with three-layer architecture.

    L1: 指令 → explicit corrections, named preferences, model lock
    L2: 习惯 → implicit patterns from message observation
    L3: 环境 → project context, working directory, trust level
    """

    MAX_CORRECTIONS = 20
    CORRECTION_CONFIDENCE_THRESHOLD = 2

    def __init__(self):
        self.profile = UserProfile()
        self._synced = False
        self._persona = None  # Lazy-init PersonaMemory bridge
        self._load()
    
    @property
    def persona(self):
        """Lazy-init PersonaMemory for 6-domain structured persona extraction."""
        if self._persona is None:
            try:
                from .persona_memory import get_persona_memory
                self._persona = get_persona_memory()
            except Exception:
                self._persona = False  # Sentinel: not available
        return self._persona if self._persona is not False else None

    # ── L1: Explicit User Instructions ──

    def record_correction(self, statement: str, category: str = "general"):
        """Record a user correction: "don't use X, use Y" or "I prefer Z"."""
        trigger, correction = self._parse_correction(statement)

        for c in self.profile.corrections:
            if c.trigger == trigger and c.correction == correction:
                c.count += 1
                c.last_seen = time.time()
                self._save()
                return

        self.profile.corrections.append(UserCorrection(
            trigger=trigger, correction=correction,
            category=category, source="explicit",
        ))

        if len(self.profile.corrections) > self.MAX_CORRECTIONS:
            self.profile.corrections.sort(key=lambda c: -c.count)
            self.profile.corrections = self.profile.corrections[:self.MAX_CORRECTIONS]

        self._save()

    def set_preference(self, key: str, value: str):
        """Generic preference: user_prefs['model'] = 'deepseek'."""
        self.record_correction(f"偏好: {key}={value}", "preference")

    def get_instruction_rules(self) -> list[str]:
        """Get high-confidence user instruction rules for prompt injection."""
        rules = []
        for c in self.profile.corrections:
            if c.count >= self.CORRECTION_CONFIDENCE_THRESHOLD:
                rules.append(c.to_rule())
        return rules

    # ── L2: Implicit Habit Tracking ──

    def observe_message(self, message: str, auto_pro: bool = False):
        """Track implicit preferences from message content and metadata.

        v2.6 PersonaVLM: Also infers 7 latent personality traits + 7 habit signals
        via momentum-based PEM updates (beta=0.85).
        """
        hour = time.localtime().tm_hour
        msg_lower = message.lower()

        domain = self._detect_domain(message)
        if domain:
            self.profile.domain_affinity[domain] = (
                self.profile.domain_affinity.get(domain, 0) + 1)

        n = max(self.profile.verbosity_avg, 1) + 1
        self.profile.verbosity_avg = int(
            self.profile.verbosity_avg + (len(message) - self.profile.verbosity_avg) / n)

        if auto_pro:
            self.profile.habits.append(UserHabit(
                name="pro_model_trigger", value=1.0, signal="complex_query"))

        negations = sum(1 for w in ["不", "没", "别", "错误", "失败", "不行"]
                        if w in message)
        if negations > 0:
            old = self.profile.negation_ratio
            self.profile.negation_ratio = old + (1.0 - old) / n

        self.profile.peak_hour = hour
        self.profile.last_updated = time.time()

        self._infer_traits_from_message(msg_lower)
        self._update_habit_signals(msg_lower, n)

        self.infer_belief_state(message)
        self.detect_knowledge_gaps(message)
        self.infer_expectation(message)
        self.infer_empathy(message)

        self._save()

        pm = self.persona
        if pm and len(message) > 20:
            try:
                pm.ingest(message)
            except Exception:
                pass

    def _infer_traits_from_message(self, msg_lower: str) -> None:
        """PersonaVLM PEM: infer latent traits from conversation signals."""
        traits = self.profile.traits
        for trait, signals in TRAIT_SIGNALS.items():
            inc_count = sum(1 for s in signals["inc"] if s.lower() in msg_lower)
            dec_count = sum(1 for s in signals["dec"] if s.lower() in msg_lower)
            if inc_count + dec_count == 0:
                continue
            delta = (inc_count - dec_count) / max(inc_count + dec_count, 1)
            current = getattr(traits, trait)
            inferred = max(0.05, min(0.95, current + delta * 0.08))
            new_val = MOMENTUM_BETA * current + (1.0 - MOMENTUM_BETA) * inferred
            setattr(traits, trait, round(max(0.05, min(0.95, new_val)), 4))

        breadths = 0
        for kws in [
            ["代码", "code", "API", "docker", "git"],
            ["数据", "data", "分析", "analysis"],
            ["写", "文档", "报告", "document"],
            ["设计", "架构", "design"],
        ]:
            if any(kw.lower() in msg_lower for kw in kws):
                breadths += 1
        inferred_breadth = min(0.95, breadths / 4.0 + 0.3)
        traits.topic_breadth = round(
            MOMENTUM_BETA * traits.topic_breadth + (1.0 - MOMENTUM_BETA) * inferred_breadth, 4)

        traits.generation += 1

        try:
            from .user_trait_evolution import get_user_trait_evolution
            ute = get_user_trait_evolution()
            ute.infer_from_conversation([msg_lower])
        except Exception:
            pass

    def _update_habit_signals(self, msg_lower: str, n: float) -> None:
        """Track 7 implicit habit signals from conversation behavior."""
        sigs = self.profile.habit_signals
        rlp = 1.0 if any(k in msg_lower for k in ["简洁", "简短", "简单"]) else (
            -1.0 if any(k in msg_lower for k in ["详细", "详细点", "长一点"]) else 0.0)
        if rlp != 0.0:
            sigs["response_length_pref"] = round(
                MOMENTUM_BETA * sigs.get("response_length_pref", 0.0) + (1.0 - MOMENTUM_BETA) * rlp, 4)

        q_count = msg_lower.count("?") + msg_lower.count("？")
        sigs["question_frequency"] = round(
            MOMENTUM_BETA * sigs.get("question_frequency", 0.0) + (1.0 - MOMENTUM_BETA) * min(1.0, q_count * 0.2), 4)

        tech_count = sum(
            1 for kw in ["架构", "流水线", "优化", "延迟", "吞吐",
                         "architecture", "pipeline", "optimize", "latency"]
            if kw.lower() in msg_lower)
        sigs["technical_jargon_ratio"] = round(
            MOMENTUM_BETA * sigs.get("technical_jargon_ratio", 0.0) + (1.0 - MOMENTUM_BETA) * min(1.0, tech_count * 0.25), 4)

        decisive = sum(1 for kw in ["确定", "直接", "就这个", "用这个"]
                       if kw in msg_lower)
        sigs["decisiveness_score"] = round(
            MOMENTUM_BETA * sigs.get("decisiveness_score", 0.0) + (1.0 - MOMENTUM_BETA) * min(1.0, decisive * 0.33), 4)

        gratitude = sum(1 for kw in ["谢谢", "感谢", "thanks", "thank"]
                        if kw.lower() in msg_lower)
        sigs["gratitude_frequency"] = round(
            MOMENTUM_BETA * sigs.get("gratitude_frequency", 0.0) + (1.0 - MOMENTUM_BETA) * min(1.0, gratitude * 0.5), 4)

        urgency = sum(1 for kw in ["紧急", "快点", "尽快", "马上", "urgent", "ASAP"]
                      if kw.lower() in msg_lower)
        sigs["urgency_language_ratio"] = round(
            MOMENTUM_BETA * sigs.get("urgency_language_ratio", 0.0) + (1.0 - MOMENTUM_BETA) * min(1.0, urgency * 0.5), 4)

    def get_user_traits(self) -> dict[str, float]:
        """Return current PEM-evolved user trait vector."""
        return self.profile.traits.to_dict()

    def get_habit_signals(self) -> dict[str, float]:
        """Return current habit signal values."""
        return dict(self.profile.habit_signals)

    def get_adaptive_communication_style(self) -> dict[str, Any]:
        """PersonaVLM response alignment: map traits to communication parameters.

        Returns style hints for temperature, verbosity, formality adjustments.
        """
        t = self.profile.traits
        style = {"temperature": 0.7, "verbosity": "medium", "formality": "neutral"}

        if t.technical_sophistication > 0.65:
            style["temperature"] = 0.5
            style["verbosity"] = "detailed"

        if t.feedback_directness > 0.65:
            style["verbosity"] = "concise"
            style["formality"] = "direct"

        if t.patience_tolerance < 0.35:
            style["verbosity"] = "concise"
            style["temperature"] = 0.4

        if t.delegation_comfort > 0.65:
            style["verbosity"] = "detailed"

        dec = self.profile.habit_signals.get("decisiveness_score", 0.0)
        if dec > 0.3:
            style["verbosity"] = "concise"

        urg = self.profile.habit_signals.get("urgency_language_ratio", 0.0)
        if urg > 0.3:
            style["verbosity"] = "concise"
            style["temperature"] = 0.3

        return style

    # ── L2b: Theory of Mind (v2.7) ──

    def infer_belief_state(self, message: str, task_context: str = "") -> UserBeliefState:
        """Infer what the user currently knows, wants, and feels about the task.

        Theory of Mind premise: the user's observable language reveals their
        internal mental model — what topics they're certain about, what they're
        unsure of, and what they implicitly want but haven't directly stated.
        """
        bs = self.profile.belief_state
        msg_lower = message.lower()

        for topic, kw_list in {
            "code": ["代码", "编译", "运行", "函数", "API", "code", "compile", "function"],
            "deploy": ["部署", "上线", "发布", "docker", "k8s", "deploy", "release"],
            "data": ["数据", "数据库", "分析", "统计", "data", "sql", "analysis"],
            "config": ["配置", "设置", "参数", "config", "settings", "parameter"],
            "doc": ["文档", "报告", "说明", "document", "report", "readme"],
            "debug": ["错误", "bug", "修", "异常", "exception", "error", "fix"],
            "security": ["安全", "权限", "认证", "security", "auth", "permission"],
            "perf": ["慢", "性能", "优化", "加速", "slow", "performance", "optimize"],
        }.items():
            if any(kw in msg_lower for kw in kw_list):
                if topic not in bs.known_topics:
                    bs.known_topics.append(topic)

        for know_gap in [
            ("不了解这个", "unfamiliar_topic"),
            ("怎么", "how_to"),
            ("为什么", "why"),
            ("不知道", "unknown"),
            ("不太清楚", "unclear"),
            ("不确定", "uncertain"),
            ("什么原因", "root_cause"),
            ("don't know", "unknown"),
            ("not sure", "uncertain"),
            ("how to", "how_to"),
        ]:
            if know_gap[0] in msg_lower:
                if know_gap[1] not in bs.unknown_topics:
                    bs.unknown_topics.append(know_gap[1])

        for goal in self._extract_goals(message):
            if goal not in bs.stated_goals:
                bs.stated_goals = (bs.stated_goals[-4:] + [goal]) if len(bs.stated_goals) >= 5 else bs.stated_goals + [goal]

        for want in self._extract_implicit_wants(message, task_context):
            if want not in bs.implied_wants:
                bs.implied_wants = (bs.implied_wants[-4:] + [want]) if len(bs.implied_wants) >= 5 else bs.implied_wants + [want]

        frustration_kw = sum(1 for kw in ["还是错", "又错了", "不对", "不行", "still wrong", "again", "还是不行"] if kw in msg_lower)
        if frustration_kw > 0:
            bs.frustration_level = min(1.0, bs.frustration_level + 0.15)
        else:
            bs.frustration_level = max(0.0, bs.frustration_level - 0.05)

        satisfaction_kw = sum(1 for kw in ["好", "对", "可以", "谢谢", "good", "correct", "thanks", "works"] if kw in msg_lower)
        if satisfaction_kw > 0:
            bs.satisfaction_level = min(1.0, bs.satisfaction_level + 0.08)
        else:
            bs.satisfaction_level = max(0.0, bs.satisfaction_level - 0.02)

        if len(message) < 15:
            bs.attention_span = "scanning"
        elif len(message) > 300:
            bs.attention_span = "deep"

        return bs

    def detect_knowledge_gaps(self, message: str, task_domain: str = "general") -> list[KnowledgeGap]:
        """Identify knowledge gaps: concepts the user seems not to know but needs.

        These are TEACHING opportunities — the agent should explain these concepts
        rather than assume the user already understands.
        """
        gaps: list[KnowledgeGap] = []
        msg_lower = message.lower()

        for pattern, topic, severity in [
            (["是什么", "什么意思", "what is", "meaning"], "definition_requested", 0.8),
            (["怎么用", "如何使用", "how to use"], "usage_unknown", 0.7),
            (["不确定", "可能", "maybe", "perhaps", "not sure"], "uncertainty", 0.5),
            (["试了", "尝试", "tried", "attempt"], "trial_and_error", 0.4),
            (["应该", "should", "supposed to"], "expected_behavior_unknown", 0.6),
            (["不懂", "不理解", "don't understand"], "comprehension_gap", 0.9),
            (["有区别", "vs", "comparison", "区别"], "comparison_needed", 0.6),
        ]:
            if any(kw in msg_lower for kw in pattern):
                gaps.append(KnowledgeGap(
                    topic=topic,
                    evidence=f"User asked about '{topic}' in message: {message[:80]}",
                    severity=severity,
                ))

        for kw, concept in [
            ("API", "api_design"),
            ("docker", "containerization"),
            ("prompt", "prompt_engineering"),
            ("部署", "deployment"),
            ("优化", "optimization"),
            ("安全", "security"),
            ("架构", "architecture"),
            ("测试", "testing"),
        ]:
            if kw in msg_lower and not any(c in self.profile.belief_state.known_topics for c in [kw]):
                gaps.append(KnowledgeGap(
                    topic=concept,
                    evidence=f"User mentioned '{kw}' but may not know '{concept}'",
                    severity=0.4,
                ))

        self.profile.knowledge_gaps = (self.profile.knowledge_gaps[-9:] + gaps)
        return gaps

    def infer_expectation(self, message: str, last_response: str = "",
                          conversation_turn: int = 0) -> ExpectationModel:
        """Predict what the user likely expects next — the implicit question behind the explicit one.

        Enables proactive responses: answer the stated question AND the unstated need.
        """
        em = ExpectationModel()
        msg_lower = message.lower()

        if any(kw in msg_lower for kw in ["写", "生成", "创建", "write", "generate", "create"]):
            em.expected_response_type = "artifact"
            em.implicit_question = "用户可能需要该产物格式说明或范例"
        elif any(kw in msg_lower for kw in ["修改", "改", "fix", "change", "update"]):
            em.expected_response_type = "correction"
            em.implicit_question = "用户可能还想确认修改是否有副作用"
        elif any(kw in msg_lower for kw in ["怎么", "如何", "how"]):
            em.expected_response_type = "tutorial"
            em.implicit_question = "用户可能还需要前置知识或环境准备说明"
        elif any(kw in msg_lower for kw in ["分析", "对比", "analyze", "compare"]):
            em.expected_response_type = "analysis"
            em.implicit_question = "用户可能还想知道可行动的建议而非仅分析结果"
        elif any(kw in msg_lower for kw in ["部署", "上线", "deploy", "release"]):
            em.expected_response_type = "checklist"
            em.implicit_question = "用户可能需要前置检查清单和回滚方案"

        if any(kw in msg_lower for kw in ["紧急", "快点", "尽快", "马上", "urgent", "ASAP"]):
            em.deadline_pressure = min(1.0, em.deadline_pressure + 0.3)

        if any(kw in msg_lower for kw in ["详细", "详细点", "全部", "detail", "detailed", "全面"]):
            em.expected_detail_level = "deep"
        elif any(kw in msg_lower for kw in ["简要", "简单", "brief", "短", "概"]):
            em.expected_detail_level = "concise"

        em.next_action_expected = em.expected_response_type
        self.profile.expectation = em
        return em

    def infer_empathy(self, message: str, task_context: str = "") -> EmpathySignal:
        """Infer the user's emotional-cognitive state from conversation signals.

        Cognitive empathy: understand what the user is feeling and thinking,
        NOT just what they're asking for. This enables the agent to adjust
        tone, detail, and strategy to match the user's state.
        """
        es = EmpathySignal()
        msg_lower = message.lower()

        if any(kw in msg_lower for kw in ["谢谢", "好", "对", "可以", "good", "great", "works", "完美"]):
            es.primary_emotion = "satisfied"
            es.confidence_level = 0.7
        elif any(kw in msg_lower for kw in ["不对", "错了", "还是错", "wrong", "incorrect", "fail", "不行"]):
            es.primary_emotion = "frustrated"
            es.confidence_level = 0.6
            es.secondary_emotion = "confused"
        elif any(kw in msg_lower for kw in ["不确定", "可能", "maybe", "perhaps", "not sure", "不确定"]):
            es.primary_emotion = "uncertain"
            es.confidence_level = 0.5
            es.inferred_need = "需要更多确定性信息或验证"
        elif any(kw in msg_lower for kw in ["紧急", "快点", "urgent", "ASAP", "尽快"]):
            es.primary_emotion = "anxious"
            es.confidence_level = 0.65
            es.time_pressure = 0.8
            es.inferred_need = "需要快速响应,优先处理"
        elif any(kw in msg_lower for kw in ["累", "麻烦", "难", "不懂", "confusing", "hard"]):
            es.primary_emotion = "overwhelmed"
            es.confidence_level = 0.5
            es.cognitive_load = 0.8
            es.inferred_need = "需要简化解释,分解步骤"

        if len(message) > 500:
            es.cognitive_load = min(1.0, es.cognitive_load + 0.3)
        if message.count("?") + message.count("？") > 3:
            es.cognitive_load = min(1.0, es.cognitive_load + 0.2)

        if any(kw in msg_lower for kw in ["请", "谢谢", "麻烦", "please", "thanks"]):
            es.social_tone = "polite"
        elif any(kw in msg_lower for kw in ["你"] + ["!"] * 2):
            es.social_tone = "direct"

        self.profile.empathy_signal = es
        return es

    def get_empathy_context(self) -> str:
        """Build injectable empathy-aware context block for system prompt."""
        es = self.profile.empathy_signal
        bs = self.profile.belief_state
        em = self.profile.expectation

        parts = []
        if es.primary_emotion != "neutral":
            parts.append(f"[心智推测] 用户情绪: {es.primary_emotion} "
                         f"(认知负荷: {es.cognitive_load:.0%}, 自信: {es.confidence_level:.0%})")
            if es.inferred_need:
                parts.append(f"  用户深层需求: {es.inferred_need}")

        if em.implicit_question:
            parts.append(f"[期望模型] {em.implicit_question}")

        if bs.unknown_topics:
            parts.append(f"[知识缺口] 用户不确定: {', '.join(bs.unknown_topics[:3])}")

        if bs.implied_wants:
            parts.append(f"[隐含需求] {', '.join(bs.implied_wants[:3])}")

        if gaps := [g for g in self.profile.knowledge_gaps if g.severity > 0.5]:
            parts.append(f"[教学时机] {', '.join(g.topic for g in gaps[:2])}")

        if not parts:
            return ""
        return "\n".join(parts)

    @staticmethod
    def _extract_goals(message: str) -> list[str]:
        goals = []
        for marker, prefix in [
            ("想", "希望"),
            ("要", "需要"),
            ("want to", "wants"),
            ("need to", "needs"),
            ("目标", "goal"),
        ]:
            idx = message.lower().find(marker)
            if idx >= 0:
                end = min(len(message), idx + len(marker) + 40)
                goals.append(f"{prefix}: {message[idx:end].strip()}")
        return goals[:3]

    @staticmethod
    def _extract_implicit_wants(message: str, task_ctx: str) -> list[str]:
        wants = []
        if any(kw in message.lower() for kw in ["快", "急", "urgent", "ASAP"]):
            wants.append("快速响应")
        if any(kw in message.lower() for kw in ["简单", "简要", "brief", "simple"]):
            wants.append("简化输出")
        if any(kw in message.lower() for kw in ["详细", "detail", "全面"]):
            wants.append("详细解释")
        if any(kw in message.lower() for kw in ["例子", "示例", "example", "sample"]):
            wants.append("具体示例")
        return wants

    # ── L2: Implicit Habit Rules ──
        """Get implicit habit and PEM trait signals for prompt injection."""
        rules = []
        if self.profile.verbosity_avg < 50:
            rules.append("用户偏好极简回答 (平均消息长度<50字符)")
        elif self.profile.verbosity_avg > 500:
            rules.append("用户偏好详细回答 (平均消息长度>500字符)")

        top_domains = sorted(self.profile.domain_affinity.items(),
                             key=lambda x: -x[1])[:3]
        if top_domains:
            rules.append(f"用户常用领域: {', '.join(d for d, _ in top_domains)}")

        if self.profile.negation_ratio > 0.3:
            rules.append("用户经常否定/修正输出 — 首次回答应更谨慎")

        if self.profile.preferred_model:
            rules.append(f"用户锁定模型: {self.profile.preferred_model}")

        t = self.profile.traits
        dominant = t.dominant_traits()
        if dominant:
            traits_desc = {
                "technical_sophistication": "技术能力强",
                "engagement_depth": "深入参与",
                "feedback_directness": "反馈直接",
                "delegation_comfort": "倾向委托",
                "patience_tolerance": "耐心高",
                "topic_breadth": "领域广泛",
            }
            descs = [traits_desc.get(d, d) for d in dominant[:3]]
            rules.append(f"用户特征: {', '.join(descs)}")

        sigs = self.profile.habit_signals
        if sigs.get("urgency_language_ratio", 0) > 0.3:
            rules.append("用户常需快速响应")

        empathy_ctx = self.get_empathy_context()
        if empathy_ctx:
            rules.append(empathy_ctx)

        return rules

    # ── L3: Environment Context ──

    def set_project_context(self, path: str, description: str = ""):
        self.profile.project_context = f"{path}"
        if description:
            self.profile.project_context += f" ({description})"
        self._save()

    def set_model_preference(self, model: str):
        self.profile.preferred_model = model
        self._save()

    def get_env_rules(self) -> list[str]:
        rules = []
        if self.profile.project_context:
            rules.append(f"当前项目: {self.profile.project_context}")
        if self.profile.preferred_model:
            rules.append(f"首选模型: {self.profile.preferred_model}")
        return rules

    # ── Unified Prompt Injection ──

    def inject_into_prompt(self, role: str = "") -> str:
        """Build unified user profile for system prompt injection.

        Returns compact profile block for appending to system message.
        Uses ContextCodex symbols for compression when available.
        """
        rules = []
        rules.extend(self.get_instruction_rules())
        rules.extend(self.get_habit_rules())
        rules.extend(self.get_env_rules())
        
        # Enrich with PersonaMemory structured facts (cross-domain user profile)
        pm = self.persona
        if pm:
            try:
                persona_ctx = pm.get_context_for_query(role or "general")
                if persona_ctx:
                    rules.append(f"用户画像: {persona_ctx[:300]}")
            except Exception:
                pass

        if not rules:
            return ""

        lines = ["[UserModel: 用户画像]\n"]
        for r in rules:
            lines.append(f"- {r}")
        lines.append("")

        raw = "\n".join(lines)
        try:
            from ..execution.context_codex import get_context_codex
            codex = get_context_codex(seed=False)
            compressed, header = codex.compress(raw, layer=2, max_header_chars=300)
            if header:
                return f"{header}\n---\n{compressed}"
        except Exception:
            pass
        return raw

    def inject_minimal(self) -> str:
        """Ultra-compact user profile (for tight context budgets)."""
        parts = []
        top_corrections = sorted(self.profile.corrections,
                                  key=lambda c: -c.count)[:3]
        for c in top_corrections:
            if c.count >= self.CORRECTION_CONFIDENCE_THRESHOLD:
                parts.append(c.correction[:80])

        if self.profile.preferred_model:
            parts.append(f"model={self.profile.preferred_model}")

        if not parts:
            return ""
        return "[用户] " + " | ".join(parts)

    # ── Internal ──

    def _parse_correction(self, statement: str) -> tuple[str, str]:
        patterns = [
            (r"不要[用做]?(.+?)[，,]\s*(?:要|用|改用|应该)(.+)", 1, 2),
            (r"(?:别|不要|停止)[用做]?(.+)", 1, 0),
            (r"以后(.+)", 0, 0),
            (r"我(?:喜欢|偏好|希望|习惯)(.+)", 0, 0),
        ]
        for pattern, trigger_group, corr_group in patterns:
            m = re.search(pattern, statement)
            if m:
                trigger = m.group(trigger_group).strip()[:50] if trigger_group > 0 else ""
                correction = m.group(corr_group).strip()[:80] if corr_group > 0 else (
                    m.group(1).strip()[:80])
                if not trigger:
                    trigger = correction
                return trigger, correction
        return statement[:50], statement[:80]

    @staticmethod
    def _detect_domain(message: str) -> str:
        msg_lower = message.lower()
        if any(kw in msg_lower for kw in ["环评", "标准", "GB", "HJ", "监测", "排放"]):
            return "EIA"
        if any(kw in msg_lower for kw in ["代码", "bug", "函数", "class", "import"]):
            return "code"
        if any(kw in msg_lower for kw in ["报告", "文档", "生成", "模板"]):
            return "document"
        if any(kw in msg_lower for kw in ["分析", "数据", "统计", "对比"]):
            return "analysis"
        return "general"

    def _save(self):
        try:
            USER_MODEL_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "corrections": [
                    {"trigger": c.trigger, "correction": c.correction,
                     "category": c.category, "count": c.count,
                     "last_seen": c.last_seen}
                    for c in self.profile.corrections
                ],
                "domain_affinity": self.profile.domain_affinity,
                "preferred_model": self.profile.preferred_model,
                "verbosity_avg": self.profile.verbosity_avg,
                "peak_hour": self.profile.peak_hour,
                "negation_ratio": self.profile.negation_ratio,
                "project_context": self.profile.project_context,
                "last_updated": time.time(),
                "traits": self.profile.traits.to_dict(),
                "trait_generation": self.profile.traits.generation,
                "habit_signals": self.profile.habit_signals,
                "belief_state": {
                    "known_topics": self.profile.belief_state.known_topics,
                    "unknown_topics": self.profile.belief_state.unknown_topics,
                    "stated_goals": self.profile.belief_state.stated_goals,
                    "implied_wants": self.profile.belief_state.implied_wants,
                    "frustration": self.profile.belief_state.frustration_level,
                    "satisfaction": self.profile.belief_state.satisfaction_level,
                },
                "knowledge_gaps": [{"topic": g.topic, "severity": g.severity}
                                   for g in self.profile.knowledge_gaps[-10:]],
                "empathy_signal": {
                    "primary_emotion": self.profile.empathy_signal.primary_emotion,
                    "confidence": self.profile.empathy_signal.confidence_level,
                    "cognitive_load": self.profile.empathy_signal.cognitive_load,
                    "inferred_need": self.profile.empathy_signal.inferred_need,
                },
            }
            USER_MODEL_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"UserModel save: {e}")

    def _load(self):
        try:
            if USER_MODEL_FILE.exists():
                data = json.loads(USER_MODEL_FILE.read_text())
                self.profile.corrections = [
                    UserCorrection(**c) for c in data.get("corrections", [])
                ]
                self.profile.domain_affinity = data.get("domain_affinity", {})
                self.profile.preferred_model = data.get("preferred_model", "")
                self.profile.verbosity_avg = data.get("verbosity_avg", 0)
                self.profile.negation_ratio = data.get("negation_ratio", 0.0)
                self.profile.project_context = data.get("project_context", "")
                self.profile.last_updated = data.get("last_updated", 0.0)
                self.profile.peak_hour = data.get("peak_hour", 9)
                saved_traits = data.get("traits", {})
                if saved_traits:
                    for k, v in saved_traits.items():
                        if hasattr(self.profile.traits, k):
                            setattr(self.profile.traits, k, v)
                    self.profile.traits.generation = data.get("trait_generation", 0)
                self.profile.habit_signals = data.get("habit_signals", {})

                bs = data.get("belief_state", {})
                if bs:
                    self.profile.belief_state.known_topics = bs.get("known_topics", [])
                    self.profile.belief_state.unknown_topics = bs.get("unknown_topics", [])
                    self.profile.belief_state.stated_goals = bs.get("stated_goals", [])
                    self.profile.belief_state.implied_wants = bs.get("implied_wants", [])
                    self.profile.belief_state.frustration_level = bs.get("frustration", 0.0)
                    self.profile.belief_state.satisfaction_level = bs.get("satisfaction", 0.5)

                for g in data.get("knowledge_gaps", []):
                    self.profile.knowledge_gaps.append(KnowledgeGap(
                        topic=g["topic"], evidence="", severity=g["severity"]))

                es = data.get("empathy_signal", {})
                if es:
                    self.profile.empathy_signal.primary_emotion = es.get("primary_emotion", "neutral")
                    self.profile.empathy_signal.confidence_level = es.get("confidence", 0.0)
                    self.profile.empathy_signal.cognitive_load = es.get("cognitive_load", 0.3)
                    self.profile.empathy_signal.inferred_need = es.get("inferred_need", "")
        except Exception as e:
            logger.debug(f"UserModel load: {e}")


_user_model: UserModel | None = None


def get_user_model() -> UserModel:
    global _user_model
    if _user_model is None:
        _user_model = UserModel()
    return _user_model
