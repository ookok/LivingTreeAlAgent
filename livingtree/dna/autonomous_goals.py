"""Autonomous Goal Generation — curiosity-driven self-assignment.

Inspired by intrinsic motivation theory (Schmidhuber 1991, Pathak et al. 2017)
and curiosity-driven exploration (Burda et al. 2019): the system discovers what
it needs to learn/do without being told, driven by pattern recognition across
its own operational history.

Core loop:
    Observe patterns → Identify gaps → Generate goal → Self-execute → Report

Five pattern categories trigger goal generation:
    1. Failed-task clustering    — same error type 3+ times
    2. Knowledge gaps             — LLM said "I don't know X"
    3. Efficiency bottlenecks     — stage taking >5s consistently
    4. User feedback              — corrections on same topic
    5. Skill gaps                 — tasks requiring external help

Safety constraints:
    - Never execute destructive goals
    - Max 3 active goals at once
    - Requires idle system state
    - All goals are reversible (no file deletion, no config mutation)

Integration:
    Called after LifeEngine post-cycle hooks when system is idle.
    Reports completions to user via the hub notification channel.

Usage:
    engine = get_autonomous_goals()
    await engine.observe_cycle(ctx)       # after each LifeEngine cycle
    await engine.generate_goals()         # create goals from patterns
    await engine.tick(consciousness, hub) # execute ready goals
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

GOALS_DIR = Path(".livingtree/meta")
GOALS_LOG = GOALS_DIR / "autonomous_goals.json"


# ═══════════════════════════════════════════════════════════════════
# Types
# ═══════════════════════════════════════════════════════════════════

class GoalStatus(str, Enum):
    PENDING = "pending"
    LEARNING = "learning"
    COMPLETED = "completed"
    REPORTED = "reported"
    ABORTED = "aborted"


class PatternCategory(str, Enum):
    FAILED_TASK = "failed_task"
    KNOWLEDGE_GAP = "knowledge_gap"
    EFFICIENCY_BOTTLENECK = "efficiency_bottleneck"
    USER_FEEDBACK = "user_feedback"
    SKILL_GAP = "skill_gap"


@dataclass
class AutonomousGoal:
    """A self-generated learning or improvement objective.

    Attributes:
        id: unique goal identifier (uuid4)
        description: what to achieve (e.g. "learn about BFS graph traversal")
        reason: why this goal was generated, with evidence
        priority: 0-1 score (higher = more urgent/valuable)
        estimated_effort: estimated token cost to complete
        parent_pattern: what observation triggered this goal
        status: current lifecycle phase
        created_at: epoch timestamp of creation
        completed_at: epoch timestamp of completion (0 if not done)
        outcome: summary of what was learned or achieved
        attempts: number of execution attempts so far
        max_attempts: maximum attempts before auto-abort
        reversible: whether the goal involves only read/learn operations
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    description: str = ""
    reason: str = ""
    priority: float = 0.5
    estimated_effort: int = 500
    parent_pattern: str = ""
    status: GoalStatus = GoalStatus.PENDING
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    outcome: str = ""
    attempts: int = 0
    max_attempts: int = 3
    reversible: bool = True

    @property
    def is_destructive(self) -> bool:
        destructive_keywords = ("delete", "remove", "destroy", "wipe", "format",
                                "drop", "truncate", "rm ", "sudo", "chmod 777")
        return any(kw in self.description.lower() for kw in destructive_keywords)

    @property
    def elapsed_seconds(self) -> float:
        if self.completed_at > 0:
            return self.completed_at - self.created_at
        return time.time() - self.created_at


@dataclass
class ObservedPattern:
    """A recurring pattern detected in system behavior.

    Attributes:
        category: what kind of pattern was observed
        signature: a stable hash or key for the pattern (e.g. error type)
        occurrences: how many times observed
        first_seen: epoch of first observation
        last_seen: epoch of most recent observation
        sample: representative example (error message, user message, etc.)
        generated_goal_ids: which goals were already created from this
    """
    category: PatternCategory
    signature: str
    occurrences: int = 1
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    sample: str = ""
    generated_goal_ids: list[str] = field(default_factory=list)


@dataclass
class GoalStats:
    """Aggregated statistics for the AutonomousGoalEngine."""
    total_generated: int = 0
    total_completed: int = 0
    total_aborted: int = 0
    total_reported: int = 0
    active_count: int = 0
    avg_completion_seconds: float = 0.0
    by_category: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    recent_completions: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# PatternObserver — detect recurring patterns worth acting on
# ═══════════════════════════════════════════════════════════════════

class PatternObserver:
    """Detects recurring patterns in system behavior that warrant action.

    Five detection categories:
      1. Failed-task clustering: same error type 3+ times → "learn about X"
      2. Knowledge gaps: LLM said "I don't know X" → "research X"
      3. Efficiency bottlenecks: stage taking >5s consistently → "optimize stage Y"
      4. User feedback: corrections on same topic → "update understanding of Z"
      5. Skill gaps: tasks requiring external help → "develop capability for W"

    Maintains a rolling window of observations and emits ObservedPattern values
    when a pattern crosses the significance threshold.
    """

    FAILED_TASK_THRESHOLD = 3
    KNOWLEDGE_GAP_THRESHOLD = 1
    EFFICIENCY_THRESHOLD_SECONDS = 5.0
    EFFICIENCY_OCCURRENCES = 3
    USER_FEEDBACK_THRESHOLD = 2
    SKILL_GAP_THRESHOLD = 2
    MAX_PATTERNS = 200
    MAX_OBSERVATION_HISTORY = 500

    def __init__(self):
        self._patterns: dict[str, ObservedPattern] = {}
        self._stage_timings: dict[str, list[float]] = defaultdict(list)
        self._error_signatures: dict[str, int] = defaultdict(int)
        self._knowledge_gaps: dict[str, int] = defaultdict(int)
        self._user_corrections: dict[str, int] = defaultdict(int)
        self._skill_gaps: dict[str, int] = defaultdict(int)
        self._stage_durations: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=20)
        )
        self._recent_observations: deque[str] = deque(
            maxlen=self.MAX_OBSERVATION_HISTORY
        )

    # ── Public API ──

    def observe_cycle(self, ctx: Any) -> list[ObservedPattern]:
        """Ingest a completed LifeEngine cycle and return any triggered patterns.

        Args:
            ctx: LifeContext from a completed LifeEngine.run() cycle.

        Returns:
            List of ObservedPattern values that crossed their threshold this cycle.
        """
        triggered: list[ObservedPattern] = []

        triggered.extend(self._detect_failed_tasks(ctx))
        triggered.extend(self._detect_knowledge_gaps(ctx))
        triggered.extend(self._detect_efficiency_bottlenecks(ctx))
        triggered.extend(self._detect_user_feedback(ctx))
        triggered.extend(self._detect_skill_gaps(ctx))

        for pattern in triggered:
            self._upsert_pattern(pattern)

        return triggered

    def observe_stage_timing(self, stage_name: str, duration_seconds: float) -> None:
        """Record a stage duration for efficiency bottleneck detection."""
        self._stage_durations[stage_name].append(duration_seconds)

    def observe_error(self, error_type: str, error_message: str, traceback: str = "") -> None:
        """Record an error for failed-task clustering."""
        sig = self._make_signature("err", error_type)
        self._error_signatures[sig] += 1
        self._recent_observations.append(f"error:{error_type}:{error_message[:120]}")

    def observe_knowledge_gap(self, topic: str, context: str = "") -> None:
        """Record an LLM-declared knowledge gap."""
        sig = self._make_signature("kg", topic)
        self._knowledge_gaps[sig] += 1
        self._recent_observations.append(f"knowledge_gap:{topic}:{context[:80]}")

    def observe_user_feedback(self, topic: str, correction: str = "") -> None:
        """Record a user correction."""
        sig = self._make_signature("uf", topic)
        self._user_corrections[sig] += 1
        self._recent_observations.append(f"user_feedback:{topic}:{correction[:80]}")

    def observe_skill_gap(self, capability: str, context: str = "") -> None:
        """Record a capability gap (task needed help that wasn't available)."""
        sig = self._make_signature("sg", capability)
        self._skill_gaps[sig] += 1
        self._recent_observations.append(f"skill_gap:{capability}:{context[:80]}")

    def get_active_patterns(self) -> list[ObservedPattern]:
        """Return all patterns that have met their significance threshold."""
        return [
            p for p in self._patterns.values()
            if p.occurrences >= self._min_occurrences_for(p.category)
        ]

    def clear_stale(self, max_age_seconds: float = 86400.0) -> int:
        """Remove patterns older than max_age. Returns number removed."""
        now = time.time()
        stale_keys = [
            k for k, p in self._patterns.items()
            if now - p.last_seen > max_age_seconds
        ]
        for k in stale_keys:
            del self._patterns[k]
        if stale_keys:
            logger.debug("PatternObserver: cleared {} stale patterns", len(stale_keys))
        return len(stale_keys)

    # ── Detection methods ──

    def _detect_failed_tasks(self, ctx: Any) -> list[ObservedPattern]:
        results: list[ObservedPattern] = []
        stages = getattr(ctx, 'stages', []) or []
        for stage in stages:
            status = getattr(stage, 'status', '')
            if status == 'failed':
                error_msg = getattr(stage, 'error', '') or getattr(stage, 'output', '') or ''
                error_type = self._classify_error(error_msg)
                sig = self._make_signature("err", error_type)
                self._error_signatures[sig] += 1
                count = self._error_signatures[sig]
                if count >= self.FAILED_TASK_THRESHOLD and sig not in {
                    p.signature for p in self._patterns
                    if p.category == PatternCategory.FAILED_TASK
                }:
                    results.append(ObservedPattern(
                        category=PatternCategory.FAILED_TASK,
                        signature=sig,
                        occurrences=count,
                        sample=error_msg[:300],
                    ))
        return results

    def _detect_knowledge_gaps(self, ctx: Any) -> list[ObservedPattern]:
        results: list[ObservedPattern] = []
        stages = getattr(ctx, 'stages', []) or []
        for stage in stages:
            output = getattr(stage, 'output', '') or ''
            if not output:
                continue
            dont_know_phrases = [
                "I don't know", "I do not know", "I'm not familiar",
                "I am not sure", "I cannot answer", "I can't answer",
                "超出我的知识范围", "我不确定", "我不知道", "我不了解",
            ]
            for phrase in dont_know_phrases:
                if phrase.lower() in output.lower():
                    topic = self._extract_topic_from(output)
                    sig = self._make_signature("kg", topic)
                    self._knowledge_gaps[sig] += 1
                    results.append(ObservedPattern(
                        category=PatternCategory.KNOWLEDGE_GAP,
                        signature=sig,
                        occurrences=self._knowledge_gaps[sig],
                        sample=output[:300],
                    ))
                    break
        return results

    def _detect_efficiency_bottlenecks(self, ctx: Any) -> list[ObservedPattern]:
        results: list[ObservedPattern] = []
        for stage_name, durations in self._stage_durations.items():
            if len(durations) < self.EFFICIENCY_OCCURRENCES:
                continue
            recent = list(durations)[-self.EFFICIENCY_OCCURRENCES:]
            avg = sum(recent) / len(recent)
            if avg > self.EFFICIENCY_THRESHOLD_SECONDS:
                sig = self._make_signature("eff", stage_name)
                existing = self._patterns.get(sig)
                if existing is None:
                    results.append(ObservedPattern(
                        category=PatternCategory.EFFICIENCY_BOTTLENECK,
                        signature=sig,
                        occurrences=len(recent),
                        sample=f"Stage '{stage_name}' avg {avg:.1f}s over {len(recent)} cycles",
                    ))
        return results

    def _detect_user_feedback(self, ctx: Any) -> list[ObservedPattern]:
        results: list[ObservedPattern] = []
        feedback = getattr(ctx, 'metadata', {}) or {}
        user_correction = (
            feedback.get('user_correction', '')
            or feedback.get('correction', '')
        )
        if not user_correction:
            user_input = getattr(ctx, 'user_input', '') or ''
            correction_markers = ("更正", "不对", "应该是", "correction:", "correct:", "wrong:")
            if not any(m in user_input.lower() for m in correction_markers):
                return results
            user_correction = user_input

        topic = self._extract_topic_from(user_correction)
        sig = self._make_signature("uf", topic)
        self._user_corrections[sig] += 1
        count = self._user_corrections[sig]
        if count >= self.USER_FEEDBACK_THRESHOLD:
            results.append(ObservedPattern(
                category=PatternCategory.USER_FEEDBACK,
                signature=sig,
                occurrences=count,
                sample=user_correction[:300],
            ))
        return results

    def _detect_skill_gaps(self, ctx: Any) -> list[ObservedPattern]:
        results: list[ObservedPattern] = []
        stages = getattr(ctx, 'stages', []) or []
        for stage in stages:
            output = getattr(stage, 'output', '') or ''
            if not output:
                continue
            skill_markers = (
                "need external", "requires external", "beyond current capability",
                "not equipped", "missing tool", "needs plugin",
                "需要外部", "无法完成", "缺少工具", "超出能力",
            )
            for marker in skill_markers:
                if marker.lower() in output.lower():
                    capability = self._extract_topic_from(output)
                    sig = self._make_signature("sg", capability)
                    self._skill_gaps[sig] += 1
                    count = self._skill_gaps[sig]
                    if count >= self.SKILL_GAP_THRESHOLD:
                        results.append(ObservedPattern(
                            category=PatternCategory.SKILL_GAP,
                            signature=sig,
                            occurrences=count,
                            sample=output[:300],
                        ))
                    break
        return results

    # ── Helpers ──

    @staticmethod
    def _make_signature(prefix: str, key: str) -> str:
        sanitized = key.strip().lower().replace(" ", "_")[:60]
        return f"{prefix}:{sanitized}"

    @staticmethod
    def _classify_error(error_text: str) -> str:
        error_text_lower = error_text.lower()
        if "timeout" in error_text_lower:
            return "timeout"
        if "connection" in error_text_lower or "http" in error_text_lower:
            return "connection_error"
        if "syntax" in error_text_lower or "parsing" in error_text_lower:
            return "syntax_error"
        if "import" in error_text_lower or "module" in error_text_lower:
            return "import_error"
        if "memory" in error_text_lower or "oom" in error_text_lower:
            return "memory_error"
        if "permission" in error_text_lower or "access" in error_text_lower:
            return "permission_error"
        if "rate" in error_text_lower or "limit" in error_text_lower or "429" in error_text_lower:
            return "rate_limit"
        return "unknown_error"

    @staticmethod
    def _extract_topic_from(text: str) -> str:
        if not text:
            return "unknown"
        words = text.split()
        if len(words) <= 5:
            return text[:80]
        return " ".join(words[:8])[:80]

    def _upsert_pattern(self, pattern: ObservedPattern) -> None:
        key = f"{pattern.category.value}:{pattern.signature}"
        if key in self._patterns:
            existing = self._patterns[key]
            existing.occurrences = pattern.occurrences
            existing.last_seen = time.time()
            existing.sample = pattern.sample or existing.sample
        else:
            self._patterns[key] = pattern
            if len(self._patterns) > self.MAX_PATTERNS:
                oldest = min(self._patterns, key=lambda k: self._patterns[k].last_seen)
                del self._patterns[oldest]

    @staticmethod
    def _min_occurrences_for(category: PatternCategory) -> int:
        mapping = {
            PatternCategory.FAILED_TASK: PatternObserver.FAILED_TASK_THRESHOLD,
            PatternCategory.KNOWLEDGE_GAP: PatternObserver.KNOWLEDGE_GAP_THRESHOLD,
            PatternCategory.EFFICIENCY_BOTTLENECK: PatternObserver.EFFICIENCY_OCCURRENCES,
            PatternCategory.USER_FEEDBACK: PatternObserver.USER_FEEDBACK_THRESHOLD,
            PatternCategory.SKILL_GAP: PatternObserver.SKILL_GAP_THRESHOLD,
        }
        return mapping.get(category, 2)


# ═══════════════════════════════════════════════════════════════════
# AutonomousGoalEngine — full goal lifecycle manager
# ═══════════════════════════════════════════════════════════════════

class AutonomousGoalEngine:
    """Curiosity-driven goal generation and self-execution engine.

    Core loop: Observe patterns → Identify gaps → Generate goal → Self-execute → Report

    Watches system behavior through PatternObserver, converts detected patterns
    into concrete AutonomousGoal values, prioritizes them, executes them (learn,
    research, optimize), and reports completions to the user via hub.

    Safety:
        - Never executes destructive goals (checked via is_destructive property)
        - Max 3 active goals (learning/completed but not yet reported)
        - Requires idle system state (checked via _is_idle)
        - All goals must be reversible by default
    """

    MAX_ACTIVE_GOALS = 3
    MAX_GOAL_HISTORY = 200
    IDLE_THRESHOLD_SECONDS = 30.0
    MIN_CYCLE_INTERVAL_SECONDS = 15.0

    def __init__(self):
        self._observer = PatternObserver()
        self._goals: dict[str, AutonomousGoal] = {}
        self._goal_queue: deque[AutonomousGoal] = deque()
        self._completion_log: deque[str] = deque(maxlen=100)
        self._total_generated = 0
        self._total_completed = 0
        self._total_aborted = 0
        self._total_reported = 0
        self._completion_times: list[float] = []
        self._last_cycle_time: float = 0.0
        self._last_user_activity: float = time.time()
        self._lock = asyncio.Lock()
        self._executing = False

    # ── Public API ──

    async def observe_cycle(self, ctx: Any) -> list[ObservedPattern]:
        """Ingest a LifeEngine cycle result. Must be called after each cycle.

        Args:
            ctx: LifeContext from a completed LifeEngine.run().

        Returns:
            Newly triggered ObservedPattern values.
        """
        async with self._lock:
            self._last_user_activity = time.time()
            triggered = self._observer.observe_cycle(ctx)

            # Also track stage timings from ctx metadata
            timing_data = {}
            if hasattr(ctx, 'metadata'):
                timing_data = ctx.metadata.get('stage_timings', {}) or {}
            stages = getattr(ctx, 'stages', []) or []
            for stage in stages:
                name = getattr(stage, 'name', '')
                if name:
                    duration = timing_data.get(name, 0) or getattr(stage, 'duration', 0) or 0
                    if duration > 0:
                        self._observer.observe_stage_timing(name, duration)

            if triggered:
                logger.debug(
                    "AutonomousGoalEngine: {} pattern(s) triggered in observe_cycle",
                    len(triggered),
                )
            return triggered

    async def observe_error(self, error_type: str, error_message: str,
                            traceback: str = "") -> None:
        """Record an error that occurred outside a full LifeEngine cycle."""
        async with self._lock:
            self._observer.observe_error(error_type, error_message, traceback)

    async def observe_knowledge_gap(self, topic: str, context: str = "") -> None:
        """Record a knowledge gap detected in a conversation response."""
        async with self._lock:
            self._observer.observe_knowledge_gap(topic, context)

    async def observe_user_feedback(self, topic: str, correction: str = "") -> None:
        """Record user feedback/correction for pattern detection."""
        async with self._lock:
            self._observer.observe_user_feedback(topic, correction)

    async def observe_skill_gap(self, capability: str, context: str = "") -> None:
        """Record a skill/capability gap detected during task execution."""
        async with self._lock:
            self._observer.observe_skill_gap(capability, context)

    async def generate_goals(self, max_active: int | None = None) -> list[AutonomousGoal]:
        """Convert observed patterns into prioritized AutonomousGoal values.

        Args:
            max_active: Override default max active goal limit. Uses
                        MAX_ACTIVE_GOALS (3) if None.

        Returns:
            Newly generated AutonomousGoal values.
        """
        if max_active is None:
            max_active = self.MAX_ACTIVE_GOALS

        async with self._lock:
            active_count = sum(
                1 for g in self._goals.values()
                if g.status in (GoalStatus.PENDING, GoalStatus.LEARNING)
            )
            if active_count >= max_active:
                logger.debug("AutonomousGoalEngine: {} active goals, at limit", active_count)
                return []

            patterns = self._observer.get_active_patterns()
            new_goals: list[AutonomousGoal] = []

            for pattern in patterns:
                if len(new_goals) + active_count >= max_active:
                    break

                # Skip patterns that already have an active goal
                if pattern.generated_goal_ids and any(
                    gid in self._goals
                    and self._goals[gid].status in (GoalStatus.PENDING, GoalStatus.LEARNING)
                    for gid in pattern.generated_goal_ids
                ):
                    continue

                goal = self._pattern_to_goal(pattern)
                if goal and not goal.is_destructive:
                    self._goals[goal.id] = goal
                    self._goal_queue.append(goal)
                    self._total_generated += 1
                    pattern.generated_goal_ids.append(goal.id)
                    new_goals.append(goal)
                    logger.info(
                        "AutonomousGoalEngine: generated goal '{}' (priority={:.2f}, from {})",
                        goal.description[:80], goal.priority, pattern.category.value,
                    )

            return new_goals

    async def execute_goal(self, goal: AutonomousGoal, consciousness: Any,
                           hub: Any) -> bool:
        """Self-execute a single goal: research, learn, or optimize.

        Args:
            goal: The AutonomousGoal to execute.
            consciousness: The system consciousness (for LLM access).
            hub: The integration hub (for tool access and notifications).

        Returns:
            True if execution succeeded, False otherwise.
        """
        if goal.is_destructive:
            logger.warning("AutonomousGoalEngine: refusing to execute destructive goal '{}'",
                           goal.description)
            goal.status = GoalStatus.ABORTED
            goal.outcome = "Aborted: destructive operations are not allowed."
            self._total_aborted += 1
            return False

        if goal.attempts >= goal.max_attempts:
            logger.warning("AutonomousGoalEngine: goal '{}' exceeded max attempts",
                           goal.description)
            goal.status = GoalStatus.ABORTED
            goal.outcome = f"Aborted: exceeded {goal.max_attempts} attempts."
            self._total_aborted += 1
            return False

        goal.status = GoalStatus.LEARNING
        goal.attempts += 1
        start_time = time.time()

        try:
            outcome_text = await self._execute_internal(goal, consciousness, hub)
            goal.status = GoalStatus.COMPLETED
            goal.completed_at = time.time()
            goal.outcome = outcome_text
            self._total_completed += 1
            self._completion_times.append(goal.completed_at - goal.created_at)
            self._completion_log.append(
                f"{goal.id}: {goal.description[:100]} (pattern={goal.parent_pattern})"
            )
            logger.success(
                "AutonomousGoalEngine: completed goal '{}' in {:.1f}s",
                goal.description[:60], goal.elapsed_seconds,
            )
            return True
        except Exception as exc:
            elapsed = time.time() - start_time
            logger.error(
                "AutonomousGoalEngine: goal '{}' failed (attempt {}/{}, {:.1f}s): {}",
                goal.description[:60], goal.attempts, goal.max_attempts, elapsed, exc,
            )
            if goal.attempts >= goal.max_attempts:
                goal.status = GoalStatus.ABORTED
                goal.completed_at = time.time()
                goal.outcome = f"Failed after {goal.max_attempts} attempts: {exc}"
                self._total_aborted += 1
            else:
                goal.status = GoalStatus.PENDING
            return False

    async def report_completion(self, goal: AutonomousGoal, hub: Any) -> None:
        """Notify user of an autonomous achievement via hub.

        Formats the goal outcome into a user-friendly message and sends it
        through the hub notification channel.
        """
        if goal.status not in (GoalStatus.COMPLETED, GoalStatus.ABORTED):
            return

        message = self._format_report(goal)
        try:
            if hub and hasattr(hub, 'notify'):
                await hub.notify(
                    channel="autonomous_goals",
                    message=message,
                    metadata={
                        "goal_id": goal.id,
                        "status": goal.status.value,
                        "priority": goal.priority,
                        "category": goal.parent_pattern,
                    },
                )
            goal.status = GoalStatus.REPORTED
            self._total_reported += 1
            logger.info("AutonomousGoalEngine: reported goal '{}'", goal.description[:60])
        except Exception as exc:
            logger.warning("AutonomousGoalEngine: failed to report goal '{}': {}", goal.id, exc)

    async def tick(self, consciousness: Any = None, hub: Any = None) -> list[str]:
        """Main periodic tick: generate goals, execute one, report completions.

        Intended to be called by LifeDaemon or a similar scheduler at regular
        intervals when the system is idle. Only executes if the system has been
        idle long enough and enough time has passed since the last cycle.

        Args:
            consciousness: System consciousness for LLM access.
            hub: Integration hub for tool access and notifications.

        Returns:
            List of goal IDs that changed state during this tick.
        """
        changed_ids: list[str] = []

        if not self._is_idle():
            return changed_ids

        if self._executing:
            return changed_ids

        now = time.time()
        if now - self._last_cycle_time < self.MIN_CYCLE_INTERVAL_SECONDS:
            return changed_ids

        self._executing = True
        try:
            # 1. Generate new goals from accumulated patterns
            new_goals = await self.generate_goals()
            for g in new_goals:
                changed_ids.append(g.id)

            # 2. Execute the highest-priority pending goal
            pending = sorted(
                [g for g in self._goals.values() if g.status == GoalStatus.PENDING],
                key=lambda g: (-g.priority, g.created_at),
            )
            if pending:
                goal = pending[0]
                await self.execute_goal(goal, consciousness, hub)
                changed_ids.append(goal.id)

            # 3. Report completed (but not yet reported) goals
            completed_unreported = [
                g for g in self._goals.values()
                if g.status == GoalStatus.COMPLETED
            ]
            for g in completed_unreported[:3]:
                await self.report_completion(g, hub)
                changed_ids.append(g.id)

            # 4. Clean up stale patterns periodically
            if self._total_generated > 0 and self._total_generated % 10 == 0:
                self._observer.clear_stale()

            self._last_cycle_time = now
        finally:
            self._executing = False

        return changed_ids

    def stats(self) -> GoalStats:
        """Return aggregated statistics for monitoring and dashboards."""
        completed_times = [t for t in self._completion_times if t > 0]
        avg_time = sum(completed_times) / len(completed_times) if completed_times else 0.0

        by_category: dict[str, int] = defaultdict(int)
        for g in self._goals.values():
            by_category[g.parent_pattern] += 1

        return GoalStats(
            total_generated=self._total_generated,
            total_completed=self._total_completed,
            total_aborted=self._total_aborted,
            total_reported=self._total_reported,
            active_count=sum(
                1 for g in self._goals.values()
                if g.status in (GoalStatus.PENDING, GoalStatus.LEARNING)
            ),
            avg_completion_seconds=round(avg_time, 1),
            by_category=dict(by_category),
            recent_completions=list(self._completion_log)[-10:],
        )

    def get_goal(self, goal_id: str) -> AutonomousGoal | None:
        """Retrieve a specific goal by ID."""
        return self._goals.get(goal_id)

    def list_goals(self, status: GoalStatus | None = None) -> list[AutonomousGoal]:
        """List all goals, optionally filtered by status."""
        if status is None:
            return list(self._goals.values())
        return [g for g in self._goals.values() if g.status == status]

    def mark_user_activity(self) -> None:
        """Signal that the user is active — resets idle timer."""
        self._last_user_activity = time.time()

    # ── Persistence ──

    async def save(self) -> None:
        """Persist goals and patterns to disk."""
        GOALS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            data = {
                "goals": {
                    gid: {
                        "id": g.id,
                        "description": g.description,
                        "reason": g.reason,
                        "priority": g.priority,
                        "estimated_effort": g.estimated_effort,
                        "parent_pattern": g.parent_pattern,
                        "status": g.status.value,
                        "created_at": g.created_at,
                        "completed_at": g.completed_at,
                        "outcome": g.outcome,
                        "attempts": g.attempts,
                        "max_attempts": g.max_attempts,
                    }
                    for gid, g in self._goals.items()
                    if g.status != GoalStatus.REPORTED
                },
                "total_generated": self._total_generated,
                "total_completed": self._total_completed,
                "total_aborted": self._total_aborted,
                "total_reported": self._total_reported,
                "completion_log": list(self._completion_log),
            }
            GOALS_LOG.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
            logger.debug("AutonomousGoalEngine: saved {} goals to disk", len(data["goals"]))
        except Exception as exc:
            logger.warning("AutonomousGoalEngine: save failed: {}", exc)

    async def load(self) -> None:
        """Restore goals and stats from disk."""
        if not GOALS_LOG.exists():
            return
        try:
            data = json.loads(GOALS_LOG.read_text(encoding="utf-8"))
            self._total_generated = data.get("total_generated", 0)
            self._total_completed = data.get("total_completed", 0)
            self._total_aborted = data.get("total_aborted", 0)
            self._total_reported = data.get("total_reported", 0)
            self._completion_log = deque(
                data.get("completion_log", []), maxlen=100
            )

            goals_data = data.get("goals", {})
            for gid, gd in goals_data.items():
                goal = AutonomousGoal(
                    id=gd.get("id", gid),
                    description=gd.get("description", ""),
                    reason=gd.get("reason", ""),
                    priority=gd.get("priority", 0.5),
                    estimated_effort=gd.get("estimated_effort", 500),
                    parent_pattern=gd.get("parent_pattern", ""),
                    status=GoalStatus(gd.get("status", "pending")),
                    created_at=gd.get("created_at", time.time()),
                    completed_at=gd.get("completed_at", 0.0),
                    outcome=gd.get("outcome", ""),
                    attempts=gd.get("attempts", 0),
                    max_attempts=gd.get("max_attempts", 3),
                )
                if goal.status != GoalStatus.REPORTED:
                    self._goals[goal.id] = goal

            logger.info(
                "AutonomousGoalEngine: loaded {} goals (generated={}, completed={})",
                len(self._goals), self._total_generated, self._total_completed,
            )
        except Exception as exc:
            logger.warning("AutonomousGoalEngine: load failed: {}", exc)

    # ── Internal methods ──

    def _is_idle(self) -> bool:
        elapsed = time.time() - self._last_user_activity
        return elapsed > self.IDLE_THRESHOLD_SECONDS

    def _pattern_to_goal(self, pattern: ObservedPattern) -> AutonomousGoal | None:
        """Convert an ObservedPattern into a concrete AutonomousGoal.

        Maps each pattern category to an appropriate goal description, priority,
        and estimated effort. Returns None if no meaningful goal can be derived.
        """
        if pattern.category == PatternCategory.FAILED_TASK:
            error_type = pattern.signature.split(":", 1)[1] if ":" in pattern.signature else pattern.signature
            return AutonomousGoal(
                description=f"Learn about handling {error_type} errors",
                reason=f"Same error type '{error_type}' failed {pattern.occurrences}+ times. "
                       f"Latest: {pattern.sample[:100]}",
                priority=min(0.7 + pattern.occurrences * 0.05, 1.0),
                estimated_effort=600,
                parent_pattern=pattern.category.value,
                reversible=True,
            )

        elif pattern.category == PatternCategory.KNOWLEDGE_GAP:
            topic = pattern.signature.split(":", 1)[1] if ":" in pattern.signature else pattern.signature
            return AutonomousGoal(
                description=f"Research and understand {topic}",
                reason=f"LLM indicated lack of knowledge about '{topic}'. "
                       f"Context: {pattern.sample[:120]}",
                priority=0.65,
                estimated_effort=800,
                parent_pattern=pattern.category.value,
                reversible=True,
            )

        elif pattern.category == PatternCategory.EFFICIENCY_BOTTLENECK:
            stage_name = pattern.signature.split(":", 1)[1] if ":" in pattern.signature else pattern.signature
            return AutonomousGoal(
                description=f"Optimize {stage_name} stage performance",
                reason=f"Stage '{stage_name}' consistently exceeds threshold. {pattern.sample}",
                priority=0.55,
                estimated_effort=1000,
                parent_pattern=pattern.category.value,
                reversible=True,
            )

        elif pattern.category == PatternCategory.USER_FEEDBACK:
            topic = pattern.signature.split(":", 1)[1] if ":" in pattern.signature else pattern.signature
            return AutonomousGoal(
                description=f"Update understanding of {topic} based on user feedback",
                reason=f"User provided corrections on '{topic}' {pattern.occurrences}+ times. "
                       f"Latest: {pattern.sample[:120]}",
                priority=0.75,
                estimated_effort=500,
                parent_pattern=pattern.category.value,
                reversible=True,
            )

        elif pattern.category == PatternCategory.SKILL_GAP:
            capability = pattern.signature.split(":", 1)[1] if ":" in pattern.signature else pattern.signature
            return AutonomousGoal(
                description=f"Develop capability for {capability}",
                reason=f"Tasks requiring '{capability}' failed due to missing tools. "
                       f"Sample: {pattern.sample[:120]}",
                priority=0.6,
                estimated_effort=1200,
                parent_pattern=pattern.category.value,
                reversible=True,
            )

        return None

    async def _execute_internal(self, goal: AutonomousGoal, consciousness: Any,
                                hub: Any) -> str:
        """Execute the goal by performing the appropriate action.

        Different goal types trigger different execution strategies:
          - knowledge_gap / failed_task → research via LLM and store in KB
          - efficiency_bottleneck → profiling and optimization suggestions
          - user_feedback → update internal knowledge/corrections
          - skill_gap → check skill hub for available plugins

        Args:
            goal: The goal to execute.
            consciousness: Consciousness instance with LLM access.
            hub: Integration hub with tool registry and KB access.

        Returns:
            Outcome text summarizing what was achieved.
        """
        research_prompt = self._build_research_prompt(goal)

        # Try to query LLM for research/learning
        llm_response = ""
        if consciousness and hasattr(consciousness, 'query'):
            try:
                llm_response = await consciousness.query(
                    prompt=research_prompt,
                    temperature=0.3,
                    max_tokens=min(goal.estimated_effort, 2000),
                )
            except Exception as exc:
                logger.warning("AutonomousGoalEngine: LLM query failed for goal '{}': {}",
                               goal.id, exc)
                llm_response = f"LLM unavailable: {exc}"

        # Store result in knowledge base if available
        stored = False
        if hub and hasattr(hub, 'knowledge_base') and llm_response:
            try:
                from ..knowledge.knowledge_base import Document
                doc = Document(
                    title=f"auto_learned:{goal.parent_pattern}:{goal.id}",
                    content=llm_response,
                    domain=goal.parent_pattern,
                    source="autonomous_goals",
                    metadata={
                        "goal_id": goal.id,
                        "priority": goal.priority,
                        "reason": goal.reason,
                    },
                )
                hub.knowledge_base.add_knowledge(doc)
                stored = True
            except Exception as exc:
                logger.debug("AutonomousGoalEngine: KB storage failed: {}", exc)

        if llm_response:
            stored_note = " and stored in KB" if stored else ""
            return (
                f"Researched '{goal.description}' successfully{stored_note}. "
                f"Key findings: {llm_response[:300]}"
            )

        if stored:
            return f"Stored context for '{goal.description}' in KB."

        return (
            f"Attempted to research '{goal.description}' but could not query LLM "
            f"or store results."
        )

    def _build_research_prompt(self, goal: AutonomousGoal) -> str:
        """Build a concise research prompt for the LLM based on the goal."""
        prompts: dict[str, str] = {
            PatternCategory.FAILED_TASK.value: (
                f"Provide a concise explanation of common causes and solutions for "
                f"the error type related to: {goal.description}. "
                f"Context: {goal.reason}. Format: brief bullet points."
            ),
            PatternCategory.KNOWLEDGE_GAP.value: (
                f"Provide a concise educational summary about: {goal.description}. "
                f"Context: {goal.reason}. Include key concepts, methods, and 3 "
                f"practical takeaways. Keep under {goal.estimated_effort} tokens."
            ),
            PatternCategory.EFFICIENCY_BOTTLENECK.value: (
                f"Analyze potential performance bottlenecks and optimization "
                f"strategies for: {goal.description}. "
                f"Context: {goal.reason}. Suggest 3-5 actionable improvements."
            ),
            PatternCategory.USER_FEEDBACK.value: (
                f"Analyze user feedback context: {goal.reason}. "
                f"How should the system update its understanding to incorporate "
                f"these corrections? Provide updated knowledge summary."
            ),
            PatternCategory.SKILL_GAP.value: (
                f"Research how to implement or acquire capability for: {goal.description}. "
                f"Context: {goal.reason}. What tools, APIs, or approaches exist? "
                f"Provide a practical implementation plan."
            ),
        }
        return prompts.get(goal.parent_pattern, goal.reason)

    def _format_report(self, goal: AutonomousGoal) -> str:
        """Format a goal completion as a user-friendly report message."""
        elapsed = ""
        if goal.completed_at > 0:
            secs = goal.completed_at - goal.created_at
            if secs < 60:
                elapsed = f" ({secs:.0f}s)"
            else:
                elapsed = f" ({secs / 60:.1f}m)"

        icon = "✓" if goal.status == GoalStatus.COMPLETED else "✗"
        return (
            f"{icon} Autonomous goal {goal.status.value}: {goal.description}{elapsed}\n"
            f"   Reason: {goal.reason[:200]}\n"
            f"   Outcome: {goal.outcome[:300]}"
        )


# ═══════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════

_goals_engine: AutonomousGoalEngine | None = None


def get_autonomous_goals() -> AutonomousGoalEngine:
    """Get or create the global AutonomousGoalEngine singleton.

    The engine is lazily created on first call and shared across all
    components. Call after LifeEngine post-cycle hooks when the system
    is idle to trigger autonomous goal generation and execution.

    Returns:
        The global AutonomousGoalEngine instance.
    """
    global _goals_engine
    if _goals_engine is None:
        _goals_engine = AutonomousGoalEngine()
        logger.info("AutonomousGoalEngine singleton created")
    return _goals_engine


__all__ = [
    "AutonomousGoal",
    "GoalStatus",
    "PatternCategory",
    "ObservedPattern",
    "GoalStats",
    "PatternObserver",
    "AutonomousGoalEngine",
    "get_autonomous_goals",
]
