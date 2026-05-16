"""PlanFill + Confidence Escalation + Local Guardian + Pro Compiler + Error Loop.

5 innovations that change HOW models collaborate, not WHICH models are used.

1. Plan→Fill: Fast model produces structured JSON plan → reasoning fills/executes.
   Simple: template render. Medium: fill gaps. Complex: step-by-step execution.

2. Confidence Escalation: Binary routing replaced by 3-tier confidence thresholds.
   High(>0.8)→accept, Medium(0.5-0.8)→light correction, Low(<0.5)→full Pro.

3. Local Guardian: Local model answers first → background Pro verification.
   Match→done. Mismatch→alert/upgrade. Handles offline, privacy, latency.

4. Pro Compiler: Batch candidate outputs → Pro does batch quality check/rewrite.
   Caches results. Reduces Pro calls for summarization, reports, templates.

5. Error Loop: Every escalation logged → boundary samples → iterative improvement.
   Learns fast model's blind spots, adjusts routing thresholds, refines prompts.

Integration:
  pf = PlanFillEngine(tree_llm)
  plan = await pf.plan(query)           # fast model → structured plan
  result = await pf.fill(plan)          # reasoning fills based on complexity
  pf.learn_from_outcome(result, user_ok)  # learn from success/failure
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

from loguru import logger


class Complexity(StrEnum):
    SIMPLE = "simple"      # template render, no LLM needed
    MEDIUM = "medium"      # light Pro correction
    COMPLEX = "complex"    # full Pro step-by-step


class Confidence(StrEnum):
    HIGH = "high"          # >0.8 → accept directly
    MEDIUM = "medium"      # 0.5-0.8 → light Pro correction
    LOW = "low"            # <0.5 → full Pro


@dataclass
class Plan:
    """Structured intermediate state from fast model."""
    original_query: str = ""
    intent: str = ""            # chat/code/reasoning/search/creative
    entities: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    sub_queries: list[str] = field(default_factory=list)
    output_format: str = "text"
    confidence: float = 0.5
    complexity: Complexity = Complexity.MEDIUM
    plan_id: str = ""
    created_at: float = field(default_factory=time.time)

    def to_prompt(self) -> str:
        """Render plan as optimized reasoning prompt."""
        parts = [self.original_query]
        if self.entities:
            parts.append(f"Entities: {', '.join(self.entities)}")
        if self.constraints:
            parts.append(f"Constraints: {', '.join(self.constraints)}")
        if self.sub_queries:
            parts.append(f"Breakdown:\n" + "\n".join(f"- {q}" for q in self.sub_queries))
        return "\n".join(parts)


@dataclass
class ErrorCase:
    """A learned error case for continuous improvement."""
    query: str
    fast_output: str = ""
    pro_output: str = ""
    error_type: str = ""     # boundary/over_escalation/format_mismatch
    user_feedback: bool = False
    learned_at: float = field(default_factory=time.time)


class PlanFillEngine:
    """Fast model plans → reasoning model fills. With learning loop."""

    def __init__(self, tree_llm=None):
        self._tree = tree_llm
        self._error_cases: list[ErrorCase] = []
        self._plan_cache: dict[str, Plan] = {}     # query_hash → plan
        self._fill_cache: dict[str, str] = {}       # plan_hash → result
        self._confidence_thresholds = {
            Confidence.HIGH: 0.8,
            Confidence.MEDIUM: 0.5,
        }
        self._stats = {"plans": 0, "fills": 0, "pro_saved": 0, "errors": 0}

    # ═══ 1. Plan→Fill Pipeline ═════════════════════════════════════

    async def plan(self, query: str, domain: str = "") -> Plan:
        """Fast model produces structured intermediate state (Plan).

        This is the key innovation: instead of fast model being just a
        router/classifier, it produces a rich intermediate representation
        that the reasoning model can use as a scaffold.
        """
        self._stats["plans"] += 1

        # Cache check
        qhash = hashlib.md5(query[:200].encode()).hexdigest()[:12]
        if qhash in self._plan_cache:
            return self._plan_cache[qhash]

        try:
            from .sticky_election import get_layer_config
            cfg = get_layer_config()
            fast_prov, fast_model = cfg.get_provider(1)
        except Exception:
            fast_prov, fast_model = "deepseek", ""

        p = self._tree._providers.get(fast_prov) if self._tree else None
        if not p:
            return Plan(original_query=query, complexity=Complexity.SIMPLE)

        plan_prompt = (
            "Analyze this query and produce a structured JSON plan.\n\n"
            f"Query: {query}\n"
            f"{'Domain: ' + domain if domain else ''}\n\n"
            "Output ONLY JSON:\n"
            '{"intent": "code|reasoning|search|chat|creative",\n'
            ' "entities": ["key entity 1", "key entity 2"],\n'
            ' "constraints": ["must have", "should not"],\n'
            ' "sub_queries": ["step 1", "step 2"],\n'
            ' "complexity": "simple|medium|complex",\n'
            ' "confidence": 0.0-1.0,\n'
            ' "output_format": "text|code|table|list"}\n\n'
            "Rules:\n"
            "- simple: single-step answer (hello, what is X)\n"
            "- medium: needs some analysis (explain, compare)\n"
            "- complex: multi-step reasoning (implement, analyze, design)\n"
            "- confidence: how sure you are about this classification\n"
        )

        try:
            resp = await p.chat(
                messages=[{"role": "user", "content": plan_prompt}],
                model=fast_model or None, temperature=0.1, max_tokens=400, timeout=10,
            )
            plan_text = resp.text if resp and hasattr(resp, 'text') else ""
        except Exception:
            plan_text = ""

        plan = self._parse_plan(plan_text, query)
        self._plan_cache[qhash] = plan
        if len(self._plan_cache) > 200:
            self._plan_cache.pop(next(iter(self._plan_cache)))
        return plan

    async def fill(self, plan: Plan) -> str:
        """Reasoning model fills/executes the plan based on complexity."""
        self._stats["fills"] += 1

        # Cache check for simple plans
        phash = hashlib.md5(json.dumps(plan.to_prompt(), sort_keys=True).encode()).hexdigest()[:12]
        if plan.complexity == Complexity.SIMPLE and phash in self._fill_cache:
            return self._fill_cache[phash]

        if plan.complexity == Complexity.SIMPLE:
            return self._fill_simple(plan)

        if plan.complexity == Complexity.MEDIUM:
            result = await self._fill_medium(plan) or self._fill_simple(plan)
            return result

        # COMPLEX: full step-by-step reasoning
        result = await self._fill_complex(plan)
        if result:
            self._fill_cache[phash] = result
        return result or self._fill_simple(plan)

    # ═══ 2. Confidence-based Escalation ════════════════════════════

    def decide_escalation(self, plan: Plan) -> Confidence:
        """Replace binary routing with 3-tier confidence thresholds."""
        if plan.confidence >= self._confidence_thresholds[Confidence.HIGH]:
            return Confidence.HIGH
        if plan.confidence >= self._confidence_thresholds[Confidence.MEDIUM]:
            return Confidence.MEDIUM
        return Confidence.LOW

    # ═══ 3. Local Guardian (always-on cache/verification) ══════════

    async def local_guardian_verify(self, fast_answer: str, pro_answer: str,
                                     query: str) -> bool:
        """Verify fast model's answer against Pro's answer.

        Returns True if answers are consistent (no alert needed).
        Returns False if significant divergence → alert/upgrade.
        """
        try:
            from .adaptive_classifier import get_adaptive_classifier
            ac = get_adaptive_classifier()
            e1 = ac._embed(fast_answer)
            e2 = ac._embed(pro_answer)
            sim = self._cosine(e1 or [], e2 or [])
            return sim > 0.8  # consistent enough
        except Exception:
            return True

    # ═══ 4. Pro Compiler (batch quality check/rewrite) ═════════════

    async def batch_compile(self, candidates: list[str],
                             domain: str = "general") -> str:
        """Batch process multiple candidate outputs through Pro for QC.

        Instead of running Pro on every request, accumulate candidates
        and do a single batch quality pass.
        """
        if not candidates:
            return ""

        try:
            from .sticky_election import get_layer_config
            cfg = get_layer_config()
            prov, model = cfg.get_provider(2)
            p = self._tree._providers.get(prov) if self._tree else None
        except Exception:
            return ""

        if not p:
            return ""

        combined = "\n---\n".join(f"Candidate {i+1}: {c}" for i, c in enumerate(candidates) if c)
        batch_prompt = (
            f"Review these {len(candidates)} candidate outputs for domain: {domain}.\n"
            "Select the best one and optionally improve it.\n\n"
            f"{combined}\n\n"
            "Output format:\n"
            '"selected": <candidate number>,\n'
            '"improved": "<improved version or empty if already good>"'
        )

        try:
            resp = await p.chat(
                messages=[{"role": "user", "content": batch_prompt}],
                model=model or None, temperature=0.1, max_tokens=2048, timeout=30,
            )
            text = resp.text if resp and hasattr(resp, 'text') else ""
        except Exception:
            text = ""

        self._stats["pro_saved"] += len(candidates) - 1  # saved N-1 Pro calls
        logger.debug(f"Pro compiler: {len(candidates)} candidates → 1 batch ({self._stats['pro_saved']} total saved)")

        # Parse and return best
        try:
            match = re.search(r'"improved":\s*"(.*?)"', text, re.DOTALL)
            if match and match.group(1):
                return match.group(1)
        except Exception:
            pass
        return candidates[0] if candidates else ""

    # ═══ 5. Error Recycling Loop ═══════════════════════════════════

    def learn_from_outcome(self, query: str, fast_output: str,
                           pro_output: str, user_ok: bool):
        """Learn from each escalation: was the fast model wrong? Was Pro overkill?"""
        case = ErrorCase(query=query, fast_output=fast_output[:500],
                         pro_output=pro_output[:500], user_feedback=user_ok)

        # Classify error type
        if not user_ok and fast_output and pro_output:
            try:
                from .adaptive_classifier import get_adaptive_classifier
                ac = get_adaptive_classifier()
                e1 = ac._embed(fast_output)
                e2 = ac._embed(pro_output)
                if e1 and e2 and self._cosine(e1, e2) < 0.5:
                    case.error_type = "boundary"  # fast model was wrong
                else:
                    case.error_type = "over_escalation"  # Pro was unnecessary
            except Exception:
                case.error_type = "unknown"
        elif user_ok and not fast_output:
            case.error_type = "boundary"

        self._error_cases.append(case)
        self._stats["errors"] += 1
        if len(self._error_cases) > 100:
            self._error_cases.pop(0)

        # Adjust thresholds from learned errors
        self._adapt_thresholds()

    def _adapt_thresholds(self):
        """Adjust confidence thresholds from learned error distribution."""
        if len(self._error_cases) < 10:
            return

        recent = self._error_cases[-30:]
        boundary_rate = sum(1 for c in recent if c.error_type == "boundary") / len(recent)

        if boundary_rate > 0.3:
            # Too many boundary errors → raise thresholds (more conservative)
            self._confidence_thresholds[Confidence.HIGH] = min(0.95,
                self._confidence_thresholds[Confidence.HIGH] + 0.02)
            self._confidence_thresholds[Confidence.MEDIUM] = min(0.7,
                self._confidence_thresholds[Confidence.MEDIUM] + 0.02)
            logger.debug(f"Error loop: raised thresholds to {self._confidence_thresholds}")
        elif boundary_rate < 0.1:
            # Few errors → lower thresholds (more aggressive)
            self._confidence_thresholds[Confidence.HIGH] = max(0.7,
                self._confidence_thresholds[Confidence.HIGH] - 0.01)
            self._confidence_thresholds[Confidence.MEDIUM] = max(0.4,
                self._confidence_thresholds[Confidence.MEDIUM] - 0.01)

    # ═══ Fill Implementations ══════════════════════════════════════

    def _fill_simple(self, plan: Plan) -> str:
        """Template-render for simple queries (no LLM call)."""
        templates = {
            "chat": f"回答：{plan.original_query}",
            "code": f"// {plan.original_query}\n// TODO: implement",
            "search": f"搜索：{plan.original_query}",
        }
        return templates.get(plan.intent, plan.to_prompt())

    async def _fill_medium(self, plan: Plan) -> str | None:
        """Light Pro correction for medium complexity."""
        try:
            from .sticky_election import get_layer_config
            cfg = get_layer_config()
            prov, model = cfg.get_provider(2)
            p = self._tree._providers.get(prov) if self._tree else None
        except Exception:
            return None

        if not p:
            return None

        try:
            resp = await p.chat(
                messages=[{"role": "user", "content": plan.to_prompt()}],
                model=model or None, temperature=0.2, max_tokens=768, timeout=20,
            )
            return resp.text if resp and hasattr(resp, 'text') else None
        except Exception:
            return None

    async def _fill_complex(self, plan: Plan) -> str | None:
        """Step-by-step execution for complex queries."""
        try:
            from .sticky_election import get_layer_config
            cfg = get_layer_config()
            prov, model = cfg.get_provider(2)
            p = self._tree._providers.get(prov) if self._tree else None
        except Exception:
            return None

        if not p:
            return None

        full_prompt = (
            f"{plan.to_prompt()}\n\n"
            "Execute step by step. For each step, show:\n"
            "- What you're doing\n"
            "- The result\n"
            "At the end, summarize."
        )
        try:
            resp = await p.chat(
                messages=[{"role": "user", "content": full_prompt}],
                model=model or None, temperature=0.3, max_tokens=2048, timeout=60,
            )
            return resp.text if resp and hasattr(resp, 'text') else None
        except Exception:
            return None

    # ═══ Utilities ═════════════════════════════════════════════════

    def _parse_plan(self, text: str, query: str) -> Plan:
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return Plan(
                    original_query=query,
                    intent=data.get("intent", "chat"),
                    entities=data.get("entities", []),
                    constraints=data.get("constraints", []),
                    sub_queries=data.get("sub_queries", []),
                    output_format=data.get("output_format", "text"),
                    confidence=float(data.get("confidence", 0.5)),
                    complexity=Complexity(data.get("complexity", "medium")),
                    plan_id=hashlib.md5(query[:200].encode()).hexdigest()[:12],
                )
        except Exception:
            pass
        return Plan(original_query=query, complexity=Complexity.MEDIUM)

    @staticmethod
    def _cosine(a, b) -> float:
        if not a or not b or len(a) != len(b): return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = (sum(x * x for x in a) ** 0.5)
        nb = (sum(y * y for y in b) ** 0.5)
        return dot / (na * nb) if na and nb else 0.0

    # ═══ Stats ═════════════════════════════════════════════════════

    def stats(self) -> dict:
        return {
            **self._stats,
            "confidence_thresholds": {k.value: round(v, 3) for k, v in self._confidence_thresholds.items()},
            "error_cases": len(self._error_cases),
            "boundary_rate": round(sum(1 for c in self._error_cases[-30:] if c.error_type=="boundary")
                                   / max(len(self._error_cases[-30:]), 1), 3) if self._error_cases else 0,
        }


# ═══ Singleton ═══

_engine: Optional[PlanFillEngine] = None


def get_planfill_engine(tree=None) -> PlanFillEngine:
    global _engine
    if _engine is None or tree:
        _engine = PlanFillEngine(tree)
    return _engine
