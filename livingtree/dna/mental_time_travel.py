"""Mental Time Travel — Episodic memory → counterfactual past + hypothetical future.

Academic grounding: Tulving 2002 "Episodic Memory and Autonoesis", Suddendorf &
Corballis 2007 "Mental Time Travel", Schacter et al. 2017 "Prospective Brain".

Enables three cognitive operations that make the agent feel "lived" rather than
merely "trained":
  1. WHAT IF PAST: Re-imagine a past event with an alternative choice
     → extract the causal lesson that would have applied
  2. PREPLAY: Simulate a future scenario constructed from past patterns
     → anticipate obstacles, prepare contingency plans
  3. GROUNDING: Anchor abstract reasoning in a remembered concrete experience
     → answer "Give me an example of when..." from lived memory

Integration surface:
  - Reads episodic events from struct_mem (struct_mem.py: EventEntry)
  - Reads factual knowledge from engram_store (engram_store.py: EngramEntry)
  - Uses consciousness.hypothesis_generation() for counterfactual branching
  - Uses consciousness.self_questioning() for gap identification
  - Feeds into life_engine via ctx.metadata["mental_time_travel"] before cognize

Architecture (mirrors medial temporal lobe → prefrontal cortex projection):
  Episodic Retrieval → Counterfactual Branching → Future Projection → Lesson Extraction
"""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


@dataclass
class TrajectoryPoint:
    """A single remembered moment in the agent's timeline."""
    event_id: str
    session_id: str
    timestamp: str
    fact_perspective: str
    rel_perspective: str
    content_snippet: str
    emotional_valence: float = 0.0
    decision_impact: float = 0.5
    patterns: list[str] = field(default_factory=list)


@dataclass
class CounterfactualBranch:
    """One alternative "what if" path derived from a real event."""
    anchor_event: TrajectoryPoint
    pivot_point: str               # "If at this moment we had chosen X instead..."
    alternative_outcome: str         # What would have happened
    causal_lesson: str               # The principle this teaches (transferable)
    confidence: float = 0.5          # How plausible this branch is
    relevant_to_current: float = 0.0 # How relevant to the present query


@dataclass
class FutureScenario:
    """One projected "what if ahead" scenario synthesized from past patterns."""
    scenario_id: str
    description: str                 # The projected situation
    likelihood: float                # Estimated probability based on pattern matches
    precursor_events: list[str]      # IDs of past events that suggest this future
    prepared_strategies: list[str]   # "If this happens, here's what to do"
    risk_factors: list[str]          # Things that could go wrong
    timeline_estimate: str           # "within next 3 turns" / "within this session" / "eventually"


@dataclass
class TravelResult:
    """Complete mental time travel output — injectable into LifeEngine context."""
    query: str
    relevant_past: list[TrajectoryPoint]
    counterfactuals: list[CounterfactualBranch]
    future_scenarios: list[FutureScenario]
    grounding_examples: list[str]           # Concrete past examples for reasoning
    synthesized_insight: str                # Human-readable synthesis
    travel_depth: int = 1                   # 1=shallow, 2=medium, 3=deep
    generated_at: str = ""

    def inject_into_context(self) -> str:
        if not self.relevant_past and not self.future_scenarios:
            return ""
        parts = ["[Mental Time Travel — 时间旅行]"]
        if self.relevant_past:
            past_summary = "; ".join(
                p.content_snippet[:80] for p in self.relevant_past[:3]
            )
            parts.append(f"  Relevant past: {past_summary}")
        if self.counterfactuals:
            cf_lessons = "; ".join(
                c.causal_lesson[:80] for c in self.counterfactuals[:2]
            )
            parts.append(f"  Counterfactual lessons: {cf_lessons}")
        if self.future_scenarios:
            future_preview = "; ".join(
                f"{s.description[:60]} (lik={s.likelihood:.2f})"
                for s in self.future_scenarios[:2]
            )
            parts.append(f"  Projected futures: {future_preview}")
        if self.synthesized_insight:
            parts.append(f"  Insight: {self.synthesized_insight}")
        return "\n".join(parts)


class MentalTimeTravel:
    """Episodic memory re-entry engine: remember the past to project the future.

    Implements the human cognitive ability to mentally detach from the present
    and navigate both backward (episodic retrieval → counterfactual) and forward
    (pattern projection → preplay). This is the core of autonoetic consciousness.
    """

    DEFAULT_PAST_HORIZON = 5        # How many past events to retrieve
    DEFAULT_FUTURE_HORIZON = 2      # How many future scenarios to project
    DEFAULT_BRANCHES = 3            # How many counterfactual branches per anchor

    def __init__(self, horizon: int = DEFAULT_PAST_HORIZON):
        self._horizon = horizon
        self._travel_log: list[TravelResult] = []
        self._cached_trajectories: list[TrajectoryPoint] = []
        self._last_retrieve_time = 0.0

    def _get_struct_mem(self):
        try:
            from ..knowledge.struct_mem import get_struct_memory
            return get_struct_memory()
        except Exception:
            return None

    def _get_engram_store(self):
        try:
            from ..knowledge.engram_store import get_engram_store
            return get_engram_store()
        except Exception:
            return None

    async def _get_consciousness(self):
        try:
            from .consciousness import Consciousness
            from ..api.stream_session import get_current_consciousness
            return get_current_consciousness()
        except Exception:
            return None

    async def retrieve_relevant_past(self, query: str, top_k: int = 5) -> list[TrajectoryPoint]:
        sm = self._get_struct_mem()
        if not sm:
            return []

        try:
            top_k = top_k or self._horizon
            entries = await sm.retrieve_for_query(query, top_k=top_k, user_only=False)
        except Exception:
            entries = []

        points: list[TrajectoryPoint] = []
        seen_ids = set()

        for entry in (entries or []):
            if not hasattr(entry, 'id') or entry.id in seen_ids:
                continue
            seen_ids.add(entry.id)

            emotional = getattr(entry, 'emotional_valence', 0.0)
            decision = 0.5
            content = getattr(entry, 'text_for_retrieval', lambda: "")()
            if "决策" in content or "决定" in content or "decision" in content.lower():
                decision = 0.8
            elif "询问" in content or "ask" in content.lower():
                decision = 0.3

            patterns = []
            for kw in ["成功", "失败", "错误", "修改", "重构", "优化", "success", "fail", "error", "refactor"]:
                if kw in content:
                    patterns.append(kw)

            points.append(TrajectoryPoint(
                event_id=getattr(entry, 'id', ''),
                session_id=getattr(entry, 'session_id', ''),
                timestamp=getattr(entry, 'timestamp', ''),
                fact_perspective=getattr(entry, 'fact_perspective', ''),
                rel_perspective=getattr(entry, 'rel_perspective', ''),
                content_snippet=content[:200],
                emotional_valence=emotional,
                decision_impact=decision,
                patterns=patterns,
            ))

        self._cached_trajectories = points
        self._last_retrieve_time = time.time()
        return points

    async def what_if_past(self, anchor: TrajectoryPoint) -> list[CounterfactualBranch]:
        consciousness = await self._get_consciousness()
        branches: list[CounterfactualBranch] = []

        pivot_markers = self._find_pivot_markers(anchor.content_snippet)
        if not pivot_markers:
            return branches

        for pivot in pivot_markers[:self.DEFAULT_BRANCHES]:
            if consciousness and hasattr(consciousness, 'hypothesis_generation'):
                try:
                    prompt = (
                        f"In a past conversation, the user/agent did: '{anchor.content_snippet[:150]}'. "
                        f"Pivot at: '{pivot}'. Generate ONE alternative path describing what if a different "
                        f"choice had been made at that pivot. Include: (1) the alternative action, "
                        f"(2) the likely different outcome, (3) a transferable lesson."
                    )
                    hypotheses = await consciousness.hypothesis_generation(prompt, count=1)
                    alt_text = hypotheses[0] if hypotheses else ""
                except Exception:
                    alt_text = ""
            else:
                alt_text = self._heuristic_counterfactual(anchor, pivot)

            if not alt_text:
                continue

            alt_parts = alt_text.split("\n")
            alternative = alt_parts[0] if alt_parts else alt_text[:100]
            outcome = alt_parts[1] if len(alt_parts) > 1 else alt_text[100:200] if len(alt_text) > 100 else ""
            lesson = alt_parts[2] if len(alt_parts) > 2 else ""

            branches.append(CounterfactualBranch(
                anchor_event=anchor,
                pivot_point=pivot,
                alternative_outcome=alternative or alt_text[:80],
                causal_lesson=lesson or self._extract_lesson(alt_text),
                confidence=0.5,
            ))

        return branches

    async def preplay_future(self, query: str, past_points: list[TrajectoryPoint]) -> list[FutureScenario]:
        if not past_points:
            return []

        consciousness = await self._get_consciousness()
        if not consciousness or not hasattr(consciousness, 'self_questioning'):
            return self._heuristic_future(query, past_points)

        try:
            pattern_summary = "; ".join(
                f"[{p.content_snippet[:60]}]" for p in past_points[:3]
            )
            prompt = (
                f"Current task: '{query[:100]}'. Remembered past patterns: {pattern_summary}. "
                f"Based on these patterns, project 2 possible future developments that might occur "
                f"as this conversation continues. For each: (1) describe the scenario, "
                f"(2) estimate likelihood, (3) suggest a prepared response."
            )
            questions = await consciousness.self_questioning(prompt)
            return self._parse_future_from_questions(questions, past_points)
        except Exception:
            return self._heuristic_future(query, past_points)

    async def travel(self, query: str, depth: int = 1,
                     travel_past: bool = True,
                     travel_future: bool = True) -> TravelResult:
        """Execute a full mental time travel — the core cognitive operation.

        depth=1: fast heuristic past retrieval only
        depth=2: past + counterfactual branching
        depth=3: past + counterfactual + future preplay (deepest)
        """
        import datetime
        result = TravelResult(
            query=query,
            relevant_past=[],
            counterfactuals=[],
            future_scenarios=[],
            grounding_examples=[],
            synthesized_insight="",
            travel_depth=depth,
            generated_at=datetime.datetime.utcnow().isoformat(),
        )

        if travel_past and depth >= 1:
            result.relevant_past = await self.retrieve_relevant_past(query)
            for p in result.relevant_past:
                if p.content_snippet and len(p.content_snippet) > 20:
                    result.grounding_examples.append(p.content_snippet[:120])

        if depth >= 2 and result.relevant_past:
            for anchor in result.relevant_past[:2]:
                branches = await self.what_if_past(anchor)
                result.counterfactuals.extend(branches)

        if travel_future and depth >= 3:
            result.future_scenarios = await self.preplay_future(query, result.relevant_past)

        if result.counterfactuals:
            lessons = [c.causal_lesson for c in result.counterfactuals if c.causal_lesson]
            if lessons:
                result.synthesized_insight = f"从过去推演: {'; '.join(lessons[:2])}"

        if result.future_scenarios:
            risks = []
            for s in result.future_scenarios:
                risks.extend(s.risk_factors[:2])
            if risks:
                prepend = result.synthesized_insight + " " if result.synthesized_insight else ""
                result.synthesized_insight = f"{prepend}预判风险: {'; '.join(risks[:3])}"

        self._travel_log.append(result)
        return result

    def _find_pivot_markers(self, content: str) -> list[str]:
        markers = []
        for kw, pivot_text in [
            ("选择", "choice between alternatives"),
            ("决定", "decision point"),
            ("但是", "but / however moment"),
            ("如果", "hypothetical conditional"),
            ("应该", "should / obligation statement"),
            ("修改", "modification / change"),
            ("but", "but / however moment"),
            ("however", "but / however moment"),
            ("choose", "choice between alternatives"),
            ("change", "modification / change"),
            ("instead", "alternative choice"),
        ]:
            if kw in content.lower():
                idx = content.lower().find(kw)
                start = max(0, idx - 30)
                end = min(len(content), idx + len(kw) + 30)
                markers.append(content[start:end].strip())
        return list(dict.fromkeys(markers))[:self.DEFAULT_BRANCHES]

    def _heuristic_counterfactual(self, anchor: TrajectoryPoint, pivot: str) -> str:
        return (
            f"If at '{pivot}' the agent had chosen differently, the outcome would differ.\n"
            f"The user's request suggests the correct path was selected.\n"
            f"Lesson: decisions near key pivot points require careful deliberation."
        )

    def _extract_lesson(self, text: str) -> str:
        for marker in ["lesson:", "教训", "原则:", "principle:", "learned:", "学到了"]:
            idx = text.lower().find(marker)
            if idx >= 0:
                return text[idx + len(marker):].split("\n")[0].strip()[:120]
        return text[:120] if text else ""

    def _heuristic_future(self, query: str, past_points: list[TrajectoryPoint]) -> list[FutureScenario]:
        import uuid
        return [FutureScenario(
            scenario_id=f"fs_{uuid.uuid4().hex[:8]}",
            description=f"Based on past patterns: '{past_points[0].content_snippet[:60] if past_points else ''}', similar situations may recur in future sessions.",
            likelihood=0.4,
            precursor_events=[p.event_id for p in past_points[:2] if p.event_id],
            prepared_strategies=["Verify assumptions before proceeding", "Check if past patterns still apply"],
            risk_factors=["Overfitting to past examples", "Context mismatch between past and present"],
            timeline_estimate="eventually",
        )]

    def _parse_future_from_questions(self, questions: list[str], past_points: list[TrajectoryPoint]) -> list[FutureScenario]:
        import uuid
        scenarios = []
        for i, q in enumerate(questions[:self.DEFAULT_FUTURE_HORIZON]):
            desc = q.split("?")[0].strip() if "?" in q else q[:100]
            risks = []
            for kw in ["障碍", "风险", "冲突", "障碍", "risk", "conflict", "fail"]:
                if kw in q.lower():
                    risks.append(kw)
            scenarios.append(FutureScenario(
                scenario_id=f"fs_{uuid.uuid4().hex[:8]}",
                description=desc or f"Projected future scenario {i+1}",
                likelihood=0.35 + i * 0.10,
                precursor_events=[p.event_id for p in past_points[:2] if p.event_id],
                prepared_strategies=["Monitor for precursor signals", "Have fallback plan ready"],
                risk_factors=risks or ["Pattern mismatch with current context"],
                timeline_estimate="within this session",
            ))
        return scenarios


def get_time_traveler() -> MentalTimeTravel:
    if "_mtt" not in _TT_CACHE:
        _TT_CACHE["_mtt"] = MentalTimeTravel()
    return _TT_CACHE["_mtt"]


_TT_CACHE: dict[str, MentalTimeTravel] = {}
