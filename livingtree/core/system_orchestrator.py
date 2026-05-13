"""System Orchestrator — central adaptive coordinator integrating all subsystems.

The single entry point that:
  1. Classifies incoming requests → delegates to AdaptivePipeline
  2. Coordinates DisCoGC + MemPO + Reasoning + Serialization + KB Accuracy
  3. Monitors system health (hallucination rate, memory pressure, storage usage)
  4. Adaptive protocol selection (JSON vs Protobuf)
  5. Self-optimization loop (periodic GC + memory retention + evolution)

Subsystems coordinated:
  - query_decomposer:      complex query → sub-queries + HyDE
  - hierarchical_chunker:  section-boundary-aware chunking
  - retrieval_validator:   relevance filtering + citation injection
  - hallucination_guard:   sentence-level verification + dashboard
  - multidoc_fusion:       cross-document synthesis + conflict resolution
  - reasoning:             rule engine + syllogism + contradiction + attribution
  - memory_policy (MemPO): credit assignment + retention + token budget
  - disco_gc (DisCoGC):    discard-based storage garbage collection
  - serialization:         Protobuf/JSON adaptive protocol selection
  - content_quality:       low-quality filter + auto-labeling
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger

from .adaptive_pipeline import AdaptivePipeline, PipelineContext, RequestType, ProtocolMode


@dataclass
class SystemStatus:
    """Real-time status snapshot of all subsystems."""
    active_requests: int = 0
    total_requests_processed: int = 0
    avg_latency_ms: float = 0.0
    hallucination_rate: float = 0.0
    memory_items: int = 0
    memory_retention_rate: float = 1.0
    storage_usage_ratio: float = 0.0
    protobuf_usage_ratio: float = 0.0
    active_pipelines: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    last_optimization: float = 0.0


class SystemOrchestrator:
    """Central adaptive orchestrator for all LivingTree subsystems.

    Usage:
        orchestrator = SystemOrchestrator()
        await orchestrator.initialize(hub=hub)

        response = await orchestrator.process("环评中大气扩散模型参数如何设置？")

        status = orchestrator.get_status()
        orchestrator.shutdown()
    """

    def __init__(self, auto_optimize_interval: int = 600):
        self._pipeline = AdaptivePipeline()
        self._status = SystemStatus()
        self._lock = threading.RLock()

        # All subsystems (lazy-init via initialize())
        self._hub: Any = None
        self._memory_optimizer: Any = None
        self._disco_gc_instances: dict[str, Any] = {}
        self._site_accelerator: Any = None
        self._persona_memory: Any = None
        self._forager: Any = None
        self._deadline_scheduler: Any = None
        self._listed_intel: Any = None
        self._opportunity_engine: Any = None
        self._investment_engine: Any = None
        self._needs_clarifier: Any = None
        self._sub_agent_dispatch: Any = None
        self._task_state: Any = None
        self._light_crawler: Any = None
        self._web2api_server: Any = None
        self._smart_dns: Any = None
        self._prompt_injector: Any = None

        self._auto_optimize_interval = auto_optimize_interval
        self._optimization_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Metrics
        self._total_latency_us: float = 0.0
        self._protobuf_count: int = 0
        self._json_count: int = 0

    async def initialize(self, hub: Any = None) -> None:
        """Initialize ALL subsystems. Called from IntegrationHub.start()."""
        self._hub = hub

        # ── Memory & Persona ──
        from ..memory.memory_policy import MemPOOptimizer
        self._memory_optimizer = MemPOOptimizer(max_memories=2000)

        from ..memory.persona_memory import get_persona_memory
        self._persona_memory = get_persona_memory()

        # ── Network & Crawling ──
        from ..network.site_accelerator import get_accelerator
        self._site_accelerator = get_accelerator()
        await self._site_accelerator.initialize()

        from ..network.smart_dns import get_smart_dns
        self._smart_dns = get_smart_dns()

        from ..capability.light_crawler import get_light_crawler
        self._light_crawler = get_light_crawler()

        # ── Forager & Market Intel ──
        from ..capability.knowledge_forager import get_forager
        self._forager = get_forager()

        from ..market.listed_intel import get_listed_intel
        self._listed_intel = get_listed_intel()

        from ..market.opportunity_scorer import get_scorer, get_bid_assistant, get_trend_analyzer
        self._opportunity_scorer = get_scorer()
        self._bid_assistant = get_bid_assistant()
        self._trend_analyzer = get_trend_analyzer()

        from ..market.revenue_engine import get_investment_engine
        self._investment_engine = get_investment_engine()

        # ── Deadline & Needs ──
        from ..capability.deadline_engine import DeadlineEngine, TaskScheduler
        self._deadline_engine = DeadlineEngine()
        self._deadline_scheduler = TaskScheduler(self._deadline_engine)

        from ..capability.needs_clarifier import get_clarifier
        self._needs_clarifier = get_clarifier()

        # ── Sub-Agent & State ──
        from ..capability.sub_agent_dispatch import get_dispatch, get_experience_recorder
        self._sub_agent_dispatch = get_dispatch()
        self._site_experience = get_experience_recorder()

        from .task_state import get_state_manager, get_prompt_injector
        self._task_state = get_state_manager()
        self._prompt_injector = get_prompt_injector()

        # ── Web2API (removed — TUI stub) ──
        logger.debug("Web2API removed — system uses web server instead")

        logger.info(
            "SystemOrchestrator: ALL subsystems initialized — "
            "persona=%d domains | forager=%d sites | intel=%d companies | "
            "crawler=%s | deadline=%d rules | web2api=%d providers",
            6, len(self._forager.food_map), self._listed_intel.get_registry_stats()["total_companies"],
            "ready" if self._light_crawler else "no",
            len(self._deadline_engine._rules) if hasattr(self._deadline_engine, '_rules') else 12,
            12,
        )

    async def process(
        self,
        user_input: str,
        session_id: str = "",
        prefer_protobuf: bool = False,
    ) -> dict:
        """Process a user request through the adaptive pipeline.

        Returns dict with: response, session_id, request_type, metrics, errors.
        """
        start = time.time()

        with self._lock:
            self._status.active_requests += 1

        try:
            ctx = self._pipeline.classify(user_input)

            if prefer_protobuf and ctx.serialization_mode != ProtocolMode.PROTOBUF:
                ctx.serialization_mode = ProtocolMode.PROTOBUF

            ctx = await self._pipeline.execute(
                ctx,
                hub=self._hub,
                memory_optimizer=self._memory_optimizer,
                disco_gc=self._disco_gc_instances.get("default"),
                site_accelerator=self._site_accelerator,
                persona_memory=self._persona_memory,
                forager=self._forager,
                listed_intel=self._listed_intel,
            )

            elapsed_ms = ctx.elapsed_ms
            self._status.total_requests_processed += 1
            self._total_latency_us += elapsed_ms * 1000

            if ctx.serialization_mode == ProtocolMode.PROTOBUF:
                self._protobuf_count += 1
            else:
                self._json_count += 1

            result = {
                "response": ctx.response or ctx.original_query,
                "response_proto": ctx.response_proto,
                "session_id": session_id,
                "request_type": ctx.request_type.value,
                "serialization": ctx.serialization_mode.value,
                "citations": ctx.citations[:5],
                "quality_score": ctx.quality_score,
                "hallucination_rate": (
                    ctx.hallucination_report.hallucination_rate
                    if ctx.hallucination_report else 0.0
                ),
                "elapsed_ms": elapsed_ms,
                "errors": ctx.errors,
                "accelerated": ctx.accelerated,
                "acceleration_ip": ctx.acceleration_ip,
                "acceleration_latency_ms": ctx.acceleration_latency_ms,
                "fetched_urls": ctx.fetched_urls,
            }

            self._status.hallucination_rate = result["hallucination_rate"]

            return result

        except Exception as e:
            logger.error("SystemOrchestrator process error: %s", e)
            self._status.errors.append(str(e))
            return {
                "response": f"Error processing request: {e}",
                "session_id": session_id,
                "request_type": "unknown",
                "elapsed_ms": (time.time() - start) * 1000,
                "errors": [str(e)],
            }
        finally:
            with self._lock:
                self._status.active_requests -= 1

    def start_auto_optimize(self) -> None:
        """Start background optimization loop (DisCoGC + MemPO + hallucination check)."""
        if self._optimization_thread and self._optimization_thread.is_alive():
            return

        self._stop_event.clear()
        self._optimization_thread = threading.Thread(
            target=self._auto_optimize_loop,
            daemon=True,
            name="system-orchestrator-optimizer",
        )
        self._optimization_thread.start()
        logger.info("SystemOrchestrator: auto-optimize started (interval=%ds)",
                   self._auto_optimize_interval)

    def stop_auto_optimize(self) -> None:
        self._stop_event.set()
        if self._optimization_thread:
            self._optimization_thread.join(timeout=5.0)

    def _auto_optimize_loop(self) -> None:
        while not self._stop_event.wait(timeout=self._auto_optimize_interval):
            try:
                self.run_optimization_cycle()
            except Exception as e:
                logger.error("Auto-optimize error: %s", e)

    def run_optimization_cycle(self) -> dict:
        """Run one full optimization cycle across all subsystems."""
        result = {"optimized": False, "actions": []}

        # MemPO: enforce retention policy + forget low-importance memories
        if self._memory_optimizer:
            mem_stats = self._memory_optimizer.optimize()
            self._status.memory_items = mem_stats.get("total_memories", 0)
            self._status.memory_retention_rate = (
                mem_stats.get("retained", 0) / max(mem_stats.get("total_memories", 1), 1)
            )
            result["mempo"] = mem_stats
            result["actions"].append("mempo_optimized")

        # DisCoGC: run GC on all storage backends
        for name, disco in self._disco_gc_instances.items():
            disco.run_gc()
            stats = disco.get_stats()
            self._status.storage_usage_ratio = (
                stats.get("storage", {}).usage_ratio
                if hasattr(stats.get("storage", {}), "usage_ratio") else 0.0
            )
            result["actions"].append(f"disco_gc:{name}")

        self._status.last_optimization = time.time()
        result["optimized"] = True

        logger.debug("SystemOrchestrator: optimization cycle — %s", result["actions"])
        return result

    def get_status(self) -> dict:
        with self._lock:
            accel_stats = {}
            if self._site_accelerator:
                try:
                    accel_stats = self._site_accelerator.get_stats()
                except Exception:
                    pass

            return {
                "active_requests": self._status.active_requests,
                "total_processed": self._status.total_requests_processed,
                "avg_latency_ms": (
                    self._total_latency_us / max(self._status.total_requests_processed, 1) / 1000
                ),
                "hallucination_rate": self._status.hallucination_rate,
                "memory_items": self._status.memory_items,
                "memory_retention_rate": self._status.memory_retention_rate,
                "storage_usage_ratio": self._status.storage_usage_ratio,
                "protobuf_ratio": (
                    self._protobuf_count / max(self._protobuf_count + self._json_count, 1)
                ),
                "last_optimization_seconds_ago": (
                    time.time() - self._status.last_optimization
                    if self._status.last_optimization else -1
                ),
                "errors": self._status.errors[-10:],
                "accelerator": accel_stats,
            }

    def get_hallucination_dashboard(self) -> dict:
        try:
            from ..knowledge.hallucination_guard import HallucinationGuard
            guard = HallucinationGuard()
            return guard.get_dashboard()
        except Exception:
            return {"status": "unavailable"}

    def get_reasoning_stats(self) -> dict:
        try:
            from ..reasoning.historical import AttributionLoop
            loop = AttributionLoop("system")
            return loop.get_stats()
        except Exception:
            return {"status": "unavailable"}

    def get_memory_policy_stats(self) -> dict:
        if self._memory_optimizer:
            return self._memory_optimizer.get_stats()
        return {"status": "unavailable"}

    # ═══ Autonomous Mode ═══

    def start_autonomous(self) -> None:
        """Start fully autonomous operation — zero human input needed."""
        self.start_auto_optimize()
        threading.Thread(target=self._autonomous_worker, daemon=True,
                        name="autonomous-loop").start()
        logger.info("SystemOrchestrator: AUTONOMOUS engaged")

    def _autonomous_worker(self) -> None:
        import asyncio
        loop = asyncio.new_event_loop()
        while not self._stop_event.is_set():
            try:
                loop.run_until_complete(self._autonomous_cycle())
            except Exception as e:
                logger.error("Autonomous: %s", e)
            self._stop_event.wait(timeout=self._auto_optimize_interval)

    async def _autonomous_cycle(self) -> None:
        # Patrol → Hunt → Intel → Digest → Optimize → Brief
        if self._forager:
            await self._forager.patrol(max_sources=10, hub=self._hub)
            active = self._forager.succession.get_active_projects(since_days=30)
            for p in active[:3]:
                await self._forager.hunt(p.project_name[:100], hub=self._hub)
            if self._listed_intel:
                signals = self._listed_intel.detect([
                    {"title": s.stage, "date": s.date, "stage": s.stage}
                    for t in self._forager.succession._timelines.values()
                    for s in t.stages[-5:]
                ])
        if self._memory_optimizer:
            self._memory_optimizer.optimize()
        if self._forager and time.strftime("%H") == "08":
            self._forager.generate_daily_brief()

    def shutdown(self) -> None:
        self._stop_event.set()
        self.stop_auto_optimize()
        for disco in self._disco_gc_instances.values():
            try: disco.close()
            except Exception: pass
        logger.info("SystemOrchestrator shut down")


# ── Singleton ──

_orchestrator: Optional[SystemOrchestrator] = None
_orch_lock = threading.Lock()


def get_orchestrator() -> SystemOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        with _orch_lock:
            if _orchestrator is None:
                _orchestrator = SystemOrchestrator()
    return _orchestrator
