"""react_executor.py — ReAct (Reasoning + Acting) interleaved execution loop.

Implements the Think-Act-Observe pattern from ReAct (Yao et al., 2022):
  Think: consciousness.chain_of_thought(task + history)
  Act:   execute one tool/action
  Observe: parse result, decide next step or FINAL_ANSWER

Complements DAGExecutor (parallel batch pipeline) with serial interleaving
for exploratory tasks where each action depends on the previous observation.

Routing: ForesightGate decides ReactExecutor vs DAGExecutor based on
task determinism (high certainty → DAG, exploratory → ReAct).

Reflexion (Shinn et al., 2023): After loop ends, reflect on full trajectory
and inject lessons into EvolutionStore for future improvement.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from loguru import logger


# ── ReAct Loop Types ──

class ReactAction(str, Enum):
    """Types of actions the ReAct agent can take."""
    THINK = "think"         # Internal reasoning / plan adjustment
    TOOL_CALL = "tool_call"  # Execute a tool (file read, web search, code exec, etc.)
    OBSERVE = "observe"     # Parse tool result, extract insights
    FINAL_ANSWER = "final_answer"  # Task complete, return result
    ASK_CLARIFY = "ask_clarify"    # Need human input before continuing


@dataclass
class ReactStep:
    """One complete Think-Act-Observe cycle."""
    iteration: int
    thought: str                    # What the agent reasoned
    action: str                     # The action performed (tool name or description)
    action_input: str               # Input to the action
    observation: str                # Result of the action
    confidence: float = 0.0         # Agent's confidence in this step
    latency_ms: float = 0.0
    tokens_used: int = 0
    error: str = ""


@dataclass
class ReactTrajectory:
    """Full ReAct execution trajectory for reflection."""
    task: str
    steps: list[ReactStep] = field(default_factory=list)
    final_answer: str = ""
    total_iterations: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    success: bool = False
    stopped_reason: str = ""        # "final_answer", "max_iterations", "error", "timeout"

    def to_reflection_text(self) -> str:
        if not self.steps:
            return f"Task '{self.task[:80]}': no steps executed."
        parts = [f"ReAct Trajectory for: {self.task[:120]}"]
        parts.append(f"Iterations: {len(self.steps)}, Success: {self.success}")
        for s in self.steps:
            status = "✓" if not s.error else "✗"
            parts.append(f"  {status} Step {s.iteration}: {s.action} → {s.observation[:80]}")
        if self.final_answer:
            parts.append(f"Answer: {self.final_answer[:200]}")
        return "\n".join(parts)

    def extract_lessons(self) -> list[str]:
        """Extract learnable lessons from this trajectory (Reflexion pattern)."""
        lessons = []
        for s in self.steps:
            if s.error:
                lessons.append(f"Avoid {s.action} on error: {s.error[:100]}")
            if s.confidence < 0.3 and s.iteration > 1:
                lessons.append(f"Low confidence at step {s.iteration}: {s.action}")
        if self.success and len(self.steps) == 1:
            lessons.append(f"Fast resolution: {self.steps[0].action}")
        if not self.success and self.stopped_reason == "max_iterations":
            lessons.append(f"Task '{self.task[:60]}' needs decomposition or human help")
        return lessons


# ── ReAct Prompt Template ──

REACT_SYSTEM_PROMPT = """You are a ReAct agent that solves tasks by interleaving thought, action, and observation.

Available actions:
- tool_call(tool_name, input): Execute a tool (read_file, search_code, web_search, run_command, etc.)
- ask_clarify(question): Ask the user for clarification before proceeding
- final_answer(response): Task is complete, return the answer

For each step, output exactly in this format:

Thought: <your reasoning about what to do next and why>
Action: tool_call(<tool_name>, <input>)  OR  Action: final_answer(<response>)  OR  Action: ask_clarify(<question>)

Rules:
1. Always think BEFORE acting — explain your reasoning in the "Thought" line
2. After each action, consider the observation and think again
3. If the observation reveals new information, adjust your plan
4. If you're uncertain, say so — don't guess
5. Stop with final_answer when the task is complete, or max_iterations is reached

Task: {task}"""

OBSERVATION_PROMPT = """Observation: {result}

Based on this observation, what is your next thought and action?
Continue with the exact format: Thought: ... Action: ..."""


# ── ReactExecutor ──

@dataclass
class ReactConfig:
    """Configuration for ReactExecutor behavior."""
    max_iterations: int = 10         # Safety ceiling
    max_tokens_per_iteration: int = 4096
    timeout_seconds: float = 120.0
    confidence_threshold: float = 0.3  # Below this, reconsider step
    enable_reflexion: bool = True     # Extract lessons after completion
    temperature: float = 0.5


class ReactExecutor:
    """Serial Think-Act-Observe loop for exploratory tasks.

    Complements DAGExecutor (parallel batch). Use when the task
    requires step-by-step reasoning with feedback adaptation.

    Usage:
        executor = ReactExecutor(consciousness)
        result = await executor.run(
            task="Debug the null pointer in auth.py",
            tools={"read_file": read_file_fn, "search_code": search_fn},
        )
    """

    def __init__(self, consciousness: Any = None):
        self._consciousness = consciousness
        self.config = ReactConfig()
        self._total_trajectories: list[ReactTrajectory] = []

    async def run(
        self,
        task: str,
        tools: Optional[dict[str, Callable[..., Coroutine]]] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> ReactTrajectory:
        """Execute a task via interleaved Think-Act-Observe.

        Args:
            task: Natural language task description
            tools: Dict of tool_name → async callable
            context: Additional context (knowledge, memory, etc.)

        Returns:
            ReactTrajectory with full step history and result
        """
        tools = tools or {}
        context = context or {}

        trajectory = ReactTrajectory(task=task)
        history: list[str] = []
        start_time = time.monotonic()

        # Build initial prompt with task + context
        knowledge = context.get("knowledge", "")
        kb_block = f"\nRelevant knowledge:\n{knowledge[:2000]}" if knowledge else ""
        current_prompt = REACT_SYSTEM_PROMPT.format(task=task) + kb_block

        for iteration in range(1, self.config.max_iterations + 1):
            if time.monotonic() - start_time > self.config.timeout_seconds:
                trajectory.stopped_reason = "timeout"
                break

            # ── THINK + ACT ──
            thought, action, action_input = await self._think_act(
                current_prompt, history, iteration)
            if not thought:
                trajectory.stopped_reason = "error"
                break

            # Check for final_answer
            if action == ReactAction.FINAL_ANSWER:
                trajectory.final_answer = action_input
                trajectory.success = True
                trajectory.stopped_reason = "final_answer"
                step = ReactStep(
                    iteration=iteration, thought=thought,
                    action="final_answer", action_input=action_input,
                    observation="Task complete.", confidence=1.0,
                )
                trajectory.steps.append(step)
                break

            # Check for clarification request
            if action == ReactAction.ASK_CLARIFY:
                step = ReactStep(
                    iteration=iteration, thought=thought,
                    action="ask_clarify", action_input=action_input,
                    observation=f"Clarification needed: {action_input}", confidence=0.5,
                )
                trajectory.steps.append(step)
                trajectory.stopped_reason = "ask_clarify"
                break

            # ── ACT: execute tool ──
            step_start = time.monotonic()
            observation, error = await self._execute_action(
                action, action_input, tools)
            step_latency = (time.monotonic() - step_start) * 1000

            # ── OBSERVE: parse and update ──
            confidence = self._estimate_confidence(observation, error)
            step = ReactStep(
                iteration=iteration, thought=thought,
                action=f"tool_call({action})", action_input=action_input,
                observation=observation or error or "", confidence=confidence,
                latency_ms=step_latency, error=error,
            )
            trajectory.steps.append(step)

            if error and iteration >= 3:
                # Three consecutive failures → abort
                recent_errors = sum(1 for s in trajectory.steps[-3:] if s.error)
                if recent_errors >= 2:
                    trajectory.stopped_reason = "error"
                    break

            # Feed observation into next iteration
            history.append(f"Step {iteration}: {thought}")
            history.append(f"Action: {action}({action_input[:100]})")
            history.append(f"Observation: {observation[:500]}")
            current_prompt = OBSERVATION_PROMPT.format(result=observation[:2000])

        # Post-loop: compute trajectory stats
        trajectory.total_iterations = len(trajectory.steps)
        trajectory.total_tokens = sum(s.tokens_used for s in trajectory.steps)
        trajectory.total_latency_ms = sum(s.latency_ms for s in trajectory.steps)

        if not trajectory.stopped_reason:
            trajectory.stopped_reason = "max_iterations"

        self._total_trajectories.append(trajectory)

        # ── Reflexion: extract lessons ──
        if self.config.enable_reflexion and hasattr(self, 'on_trajectory_complete'):
            await self.on_trajectory_complete(trajectory)

        return trajectory

    async def _think_act(
        self, prompt: str, history: list[str], iteration: int,
    ) -> tuple[str, ReactAction, str]:
        """Think phase: call LLM to decide next action."""
        if self._consciousness is None:
            return "", ReactAction.FINAL_ANSWER, "No consciousness available"

        # Truncate history to fit context window
        hist_block = "\n".join(history[-10:]) if history else "(start)"
        full_prompt = f"{prompt}\n\nHistory:\n{hist_block}"

        try:
            response = await self._consciousness.chain_of_thought(
                full_prompt, temperature=self.config.temperature,
                max_tokens=self.config.max_tokens_per_iteration,
            )
        except Exception as e:
            logger.warning(f"ReAct think failed: {e}")
            return "Error in reasoning", ReactAction.FINAL_ANSWER, str(e)

        return self._parse_action(response)

    @staticmethod
    def _parse_action(response: str) -> tuple[str, ReactAction, str]:
        """Parse Thought and Action from LLM response."""
        # Extract Thought
        thought_match = re.search(
            r'Thought:\s*(.+?)(?=\n(?:Action|Observation):|\Z)',
            response, re.DOTALL | re.IGNORECASE)
        thought = thought_match.group(1).strip() if thought_match else response[:200]

        # Extract Action
        action_match = re.search(
            r'Action:\s*(\w+)\((.+?)\)',
            response, re.IGNORECASE)

        if not action_match:
            # Fallback: try to detect final answer pattern
            if any(kw in response.lower() for kw in
                   ['final answer', 'the answer is', 'in conclusion']):
                return thought, ReactAction.FINAL_ANSWER, response[:1000]
            # Fallback: treat as thought-only
            return thought, ReactAction.THINK, "re-evaluating"

        action_type = action_match.group(1).strip().lower()
        action_input = action_match.group(2).strip()

        # Map to ReactAction enum
        if action_type in ('final_answer', 'finalanswer', 'answer'):
            return thought, ReactAction.FINAL_ANSWER, action_input
        elif action_type in ('ask_clarify', 'askclarify', 'clarify', 'question'):
            return thought, ReactAction.ASK_CLARIFY, action_input
        else:
            return thought, ReactAction.TOOL_CALL, action_input

    @staticmethod
    async def _execute_action(
        action: str, action_input: str, tools: dict[str, Callable],
    ) -> tuple[str, str]:
        """Execute a tool action and return observation + error."""
        if action not in tools:
            return "", f"Unknown tool: {action}"

        try:
            # Try calling the tool with input
            result = await tools[action](action_input)
            observation = str(result)[:2000]
            return observation, ""
        except Exception as e:
            return "", f"Tool {action} failed: {str(e)[:200]}"

    @staticmethod
    def _estimate_confidence(observation: str, error: str) -> float:
        """Lightweight confidence estimation from observation quality."""
        if error:
            return 0.1

        score = 0.5  # neutral baseline

        # Positive signals
        if len(observation) > 100:
            score += 0.2
        if any(kw in observation.lower() for kw in ['success', 'completed', 'found', 'result']):
            score += 0.15

        # Negative signals
        if any(kw in observation.lower() for kw in ['error', 'failed', 'not found', 'empty']):
            score -= 0.3
        if len(observation) < 10:
            score -= 0.2

        return max(0.0, min(1.0, score))

    async def on_trajectory_complete(self, trajectory: ReactTrajectory) -> None:
        """Hook for post-execution processing (Reflexion, evolution, etc.)."""
        lessons = trajectory.extract_lessons()
        if lessons:
            logger.info(f"ReAct Reflexion: {len(lessons)} lessons from '{trajectory.task[:60]}'")
            for lesson in lessons:
                logger.debug(f"  → {lesson}")

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics across all trajectories."""
        if not self._total_trajectories:
            return {"trajectories": 0}
        trajs = self._total_trajectories
        return {
            "trajectories": len(trajs),
            "success_rate": round(sum(1 for t in trajs if t.success) / len(trajs), 3),
            "avg_iterations": round(sum(t.total_iterations for t in trajs) / len(trajs), 1),
            "avg_tokens": round(sum(t.total_tokens for t in trajs) / len(trajs)),
            "avg_latency_ms": round(sum(t.total_latency_ms for t in trajs) / len(trajs)),
            "common_actions": self._common_actions(trajs),
        }

    @staticmethod
    def _common_actions(trajectories: list[ReactTrajectory]) -> list[str]:
        counts: dict[str, int] = {}
        for t in trajectories:
            for s in t.steps:
                key = s.action
                counts[key] = counts.get(key, 0) + 1
        return [a for a, _ in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]]


# ── Dual-Mode Router ──

class ExecutionMode(str, Enum):
    DAG = "dag"       # Parallel batch pipeline (Plan-then-Execute)
    REACT = "react"   # Serial interleaved (Think-Act-Observe)
    HYBRID = "hybrid" # DAG for deterministic subtasks, ReAct for exploratory


async def route_execution(
    task: str,
    plan: list[dict],
    consciousness: Any,
    foresight_gate: Any = None,
) -> ExecutionMode:
    """Route task to appropriate execution mode based on determinism.

    Uses ForesightGate to assess task nature:
    - High confidence (>0.7) + simple plan → DAG (parallel batch)
    - Low confidence (<0.5) or exploratory → REACT (interleaved)
    - Everything else → HYBRID (DAG main + ReAct on ambiguous steps)

    Args:
        task: Natural language task
        plan: Decomposed task plan
        consciousness: LLM interface
        foresight_gate: Optional CoherenceGate for decision

    Returns:
        Recommended ExecutionMode
    """
    if not foresight_gate:
        # Simple heuristic: if plan has >3 independent steps, use DAG
        return ExecutionMode.DAG if len(plan) > 3 else ExecutionMode.REACT

    try:
        decision = foresight_gate.gate(
            task=task,
            context={"plan_length": len(plan), "has_subtasks": len(plan) > 1},
            history=[],
        )
    except Exception:
        # Fallback if gate doesn't have gate() method (legacy assess)
        try:
            decision = foresight_gate.assess(task, "general", [], "low")
        except Exception:
            return ExecutionMode.DAG if len(plan) > 3 else ExecutionMode.REACT

    confidence = getattr(decision, 'confidence', 0.5)
    state = getattr(decision, 'state', None)

    if state and hasattr(state, 'value'):
        state_val = state.value
    else:
        state_val = "accept"

    # Routing logic
    if state_val == "reject":
        return ExecutionMode.REACT  # Don't DAG on rejected — think step by step
    if state_val == "recalibrate":
        return ExecutionMode.REACT  # Need more info — ReAct observes and adapts
    if confidence > 0.7 and len(plan) > 2:
        return ExecutionMode.DAG   # High certainty, batchable
    if confidence < 0.5:
        return ExecutionMode.REACT  # Low confidence → observe after each step

    return ExecutionMode.HYBRID


# Singleton
_REACT_EXECUTOR: Optional[ReactExecutor] = None


def get_react_executor(consciousness: Any = None) -> ReactExecutor:
    global _REACT_EXECUTOR
    if _REACT_EXECUTOR is None:
        _REACT_EXECUTOR = ReactExecutor(consciousness)
    elif consciousness is not None and _REACT_EXECUTOR._consciousness is None:
        _REACT_EXECUTOR._consciousness = consciousness
    return _REACT_EXECUTOR
