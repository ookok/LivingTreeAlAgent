"""CoFEE Cognitive Reasoning Control — structured inductive biases for LLM agents.

Based on Westermann et al. (Oxford, 2026), arXiv:2604.21584:
  "CoFEE: Reasoning Control for LLM-Based Feature Discovery"
  +15.2% success rate, -29% fewer outputs, -53.3% cost reduction

Core insight: unconstrained LLM generation produces noisy, leaky, redundant
outputs. Enforcing four cognitive behaviors as structured prompt constraints
acts as inductive biases, yielding higher-quality, more efficient generation.

Four cognitive behavior constraints (mapped to LivingTree):
  1. BACKWARD CHAINING — start from the goal, work backward to steps.
     Each step must explain HOW it contributes to the final outcome.
  2. SUBGOAL DECOMPOSITION — break complex tasks into verifiable subgoals.
     Each subgoal must be independently checkable.
  3. VERIFICATION (observability + non-leakage) — every proposed action must:
     a) Be observable (can we verify it happened?)
     b) Be non-leaking (no future information, no proxy variables)
     c) Have a clear causal hypothesis
  4. BACKTRACKING — explicitly record rejected alternatives and WHY they
     were rejected. This prevents the LLM from silently converging on suboptimal paths.

Three-agent pipeline (CoFEE analog):
  Agent 1 (DISCOVER)  → Idea Agent: generates candidate plans/hypotheses
  Agent 2 (MERGE)     → Reviewer: deduplicates, merges semantically similar
  Agent 3 (EVALUATE)  → PlanValidator: statistical evaluation on held-out criteria

Integration:
  ResearchTeam Reviewer → enhanced with cognitive constraint prompts
  PlanValidator → enhanced with backward chaining + verification
  GTSMPlanner → backtracking records rejected alternatives
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


# ═══ Data Types ═══


class CognitiveBehavior(str, Enum):
    BACKWARD_CHAIN = "backward_chain"      # Goal → steps reasoning
    SUBGOAL_DECOMPOSE = "subgoal_decompose" # Break into verifiable chunks
    VERIFY = "verify"                       # Observability + non-leakage check
    BACKTRACK = "backtrack"                 # Record rejected alternatives


@dataclass
class VerificationResult:
    """Result of verification against cognitive constraints."""
    step_id: str
    # Backward chain: does this step logically lead to the goal?
    backward_chain_valid: bool = True
    backward_chain_reason: str = ""
    # Subgoal: is this independently verifiable?
    subgoal_verifiable: bool = True
    subgoal_reason: str = ""
    # Observability: can we know if this step succeeded?
    observable: bool = True
    observable_reason: str = ""
    # Non-leakage: does this step use information that shouldn't exist yet?
    non_leaking: bool = True
    leakage_reason: str = ""
    # Causal hypothesis: can we articulate why this step causes the outcome?
    has_causal_hypothesis: bool = True
    causal_hypothesis: str = ""
    # Overall
    passed: bool = True
    score: float = 1.0
    fix_suggestions: list[str] = field(default_factory=list)


@dataclass
class BacktrackRecord:
    """A rejected alternative and why it was rejected."""
    alternative: str               # What was considered
    why_rejected: str              # Why it was not chosen
    cognitive_behavior: str        # Which constraint it violated
    better_alternative: str = ""   # What was chosen instead
    timestamp: float = 0.0


@dataclass
class CognitiveAudit:
    """Complete cognitive audit of a plan/hypothesis generation."""
    plan_id: str
    steps_verified: list[VerificationResult]
    backtrack_records: list[BacktrackRecord]
    # Metrics
    total_steps: int
    steps_passed: int
    pass_rate: float
    avg_score: float
    # Cost
    steps_before_merge: int       # Before deduplication
    steps_after_merge: int        # After semantic merge
    compression_ratio: float      # How much was saved
    # Summary
    recommendation: str = ""


# ═══ CoFEE Cognitive Prompts ═══


class CoFEEPrompts:
    """Structured prompt templates enforcing cognitive behaviors.

    These prompts are designed as "inductive biases" — they constrain
    the LLM's generation space toward higher-quality outputs without
    requiring model modification or fine-tuning.

    The key CoFEE insight: unconstrained prompts produce many weak outputs;
    constrained prompts produce fewer, stronger outputs.
    """

    # ═══ Backward Chaining ═══
    BACKWARD_CHAIN_PROMPT = """[Cognitive Constraint: BACKWARD CHAINING]

You are generating a plan to achieve this goal: {goal}

IMPORTANT: Work backward from the goal. For each step you propose, you MUST:
1. State explicitly: "This step contributes to the goal by..."
2. Show the causal chain: step → intermediate outcome → final goal
3. If you cannot articulate how a step leads to the goal, DO NOT include it.

Format each step as:
```
Step N: [action]
→ Contributes to goal by: [explicit causal link]
→ Depends on: [prerequisites]
→ Verifiable by: [how we know it worked]
```"""

    # ═══ Subgoal Decomposition ═══
    SUBGOAL_DECOMPOSE_PROMPT = """[Cognitive Constraint: SUBGOAL DECOMPOSITION]

The task "{task}" is complex. Before proposing a solution, decompose it into
independently verifiable subgoals. Each subgoal must:

1. Be independently checkable — can someone verify it was achieved without
   knowing the result of other subgoals?
2. Have a clear completion criterion — "done" must be unambiguous
3. Not depend on information from future subgoals (no leakage)

Produce a numbered list of subgoals, then propose steps for each."""

    # ═══ Verification (Observability + Non-Leakage) ═══
    VERIFY_PROMPT = """[Cognitive Constraint: VERIFICATION]

Review the following proposed output: {output}

For EACH step or claim, verify:
1. OBSERVABILITY: Can we independently verify this succeeded?
   If NOT observable, mark as REJECT and explain why.
2. NON-LEAKAGE: Does this step use information that would not exist
   at the time of execution? (future data, post-outcome signals)
   If YES, mark as REJECT — this is data leakage.
3. CAUSAL HYPOTHESIS: Can we state WHY this step causes the outcome?
   If NO causal link, mark as LOW_CONFIDENCE.

Output format:
```
Step checked: [step description]
✓/✗ Observable: [reason]
✓/✗ Non-leaking: [reason]
✓/✗ Causal link: [hypothesis or reason absent]
Overall: ACCEPT / REJECT / MODIFY
Modification if needed: [specific fix]
```"""

    # ═══ Backtracking ═══
    BACKTRACK_PROMPT = """[Cognitive Constraint: BACKTRACKING]

Before finalizing your answer, explicitly list:
1. At least 2 alternative approaches you considered but rejected
2. WHY each was rejected (which cognitive constraint it violated)
3. Why the chosen approach is superior

Format:
```
Rejected Alternative 1: [description]
→ Rejected because: [violated constraint X / less efficient / no causal link]

Rejected Alternative 2: [description]
→ Rejected because: [reason]

Chosen approach: [description]
→ Chosen because: [superiority rationale]
```"""

    # ═══ Merged Agent Review Prompt (CoFEE 3-agent pipeline) ═══
    AGENT_REVIEW_PROMPT = """[CoFEE Cognitive Review — Agent 2: MERGE + Agent 3: EVALUATE]

You are reviewing candidate outputs from the discovery agent. Perform TWO tasks:

TASK A — MERGE (deduplication):
  - Identify semantically duplicate candidates
  - Merge them into a single, stronger candidate
  - Record: {before_count} candidates → {after_count} candidates

TASK B — EVALUATE (verification):
  - For each remaining candidate, apply ALL four cognitive checks:
    1. Backward chain to goal
    2. Subgoal decomposability
    3. Observability + non-leakage
    4. Alternative consideration (backtracking)

Candidates to review:
{candidates}

Original goal: {goal}
"""


# ═══ CoFEE Cognitive Engine ═══


class CoFEECognitiveEngine:
    """Enforces cognitive behaviors on LLM agent outputs.

    Uses structured prompt constraints (not model modification) to generate
    higher-quality plans, hypotheses, and research outputs.

    Three-agent pipeline (paper's core architecture):
      Agent 1 (DISCOVER) → generates candidates under cognitive constraints
      Agent 2 (MERGE)    → deduplicates semantically similar outputs
      Agent 3 (EVALUATE) → verifies against all four cognitive criteria

    Integration points:
      - ResearchTeam Reviewer: enhanced with cognitive constraint prompts
      - PlanValidator: enhanced with backward chain + verifiability
      - GTSMPlanner: backtracking records rejected alternatives
      - PipelineOrchestrator: auto-selects CoFEE-constrained pipeline variant
    """

    # Verification thresholds
    MIN_CAUSAL_SCORE = 0.3
    LEAKAGE_KEYWORDS = [
        "最终结果", "事后", "回过头看", "最终证明",
        "actual outcome", "after the fact", "hindsight",
        "resulting in", "which led to", "turned out",
    ]

    def __init__(self):
        self._backtrack_history: list[BacktrackRecord] = []
        self._audits: list[CognitiveAudit] = []

    # ═══ Backward Chain Validation ═══

    def check_backward_chain(
        self, step: str, goal: str,
    ) -> tuple[bool, str]:
        """Check if a step logically connects backward to the goal.

        Heuristic: does the step contain goal-relevant keywords?
        For full accuracy, this would use an LLM call with the structured prompt.
        The heuristic provides fast first-pass filtering.
        """
        step_lower = step.lower()
        goal_words = set(goal.lower().split())
        step_words = set(step_lower.split())

        overlap = len(goal_words & step_words)
        if overlap == 0:
            return False, f"No keyword overlap with goal '{goal[:40]}...'"
        if overlap >= 2:
            return True, f"Strong keyword overlap ({overlap} words) with goal"
        return True, f"Weak keyword overlap ({overlap} word) — verify with LLM"

    # ═══ Subgoal Verifiability ═══

    def check_subgoal_verifiable(self, step: str) -> tuple[bool, str]:
        """Check if a step is independently verifiable as a subgoal.

        A subgoal is verifiable if:
        - It has a clear action (not vague "think about" or "consider")
        - It produces a concrete output
        - Its success/failure can be determined independently
        """
        step_lower = step.lower()
        # Vague actions that are NOT independently verifiable
        vague = ["思考", "考虑", "研究", "探索", "think", "ponder", "explore", "look into"]
        for v in vague:
            if v in step_lower:
                return False, f"Contains vague action '{v}' — no clear success criterion"
        # Concrete actions that ARE verifiable
        concrete = ["生成", "创建", "计算", "检索", "提取", "写入", "执行",
                     "generate", "create", "compute", "retrieve", "extract",
                     "write", "execute", "run", "build"]
        for c in concrete:
            if c in step_lower:
                return True, f"Contains concrete action '{c}'"
        return False, "No verifiable action found — needs concretization"

    # ═══ Observability Check ═══

    def check_observable(self, step: str) -> tuple[bool, str]:
        """Can we independently observe whether this step succeeded?

        Observable: produces file, returns data, changes visible state
        Not observable: internal reasoning, "understanding", "realizing"
        """
        step_lower = step.lower()
        observables = ["文件", "输出", "返回", "生成", "写入", "数据",
                        "file", "output", "return", "generate", "write", "data",
                        "result", "report"]
        for o in observables:
            if o in step_lower:
                return True, f"Produces observable '{o}'"
        return False, "No observable output specified"

    # ═══ Leakage Detection ═══

    def check_leakage(self, step: str) -> tuple[bool, str]:
        """Check if a step uses information that shouldn't exist yet.

        Data leakage = using post-outcome information during planning.
        This is a critical failure mode for LLM-generated plans.
        """
        step_lower = step.lower()
        for keyword in self.LEAKAGE_KEYWORDS:
            if keyword.lower() in step_lower:
                return False, f"Potential leakage: uses post-hoc keyword '{keyword}'"
        return True, "No leakage indicators detected"

    # ═══ Causal Hypothesis Check ═══

    def check_causal(self, step: str, goal: str) -> tuple[bool, str]:
        """Does this step have a plausible causal connection to the goal?"""
        # Check for causal language
        causal_markers = ["因为", "所以", "导致", "使得", "从而",
                           "because", "therefore", "leads to", "causes", "enables"]
        has_causal = any(m in step.lower() for m in causal_markers)
        if has_causal:
            return True, "Contains causal reasoning markers"
        # Check for action → outcome pattern
        if "→" in step or "->" in step or "=>" in step:
            return True, "Contains explicit causal arrow"
        return False, "No causal hypothesis articulated"

    # ═══ Full Verification ═══

    def verify_step(
        self, step_id: str, step_description: str, goal: str,
    ) -> VerificationResult:
        """Apply all four cognitive checks to a single step.

        Returns a VerificationResult with pass/fail and fix suggestions.
        """
        bc_valid, bc_reason = self.check_backward_chain(step_description, goal)
        sg_valid, sg_reason = self.check_subgoal_verifiable(step_description)
        ob_valid, ob_reason = self.check_observable(step_description)
        nl_valid, nl_reason = self.check_leakage(step_description)
        ca_valid, ca_reason = self.check_causal(step_description, goal)

        # Score: each check = 0.25
        score = (float(bc_valid) + float(sg_valid) + float(ob_valid)
                 + float(nl_valid) + float(ca_valid)) / 5.0 * 0.8
        if ca_valid:
            score += 0.2  # Bonus for explicit causal reasoning

        passed = score >= self.MIN_CAUSAL_SCORE
        suggestions = []
        if not bc_valid:
            suggestions.append(f"Add backward chain: explain how this leads to '{goal[:40]}'")
        if not sg_valid:
            suggestions.append("Concretize: replace vague action with verifiable subgoal")
        if not ob_valid:
            suggestions.append("Add observable output (file, return value, report)")
        if not nl_valid:
            suggestions.append(f"Remove post-hoc reasoning: {nl_reason}")
        if not ca_valid:
            suggestions.append("Add causal hypothesis: why this → goal")

        return VerificationResult(
            step_id=step_id,
            backward_chain_valid=bc_valid, backward_chain_reason=bc_reason,
            subgoal_verifiable=sg_valid, subgoal_reason=sg_reason,
            observable=ob_valid, observable_reason=ob_reason,
            non_leaking=nl_valid, leakage_reason=nl_reason,
            has_causal_hypothesis=ca_valid, causal_hypothesis=ca_reason,
            passed=passed, score=round(score, 3),
            fix_suggestions=suggestions,
        )

    # ═══ Full Plan Audit ═══

    def audit_plan(
        self, plan_id: str, steps: list[str], goal: str,
    ) -> CognitiveAudit:
        """Run full cognitive audit on a generated plan.

        CoFEE three-agent pipeline applied to plan verification:
          1. Verify each step against all four cognitive constraints
          2. Simulate semantic merge (count duplicates by description)
          3. Compute pass rate, compression ratio, and recommendations
        """
        verified = []
        for i, step in enumerate(steps):
            v = self.verify_step(f"step_{i}", step, goal)
            verified.append(v)

        passed_count = sum(1 for v in verified if v.passed)
        total = len(verified)
        pass_rate = passed_count / max(total, 1)
        avg_score = sum(v.score for v in verified) / max(total, 1)

        # Simulate semantic merge: detect near-duplicates
        before = total
        seen: set[str] = set()
        unique_steps = []
        for step in steps:
            normalized = " ".join(sorted(step.lower().split()[:5]))
            if normalized not in seen:
                seen.add(normalized)
                unique_steps.append(step)
        after = len(unique_steps)
        compression = after / max(before, 1)

        if pass_rate >= 0.8:
            rec = "Plan passes cognitive audit — high quality, efficient"
        elif pass_rate >= 0.5:
            rec = "Plan needs improvement — apply fix suggestions"
        else:
            rec = "Plan fails cognitive audit — regenerate with CoFEE constraints"

        audit = CognitiveAudit(
            plan_id=plan_id,
            steps_verified=verified,
            backtrack_records=list(self._backtrack_history[-10:]),
            total_steps=total, steps_passed=passed_count,
            pass_rate=round(pass_rate, 3), avg_score=round(avg_score, 3),
            steps_before_merge=before, steps_after_merge=after,
            compression_ratio=round(compression, 3),
            recommendation=rec,
        )
        self._audits.append(audit)
        return audit

    # ═══ Backtrack Recording ═══

    def record_backtrack(
        self, alternative: str, why_rejected: str,
        cognitive_behavior: str, better: str = "",
    ) -> BacktrackRecord:
        """Record a rejected alternative for transparency."""
        import time
        record = BacktrackRecord(
            alternative=alternative, why_rejected=why_rejected,
            cognitive_behavior=cognitive_behavior,
            better_alternative=better, timestamp=time.time(),
        )
        self._backtrack_history.append(record)
        if len(self._backtrack_history) > 200:
            self._backtrack_history = self._backtrack_history[-200:]
        return record

    # ═══ Prompt Builder for Agent Integration ═══

    def build_constrained_prompt(
        self, task: str, goal: str, behaviors: list[str] | None = None,
    ) -> str:
        """Build a CoFEE-constrained prompt for an LLM agent.

        Automatically includes all four cognitive behaviors unless
        a subset is specified.
        """
        behaviors = behaviors or ["backward_chain", "subgoal_decompose",
                                   "verify", "backtrack"]
        parts = ["[CoFEE Cognitive Control — constrained feature discovery]\n"]

        if "backward_chain" in behaviors:
            parts.append(CoFEEPrompts.BACKWARD_CHAIN_PROMPT.format(goal=goal))
        if "subgoal_decompose" in behaviors:
            parts.append(CoFEEPrompts.SUBGOAL_DECOMPOSE_PROMPT.format(task=task))
        if "verify" in behaviors:
            parts.append(CoFEEPrompts.VERIFY_PROMPT.format(
                output="(your proposed output)"))
        if "backtrack" in behaviors:
            parts.append(CoFEEPrompts.BACKTRACK_PROMPT)

        parts.append(f"\nTask: {task}")
        parts.append(f"Goal: {goal}")
        return "\n\n".join(parts)

    # ═══ Stats ═══

    def stats(self) -> dict[str, Any]:
        audits = self._audits[-20:] if self._audits else []
        return {
            "total_audits": len(self._audits),
            "avg_pass_rate": round(
                sum(a.pass_rate for a in audits) / max(len(audits), 1), 3),
            "avg_compression": round(
                sum(a.compression_ratio for a in audits) / max(len(audits), 1), 3),
            "backtrack_records": len(self._backtrack_history),
            "paper_targets": {
                "success_improvement": "+15.2%",
                "feature_reduction": "-29%",
                "cost_reduction": "-53.3%",
            },
        }


# ═══ Integration with Research Team ═══

def enhance_reviewer_prompt(original_prompt: str, goal: str) -> str:
    """Wrap the existing Reviewer prompt with CoFEE cognitive constraints.

    Usage in research_team.py:
        enhanced = enhance_reviewer_prompt(original_prompt, task)
    """
    engine = get_cofee_engine()
    cognitive_part = engine.build_constrained_prompt(
        task="review", goal=goal,
        behaviors=["verify", "backtrack"],
    )
    return f"{cognitive_part}\n\n{original_prompt}"


# ═══ Singleton ═══

_cofee: CoFEECognitiveEngine | None = None


def get_cofee_engine() -> CoFEECognitiveEngine:
    global _cofee
    if _cofee is None:
        _cofee = CoFEECognitiveEngine()
    return _cofee


__all__ = [
    "CoFEECognitiveEngine", "CoFEEPrompts",
    "VerificationResult", "BacktrackRecord", "CognitiveAudit",
    "CognitiveBehavior", "enhance_reviewer_prompt", "get_cofee_engine",
]
