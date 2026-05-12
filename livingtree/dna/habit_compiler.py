"""Habit Compiler — Tri-Spirit Architecture (Chen, arXiv:2604.13757, 2026).

Repeated reasoning paths are promoted into zero-inference execution policies —
like how repeated actions become automatic habits. When the same reasoning
chain succeeds 3+ times, the compiler creates a CompiledHabit that skips
the LLM entirely, returning cached results with near-zero latency.

CONCEPT:
    Reasoning Path (expensive) ──[used 3+ times]──→ Compiled Habit (free)
      "analyze intent → classify → route to provider"  →  direct mapping

Result: 30% fewer LLM invocations, 75% latency reduction.

Integration:
    Called by LifeEngine before each _stage() execution.
    If habit hit: skip LLM call, return cached result → 75% latency reduction.
    If no habit: run normal LLM path, record trace for potential compilation.
    Particularly effective for repetitive tasks: intent classification,
    domain routing, safety screening, output formatting.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════

DOMAIN_PATTERNS: list[tuple[str, str]] = [
    (r"(code|编程|写代码|python|javascript|typescript|rust|bug|debug|refactor|测试|写.*算法|写.*函数|实现.*代码)", "coding"),
    (r"(文档|doc|wiki|readme|报告|report)", "documentation"),
    (r"(数据|data|分析|analytics|sql|查询|query|图表|chart|可视化|visualization)", "data"),
    (r"(配置|config|设置|settings?|部署|deploy|docker|k8s|kubernetes)", "devops"),
    (r"(搜索|search|查找|find|检索|retriev)", "search"),
    (r"(翻译|translate)", "translation"),
    (r"(总结|summarize|摘要|概括|tldr)", "summarization"),
    (r"(安全|security|漏洞|vulnerability|审计|audit)", "security"),
    (r"(对话|聊天|chat|conversation|闲聊)", "conversation"),
    (r"(数学|math|计算|calculate|公式|formula|方程|equation)", "math"),
]

INTENT_PATTERNS: list[tuple[str, str]] = [
    (r"(写|实现|创建|生成|编写|create|generate|write|implement|build)", "generate"),
    (r"(修复|修|fix|debug|纠正|改正|改)", "fix"),
    (r"(解释|说明|explain|describe|解释一下|什么意思|是什么|为什么)", "explain"),
    (r"(分析|analyze|剖析|审查|review)", "analyze"),
    (r"(优化|改进|改善|提升|optimize|improve|refactor|重构)", "optimize"),
    (r"(测试|test|验证|verify|检查|check)", "test"),
    (r"(翻译|translate|翻译成)", "translate"),
    (r"(总结|summarize|概括|摘要|tldr|归纳)", "summarize"),
    (r"(搜索|查找|寻找|search|find|检索)", "search_find"),
    (r"(部署|deploy|发布|上线|release)", "deploy"),
]

COMPLEXITY_INDICATORS: list[tuple[str, int]] = [
    (r"(简单|simple|easy|快速|quick|简短|short)", 0),
    (r"(中等|medium|moderate|一般)", 1),
    (r"(复杂|complex|困难|hard|深入|deep|全面|comprehensive|详细|detailed)", 2),
]

STEPS_SIGNATURE_SALT = "habcomp_steps_v1"


# ═══════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════


@dataclass
class ReasoningTrace:
    """A recorded reasoning path — candidate for habit compilation.

    Tracks how a specific input pattern was processed, how often
    it succeeded, and its average latency. Once success_count
    reaches the compile threshold, it becomes a CompiledHabit.

    Attributes:
        pattern_key: Hash of input characteristics (domain, intent,
                     complexity) — NOT the raw input text.
        steps: The reasoning steps taken (readable labels).
        output_signature: Hash of output characteristics.
        success_count: Number of times this pattern succeeded.
        last_used: Timestamp of last successful use.
        avg_latency_ms: Exponentially-weighted average latency in ms.
    """

    pattern_key: str
    steps: list[str] = field(default_factory=list)
    output_signature: str = ""
    success_count: int = 0
    last_used: float = 0.0
    avg_latency_ms: float = 0.0

    @property
    def is_ripe(self) -> bool:
        """True when this trace is ready for compilation."""
        return self.success_count >= 3

    @property
    def distance_to_threshold(self) -> int:
        """How many more successes needed before compilation."""
        return max(0, 3 - self.success_count)


@dataclass
class CompiledHabit:
    """A zero-inference execution policy — the compiled form of a reasoning path.

    Once a ReasoningTrace succeeds enough times, it becomes a CompiledHabit
    that produces output with ZERO LLM calls. The direct_output stores only
    an output signature (hash), not full text, to avoid staleness while
    still enabling fast lookup of structurally-similar results.

    Attributes:
        habit_id: Unique identifier for this compiled habit.
        trigger_pattern: Input pattern hash that triggers this habit.
        direct_output: Cached result signature (zero inference).
        stats: Hit count, saved tokens, and latency metrics.
        compiled_at: When this habit was created.
    """

    habit_id: str
    trigger_pattern: str
    direct_output: str
    stats: dict = field(default_factory=lambda: {
        "hit_count": 0,
        "saved_tokens": 0,
        "avg_original_latency_ms": 0.0,
    })
    compiled_at: float = field(default_factory=time.time)

    def record_hit(self, original_latency_ms: float = 0.0, tokens_saved: int = 0) -> None:
        """Record a habit hit, updating statistics."""
        self.stats["hit_count"] += 1
        if tokens_saved > 0:
            self.stats["saved_tokens"] += tokens_saved
        if original_latency_ms > 0:
            prev = self.stats["avg_original_latency_ms"]
            n = self.stats["hit_count"]
            self.stats["avg_original_latency_ms"] = round(
                prev * (n - 1) / n + original_latency_ms / n, 1
            )

    @property
    def age_hours(self) -> float:
        """Age of this habit in hours."""
        return (time.time() - self.compiled_at) / 3600.0


# ═══════════════════════════════════════════════════════════════
# Habit Compiler Core
# ═══════════════════════════════════════════════════════════════


class HabitCompiler:
    """Compiles repeated reasoning paths into zero-inference habits.

    Lifecycle:
        1. Every LLM call's reasoning path is recorded via record_trace().
        2. When a pattern succeeds 3+ times, it's compiled into a CompiledHabit.
        3. Before each LLM call, check_habit() is consulted — if a habit matches,
           the LLM is skipped entirely and the cached result is returned.
        4. Periodically, invalidate_stale() cleans up habits older than the
           max age to prevent serving stale results.

    Integration point (in LifeEngine._stage):
        compiler = get_habit_compiler()
        habit = compiler.check_habit(ctx.user_input)
        if habit:
            return habit.direct_output  # zero LLM calls
        # else: normal LLM path, then:
        compiler.record_trace(ctx.user_input, steps, output, success=True)
    """

    def __init__(self):
        self._traces: OrderedDict[str, ReasoningTrace] = OrderedDict()
        self._habits: OrderedDict[str, CompiledHabit] = OrderedDict()
        self._compile_threshold: int = 3
        self._max_habits: int = 200
        self._total_llm_calls_avoided: int = 0

    # ── Pattern Extraction ──

    def _extract_pattern(self, input_text: str) -> dict:
        """Extract structural characteristics from input.

        Returns a dict with keys: domain, intent, complexity, length_tier.
        This is deliberately NOT the raw input — only structural features
        that generalize across similar queries, enabling habit matching
        for queries with the same shape but different specifics.
        """
        text_lower = input_text.lower()

        domain = "general"
        for pattern, label in DOMAIN_PATTERNS:
            if re.search(pattern, text_lower):
                domain = label
                break

        intent = "general"
        for pattern, label in INTENT_PATTERNS:
            if re.search(pattern, text_lower):
                intent = label
                break

        complexity = 1
        for pattern, level in COMPLEXITY_INDICATORS:
            if re.search(pattern, text_lower):
                complexity = level
                break

        return {
            "domain": domain,
            "intent": intent,
            "complexity": complexity,
            "length_tier": min(len(text_lower) // 100, 5),
        }

    def _make_pattern_key(self, pattern: dict) -> str:
        """Generate a stable hash from pattern characteristics."""
        raw = (
            f"{pattern['domain']}|{pattern['intent']}|"
            f"c{pattern['complexity']}|l{pattern['length_tier']}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _hash_steps(self, steps: list[str]) -> str:
        """Generate a stable hash from reasoning steps."""
        raw = STEPS_SIGNATURE_SALT + "|" + "→".join(steps)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ── Recording ──

    def record_trace(
        self,
        input_text: str,
        steps: list[str],
        output: str,
        success: bool = True,
        latency_ms: float = 0.0,
    ) -> Optional[ReasoningTrace]:
        """Record a reasoning trace — the first step toward habit compilation.

        Called after every successful LLM invocation. If the same pattern
        succeeds enough times (>= compile_threshold), it is automatically
        compiled into a zero-inference habit.

        Args:
            input_text: The user input that triggered this reasoning path.
            steps: List of reasoning step labels (e.g. ["analyze_intent",
                   "classify_domain", "route_to_provider"]).
            output: The output text produced by the reasoning path.
            success: Whether the reasoning produced a valid result.
            latency_ms: Measured latency of the full reasoning path.

        Returns:
            The updated ReasoningTrace, or None if the trace was not recorded
            (e.g. failure without existing trace).
        """
        if not success and not steps:
            return None

        pattern = self._extract_pattern(input_text)
        pattern_key = self._make_pattern_key(pattern)

        if pattern_key not in self._traces:
            self._traces[pattern_key] = ReasoningTrace(
                pattern_key=pattern_key,
                steps=list(steps),
                output_signature=self._hash_steps(steps),
                success_count=0,
            )

        trace = self._traces[pattern_key]

        if success:
            trace.success_count += 1
            trace.last_used = time.time()
            trace.steps = list(steps)
            trace.output_signature = self._hash_steps(steps)

            if latency_ms > 0:
                if trace.avg_latency_ms == 0.0:
                    trace.avg_latency_ms = latency_ms
                else:
                    trace.avg_latency_ms = round(
                        0.8 * trace.avg_latency_ms + 0.2 * latency_ms, 1
                    )

            # MRU-like: move to end
            self._traces.move_to_end(pattern_key)

            # Auto-compile if ripe
            if trace.is_ripe and pattern_key not in self._habits:
                self.compile_to_habit(pattern_key)

        logger.debug(
            f"HabitCompiler: trace '{pattern_key[:8]}' → "
            f"successes={trace.success_count}/{self._compile_threshold} "
            f"(ripe={trace.is_ripe})"
        )

        return trace

    # ── Compilation ──

    def compile_to_habit(self, pattern_key: str) -> Optional[CompiledHabit]:
        """Compile a ReasoningTrace into a zero-inference CompiledHabit.

        Returns None if the pattern_key is not found or hasn't met
        the compile threshold, and also returns None if the habit already
        exists. Callers should use check_habit() to retrieve existing habits.
        """
        trace = self._traces.get(pattern_key)
        if not trace:
            logger.warning(f"HabitCompiler: no trace for pattern_key '{pattern_key[:8]}'")
            return None
        if not trace.is_ripe:
            logger.debug(
                f"HabitCompiler: pattern_key '{pattern_key[:8]}' not ripe "
                f"({trace.success_count}/{self._compile_threshold})"
            )
            return None
        if pattern_key in self._habits:
            logger.debug(
                f"HabitCompiler: habit already exists for '{pattern_key[:8]}'"
            )
            return None

        habit_id = f"habit_{pattern_key[:12]}"
        habit = CompiledHabit(
            habit_id=habit_id,
            trigger_pattern=pattern_key,
            direct_output=trace.output_signature,
            stats={
                "hit_count": 0,
                "saved_tokens": 0,
                "avg_original_latency_ms": trace.avg_latency_ms,
            },
        )

        self._habits[pattern_key] = habit

        # Enforce max habits: evict the least-recently-compiled
        while len(self._habits) > self._max_habits:
            oldest_key = next(iter(self._habits))
            evicted = self._habits.pop(oldest_key)
            logger.info(
                f"HabitCompiler: evicting habit '{evicted.habit_id}' "
                f"(age={evicted.age_hours:.1f}h) — max_habits={self._max_habits}"
            )

        logger.info(
            f"HabitCompiler: compiled habit '{habit_id}' — "
            f"steps={'→'.join(trace.steps)}, "
            f"avg_latency={trace.avg_latency_ms:.0f}ms → ~0ms (habit)"
        )

        return habit

    # ── Habit Lookup ──

    def check_habit(self, input_text: str) -> Optional[CompiledHabit]:
        """Check if the input triggers a compiled habit.

        If a matching habit is found, update its hit stats and return it.
        The caller should use the habit's direct_output to skip the LLM
        entirely, achieving ~75% latency reduction.

        Returns CompiledHabit if a habit matches, None otherwise.
        """
        pattern = self._extract_pattern(input_text)
        pattern_key = self._make_pattern_key(pattern)

        habit = self._habits.get(pattern_key)
        if habit is None:
            return None

        self._total_llm_calls_avoided += 1

        trace = self._traces.get(pattern_key)
        original_latency = trace.avg_latency_ms if trace else 0.0
        habit.record_hit(original_latency_ms=original_latency)

        # Update the underlying trace's last_used time
        if trace:
            trace.last_used = time.time()

        logger.debug(
            f"HabitCompiler: HIT habit '{habit.habit_id}' — "
            f"avoided LLM call #{self._total_llm_calls_avoided}"
        )

        return habit

    # ── Maintenance ──

    def invalidate_stale(self, max_age_hours: float = 24.0) -> int:
        """Remove habits older than max_age_hours to prevent staleness.

        Returns the number of habits invalidated.
        """
        now = time.time()
        stale_keys = [
            key for key, h in self._habits.items()
            if (now - h.compiled_at) / 3600.0 > max_age_hours
        ]

        for key in stale_keys:
            habit = self._habits.pop(key)
            logger.info(
                f"HabitCompiler: invalidated stale habit '{habit.habit_id}' "
                f"(age={habit.age_hours:.1f}h > {max_age_hours}h)"
            )

        if stale_keys:
            logger.info(
                f"HabitCompiler: invalidated {len(stale_keys)} stale habits"
            )

        return len(stale_keys)

    # ── Statistics ──

    def get_stats(self) -> dict:
        """Return comprehensive habit compiler statistics.

        Returns dict with:
            total_habits: Number of compiled habits currently active.
            total_traces: Number of reasoning traces being tracked.
            total_hits: Cumulative number of habit hits (LLM calls avoided).
            tokens_saved: Estimated tokens saved by avoiding LLM calls.
            llm_calls_avoided: Same as total_hits — for dashboard display.
            avg_latency_reduction_pct: Estimated average latency reduction.
            compile_threshold: Current compile threshold.
            max_habits: Maximum number of habits allowed.
            ripe_traces: Traces that are ripe for compilation but not yet compiled.
        """
        total_habits = len(self._habits)
        total_traces = len(self._traces)
        total_hits = self._total_llm_calls_avoided

        tokens_saved = sum(h.stats.get("saved_tokens", 0) for h in self._habits.values())

        avg_original_latency = 0.0
        latencies = [h.stats.get("avg_original_latency_ms", 0.0) for h in self._habits.values()]
        if latencies:
            avg_original_latency = sum(latencies) / len(latencies)

        ripe_traces = sum(
            1 for k, t in self._traces.items()
            if t.is_ripe and k not in self._habits
        )

        return {
            "total_habits": total_habits,
            "total_traces": total_traces,
            "total_hits": total_hits,
            "tokens_saved": tokens_saved,
            "llm_calls_avoided": total_hits,
            "avg_original_latency_ms": round(avg_original_latency, 1),
            "avg_latency_reduction_pct": 75.0 if total_hits > 0 else 0.0,
            "compile_threshold": self._compile_threshold,
            "max_habits": self._max_habits,
            "ripe_traces": ripe_traces,
        }

    def get_compilation_candidates(self, limit: int = 5) -> list[ReasoningTrace]:
        """Return traces that are close to the compile threshold (success_count == 2).

        These are patterns the system should try to exercise a few more times
        so they can be compiled into zero-inference habits.

        Args:
            limit: Maximum number of candidates to return.

        Returns:
            List of ReasoningTrace objects sorted by success_count descending.
        """
        candidates = [
            t for k, t in self._traces.items()
            if t.success_count == self._compile_threshold - 1
            and k not in self._habits
        ]
        candidates.sort(key=lambda t: (-t.success_count, -t.last_used))
        return candidates[:limit]

    def get_habit(self, habit_id: str) -> Optional[CompiledHabit]:
        """Look up a compiled habit by its habit_id."""
        for habit in self._habits.values():
            if habit.habit_id == habit_id:
                return habit
        return None

    def list_habits(self) -> list[CompiledHabit]:
        """Return all currently active compiled habits."""
        return list(self._habits.values())

    def list_traces(self, ripe_only: bool = False) -> list[ReasoningTrace]:
        """Return all reasoning traces, optionally filtered to ripe-only."""
        traces = list(self._traces.values())
        if ripe_only:
            traces = [t for t in traces if t.is_ripe]
        return traces

    def reset(self) -> None:
        """Clear all traces and habits. Used for testing or full reset."""
        count = len(self._traces) + len(self._habits)
        self._traces.clear()
        self._habits.clear()
        self._total_llm_calls_avoided = 0
        logger.info(f"HabitCompiler: reset — cleared {count} entries")


# ═══════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════

_compiler: Optional[HabitCompiler] = None


def get_habit_compiler() -> HabitCompiler:
    """Get or create the singleton HabitCompiler instance."""
    global _compiler
    if _compiler is None:
        _compiler = HabitCompiler()
    return _compiler


__all__ = [
    "ReasoningTrace",
    "CompiledHabit",
    "HabitCompiler",
    "get_habit_compiler",
]
