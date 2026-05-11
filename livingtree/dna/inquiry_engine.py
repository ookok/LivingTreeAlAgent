"""Doctor-R1 Clinical Inquiry Engine — experiential RL for strategic dialogue.

Based on Lai, Liu, Wang, Ma & Liu (Tsinghua, 2025), arXiv:2510.04284:
  "Doctor-R1: Mastering Clinical Inquiry with Experiential Agentic RL"

Three core mechanisms adapted from clinical inquiry to LivingTree:
  1. COUNTERPARTY AGENT — simulates stakeholder/regulator for realistic dialogue
     (maps to: environmental regulator, project owner, auditor)
  2. TWO-TIERED REWARD — separates task accuracy from interaction quality
     (maps to: S-GRPO reward → task_quality + interaction_quality split)
  3. EXPERIENCE REPOSITORY — stores high-quality trajectories for policy learning
     (maps to: EvolutionStore + elite_registry enhanced with trajectory filtering)

Key insight from the paper: "strategic multi-turn inquiry to guide decision-making"
→ this is isomorphic to LivingTree's Clarifier + ResearchTeam pipeline for
environmental reports, but currently lacks adversarial testing and trajectory
learning.

Integration:
  ResearchTeam + CounterpartyAgent → adversarial multi-turn inquiry
  S-GRPO + TDMReward → two-tiered (task_accuracy + interaction_quality)
  EvolutionStore → experience repository for high-yield question patterns
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ═══ Data Types ═══


@dataclass
class HighYieldQuestion:
    """A question pattern that consistently yields high information gain.

    Doctor-R1 analog: "high-yield questions" — questions that maximize
    diagnostic value per turn in the clinical conversation.
    """
    pattern: str                   # The question template
    domain: str                    # Which domain (环评, code, financial...)
    information_gain: float        # Average IG achieved by this question
    usage_count: int               # How many times used
    success_count: int             # How many times led to better outcome
    last_used: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.success_count / max(self.usage_count, 1)


@dataclass
class CounterpartyProfile:
    """Profile of a stakeholder/regulator for adversarial testing.

    Doctor-R1 analog: the "patient agent" that simulates realistic
    clinical presentations with varying levels of clarity and honesty.
    """
    role: str                      # "regulator", "project_owner", "auditor", "expert"
    name: str
    knowledge_level: float         # 0=layperson, 1=domain expert
    cooperativeness: float         # 0=adversarial, 1=fully cooperative
    verbosity: float               # 0=terse, 1=verbose
    bias: str = "neutral"         # lean toward: "approval", "rejection", "neutral"
    goals: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)


@dataclass
class InquiryTurn:
    """A single turn in a multi-turn inquiry dialogue."""
    turn_id: int
    agent_question: str            # What the agent asked
    counterparty_response: str     # How the stakeholder replied
    information_gain: float        # How much new info was obtained
    question_type: str             # "clarification", "verification", "exploration", "confirmation"
    task_quality_impact: float     # How much this turn improved task accuracy
    interaction_quality: float     # How natural/appropriate the interaction was


@dataclass
class ClinicalTrajectory:
    """A complete multi-turn inquiry trajectory.

    Doctor-R1 analog: a full doctor-patient consultation episode
    stored in the experience repository.
    """
    trajectory_id: str
    task: str
    domain: str
    counterparty: CounterpartyProfile
    turns: list[InquiryTurn]
    final_outcome: str             # The final conclusion
    task_accuracy: float           # How correct was the final answer?
    interaction_quality: float     # How good was the dialogue process?
    total_information_gain: float
    lessons_learned: list[str]
    timestamp: float = field(default_factory=time.time)

    @property
    def total_score(self) -> float:
        return 0.5 * self.task_accuracy + 0.5 * self.interaction_quality

    @property
    def is_high_quality(self) -> bool:
        return self.total_score > 0.7


# ═══ Counterparty Agent ═══


class CounterpartyAgent:
    """Adversarial/testing counterparty for multi-turn inquiry.

    Doctor-R1 analog: the patient agent that provides realistic clinical
    presentations. In LivingTree, this is a stakeholder (regulator,
    project owner, auditor) who responds to the agent's questions.

    The key Doctor-R1 insight: true clinical/professional competence
    is demonstrated not in answering static benchmarks, but in conducting
    strategic multi-turn dialogue with an uncooperative or uncertain
    counterparty who may omit critical information.
    """

    # Domain-specific counterparty profiles
    PROFILES: dict[str, CounterpartyProfile] = {
        "regulator_strict": CounterpartyProfile(
            role="regulator", name="Environmental Regulator",
            knowledge_level=0.9, cooperativeness=0.3, verbosity=0.5,
            bias="rejection",
            goals=["Ensure full compliance", "Identify any violations"],
            constraints=["Must reference specific standards", "No verbal approval without documentation"],
        ),
        "regulator_normal": CounterpartyProfile(
            role="regulator", name="Standards Official",
            knowledge_level=0.7, cooperativeness=0.6, verbosity=0.6,
            bias="neutral",
            goals=["Verify compliance", "Provide guidance"],
            constraints=["References to GB/HJ standards preferred"],
        ),
        "project_owner": CounterpartyProfile(
            role="project_owner", name="Project Applicant",
            knowledge_level=0.4, cooperativeness=0.8, verbosity=0.7,
            bias="approval",
            goals=["Get project approved", "Minimize costs"],
            constraints=["May omit unfavorable data", "Needs clear guidance"],
        ),
        "auditor": CounterpartyProfile(
            role="auditor", name="Third-Party Auditor",
            knowledge_level=0.8, cooperativeness=0.5, verbosity=0.4,
            bias="neutral",
            goals=["Objective assessment", "Identify gaps"],
            constraints=["Requires evidence for all claims", "Will challenge unsupported assertions"],
        ),
        "expert_reviewer": CounterpartyProfile(
            role="expert", name="Domain Expert Reviewer",
            knowledge_level=0.95, cooperativeness=0.7, verbosity=0.3,
            bias="rejection",
            goals=["Ensure scientific rigor", "Catch methodological errors"],
            constraints=["Expects quantitative justification", "Will spot proxy variables"],
        ),
    }

    def __init__(self):
        self._used_profiles: dict[str, int] = {}

    def get_profile(self, role: str) -> CounterpartyProfile:
        """Get or create a counterparty profile."""
        profile = self.PROFILES.get(role)
        if not profile:
            profile = CounterpartyProfile(role=role, name=role, knowledge_level=0.5,
                                          cooperativeness=0.5, verbosity=0.5)
        self._used_profiles[role] = self._used_profiles.get(role, 0) + 1
        return profile

    def simulate_response(
        self, profile: CounterpartyProfile, question: str,
        hidden_knowledge: str = "",
    ) -> tuple[str, float]:
        """Simulate a counterparty response to an agent's question.

        The response quality depends on the profile's cooperativeness,
        knowledge level, and bias. Less cooperative profiles may omit
        critical information (requiring the agent to probe deeper).

        Returns:
            (response_text, information_gain) — how much new info was revealed
        """
        # Information gain depends on question quality and counterparty traits
        question_quality = self._assess_question_quality(question)
        base_gain = question_quality * profile.cooperativeness
        knowledge_ceiling = profile.knowledge_level

        ig = min(base_gain, knowledge_ceiling) * 0.7 + base_gain * 0.3

        # Build response
        response = self._build_response(profile, question, hidden_knowledge, ig)

        return response, round(ig, 3)

    @staticmethod
    def _assess_question_quality(question: str) -> float:
        """Rate a question's quality (how much information it will extract)."""
        score = 0.3  # Base
        q = question.lower()

        # Specific questions score higher
        if "?" in q or "？" in q:
            score += 0.1
        if len(q) > 20:
            score += 0.1
        if any(kw in q for kw in ["具体", "多少", "何时", "哪里", "哪个",
                                     "specific", "how many", "when", "where", "which"]):
            score += 0.15
        if any(kw in q for kw in ["标准", "规范", "法规", "standard", "regulation"]):
            score += 0.1
        # Follow-up questions score higher (show engagement)
        if any(kw in q for kw in ["进一步", "明确", "确认", "further", "clarify", "confirm"]):
            score += 0.1
        # Open-ended questions extract more
        if any(kw in q for kw in ["描述", "说明", "解释", "describe", "explain"]):
            score += 0.1

        return min(1.0, score)

    def _build_response(
        self, profile: CounterpartyProfile, question: str,
        hidden: str, info_gain: float,
    ) -> str:
        """Build a realistic counterparty response."""
        # High info gain → detailed answer
        # Low info gain → vague or evasive answer

        parts = []

        if profile.knowledge_level > 0.7 and info_gain > 0.5:
            parts.append("Based on my understanding, ")
            if hidden:
                parts.append(f"{hidden[:200]}. ")
            parts.append("The key aspects are: ")

        if info_gain > 0.6:
            parts.append("The relevant standard GB3095-2012 specifies that... "
                         "monitoring data should be collected over 24-hour periods "
                         "for SO2 and NO2, with wind direction noted.")
        elif info_gain > 0.3:
            parts.append("There are some standards that apply, but I would "
                         "need to check the specific requirements. "
                         "Generally speaking, emissions must be within limits.")
        else:
            if profile.cooperativeness < 0.5:
                parts.append("I'm not sure I can comment on that specifically. "
                             "You should refer to the project documentation.")
            else:
                parts.append("That's a good question. I don't have the "
                             "specific data at hand, but I can direct you to "
                             "the relevant section of the application.")

        # Add bias coloring
        if profile.bias == "rejection" and info_gain < 0.5:
            parts.append(" I would note that this area typically requires "
                         "stricter scrutiny under current regulations.")
        elif profile.bias == "approval":
            parts.append(" Generally, this type of project has been approved "
                         "in similar cases.")

        return " ".join(parts)


# ═══ Two-Tiered Reward System ═══


class TwoTieredReward:
    """Separate task accuracy from interaction quality rewards.

    Doctor-R1 analog: the two-tiered reward architecture that separately
    optimizes clinical decision-making (Tier 1) and communicative inquiry
    skills (Tier 2).

    Applied to LivingTree:
      Tier 1: task_accuracy — output correctness, plan feasibility, compliance
      Tier 2: interaction_quality — dialogue efficiency, question relevance,
              information gain per turn, cost efficiency
    """

    def __init__(self, alpha: float = 0.5):
        """alpha: weight for task_accuracy vs interaction_quality."""
        self._alpha = alpha
        self._task_scores: deque[float] = deque(maxlen=100)
        self._interaction_scores: deque[float] = deque(maxlen=100)

    def compute_rewards(
        self, trajectory: ClinicalTrajectory,
    ) -> tuple[float, float, float]:
        """Compute two-tiered rewards + combined score.

        Returns:
            (task_accuracy, interaction_quality, combined_score)
        """
        # Tier 1: Task accuracy
        task_acc = trajectory.task_accuracy

        # Tier 2: Interaction quality
        if trajectory.turns:
            avg_ig = sum(t.information_gain for t in trajectory.turns) / len(trajectory.turns)
            question_eff = sum(
                1.0 for t in trajectory.turns
                if t.question_type in ("verification", "confirmation")
            ) / max(len(trajectory.turns), 1)
            interaction = 0.6 * avg_ig + 0.4 * question_eff
        else:
            interaction = 0.5

        combined = self._alpha * task_acc + (1 - self._alpha) * interaction

        self._task_scores.append(task_acc)
        self._interaction_scores.append(interaction)

        return round(task_acc, 3), round(interaction, 3), round(combined, 3)

    def calibrate(self, target_task_ratio: float = 0.5) -> float:
        """Auto-calibrate alpha to achieve target task/interaction balance."""
        if not self._task_scores or not self._interaction_scores:
            return self._alpha
        avg_task = sum(self._task_scores) / len(self._task_scores)
        avg_inter = sum(self._interaction_scores) / len(self._interaction_scores)
        if avg_task + avg_inter > 0:
            current_ratio = avg_task / (avg_task + avg_inter)
            # Adjust alpha toward target
            self._alpha += 0.1 * (target_task_ratio - current_ratio)
            self._alpha = max(0.2, min(0.8, self._alpha))
        return self._alpha

    def stats(self) -> dict:
        return {
            "alpha": round(self._alpha, 3),
            "avg_task_accuracy": round(
                sum(self._task_scores) / max(len(self._task_scores), 1), 3),
            "avg_interaction_quality": round(
                sum(self._interaction_scores) / max(len(self._interaction_scores), 1), 3),
        }


# ═══ Experience Repository ═══


class ExperienceRepository:
    """Stores high-quality trajectories for policy learning.

    Doctor-R1 analog: the experience repository that grounds RL policy
    learning in high-quality prior trajectories, helping the agent learn
    which inquiry strategies are most effective.

    Three functions:
      1. Store: add completed trajectories
      2. Retrieve: get top-K trajectories by domain and quality
      3. Extract: derive high-yield question patterns from stored trajectories
    """

    def __init__(self, max_trajectories: int = 500):
        self._trajectories: deque[ClinicalTrajectory] = deque(maxlen=max_trajectories)
        self._high_yield_questions: dict[str, list[HighYieldQuestion]] = {}
        self._domain_patterns: dict[str, list[str]] = {}

    # ── Store ──

    def store(self, trajectory: ClinicalTrajectory) -> None:
        """Store a completed trajectory and extract patterns."""
        self._trajectories.append(trajectory)
        self._extract_patterns(trajectory)

    def _extract_patterns(self, trajectory: ClinicalTrajectory) -> None:
        """Extract high-yield question patterns from a trajectory."""
        domain = trajectory.domain
        if domain not in self._high_yield_questions:
            self._high_yield_questions[domain] = []

        for turn in trajectory.turns:
            if turn.information_gain > 0.5:
                # Check if similar pattern exists
                pattern = turn.agent_question[:60].lower()
                existing = None
                for hq in self._high_yield_questions[domain]:
                    if self._similarity(pattern, hq.pattern) > 0.7:
                        existing = hq
                        break

                if existing:
                    existing.usage_count += 1
                    existing.information_gain = (
                        0.8 * existing.information_gain + 0.2 * turn.information_gain)
                    if trajectory.task_accuracy > 0.7:
                        existing.success_count += 1
                    existing.last_used = time.time()
                else:
                    hq = HighYieldQuestion(
                        pattern=pattern,
                        domain=domain,
                        information_gain=turn.information_gain,
                        usage_count=1,
                        success_count=1 if trajectory.task_accuracy > 0.7 else 0,
                        last_used=time.time(),
                    )
                    self._high_yield_questions[domain].append(hq)

    # ── Retrieve ──

    def get_trajectories(
        self, domain: str = "", min_score: float = 0.6, top_k: int = 5,
    ) -> list[ClinicalTrajectory]:
        """Get top-K high-quality trajectories."""
        candidates = [
            t for t in self._trajectories
            if (not domain or t.domain == domain) and t.total_score >= min_score
        ]
        candidates.sort(key=lambda t: -t.total_score)
        return candidates[:top_k]

    def get_lessons(self, domain: str = "", top_k: int = 5) -> list[str]:
        """Get lessons learned from high-quality trajectories."""
        trajs = self.get_trajectories(domain, min_score=0.7, top_k=top_k)
        lessons = []
        for t in trajs:
            lessons.extend(t.lessons_learned[:3])
        return list(dict.fromkeys(lessons))[:top_k]  # Deduplicate

    # ── High-Yield Questions ──

    def get_high_yield_questions(
        self, domain: str, min_success_rate: float = 0.5, top_k: int = 5,
    ) -> list[HighYieldQuestion]:
        """Get the most effective question patterns for a domain."""
        candidates = self._high_yield_questions.get(domain, [])
        qualified = [q for q in candidates if q.success_rate >= min_success_rate]
        qualified.sort(key=lambda q: -q.information_gain)
        return qualified[:top_k]

    def suggest_question(self, domain: str) -> str | None:
        """Suggest the single best question to ask next."""
        questions = self.get_high_yield_questions(domain, top_k=1)
        return questions[0].pattern if questions else None

    # ── Helpers ──

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Jaccard word similarity."""
        wa = set(a.split())
        wb = set(b.split())
        if not wa or not wb:
            return 0.0
        return len(wa & wb) / len(wa | wb)

    # ── Stats ──

    def stats(self) -> dict[str, Any]:
        domains = set(t.domain for t in self._trajectories)
        return {
            "total_trajectories": len(self._trajectories),
            "high_quality_count": sum(1 for t in self._trajectories if t.is_high_quality),
            "domains": list(domains),
            "high_yield_questions": {
                d: len(qs) for d, qs in self._high_yield_questions.items()},
        }


# ═══ Integrated Inquiry Engine ═══


class InquiryEngine:
    """Full Doctor-R1 inquiry pipeline for LivingTree.

    Combines Counterparty Agent + Two-Tiered Reward + Experience Repository
    into a single integrated engine for strategic multi-turn inquiry.

    HiLight integration (v2): Uses the two-tiered reward signal (task_accuracy
    + interaction_quality) as RL training reward for the EmphasisActor.
    Each completed inquiry trajectory provides per-turn (query, response, reward)
    training samples — the more inquiries completed, the better the highlighting
    policy becomes at identifying critical evidence in inquiry responses.
    """

    def __init__(self, emphasizer: Any = None):
        self._counterparty = CounterpartyAgent()
        self._reward = TwoTieredReward()
        self._repo = ExperienceRepository()
        self._active_trajectories: dict[str, ClinicalTrajectory] = {}
        self._emphasizer = emphasizer  # Optional EmphasisActor for HiLight RL training

    # ── Start Inquiry ──

    def start_inquiry(
        self, task: str, domain: str, counterparty_role: str,
    ) -> tuple[str, CounterpartyProfile]:
        """Begin a new multi-turn inquiry session.

        Returns:
            (trajectory_id, counterparty_profile) for tracking the conversation
        """
        profile = self._counterparty.get_profile(counterparty_role)
        traj_id = f"inq_{time.time():.0f}_{domain[:10]}"
        trajectory = ClinicalTrajectory(
            trajectory_id=traj_id, task=task, domain=domain,
            counterparty=profile, turns=[],
            final_outcome="", task_accuracy=0.0, interaction_quality=0.0,
            total_information_gain=0.0, lessons_learned=[],
        )
        self._active_trajectories[traj_id] = trajectory
        logger.info(f"Inquiry started: {traj_id} ({domain}, vs {profile.name})")
        return traj_id, profile

    # ── Ask Question ──

    def ask_question(
        self, traj_id: str, question: str, hidden_knowledge: str = "",
        question_type: str = "exploration",
    ) -> tuple[str, float]:
        """Ask a question to the counterparty and get response + info gain.

        Returns:
            (response_text, information_gain)
        """
        traj = self._active_trajectories.get(traj_id)
        if not traj:
            raise ValueError(f"No active inquiry: {traj_id}")

        response, ig = self._counterparty.simulate_response(
            traj.counterparty, question, hidden_knowledge)

        turn = InquiryTurn(
            turn_id=len(traj.turns) + 1,
            agent_question=question,
            counterparty_response=response,
            information_gain=ig,
            question_type=question_type,
            task_quality_impact=ig * 0.8,  # Info gain ≈ task improvement
            interaction_quality=0.7,       # Assume reasonable for now
        )
        traj.turns.append(turn)
        traj.total_information_gain += ig

        return response, ig

    # ── End Inquiry ──

    def end_inquiry(
        self, traj_id: str, final_outcome: str,
        task_accuracy: float, interaction_quality: float,
        lessons: list[str] | None = None,
    ) -> ClinicalTrajectory:
        """Complete the inquiry session and store in experience repository."""
        traj = self._active_trajectories.pop(traj_id, None)
        if not traj:
            raise ValueError(f"No active inquiry: {traj_id}")

        traj.final_outcome = final_outcome
        traj.task_accuracy = task_accuracy
        traj.interaction_quality = interaction_quality
        traj.lessons_learned = lessons or []

        # Compute two-tiered reward
        task, inter, combined = self._reward.compute_rewards(traj)

        # Store in experience repository
        self._repo.store(traj)

        # ── HiLight RL: train emphasis policy from inquiry reward ──
        if self._emphasizer is not None and traj.turns:
            self._train_emphasizer_from_trajectory(traj, combined)

        logger.info(
            f"Inquiry ended: {traj_id} — task={task:.2f} inter={inter:.2f} "
            f"combined={combined:.2f} ({len(traj.turns)} turns, {traj.total_information_gain:.2f} IG)",
        )
        return traj

    # ── HiLight RL Training ────────────────────────────────────────

    def _train_emphasizer_from_trajectory(
        self, traj: ClinicalTrajectory, combined_reward: float,
    ) -> None:
        """Train EmphasisActor using inquiry trajectory as RL signal.

        Each inquiry turn provides a (query, response, reward) tuple:
          - query: the agent's question (what to look for)
          - context: the counterparty's response (where evidence lives)
          - reward: the combined task+interaction score

        High-reward turns → policy learns to highlight response spans
        that led to high information gain.
        """
        if self._emphasizer is None:
            return

        try:
            for turn in traj.turns:
                if len(turn.counterparty_response) < 30:
                    continue
                # Per-turn reward: weight by information gain
                turn_reward = combined_reward * (0.5 + 0.5 * turn.information_gain)
                result = self._emphasizer.train_step(
                    turn.agent_question,
                    turn.counterparty_response,
                    turn_reward,
                )

            logger.debug(
                f"HiLight trained from inquiry {traj.trajectory_id}: "
                f"reward={combined_reward:.2f}, turns={len(traj.turns)}"
            )
        except Exception as e:
            logger.debug(f"HiLight inquiry training failed: {e}")

    @property
    def emphasizer(self):
        """Access the EmphasisActor for external training control."""
        return self._emphasizer

    @emphasizer.setter
    def emphasizer(self, value):
        self._emphasizer = value

    # ── Suggest Next Question ──

    def suggest_question(self, domain: str) -> str | None:
        """Suggest the best next question based on experience repository."""
        return self._repo.suggest_question(domain)

    # ── Doctor-R1 Enhanced Trajectory Filtering ═────────────────────

    def filter_trajectories(
        self, min_information_gain: float = 0.5,
        min_task_accuracy: float = 0.3,
        max_trajectories: int = 50,
    ) -> list:
        """Filter high-quality trajectories for experience replay.

        Doctor-R1 (arXiv:2510.04284): only store trajectories where the
        inquiry process led to meaningful outcomes. This prevents the
        experience repository from being diluted by low-quality interactions
        that would corrupt the policy learning signal.

        Filtering criteria:
          1. Total information gain ≥ min_information_gain
          2. Task accuracy ≥ min_task_accuracy
          3. Multi-turn trajectories preferred over single-turn

        Returns:
            Sorted list of qualifying trajectories (best first)
        """
        all_trajs = self._repo.get_all()
        filtered = []
        for traj in all_trajs:
            if traj.total_information_gain >= min_information_gain:
                if traj.task_accuracy >= min_task_accuracy:
                    filtered.append(traj)

        # Multi-turn bonus: order by composite quality score
        filtered.sort(
            key=lambda t: (
                t.task_accuracy * 0.4 +
                t.interaction_quality * 0.3 +
                t.total_information_gain * 0.2 +
                (0.1 if len(t.turns) >= 3 else 0.0)
            ),
            reverse=True,
        )
        return filtered[:max_trajectories]

    def replay_buffer_sample(
        self, n: int = 5, domain: str | None = None,
    ) -> list[dict[str, Any]]:
        """Sample from replay buffer for Doctor-R1 policy learning.

        Periodically sample past successful inquiry trajectories to
        reinforce question patterns that led to high information gain.
        This closes the training loop:
          inquiry → outcome → filter → replay → improve

        Args:
            n: Number of trajectory segments to sample
            domain: Optional domain filter

        Returns:
            List of replay samples with question, response, and outcome
        """
        import random
        qualified = self.filter_trajectories(min_information_gain=0.3)
        if domain:
            qualified = [
                t for t in qualified
                if t.domain == domain or t.domain == "general"
            ]

        if not qualified:
            return []

        samples = []
        for _ in range(min(n, len(qualified))):
            traj = random.choice(qualified)
            if traj.turns:
                best_turn = max(traj.turns, key=lambda t: t.information_gain)
                samples.append({
                    "trajectory_id": traj.trajectory_id,
                    "domain": traj.domain,
                    "question": best_turn.agent_question,
                    "response": best_turn.counterparty_response[:200],
                    "information_gain": best_turn.information_gain,
                    "task_accuracy": traj.task_accuracy,
                    "lesson": traj.lessons_learned[0] if traj.lessons_learned else "",
                })

        return samples

    # ── Stats ──

    def stats(self) -> dict[str, Any]:
        return {
            "active_inquiries": len(self._active_trajectories),
            "reward": self._reward.stats(),
            "repository": self._repo.stats(),
            "has_emphasizer": self._emphasizer is not None,
        }


# ═══ Singleton ═══

_inquiry: InquiryEngine | None = None


def get_inquiry_engine(emphasizer: Any = None) -> InquiryEngine:
    global _inquiry
    if _inquiry is None:
        _inquiry = InquiryEngine(emphasizer=emphasizer)
    elif emphasizer is not None and _inquiry._emphasizer is None:
        _inquiry._emphasizer = emphasizer
    return _inquiry


__all__ = [
    "InquiryEngine", "CounterpartyAgent", "CounterpartyProfile",
    "TwoTieredReward", "ExperienceRepository",
    "ClinicalTrajectory", "InquiryTurn", "HighYieldQuestion",
    "get_inquiry_engine",
]
