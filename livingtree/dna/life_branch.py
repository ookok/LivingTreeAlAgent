"""LifeBranch — Branching and hypothesis exploration mixin for LifeEngine.

Extracted from life_engine.py: fork/compare/merge/list/_should_branch.
Defines the BranchMixin class that LifeEngine inherits from.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from loguru import logger

from .life_context import Branch, ComparisonReport, BranchDecision, LifeContext


class BranchMixin:
    """Branching operations for hypothesis-driven exploration.

    This mixin provides fork/compare/merge/list branch utilities
    that operate on self._branches (a dict[str, Branch] attribute
    expected to exist on the owning LifeEngine instance).
    """

    _branches: dict[str, Branch]

    def fork_branch(self, name: str, hypothesis: str, ctx: LifeContext) -> Branch:
        branch_id = f"branch-{uuid.uuid4().hex[:8]}"
        snapshot: dict[str, Any] = {
            "plan": ctx.plan,
            "retrieved_knowledge": ctx.retrieved_knowledge,
        }
        b = Branch(
            id=branch_id,
            name=name,
            hypothesis=hypothesis,
            parent_session=ctx.session_id,
            created_at=datetime.utcnow().isoformat(),
            context_snapshot=snapshot,
            plan=list(ctx.plan),
            execution_results=list(ctx.execution_results),
            reflections=list(ctx.reflections),
            success_rate=ctx.metadata.get("success_rate", 0.0),
            metadata=dict(ctx.metadata),
        )
        self._branches[branch_id] = b
        logger.info(f"[branch] forked new branch {branch_id} from session {ctx.session_id}")
        return b

    def compare_branches(self, branch_ids: list[str] | None = None) -> ComparisonReport:
        if branch_ids is None:
            candidates = [b for b in self._branches.values() if b.status in ("completed", "merged")]
        else:
            candidates = [self._branches[bid] for bid in branch_ids if bid in self._branches]
        if not candidates:
            return ComparisonReport(branches_compared=[], winner="", winner_score=0.0, scores={})

        scores = {b.id: (b.success_rate, len(b.execution_results)) for b in candidates}
        winner = max(candidates, key=lambda b: (b.success_rate, len(b.execution_results)))
        winner_score = scores[winner.id][0]
        all_ids = [b.id for b in candidates]

        report = ComparisonReport(
            branches_compared=all_ids,
            winner=winner.id,
            winner_score=float(winner_score),
            scores={b.id: scores[b.id][0] for b in candidates},
            improvements=[],
            regressions=[],
            recommendation=f"Selected {winner.id} as best branch based on highest success rate and progress.",
        )
        logger.info(f"[branch] comparison done: winner={report.winner}")
        return report

    def merge_branch(self, branch_id: str, strategy: str = "best") -> Branch | None:
        target = self._branches.get(branch_id)
        if not target:
            return None

        if self._branches:
            winner = max(self._branches.values(), key=lambda b: (b.success_rate, len(b.execution_results)))
        else:
            winner = target

        if strategy == "best" and winner:
            target.execution_results = list(winner.execution_results)
            target.plan = list(winner.plan)
            target.success_rate = winner.success_rate
        elif strategy == "concat":
            merged: list[Any] = []
            for b in self._branches.values():
                merged.extend(b.execution_results)
            target.execution_results = merged
            target.plan = [step for b in self._branches.values() for step in b.plan]
            target.success_rate = max(b.success_rate for b in self._branches.values()) if self._branches else target.success_rate
        elif strategy == "voting":
            if target.plan:
                target.plan = target.plan

        target.status = "merged"
        logger.info(f"[branch] merged branch {branch_id} using strategy '{strategy}'")
        return target

    def list_branches(self) -> list[Branch]:
        return list(self._branches.values())

    def _should_branch(self, ctx: LifeContext) -> BranchDecision:
        hypotheses = ctx.metadata.get("hypotheses", []) or []
        explore_mode = ctx.metadata.get("explore_mode", False)
        complexity = len(ctx.user_input) if ctx.user_input else 0
        threshold = 50
        should = len(hypotheses) >= 2 or explore_mode or complexity > threshold
        return BranchDecision(
            should_branch=should,
            reason=(
                "multiple hypotheses detected" if len(hypotheses) >= 2
                else "explore_mode" if explore_mode else "complexity"
            ),
            num_branches=len(hypotheses) if hypotheses else 1,
            hypotheses=hypotheses,
            confidence=0.7,
        )
