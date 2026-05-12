"""Rationale-Generation Layer — self-explaining agent based on ACL 2017.

Based on: Ling, Yogatama, Dyer, Blunsom (2017, DeepMind, ACL)
  "Program Induction by Rationale Generation"

Core insight: Rationales (step-by-step natural language explanations) serve
as a bridge between problems and programs. They provide intermediate milestones
that make complex decisions feasible and auditable.

LivingTree application:
  Every agent decision (skill selection, code mutation, plan generation,
  provider choice, compilation) generates a rationale explaining WHY.
  Rationales become:
    1. Training data for future decisions (rationale → better decisions)
    2. Visibility artifacts (user sees WHY, not just WHAT)
    3. Verification anchors (check if rationale holds for similar queries)
    4. Mutation guidance (rationale reveals which part of decision was wrong)
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════
# Rationale Data Types
# ═══════════════════════════════════════════════════════

class DecisionType(str, Enum):
    SKILL_SELECT = "skill_select"        # Why this skill was chosen
    CODE_MUTATION = "code_mutation"      # Why this code change
    PLAN_GENERATION = "plan_generation"  # Why this plan structure
    PROVIDER_CHOICE = "provider_choice"  # Why this model
    COMPILATION = "compilation"          # Why this path was compiled
    TOOL_SELECT = "tool_select"           # Why this tool
    ROLE_ASSIGN = "role_assign"          # Why this role
    REJECTION = "rejection"              # Why a candidate was rejected
    EXPLORATION = "exploration"          # Why explore instead of exploit


@dataclass
class Rationale:
    """A self-contained explanation of WHY a decision was made.

    Like the paper's "rationales" — not the program itself,
    but the natural-language scaffolding that makes it understandable.
    """
    decision_type: DecisionType
    what_was_chosen: str        # The selected option
    what_was_rejected: list[str] = field(default_factory=list)  # Alternatives considered
    why_chosen: str = ""         # Reasoning chain (the actual rationale)
    evidence: list[str] = field(default_factory=list)  # Facts supporting this decision
    confidence: float = 0.5
    # Paper's key concept: intermediate milestones
    intermediate_steps: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    session_id: str = ""

    def to_human_readable(self) -> str:
        """Render rationale as human-readable explanation."""
        lines = [
            f"📋 Decision: {self.decision_type.value}",
            f"   ✅ Chose: {self.what_was_chosen}",
        ]
        if self.what_was_rejected:
            lines.append(f"   ❌ Rejected: {', '.join(self.what_was_rejected[:3])}")
        lines.append(f"   💡 Why: {self.why_chosen}")
        if self.intermediate_steps:
            lines.append("   🔗 Steps:")
            for step in self.intermediate_steps:
                lines.append(f"      → {step}")
        lines.append(f"   📊 Confidence: {self.confidence:.0%}")
        return "\n".join(lines)

    def to_compact(self) -> str:
        """Ultra-compact rationale for LLM injection — minimal tokens."""
        return (
            f"[RATIONALE:{self.decision_type.value}] "
            f"chose='{self.what_was_chosen[:40]}' "
            f"because='{self.why_chosen[:80]}' "
            f"conf={self.confidence:.2f}"
        )

    def verify(self, new_context: dict) -> bool:
        """Check if rationale still holds under new context.

        Paper's insight: rationale = intermediate milestone.
        If the milestone no longer makes sense, the decision is suspect.
        """
        # Check if evidence still supports the decision
        for evidence_item in self.evidence:
            context_str = str(new_context).lower()
            if evidence_item.lower() not in context_str:
                return False  # Evidence missing → rationale invalidated
        return True


# ═══════════════════════════════════════════════════════
# Rationale Generator — produce self-explanations
# ═══════════════════════════════════════════════════════

class RationaleGenerator:
    """Generate rationales for every agent decision.

    The paper's key method: instead of directly outputting a program,
    first generate rationale scaffolding.

    Applied to LivingTree: every decision-producing module calls
    generate_rationale() to attach a self-explanation.
    """

    # Decision templates — the "scaffolding" from the paper
    REASONING_TEMPLATES = {
        DecisionType.SKILL_SELECT: (
            "Chose skill '{chosen}' over {rejected} for task '{context}'. "
            "Reasoning: skill fitness={fitness:.2f}, domain match={domain}, "
            "usage history={usage} successes. "
            "Rejected alternatives had lower fitness or domain mismatch."
        ),
        DecisionType.CODE_MUTATION: (
            "Applied mutation '{chosen}' to {file}. "
            "Reasoning: fitness signal '{signal}' scored {score:.2f} (below threshold). "
            "Mutation type targets {target_improvement}. "
            "Expected impact: {expected_impact}."
        ),
        DecisionType.PLAN_GENERATION: (
            "Generated {step_count}-step plan with {topology} topology. "
            "Reasoning: query complexity={complexity:.2f}, domain={domain}. "
            "Deep planning triggered because complexity > 0.6. "
            "Token Accountant approved {approved}/{total} steps."
        ),
        DecisionType.PROVIDER_CHOICE: (
            "Selected provider '{chosen}' over {rejected}. "
            "Reasoning: Thompson sample={sample:.2f}, latency={latency}ms, "
            "cost={cost}/1k tokens. "
            "Rejected providers had lower Thompson samples or were circuit-broken."
        ),
        DecisionType.COMPILATION: (
            "Compiled intent '{intent}' at {level} level. "
            "Reasoning: {cache_status}. "
            "Compiled {tool_count} tool calls into direct execution path. "
            "Next identical query → NATIVE (< 500ms)."
        ),
        DecisionType.REJECTION: (
            "Rejected '{rejected_option}'. "
            "Reasoning: {rejection_reason}. "
            "Alternative '{chosen}' selected instead because {chosen_reason}."
        ),
        DecisionType.EXPLORATION: (
            "Choosing EXPLORATION over exploitation. "
            "Reasoning: exploration_rate={rate:.2f}, confidence_drop={drop:.2f}. "
            "Trying {novel_option} to discover better alternatives."
        ),
    }

    def generate(self, decision_type: DecisionType, **kwargs) -> Rationale:
        """Generate a rationale from a decision template + context.

        The template provides the SCAFFOLDING (paper's key insight).
        Context fills in the specifics.
        """
        template = self.REASONING_TEMPLATES.get(decision_type, "")

        # Fill template with context
        why_chosen = template.format(**kwargs) if template else str(kwargs.get("reason", ""))

        # Extract intermediate milestones
        milestones = self._extract_milestones(decision_type, kwargs)

        return Rationale(
            decision_type=decision_type,
            what_was_chosen=kwargs.get("chosen", kwargs.get("what", "")),
            what_was_rejected=kwargs.get("rejected", []),
            why_chosen=why_chosen,
            evidence=kwargs.get("evidence", []),
            confidence=kwargs.get("confidence", 0.5),
            intermediate_steps=milestones,
        )

    def _extract_milestones(self, decision_type: DecisionType, kwargs: dict) -> list[str]:
        """Extract intermediate milestones from the decision context.

        Paper's key concept: each rationale contains milestones that
        break down a complex program into manageable steps.
        """
        milestones = []

        if decision_type == DecisionType.PLAN_GENERATION:
            milestones = [
                f"Complexity assessment: {kwargs.get('complexity', 0):.2f}",
                f"Topology selection: {kwargs.get('topology', 'sequential')}",
                f"Step allocation: {kwargs.get('approved', 1)}/{kwargs.get('total', 1)} steps approved",
            ]
        elif decision_type == DecisionType.PROVIDER_CHOICE:
            milestones = [
                f"Thompson sampling: {kwargs.get('sample', 0):.2f}",
                f"Latency check: {kwargs.get('latency', 0)}ms",
                f"Cost check: {kwargs.get('cost', 0)}/1k tokens",
            ]
        elif decision_type == DecisionType.CODE_MUTATION:
            milestones = [
                f"Signal analysis: {kwargs.get('signal', 'unknown')} = {kwargs.get('score', 0):.2f}",
                f"Mutation selection: {kwargs.get('chosen', 'unknown')}",
                f"Sandbox testing: {'passed' if kwargs.get('tests_passed', False) else 'failed'}",
            ]

        return milestones


# ═══════════════════════════════════════════════════════
# Rationale Store — persistent explanation history
# ═══════════════════════════════════════════════════════

class RationaleStore:
    """Store and retrieve rationales for learning and verification.

    Rationales accumulate over time → become training data for:
      - Better future decisions (pattern: "what reasoning led to success?")
      - Verification anchors ("does this decision still make sense?")
      - Mutation guidance ("which part of the rationale was wrong?")
    """

    def __init__(self, store_path: str = ".livingtree/rationales.json"):
        self._store = Path(store_path)
        self._rationales: list[Rationale] = []
        self._by_type: dict[DecisionType, list[int]] = defaultdict(list)
        self._by_session: dict[str, list[int]] = defaultdict(list)
        self._load()

    def store(self, rationale: Rationale) -> int:
        """Store a rationale — return its index."""
        idx = len(self._rationales)
        self._rationales.append(rationale)
        self._by_type[rationale.decision_type].append(idx)
        if rationale.session_id:
            self._by_session[rationale.session_id].append(idx)
        self._save()
        return idx

    def query_by_type(self, decision_type: DecisionType, n: int = 10) -> list[Rationale]:
        """Get recent rationales of a specific decision type."""
        indices = self._by_type.get(decision_type, [])[-n:]
        return [self._rationales[i] for i in indices]

    def query_by_session(self, session_id: str) -> list[Rationale]:
        """Get all rationales for a session."""
        indices = self._by_session.get(session_id, [])
        return [self._rationales[i] for i in indices]

    def verify_decisions(self, session_id: str, new_context: dict) -> list[dict]:
        """Re-verify all decisions in a session against new context.

        Paper's insight: rationales are intermediate milestones.
        If the milestone is invalidated, the decision needs review.
        """
        results = []
        for rationale in self.query_by_session(session_id):
            valid = rationale.verify(new_context)
            results.append({
                "decision_type": rationale.decision_type.value,
                "chosen": rationale.what_was_chosen[:60],
                "still_valid": valid,
                "confidence": rationale.confidence,
            })
        return results

    def train_from_successful(self, decision_type: DecisionType) -> list[str]:
        """Extract reasoning patterns from successful decisions.

        This is the paper's core mechanism: rationales from successful
        outcomes become templates for future decisions.
        """
        successful = [
            r for r in self.query_by_type(decision_type, 50)
            if r.confidence > 0.7
        ]
        patterns = []
        for r in successful[:10]:
            # Extract the "why" as a transferable pattern
            patterns.append(r.why_chosen[:200])
        return patterns

    def find_wrong_rationales(self, failed_session_id: str) -> list[dict]:
        """For a failed session, identify which rationales were wrong.

        This guides mutation: "this reasoning led to failure → try different logic."
        """
        wrong = []
        for rationale in self.query_by_session(failed_session_id):
            if rationale.confidence < 0.3:
                wrong.append({
                    "decision": rationale.decision_type.value,
                    "wrong_reasoning": rationale.why_chosen[:150],
                    "suggested_fix": (
                        f"For '{rationale.decision_type.value}', "
                        f"reconsider the evidence: {', '.join(rationale.evidence[:3])}"
                    ),
                })
        return wrong

    def _load(self) -> None:
        try:
            if self._store.exists():
                data = json.loads(self._store.read_text("utf-8"))
                for r in data:
                    rationale = Rationale(
                        decision_type=DecisionType(r["decision_type"]),
                        what_was_chosen=r["what_was_chosen"],
                        what_was_rejected=r.get("what_was_rejected", []),
                        why_chosen=r.get("why_chosen", ""),
                        evidence=r.get("evidence", []),
                        confidence=r.get("confidence", 0.5),
                        intermediate_steps=r.get("intermediate_steps", []),
                        session_id=r.get("session_id", ""),
                    )
                    self.store(rationale)
        except Exception:
            pass

    def _save(self) -> None:
        try:
            self._store.parent.mkdir(parents=True, exist_ok=True)
            data = [{
                "decision_type": r.decision_type.value,
                "what_was_chosen": r.what_was_chosen,
                "what_was_rejected": r.what_was_rejected,
                "why_chosen": r.why_chosen,
                "evidence": r.evidence,
                "confidence": r.confidence,
                "intermediate_steps": r.intermediate_steps,
                "timestamp": r.timestamp,
                "session_id": r.session_id,
            } for r in self._rationales[-1000:]]  # Keep last 1000
            self._store.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        except Exception:
            pass

    @property
    def size(self) -> int:
        return len(self._rationales)


# ═══════════════════════════════════════════════════════
# Self-Explaining Agent — all decisions produce rationales
# ═══════════════════════════════════════════════════════

class SelfExplainingAgent:
    """Every decision this agent makes is accompanied by a rationale.

    Like the paper's approach: programs are not directly induced.
    Rationales provide the scaffolding that makes decisions:
      - Explainable (user sees WHY)
      - Learnable (successful rationales guide future decisions)
      - Verifiable (check if rationale still holds)
      - Auditable (trace every decision back to its reasoning)
    """

    def __init__(self):
        self.generator = RationaleGenerator()
        self.store = RationaleStore()

    def decide_skill(self, query: str, candidates: list[dict],
                     chosen: str, fitness: float, session_id: str = "") -> Rationale:
        """Generate rationale for skill selection."""
        r = self.generator.generate(
            DecisionType.SKILL_SELECT,
            chosen=chosen,
            rejected=[c.get("name", "") for c in candidates[:3] if c.get("name") != chosen],
            context=query[:60],
            fitness=fitness,
            domain=candidates[0].get("domain", "general") if candidates else "general",
            usage=3,
        )
        r.session_id = session_id
        self.store.store(r)
        return r

    def decide_plan(self, query: str, steps: int, topology: str,
                    complexity: float, approved: int, total: int) -> Rationale:
        """Generate rationale for plan generation."""
        r = self.generator.generate(
            DecisionType.PLAN_GENERATION,
            chosen=f"{steps}-step {topology} plan",
            step_count=steps,
            topology=topology,
            complexity=complexity,
            domain="general",
            approved=approved,
            total=total,
            confidence=approved / max(1, total),
        )
        self.store.store(r)
        return r

    def decide_provider(self, chosen: str, rejected: list[str],
                        sample: float, latency: float, cost: float) -> Rationale:
        """Generate rationale for provider choice."""
        r = self.generator.generate(
            DecisionType.PROVIDER_CHOICE,
            chosen=chosen,
            rejected=rejected,
            sample=sample,
            latency=latency,
            cost=cost,
            confidence=sample,
        )
        self.store.store(r)
        return r

    def session_report(self, session_id: str) -> str:
        """Generate comprehensive rationale report for a session."""
        rationales = self.store.query_by_session(session_id)
        if not rationales:
            return "No decisions recorded for this session."

        lines = [f"📋 DECISION RATIONALE REPORT — Session {session_id[:12]}"]
        lines.append(f"   Total decisions: {len(rationales)}")
        lines.append("")

        for i, r in enumerate(rationales):
            lines.append(f"  Decision {i+1}/ {len(rationales)}:")
            lines.append(f"  {r.to_compact()}")
            lines.append("")

        # Verification: check which decisions need review
        invalid = [r for r in rationales if r.confidence < 0.3]
        if invalid:
            lines.append(f"  ⚠️ {len(invalid)} low-confidence decisions need review:")
            for r in invalid:
                lines.append(f"     - {r.decision_type.value}: {r.what_was_chosen[:50]}")

        return "\n".join(lines)

    def learn_from_outcomes(self, success: bool, session_id: str) -> list[str]:
        """Extract learning signals from session outcomes.

        Success → extract reasoning patterns as training data.
        Failure → identify wrong rationales to guide mutations.
        """
        if success:
            rationales = self.store.query_by_session(session_id)
            patterns = []
            for r in rationales:
                if r.confidence > 0.5:
                    patterns.append(r.why_chosen[:150])
            return patterns
        else:
            wrong = self.store.find_wrong_rationales(session_id)
            return [w["suggested_fix"] for w in wrong]


# ── Singleton ──

_agent: Optional[SelfExplainingAgent] = None


def get_self_explaining_agent() -> SelfExplainingAgent:
    global _agent
    if _agent is None:
        _agent = SelfExplainingAgent()
    return _agent
