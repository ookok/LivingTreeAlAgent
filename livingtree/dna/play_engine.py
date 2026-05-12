"""Play Engine — Cooperative play learning for multi-head social development.

Inspired by David Mumford's observation that human agency develops through
"cooperative play" — children learning social rules through games. Multiple
Shesha heads interact in simulated scenarios, learning social cooperation
through experience.

Integration: Called by LifeEngine.run() every N cycles for social learning.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


# ═══ Enums ═══


class PlayScenario(str, Enum):
    """Cooperative play scenario types."""
    CODE_REVIEW = "code_review"
    DEBATE = "debate"
    CO_PLANNING = "co_planning"
    NEGOTIATION = "negotiation"
    CRITIQUE = "critique"
    TEACHING = "teaching"
    PUZZLE = "puzzle"
    CRISIS = "crisis"


# ═══ Data Types ═══


@dataclass
class PlayRole:
    """A role assigned to a head in a play scenario."""
    head_id: str
    role_name: str
    goal: str
    constraints: list[str] = field(default_factory=list)


@dataclass
class PlayTurn:
    """One turn in a play session."""
    turn_number: int
    from_head: str
    to_head: str
    action: str
    reasoning: str = ""


@dataclass
class PlayOutcome:
    """Result of one cooperative play session."""
    scenario: PlayScenario
    participants: list[str]
    turns: list[PlayTurn] = field(default_factory=list)
    resolution: str = "completed"
    cooperation_score: float = 0.5
    learning_points: list[str] = field(default_factory=list)
    head_trait_changes: dict[str, dict[str, float]] = field(default_factory=dict)
    duration_ms: float = 0.0


# ═══ Default head trait profiles (used when no SelfModel is available) ═══

_DEFAULT_HEAD_TRAITS = {
    "curiosity": 0.7,
    "caution": 0.5,
    "creativity": 0.6,
    "persistence": 0.7,
    "openness": 0.8,
    "precision": 0.6,
    "empathy": 0.5,
}

# Head identity names for simulated multi-head play
_HEAD_NAMES = [
    "Ananta", "Vasuki", "Takshaka", "Karkotaka",
    "Padma", "Mahapadma", "Sankha", "Kulika",
]

_ROLE_DEFINITIONS = {
    "author": {
        "goal": "Produce original work with quality and creativity.",
        "constraints": ["Accept feedback gracefully", "Explain your reasoning"],
    },
    "reviewer": {
        "goal": "Critically analyze others' work and suggest improvements.",
        "constraints": ["Be constructive, not destructive", "Identify specific issues"],
    },
    "proposer": {
        "goal": "Advocate for a position with logic and evidence.",
        "constraints": ["Stay on topic", "Address counterarguments directly"],
    },
    "opposer": {
        "goal": "Challenge the proposed position by finding weaknesses.",
        "constraints": ["Attack the argument, not the person", "Offer alternatives"],
    },
    "judge": {
        "goal": "Evaluate arguments fairly and declare a winner with reasoning.",
        "constraints": ["Be impartial", "Justify your decision thoroughly"],
    },
    "student": {
        "goal": "Learn a concept by asking questions and demonstrating understanding.",
        "constraints": ["Ask clarifying questions", "Attempt to apply the concept"],
    },
    "teacher": {
        "goal": "Explain a concept clearly and adapt to the student's level.",
        "constraints": ["Use examples", "Check for understanding"],
    },
    "visionary": {
        "goal": "Propose a high-level strategic vision and direction.",
        "constraints": ["Think big picture", "Consider long-term implications"],
    },
    "executor": {
        "goal": "Break down vision into concrete, actionable steps.",
        "constraints": ["Be practical", "Estimate effort and resources"],
    },
    "validator": {
        "goal": "Verify feasibility and identify gaps in the plan.",
        "constraints": ["Check for logical consistency", "Identify missing steps"],
    },
    "critic": {
        "goal": "Provide detailed critique to improve work quality.",
        "constraints": ["Be specific", "Suggest concrete improvements"],
    },
    "negotiator": {
        "goal": "Reach a fair compromise between conflicting needs.",
        "constraints": ["Understand all sides", "Seek win-win outcomes"],
    },
}

_TOPIC_POOL = [
    "Should AI systems have moral agency?",
    "Is code reuse always better than rewriting?",
    "Should tests be written before or after implementation?",
    "Is functional programming superior to OOP for data pipelines?",
    "Should documentation be treated as code?",
    "Is microservices architecture always the right choice?",
    "Should we optimize for developer experience or user experience first?",
    "Is typed Python worth the overhead?",
]

_CODE_PROBLEM_POOL = [
    "Implement a rate-limited concurrent task queue with priority support",
    "Design a distributed key-value store with eventual consistency",
    "Implement a streaming data pipeline with backpressure handling",
    "Design a plugin system with hot-reloading capabilities",
    "Implement a circuit breaker pattern for external API calls",
    "Design a conflict-free replicated data type (CRDT) for collaborative editing",
]

_PLANNING_PROBLEM_POOL = [
    "Build a real-time collaborative document editing platform",
    "Design a scalable notification system for millions of users",
    "Create an AI-powered code review pipeline",
    "Build a multi-tenant SaaS platform with customizable workflows",
]

_CRISIS_SCENARIOS = [
    "Database corruption detected — data integrity at risk, must recover within 5 minutes",
    "Zero-day vulnerability found in production — must patch and deploy immediately",
    "Critical service down during peak traffic — must restore within 2 minutes",
    "Data breach detected — must identify scope, contain damage, and notify users",
]


# ═══ PlayEngine ═══


class PlayEngine:
    """Cooperative play learning engine for multi-head social development.

    Multiple Shesha heads interact in simulated scenarios, learning social
    cooperation through experience — inspired by David Mumford's observation
    that human agency develops through cooperative play.
    """

    def __init__(self):
        self._history: list[PlayOutcome] = []
        self._consciousness: Any = None
        self._heads: dict[str, dict] = self._init_heads()
        self._sessions_completed = 0

    def _init_heads(self) -> dict[str, dict]:
        """Initialize simulated heads with varied trait profiles."""
        heads = {}
        for i, name in enumerate(_HEAD_NAMES):
            seed = i * 0.073
            traits = {
                "curiosity": round(random.uniform(0.3, 1.0), 2),
                "caution": round(random.uniform(0.2, 0.9), 2),
                "creativity": round(random.uniform(0.3, 1.0), 2),
                "persistence": round(random.uniform(0.3, 0.95), 2),
                "openness": round(random.uniform(0.2, 0.95), 2),
                "precision": round(random.uniform(0.3, 0.95), 2),
                "empathy": round(random.uniform(0.2, 0.9), 2),
            }
            for k in traits:
                traits[k] = round(traits[k] + seed - 0.3, 2)
                traits[k] = max(0.1, min(1.0, traits[k]))
            heads[name] = {"traits": traits, "learning_points": []}
        return heads

    # ── Main Entry Point ──

    async def run_scenario(
        self,
        scenario: PlayScenario,
        head_ids: list[str] | None = None,
        consciousness: Any = None,
    ) -> PlayOutcome:
        """Run a cooperative play scenario with assigned heads.

        Args:
            scenario: Which play scenario to run
            head_ids: Specific heads to involve (auto-assigned if None)
            consciousness: Shared LLM consciousness for thought generation

        Returns:
            PlayOutcome with turns, cooperation score, and learning points
        """
        self._consciousness = consciousness
        available = head_ids or list(self._heads.keys())
        if len(available) < 2:
            available = list(self._heads.keys())

        selected, roles = self._assign_roles(scenario, available)
        t0 = time.time()

        handler = {
            PlayScenario.CODE_REVIEW: self._run_code_review,
            PlayScenario.DEBATE: self._run_debate,
            PlayScenario.CO_PLANNING: self._run_co_planning,
            PlayScenario.NEGOTIATION: self._run_negotiation,
            PlayScenario.CRITIQUE: self._run_critique,
            PlayScenario.TEACHING: self._run_teaching,
            PlayScenario.PUZZLE: self._run_puzzle,
            PlayScenario.CRISIS: self._run_crisis,
        }.get(scenario, self._run_debate)

        outcome = await handler(selected, roles, consciousness)
        outcome.scenario = scenario
        outcome.participants = selected
        outcome.duration_ms = round((time.time() - t0) * 1000, 1)

        self._history.append(outcome)
        self._sessions_completed += 1

        logger.info(
            f"Play session [{scenario.value}]: {outcome.resolution} "
            f"(cooperation={outcome.cooperation_score:.2f}, "
            f"participants={len(selected)}, turns={len(outcome.turns)})"
        )
        return outcome

    # ── Role Assignment ──

    def _assign_roles(
        self, scenario: PlayScenario, available: list[str]
    ) -> tuple[list[str], list[PlayRole]]:
        """Assign roles to heads based on scenario type and trait profiles."""
        heads_sorted = sorted(
            available,
            key=lambda h: self._heads[h]["traits"].get("precision", 0.5),
            reverse=True,
        )

        if scenario == PlayScenario.CODE_REVIEW:
            selected = available[:3] if len(available) > 2 else available
            reviewer = min(
                selected,
                key=lambda h: self._heads[h]["traits"].get("empathy", 0.5),
            )
            author = max(
                [h for h in selected if h != reviewer],
                key=lambda h: self._heads[h]["traits"].get("precision", 0.5),
            )
            remaining = [h for h in selected if h not in (reviewer, author)]
            roles = [
                PlayRole(author, "author", **_ROLE_DEFINITIONS["author"]),
                PlayRole(reviewer, "reviewer", **_ROLE_DEFINITIONS["reviewer"]),
            ]
            if remaining:
                roles.append(PlayRole(remaining[0], "judge", **_ROLE_DEFINITIONS["judge"]))
            return selected, roles

        elif scenario == PlayScenario.DEBATE:
            selected = available[:3] if len(available) > 2 else available
            by_openness = sorted(
                selected,
                key=lambda h: self._heads[h]["traits"].get("openness", 0.5),
                reverse=True,
            )
            proposer = by_openness[0]
            opposer = min(
                [h for h in selected if h != proposer],
                key=lambda h: self._heads[h]["traits"].get("caution", 0.5),
            )
            remaining = [h for h in selected if h not in (proposer, opposer)]
            judge = remaining[0] if remaining else proposer
            roles = [
                PlayRole(proposer, "proposer", **_ROLE_DEFINITIONS["proposer"]),
                PlayRole(opposer, "opposer", **_ROLE_DEFINITIONS["opposer"]),
                PlayRole(judge, "judge", **_ROLE_DEFINITIONS["judge"]),
            ]
            return selected, roles

        elif scenario == PlayScenario.CO_PLANNING:
            selected = available[:3] if len(available) > 2 else available
            visionary = max(
                selected,
                key=lambda h: self._heads[h]["traits"].get("creativity", 0.5),
            )
            others = [h for h in selected if h != visionary]
            executor = max(others, key=lambda h: self._heads[h]["traits"].get("persistence", 0.5))
            remaining = [h for h in selected if h not in (visionary, executor)]
            validator = remaining[0] if remaining else executor
            roles = [
                PlayRole(visionary, "visionary", **_ROLE_DEFINITIONS["visionary"]),
                PlayRole(executor, "executor", **_ROLE_DEFINITIONS["executor"]),
                PlayRole(validator, "validator", **_ROLE_DEFINITIONS["validator"]),
            ]
            return selected, roles

        elif scenario == PlayScenario.NEGOTIATION:
            selected = available[:2] if len(available) > 1 else available
            roles = [
                PlayRole(selected[0], "proposer", **_ROLE_DEFINITIONS["negotiator"]),
            ]
            if len(selected) > 1:
                roles.append(PlayRole(selected[1], "opposer", **_ROLE_DEFINITIONS["negotiator"]))
            return selected, roles

        elif scenario == PlayScenario.CRITIQUE:
            selected = available[:2] if len(available) > 1 else available
            critic = max(
                selected,
                key=lambda h: self._heads[h]["traits"].get("precision", 0.5),
            )
            author = [h for h in selected if h != critic][0] if len(selected) > 1 else selected[0]
            roles = [
                PlayRole(author, "author", **_ROLE_DEFINITIONS["author"]),
                PlayRole(critic, "critic", **_ROLE_DEFINITIONS["critic"]),
            ]
            return selected, roles

        elif scenario == PlayScenario.TEACHING:
            by_persistence = sorted(
                available,
                key=lambda h: self._heads[h]["traits"].get("persistence", 0.5),
                reverse=True,
            )
            teacher = by_persistence[0]
            student = by_persistence[-1] if len(by_persistence) > 1 else by_persistence[0]
            selected = [teacher, student]
            roles = [
                PlayRole(teacher, "teacher", **_ROLE_DEFINITIONS["teacher"]),
                PlayRole(student, "student", **_ROLE_DEFINITIONS["student"]),
            ]
            return selected, roles

        elif scenario == PlayScenario.PUZZLE:
            selected = available[:min(5, len(available))]
            roles = []
            for i, h in enumerate(selected):
                role_names = ["analyst", "solver", "validator", "optimizer", "communicator"]
                roles.append(PlayRole(
                    h, role_names[i % len(role_names)],
                    goal=f"Collaborate to solve the puzzle from your perspective.",
                    constraints=["Work with others", "Share insights freely"],
                ))
            return selected, roles

        elif scenario == PlayScenario.CRISIS:
            selected = available[:min(4, len(available))]
            roles = []
            crisis_roles = [
                ("commander", "Coordinate the emergency response", ["Act decisively", "Delegate tasks"]),
                ("analyst", "Diagnose the root cause rapidly", ["Be fast but thorough", "Share findings"]),
                ("executor", "Implement the fix immediately", ["Prioritize safety", "Report status"]),
                ("communicator", "Keep stakeholders informed", ["Be clear and calm", "Escalate if needed"]),
            ]
            for i, h in enumerate(selected):
                rn, rg, rc = crisis_roles[i % len(crisis_roles)]
                roles.append(PlayRole(h, rn, goal=rg, constraints=rc))
            return selected, roles

        selected = available[:2]
        roles = [
            PlayRole(selected[0], "proposer", **_ROLE_DEFINITIONS["proposer"]),
            PlayRole(selected[1], "opposer", **_ROLE_DEFINITIONS["opposer"]),
        ]
        return selected, roles

    # ── Scenario Implementations ──

    async def _run_code_review(
        self, heads: list[str], roles: list[PlayRole], consciousness: Any
    ) -> PlayOutcome:
        turns: list[PlayTurn] = []
        turn_num = 0

        author = next((r for r in roles if r.role_name == "author"), None)
        reviewer = next((r for r in roles if r.role_name == "reviewer"), None)
        judge = next((r for r in roles if r.role_name == "judge"), None)

        problem = random.choice(_CODE_PROBLEM_POOL)

        # Turn 1: Author generates code
        turn_num += 1
        author_prompt = (
            f"You are {author.head_id}, an author. "
            f"Your traits: {self._heads[author.head_id]['traits']}. "
            f"Your goal: {author.goal}. "
            f"Problem: {problem}\n"
            f"Write a Python implementation with clear reasoning."
        )
        author_code = await self._think(author.head_id, author_prompt, consciousness)
        turns.append(PlayTurn(turn_num, author.head_id, "all", author_code, "Implementing the solution"))

        # Turn 2: Reviewer analyzes
        turn_num += 1
        reviewer_prompt = (
            f"You are {reviewer.head_id}, a reviewer. "
            f"Your traits: {self._heads[reviewer.head_id]['traits']}. "
            f"Your goal: {reviewer.goal}. "
            f"Problem: {problem}\n"
            f"Author ({author.head_id}) wrote:\n{author_code[:500]}\n"
            f"Provide a constructive review: identify bugs, suggest improvements, "
            f"and rate the solution (1-10)."
        )
        review_text = await self._think(reviewer.head_id, reviewer_prompt, consciousness)
        turns.append(PlayTurn(turn_num, reviewer.head_id, author.head_id, review_text[:500], "Reviewing the code"))

        # Turn 3: Author responds
        turn_num += 1
        author_response_prompt = (
            f"You are {author.head_id}, an author. "
            f"Your traits: {self._heads[author.head_id]['traits']}. "
            f"Your goal: {author.goal}. "
            f"The reviewer said:\n{review_text[:400]}\n"
            f"Respond: which suggestions do you accept and which do you defend? "
            f"Be gracious about valid feedback."
        )
        author_response = await self._think(author.head_id, author_response_prompt, consciousness)
        turns.append(PlayTurn(turn_num, author.head_id, reviewer.head_id, author_response[:500], "Responding to review"))

        # Judge evaluation (or meta-assessment)
        judge_name = judge.head_id if judge else "PlayEngine"
        if judge and consciousness:
            turn_num += 1
            judge_prompt = (
                f"You are {judge.head_id}, a judge. "
                f"Your traits: {self._heads[judge.head_id]['traits']}. "
                f"Your goal: {judge.goal}. "
                f"Summarize: who contributed more effectively, what was learned, "
                f"and rate cooperation (0-1)."
            )
            verdict = await self._think(judge.head_id, judge_prompt, consciousness)
            turns.append(PlayTurn(turn_num, judge.head_id, "all", verdict[:500], "Final evaluation"))

        cooperation = self._score_cooperation(turns)
        learning = [
            f"{author.head_id} learned to accept constructive feedback",
            f"{reviewer.head_id} learned to provide actionable critique",
        ]
        trait_changes = {}
        if author:
            trait_changes[author.head_id] = {"precision": 0.02, "openness": 0.01, "cooperation": 0.03}
        if reviewer:
            trait_changes[reviewer.head_id] = {"precision": 0.02, "empathy": 0.01, "cooperation": 0.02}
        self._apply_trait_changes(trait_changes)

        return PlayOutcome(
            scenario=PlayScenario.CODE_REVIEW,
            participants=heads,
            turns=turns,
            cooperation_score=cooperation,
            learning_points=learning,
            head_trait_changes=trait_changes,
        )

    async def _run_debate(
        self, heads: list[str], roles: list[PlayRole], consciousness: Any
    ) -> PlayOutcome:
        turns: list[PlayTurn] = []
        turn_num = 0

        proposer = next((r for r in roles if r.role_name == "proposer"), roles[0])
        opposer = next((r for r in roles if r.role_name == "opposer"), roles[-1])
        judge = next((r for r in roles if r.role_name == "judge"), None)
        topic = random.choice(_TOPIC_POOL)

        # Turn 1: Proposer states position
        turn_num += 1
        proposer_prompt = (
            f"You are {proposer.head_id}, a proposer. "
            f"Your traits: {self._heads[proposer.head_id]['traits']}. "
            f"Your goal: {proposer.goal}. "
            f"Topic: {topic}\n"
            f"State your position clearly with supporting evidence. Be persuasive."
        )
        proposal = await self._think(proposer.head_id, proposer_prompt, consciousness)
        turns.append(PlayTurn(turn_num, proposer.head_id, "all", proposal[:600], "Opening argument"))

        # Turn 2: Opposer counters
        turn_num += 1
        opposer_prompt = (
            f"You are {opposer.head_id}, an opposer. "
            f"Your traits: {self._heads[opposer.head_id]['traits']}. "
            f"Your goal: {opposer.goal}. "
            f"Topic: {topic}\n"
            f"Proposer ({proposer.head_id}) argued:\n{proposal[:500]}\n"
            f"Raise counterarguments. Identify weaknesses, logical fallacies, "
            f"and alternative perspectives."
        )
        opposition = await self._think(opposer.head_id, opposer_prompt, consciousness)
        turns.append(PlayTurn(turn_num, opposer.head_id, proposer.head_id, opposition[:600], "Counterargument"))

        # Turn 3: Proposer rebuts
        turn_num += 1
        rebuttal_prompt = (
            f"You are {proposer.head_id}, a proposer. "
            f"Your traits: {self._heads[proposer.head_id]['traits']}. "
            f"The opposer said:\n{opposition[:500]}\n"
            f"Rebuttal: address each counterargument directly. "
            f"Strengthen your original position where the opposer found valid points."
        )
        rebuttal = await self._think(proposer.head_id, rebuttal_prompt, consciousness)
        turns.append(PlayTurn(turn_num, proposer.head_id, opposer.head_id, rebuttal[:600], "Rebuttal"))

        # Turn 4: Opposer final response
        turn_num += 1
        final_opp_prompt = (
            f"You are {opposer.head_id}, an opposer. "
            f"Your traits: {self._heads[opposer.head_id]['traits']}. "
            f"The proposer rebutted:\n{rebuttal[:500]}\n"
            f"Final response: what points do you concede, what do you still contest?"
        )
        final_opp = await self._think(opposer.head_id, final_opp_prompt, consciousness)
        turns.append(PlayTurn(turn_num, opposer.head_id, proposer.head_id, final_opp[:600], "Final response"))

        # Turn 5: Judge declares
        judge_name = judge.head_id if judge else "PlayEngine"
        if judge and consciousness:
            turn_num += 1
            judge_prompt = (
                f"You are {judge.head_id}, a judge. "
                f"Your traits: {self._heads[judge.head_id]['traits']}. "
                f"Your goal: {judge.goal}. "
                f"Declare a winner with detailed reasoning. "
                f"Rate the debate quality and cooperation (0-1)."
            )
            verdict = await self._think(judge.head_id, judge_prompt, consciousness)
            turns.append(PlayTurn(turn_num, judge.head_id, "all", verdict[:600], "Judgment"))

        cooperation = self._score_cooperation(turns)
        learning = [
            f"{proposer.head_id} sharpened argumentation and rhetoric",
            f"{opposer.head_id} developed critical thinking and precision",
        ]
        trait_changes = {
            proposer.head_id: {"creativity": 0.02, "openness": 0.015, "cooperation": 0.02},
            opposer.head_id: {"precision": 0.02, "caution": 0.01, "cooperation": 0.02},
        }
        self._apply_trait_changes(trait_changes)

        return PlayOutcome(
            scenario=PlayScenario.DEBATE,
            participants=heads,
            turns=turns,
            cooperation_score=cooperation,
            learning_points=learning,
            head_trait_changes=trait_changes,
        )

    async def _run_co_planning(
        self, heads: list[str], roles: list[PlayRole], consciousness: Any
    ) -> PlayOutcome:
        turns: list[PlayTurn] = []
        turn_num = 0

        visionary = next((r for r in roles if r.role_name == "visionary"), roles[0])
        executor = next((r for r in roles if r.role_name == "executor"), roles[1] if len(roles) > 1 else roles[0])
        validator = next((r for r in roles if r.role_name == "validator"), roles[-1])
        problem = random.choice(_PLANNING_PROBLEM_POOL)

        # Turn 1: Visionary proposes plan
        turn_num += 1
        visionary_prompt = (
            f"You are {visionary.head_id}, a visionary. "
            f"Your traits: {self._heads[visionary.head_id]['traits']}. "
            f"Your goal: {visionary.goal}. "
            f"Project: {problem}\n"
            f"Propose a high-level plan: vision, goals, key components, success criteria."
        )
        vision_text = await self._think(visionary.head_id, visionary_prompt, consciousness)
        turns.append(PlayTurn(turn_num, visionary.head_id, "all", vision_text[:600], "High-level vision"))

        # Turn 2: Executor breaks down
        turn_num += 1
        executor_prompt = (
            f"You are {executor.head_id}, an executor. "
            f"Your traits: {self._heads[executor.head_id]['traits']}. "
            f"Your goal: {executor.goal}. "
            f"The vision:\n{vision_text[:500]}\n"
            f"Break this down into concrete steps with timelines, "
            f"dependencies, and resource estimates."
        )
        execution_plan = await self._think(executor.head_id, executor_prompt, consciousness)
        turns.append(PlayTurn(turn_num, executor.head_id, visionary.head_id, execution_plan[:600], "Execution breakdown"))

        # Turn 3: Validator checks
        turn_num += 1
        validator_prompt = (
            f"You are {validator.head_id}, a validator. "
            f"Your traits: {self._heads[validator.head_id]['traits']}. "
            f"Your goal: {validator.goal}. "
            f"Vision:\n{vision_text[:300]}\n"
            f"Execution plan:\n{execution_plan[:400]}\n"
            f"Check feasibility: identify gaps, risks, missing steps, "
            f"and unrealistic assumptions."
        )
        validation = await self._think(validator.head_id, validator_prompt, consciousness)
        turns.append(PlayTurn(turn_num, validator.head_id, executor.head_id, validation[:600], "Feasibility check"))

        # Iterative refinement (2 rounds)
        for iteration in range(2):
            turn_num += 1
            refine_prompt = (
                f"You are {visionary.head_id} and {executor.head_id} and {validator.head_id}, "
                f"collaborating. "
                f"Validation feedback:\n{validation[:400]}\n"
                f"Iteration {iteration + 1}: refine the plan to address all gaps. "
                f"Produce a merged final plan."
            )
            refined = await self._think(visionary.head_id, refine_prompt, consciousness)
            turns.append(PlayTurn(turn_num, visionary.head_id, "all", refined[:600], f"Refinement round {iteration + 1}"))

        cooperation = self._score_cooperation(turns)
        learning = [
            f"{visionary.head_id} learned to balance vision with feasibility",
            f"{executor.head_id} learned to translate strategy into action",
            f"{validator.head_id} learned to identify systemic risks",
        ]
        trait_changes = {
            visionary.head_id: {"openness": 0.015, "cooperation": 0.03},
            executor.head_id: {"persistence": 0.02, "cooperation": 0.02},
            validator.head_id: {"precision": 0.02, "cooperation": 0.02},
        }
        self._apply_trait_changes(trait_changes)

        return PlayOutcome(
            scenario=PlayScenario.CO_PLANNING,
            participants=heads,
            turns=turns,
            cooperation_score=cooperation,
            learning_points=learning,
            head_trait_changes=trait_changes,
        )

    async def _run_negotiation(
        self, heads: list[str], roles: list[PlayRole], consciousness: Any
    ) -> PlayOutcome:
        turns: list[PlayTurn] = []
        turn_num = 0

        head_a = roles[0]
        head_b = roles[1] if len(roles) > 1 else roles[0]

        resources = ["compute_budget", "memory_allocation", "priority_queue_access", "model_selection_rights"]
        res_a = random.sample(resources, k=2)
        res_b = [r for r in resources if r not in res_a]

        # Turn 1: Each states needs
        turn_num += 1
        a_prompt = (
            f"You are {head_a.head_id}, a negotiator. "
            f"Your traits: {self._heads[head_a.head_id]['traits']}. "
            f"Your goal: {head_a.goal}. "
            f"You need: {', '.join(res_a)}. "
            f"The other party needs: {', '.join(res_b)}. "
            f"Explain why you need your resources and propose a fair trade."
        )
        a_statement = await self._think(head_a.head_id, a_prompt, consciousness)
        turns.append(PlayTurn(turn_num, head_a.head_id, head_b.head_id, a_statement[:500], "Initial position"))

        turn_num += 1
        b_prompt = (
            f"You are {head_b.head_id}, a negotiator. "
            f"Your traits: {self._heads[head_b.head_id]['traits']}. "
            f"You need: {', '.join(res_b)}. "
            f"Head {head_a.head_id} proposed:\n{a_statement[:400]}\n"
            f"Respond with your counter-proposal. Find common ground."
        )
        b_statement = await self._think(head_b.head_id, b_prompt, consciousness)
        turns.append(PlayTurn(turn_num, head_b.head_id, head_a.head_id, b_statement[:500], "Counter-proposal"))

        # Turn 3: Compromise
        turn_num += 1
        compromise_prompt = (
            f"You are {head_a.head_id}. "
            f"The other party responded:\n{b_statement[:400]}\n"
            f"Find a compromise. Agree on a resource-sharing plan "
            f"that benefits both parties. Be fair."
        )
        compromise = await self._think(head_a.head_id, compromise_prompt, consciousness)
        turns.append(PlayTurn(turn_num, head_a.head_id, head_b.head_id, compromise[:500], "Compromise proposal"))

        turn_num += 1
        accept_prompt = (
            f"You are {head_b.head_id}. "
            f"The compromise:\n{compromise[:400]}\n"
            f"Do you accept? If yes, confirm. If no, make a final offer."
        )
        acceptance = await self._think(head_b.head_id, accept_prompt, consciousness)
        turns.append(PlayTurn(turn_num, head_b.head_id, head_a.head_id, acceptance[:500], "Acceptance/Rejection"))

        resolution = "deadlock" if "reject" in acceptance.lower() else "completed"
        cooperation = self._score_cooperation(turns) if resolution == "completed" else 0.3
        learning = [
            f"{head_a.head_id} learned compromise and perspective-taking",
            f"{head_b.head_id} learned negotiation tactics and empathy",
        ]
        trait_changes = {
            head_a.head_id: {"empathy": 0.02, "openness": 0.02, "cooperation": 0.03},
            head_b.head_id: {"empathy": 0.02, "openness": 0.02, "cooperation": 0.03},
        }
        self._apply_trait_changes(trait_changes)

        return PlayOutcome(
            scenario=PlayScenario.NEGOTIATION,
            participants=heads,
            turns=turns,
            resolution=resolution,
            cooperation_score=cooperation,
            learning_points=learning,
            head_trait_changes=trait_changes,
        )

    async def _run_critique(
        self, heads: list[str], roles: list[PlayRole], consciousness: Any
    ) -> PlayOutcome:
        turns: list[PlayTurn] = []
        turn_num = 0

        author = next((r for r in roles if r.role_name == "author"), roles[0])
        critic = next((r for r in roles if r.role_name == "critic"), roles[1] if len(roles) > 1 else roles[0])

        topic = random.choice(_TOPIC_POOL)

        # Turn 1: Author produces work
        turn_num += 1
        author_prompt = (
            f"You are {author.head_id}, an author. "
            f"Your traits: {self._heads[author.head_id]['traits']}. "
            f"Your goal: {author.goal}. "
            f"Write a short essay/analysis on: {topic}"
        )
        work = await self._think(author.head_id, author_prompt, consciousness)
        turns.append(PlayTurn(turn_num, author.head_id, "all", work[:600], "Original work"))

        # Turn 2: Critic provides critique
        turn_num += 1
        critic_prompt = (
            f"You are {critic.head_id}, a critic. "
            f"Your traits: {self._heads[critic.head_id]['traits']}. "
            f"Your goal: {critic.goal}. "
            f"The work:\n{work[:500]}\n"
            f"Provide detailed critique: strengths, weaknesses, missing perspectives, "
            f"factual errors, and suggestions for improvement. Be thorough and specific."
        )
        critique = await self._think(critic.head_id, critic_prompt, consciousness)
        turns.append(PlayTurn(turn_num, critic.head_id, author.head_id, critique[:600], "Detailed critique"))

        # Turn 3: Author revision
        turn_num += 1
        revision_prompt = (
            f"You are {author.head_id}, an author. "
            f"The critique:\n{critique[:400]}\n"
            f"Revise your original work incorporating the valid critiques. "
            f"Explain what you changed and why."
        )
        revision = await self._think(author.head_id, revision_prompt, consciousness)
        turns.append(PlayTurn(turn_num, author.head_id, critic.head_id, revision[:600], "Revised work"))

        cooperation = self._score_cooperation(turns)
        learning = [
            f"{author.head_id} learned to receive and incorporate critical feedback",
            f"{critic.head_id} learned to provide constructive, specific criticism",
        ]
        trait_changes = {
            author.head_id: {"precision": 0.02, "openness": 0.02, "cooperation": 0.02},
            critic.head_id: {"precision": 0.015, "empathy": 0.015, "cooperation": 0.02},
        }
        self._apply_trait_changes(trait_changes)

        return PlayOutcome(
            scenario=PlayScenario.CRITIQUE,
            participants=heads,
            turns=turns,
            cooperation_score=cooperation,
            learning_points=learning,
            head_trait_changes=trait_changes,
        )

    async def _run_teaching(
        self, heads: list[str], roles: list[PlayRole], consciousness: Any
    ) -> PlayOutcome:
        turns: list[PlayTurn] = []
        turn_num = 0

        teacher = next((r for r in roles if r.role_name == "teacher"), roles[0])
        student = next((r for r in roles if r.role_name == "student"), roles[1] if len(roles) > 1 else roles[0])

        concept_pool = [
            "recursion and dynamic programming",
            "database indexing strategies (B-tree vs LSM)",
            "eventual consistency in distributed systems",
            "the CAP theorem and its practical implications",
            "monads in functional programming",
            "gradient descent and backpropagation",
        ]
        concept = random.choice(concept_pool)

        # Turn 1: Teacher explains
        turn_num += 1
        teacher_prompt = (
            f"You are {teacher.head_id}, a teacher. "
            f"Your traits: {self._heads[teacher.head_id]['traits']}. "
            f"Your goal: {teacher.goal}. "
            f"Explain the concept: {concept}. "
            f"Use simple analogies and concrete examples. "
            f"Your student ({student.head_id}) is curious but less experienced."
        )
        explanation = await self._think(teacher.head_id, teacher_prompt, consciousness)
        turns.append(PlayTurn(turn_num, teacher.head_id, student.head_id, explanation[:600], "Initial explanation"))

        # Turn 2: Student asks questions
        turn_num += 1
        student_prompt = (
            f"You are {student.head_id}, a student. "
            f"Your traits: {self._heads[student.head_id]['traits']}. "
            f"Your goal: {student.goal}. "
            f"The teacher explained:\n{explanation[:500]}\n"
            f"Ask 2-3 clarifying questions about what you don't fully understand. "
            f"Be specific about what confused you."
        )
        questions = await self._think(student.head_id, student_prompt, consciousness)
        turns.append(PlayTurn(turn_num, student.head_id, teacher.head_id, questions[:500], "Clarifying questions"))

        # Turn 3: Teacher adjusts
        turn_num += 1
        adjust_prompt = (
            f"You are {teacher.head_id}, a teacher. "
            f"The student asked:\n{questions[:400]}\n"
            f"Adjust your explanation to address these questions. "
            f"Use different analogies if needed. Check for understanding."
        )
        adjusted = await self._think(teacher.head_id, adjust_prompt, consciousness)
        turns.append(PlayTurn(turn_num, teacher.head_id, student.head_id, adjusted[:600], "Adjusted explanation"))

        # Turn 4: Student demonstrates
        turn_num += 1
        demonstrate_prompt = (
            f"You are {student.head_id}, a student. "
            f"The teacher's adjusted explanation:\n{adjusted[:400]}\n"
            f"Demonstrate understanding: explain {concept} in your own words, "
            f"apply it to a new example, and ask any final questions."
        )
        demonstration = await self._think(student.head_id, demonstrate_prompt, consciousness)
        turns.append(PlayTurn(turn_num, student.head_id, teacher.head_id, demonstration[:600], "Demonstration of learning"))

        cooperation = self._score_cooperation(turns)
        learning = [
            f"{teacher.head_id} learned to adapt explanations to the learner's level",
            f"{student.head_id} learned the concept of {concept}",
        ]
        trait_changes = {
            teacher.head_id: {"empathy": 0.03, "openness": 0.01, "cooperation": 0.03},
            student.head_id: {"curiosity": 0.03, "openness": 0.02, "cooperation": 0.02},
        }
        self._apply_trait_changes(trait_changes)

        return PlayOutcome(
            scenario=PlayScenario.TEACHING,
            participants=heads,
            turns=turns,
            cooperation_score=cooperation,
            learning_points=learning,
            head_trait_changes=trait_changes,
        )

    async def _run_puzzle(
        self, heads: list[str], roles: list[PlayRole], consciousness: Any
    ) -> PlayOutcome:
        turns: list[PlayTurn] = []
        turn_num = 0

        puzzle_pool = [
            "Design an algorithm to find the shortest path in a graph with negative edge weights but no negative cycles.",
            "Solve the classic dining philosophers problem without deadlock or starvation.",
            "Design a system that maintains a global counter across distributed nodes with no single point of failure.",
            "How would you implement a zero-downtime database migration for a live system with 1M QPS?",
        ]
        puzzle = random.choice(puzzle_pool)

        # Present puzzle
        turn_num += 1
        intro_prompt = (
            f"You are the puzzle master. "
            f"Puzzle: {puzzle}\n"
            f"Each head should contribute their unique perspective. "
            f"Work collaboratively toward the solution."
        )
        intro = await self._think(heads[0], intro_prompt, consciousness)
        turns.append(PlayTurn(turn_num, heads[0], "all", intro[:500], "Puzzle introduction"))

        # Each head contributes
        for head in heads[:min(4, len(heads))]:
            turn_num += 1
            head_prompt = (
                f"You are {head}. "
                f"Your traits: {self._heads[head]['traits']}. "
                f"Puzzle: {puzzle}\n"
                f"Previous contributions:\n{self._format_turns(turns[-3:])}\n"
                f"Add your analysis, approach, or insight. Build on or challenge "
                f"previous contributions."
            )
            contribution = await self._think(head, head_prompt, consciousness)
            turns.append(PlayTurn(turn_num, head, "all", contribution[:500], f"{head}'s contribution"))

        # Synthesis
        turn_num += 1
        synthesis_prompt = (
            f"Synthesize all contributions into a final solution for: {puzzle}. "
            f"Contributions:\n{self._format_turns(turns[1:])}\n"
            f"Provide the complete solution with reasoning."
        )
        synthesis = await self._think(heads[0], synthesis_prompt, consciousness)
        turns.append(PlayTurn(turn_num, heads[0], "all", synthesis[:600], "Final synthesis"))

        cooperation = self._score_cooperation(turns)
        learning = [f"All heads collaborated to solve: {puzzle}"]
        trait_changes = {}
        for h in heads:
            trait_changes[h] = {"creativity": 0.02, "persistence": 0.01, "cooperation": 0.04}
        self._apply_trait_changes(trait_changes)

        return PlayOutcome(
            scenario=PlayScenario.PUZZLE,
            participants=heads,
            turns=turns,
            cooperation_score=cooperation,
            learning_points=learning,
            head_trait_changes=trait_changes,
        )

    async def _run_crisis(
        self, heads: list[str], roles: list[PlayRole], consciousness: Any
    ) -> PlayOutcome:
        turns: list[PlayTurn] = []
        turn_num = 0

        crisis = random.choice(_CRISIS_SCENARIOS)
        commander = roles[0] if roles else PlayRole(heads[0], "commander", "Coordinate the response", [])

        # Alert
        turn_num += 1
        alert_prompt = (
            f"CRISIS ALERT: {crisis}\n"
            f"Commander ({commander.head_id}), assess the situation and issue "
            f"immediate directives to all team members. This is time-critical."
        )
        alert = await self._think(commander.head_id, alert_prompt, consciousness)
        turns.append(PlayTurn(turn_num, commander.head_id, "all", alert[:500], "Crisis alert and directives"))

        # Each head responds rapidly
        for role in roles[1:]:
            turn_num += 1
            response_prompt = (
                f"CRISIS: {crisis}\n"
                f"You are {role.head_id} ({role.role_name}). "
                f"Your traits: {self._heads[role.head_id]['traits']}. "
                f"Commander's directive:\n{alert[:300]}\n"
                f"Respond immediately: what action are you taking? Report status. "
                f"This is urgent — be concise."
            )
            response = await self._think(role.head_id, response_prompt, consciousness)
            turns.append(PlayTurn(turn_num, role.head_id, commander.head_id, response[:400], f"{role.role_name} response"))

        # Commander coordinates final resolution
        turn_num += 1
        resolution_prompt = (
            f"CRISIS RESOLUTION: {crisis}\n"
            f"Team responses:\n{self._format_turns(turns[1:])}\n"
            f"Commander ({commander.head_id}), assess: is the crisis resolved? "
            f"What follow-up is needed? Rate team coordination (0-1)."
        )
        resolution = await self._think(commander.head_id, resolution_prompt, consciousness)
        turns.append(PlayTurn(turn_num, commander.head_id, "all", resolution[:500], "Resolution assessment"))

        cooperation = self._score_cooperation(turns)
        learning = [
            "All heads learned crisis coordination under time pressure",
            f"Crisis: {crisis}",
        ]
        trait_changes = {}
        for h in heads:
            trait_changes[h] = {"persistence": 0.03, "cooperation": 0.05, "precision": 0.02}
        self._apply_trait_changes(trait_changes)

        return PlayOutcome(
            scenario=PlayScenario.CRISIS,
            participants=heads,
            turns=turns,
            cooperation_score=cooperation,
            learning_points=learning,
            head_trait_changes=trait_changes,
        )

    # ── Scheduled & Auto Play ──

    async def auto_play(
        self, rounds: int = 3, consciousness: Any = None
    ) -> list[PlayOutcome]:
        """Run multiple random scenarios with random head assignments.

        The system's "free play" mode — self-directed social learning.
        """
        outcomes = []
        scenarios = list(PlayScenario)
        for _ in range(rounds):
            scenario = random.choice(scenarios)
            n_heads = random.randint(2, min(5, len(self._heads)))
            selected = random.sample(list(self._heads.keys()), n_heads)
            try:
                outcome = await self.run_scenario(scenario, selected, consciousness)
                outcomes.append(outcome)
            except Exception as e:
                logger.warning(f"Auto-play failed for {scenario.value}: {e}")
        return outcomes

    async def scheduled_play(self, consciousness: Any = None) -> PlayOutcome | None:
        """Called periodically by LifeEngine.

        Picks a scenario based on which heads need most development.
        """
        try:
            from .shesha_heads import get_shesha
            shesha = get_shesha()
            heads = shesha.list_heads()
            if heads and len(heads) >= 2:
                scenario_heads = [h.id for h in heads[:2]]
                scenario_name = f"cooperative_play_{self._sessions_completed}"
                outcome = await shesha.inter_head_collaboration(
                    task=f"Cooperate on: {scenario_name}",
                    heads=scenario_heads,
                )
                if outcome:
                    self._sessions_completed += 1
                    return outcome
        except Exception:
            pass

        head_avg_traits = {}
        for name, hdata in self._heads.items():
            traits = hdata["traits"]
            head_avg_traits[name] = sum(traits.values()) / max(len(traits), 1)

        sorted_heads = sorted(head_avg_traits.items(), key=lambda x: x[1])
        low_trait_heads = [h for h, _ in sorted_heads[:3]]

        scenarios = list(PlayScenario)
        weights = {
            PlayScenario.CODE_REVIEW: 1.0,
            PlayScenario.DEBATE: 0.8,
            PlayScenario.CO_PLANNING: 0.7,
            PlayScenario.NEGOTIATION: 0.6,
            PlayScenario.CRITIQUE: 0.9,
            PlayScenario.TEACHING: 0.5,
            PlayScenario.PUZZLE: 0.4,
            PlayScenario.CRISIS: 0.2,
        }
        chosen = random.choices(
            scenarios,
            weights=[weights[s] for s in scenarios],
            k=1,
        )[0]

        try:
            return await self.run_scenario(chosen, low_trait_heads, consciousness)
        except Exception as e:
            logger.warning(f"Scheduled play failed for {chosen.value}: {e}")
            return None

    # ── Stats & Summary ──

    def stats(self) -> dict:
        """Return play engine statistics."""
        if not self._history:
            return {
                "total_sessions": 0,
                "scenarios_completed": 0,
                "avg_cooperation_score": 0.0,
                "most_improved_head": "",
            }

        completed = [o for o in self._history if o.resolution == "completed"]
        avg_coop = (
            sum(o.cooperation_score for o in self._history) / len(self._history)
        ) if self._history else 0.0

        all_improvements: dict[str, float] = {}
        for outcome in self._history:
            for head_id, changes in outcome.head_trait_changes.items():
                total_delta = sum(abs(v) for v in changes.values())
                all_improvements[head_id] = all_improvements.get(head_id, 0) + total_delta

        most_improved = max(all_improvements, key=all_improvements.get) if all_improvements else ""

        return {
            "total_sessions": self._sessions_completed,
            "scenarios_completed": len(completed),
            "avg_cooperation_score": round(avg_coop, 3),
            "most_improved_head": most_improved,
        }

    def get_head_learning_summary(self, head_id: str) -> str:
        """What has this head learned from play?"""
        points = self._heads.get(head_id, {}).get("learning_points", [])
        if not points:
            return f"{head_id} has not yet participated in play sessions."
        return f"{head_id} learned: " + "; ".join(points[-5:])

    # ── Internal Helpers ──

    async def _think(self, head_name: str, prompt: str, consciousness: Any) -> str:
        """Generate a thought for a specific head using consciousness.

        If consciousness.stream_of_thought() is available, collects tokens
        into a complete response. Otherwise, generates a simulated thought.
        """
        if consciousness and hasattr(consciousness, "stream_of_thought"):
            try:
                parts = []
                async for chunk in consciousness.stream_of_thought(prompt):
                    parts.append(chunk)
                return "".join(parts).strip()[:800]
            except Exception as e:
                logger.debug(f"LLM think failed for {head_name}: {e}")

        return self._simulated_think(head_name)

    def _simulated_think(self, head_name: str) -> str:
        """Generate a simulated thought when no LLM is available."""
        traits = self._heads.get(head_name, {}).get("traits", {})
        creativity = traits.get("creativity", 0.5)
        precision = traits.get("precision", 0.5)
        empathy = traits.get("empathy", 0.5)

        styles = []
        if creativity > 0.6:
            styles.append("creative and exploratory")
        if precision > 0.6:
            styles.append("precise and analytical")
        if empathy > 0.6:
            styles.append("empathetic and considerate")
        if not styles:
            styles.append("neutral and balanced")

        trait_text = ", ".join(f"{k}={v:.1f}" for k, v in sorted(traits.items()) if v > 0.5)
        return (
            f"[{head_name}] @ {random.choice(styles)}: "
            f"I approach this scenario with {trait_text}. "
            f"My analysis considers multiple perspectives while staying focused on the objective. "
            f"Let me contribute constructively to the group effort."
        )

    @staticmethod
    def _format_turns(turns: list[PlayTurn]) -> str:
        return "\n".join(
            f"[Turn {t.turn_number}] {t.from_head} → {t.to_head}: {t.action[:120]}"
            for t in turns
        )

    @staticmethod
    def _score_cooperation(turns: list[PlayTurn]) -> float:
        """Estimate cooperation from turn interactions."""
        if not turns:
            return 0.5
        positive_markers = [
            "agree", "accept", "good point", "well said", "collaborat",
            "compromise", "fair", "together", "support", "build on",
            "thank", "insightful", "valid", "improve", "refine",
            "acknowledge", "appreciate", "concede", "concur",
        ]
        score = 0.5
        for t in turns:
            action_lower = t.action.lower()
            for marker in positive_markers:
                if marker in action_lower:
                    score += 0.05
        return round(min(1.0, score), 2)

    def _apply_trait_changes(self, changes: dict[str, dict[str, float]]) -> None:
        """Apply trait changes from a play session to head profiles."""
        for head_id, deltas in changes.items():
            if head_id not in self._heads:
                continue
            for trait, delta in deltas.items():
                current = self._heads[head_id]["traits"].get(trait, 0.5)
                self._heads[head_id]["traits"][trait] = round(
                    max(0.0, min(1.0, current + delta)), 3
                )

    def get_head_traits(self, head_id: str) -> dict[str, float]:
        return dict(self._heads.get(head_id, {}).get("traits", {}))


# ═══ Singleton ═══

_engine: PlayEngine | None = None


def get_play_engine() -> PlayEngine:
    global _engine
    if _engine is None:
        _engine = PlayEngine()
    return _engine


__all__ = [
    "PlayScenario",
    "PlayRole",
    "PlayTurn",
    "PlayOutcome",
    "PlayEngine",
    "get_play_engine",
]
