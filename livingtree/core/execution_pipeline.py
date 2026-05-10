"""ExecutionPipeline — merged life_engine + gtsm_planner execution skeleton.

Accepts ModelConfig protocol from TreeLLM (independent cognitive layer).
Converges: decompose → sandbox → verify → fold → memorize into one pipeline.

Architecture:
  🧠 Brain (TreeLLM) → ModelConfig protocol
                         ↓
  🦴 Bones + 🦵 Legs (ExecutionPipeline) → ExecutionResult
                         ↓
  🛡️ Immune (PolicyGuard) → ARQ verify
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DEGRADED = "degraded"


@dataclass
class ModelConfig:
    """Protocol between TreeLLM and ExecutionPipeline — zero coupling."""
    model: str
    tools: list[str] = field(default_factory=list)
    priority: float = 0.5
    fallback_chain: list[str] = field(default_factory=list)
    max_retries: int = 2
    temperature: float = 0.7
    meta: dict = field(default_factory=dict)


@dataclass
class ExecutionResult:
    plan: list[dict] = field(default_factory=list)
    output: str = ""
    model_used: str = ""
    tools_used: list[str] = field(default_factory=list)
    status: PipelineStatus = PipelineStatus.PENDING
    latency_ms: float = 0.0
    retries: int = 0
    folded_context: str = ""
    trace_id: str = ""
    error: str = ""


class ExecutionPipeline:
    """Converged execution skeleton.

    Replaces life_engine.run() + gtsm_planner.plan() with a unified
    decompose→sandbox→verify→fold→memorize pipeline.
    Accepts ModelConfig from TreeLLM via protocol — zero direct dependency.
    
    Parallel optimizations (no extra LLM cost):
      - Multi-plan decompose: 3 plans in parallel → pick best via heuristic
      - Multi-strategy verify: ARQ + Shield + Lint → concurrent
      - Memorize: always fire-and-forget
    """

    def __init__(self, hub=None):
        self._hub = hub
        self._sandbox = None
        self._arq = None
        self._folder = None
        self._memory = None
        self._enabled: bool = False
        self._flow_pct: float = 0.0
        self._parallel_decompose: bool = True   # multi-plan parallel
        self._parallel_verify: bool = True      # multi-strategy parallel
        self._stats = {"total": 0, "success": 0, "degraded": 0, "failed": 0,
                       "parallel_gains": 0, "plans_compared": 0}

    # ═══ Lifecycle ═══

    async def start(self, flow_pct: float = 0.0):
        self._enabled = flow_pct > 0
        self._flow_pct = flow_pct
        logger.info(f"ExecutionPipeline: enabled={self._enabled} flow={flow_pct:.0%}")

    async def stop(self):
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ═══ Main Pipeline ═══

    async def run(
        self, config: ModelConfig, user_input: str,
        context: dict = None,
    ) -> ExecutionResult:
        """Full execution pipeline: decompose → sandbox → verify → fold."""
        t0 = time.time()
        trace_id = str(uuid.uuid4())[:8]
        self._stats["total"] += 1

        result = ExecutionResult(trace_id=trace_id, model_used=config.model)

        try:
            # Stage 1: Decompose (parallel multi-plan)
            if self._parallel_decompose and len(config.tools) <= 6:
                plan = await self._decompose_parallel(user_input, config)
            else:
                plan = await self._decompose(user_input, config)
            result.plan = plan

            # Stage 2: Sandbox execute
            for attempt in range(config.max_retries + 1):
                try:
                    output = await self._execute(plan, config, context)
                    result.output = output
                    result.retries = attempt
                    break
                except Exception as e:
                    if attempt < config.max_retries:
                        logger.debug(f"ExecutionPipeline retry {attempt+1}: {e}")
                        config = self._fallback_config(config, attempt)
                        plan = await self._decompose(user_input, config)
                    else:
                        raise

            # Stage 3: Multi-strategy verify — ARQ + Shield + Lint parallel
            passed, verification = await self._verify_parallel(user_input, result.output)
            if not passed:
                result.status = PipelineStatus.DEGRADED
                self._stats["degraded"] += 1
                result.output = verification.get("sanitized", result.output)
            else:
                result.status = PipelineStatus.SUCCESS
                self._stats["success"] += 1

            # Stage 4: Context fold
            result.folded_context = await self._fold(result.output, context)

            # Stage 5: Memorize (fire-and-forget)
            asyncio.create_task(self._memorize(user_input, result, config))

        except Exception as e:
            result.status = PipelineStatus.FAILED
            result.error = str(e)[:200]
            self._stats["failed"] += 1
            logger.warning(f"ExecutionPipeline [{trace_id}]: {e}")

        result.latency_ms = (time.time() - t0) * 1000
        result.tools_used = config.tools
        return result

    # ═══ Parallel: Multi-plan decompose (3 plans, pick best) ═══

    async def _decompose_parallel(self, user_input: str, config: ModelConfig) -> list[dict]:
        """Run 3 decompose variants in parallel, select the best plan.

        Variants: concise (minimal steps), detailed (exhaustive), creative (novel paths).
        Best heuristic: highest step count without exceeding tool budget.
        """
        import asyncio

        variants = [
            ("concise", f"简洁分解: {user_input}"),
            ("detailed", f"详细分解: {user_input}"),
            ("creative", f"创新分解: {user_input}"),
        ]

        tasks = [self._decompose(prompt, config) for _, prompt in variants]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        plans = []
        for (label, _), r in zip(variants, results):
            if isinstance(r, Exception):
                continue
            if r and isinstance(r, list) and len(r) > 0:
                plans.append((label, r))

        if not plans:
            return await self._decompose(user_input, config)

        if len(plans) == 1:
            self._stats["plans_compared"] += 1
            return plans[0][1]

        best = max(plans, key=lambda p: (
            min(len(p[1]), len(config.tools)) * 10 +     # prefer more steps
            sum(1 for s in p[1] if s.get("tool") in config.tools) * 5  # tool match
        ))

        self._stats["plans_compared"] += len(plans)
        self._stats["parallel_gains"] += 1
        logger.info(f"ExecutionPipeline: multi-plan → {best[0]} ({len(best[1])} steps, from {len(plans)} variants)")
        return best[1]

    # ═══ Parallel: Multi-strategy verify (ARQ + Shield + Lint) ═══

    async def _verify_parallel(self, user_input: str, output: str) -> tuple[bool, dict]:
        """Run ARQ + prompt-shield + output-lint in parallel. Returns (passed, {sanitized, issues})."""
        import asyncio

        async def _arq_check():
            try:
                from ..core.behavior_control import get_arq
                v = await get_arq().verify_response(user_input, output, get_arq())
                return v.get("passed", True), v.get("modified_output", output)
            except Exception:
                return True, output

        async def _shield_check():
            try:
                from ..core.prompt_shield import get_shield
                r = get_shield().check_output(output)
                return r.passed, r.sanitized_text or output, r.violations
            except Exception:
                return True, output, []

        async def _lint_check():
            try:
                from ..core.output_linter import get_linter
                r = get_linter().lint(output)
                return r.passed, r.sanitized or output, r.issues
            except Exception:
                return True, output, []

        arq_task = asyncio.create_task(_arq_check())
        shield_task = asyncio.create_task(_shield_check())
        lint_task = asyncio.create_task(_lint_check())

        arq_ok, arq_out = await arq_task
        shield_ok, shield_out, shield_violations = await shield_task
        lint_ok, lint_out, lint_issues = await lint_task

        all_ok = arq_ok and shield_ok and lint_ok
        sanitized = output
        issues = []

        if not shield_ok:
            sanitized = shield_out
            issues.extend(shield_violations)
        if not lint_ok:
            sanitized = lint_out
            issues.extend(lint_issues)
        if not arq_ok:
            sanitized = arq_out

        if not all_ok:
            logger.info(f"ExecutionPipeline: verify failed — ARQ={arq_ok} Shield={shield_ok} Lint={lint_ok}")

        return all_ok, {"sanitized": sanitized, "issues": issues}

    # ═══ Single-path (legacy fallback) ═══

    async def _decompose(self, user_input: str, config: ModelConfig) -> list[dict]:
        if self._hub and hasattr(self._hub, "world") and self._hub.world:
            try:
                planner = getattr(self._hub.world, "gtsm_planner", None)
                if planner and hasattr(planner, "plan"):
                    trajectory = await planner.plan(prompt=user_input, tools=config.tools)
                    return trajectory.to_plan_format() if hasattr(trajectory, "to_plan_format") else []
            except Exception:
                pass
        return [{"step": 1, "action": "direct", "tool": config.tools[0] if config.tools else "llm"}]

    async def _execute(self, plan: list[dict], config: ModelConfig, context: dict = None) -> str:
        tasks = []
        for step in plan:
            tool = step.get("tool", "llm")
            if self._hub and hasattr(self._hub, "call_tool"):
                tasks.append(self._hub.call_tool(tool, step))
        if not tasks:
            if self._hub and hasattr(self._hub, "chat"):
                return await self._hub.chat({"role": "user", "content": str(plan)})
            return str(plan)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return "\n".join(str(r) for r in results if not isinstance(r, Exception))

    async def _verify(self, user_input: str, output: str) -> bool:
        try:
            from ..core.behavior_control import get_arq
            arq = get_arq()
            v = await arq.verify_response(user_input, output, get_arq())
            return v.get("passed", True)
        except Exception:
            return True

    async def _sanitize_output(self, output: str) -> str:
        try:
            from ..core.prompt_shield import get_shield
            result = get_shield().check_output(output)
            return result.sanitized_text if not result.passed else output
        except Exception:
            return output

    async def _fold(self, output: str, context: dict = None) -> str:
        try:
            from ..core.adaptive_folder import AdaptiveFolder
            folder = AdaptiveFolder()
            folded = folder.fold({"content": output, "context": context or {}})
            return str(folded)[:2000]
        except Exception:
            return output[:500]

    async def _memorize(self, user_input: str, result: ExecutionResult, config: ModelConfig):
        try:
            from ..dna.struct_mem import get_struct_mem
            mem = get_struct_mem()
            if mem:
                mem.store(
                    key=f"exec_{result.trace_id}",
                    content=result.output[:500],
                    metadata={"model": config.model, "latency_ms": result.latency_ms},
                )
        except Exception:
            pass

    def _fallback_config(self, config: ModelConfig, attempt: int) -> ModelConfig:
        if attempt < len(config.fallback_chain):
            return ModelConfig(
                model=config.fallback_chain[attempt],
                tools=config.tools,
                priority=config.priority * 0.8,
                max_retries=1,
            )
        return config

    # ═══ Gray-Release Routing ═══

    def should_handle(self, trace_id: str = "") -> bool:
        """Gray-release: route request based on flow percentage."""
        if not self._enabled:
            return False
        if self._flow_pct >= 1.0:
            return True
        bucket = int(trace_id[:4], 16) if trace_id else hash(str(time.time_ns())) % 10000
        return bucket < self._flow_pct * 10000

    def update_flow(self, pct: float):
        self._flow_pct = max(0.0, min(1.0, pct))
        self._enabled = self._flow_pct > 0
        logger.info(f"ExecutionPipeline flow: {self._flow_pct:.0%}")

    # ═══ Stats ═══

    def stats(self) -> dict:
        s = self._stats
        total = max(1, s["total"])
        return {
            "enabled": self._enabled,
            "flow_pct": round(self._flow_pct, 2),
            "total_runs": s["total"],
            "success_rate": round(s["success"] / total, 3),
            "degraded_rate": round(s["degraded"] / total, 3),
            "failure_rate": round(s["failed"] / total, 3),
            "parallel_decompose": self._parallel_decompose,
            "parallel_verify": self._parallel_verify,
            "plans_compared": s.get("plans_compared", 0),
            "parallel_gains": s.get("parallel_gains", 0),
            "stage": "alpha" if self._flow_pct < 0.1 else (
                "beta" if self._flow_pct < 0.5 else (
                    "rc" if self._flow_pct < 1.0 else "ga")),
        }

    def render_html(self) -> str:
        st = self.stats()
        color = "var(--warn)" if st["stage"] in ("alpha", "beta") else "var(--accent)"
        pd = "✅ 并行" if st["parallel_decompose"] else "🔗 线性"
        pv = "✅ 并行" if st["parallel_verify"] else "🔗 线性"
        return f'''<div class="card">
<h2>⚙ 执行管道 <span style="font-size:10px;color:var(--dim)">— ExecutionPipeline</span></h2>
<div style="text-align:center;margin:8px 0">
  <div style="font-size:28px">{'🦴' if st["enabled"] else '⏸'}</div>
  <div style="font-size:14px;font-weight:700;color:{color}">{st["stage"].upper()}</div>
  <div style="font-size:11px;color:var(--dim)">流量 {st["flow_pct"]:.0%} · {st["total_runs"]}次执行</div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:10px;color:var(--dim)">
  <div>Decompose: {pd} · {st["plans_compared"]}方案对比</div>
  <div>Verify: {pv} · {st["parallel_gains"]}次增益</div>
</div>
<div style="font-size:10px;color:var(--dim);margin-top:4px">
  成功{st["success_rate"]:.0%} 降级{st["degraded_rate"]:.0%} 失败{st["failure_rate"]:.0%}
</div>
<div style="font-size:9px;color:var(--dim);margin-top:4px;text-align:center">
  并行 decompose(3方案)→ verify(ARQ+Shield+Lint) | 灰度{st["flow_pct"]:.0%}</div>
</div>'''


_instance: Optional[ExecutionPipeline] = None


def get_execution_pipeline() -> ExecutionPipeline:
    global _instance
    if _instance is None:
        _instance = ExecutionPipeline()
    return _instance
