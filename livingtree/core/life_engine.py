"""
LivingTree 生命引擎 (LifeEngine)
================================

数字生命体的中央调度器，以细胞Ai架构为骨架，
组织完整的任务链：感知 → 认知 → 规划 → 执行 → 反思

5 种核心细胞:
- PerceptionCell: 感知用户输入和环境变化
- MemoryCell:    记忆存取和知识管理
- ReasoningCell: 逻辑推理和决策
- LearningCell:  从经验中学习
- ActionCell:    执行具体操作
"""

import asyncio
import time
import uuid
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock

from ..infrastructure.config import get_config, LTAIConfig
from ..infrastructure.event_bus import get_event_bus, EVENTS, publish
from .observability.logger import get_logger
from .observability.tracer import get_tracer, TraceContext, Span
from .observability.metrics import get_metrics, MetricsCollector

# ── 子模块真实实现 ────────────────────────────────────────────
from .intent.parser import IntentParser as _RealIntentParser
from .intent.parser import IntentType as _RealIntentType
from .intent.parser import ParsedIntent as _RealParsedIntent
from .intent.parser import IntentTracker as _RealIntentTracker

from .planning.decomposer import TaskPlanner as _RealTaskPlanner
from .planning.decomposer import TaskDecomposer as _RealDecomposer
from .planning.decomposer import TaskScheduler as _RealScheduler
from .planning.decomposer import TaskNode as _RealTaskNode
from .planning.decomposer import TaskPlan as _RealTaskPlan
from .planning.decomposer import TaskStatus as _RealTaskStatus

from .model.router import (
    UnifiedModelRouter as _RealModelRouter,
    UnifiedModelClient as _RealModelClient,
    ComputeTier as _RealComputeTier,
    get_model_router as _get_router,
)

from .context.assembler import ContextAssembler as _RealContextAssembler
from .context.assembler import ContextCompressor as _RealContextCompressor

from .evolution.reflection import (
    EvolutionEngine as _RealEvolutionEngine,
    ExecutionRecord as _RealExecRecord,
    Reflector as _RealReflector,
)

from .memory.store import MemoryStore, MemoryQuery, MemoryItem, MemoryType
from .skills.matcher import SkillMatcher as _RealSkillMatcher
from .skills.matcher import SkillRepository as _RealSkillRepo


# ── LifeEngine 数据模型 ──────────────────────────────────────

class IntentType(Enum):
    CHAT = "chat"
    WRITING = "writing"
    CODE = "code"
    SEARCH = "search"
    ANALYSIS = "analysis"
    AUTOMATION = "automation"
    COMMAND = "command"
    FILE_OP = "file_operation"
    UNKNOWN = "unknown"


@dataclass
class Intent:
    type: IntentType = IntentType.UNKNOWN
    raw_text: str = ""
    entities: List[str] = field(default_factory=list)
    complexity: float = 0.0
    priority: int = 1
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Context:
    intent: Intent = field(default_factory=Intent)
    memories: List[Dict[str, Any]] = field(default_factory=list)
    knowledge: List[Dict[str, Any]] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    history_summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskNode:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    depth: int = 0
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"
    result: str = ""
    error: str = ""
    estimated_tokens: int = 0


@dataclass
class TaskPlan:
    steps: List[TaskNode] = field(default_factory=list)
    estimated_tokens: int = 0
    strategy: str = "sequential"
    fallback: str = ""


@dataclass
class ModelBinding:
    model: str = ""
    backend: str = "ollama"
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    output: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    duration_ms: float = 0.0
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    success: bool = True


@dataclass
class LearningRecord:
    insights: List[str] = field(default_factory=list)
    score: float = 0.0
    improvements: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Stimulus:
    user_input: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Response:
    text: str = ""
    result: ExecutionResult = field(default_factory=ExecutionResult)
    learning: LearningRecord = field(default_factory=LearningRecord)
    trace_id: str = ""


# ── 细胞基类 ──────────────────────────────────────────────────

class Cell:
    def __init__(self, name: str, engine: "LifeEngine"):
        self.name = name
        self.engine = engine
        self.logger = engine.logger
        self.config = engine.config

    async def process(self, *args, **kwargs) -> Any:
        raise NotImplementedError


class PerceptionCell(Cell):
    def __init__(self, engine: "LifeEngine"):
        super().__init__("perception", engine)

    async def perceive(self, stimulus: Stimulus) -> Intent:
        return await self.engine.intent_parser.parse(stimulus.user_input)


class MemoryCell(Cell):
    def __init__(self, engine: "LifeEngine"):
        super().__init__("memory", engine)

    async def retrieve(self, intent: Intent) -> List[Dict[str, Any]]:
        memories = []
        kb = self.engine._knowledge_store
        if kb:
            try:
                results = kb.search(intent.raw_text, limit=5)
                memories.extend(results)
            except Exception as e:
                self.logger.warn("memory_retrieve_failed", error=str(e))
        return memories

    async def archive(self, result: ExecutionResult, trace_id: str):
        publish(EVENTS["MEMORY_ARCHIVED"], {"trace_id": trace_id})


class ReasoningCell(Cell):
    def __init__(self, engine: "LifeEngine"):
        super().__init__("reasoning", engine)

    async def plan(self, intent: Intent, ctx: Context) -> TaskPlan:
        return await self.engine.task_planner.plan(intent, ctx)


class LearningCell(Cell):
    def __init__(self, engine: "LifeEngine"):
        super().__init__("learning", engine)

    async def reflect(self, result: ExecutionResult) -> LearningRecord:
        return await self.engine.evolution_engine.reflect(result)


class ActionCell(Cell):
    def __init__(self, engine: "LifeEngine"):
        super().__init__("action", engine)

    async def execute(self, plan: TaskPlan, model: ModelBinding,
                      ctx: Context) -> ExecutionResult:
        return await self.engine.execution_loop.run(plan, model, ctx)


# ── 适配器: LifeEngine Intent ↔ intent/parser ParsedIntent ──────

class AdaptedIntentParser:
    """将真实 IntentParser 适配到 LifeEngine 的 Intent 模型"""

    def __init__(self, engine: "LifeEngine"):
        self.engine = engine
        self._real = _RealIntentParser()
        self._tracker = _RealIntentTracker()

    async def parse(self, text: str) -> Intent:
        parsed = self._real.parse(text)
        self._tracker.track(parsed, text)

        return Intent(
            type=IntentType(parsed.type.value),
            raw_text=text,
            entities=parsed.entities,
            complexity=parsed.complexity,
            priority=parsed.priority,
            confidence=parsed.confidence,
        )


# ── 适配器: LifeEngine Context ↔ context/assembler AssembledContext

class AdaptedContextAssembler:
    def __init__(self, engine: "LifeEngine"):
        self.engine = engine
        self._real = _RealContextAssembler(MemoryStore())
        self._compressor = _RealContextCompressor()

    async def assemble(self, intent: Intent) -> Context:
        assembled = self._real.assemble(
            intent_type=intent.type.value,
            raw_text=intent.raw_text,
            complexity=intent.complexity,
        )

        ctx = Context(intent=intent)
        ctx.memories = assembled.memories
        ctx.knowledge = assembled.knowledge
        ctx.skills = assembled.skills
        ctx.tools = assembled.tools
        ctx.history_summary = assembled.history_summary
        return ctx


# ── 适配器: LifeEngine TaskPlan ↔ planning/decomposer TaskPlan ──

class AdaptedTaskPlanner:
    def __init__(self, engine: "LifeEngine"):
        self.engine = engine
        self._real = _RealTaskPlanner(max_depth=3, complexity_threshold=0.5)

    async def plan(self, intent: Intent, ctx: Context) -> TaskPlan:
        real_plan = self._real.plan(
            description=intent.raw_text,
            intent_type=intent.type.value,
            complexity=intent.complexity,
        )

        steps = []
        for rstep in real_plan.steps:
            steps.append(TaskNode(
                id=rstep.id,
                description=rstep.description,
                depth=rstep.depth,
                dependencies=rstep.dependencies,
                status=rstep.status.value,
                estimated_tokens=rstep.estimated_tokens,
            ))

        return TaskPlan(
            steps=steps,
            estimated_tokens=real_plan.estimated_total_tokens,
            strategy=real_plan.strategy,
        )


# ── 适配器: LifeEngine ModelBinding ↔ model/router UnifiedModelRouter

class AdaptedModelRouter:
    def __init__(self, engine: "LifeEngine"):
        self.engine = engine
        self._real = _get_router()

    async def route(self, plan: TaskPlan) -> ModelBinding:
        total_complexity = min(1.0, plan.estimated_tokens / 5000.0)

        description = "; ".join(s.description for s in plan.steps[:3])

        endpoint = self._real.route(
            task_description=description,
            complexity=total_complexity,
        )

        return ModelBinding(
            model=endpoint.model_name,
            backend=endpoint.tier.value,
            config={"tier": endpoint.tier.value, "endpoint": endpoint.endpoint},
        )


# ── 执行循环 ─────────────────────────────────────────────────

class AdaptedExecutionLoop:
    """执行循环: 遍历 TaskPlan 逐步执行, 支持 LLM 调用和工具调用"""

    def __init__(self, engine: "LifeEngine"):
        self.engine = engine

    async def run(self, plan: TaskPlan, model: ModelBinding,
                  ctx: Context) -> ExecutionResult:
        start = time.time()
        output_parts = []
        errors = []

        for step in plan.steps:
            if step.status in ("pending", "queued"):
                step.status = "in_progress"
                try:
                    part = await self._execute_step(step, model, ctx)
                    output_parts.append(part)
                    step.status = "completed"
                    step.result = part
                except Exception as e:
                    step.status = "failed"
                    step.error = str(e)
                    errors.append(str(e))

        return ExecutionResult(
            output="\n".join(output_parts),
            tokens_output=plan.estimated_tokens,
            duration_ms=(time.time() - start) * 1000,
            errors=errors,
            success=len(errors) == 0,
        )

    async def _execute_step(self, step: TaskNode, model: ModelBinding,
                            ctx: Context) -> str:
        llm = self.engine._llm_client
        if llm and hasattr(llm, "chat_sync"):
            prompt = step.description
            if ctx.memories:
                mem_text = "\n".join(
                    m.get("content", "")[:200] for m in ctx.memories[:3]
                )
                prompt = f"[上下文知识]\n{mem_text}\n\n[任务]\n{step.description}"
            resp = llm.chat_sync(prompt, model=model.model,
                                temperature=self.engine.config.agent.temperature,
                                max_tokens=self.engine.config.agent.max_tokens)
            return resp if isinstance(resp, str) else str(resp)

        if llm and hasattr(llm, "chat_async"):
            prompt = step.description
            resp = await llm.chat_async(prompt, model=model.model)
            return resp if isinstance(resp, str) else str(resp)

        return f"[{step.description}]: 配置 DeepSeek API Key 以启用真实推理"


# ── 适配器: LifeEngine LearningRecord ↔ evolution/reflection EvolutionEngine

class AdaptedEvolutionEngine:
    def __init__(self, engine: "LifeEngine"):
        self.engine = engine
        self._real = _RealEvolutionEngine()

    async def reflect(self, result: ExecutionResult) -> LearningRecord:
        record = _RealExecRecord(
            task_description="",
            success=result.success,
            duration_ms=result.duration_ms,
            tokens_used=result.tokens_input + result.tokens_output,
            errors=result.errors,
        )
        self._real.record_execution(record)

        if self._real.should_evolve():
            report = self._real.reflect()
            score = report.overall_score
            insights = report.patterns_found + report.suggested_improvements
            improvements = (
                report.common_errors[:3] if report.common_errors else []
            )
        else:
            score = 0.85 if result.success else 0.3
            insights = ["执行质量良好"] if result.success else result.errors
            improvements = []

        return LearningRecord(
            insights=insights,
            score=score,
            improvements=improvements,
        )


# ── 生命引擎 ─────────────────────────────────────────────────

class LifeEngine:
    """生命引擎 — 数字生命体的中央调度器

    完整任务链:
    Perception → Memory(检索) → Reasoning(规划) → Action(执行) → Memory(存储) → Learning(反思)
    """

    _instance: Optional["LifeEngine"] = None
    _lock = Lock()

    def __init__(self, config: Optional[LTAIConfig] = None):
        self.config = config or get_config()
        self.logger = get_logger("life_engine")
        self.tracer = get_tracer()
        self.metrics = get_metrics()
        self.event_bus = get_event_bus()

        # ── 核心组件 (真实实现适配) ──
        self.intent_parser = AdaptedIntentParser(self)
        self.context_assembler = AdaptedContextAssembler(self)
        self.task_planner = AdaptedTaskPlanner(self)
        self.model_router = AdaptedModelRouter(self)
        self.execution_loop = AdaptedExecutionLoop(self)
        self.evolution_engine = AdaptedEvolutionEngine(self)

        # ── 5 种核心细胞 ──
        self.cells: Dict[str, Cell] = {
            "perception": PerceptionCell(self),
            "reasoning": ReasoningCell(self),
            "memory": MemoryCell(self),
            "learning": LearningCell(self),
            "action": ActionCell(self),
        }

        # ── 外部注入接口 ──
        self._knowledge_store: Any = None
        self._skill_matcher: Any = None
        self._llm_client: Any = None

        self._started = False
        publish(EVENTS["SYSTEM_INITIALIZED"], {"version": self.config.version})
        self.logger.info("life_engine_initialized",
                         input_summary=f"LivingTree v{self.config.version}")

    @classmethod
    def get_instance(cls) -> "LifeEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── 生命周期 ──

    async def startup(self):
        """异步启动：完成初始化后调用."""
        if self._started:
            return
        self._started = True

        from .model.router import get_model_router
        router = get_model_router()
        try:
            await router.registry.start_health_checks()
        except Exception:
            pass

        if self._knowledge_store and hasattr(self._knowledge_store, "auto_maintain"):
            self._knowledge_store.auto_maintain()

        self.logger.info("life_engine_started", input_summary="LifeEngine startup complete")
        publish(EVENTS["SYSTEM_INITIALIZED"], {"version": self.config.version, "started": True})

    async def shutdown(self):
        """优雅关闭：释放资源."""
        self._started = False

        from .model.router import get_model_router
        router = get_model_router()
        try:
            await router.registry.stop_health_checks()
        except Exception:
            pass

        if self._knowledge_store and hasattr(self._knowledge_store, "cleanup_expired"):
            self._knowledge_store.cleanup_expired()

        self.logger.info("life_engine_shutdown", input_summary="LifeEngine shutdown complete")
        publish(EVENTS["SYSTEM_INITIALIZED"], {"version": self.config.version, "shutdown": True})

    # ── 外部注入 ──

    def inject_knowledge_store(self, store: Any):
        self._knowledge_store = store

    def inject_skill_matcher(self, matcher: Any):
        self._skill_matcher = matcher

    def inject_llm_client(self, client: Any):
        self._llm_client = client

    # ── 主入口 ──

    async def process(self, stimulus: Stimulus) -> Response:
        trace_ctx = self.tracer.start_trace()
        request_start = time.time()

        try:
            root_span = self.tracer.start_span(trace_ctx, "handle_request")

            # [1] 感知: 意图解析
            s1 = self.tracer.start_span(trace_ctx, "intent_parsing", root_span)
            intent = await self.intent_parser.parse(stimulus.user_input)
            self.tracer.end_span(s1,
                output_summary=f"type={intent.type.value} complexity={intent.complexity:.2f}")
            publish(EVENTS["INTENT_PARSED"],
                    {"type": intent.type.value, "complexity": intent.complexity})

            # [2] 认知: 上下文装配
            s2 = self.tracer.start_span(trace_ctx, "context_assembly", root_span)
            ctx = await self.context_assembler.assemble(intent)
            self.tracer.end_span(s2,
                output_summary=f"memories={len(ctx.memories)} skills={len(ctx.skills)}")
            publish(EVENTS["CONTEXT_ASSEMBLED"],
                    {"memories_count": len(ctx.memories)})

            # [3] 规划: 任务规划
            s3 = self.tracer.start_span(trace_ctx, "task_planning", root_span)
            task_plan = await self.task_planner.plan(intent, ctx)
            self.tracer.end_span(s3,
                output_summary=f"steps={len(task_plan.steps)} tokens={task_plan.estimated_tokens}")
            publish(EVENTS["TASK_PLANNED"],
                    {"steps_count": len(task_plan.steps)})

            # [4] 调度: 模型路由
            s4 = self.tracer.start_span(trace_ctx, "model_dispatch", root_span)
            model = await self.model_router.route(task_plan)
            self.tracer.end_span(s4, output_summary=f"model={model.model}")
            publish(EVENTS["MODEL_DISPATCHED"], {"model": model.model})

            # [5] 执行: 执行循环
            s5 = self.tracer.start_span(trace_ctx, "execution_loop", root_span)
            exec_result = await self.execution_loop.run(task_plan, model, ctx)
            self.tracer.end_span(s5,
                output_summary=f"success={exec_result.success} tokens={exec_result.tokens_output}")
            publish(EVENTS["EXECUTION_COMPLETED"],
                    {"success": exec_result.success})

            # [6] 学习: 反思归档
            s6 = self.tracer.start_span(trace_ctx, "reflection", root_span)
            learning = await self.evolution_engine.reflect(exec_result)
            self.tracer.end_span(s6, output_summary=f"score={learning.score:.2f}")
            publish(EVENTS["REFLECTION_ARCHIVED"], {"score": learning.score})

            mem_cell = self.cells.get("memory")
            if mem_cell:
                await mem_cell.archive(exec_result, trace_ctx.trace_id)

            self.metrics.record_request(
                success=exec_result.success,
                duration_ms=(time.time() - request_start) * 1000,
            )

            self.tracer.end_span(root_span, exec_result.success)
            self.tracer.end_trace(trace_ctx, exec_result.success)

            publish(EVENTS["REQUEST_COMPLETED"],
                    {"trace_id": trace_ctx.trace_id, "success": exec_result.success})

            return Response(
                text=exec_result.output,
                result=exec_result,
                learning=learning,
                trace_id=trace_ctx.trace_id,
            )

        except Exception as e:
            self.logger.error("process_failed", error=e)
            self.metrics.record_error(
                type("ErrorRecord", (), {
                    "module": "life_engine",
                    "error_type": type(e).__name__,
                    "message": str(e),
                    "level": "FATAL",
                })
            )
            self.tracer.end_trace(trace_ctx, success=False, error=str(e))
            publish(EVENTS["REQUEST_COMPLETED"],
                    {"trace_id": trace_ctx.trace_id, "success": False})
            raise

    # ── 同步入口 ──

    def handle_request(self, user_input: str) -> Response:
        stimulus = Stimulus(user_input=user_input)
        return asyncio.run(self.process(stimulus))

    async def process_stream(self, stimulus: Stimulus):
        """流式处理 — async generator 逐个步骤推送中间结果."""
        trace_ctx = self.tracer.start_trace()
        request_start = time.time()

        try:
            yield {"stage": "perceive", "status": "started"}
            intent = await self.intent_parser.parse(stimulus.user_input)
            yield {"stage": "perceive", "status": "completed",
                   "intent_type": intent.type.value, "complexity": intent.complexity}

            yield {"stage": "cognize", "status": "started"}
            ctx = await self.context_assembler.assemble(intent)
            yield {"stage": "cognize", "status": "completed",
                   "memories": len(ctx.memories), "skills": len(ctx.skills)}

            yield {"stage": "plan", "status": "started"}
            task_plan = await self.task_planner.plan(intent, ctx)
            yield {"stage": "plan", "status": "completed",
                   "steps": len(task_plan.steps), "tokens": task_plan.estimated_tokens}

            yield {"stage": "dispatch", "status": "started"}
            model = await self.model_router.route(task_plan)
            yield {"stage": "dispatch", "status": "completed",
                   "model": model.model, "tier": model.config.get("tier", "unknown")}

            yield {"stage": "execute", "status": "started"}
            exec_result = await self.execution_loop.run(task_plan, model, ctx)
            yield {"stage": "execute", "status": "completed",
                   "success": exec_result.success,
                   "output": exec_result.output[:500]}

            yield {"stage": "reflect", "status": "started"}
            learning = await self.evolution_engine.reflect(exec_result)
            yield {"stage": "reflect", "status": "completed",
                   "score": learning.score}

            mem_cell = self.cells.get("memory")
            if mem_cell:
                await mem_cell.archive(exec_result, trace_ctx.trace_id)

            self.metrics.record_request(
                success=exec_result.success,
                duration_ms=(time.time() - request_start) * 1000,
            )

            yield {"stage": "done", "response": exec_result.output,
                   "trace_id": trace_ctx.trace_id}

        except Exception as e:
            self.logger.error("process_stream_failed", error=e)
            self.tracer.end_trace(trace_ctx, success=False, error=str(e))
            yield {"stage": "error", "error": str(e),
                   "error_type": type(e).__name__}

    def handle_request_stream(self, user_input: str):
        """同步流式入口."""
        stimulus = Stimulus(user_input=user_input)
        stream = self.process_stream(stimulus)

        async def collect():
            results = []
            async for chunk in stream:
                results.append(chunk)
            return results

        return asyncio.run(collect())

    async def process_batch(self, inputs: List[str],
                            max_concurrent: int = 3) -> List[Response]:
        """批量处理."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_one(text: str) -> Response:
            async with semaphore:
                return await self.process(Stimulus(user_input=text))

        return await asyncio.gather(*[process_one(t) for t in inputs])

    # ── 状态查询 ──

    def get_health(self) -> Dict[str, Any]:
        health = {
            "version": self.config.version,
            "started": self._started,
            "config_loaded": bool(self.config.model_market.default_source),
            "cells": list(self.cells.keys()),
            "knowledge_store": self._knowledge_store is not None,
            "skill_matcher": self._skill_matcher is not None,
            "llm_client": self._llm_client is not None,
            "evolution_history": len(self.evolution_engine._real._history),
            "llm_status": self._check_llm_status(),
        }

        try:
            from .model.router import get_model_router
            router = get_model_router()
            health["model_router"] = router.get_stats()
        except Exception:
            health["model_router"] = "unavailable"

        try:
            if self._knowledge_store and hasattr(self._knowledge_store, "stats"):
                health["memory_store"] = self._knowledge_store.stats()
        except Exception:
            health["memory_store"] = "unavailable"

        try:
            health["metrics"] = self.metrics.get_snapshot()
        except Exception:
            health["metrics"] = "unavailable"

        return health

    def diagnose(self) -> Dict[str, Any]:
        """诊断报告 — 深度检查各子系统状态."""
        report = {"timestamp": datetime.now().isoformat(), "status": "healthy", "findings": []}

        packages = [
            ("config", "livingtree.infrastructure.config"),
            ("event_bus", "livingtree.infrastructure.event_bus"),
            ("model", "livingtree.core.model.router"),
            ("memory", "livingtree.core.memory.store"),
            ("intent", "livingtree.core.intent.parser"),
            ("planning", "livingtree.core.planning.decomposer"),
            ("evolution", "livingtree.core.evolution.reflection"),
            ("observability", "livingtree.core.observability.logger"),
        ]

        for name, module_path in packages:
            try:
                import importlib
                importlib.import_module(module_path)
                report["findings"].append({"module": name, "status": "ok"})
            except ImportError as e:
                report["findings"].append({"module": name, "status": "missing", "error": str(e)})
                report["status"] = "degraded"

        if self._llm_client is None:
            report["findings"].append({"module": "llm_client", "status": "not_injected",
                                        "hint": "调用 engine.inject_llm_client(client)"})
            report["status"] = "degraded"

        return report

    def _check_llm_status(self) -> str:
        if not self._llm_client:
            return "not_injected"
        if hasattr(self._llm_client, "available"):
            return "available" if self._llm_client.available else "unavailable"
        return "injected"


__all__ = [
    "LifeEngine",
    "Cell",
    "PerceptionCell", "MemoryCell", "ReasoningCell",
    "LearningCell", "ActionCell",
    "Intent", "IntentType", "Context",
    "TaskNode", "TaskPlan", "ModelBinding",
    "ExecutionResult", "LearningRecord",
    "Stimulus", "Response",
]
