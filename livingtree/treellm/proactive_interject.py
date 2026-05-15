"""ProactiveInterject — Proactive interjection and clarification engine.

Based on Thinking Machines Lab "Interaction Models" (May 2026):
  "The model jumps in as needed depending on the context, not only when
   the user finishes speaking... the model can do things like proactive
   interjections ('interrupt when I say something wrong') or reactions
   to visual cues ('tell me when I've written a bug in my code')."

Key insight: Traditional LLM interfaces are PASSIVE — they wait for the user
to finish, then respond. ProactiveInterject makes LivingTree ACTIVE — it
detects situations where interjecting NOW would be more valuable than waiting.

Interjection triggers (text-based adaptation):
  1. Ambiguity detection: User said something vague → "Did you mean X or Y?"
  2. Error detection: User seems to be on a wrong path → "Wait, have you
     considered that...?"
  3. Direction suggestion: User is going deep on one angle → "Another angle
     worth exploring: ..."
  4. Scope creep detection: User's question keeps expanding → "To focus this,
     which aspect is most important?"
  5. Repetition detection: User is rephrasing the same question → "I think
     what you're asking is essentially..."

Integration:
  - Called BEFORE routing — if interjection is needed, return it immediately
    instead of routing to a full model response
  - Works with MicroTurnAware to time the interjection correctly
  - Uses ConcurrentStream's weave mechanism for pro model insights

Usage:
    pi = get_proactive_interject()
    decision = pi.evaluate(user_text, conversation_history)
    if decision.should_interject:
        return decision.interjection_text  # Immediate response
    # Otherwise, proceed with normal routing
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

from loguru import logger


# ═══ Data Types ════════════════════════════════════════════════════


class InterjectTrigger(StrEnum):
    """What triggered the interjection."""
    AMBIGUITY = "ambiguity"              # Vague/unclear input
    ERROR_DETECTED = "error_detected"    # User seems on wrong path
    DIRECTION_SUGGEST = "direction"      # Alternative angle suggested
    SCOPE_CREEP = "scope_creep"          # Question keeps expanding
    REPETITION = "repetition"            # User rephrasing same thing
    MISSING_CONTEXT = "missing_context"  # Critical info not provided
    CONTRADICTION = "contradiction"      # User contradicts earlier statement
    CLARIFICATION = "clarification"      # Term or concept needs defining


@dataclass
class InterjectDecision:
    """Decision on whether/how to interject."""
    should_interject: bool
    trigger: InterjectTrigger | None = None
    interjection_text: str = ""
    confidence: float = 0.0             # How confident we should interject
    urgency: float = 0.0                # How urgently (0=nice to have, 1=critical)
    alternative_phrasing: str = ""      # Suggested rephrase of user query
    metadata: dict = field(default_factory=dict)


# ═══ ProactiveInterject Engine ════════════════════════════════════


class ProactiveInterject:
    """Proactive interjection engine — makes LivingTree an ACTIVE collaborator.

    Design: Unlike passive interfaces that always route to a model, this engine
    evaluates whether interjecting BEFORE routing would be more valuable.

    From TML: "The model jumps in as needed... all of these different
    interaction modes that require special harnesses today become
    special-cases of what the model can do."

    For LivingTree: interjections are generated heuristically (fast, no LLM
    call) based on text pattern analysis. Complex interjections can optionally
    use a flash model for generation.
    """

    # ── Thresholds ──

    AMBIGUITY_SCORE_THRESHOLD = 0.6     # Below this confidence → ambiguous
    MIN_TEXT_FOR_INTERJECT = 15         # Don't interject on very short input
    SCOPE_EXPANSION_RATIO = 2.0         # History:current ratio for scope creep
    REPETITION_SIMILARITY = 0.7         # Jaccard threshold for repetition
    CONTRADICTION_SIMILARITY = 0.5      # High sim + negations = contradiction
    MAX_INTERJECT_PER_SESSION = 3       # Don't be annoying
    INTERJECT_COOLDOWN = 5.0            # Seconds between interjections

    def __init__(self):
        self._interject_count: dict[str, int] = {}  # session_id → count
        self._last_interject_time: float = 0.0
        self._history_buffer: list[str] = []        # Recent user messages
        self._max_history = 10

    # ── Main Evaluation ───────────────────────────────────────────

    def evaluate(
        self, current_text: str, conversation_history: list[str] | None = None,
        session_id: str = "default", task_type: str = "general",
    ) -> InterjectDecision:
        """Evaluate whether to interject before routing.

        Args:
            current_text: User's current input text.
            conversation_history: Previous messages in this conversation.
            session_id: Unique session identifier for rate limiting.
            task_type: Task type for context.

        Returns:
            InterjectDecision with whether to interject and what to say.
        """
        # Rate limiting
        if not self._can_interject(session_id):
            return InterjectDecision(should_interject=False)

        # Update history
        self._history_buffer.append(current_text)
        if len(self._history_buffer) > self._max_history:
            self._history_buffer = self._history_buffer[-self._max_history:]

        # Merge conversation history
        history = (conversation_history or []) + self._history_buffer[:-1]

        # ── Check each trigger ──
        decisions: list[InterjectDecision] = []

        # 1. Ambiguity check
        amb = self._check_ambiguity(current_text)
        if amb.should_interject:
            decisions.append(amb)

        # 2. Missing context check
        mc = self._check_missing_context(current_text, task_type)
        if mc.should_interject:
            decisions.append(mc)

        # 3. Scope creep check
        sc = self._check_scope_creep(current_text, history)
        if sc.should_interject:
            decisions.append(sc)

        # 4. Repetition check
        rep = self._check_repetition(current_text, history)
        if rep.should_interject:
            decisions.append(rep)

        # 5. Contradiction check
        contra = self._check_contradiction(current_text, history)
        if contra.should_interject:
            decisions.append(contra)

        # 6. Direction suggestion (for code/analysis tasks)
        if task_type in ("code", "analysis", "reasoning"):
            d = self._check_direction_suggest(current_text, task_type)
            if d.should_interject:
                decisions.append(d)

        # ── Select highest-urgency interjection ──
        if decisions:
            decisions.sort(key=lambda d: -d.urgency)
            best = decisions[0]
            self._record_interject(session_id)
            logger.info(
                f"ProactiveInterject: {best.trigger} "
                f"(urgency={best.urgency:.2f}, conf={best.confidence:.2f})"
            )
            return best

        return InterjectDecision(should_interject=False)

    # ── Trigger: Ambiguity Detection ──────────────────────────────

    def _check_ambiguity(self, text: str) -> InterjectDecision:
        """Detect if user input is too vague/ambiguous to route effectively."""
        if len(text) < self.MIN_TEXT_FOR_INTERJECT:
            return InterjectDecision(should_interject=False)

        # Very short inputs are inherently ambiguous
        if len(text) < 30:
            return InterjectDecision(
                should_interject=True,
                trigger=InterjectTrigger.AMBIGUITY,
                interjection_text=(
                    f"你提到的「{text[:20]}...」可以朝几个方向展开——"
                    f"你更关心哪方面？是具体的操作步骤、原理分析、还是方案对比？"
                ),
                confidence=0.85,
                urgency=0.7,
            )

        # Pronoun-heavy without clear referents
        pronouns = ["它", "这", "那", "这个", "那个", "it", "this", "that", "they"]
        pronoun_count = sum(text.lower().count(p) for p in pronouns)
        if pronoun_count > 2 and len(text) < 100:
            return InterjectDecision(
                should_interject=True,
                trigger=InterjectTrigger.AMBIGUITY,
                interjection_text=(
                    f"你说的「这/那」具体指的是什么？我先确认一下，"
                    f"免得回答偏了方向。"
                ),
                confidence=0.75,
                urgency=0.6,
            )

        # No clear action verb
        action_verbs = ["优化", "实现", "分析", "设计", "修改", "修复",
                        "optimize", "implement", "analyze", "design", "fix"]
        has_action = any(v in text.lower() for v in action_verbs)
        if not has_action and len(text) > 30:
            return InterjectDecision(
                should_interject=True,
                trigger=InterjectTrigger.AMBIGUITY,
                interjection_text=(
                    f"你是想让我分析这个问题、给出方案、还是直接帮你做？"
                    f"明确一下我可以更精准地回答。"
                ),
                confidence=0.65,
                urgency=0.5,
            )

        return InterjectDecision(should_interject=False)

    # ── Trigger: Missing Critical Context ─────────────────────────

    def _check_missing_context(self, text: str, task_type: str) -> InterjectDecision:
        """Detect if critical context is missing for effective routing."""
        if len(text) < 30:
            return InterjectDecision(should_interject=False)

        if task_type == "code":
            missing = []
            if "错误" in text or "error" in text.lower():
                if "error message" not in text.lower() and "报错" not in text and "错误信息" not in text:
                    missing.append("具体的错误信息是什么？")
            if ("怎么" in text or "how" in text.lower()) and "语言" not in text and "language" not in text.lower():
                missing.append("你用什么编程语言/框架？")
            if missing:
                return InterjectDecision(
                    should_interject=True,
                    trigger=InterjectTrigger.MISSING_CONTEXT,
                    interjection_text=" ".join(missing),
                    confidence=0.7,
                    urgency=0.8,
                )

        return InterjectDecision(should_interject=False)

    # ── Trigger: Scope Creep ──────────────────────────────────────

    def _check_scope_creep(
        self, text: str, history: list[str],
    ) -> InterjectDecision:
        """Detect if user's question keeps expanding (scope creep)."""
        if len(history) < 2:
            return InterjectDecision(should_interject=False)

        # Check if current text is much longer than recent average
        recent_lens = [len(h) for h in history[-3:]]
        if not recent_lens:
            return InterjectDecision(should_interject=False)

        avg_len = sum(recent_lens) / len(recent_lens)
        if len(text) > avg_len * self.SCOPE_EXPANSION_RATIO:
            return InterjectDecision(
                should_interject=True,
                trigger=InterjectTrigger.SCOPE_CREEP,
                interjection_text=(
                    f"我注意到你的问题范围在扩大——"
                    f"要不要我们先聚焦最核心的那个问题，其他的可以后续讨论？"
                ),
                confidence=0.6,
                urgency=0.4,
            )

        return InterjectDecision(should_interject=False)

    # ── Trigger: Repetition ───────────────────────────────────────

    def _check_repetition(
        self, text: str, history: list[str],
    ) -> InterjectDecision:
        """Detect if user is rephrasing the same question."""
        if len(history) < 1:
            return InterjectDecision(should_interject=False)

        for h in reversed(history[-3:]):
            sim = self._jaccard_similarity(text, h)
            if sim > self.REPETITION_SIMILARITY:
                return InterjectDecision(
                    should_interject=True,
                    trigger=InterjectTrigger.REPETITION,
                    interjection_text=(
                        f"我觉得你想问的本质上可能是：{self._extract_core(text)}"
                        f"——让我从这个角度来回答。"
                    ),
                    confidence=sim,
                    urgency=0.5,
                )

        return InterjectDecision(should_interject=False)

    # ── Trigger: Contradiction ────────────────────────────────────

    def _check_contradiction(
        self, text: str, history: list[str],
    ) -> InterjectDecision:
        """Detect if user contradicts an earlier statement."""
        if len(history) < 1:
            return InterjectDecision(should_interject=False)

        for h in reversed(history[-3:]):
            sim = self._jaccard_similarity(text, h)
            if sim > self.CONTRADICTION_SIMILARITY:
                # Check for negation asymmetry
                negs = {"不", "没有", "不是", "别", "not", "no", "never", "don't"}
                text_negs = sum(1 for n in negs if n in text.lower().split())
                hist_negs = sum(1 for n in negs if n in h.lower().split())
                if text_negs != hist_negs and abs(text_negs - hist_negs) >= 1:
                    return InterjectDecision(
                        should_interject=True,
                        trigger=InterjectTrigger.CONTRADICTION,
                        interjection_text=(
                            f"等一下——你之前说的是「{h[:50]}...」，"
                            f"现在似乎角度不同了。你现在的侧重点变了吗？"
                        ),
                        confidence=0.6,
                        urgency=0.6,
                    )

        return InterjectDecision(should_interject=False)

    # ── Trigger: Direction Suggestion ─────────────────────────────

    def _check_direction_suggest(
        self, text: str, task_type: str,
    ) -> InterjectDecision:
        """Suggest alternative analysis directions for complex tasks."""
        if len(text) < 50:
            return InterjectDecision(should_interject=False)

        # Single-dimension analysis detected
        if task_type == "analysis":
            single_view_indicators = ["怎么优化", "如何提升", "为什么慢"]
            if any(ind in text for ind in single_view_indicators):
                return InterjectDecision(
                    should_interject=True,
                    trigger=InterjectTrigger.DIRECTION_SUGGEST,
                    interjection_text=(
                        f"在分析之前——除了性能角度，可能还需要考虑可维护性和安全性的影响。"
                        f"要不要我把这三个维度都纳入分析？"
                    ),
                    confidence=0.55,
                    urgency=0.3,
                )

        if task_type == "code":
            if "怎么写" in text or "how to write" in text.lower():
                return InterjectDecision(
                    should_interject=True,
                    trigger=InterjectTrigger.DIRECTION_SUGGEST,
                    interjection_text=(
                        f"在给代码之前——你能说一下这个功能的使用场景和输入输出吗？"
                        f"这样我能给出更贴合的实现。"
                    ),
                    confidence=0.7,
                    urgency=0.5,
                )

        return InterjectDecision(should_interject=False)

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _jaccard_similarity(a: str, b: str) -> float:
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    @staticmethod
    def _extract_core(text: str) -> str:
        """Extract core question from text."""
        # Simple: take first sentence or first 50 chars
        sentences = re.split(r'[.!?。！？]+', text)
        return sentences[0].strip()[:80] if sentences else text[:80]

    # ── Rate Limiting ─────────────────────────────────────────────

    def _can_interject(self, session_id: str) -> bool:
        """Check rate limits before interjecting."""
        count = self._interject_count.get(session_id, 0)
        if count >= self.MAX_INTERJECT_PER_SESSION:
            return False
        if time.time() - self._last_interject_time < self.INTERJECT_COOLDOWN:
            return False
        return True

    def _record_interject(self, session_id: str) -> None:
        self._interject_count[session_id] = self._interject_count.get(session_id, 0) + 1
        self._last_interject_time = time.time()

    def reset(self, session_id: str = "default") -> None:
        """Reset interjection counters for a session."""
        self._interject_count.pop(session_id, None)
        self._history_buffer.clear()

    # ── Statistics ─────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "total_interjections": sum(self._interject_count.values()),
            "active_sessions": len(self._interject_count),
            "cooldown_remaining": max(0.0,
                self.INTERJECT_COOLDOWN - (time.time() - self._last_interject_time)),
        }


# ═══ Singleton ═════════════════════════════════════════════════════

_pi: Optional[ProactiveInterject] = None
_pi_lock = threading.Lock()


def get_proactive_interject() -> ProactiveInterject:
    global _pi
    if _pi is None:
        with _pi_lock:
            if _pi is None:
                _pi = ProactiveInterject()
    return _pi


__all__ = [
    "ProactiveInterject", "InterjectDecision", "InterjectTrigger",
    "get_proactive_interject",
]
