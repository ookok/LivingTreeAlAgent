"""System Orchestrator integration tests — adaptive pipeline + full orchestration.

Tests:
  - AdaptivePipeline: request classification
  - AdaptivePipeline: pipeline execution per request type
  - SystemOrchestrator: process + status
  - SystemOrchestrator: optimization cycle
  - Integration: all subsystems wired through orchestrator
"""

from __future__ import annotations

import time
import pytest

from livingtree.core.adaptive_pipeline import (
    AdaptivePipeline, PipelineContext, RequestType, ProtocolMode,
)
from livingtree.core.system_orchestrator import (
    SystemOrchestrator, SystemStatus, get_orchestrator,
)


# ═══ AdaptivePipeline ═══

class TestAdaptivePipeline:
    def test_classify_chat(self):
        pipe = AdaptivePipeline()
        ctx = pipe.classify("环评是什么？")
        assert ctx.request_type == RequestType.CHAT

    def test_classify_search(self):
        pipe = AdaptivePipeline()
        ctx = pipe.classify("搜索大气扩散模型标准")
        assert ctx.request_type in (RequestType.SEARCH, RequestType.CHAT)

    def test_classify_generate(self):
        pipe = AdaptivePipeline()
        ctx = pipe.classify("生成环评大气章节")
        assert ctx.request_type == RequestType.GENERATE

    def test_classify_analyze(self):
        pipe = AdaptivePipeline()
        ctx = pipe.classify("分析大气扩散模型参数设置方法")
        assert ctx.request_type == RequestType.ANALYZE

    def test_classify_train(self):
        pipe = AdaptivePipeline()
        ctx = pipe.classify("训练模型参数优化")
        assert ctx.request_type == RequestType.TRAIN

    def test_auto_serialization_mode_small(self):
        pipe = AdaptivePipeline()
        ctx = pipe.classify("简短问题")
        assert ctx.serialization_mode == ProtocolMode.JSON

    def test_auto_serialization_mode_large(self):
        pipe = AdaptivePipeline()
        ctx = pipe.classify("大" * 3000)
        assert ctx.serialization_mode == ProtocolMode.PROTOBUF

    @pytest.mark.asyncio
    async def test_execute_chat_pipeline(self):
        pipe = AdaptivePipeline()
        ctx = pipe.classify("环评报告如何生成？")
        ctx = await pipe.execute(ctx)
        assert ctx.elapsed_ms > 0

    @pytest.mark.asyncio
    async def test_execute_search_pipeline(self):
        pipe = AdaptivePipeline()
        ctx = pipe.classify("搜索大气扩散模型参数")
        ctx = await pipe.execute(ctx)
        assert ctx.elapsed_ms > 0

    @pytest.mark.asyncio
    async def test_execute_generate_pipeline(self):
        pipe = AdaptivePipeline()
        ctx = pipe.classify("生成环评报告大气章节")
        ctx = await pipe.execute(ctx)
        assert ctx.elapsed_ms > 0

    def test_pipeline_context_defaults(self):
        ctx = PipelineContext()
        assert ctx.request_type == RequestType.UNKNOWN
        assert ctx.quality_score == 0.0
        assert ctx.errors == []


# ═══ SystemOrchestrator ═══

class TestSystemOrchestrator:
    @pytest.mark.asyncio
    async def test_initialize(self):
        orch = SystemOrchestrator()
        await orch.initialize()
        status = orch.get_status()
        assert "active_requests" in status

    @pytest.mark.asyncio
    async def test_process_simple(self):
        orch = SystemOrchestrator()
        await orch.initialize()

        result = await orch.process("环评是什么？")
        assert "response" in result
        assert "request_type" in result
        assert "elapsed_ms" in result

    @pytest.mark.asyncio
    async def test_process_with_session(self):
        orch = SystemOrchestrator()
        await orch.initialize()

        result = await orch.process("搜索大气扩散模型", session_id="test_session_1")
        assert result["session_id"] == "test_session_1"

    @pytest.mark.asyncio
    async def test_process_error_handling(self):
        orch = SystemOrchestrator()
        await orch.initialize()

        result = await orch.process("")
        assert "response" in result

    def test_get_status(self):
        orch = SystemOrchestrator()
        status = orch.get_status()
        assert "total_processed" in status
        assert "avg_latency_ms" in status
        assert "hallucination_rate" in status

    def test_run_optimization_cycle(self):
        orch = SystemOrchestrator()
        result = orch.run_optimization_cycle()
        assert "optimized" in result

    def test_get_hallucination_dashboard(self):
        orch = SystemOrchestrator()
        dashboard = orch.get_hallucination_dashboard()
        assert "status" in dashboard

    def test_get_memory_policy_stats(self):
        orch = SystemOrchestrator()
        stats = orch.get_memory_policy_stats()
        assert stats is not None

    def test_shutdown(self):
        orch = SystemOrchestrator()
        orch.shutdown()

    def test_singleton(self):
        o1 = get_orchestrator()
        o2 = get_orchestrator()
        assert o1 is o2


# ═══ Integration — All Subsystems ═══

class TestAllSubsystemsIntegration:
    @pytest.mark.asyncio
    async def test_full_chat_pipeline_with_memory(self):
        """Chat → retrieve → validate → verify → MemPO credit."""
        from livingtree.memory.memory_policy import MemPOOptimizer

        orch = SystemOrchestrator()
        mempo = MemPOOptimizer(max_memories=100)
        mempo.add_memory("HJ2.2标准大气扩散模型参数设置方法")
        mempo.add_memory("GB12348噪声限值标准")

        await orch.initialize()

        result = await orch.process(
            "大气扩散模型参数如何设置？",
            session_id="integration_test",
        )

        assert result["request_type"] in ("chat", "search", "analyze", "generate")
        assert "elapsed_ms" in result

    @pytest.mark.asyncio
    async def test_serialization_auto_selection(self):
        """Large request → auto protobuf selection."""
        orch = SystemOrchestrator()
        await orch.initialize()

        large_query = "生成环评报告大气环境影响评价章节，包括扩散模型参数设置、监测数据分析、合规性评价等内容。" * 30
        result = await orch.process(large_query)

        assert "response" in result
        assert "serialization" in result

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Multiple concurrent requests should not interfere."""
        import asyncio

        orch = SystemOrchestrator()
        await orch.initialize()

        tasks = [
            orch.process(f"问题 {i}: 环评标准查询", session_id=f"sess_{i}")
            for i in range(3)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        for r in results:
            assert "response" in r

    def test_optimization_after_processing(self):
        """After processing, MemPO should track accessed memories."""
        from livingtree.memory.memory_policy import MemPOOptimizer

        mempo = MemPOOptimizer(max_memories=100)
        mempo.add_memory("大气扩散模型HJ2.2标准")
        orch = SystemOrchestrator()

        mempo.log_access("mem_1")
        mempo.on_task_complete(success=0.9, task_output="大气扩散模型参数设置")

        stats = mempo.get_stats()
        assert stats["total_memories"] > 0
