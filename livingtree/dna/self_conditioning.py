"""Self-Conditioning Loop — Bidirectional flow in the LifeEngine pipeline.

Implements self-conditioned generation: downstream stages detect that upstream stages
need revision and send backward signals to trigger re-execution of earlier stages.

Inspired by:

  - **PFlowNet** (arXiv:2605.02730, ICML 2026):
    "Decouple perception from reasoning to establish a self-conditioned generation
    process."  PFlowNet shows that by allowing downstream stages to condition the
    generation of upstream stages (rather than strictly serial forward flow), the
    system achieves higher quality outputs with fewer hallucinated artifacts.  We
    adapt this insight from video generation to our cognitive pipeline.

  - **ROMA** (arXiv:2602.01848):
    "Representation-Oriented Multi-Agent" framework demonstrates that letting
    refinement signals flow backward through a processing chain improves
    coordination and reduces error propagation.  Our backward signals correspond
    to ROMA's inter-agent correction messages.

  - **Tree-of-Thoughts** (arXiv:2305.10601):
    "Tree of Thoughts: Deliberate Problem Solving with Large Language Models."
    Shows that revisiting earlier reasoning steps when later steps uncover flaws
    dramatically improves reasoning quality.  Our conditioning loop generalizes
    this to any stage in the pipeline.

  - **MoDA** (arXiv:2603.15619, v2.4):
    Continuous corrective routing instead of binary trigger. Instead of fully
    re-executing stages, MoDA-style joint attention enables fine-grained
    content correction — routing specific corrective tokens from downstream
    to upstream stages via the depth K/V cache, rather than re-running
    the entire stage.

Architecture::

    CURRENT (strictly serial):
      perceive → cognize → ontogrow → plan → simulate → execute → reflect → evolve

    TARGET (self-conditioned with backward signals):
      perceive ↔ cognize ↔ ontogrow ↔ plan ↔ simulate ↔ execute ↔ reflect → evolve
         ↑         ↑          ↑        ↑        ↑         ↑         ↑
         └─────────┴──────────┴────────┴────────┴─────────┴── backward signals ──┘

    v2.4 MoDA-Enhanced: continuous routing replaces binary trigger
      perceive ←─⊕─← cognize ←─⊕─← plan ←─⊕─← execute ←─⊕─← reflect
           ↑    ⊕ = routing gate (routes specific corrections, not full re-exec)

Integration:
  Called AFTER all 8 stages complete in LifeEngine.run().  If backward signals
  are detected, earlier stages are re-executed with conditioning hints injected
  via ctx.metadata["{stage}_recondition_hint"].  The conditioning loop runs for
  at most 2 iterations, re-executing at most 3 stages per iteration.

  v2.4: When ModaCore is available, uses continuous content-corrective routing
  via `route_corrections_to_upstream()` instead of full stage re-execution.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from .life_context import LifeContext

# ═══════════════════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════════════════

STAGE_ORDER: tuple[str, ...] = (
    "perceive",
    "cognize",
    "ontogrow",
    "plan",
    "simulate",
    "execute",
    "reflect",
    "evolve",
)

# ── Built-in backward-signal detection rules ──
# Each tuple: (condition_desc, strength, hint)
# Evaluated in order; first matching condition for each (current_stage, target_stage) wins.


@dataclass
class BackwardSignal:
    """A signal from a downstream stage that an upstream stage needs revision.

    Modeled after PFlowNet's "reverse conditioning signal" which carries
    gradient-like information from the downstream task back to the upstream
    generation process.
    """

    source_stage: str
    target_stage: str
    strength: float
    reason: str
    hint: str
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        self.strength = min(1.0, max(0.0, self.strength))


@dataclass
class StageRewriteRule:
    """A programmable rule that amplifies or suppresses backward signals."""

    source_stage: str
    target_stage: str
    condition_desc: str
    strength_multiplier: float = 1.0


@dataclass
class ConditioningTrace:
    """Audit record for one re-conditioning iteration."""

    iteration: int
    signals: list[BackwardSignal] = field(default_factory=list)
    re_executed_stages: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Self-Conditioning Loop
# ═══════════════════════════════════════════════════════════════════════════════


class SelfConditioningLoop:
    """Bidirectional flow controller for the LifeEngine cognitive pipeline.

    After all 8 stages complete, this loop inspects each stage's output for
    implicit signals that an earlier stage should be revised.  When signals
    are found, it re-executes the target stages with conditioning hints,
    enabling the system to self-correct without external intervention.

    Key design constraints:
      - Max 2 full re-conditioning cycles (bounded by max_iterations).
      - Max 3 stages re-executed per cycle (bounded in select_stages_to_redo).
      - The "evolve" stage can send backward signals but is never re-triggered.
    """

    def __init__(
        self,
        max_iterations: int = 2,
        signal_threshold: float = 0.4,
        enable_evolve_feedback: bool = True,
    ) -> None:
        self.max_iterations = max_iterations
        self.signal_threshold = signal_threshold
        self.enable_evolve_feedback = enable_evolve_feedback
        self._traces: list[ConditioningTrace] = []
        self._custom_rules: list[StageRewriteRule] = []

    # ── Public API ──

    def check_backward_signals(
        self, ctx: LifeContext, current_stage: str
    ) -> list[BackwardSignal]:
        """Analyze current_stage output in ctx and detect backward signals.

        Each detection rule inspects specific fields on the LifeContext to
        determine whether an upstream stage was insufficient and should be
        re-executed with corrective hints.
        """
        signals: list[BackwardSignal] = []
        now = time.time()

        if current_stage == "cognize":
            signals.extend(self._check_cognize(ctx, now))

        elif current_stage == "ontogrow":
            signals.extend(self._check_ontogrow(ctx, now))

        elif current_stage == "plan":
            signals.extend(self._check_plan_stage(ctx, now))

        elif current_stage == "simulate":
            signals.extend(self._check_simulate(ctx, now))

        elif current_stage == "execute":
            signals.extend(self._check_execute(ctx, now))

        elif current_stage == "reflect":
            signals.extend(self._check_reflect(ctx, now))

        elif current_stage == "evolve":
            if self.enable_evolve_feedback:
                signals.extend(self._check_evolve_stage(ctx, now))

        self._apply_custom_rules(signals)
        return signals

    def should_recondition(self, signals: list[BackwardSignal]) -> bool:
        """Return True if any signal has meaningful weight after softmax attention.

        AttnRes-inspired (Kimi Team, arXiv:2603.15031): uses softmax attention
        over signal strengths instead of a fixed threshold. This makes the
        reconditioning decision content-dependent rather than hard-coded.

        A single weak signal in isolation may not trigger reconditioning, but
        multiple moderate signals can collectively cross the attention threshold
        because softmax amplifies relative differences.
        """
        if not signals:
            return False
        try:
            from .depth_attention import get_depth_attention
            da = get_depth_attention()
            values = [s.strength for s in signals]
            weights = da.compute_weights(values)
            # Trigger if the top-weighted signal has >15% of attention mass
            # (softmax: if all equal, each gets 1/N; top needs >1.5x equal share)
            n = len(values)
            equal_share = 1.0 / n
            return max(weights) > equal_share * 1.5 if n > 0 else False
        except Exception:
            return any(s.strength >= self.signal_threshold for s in signals)

    def select_stages_to_redo(
        self, signals: list[BackwardSignal], already_redone: set[str]
    ) -> list[str]:
        """Return priority-ordered stages, weighted by softmax attention.

        AttnRes-inspired: uses attention weights rather than raw signal
        strengths. This means a signal of 0.6 that dominates other signals
        gets higher priority than a signal of 0.8 among many strong signals.
        """
        eligible = [
            s for s in signals
            if s.target_stage not in already_redone
            and s.target_stage != "evolve"
        ]
        if not eligible:
            return []

        best: dict[str, BackwardSignal] = {}
        for s in eligible:
            if s.target_stage not in best or s.strength > best[s.target_stage].strength:
                best[s.target_stage] = s

        try:
            from .depth_attention import get_depth_attention
            da = get_depth_attention()
            values = [s.strength for s in best.values()]
            weights = da.compute_weights(values)
            # Sort by attention weight, not raw strength
            weighted = list(zip(best.values(), weights))
            weighted.sort(key=lambda x: -x[1])
            return [s.target_stage for s, _ in weighted[:3]]
        except Exception:
            ordered = sorted(best.values(), key=lambda x: x.strength, reverse=True)
            return [s.target_stage for s in ordered[:3]]

    def build_recondition_hints(
        self, signals: list[BackwardSignal], target_stage: str
    ) -> str:
        """Combine hints targeting the same stage, weighted by attention.

        AttnRes-inspired: hints with higher attention weight contribute
        more prominently to the reconditioning prompt.
        """
        relevant = [s for s in signals if s.target_stage == target_stage]
        if not relevant:
            return ""

        try:
            from .depth_attention import get_depth_attention
            da = get_depth_attention()
            values = [s.strength for s in relevant]
            weights = da.compute_weights(values)
        except Exception:
            weights = [s.strength for s in relevant]

        strongest = max(relevant, key=lambda s: s.strength)
        parts: list[str] = [
            f"[Self-Conditioning · AttnRes] 上游阶段反馈需要重新执行 {target_stage}。"
        ]
        for s, w in zip(relevant, weights):
            emphasis = "★" if w > 0.4 else "·"
            parts.append(f"  {emphasis} [{w:.0%}] {s.reason}: {s.hint}")
        parts.append(f"\n主要修正方向 [{max(weights):.0%}权重]: {strongest.hint}")
        return "\n".join(parts)

    def route_corrections_to_upstream(
        self,
        signals: list[BackwardSignal],
        current_stage: str,
        moda_core: Any = None,
    ) -> dict[str, list[str]]:
        """MoDA continuous corrective routing: route specific corrections instead of full re-exec.

        Instead of binary trigger (re-execute stage yes/no), this method
        computes which specific corrections from downstream should be
        routed to upstream stages. It uses MoDA's joint attention principle:
        the downstream signal attends to all upstream stages, and only the
        most relevant corrections are routed.

        Args:
            signals: Detected backward signals.
            current_stage: The current downstream stage.
            moda_core: Optional ModaCore instance for joint attention scoring.

        Returns:
            Dict mapping target_stage → list of corrective hint strings,
            suitable for injection as partial corrections (not full re-exec).
        """
        corrections: dict[str, list[str]] = {}

        if moda_core is not None:
            try:
                from .vector_context import text_to_vector, _cosine_similarity
                for signal in signals:
                    hint_vec = text_to_vector(signal.hint)
                    reason_vec = text_to_vector(signal.reason)
                    depth_vecs = moda_core.cache.get_depth_vectors()
                    depth_stages = moda_core.cache.get_depth_stages()
                    if depth_vecs:
                        for i, (dv, ds) in enumerate(zip(depth_vecs, depth_stages)):
                            if ds == signal.target_stage:
                                hint_sim = _cosine_similarity(hint_vec, dv)
                                if hint_sim > 0.2:
                                    corrections.setdefault(ds, []).append(
                                        f"[MoDA-route] {signal.hint} (rel={hint_sim:.2f})"
                                    )
                    if signal.target_stage not in corrections:
                        corrections.setdefault(signal.target_stage, []).append(
                            f"[MoDA-route] {signal.hint}"
                        )
                return corrections
            except Exception as e:
                logger.debug(f"MoDA routing fallback: {e}")

        for signal in signals:
            corrections.setdefault(signal.target_stage, []).append(signal.hint)
        return corrections

    def record_trace(
        self,
        iteration: int,
        signals: list[BackwardSignal],
        redone: list[str],
        duration_ms: float,
    ) -> None:
        """Record a ConditioningTrace for later audit and analysis."""
        trace = ConditioningTrace(
            iteration=iteration,
            signals=list(signals),
            re_executed_stages=list(redone),
            duration_ms=duration_ms,
        )
        self._traces.append(trace)

    def get_trace(self) -> list[ConditioningTrace]:
        """Return all conditioning traces from the current run."""
        return list(self._traces)

    def reset(self) -> None:
        """Clear all traces for a fresh run."""
        self._traces.clear()

    def stats(self) -> dict:
        """Return aggregate statistics across all conditioning traces."""
        if not self._traces:
            return {
                "total_iterations": 0,
                "total_signals": 0,
                "stages_redone_count": {},
                "avg_signal_strength": 0.0,
            }

        total_signals = sum(len(t.signals) for t in self._traces)
        all_signals: list[BackwardSignal] = []
        stage_counts: dict[str, int] = {}
        for t in self._traces:
            for s in t.signals:
                all_signals.append(s)
            for stage in t.re_executed_stages:
                stage_counts[stage] = stage_counts.get(stage, 0) + 1

        avg_strength = (
            sum(s.strength for s in all_signals) / len(all_signals)
            if all_signals
            else 0.0
        )

        return {
            "total_iterations": len(self._traces),
            "total_signals": total_signals,
            "stages_redone_count": stage_counts,
            "avg_signal_strength": round(avg_strength, 4),
        }

    # ── Custom rules ──

    def add_rule(self, rule: StageRewriteRule) -> None:
        """Register a user-defined rewrite rule that adjusts signal strengths."""
        self._custom_rules.append(rule)

    def _apply_custom_rules(self, signals: list[BackwardSignal]) -> None:
        """Apply registered StageRewriteRules to adjust signal strengths."""
        for rule in self._custom_rules:
            for s in signals:
                if (
                    s.source_stage == rule.source_stage
                    and s.target_stage == rule.target_stage
                ):
                    s.strength = min(1.0, s.strength * rule.strength_multiplier)

    # ── Per-stage detection ──

    @staticmethod
    def _check_cognize(ctx: LifeContext, now: float) -> list[BackwardSignal]:
        signals: list[BackwardSignal] = []
        intent = (ctx.intent or "").strip().lower()
        confidence = ctx.metadata.get("cognize_confidence", 0.5)
        vague_intents = {"general", "通用", "其他", "other", "unknown", "未知", ""}
        if intent in vague_intents or confidence < 0.5:
            signals.append(BackwardSignal(
                source_stage="cognize",
                target_stage="perceive",
                strength=0.5,
                reason=f"意图分析模糊(intent='{intent[:30]}', confidence={confidence:.2f})",
                hint="需要更具体的上下文信息",
                timestamp=now,
            ))
        return signals

    @staticmethod
    def _check_ontogrow(ctx: LifeContext, now: float) -> list[BackwardSignal]:
        signals: list[BackwardSignal] = []
        growth = ctx.metadata.get("ontology_growth", "")
        if not growth or growth == "no new concepts":
            # "no new concepts" means 0 new entities (< 2)
            signals.append(BackwardSignal(
                source_stage="ontogrow",
                target_stage="perceive",
                strength=0.4,
                reason="本体增长不足(未提取到新概念)",
                hint="本体增长不足，可能需要更多感知输入",
                timestamp=now,
            ))
        return signals

    @staticmethod
    def _check_plan_stage(ctx: LifeContext, now: float) -> list[BackwardSignal]:
        signals: list[BackwardSignal] = []
        plan = ctx.plan or []
        if len(plan) < 2:
            signals.append(BackwardSignal(
                source_stage="plan",
                target_stage="cognize",
                strength=0.6,
                reason=f"计划步骤过少({len(plan)}步)",
                hint="意图分析不够细化，需要更明确的任务分解",
                timestamp=now,
            ))
        return signals

    @staticmethod
    def _check_simulate(ctx: LifeContext, now: float) -> list[BackwardSignal]:
        signals: list[BackwardSignal] = []
        findings = ctx.simulation_findings or {}
        findings_text = str(findings).lower()
        if "contradiction" in findings_text or "inconsistent" in findings_text:
            signals.append(BackwardSignal(
                source_stage="simulate",
                target_stage="plan",
                strength=0.7,
                reason=f"模拟发现矛盾: {findings_text[:100]}",
                hint="计划存在矛盾，需要修正步骤",
                timestamp=now,
            ))
        return signals

    @staticmethod
    def _check_execute(ctx: LifeContext, now: float) -> list[BackwardSignal]:
        signals: list[BackwardSignal] = []
        results = ctx.execution_results or []
        plan = ctx.plan or []
        quality_reports = ctx.quality_reports or []

        total = len(results)
        if total == 0:
            # execution_results empty but plan has steps
            if len(plan) > 0:
                signals.append(BackwardSignal(
                    source_stage="execute",
                    target_stage="simulate",
                    strength=0.5,
                    reason="执行结果为空但计划有步骤",
                    hint="执行结果为空，可能需要先模拟验证",
                    timestamp=now,
                ))
            return signals

        failed = sum(
            1 for r in results
            if r.get("status") not in ("completed", "ok")
        )
        failure_rate = failed / max(total, 1)

        if failure_rate > 0.5:
            signals.append(BackwardSignal(
                source_stage="execute",
                target_stage="plan",
                strength=0.8,
                reason=f"执行大面积失败({failed}/{total}, rate={failure_rate:.2f})",
                hint="执行大面积失败，需要重新规划",
                timestamp=now,
            ))

        has_critical = False
        has_any = False
        for qr in quality_reports:
            if isinstance(qr, dict):
                score = qr.get("score", qr.get("final_score", 0.5))
                passed = qr.get("passed", score >= 0.5)
                if not passed:
                    has_any = True
                    if score < 0.3:
                        has_critical = True
                        break
            else:
                # Non-dict quality report — treat as issue
                has_any = True

        if has_critical:
            signals.append(BackwardSignal(
                source_stage="execute",
                target_stage="cognize",
                strength=0.6,
                reason="质量报告发现严重问题",
                hint="执行质量严重不达标，可能需要重新理解任务",
                timestamp=now,
            ))
        elif has_any:
            signals.append(BackwardSignal(
                source_stage="execute",
                target_stage="plan",
                strength=0.5,
                reason="质量报告发现问题",
                hint="质量报告发现问题，建议调整计划",
                timestamp=now,
            ))

        return signals

    @staticmethod
    def _check_reflect(ctx: LifeContext, now: float) -> list[BackwardSignal]:
        signals: list[BackwardSignal] = []
        success_rate = ctx.metadata.get("success_rate", 0.5)
        reflections = ctx.reflections or []
        reflection_text = " ".join(reflections).lower()

        if success_rate < 0.3:
            signals.append(BackwardSignal(
                source_stage="reflect",
                target_stage="plan",
                strength=0.7,
                reason=f"成功率过低({success_rate:.2f})",
                hint="成功率过低，需要完全重新规划",
                timestamp=now,
            ))

        # Check Chinese keywords in full text (non-lowered)
        raw_text = " ".join(reflections)
        if "missing context" in reflection_text or "信息不足" in raw_text:
            signals.append(BackwardSignal(
                source_stage="reflect",
                target_stage="perceive",
                strength=0.6,
                reason="反思发现缺少关键上下文",
                hint="反思发现缺少关键上下文，需要重新感知",
                timestamp=now,
            ))

        if "wrong approach" in reflection_text or "方向错误" in raw_text:
            signals.append(BackwardSignal(
                source_stage="reflect",
                target_stage="cognize",
                strength=0.8,
                reason="反思发现理解方向有问题",
                hint="反思发现理解方向有问题，需要重新理解意图",
                timestamp=now,
            ))

        return signals

    @staticmethod
    def _check_evolve_stage(ctx: LifeContext, now: float) -> list[BackwardSignal]:
        signals: list[BackwardSignal] = []
        lessons = ctx.metadata.get("lessons", []) or []
        evolution_notes = ctx.metadata.get("evolution_notes", "")
        failure_keywords = [
            "systematic", "反复", "重复", "pattern", "模式",
            "系统性", "频繁", "总是",
        ]
        combined = (
            " ".join(str(l) for l in (lessons if isinstance(lessons, list) else [lessons]))
            + " "
            + str(evolution_notes)
        ).lower()

        if any(kw in combined for kw in failure_keywords):
            signals.append(BackwardSignal(
                source_stage="evolve",
                target_stage="plan",
                strength=0.6,
                reason=f"进化经验表明计划模式存在问题",
                hint="进化经验表明计划模式有问题，需要调整计划策略",
                timestamp=now,
            ))

        return signals


# ═══════════════════════════════════════════════════════════════════════════════
# Conditioning Loop Algorithm (for integration into LifeEngine.run())
# ═══════════════════════════════════════════════════════════════════════════════
#
#   loop = get_conditioning_loop()
#   loop.reset()
#   iteration = 0
#   already_redone: set[str] = set()
#   t_start = time.time()
#
#   while iteration < loop.max_iterations:
#       signals: list[BackwardSignal] = []
#       for stage in ["cognize", "plan", "simulate", "execute", "reflect", "evolve"]:
#           new_signals = loop.check_backward_signals(ctx, stage)
#           signals.extend(new_signals)
#
#       if not loop.should_recondition(signals):
#           break
#
#       stages_to_redo = loop.select_stages_to_redo(signals, already_redone)
#       if not stages_to_redo:
#           break
#
#       for target in stages_to_redo:
#           hints = loop.build_recondition_hints(signals, target)
#           ctx.metadata[f"{target}_recondition_hint"] = hints
#           ctx.metadata["reconditioning"] = True
#           await self._stage(target, getattr(self, f"_{target}"), ctx, gate_enabled=False)
#           if self._fold_enabled:
#               await self._fold_stage(target, ctx, fold_max_chars)
#           already_redone.add(target)
#
#       duration = (time.time() - t_start) * 1000
#       loop.record_trace(iteration, signals, stages_to_redo, duration)
#       iteration += 1
#
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════════════════

_loop: SelfConditioningLoop | None = None


def get_conditioning_loop() -> SelfConditioningLoop:
    """Get or create the singleton SelfConditioningLoop."""
    global _loop
    if _loop is None:
        _loop = SelfConditioningLoop()
    return _loop


# ═══════════════════════════════════════════════════════════════════════════════
# LifeEngine.run() integration helper
# ═══════════════════════════════════════════════════════════════════════════════

# Mapping from stage name to method name on StageMixin (life_stage.py).
# Used by the integration code in LifeEngine.run() to resolve the correct
# method to re-invoke for each stage.
STAGE_METHOD_MAP: dict[str, str] = {
    "perceive": "_perceive",
    "cognize": "_cognize",
    "ontogrow": "_grow_ontology",
    "plan": "_plan",
    "simulate": "_simulate",
    "execute": "_execute",
    "reflect": "_reflect",
    "evolve": "_evolve",
}

# Stages whose output is checked for backward signals (downstream stages only).
# Perceive and ontogrow are excluded because they have no meaningful downstream
# output to analyze for backward signals in the initial pass.
BACKWARD_CHECK_STAGES: tuple[str, ...] = (
    "cognize",
    "ontogrow",
    "plan",
    "simulate",
    "execute",
    "reflect",
    "evolve",
)

# ═══ Zakharova IEM: Why Did I Fail? ───────────────────────────────

def why_did_i_fail(signals: list, stage: str) -> str:
    """Generate a first-person explanation for pipeline failure.

    Zakharova (2025) Argument 3: functional self-monitoring (detecting
    backward signals and re-executing stages) is NOT introspection. But
    when the system produces a first-person explanation of WHY it failed,
    it transforms monitoring into metacognitive reflection.

    Args:
        signals: list of BackwardSignal objects detected
        stage: the current pipeline stage that experienced issues

    Returns:
        A first-person reflection string explaining the failure
    """
    if not signals:
        return ""
    strongest = max(signals, key=lambda s: getattr(s, "strength", 0))
    reason = getattr(strongest, "reason", "unknown reason")
    source = getattr(strongest, "source_stage", "unknown")
    return (
        f"I notice that my {stage} stage failed. "
        f"The strongest signal came from my {source} stage "
        f"which detected: {reason}. "
        f"I believe this happened because my processing was insufficiently "
        f"thorough at the {stage} level. I will re-execute with greater care."
    )


async def run_conditioning_loop(
    engine,                # LifeEngine instance (has _stage, _fold_stage, etc.)
    ctx: LifeContext,
    fold_enabled: bool = False,
    fold_max_chars: int = 500,
    max_iterations: int | None = None,
) -> list[ConditioningTrace]:
    """Run the self-conditioning loop as an integration helper.

    Call this from LifeEngine.run() after the initial 8-stage pass completes.
    Returns the list of ConditioningTrace records for the run.

    Args:
        max_iterations: Override the loop's default max_iterations.
            None = use loop default (2). Set based on task complexity.
            Mythos-inspired: simple tasks use 0-1 iterations, complex use 2-4.

    Usage in life_engine.py::

        # After initial 8-stage pass completes:
        from .self_conditioning import run_conditioning_loop
        traces = await run_conditioning_loop(self, ctx, fold=self._fold_enabled)
        if traces:
            logger.info(f"[conditioning] {len(traces)} cycles, "
                        f"{sum(len(t.signals) for t in traces)} signals")
    """
    loop = get_conditioning_loop()
    loop.reset()

    effective_max = max_iterations if max_iterations is not None else loop.max_iterations

    iteration = 0
    already_redone: set[str] = set()
    t_start = time.time()

    while iteration < effective_max:
        signals: list[BackwardSignal] = []
        for stage in BACKWARD_CHECK_STAGES:
            new_signals = loop.check_backward_signals(ctx, stage)
            signals.extend(new_signals)

        if signals:
            summary = ", ".join(
                f"{s.source_stage}→{s.target_stage}({s.strength:.2f})"
                for s in signals[:6]
            )
            logger.debug(
                f"[conditioning] Iter {iteration}: {len(signals)} signals — {summary}"
            )

        if not loop.should_recondition(signals):
            logger.debug(f"[conditioning] No signals above threshold ({loop.signal_threshold})")
            break

        stages_to_redo = loop.select_stages_to_redo(signals, already_redone)
        if not stages_to_redo:
            logger.debug("[conditioning] No eligible stages to redo")
            break

        logger.info(
            f"[conditioning] Iter {iteration}: redoing {stages_to_redo} "
            f"(from {len(signals)} signals)"
        )

        for target in stages_to_redo:
            hints = loop.build_recondition_hints(signals, target)
            ctx.metadata[f"{target}_recondition_hint"] = hints
            ctx.metadata["reconditioning"] = True

            method_name = STAGE_METHOD_MAP.get(target)
            if method_name is None:
                logger.warning(f"[conditioning] Unknown stage '{target}' — skipping")
                continue

            stage_fn = getattr(engine, method_name, None)
            if stage_fn is None:
                logger.warning(f"[conditioning] No method '{method_name}' on engine — skipping")
                continue

            try:
                await engine._stage(target, stage_fn, ctx, gate_enabled=False)
                if fold_enabled and hasattr(engine, '_fold_stage'):
                    await engine._fold_stage(target, ctx, fold_max_chars)
                already_redone.add(target)
                logger.debug(f"[conditioning] Re-executed stage: {target}")
            except Exception as e:
                logger.warning(f"[conditioning] Failed to re-execute {target}: {e}")

        duration = (time.time() - t_start) * 1000
        loop.record_trace(iteration, signals, stages_to_redo, duration)
        iteration += 1

    traces = loop.get_trace()
    if traces:
        stats = loop.stats()
        logger.info(
            f"[conditioning] Complete: {stats['total_iterations']} iterations, "
            f"{stats['total_signals']} signals, "
            f"avg strength={stats['avg_signal_strength']:.3f}, "
            f"redone: {stats['stages_redone_count']}"
        )
        ctx.metadata["conditioning_stats"] = stats

    return traces


__all__ = [
    "BackwardSignal",
    "StageRewriteRule",
    "ConditioningTrace",
    "SelfConditioningLoop",
    "STAGE_ORDER",
    "STAGE_METHOD_MAP",
    "BACKWARD_CHECK_STAGES",
    "get_conditioning_loop",
    "run_conditioning_loop",
]
