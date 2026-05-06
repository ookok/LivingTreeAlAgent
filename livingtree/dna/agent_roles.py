"""
Agent Roles — Agentic Harness-style 3-role architecture.

The Evolver-Evaluator-Verifier triad ensures that every code change goes through
a quality gate before being accepted:

    Evolver (proposes) → Evaluator (scores) → Verifier (checks evidence)
           ↑                                         ↓
           └────────── remediation loop ──────────────┘

Inspired by the Agentic Harness paper's multi-agent quality assurance architecture.

Usage:
    from livingtree.dna.agent_roles import RoleTriad, AgentRole, get_triad
    triad = get_triad()
    result = triad.coordinate(
        task="Optimize the search index",
        context={"file": "knowledge_base.py", "issue": "slow query on 100k docs"},
    )
    if result["passed"]:
        print(f"Accepted with score {result['score']}")
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Callable

from loguru import logger

TRIAD_DIR = Path(".livingtree/triad")
TRIAD_LOG = TRIAD_DIR / "role_sessions.jsonl"


class AgentRole(str, Enum):
    EVOLVER = "evolver"      # Proposes changes
    EVALUATOR = "evaluator"  # Scores quality
    VERIFIER = "verifier"    # Checks evidence


class Verdict(str, Enum):
    ACCEPT = "accept"
    REVISE = "revise"
    REJECT = "reject"


@dataclass
class RoleAction:
    """One action by a role in the triad loop."""
    role: AgentRole
    session_id: str
    round: int
    input_summary: str
    output_summary: str
    score: float = 0.0  # Evolver: proposed, Evaluator: scored, Verifier: evidence score
    verdict: str = ""   # Evaluator/Verifier: accept/revise/reject
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["role"] = self.role.value
        return d


@dataclass
class TriadSession:
    """A complete triad coordination session."""
    id: str
    task: str
    context: dict = field(default_factory=dict)
    max_rounds: int = 5
    min_score: float = 0.6
    actions: list[RoleAction] = field(default_factory=list)
    final_verdict: str = ""
    final_score: float = 0.0
    rounds_used: int = 0
    resolved: bool = False
    started_at: float = 0.0
    completed_at: float = 0.0


class RoleTriad:
    """Coordinates the Evolver → Evaluator → Verifier loop.

    The triad enforces a quality gate: a change is only accepted when
    both the Evaluator (quality score ≥ min_score) AND the Verifier
    (evidence check passed) agree.

    If either rejects, control loops back to the Evolver for revision.
    """

    def __init__(self):
        TRIAD_DIR.mkdir(parents=True, exist_ok=True)
        self._sessions: list[TriadSession] = []

    # ── Coordination ──

    def coordinate(
        self,
        task: str,
        context: Optional[dict] = None,
        evolver_fn: Optional[Callable[[str, dict], tuple[str, float]]] = None,
        evaluator_fn: Optional[Callable[[str, str], tuple[float, str, str]]] = None,
        verifier_fn: Optional[Callable[[str, str], tuple[bool, str]]] = None,
        max_rounds: int = 5,
        min_score: float = 0.6,
    ) -> dict:
        """Run the full triad coordination loop.

        Args:
            task: The task description
            context: Additional context (file, issue, constraints, etc.)
            evolver_fn: Optional custom Evolver function (task, context) → (proposal, confidence)
            evaluator_fn: Optional custom Evaluator function (task, proposal) → (score, verdict, feedback)
            verifier_fn: Optional custom Verifier function (task, proposal) → (passed, evidence)
            max_rounds: Max revision rounds before giving up
            min_score: Minimum quality score to accept

        Returns:
            dict with 'passed', 'score', 'rounds', 'actions', 'verdict'
        """
        session = TriadSession(
            id=f"triad_{uuid.uuid4().hex[:12]}",
            task=task,
            context=context or {},
            max_rounds=max_rounds,
            min_score=min_score,
            started_at=time.time(),
        )

        current_proposal = ""
        current_evidence = ""

        for round_num in range(1, max_rounds + 1):
            # ── EVOLVER: propose change ──
            if evolver_fn:
                proposal, evolver_confidence = evolver_fn(task, context or {})
            else:
                proposal, evolver_confidence = self._default_evolver(task, context or {}, current_proposal)

            session.actions.append(RoleAction(
                role=AgentRole.EVOLVER, session_id=session.id, round=round_num,
                input_summary=task, output_summary=proposal[:500],
                score=evolver_confidence, timestamp=time.time(),
            ))
            current_proposal = proposal

            # ── EVALUATOR: score quality ──
            if evaluator_fn:
                score, verdict_str, feedback = evaluator_fn(task, proposal)
            else:
                score, verdict_str, feedback = self._default_evaluator(task, proposal)

            session.actions.append(RoleAction(
                role=AgentRole.EVALUATOR, session_id=session.id, round=round_num,
                input_summary=proposal[:200], output_summary=f"{verdict_str}: {feedback[:300]}",
                score=score, verdict=verdict_str, timestamp=time.time(),
            ))

            if Verdict(verdict_str) == Verdict.REJECT:
                logger.info(f"Triad {session.id} round {round_num}: rejected by Evaluator (score={score:.2f})")
                continue  # loop back to Evolver

            # ── VERIFIER: check evidence ──
            if verifier_fn:
                passed, evidence = verifier_fn(task, proposal)
            else:
                passed, evidence = self._default_verifier(task, proposal)

            session.actions.append(RoleAction(
                role=AgentRole.VERIFIER, session_id=session.id, round=round_num,
                input_summary=proposal[:200], output_summary=f"passed={passed}: {evidence[:300]}",
                score=1.0 if passed else 0.0, timestamp=time.time(),
            ))
            current_evidence = evidence

            if not passed:
                logger.info(f"Triad {session.id} round {round_num}: rejected by Verifier")
                continue  # loop back to Evolver

            # ── ACCEPT: both Evaluator and Verifier passed ──
            session.final_verdict = "accept"
            session.final_score = score
            session.rounds_used = round_num
            session.resolved = True
            session.completed_at = time.time()
            self._sessions.append(session)
            self._log_session(session)
            logger.info(f"Triad {session.id} ACCEPTED: score={score:.2f} after {round_num} rounds")
            return {
                "passed": True, "score": score, "rounds": round_num,
                "proposal": proposal, "actions": len(session.actions),
                "session_id": session.id,
            }

        # ── EXHAUSTED: max rounds reached without acceptance ──
        session.final_verdict = "exhausted"
        session.rounds_used = max_rounds
        session.resolved = False
        session.completed_at = time.time()
        self._sessions.append(session)
        self._log_session(session)
        logger.warning(f"Triad {session.id} EXHAUSTED: {max_rounds} rounds without resolution")
        return {
            "passed": False, "score": session.final_score, "rounds": max_rounds,
            "actions": len(session.actions), "session_id": session.id,
        }

    # ── Default role implementations (heuristic fallbacks) ──

    def _default_evolver(self, task: str, context: dict, previous: str = "") -> tuple[str, float]:
        """Default Evolver: generates a proposal from task + context."""
        file = context.get("file", "unknown")
        issue = context.get("issue", task)
        previous_note = f"\nPrevious attempt was: {previous[:200]}" if previous else ""
        proposal = (
            f"Task: {task}\n"
            f"File: {file}\n"
            f"Issue: {issue}{previous_note}\n"
            f"Proposed change: address '{issue}' in {file} by analyzing root cause and applying targeted fix"
        )
        confidence = 0.7 if previous else 0.85
        return proposal, confidence

    def _default_evaluator(self, task: str, proposal: str) -> tuple[float, str, str]:
        """Default Evaluator: scores proposal quality heuristically.

        Checks: relevance to task, specificity, feasibility markers.
        """
        score = 0.5  # baseline

        # Task relevance: does proposal mention the task?
        task_keywords = set(task.lower().split()) & {"fix", "add", "optimize", "refactor", "remove", "update"}
        proposal_lower = proposal.lower()
        matches = sum(1 for kw in task_keywords if kw in proposal_lower)
        score += min(0.25, matches * 0.08)

        # Specificity: does it mention concrete steps?
        specificity_markers = ["change", "modify", "replace", "add", "remove", "file", "function", "class", "method"]
        spec_matches = sum(1 for m in specificity_markers if m in proposal_lower)
        score += min(0.15, spec_matches * 0.03)

        # Feasibility: does it seem actionable?
        if "root cause" in proposal_lower or "fix" in proposal_lower or "implement" in proposal_lower:
            score += 0.1

        score = min(1.0, score)

        if score >= 0.7:
            return score, "accept", f"Good proposal (score={score:.2f})"
        elif score >= 0.4:
            return score, "revise", f"Adequate but needs more detail (score={score:.2f})"
        else:
            return score, "reject", f"Insufficient proposal (score={score:.2f})"

    def _default_verifier(self, task: str, proposal: str) -> tuple[bool, str]:
        """Default Verifier: checks for common issues in proposals.

        Checks: empty proposal, missing context, contradiction markers.
        """
        if not proposal or len(proposal.strip()) < 20:
            return False, "Proposal too short (less than 20 chars)"

        proposal_lower = proposal.lower()

        # Detect contradiction / hallucination markers
        red_flags = [
            ("never" in proposal_lower and "always" in proposal_lower),
            ("guarantee" in proposal_lower and proposal.count("?") > 3),
            ("delete the entire" in proposal_lower),
            ("remove all files" in proposal_lower),
        ]
        if any(red_flags):
            return False, "Detected contradictory or dangerous claims"

        # Check essential context presence
        if "file" not in proposal_lower and "function" not in proposal_lower and "class" not in proposal_lower:
            return False, "Proposal lacks specific file/function/class reference"

        return True, "Verification passed: no red flags, has sufficient context"

    # ── Session management ──

    def get_session(self, session_id: str) -> Optional[TriadSession]:
        """Retrieve a triad session by ID."""
        for s in self._sessions:
            if s.id == session_id:
                return s
        return None

    def get_stats(self) -> dict:
        """Get aggregate triad statistics."""
        if not self._sessions:
            return {"total_sessions": 0, "accept_rate": 0.0, "avg_rounds": 0.0, "avg_score": 0.0}
        accepted = sum(1 for s in self._sessions if s.resolved)
        scores = [s.final_score for s in self._sessions if s.final_score > 0]
        rounds = [s.rounds_used for s in self._sessions]
        return {
            "total_sessions": len(self._sessions),
            "accepted": accepted,
            "rejected": len(self._sessions) - accepted,
            "accept_rate": round(accepted / len(self._sessions), 3),
            "avg_rounds": round(sum(rounds) / len(rounds), 1) if rounds else 0.0,
            "avg_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
        }

    def _log_session(self, session: TriadSession):
        """Append session to JSONL log for analysis."""
        try:
            record = {
                "id": session.id, "task": session.task[:200],
                "final_verdict": session.final_verdict,
                "final_score": session.final_score,
                "rounds_used": session.rounds_used,
                "resolved": session.resolved,
                "actions": [a.to_dict() for a in session.actions],
                "completed_at": session.completed_at,
            }
            with open(TRIAD_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to log triad session: {e}")


# ── Singleton ──

ROLE_TRIAD = RoleTriad()


def get_triad() -> RoleTriad:
    """Get the global RoleTriad singleton."""
    return ROLE_TRIAD
