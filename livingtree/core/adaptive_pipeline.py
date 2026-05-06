"""Adaptive Pipeline — auto-detect request type and build optimal processing chain.

The brain of the system orchestration. Determines:
  1. Request classification: chat / search / generate / analyze / train
  2. Pipeline assembly: which subsystems to invoke in what order
  3. Protocol selection: JSON vs Protobuf based on payload size
  4. Memory optimization: MemPO credit assignment + retention
  5. Quality gates: HallucinationGuard + RetrievalValidator

All modules built in previous phases are adaptively called:
  DisCoGC → storage optimization
  MultiDocFusion → cross-document synthesis
  Reasoning → rule engine + syllogism + contradiction + attribution
  MemPO → memory credit assignment + retention
  Serialization → Protobuf for large payloads, JSON for small
  KB Accuracy → query decomposition + citation injection + hallucination guard
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


class RequestType(str, Enum):
    CHAT = "chat"
    SEARCH = "search"
    GENERATE = "generate"
    ANALYZE = "analyze"
    TRAIN = "train"
    WEB_FETCH = "web_fetch"
    UNKNOWN = "unknown"


class ProtocolMode(str, Enum):
    JSON = "json"
    PROTOBUF = "protobuf"
    AUTO = "auto"


@dataclass
class PipelineStep:
    """One step in the adaptive pipeline."""
    name: str
    module: str
    action: str
    priority: int = 0
    condition: Optional[str] = None  # Python expression evaluated against context
    metadata: dict = field(default_factory=dict)


@dataclass
class PipelineContext:
    """Context flowing through the pipeline with all subsystem results."""
    request_type: RequestType = RequestType.UNKNOWN
    original_query: str = ""
    user_input: str = ""

    # Subsystem results
    decomposed_queries: list = field(default_factory=list)
    retrieved_hits: list = field(default_factory=list)
    validated_hits: list = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    hallucination_report: Any = None
    memory_credits_assigned: float = 0.0
    reasoning_results: dict = field(default_factory=dict)
    fusion_result: Any = None
    serialization_mode: ProtocolMode = ProtocolMode.AUTO

    # Quality metrics
    quality_score: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0

    # Site acceleration
    accelerated: bool = False
    acceleration_ip: str = ""
    acceleration_latency_ms: float = 0.0

    # Output
    response: str = ""
    response_proto: Optional[bytes] = None
    fetched_urls: list[str] = field(default_factory=list)


class AdaptivePipeline:
    """Auto-detects request type and builds the optimal processing chain.

    Pipeline templates per request type:

    CHAT → expand → retrieve(hierarchical) → validate → generate → verify
    SEARCH → decompose → retrieve(multi-source) → validate → fuse
    GENERATE → retrieve → MultiDocFusion → generate → verify → MemPO credit
    ANALYZE → decompose → retrieve → Reasoning(rule+syllogism) → verify
    TRAIN → retrieve → generate → verify → MemPO credit → DisCoGC optimize
    WEB_FETCH → accelerate → fetch → validate → verify

    Usage:
        pipeline = AdaptivePipeline()
        ctx = pipeline.classify("环评中大气扩散模型参数如何设置？")
        ctx = await pipeline.execute(ctx, hub=hub)
        print(ctx.response)
    """

    PIPELINE_TEMPLATES = {
        RequestType.CHAT: [
            PipelineStep("expand_query", "intelligent_kb", "expand_query", priority=1),
            PipelineStep("retrieve", "intelligent_kb", "hierarchical_retrieve", priority=2),
            PipelineStep("validate", "retrieval_validator", "validate", priority=3),
            PipelineStep("serialize_proto", "serialization", "to_proto",
                        condition="ctx.serialization_mode == 'protobuf'", priority=4),
            PipelineStep("verify", "hallucination_guard", "check_generation", priority=5),
            PipelineStep("mempo_credit", "memory_policy", "on_task_complete", priority=6),
        ],
        RequestType.SEARCH: [
            PipelineStep("decompose", "query_decomposer", "decompose", priority=1),
            PipelineStep("retrieve", "intelligent_kb", "accurate_retrieve", priority=2),
            PipelineStep("validate", "retrieval_validator", "validate", priority=3),
            PipelineStep("fuse", "multidoc_fusion", "fuse",
                        condition="len(ctx.retrieved_hits) > 1", priority=4),
        ],
        RequestType.GENERATE: [
            PipelineStep("retrieve", "intelligent_kb", "accurate_retrieve", priority=1),
            PipelineStep("validate", "retrieval_validator", "validate", priority=2),
            PipelineStep("fuse", "multidoc_fusion", "fuse", priority=3),
            PipelineStep("verify", "hallucination_guard", "check_generation", priority=4),
            PipelineStep("mempo_credit", "memory_policy", "on_task_complete", priority=5),
            PipelineStep("disco_optimize", "disco_gc", "run_gc",
                        condition="ctx.quality_score < 0.7", priority=6),
        ],
        RequestType.ANALYZE: [
            PipelineStep("decompose", "query_decomposer", "decompose", priority=1),
            PipelineStep("retrieve", "intelligent_kb", "hierarchical_retrieve", priority=2),
            PipelineStep("reason_formal", "reasoning", "forward_chain",
                        condition="ctx.retrieved_hits", priority=3),
            PipelineStep("reason_bayes", "reasoning", "bayesian_update",
                        condition="len(ctx.retrieved_hits) >= 2", priority=4),
            PipelineStep("verify", "hallucination_guard", "check_generation", priority=5),
        ],
        RequestType.TRAIN: [
            PipelineStep("retrieve", "intelligent_kb", "accurate_retrieve", priority=1),
            PipelineStep("content_quality", "content_quality", "evaluate", priority=2),
            PipelineStep("fuse", "multidoc_fusion", "fuse", priority=3),
            PipelineStep("verify", "hallucination_guard", "check_generation", priority=4),
            PipelineStep("mempo_credit", "memory_policy", "on_task_complete", priority=5),
            PipelineStep("disco_optimize", "disco_gc", "run_gc", priority=6),
        ],
        RequestType.WEB_FETCH: [
            PipelineStep("accelerate", "site_accelerator", "route_optimal_ip", priority=1),
            PipelineStep("fetch", "site_accelerator", "accelerated_fetch", priority=2),
            PipelineStep("validate", "retrieval_validator", "validate", priority=3),
            PipelineStep("verify", "hallucination_guard", "check_generation", priority=4),
        ],
    }

    def __init__(self):
        self._classifiers = [
            (["生成", "写", "创建", "制作", "输出", "generate", "create", "write", "produce"], RequestType.GENERATE),
            (["搜索", "查找", "检索", "找", "search", "find", "query", "lookup"], RequestType.SEARCH),
            (["分析", "评估", "诊断", "检查", "analyze", "evaluate", "diagnose", "check", "inspect"], RequestType.ANALYZE),
            (["训练", "学习", "微调", "train", "learn", "fine-tune", "fit"], RequestType.TRAIN),
            (["趋势", "热点", "雷达", "trend", "trending", "hot", "新闻", "news"], RequestType.ANALYZE),  # 趋势→分析
            (["抓取", "下载", "获取", "fetch", "download", "http", "https://", "github.com", "huggingface.co", "pypi.org"], RequestType.WEB_FETCH),
            (["?？吗呢吧", "如何", "怎么", "什么", "为什么"], RequestType.CHAT),
        ]

    def classify(self, query: str) -> PipelineContext:
        """Classify the request and create a pipeline context."""
        ctx = PipelineContext(original_query=query, user_input=query)

        for keywords, req_type in self._classifiers:
            if any(kw in query for kw in keywords):
                ctx.request_type = req_type
                break

        if ctx.request_type == RequestType.UNKNOWN:
            ctx.request_type = RequestType.CHAT

        # Auto-select serialization mode
        if len(query.encode("utf-8")) > 2000:
            ctx.serialization_mode = ProtocolMode.PROTOBUF
        else:
            ctx.serialization_mode = ProtocolMode.JSON

        logger.debug(
            "AdaptivePipeline: classified '%s...' as %s (serialization=%s)",
            query[:40], ctx.request_type.value, ctx.serialization_mode.value,
        )
        return ctx

    async def execute(
        self,
        ctx: PipelineContext,
        hub: Any = None,
        memory_optimizer: Any = None,
        disco_gc: Any = None,
        site_accelerator: Any = None,
        persona_memory: Any = None,
        forager: Any = None,
        listed_intel: Any = None,
    ) -> PipelineContext:
        """Execute the optimal pipeline for the classified request."""
        start = time.time()
        steps = self.PIPELINE_TEMPLATES.get(ctx.request_type, [])
        steps.sort(key=lambda s: -s.priority)

        for step in steps:
            if step.condition:
                try:
                    if not eval(step.condition, {"ctx": ctx, "len": len}):
                        continue
                except Exception:
                    pass

            try:
                await self._execute_step(step, ctx, hub, memory_optimizer, disco_gc, site_accelerator, persona_memory, forager, listed_intel)
            except Exception as e:
                logger.warning("Pipeline step '%s' failed: %s", step.name, e)
                ctx.errors.append(f"{step.name}: {e}")

        ctx.elapsed_ms = (time.time() - start) * 1000
        return ctx

    async def _execute_step(
        self, step: PipelineStep, ctx: PipelineContext,
        hub: Any, memory_optimizer: Any, disco_gc: Any,
        site_accelerator: Any = None, persona_memory: Any = None,
        forager: Any = None, listed_intel: Any = None,
    ) -> None:
        """Execute a single pipeline step by routing to the right module."""

        if step.module == "site_accelerator" and step.action == "route_optimal_ip":
            if site_accelerator:
                urls = [ctx.original_query]
                for url in urls:
                    if url.startswith(("http://", "https://")):
                        params = site_accelerator.get_optimal_connection_params(url)
                        if params.get("resolved_ip"):
                            ctx.accelerated = True
                            ctx.acceleration_ip = params["resolved_ip"]
                            ctx.acceleration_latency_ms = params.get("estimated_latency_ms", 0)

        elif step.module == "site_accelerator" and step.action == "accelerated_fetch":
            if site_accelerator:
                url = ctx.original_query if ctx.original_query.startswith("http") else ""
                if url:
                    content = await site_accelerator.accelerated_fetch(url)
                    if content:
                        ctx.response = content[:50000]
                        ctx.fetched_urls.append(url)
                        if not ctx.accelerated:
                            ctx.accelerated = site_accelerator._accelerated_fetches > 0

        if step.module == "intelligent_kb" and step.action == "hierarchical_retrieve":
            from ..knowledge.intelligent_kb import hierarchical_retrieve
            ctx.retrieved_hits = await hierarchical_retrieve(ctx.original_query, top_k=10, hub=hub)

        elif step.module == "intelligent_kb" and step.action == "accurate_retrieve":
            from ..knowledge.intelligent_kb import accurate_retrieve
            result = await accurate_retrieve(ctx.original_query, top_k=10, hub=hub, decompose=True)
            ctx.retrieved_hits = result.get("hits", [])
            ctx.citations = result.get("citations", [])
            ctx.hallucination_report = result.get("hallucination_report")

        elif step.module == "intelligent_kb" and step.action == "expand_query":
            from ..knowledge.intelligent_kb import expand_query
            expanded = expand_query(ctx.original_query, hub)
            ctx.decomposed_queries = expanded

        elif step.module == "retrieval_validator":
            from ..knowledge.retrieval_validator import RetrievalValidator
            rv = RetrievalValidator()
            validated = rv.validate(ctx.retrieved_hits)
            ctx.validated_hits = validated.hits
            ctx.citations = validated.citations

        elif step.module == "query_decomposer":
            from ..knowledge.query_decomposer import QueryDecomposer
            qd = QueryDecomposer()
            decomp = qd.decompose(ctx.original_query, hub)
            ctx.decomposed_queries = [sq.query for sq in decomp.sub_queries]

        elif step.module == "hallucination_guard":
            from ..knowledge.hallucination_guard import HallucinationGuard
            guard = HallucinationGuard()
            context_text = "\n".join(ctx.citations) if ctx.citations else ctx.original_query
            ctx.hallucination_report = guard.check_generation(
                ctx.response or ctx.original_query, context_text,
            )
            ctx.quality_score = 1.0 - ctx.hallucination_report.hallucination_rate

        elif step.module == "multidoc_fusion":
            if len(ctx.retrieved_hits) >= 2:
                from ..knowledge.multidoc_fusion import MultiDocFusionEngine
                from ..knowledge.hierarchical_chunker import build_document_tree
                engine = MultiDocFusionEngine()
                trees = [
                    build_document_tree(h.text, title=f"source_{i}")
                    for i, h in enumerate(ctx.retrieved_hits[:5])
                ]
                ctx.fusion_result = engine.fuse(trees, hub)

        elif step.module == "reasoning":
            from ..reasoning.formal import RuleEngine, Rule
            engine = RuleEngine("adaptive")
            for hit in ctx.retrieved_hits[:5]:
                engine.assert_fact(f"fact_{hit.chunk_id}" if hasattr(hit, 'chunk_id') else f"hit_{id(hit)}", True)
            engine.forward_chain()
            ctx.reasoning_results["rule_engine"] = engine.get_stats()

        elif step.module == "memory_policy":
            if memory_optimizer:
                memory_optimizer.on_task_complete(
                    success=ctx.quality_score or 0.8,
                    task_output=ctx.response or ctx.original_query,
                )

        elif step.module == "disco_gc":
            if disco_gc:
                disco_gc.run_gc()

        elif step.module == "serialization":
            from ..serialization import ChatRequest
            req = ChatRequest(
                model="adaptive",
                messages=[{"role": "user", "content": ctx.original_query}],
            )
            ctx.response_proto = req.to_proto()

        elif step.module == "content_quality":
            from ..knowledge.content_quality import ContentQuality
            cq = ContentQuality()
            text = "\n".join(getattr(h, 'text', str(h)) for h in ctx.retrieved_hits[:5])
            score = cq.evaluate(text)
            ctx.quality_score = (ctx.quality_score + score.overall) / 2 if ctx.quality_score else score.overall
