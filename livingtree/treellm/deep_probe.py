"""DeepProbe — Cognitive forcing engine for inducing deep reasoning in LLMs.

Core insight: Online LLMs are economically incentivized to give shallow, cache-friendly
answers. DeepProbe rewrites user queries to force models into genuine reasoning by
injecting structural constraints that CANNOT be satisfied by cached pattern-matching.

Key forcing techniques (cannot be defeated by cache hits):
  1. Forced enumeration — "List N possible X, ranked by impact" (quantity prevents cache)
  2. Multi-dimensional constraints — "Analyze from A, B, C perspectives" (combinatorics)
  3. Self-challenge — "What's the strongest argument AGAINST your conclusion?"
  4. Step-locking — "Complete step 1 before step 2. Show reasoning at each step."
  5. Counterfactual injection — "If resource X were halved, does your answer change?"
  6. Process requirements — "Show your reasoning chain, not just the conclusion"
  7. Edge-case forcing — "Identify 3 edge cases where your answer would fail"
  8. Assumption surfacing — "List every assumption you made to reach this conclusion"

Strategy templates are task-type-aware, applying different forcing combinations
for code, reasoning, analysis, creative, and decision tasks.

Integration:
  - Placed BEFORE TreeLLM route_layered() — rewrites query then routes
  - SynapseAggregator receives deep-probed outputs for fusion
  - DepthGrading uses probe structure as scoring rubric

Usage:
    probe = get_deep_probe()
    rewritten, strategy = probe.rewrite(user_query, task_type="analysis")
    # rewritten = cognitively forced prompt
    # strategy = which strategies were applied
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional

from loguru import logger


# ═══ Strategy Types ═══════════════════════════════════════════════


class ProbeStrategy(StrEnum):
    """Cognitive forcing strategies for deep reasoning induction."""
    FORCED_ENUMERATION = "forced_enumeration"       # "List N possible X"
    MULTI_DIMENSION = "multi_dimension"              # "Analyze from A,B,C views"
    SELF_CHALLENGE = "self_challenge"                # "Argue AGAINST your conclusion"
    STEP_LOCKING = "step_locking"                    # "Complete step 1 before step 2"
    COUNTERFACTUAL = "counterfactual"                # "If X changed, what then?"
    PROCESS_REQUIRE = "process_require"              # "Show reasoning, not just answer"
    EDGE_CASE = "edge_case"                          # "Where would your answer fail?"
    ASSUMPTION_SURFACE = "assumption_surface"        # "List every assumption made"
    ANTI_CACHE = "anti_cache"                        # Inject uniqueness tokens
    VERIFY_REQUIRE = "verify_require"                # Opus 4.7: self-verify before output


@dataclass
class ProbeContext:
    """Context info extracted from query to guide strategy selection."""
    task_type: str                          # code, analysis, decision, creative, general
    complexity: float = 0.5                 # 0-1 inferred complexity
    has_constraints: bool = False           # Query already has constraints
    is_ambiguous: bool = False              # Query is vague/ambiguous
    language: str = "zh"                    # zh or en


@dataclass
class ProbeResult:
    """Result of deep probe rewriting."""
    original: str                           # Original user query
    rewritten: str                          # Cognitively forced prompt
    strategies_applied: list[ProbeStrategy]  # Which strategies were used
    task_type: str                          # Inferred task type
    probe_depth: int = 1                    # 1=light, 2=medium, 3=full depth
    expected_steps: int = 3                 # How many reasoning steps expected
    anti_cache_seed: str = ""               # Unique seed to break caching
    metadata: dict = field(default_factory=dict)


# ═══ DeepProbe Engine ═════════════════════════════════════════════


class DeepProbe:
    """Cognitive forcing engine — rewrites queries to induce deep reasoning.

    Design: Unlike post-processing or model selection, DeepProbe operates at the
    PRE-INFERENCE stage. It restructures the prompt so deeply that the model has
    no choice but to engage genuine reasoning processes.

    Strategy Selection Logic:
    - complex query → all strategies (depth=3)
    - medium query → 4-5 strategies (depth=2)
    - simple query → 2-3 strategies (depth=1)
    - already-structured query → fewer strategies (redundant)
    """

    # Strategy weights by task type (0=never, 1=always)
    STRATEGY_MATRIX: dict[str, dict[str, float]] = {
        "analysis": {
            "forced_enumeration": 1.0,
            "multi_dimension": 1.0,
            "self_challenge": 0.9,
            "step_locking": 0.8,
            "counterfactual": 0.7,
            "process_require": 0.9,
            "edge_case": 0.8,
            "assumption_surface": 0.8,
            "verify_require": 0.85,
        },
        "code": {
            "forced_enumeration": 0.9,
            "multi_dimension": 0.5,
            "self_challenge": 0.6,
            "step_locking": 1.0,
            "counterfactual": 0.7,
            "process_require": 0.8,
            "edge_case": 1.0,
            "assumption_surface": 0.5,
            "verify_require": 0.75,
        },
        "decision": {
            "forced_enumeration": 1.0,
            "multi_dimension": 1.0,
            "self_challenge": 0.9,
            "step_locking": 0.6,
            "counterfactual": 1.0,
            "process_require": 0.7,
            "edge_case": 0.7,
            "assumption_surface": 0.9,
            "verify_require": 0.80,
        },
        "creative": {
            "forced_enumeration": 0.8,
            "multi_dimension": 0.8,
            "self_challenge": 0.5,
            "step_locking": 0.4,
            "counterfactual": 0.7,
            "process_require": 0.5,
            "edge_case": 0.5,
            "assumption_surface": 0.6,
            "verify_require": 0.60,
        },
        "general": {
            "forced_enumeration": 0.7,
            "multi_dimension": 0.7,
            "self_challenge": 0.5,
            "step_locking": 0.6,
            "counterfactual": 0.5,
            "process_require": 0.7,
            "edge_case": 0.5,
            "assumption_surface": 0.5,
            "verify_require": 0.70,
        },
    }

    def __init__(self, default_depth: int = 2, max_strategies: int = 6):
        self._default_depth = default_depth
        self._max_strategies = max_strategies
        self._rewrite_count = 0
        self._strategy_success: dict[str, dict[str, list[float]]] = {}  # task_type → strategy → scores

    # ── Main Rewrite Pipeline ─────────────────────────────────────

    def rewrite(
        self, query: str, task_type: str = "general",
        depth: int | None = None,
    ) -> ProbeResult:
        """Rewrite a user query into a cognitively forced prompt.

        Args:
            query: Original user query.
            task_type: Inferred task type (analysis, code, decision, creative, general).
            depth: Override depth (1=light, 2=medium, 3=full). None=auto-detect.

        Returns:
            ProbeResult with rewritten prompt and strategy metadata.
        """
        self._rewrite_count += 1

        # Step 1: Analyze the query
        ctx = self._analyze(query, task_type)

        # Step 2: Determine depth
        if depth is None:
            depth = self._auto_depth(ctx)
        depth = max(1, min(3, depth))

        # Step 3: Select strategies based on task matrix + depth threshold
        strategies = self._select_strategies(task_type, depth, ctx)

        # Step 4: Generate anti-cache seed (prevents any cached response)
        import hashlib
        import time
        seed = hashlib.md5(
            f"{query[:50]}{time.time()}{self._rewrite_count}".encode()
        ).hexdigest()[:8]

        # Step 5: Build the forced prompt
        rewritten = self._build_prompt(query, strategies, ctx, depth, seed)

        # Step 6: Count expected reasoning steps
        expected_steps = self._count_expected_steps(strategies, depth)

        logger.info(
            f"DeepProbe: [{task_type}] depth={depth}, "
            f"strategies={len(strategies)}/{self._max_strategies}, "
            f"expected_steps={expected_steps}"
        )

        return ProbeResult(
            original=query,
            rewritten=rewritten,
            strategies_applied=strategies,
            task_type=task_type,
            probe_depth=depth,
            expected_steps=expected_steps,
            anti_cache_seed=seed,
            metadata={
                "complexity": ctx.complexity,
                "language": ctx.language,
                "has_constraints": ctx.has_constraints,
                "is_ambiguous": ctx.is_ambiguous,
            },
        )

    # ── Analysis ──────────────────────────────────────────────────

    @staticmethod
    def _analyze(query: str, task_type: str) -> ProbeContext:
        """Extract query properties to guide strategy selection."""
        q = query or ""
        ql = q.lower()

        # Complexity heuristics
        complexity = 0.3  # baseline
        if len(q) > 200:
            complexity += 0.2
        complex_markers = [
            "如何", "怎么优化", "架构", "设计", "分析", "策略",
            "how to", "optimize", "architecture", "design", "strategy",
        ]
        matches = sum(1 for m in complex_markers if m in ql)
        complexity += min(0.3, matches * 0.1)

        # Constraint detection
        has_constraints = any(
            m in ql for m in ["必须", "不能", "限制", "requirement",
                              "must", "cannot", "constraint", "budget"]
        )

        # Ambiguity detection
        is_ambiguous = (
            len(q) < 20
            or ql in ["帮我看看", "优化一下", "怎么改", "有问题", "help", "fix"]
            or (not any(c.isalpha() for c in q))
        )

        # Language
        chinese_chars = sum(1 for c in q if '\u4e00' <= c <= '\u9fff')
        language = "zh" if chinese_chars > len(q) * 0.2 else "en"

        return ProbeContext(
            task_type=task_type,
            complexity=min(1.0, complexity),
            has_constraints=has_constraints,
            is_ambiguous=is_ambiguous,
            language=language,
        )

    @staticmethod
    def _auto_depth(ctx: ProbeContext) -> int:
        """Auto-detect optimal probe depth based on query complexity."""
        if ctx.complexity > 0.7 or ctx.is_ambiguous:
            return 3  # Full depth — complex or vague queries
        if ctx.complexity > 0.4:
            return 2  # Medium depth
        return 1  # Light depth — simple queries

    # ── Strategy Selection ────────────────────────────────────────

    def _select_strategies(
        self, task_type: str, depth: int, ctx: ProbeContext,
    ) -> list[ProbeStrategy]:
        """Select which cognitive forcing strategies to apply."""
        matrix = self.STRATEGY_MATRIX.get(task_type, self.STRATEGY_MATRIX["general"])

        # Threshold: higher depth → lower threshold (more strategies applied)
        thresholds = {1: 0.85, 2: 0.6, 3: 0.35}
        threshold = thresholds.get(depth, 0.6)

        # Candidate strategies that exceed threshold
        candidates = [
            (ProbeStrategy(k), v)
            for k, v in matrix.items()
            if v >= threshold
        ]

        # Sort by weight descending
        candidates.sort(key=lambda x: -x[1])

        # Reduce if query already structured
        if ctx.has_constraints and len(candidates) > 4:
            candidates = candidates[:max(3, len(candidates) - 2)]

        # Always include ANTI_CACHE
        selected = [s for s, _ in candidates[:self._max_strategies]]
        if ProbeStrategy.ANTI_CACHE not in selected:
            selected.append(ProbeStrategy.ANTI_CACHE)

        return selected

    # ── Prompt Building ───────────────────────────────────────────

    def _build_prompt(
        self, query: str, strategies: list[ProbeStrategy],
        ctx: ProbeContext, depth: int, seed: str,
    ) -> str:
        """Build the cognitively forced prompt from selected strategies."""
        parts: list[str] = []

        # Anti-cache header (MUST come first — breaks all cached responses)
        if ProbeStrategy.ANTI_CACHE in strategies:
            parts.append(
                f"[uid:{seed}] Think carefully. This is a unique request "
                f"requiring original reasoning — not a cached answer."
            )

        # Core instruction
        if ctx.language == "zh":
            parts.append(f"请深度分析以下问题：{query}")
        else:
            parts.append(f"Analyze the following question in depth: {query}")

        # Step-by-step structure (STEP_LOCKING)
        if ProbeStrategy.STEP_LOCKING in strategies:
            parts.append(self._build_step_lock(ctx))

        # Forced enumeration
        if ProbeStrategy.FORCED_ENUMERATION in strategies:
            parts.append(self._build_enumeration(ctx))

        # Multi-dimensional analysis
        if ProbeStrategy.MULTI_DIMENSION in strategies:
            parts.append(self._build_multi_dimension(ctx))

        # Process requirements
        if ProbeStrategy.PROCESS_REQUIRE in strategies:
            parts.append(self._build_process_require(ctx))

        # Opus 4.7 Self-Verify: add explicit verification stage
        if ProbeStrategy.VERIFY_REQUIRE in strategies:
            parts.append(self._build_verify_require(ctx))

        # Self-challenge
        if ProbeStrategy.SELF_CHALLENGE in strategies:
            parts.append(self._build_self_challenge(ctx))

        # Counterfactual
        if ProbeStrategy.COUNTERFACTUAL in strategies:
            parts.append(self._build_counterfactual(ctx))

        # Edge case forcing
        if ProbeStrategy.EDGE_CASE in strategies:
            parts.append(self._build_edge_case(ctx))

        # Assumption surfacing
        if ProbeStrategy.ASSUMPTION_SURFACE in strategies:
            parts.append(self._build_assumption_surface(ctx))

        # Footer: explicit anti-shortcut
        parts.append(self._build_footer(ctx, depth))

        return "\n\n".join(parts)

    # ── Strategy Templates ────────────────────────────────────────

    @staticmethod
    def _build_step_lock(ctx: ProbeContext) -> str:
        if ctx.language == "zh":
            return (
                "请按以下步骤逐一执行，完成每步后再进行下一步：\n"
                "第1步：明确问题的范围和边界条件\n"
                "第2步：识别所有相关因素和变量\n"
                "第3步：逐一分析每个因素的作用机制\n"
                "第4步：综合所有分析，给出结论\n"
                "第5步：反思你的结论，指出可能的不足"
            )
        return (
            "Execute the following steps in order. Complete each step before "
            "moving to the next:\n"
            "Step 1: Define the problem scope and boundary conditions\n"
            "Step 2: Identify all relevant factors and variables\n"
            "Step 3: Analyze each factor's mechanism of action\n"
            "Step 4: Synthesize all analysis into a conclusion\n"
            "Step 5: Reflect on your conclusion — point out possible gaps"
        )

    @staticmethod
    def _build_enumeration(ctx: ProbeContext) -> str:
        n = 5 if ctx.complexity > 0.6 else 3
        if ctx.language == "zh":
            return (
                f"列出至少{n}种可能的{('方案' if ctx.task_type == 'decision' else '角度')}"
                f"或{('原因' if ctx.task_type == 'analysis' else '方法')}，"
                f"按{('影响程度' if ctx.task_type == 'analysis' else '可行性')}排序。"
                f"对每一项都给出具体依据。"
            )
        return (
            f"List at least {n} possible "
            f"{'solutions' if ctx.task_type == 'decision' else 'perspectives or causes'}, "
            f"ranked by {'impact' if ctx.task_type == 'analysis' else 'feasibility'}. "
            f"Provide specific reasoning for each item."
        )

    @staticmethod
    def _build_multi_dimension(ctx: ProbeContext) -> str:
        dimensions = {
            "code": ["正确性", "性能", "可维护性", "安全性"],
            "analysis": ["因果逻辑", "数据支撑", "边界假设", "历史对比"],
            "decision": ["成本", "收益", "风险", "可行性"],
            "creative": ["原创性", "可行性", "受众适配", "情感影响"],
            "general": ["逻辑性", "完整性", "实用性", "创新性"],
        }
        dims = dimensions.get(ctx.task_type, dimensions["general"])
        if ctx.language == "zh":
            dim_str = "、".join(dims)
            return f"从以下维度分别分析：{dim_str}。每个维度至少2句分析。"
        return (
            f"Analyze from the following dimensions: "
            f"{', '.join(dims)}. At least 2 sentences per dimension."
        )

    @staticmethod
    def _build_process_require(ctx: ProbeContext) -> str:
        if ctx.language == "zh":
            return (
                "⚠ 重要：你必须展示推理过程，而不仅仅是给出结论。"
                "每个主张必须附带形成该主张的思维链条。"
                "禁止省略推理步骤。禁止使用「显然」「众所周知」等跳过推理的表述。"
            )
        return (
            "CRITICAL: Show your reasoning process, not just conclusions. "
            "Every claim must include the chain of thought that led to it. "
            "Do NOT skip reasoning steps. Do NOT use 'obviously' or "
            "'it is well known' to bypass reasoning."
        )

    @staticmethod
    def _build_verify_require(ctx: ProbeContext) -> str:
        """Opus 4.7 Self-Verify: require internal verification before output.

        Adds a <verify> stage that forces the model to check its own reasoning
        chain before presenting the final answer. This mimics the "scratch paper"
        internal verification mechanism of Opus 4.7.
        """
        if ctx.language == "zh":
            return (
                "Step 6: 在给出最终答案之前，请先完成一个 <验证> 阶段：\n"
                "  a) 回溯你的推理链条，逐项检查每个论断是否基于可靠的论据\n"
                "  b) 识别推理过程中可能的逻辑跳跃或隐含假设\n"
                "  c) 检查最终结论与中间步骤是否自洽，有无前后矛盾\n"
                "  d) 如果发现不一致，修正后再输出最终答案\n"
                "  e) 为每个关键结论标注可信度（高/中/低）"
            )
        return (
            "Step 6: Before presenting your final answer, complete a <verify> stage:\n"
            "  a) Trace back your reasoning chain and check each claim against evidence\n"
            "  b) Identify any logical leaps or unstated assumptions in your reasoning\n"
            "  c) Check that your conclusion is self-consistent with all intermediate steps\n"
            "  d) If you find any inconsistencies, revise before outputting the final answer\n"
            "  e) Mark confidence level (high/medium/low) for each key conclusion"
        )

    @staticmethod
    def _build_self_challenge(ctx: ProbeContext) -> str:
        if ctx.language == "zh":
            return (
                "在你完成分析后，请找出你的论证中最薄弱的两个环节，"
                "并构造针对这些环节的最强反驳论点。然后解释为什么你的结论"
                "在这些反驳下仍然成立（或不成立，如果反驳足够强的话）。"
            )
        return (
            "After completing your analysis, identify the TWO weakest parts "
            "of your argument. Construct the strongest possible counter-arguments "
            "against those parts. Then explain why your conclusion still holds "
            "(or does not hold, if the counter-arguments are strong enough)."
        )

    @staticmethod
    def _build_counterfactual(ctx: ProbeContext) -> str:
        if ctx.language == "zh":
            return (
                "假设一个关键约束条件发生了根本性变化（比如预算减半、时间窗口缩短、"
                "或团队规模缩小），你的分析结论会发生什么变化？请指出哪些结论是"
                "脆弱的（依赖于当前约束），哪些是稳健的（不依赖于具体约束）。"
            )
        return (
            "Suppose a key constraint changes fundamentally (e.g. budget halved, "
            "timeline compressed, team size reduced). How would your analysis change? "
            "Identify which conclusions are FRAGILE (constraint-dependent) and which "
            "are ROBUST (independent of specific constraints)."
        )

    @staticmethod
    def _build_edge_case(ctx: ProbeContext) -> str:
        if ctx.language == "zh":
            return (
                "找出你的分析可能失效的至少3个边缘场景（边界条件、极端输入、"
                "或特殊上下文）。对每个场景，说明为什么会失效。"
            )
        return (
            "Identify at least 3 edge cases where your analysis would BREAK DOWN "
            "(boundary conditions, extreme inputs, or special contexts). "
            "For each edge case, explain why it breaks."
        )

    @staticmethod
    def _build_assumption_surface(ctx: ProbeContext) -> str:
        if ctx.language == "zh":
            return (
                "明确列出你在分析中做出的全部假设（至少5条）。"
                "对每条假设，评估如果该假设不成立，对你的结论的影响程度（高/中/低）。"
            )
        return (
            "Explicitly list ALL assumptions you made in your analysis (at least 5). "
            "For each assumption, rate the impact on your conclusion (high/medium/low) "
            "if that assumption were to be false."
        )

    @staticmethod
    def _build_footer(ctx: ProbeContext, depth: int) -> str:
        seed_keywords = [
            "unique", "specific", "original", "non-cached", "live-reasoning",
            "unique-request", "do-not-template", "reason-from-scratch",
        ]
        import random
        anti_word = random.choice(seed_keywords)

        if ctx.language == "zh":
            return (
                f"提醒：这不是一个可以用模板回答的问题。你的回答必须体现"
                f"对该具体情境的独立推理（{anti_word}-{depth}）。"
                f"直接给出结论而不展示推理过程将被视为不完整回答。"
            )
        return (
            f"Reminder: This is not a template-able question. Your response must "
            f"demonstrate independent reasoning specific to this context "
            f"({anti_word}-{depth}). Conclusions without visible reasoning "
            f"will be considered incomplete."
        )

    # ── Expected Steps Counter ────────────────────────────────────

    @staticmethod
    def _count_expected_steps(
        strategies: list[ProbeStrategy], depth: int,
    ) -> int:
        """Estimate how many reasoning steps the forced prompt will generate."""
        step_map = {
            ProbeStrategy.STEP_LOCKING: 5,
            ProbeStrategy.FORCED_ENUMERATION: 4,
            ProbeStrategy.MULTI_DIMENSION: 4,
            ProbeStrategy.SELF_CHALLENGE: 3,
            ProbeStrategy.COUNTERFACTUAL: 2,
            ProbeStrategy.EDGE_CASE: 3,
            ProbeStrategy.ASSUMPTION_SURFACE: 2,
            ProbeStrategy.PROCESS_REQUIRE: 1,
        }
        base = sum(step_map.get(s, 1) for s in strategies)
        return base * depth // 2 if depth > 1 else base

    # ── Dynamic Strategy Learning ──────────────────────────────────

    def learn_from_depth(self, task_type: str, strategies_applied: list[ProbeStrategy],
                          depth_grade: float) -> None:
        """Learn which strategies work best per task type from DepthGrading feedback.
        
        Uses Thompson Sampling (Beta distribution) to rapidly adapt strategy selection.
        High depth grades → reinforce; shallow grades → penalize. Converges faster
        than EMA because Beta posteriors narrow with each observation.
        """
        if task_type not in self._strategy_success:
            self._strategy_success[task_type] = {}
        for s in strategies_applied:
            key = s.value if isinstance(s, ProbeStrategy) else str(s)
            if key not in self._strategy_success[task_type]:
                self._strategy_success[task_type][key] = {"alpha": 2.0, "beta": 2.0}
            # Thompson update: depth_grade as reward signal
            reward = min(1.0, max(0.0, depth_grade))
            self._strategy_success[task_type][key]["alpha"] += reward * 3.0
            self._strategy_success[task_type][key]["beta"] += (1.0 - reward) * 3.0

        # Adapt STRATEGY_MATRIX every 5 feedback signals (faster than before)
        total = sum(len(v) if isinstance(v, list) else v.get("alpha", 0)
                     for v in self._strategy_success.get(task_type, {}).values())
        if int(total) >= 5 and int(total) % 5 == 0:
            self._adapt_matrix(task_type)

    def _adapt_matrix(self, task_type: str) -> None:
        """Adapt STRATEGY_MATRIX from Beta posterior means."""
        import random
        matrix = self.STRATEGY_MATRIX.get(task_type, self.STRATEGY_MATRIX["general"])
        for key, stats in self._strategy_success.get(task_type, {}).items():
            if isinstance(stats, dict) and "alpha" in stats:
                mean = stats["alpha"] / max(stats["alpha"] + stats["beta"], 0.01)
                matrix[key] = round(mean, 2)

    def stats(self) -> dict:
        return {
            "rewrites": self._rewrite_count,
            "default_depth": self._default_depth,
            "max_strategies": self._max_strategies,
        }


# ═══ Singleton ═════════════════════════════════════════════════════

_probe: Optional[DeepProbe] = None


def get_deep_probe() -> DeepProbe:
    global _probe
    if _probe is None:
        _probe = DeepProbe()
    return _probe


__all__ = [
    "DeepProbe", "ProbeStrategy", "ProbeContext", "ProbeResult",
    "get_deep_probe",
]
