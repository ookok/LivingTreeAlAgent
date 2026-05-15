"""JointEvolution — Three-body closed-loop co-evolution coordinator.

Based on "Robot Cognitive Learning by Considering Physical Properties"
(Sun, Huang, Luo, Ji, Liu, Liu, Zhang — Engineering, 2025).

Core thesis: A robot is a three-body physical system (P-body, C-body, B-body)
that evolves through closed-loop interactions, NOT one-way pipelines.

Mapping to LivingTree:
  P-body = knowledge/ + observability/ + model output reception
  C-body = treellm/ + dna/ + reasoning/ + economy/
  B-body = execution/ + capability/ + core/

Three critical closed loops (from the paper):

1. C→P (Long-term reward):
   C-body provides FUTURE sub-goal-anchored rewards to optimize P-body's
   perception policy — not immediate latency/quality scores, but trajectory-level
   delayed rewards: "did choosing model A for step 1 ultimately lead to task
   success after step 4?"

2. C→B (Sub-goal decomposition):
   C-body generates intermediate sub-goals that decompose complex tasks into
   short, simple sequential sub-tasks. Each sub-goal is a verifiable milestone
   with completion criteria — NOT just "use model X for step Y".

3. B→P (Knowledge feedback loop):
   B-body's execution results change the environment state → P-body acquires
   new information → knowledge base updates → future perception improves.

Joint evolution metric: The three bodies evolve together. A unified health
score measures how efficiently the P→C→B→P loop operates as a whole.

Usage:
    je = get_joint_evolution()
    trajectory = je.start_trajectory(query="...", task_id="...")
    # ... route through P-body (perception) ...
    je.record_perception(trajectory_id, states={...})
    # ... C-body cognition (routing decision) ...
    je.record_cognition(trajectory_id, decision={...})
    # ... B-body execution ...
    je.record_behavior(trajectory_id, result={...})
    # Complete the loop
    je.complete_trajectory(trajectory_id, success=True)
    # Get joint health
    health = je.joint_health()
"""

from __future__ import annotations

import json
import math
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

TRAJECTORY_DIR = Path(".livingtree/joint_evolution")
HEALTH_FILE = TRAJECTORY_DIR / "joint_health.json"


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class PerceptionState:
    """P-body state at a point in the trajectory.

    What the system "perceives" — extracted knowledge, context, observations.
    """
    query: str
    task_type: str = "general"
    knowledge_retrieved: int = 0          # Number of knowledge items retrieved
    context_tokens: int = 0               # Context window size
    confidence: float = 0.5               # Perception confidence
    deep_probe_strategies: list[str] = field(default_factory=list)
    embedding_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class CognitionDecision:
    """C-body decision at a point in the trajectory.

    What the cognition layer decided — routing, sub-goals, strategy.
    """
    elected_provider: str = ""
    backup_provider: str = ""
    routing_method: str = ""              # election, bandit, fitness, score_matching
    sub_goals: list[str] = field(default_factory=list)
    election_scores: dict[str, float] = field(default_factory=dict)
    aggregate_used: bool = False
    deep_probe_used: bool = False
    self_play_used: bool = False
    reasoning_depth: float = 0.5           # From DepthGrading


@dataclass
class BehaviorResult:
    """B-body result at a point in the trajectory.

    What the behavior layer executed — actions, outcomes.
    """
    provider: str = ""
    success: bool = False
    tokens_used: int = 0
    latency_ms: float = 0.0
    cost_yuan: float = 0.0
    output_length: int = 0
    depth_grade_tier: str = "shallow"      # From DepthGrading
    self_critique_present: bool = False
    error_detail: str = ""
    sub_goal_achieved: list[bool] = field(default_factory=list)


@dataclass
class EvolutionStep:
    """A single step in the P→C→B evolution loop."""
    step_id: int
    perception: PerceptionState = field(default_factory=PerceptionState)
    cognition: CognitionDecision = field(default_factory=CognitionDecision)
    behavior: BehaviorResult = field(default_factory=BehaviorResult)
    timestamp: float = field(default_factory=time.time)


@dataclass
class EvolutionTrajectory:
    """A complete trajectory through the P→C→B→P loop.

    Tracks the full co-evolution of all three bodies across a task.
    """
    trajectory_id: str
    task_id: str
    task_description: str = ""
    steps: list[EvolutionStep] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    overall_success: bool = False
    total_tokens: int = 0
    total_cost_yuan: float = 0.0
    total_latency_ms: float = 0.0
    p_quality: float = 0.0       # Perception quality (knowledge relevance, context)
    c_quality: float = 0.0       # Cognition quality (routing accuracy, sub-goal fit)
    b_quality: float = 0.0       # Behavior quality (execution success, cost efficiency)
    joint_health_contribution: float = 0.0  # How much this trajectory improved joint health

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def p_to_c_latency(self) -> float:
        """C→P interaction: how fast perception feeds cognition."""
        if len(self.steps) < 2:
            return 0.0
        intervals = [
            self.steps[i].timestamp - self.steps[i-1].timestamp
            for i in range(1, len(self.steps))
        ]
        return sum(intervals) / len(intervals) if intervals else 0.0


@dataclass
class JointHealth:
    """Unified metric for self-evolving AI agents (Fang et al., 2025 survey).

    Four-component taxonomy: System Inputs / Agent System / Environment / Optimisers.
    """
    score: float = 0.0
    p_health: float = 0.5       # System Inputs health (DeepProbe, MicroTurn, Interject)
    c_health: float = 0.5       # Agent System health (TreeLLM, Providers, Election)
    b_health: float = 0.5       # Environment health (Knowledge, Stigmergy, Feedback)
    o_health: float = 0.5       # Optimiser health (JointEvolution, Elo, RouteLearner)
    c_to_p_reward_quality: float = 0.5
    c_to_b_subgoal_quality: float = 0.5
    b_to_p_feedback_quality: float = 0.5
    loop_efficiency: float = 0.5
    total_trajectories: int = 0
    successful_trajectories: int = 0
    safety_compliance: float = 0.5  # Safety/ethical score from CompetitiveEliminator
    convergence_trend: float = 0.0
    last_updated: float = field(default_factory=time.time)


# ═══ JointEvolution Coordinator ═══════════════════════════════════


class JointEvolutionCoordinator:
    """Three-body closed-loop co-evolution engine.

    Design: Sits above the existing P/C/B modules, tracking trajectories
    and computing delayed rewards that feed back into each layer's optimization.

    Key innovation over static pipelines:
      1. Delayed rewards: not "was this call fast?", but "did this decision help
         the ENTIRE task succeed?"
      2. Knowledge feedback: execution results update the perception model
      3. Joint health: all three bodies measured as ONE system

    From the paper: "The physical synergy among these three bodies contributes
    to their collective enhancement."
    """

    WINDOW_SIZE = 50           # Recent trajectories for health computation
    REWARD_DELAY_WINDOW = 5    # Steps before computing delayed reward
    MIN_TRAJECTORIES = 10      # Minimum trajectories before health is reliable

    def __init__(self):
        self._trajectories: dict[str, EvolutionTrajectory] = {}
        self._active_steps: dict[str, EvolutionStep] = {}  # traj_id → current step
        self._health = JointHealth()
        self._long_term_rewards: dict[str, float] = {}     # provider → accumulated reward
        self._subgoal_success: dict[str, list[bool]] = defaultdict(list)  # provider → subgoal results
        self._loaded = False
        self._load()

    # ── Trajectory Lifecycle ──────────────────────────────────────

    def start_trajectory(
        self, query: str, task_id: str = "", task_description: str = "",
    ) -> str:
        """Begin tracking a new P→C→B evolution trajectory.

        Returns trajectory_id for subsequent record_*() calls.
        """
        import hashlib
        traj_id = hashlib.sha256(
            f"{task_id}{query}{time.time()}".encode()
        ).hexdigest()[:16]

        trajectory = EvolutionTrajectory(
            trajectory_id=traj_id,
            task_id=task_id or traj_id,
            task_description=task_description or query[:200],
        )
        self._trajectories[traj_id] = trajectory
        logger.debug(
            f"JointEvolution: trajectory {traj_id} started "
            f"('{task_description[:60]}...')"
        )
        return traj_id

    def record_perception(
        self, trajectory_id: str, step_id: int = 0,
        query: str = "", task_type: str = "general",
        knowledge_retrieved: int = 0, context_tokens: int = 0,
        confidence: float = 0.5, deep_probe_strategies: list[str] | None = None,
        embedding_scores: dict[str, float] | None = None,
    ) -> EvolutionStep:
        """Record P-body (perception) state.

        Called after knowledge retrieval, context preparation, DeepProbe rewriting.
        """
        step = EvolutionStep(
            step_id=step_id,
            perception=PerceptionState(
                query=query, task_type=task_type,
                knowledge_retrieved=knowledge_retrieved,
                context_tokens=context_tokens,
                confidence=confidence,
                deep_probe_strategies=deep_probe_strategies or [],
                embedding_scores=embedding_scores or {},
            ),
        )
        self._active_steps[trajectory_id] = step

        traj = self._trajectories.get(trajectory_id)
        if traj:
            traj.steps.append(step)

        return step

    def record_cognition(
        self, trajectory_id: str, step_id: int = 0,
        elected_provider: str = "", backup_provider: str = "",
        routing_method: str = "", sub_goals: list[str] | None = None,
        election_scores: dict[str, float] | None = None,
        aggregate_used: bool = False, deep_probe_used: bool = False,
        self_play_used: bool = False, reasoning_depth: float = 0.5,
    ) -> None:
        """Record C-body (cognition) decision.

        Called after routing/election, sub-goal generation.
        """
        step = self._active_steps.get(trajectory_id)
        if not step:
            step = EvolutionStep(step_id=step_id)
            self._active_steps[trajectory_id] = step

        step.cognition = CognitionDecision(
            elected_provider=elected_provider,
            backup_provider=backup_provider,
            routing_method=routing_method,
            sub_goals=sub_goals or [],
            election_scores=election_scores or {},
            aggregate_used=aggregate_used,
            deep_probe_used=deep_probe_used,
            self_play_used=self_play_used,
            reasoning_depth=reasoning_depth,
        )

    def record_behavior(
        self, trajectory_id: str, step_id: int = 0,
        provider: str = "", success: bool = False,
        tokens_used: int = 0, latency_ms: float = 0.0,
        cost_yuan: float = 0.0, output_length: int = 0,
        depth_grade_tier: str = "shallow",
        self_critique_present: bool = False,
        error_detail: str = "",
    ) -> None:
        """Record B-body (behavior) execution result.

        Called after model output received, DepthGrading complete.
        """
        step = self._active_steps.get(trajectory_id)
        if not step:
            step = EvolutionStep(step_id=step_id)
            self._active_steps[trajectory_id] = step

        step.behavior = BehaviorResult(
            provider=provider, success=success,
            tokens_used=tokens_used, latency_ms=latency_ms,
            cost_yuan=cost_yuan, output_length=output_length,
            depth_grade_tier=depth_grade_tier,
            self_critique_present=self_critique_present,
            error_detail=error_detail,
        )

    def complete_trajectory(
        self, trajectory_id: str, overall_success: bool = True,
    ) -> EvolutionTrajectory | None:
        """Close the P→C→B loop and compute delayed rewards.

        Returns the completed trajectory, or None if not found.
        """
        traj = self._trajectories.get(trajectory_id)
        if not traj:
            return None

        traj.completed_at = time.time()
        traj.overall_success = overall_success

        # Aggregate step-level metrics
        traj.total_tokens = sum(
            s.behavior.tokens_used for s in traj.steps
        )
        traj.total_cost_yuan = sum(
            s.behavior.cost_yuan for s in traj.steps
        )
        traj.total_latency_ms = sum(
            s.behavior.latency_ms for s in traj.steps
        )

        # ── Compute body quality scores ──
        traj.p_quality = self._compute_p_quality(traj)
        traj.c_quality = self._compute_c_quality(traj)
        traj.b_quality = self._compute_b_quality(traj)

        # ── Compute delayed rewards (C→P loop) ──
        self._compute_long_term_rewards(traj)

        # ── Update subgoal tracking (C→B loop) ──
        self._update_subgoal_tracking(traj)

        # ── Update joint health ──
        traj.joint_health_contribution = self._update_health(traj)

        # ── Knowledge feedback (B→P loop) ──
        if overall_success:
            self._feedback_to_knowledge(traj)

        logger.info(
            f"JointEvolution: trajectory {trajectory_id} completed "
            f"(success={overall_success}, steps={traj.step_count}, "
            f"P={traj.p_quality:.2f} C={traj.c_quality:.2f} B={traj.b_quality:.2f})"
        )

        # Cleanup
        self._active_steps.pop(trajectory_id, None)

        # Persist
        self._save_health()

        # Prune old trajectories
        self._prune()

        return traj

    # ── Body Quality Scoring ──────────────────────────────────────

    @staticmethod
    def _compute_p_quality(traj: EvolutionTrajectory) -> float:
        """P-body quality: knowledge retrieval effectiveness."""
        if not traj.steps:
            return 0.5
        scores = []
        for s in traj.steps:
            # Knowledge retrieved vs context tokens ratio
            k_score = min(1.0, s.perception.knowledge_retrieved / 5.0) if s.perception.knowledge_retrieved > 0 else 0.3
            # DeepProbe strategies applied
            d_score = min(1.0, len(s.perception.deep_probe_strategies) / 4.0)
            # Confidence
            c_score = s.perception.confidence
            scores.append(k_score * 0.4 + d_score * 0.3 + c_score * 0.3)
        return round(sum(scores) / len(scores), 4)

    @staticmethod
    def _compute_c_quality(traj: EvolutionTrajectory) -> float:
        """C-body quality: routing accuracy + sub-goal effectiveness."""
        if not traj.steps:
            return 0.5
        scores = []
        for s in traj.steps:
            # Routing: did the elected provider succeed?
            r_score = 1.0 if s.behavior.success else 0.3
            # Sub-goals: did we generate meaningful sub-goals?
            g_score = min(1.0, len(s.cognition.sub_goals) / 3.0) if s.cognition.sub_goals else 0.3
            # Advanced features used
            a_score = 0.0
            if s.cognition.aggregate_used:
                a_score += 0.3
            if s.cognition.deep_probe_used:
                a_score += 0.2
            if s.cognition.self_play_used:
                a_score += 0.2
            scores.append(r_score * 0.5 + g_score * 0.3 + a_score * 0.2)
        return round(sum(scores) / len(scores), 4)

    @staticmethod
    def _compute_b_quality(traj: EvolutionTrajectory) -> float:
        """B-body quality: execution efficiency and depth."""
        if not traj.steps:
            return 0.5
        scores = []
        for s in traj.steps:
            # Success
            succ = 1.0 if s.behavior.success else 0.0
            # Depth
            tier_map = {"profound": 1.0, "deep": 0.7, "medium": 0.5, "shallow": 0.2}
            depth = tier_map.get(s.behavior.depth_grade_tier, 0.3)
            # Efficiency: tokens per unit output
            eff = min(1.0, s.behavior.output_length / max(s.behavior.tokens_used, 1))
            # Self-critique bonus
            sc = 0.2 if s.behavior.self_critique_present else 0.0
            scores.append(succ * 0.4 + depth * 0.3 + eff * 0.2 + sc)
        return round(sum(scores) / len(scores), 4)

    # ── C→P: Long-Term Reward Computation ────────────────────────

    def _compute_long_term_rewards(self, traj: EvolutionTrajectory) -> None:
        """C→P closed loop: compute delayed rewards and feed back to election.

        Key insight from the paper: C-body provides FUTURE sub-goal-anchored
        rewards to optimize P-body's perception policy — NOT immediate scores.

        Implementation: For each step's elected provider, the reward is:
          - If trajectory succeeded: +1.0 × trajectory quality
          - If trajectory failed: -0.5 × (trajectory progress at failure point)
        """
        for step in traj.steps:
            provider = step.cognition.elected_provider or step.behavior.provider
            if not provider:
                continue

            # Base reward
            if traj.overall_success:
                # Positive: trajectory-level success
                reward = 1.0 * (
                    traj.p_quality * 0.3 +
                    traj.c_quality * 0.3 +
                    traj.b_quality * 0.4
                )
            else:
                # Negative: but proportional to how far we got
                progress = step.step_id / max(traj.step_count, 1)
                reward = -0.5 * progress

            # EMA update to provider's long-term reward
            old = self._long_term_rewards.get(provider, 0.0)
            self._long_term_rewards[provider] = round(
                0.7 * old + 0.3 * reward, 4
            )

            logger.debug(
                f"JointEvolution C→P: {provider} "
                f"reward={reward:.3f} (trajectory {'✓' if traj.overall_success else '✗'})"
            )

    def get_long_term_reward(self, provider: str) -> float:
        """Get accumulated long-term reward for a provider.

        This should be used by HolisticElection to weight provider scores.
        Positive = this provider tends to lead to successful trajectories.
        """
        return self._long_term_rewards.get(provider, 0.0)

    def inject_rewards_to_election(self) -> dict[str, float]:
        """v2.6 LPO (arXiv:2605.06139): Trajectory-level target distribution
        for election scoring.

        Replaces simple reward * 0.3 scaling with LPO's principled geometric
        projection: long-term rewards → explicit π* target → zero-sum modifiers.

        Providers that tend to lead to successful trajectories get positive
        modifiers; chronic underperformers get proportionally negative ones.
        Total sum ≈ 0 (zero-sum property of LPO gradients).
        """
        if not self._long_term_rewards:
            return {}
        try:
            from livingtree.optimization.lpo_optimizer import TrajectoryLPO
            tto = TrajectoryLPO(divergence="reverse_kl", temperature=0.8)
            return tto.inject_to_election(self._long_term_rewards)
        except Exception:
            pass
        # Fallback: simple scaling
        modifiers: dict[str, float] = {}
        for provider, reward in self._long_term_rewards.items():
            modifiers[provider] = round(reward * 0.3, 4)
        return modifiers

    # ── C→B: Sub-Goal Tracking ────────────────────────────────────

    def _update_subgoal_tracking(self, traj: EvolutionTrajectory) -> None:
        """C→B closed loop: track sub-goal achievement per provider.

        From the paper: C-body generates sub-goals; B-body executes them.
        The success rate of sub-goal achievement measures C-body's effectiveness.
        """
        for step in traj.steps:
            provider = step.cognition.elected_provider or step.behavior.provider
            if not provider:
                continue

            # Sub-goal success: if behavior succeeded, assume sub-goals were met
            subgoal_ok = step.behavior.success
            self._subgoal_success[provider].append(subgoal_ok)

            # Keep only last 50
            if len(self._subgoal_success[provider]) > 50:
                self._subgoal_success[provider] = \
                    self._subgoal_success[provider][-50:]

    def get_subgoal_success_rate(self, provider: str) -> float:
        """Get sub-goal achievement rate for a provider.

        High rate → C-body's sub-goals for this provider are effective.
        """
        results = self._subgoal_success.get(provider, [])
        if not results:
            return 0.5
        return sum(results) / len(results)

    # ── B→P: Knowledge Feedback ───────────────────────────────────

    @staticmethod
    def _feedback_to_knowledge(traj: EvolutionTrajectory) -> None:
        """B→P closed loop: successful execution patterns → knowledge base.

        From the paper: B-body's actions change the environment → P-body
        acquires new information → updates its perception model.

        Implementation: record successful trajectory patterns for future
        routing decisions. Which provider+strategy combos work well together?
        """
        try:
            from ..knowledge.context_wiki import get_context_wiki
            wiki = get_context_wiki()
            # Store successful routing pattern as knowledge
            for step in traj.steps:
                if step.behavior.success and step.cognition.elected_provider:
                    pattern_key = (
                        f"route:{step.cognition.elected_provider}:"
                        f"{step.perception.task_type}"
                    )
                    # Store incrementally
                    existing = wiki.get(pattern_key, "").strip()
                    score_str = f"success_count:{int(time.time())}"
                    new_value = (
                        f"{existing}; {score_str}" if existing else score_str
                    )
                    wiki.set(pattern_key, new_value[:500])
        except (ImportError, AttributeError):
            pass

    # ── Joint Health ──────────────────────────────────────────────

    def _update_health(self, traj: EvolutionTrajectory) -> float:
        """Update joint health score with this trajectory's contribution."""
        recent = self._get_recent_trajectories()

        self._health.total_trajectories = len(recent)
        self._health.successful_trajectories = sum(
            1 for t in recent if t.overall_success
        )

        # Individual body health (EMA over recent trajectories)
        if recent:
            self._health.p_health = round(
                0.8 * self._health.p_health +
                0.2 * (sum(t.p_quality for t in recent) / len(recent)), 4
            )
            self._health.c_health = round(
                0.8 * self._health.c_health +
                0.2 * (sum(t.c_quality for t in recent) / len(recent)), 4
            )
            self._health.b_health = round(
                0.8 * self._health.b_health +
                0.2 * (sum(t.b_quality for t in recent) / len(recent)), 4
            )

        # Loop qualities
        self._health.c_to_p_reward_quality = self._compute_reward_quality()
        self._health.c_to_b_subgoal_quality = self._compute_subgoal_quality()
        self._health.b_to_p_feedback_quality = self._compute_feedback_quality()
        self._health.loop_efficiency = self._compute_loop_efficiency(recent)
        self._health.avg_trajectory_steps = (
            sum(t.step_count for t in recent) / max(len(recent), 1)
        )

        # Overall joint health: weighted balance of all three bodies
        self._health.score = round(
            self._health.p_health * 0.25 +
            self._health.c_health * 0.35 +    # C-body is most important (the "brain")
            self._health.b_health * 0.25 +
            self._health.loop_efficiency * 0.15, 4
        )

        # Convergence trend: positive = improving
        if recent and len(recent) >= 5:
            first_half = list(recent)[:len(recent)//2]
            second_half = list(recent)[len(recent)//2:]
            first_score = sum(t.joint_health_contribution for t in first_half) / max(len(first_half), 1)
            second_score = sum(t.joint_health_contribution for t in second_half) / max(len(second_half), 1)
            self._health.convergence_trend = round(second_score - first_score, 4)

        self._health.last_updated = time.time()

        return traj.joint_health_contribution

    def joint_health(self) -> JointHealth:
        """Get current joint health report."""
        return self._health

    def _compute_reward_quality(self) -> float:
        """How well are long-term rewards differentiating good/bad providers?"""
        rewards = list(self._long_term_rewards.values())
        if len(rewards) < 2:
            return 0.5
        avg = sum(rewards) / len(rewards)
        variance = sum((r - avg) ** 2 for r in rewards) / len(rewards)
        # Higher variance = better differentiation = better reward quality
        return min(1.0, math.sqrt(variance) * 3.0)

    def _compute_subgoal_quality(self) -> float:
        """How effective are sub-goals across all providers?"""
        all_rates = [
            sum(v) / max(len(v), 1)
            for v in self._subgoal_success.values()
            if v
        ]
        if not all_rates:
            return 0.5
        return round(sum(all_rates) / len(all_rates), 4)

    @staticmethod
    def _compute_feedback_quality() -> float:
        """B→P feedback: is knowledge being updated?"""
        # Proxy: check if knowledge patterns are accumulating
        try:
            from ..knowledge.context_wiki import get_context_wiki
            wiki = get_context_wiki()
            route_entries = sum(
                1 for k in wiki.keys() if str(k).startswith("route:")
            )
            return min(1.0, route_entries / 20.0)
        except Exception:
            return 0.0

    @staticmethod
    def _compute_loop_efficiency(trajectories: list[EvolutionTrajectory]) -> float:
        """P→C→B→P loop throughput efficiency."""
        if not trajectories:
            return 0.5
        # Efficiency = success rate × (1 / avg latency normalized)
        success_rate = sum(
            1 for t in trajectories if t.overall_success
        ) / len(trajectories)
        avg_latency = sum(
            t.total_latency_ms for t in trajectories
        ) / max(len(trajectories), 1)
        latency_score = max(0.0, 1.0 - avg_latency / 60000.0)  # Normalize to 60s
        return round(success_rate * 0.6 + latency_score * 0.4, 4)

    # ── Trajectory Management ─────────────────────────────────────

    def _get_recent_trajectories(self) -> list[EvolutionTrajectory]:
        """Get recent trajectories within window."""
        completed = sorted(
            [t for t in self._trajectories.values() if t.completed_at > 0],
            key=lambda t: -t.completed_at,
        )
        return completed[:self.WINDOW_SIZE]

    def get_trajectory(self, trajectory_id: str) -> EvolutionTrajectory | None:
        return self._trajectories.get(trajectory_id)

    def _prune(self) -> None:
        """Remove oldest trajectories beyond retention limit."""
        if len(self._trajectories) <= self.WINDOW_SIZE * 3:
            return
        completed = sorted(
            [t for t in self._trajectories.values() if t.completed_at > 0],
            key=lambda t: t.completed_at,
        )
        to_remove = completed[:len(completed) - self.WINDOW_SIZE * 2]
        for t in to_remove:
            self._trajectories.pop(t.trajectory_id, None)

    # ── Persistence ────────────────────────────────────────────────

    def _save_health(self) -> None:
        try:
            TRAJECTORY_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "health": {
                    "score": self._health.score,
                    "p_health": self._health.p_health,
                    "c_health": self._health.c_health,
                    "b_health": self._health.b_health,
                    "loop_efficiency": self._health.loop_efficiency,
                    "total_trajectories": self._health.total_trajectories,
                    "successful_trajectories": self._health.successful_trajectories,
                    "convergence_trend": self._health.convergence_trend,
                    "last_updated": self._health.last_updated,
                },
                "long_term_rewards": self._long_term_rewards,
            }
            HEALTH_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"JointEvolution save: {e}")

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            if HEALTH_FILE.exists():
                data = json.loads(HEALTH_FILE.read_text())
                h = data.get("health", {})
                self._health.score = h.get("score", 0.0)
                self._health.total_trajectories = h.get("total_trajectories", 0)
                self._health.successful_trajectories = h.get("successful_trajectories", 0)
                self._long_term_rewards = data.get("long_term_rewards", {})
                logger.info(
                    f"JointEvolution: loaded health score={self._health.score:.2f}, "
                    f"rewards={len(self._long_term_rewards)} providers"
                )
        except Exception as e:
            logger.debug(f"JointEvolution load: {e}")
        self._loaded = True

    def save(self) -> None:
        self._save_health()

    # ── Statistics ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "joint_health": self._health.score,
            "p_health": self._health.p_health,
            "c_health": self._health.c_health,
            "b_health": self._health.b_health,
            "loop_efficiency": self._health.loop_efficiency,
            "convergence_trend": self._health.convergence_trend,
            "total_trajectories": self._health.total_trajectories,
            "successful_trajectories": self._health.successful_trajectories,
            "active_trajectories": len(self._active_steps),
            "providers_with_rewards": len(self._long_term_rewards),
            "subgoal_tracked_providers": len(self._subgoal_success),
        }


# ═══ Singleton ═════════════════════════════════════════════════════

_je: Optional[JointEvolutionCoordinator] = None
_je_lock = threading.Lock()


def get_joint_evolution() -> JointEvolutionCoordinator:
    global _je
    if _je is None:
        with _je_lock:
            if _je is None:
                _je = JointEvolutionCoordinator()
    return _je


__all__ = [
    "JointEvolutionCoordinator", "EvolutionTrajectory", "EvolutionStep",
    "PerceptionState", "CognitionDecision", "BehaviorResult", "JointHealth",
    "get_joint_evolution",
]
