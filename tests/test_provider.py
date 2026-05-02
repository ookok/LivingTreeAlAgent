# -*- coding: utf-8 -*-
"""
tests/test_provider.py — Provider 模块完整测试

覆盖：
  1. base.py 数据模型
  2. 三种驱动（HardLoad / LocalService / Cloud）
  3. Gateway 路由与调用
  4. FaultTolerance 熔断与降级
  5. Monitor 资源监控
  6. ConfigManager 配置管理
"""

import json
import os
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# ── 确保 provider 包可导入 ──────────────────────────────────────

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from livingtree.core.provider.base import (
    DriverMode, DriverState,
    ChatMessage, ChatRequest, ChatResponse,
    CompletionRequest, CompletionResponse,
    EmbeddingRequest, EmbeddingResponse,
    StreamChunk, UsageInfo,
    HealthReport, ModelDriver,
)
from livingtree.core.provider.gateway import ModelGateway, RouteStrategy
from livingtree.core.provider.fault_tolerance import (
    FaultToleranceManager, DegradationStrategy,
    CircuitBreaker, CircuitState,
)
from livingtree.core.provider.monitor import ResourceMonitor, ResourceSnapshot, AppMetrics
from livingtree.core.provider.config_manager import (
    ProviderConfigManager, ProviderConfig,
    ModelSlotConfig, ABTestConfig,
)


# ═══════════════════════════════════════════════════════════════
# 1. 基础数据模型测试
# ═══════════════════════════════════════════════════════════════

class TestBaseModels:
    """base.py 数据模型"""

    def test_driver_mode_enum(self):
        assert DriverMode.HARD_LOAD.value == "hard_load"
        assert DriverMode.LOCAL_SERVICE.value == "local_service"
        assert DriverMode.CLOUD_SERVICE.value == "cloud_service"

    def test_driver_state_enum(self):
        assert DriverState.UNINITIALIZED.value == "uninitialized"
        assert DriverState.READY.value == "ready"
        assert DriverState.ERROR.value == "error"

    def test_chat_message(self):
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.name is None
        assert msg.tool_calls is None

    def test_chat_request_defaults(self):
        req = ChatRequest(messages=[ChatMessage(role="user", content="Hi")])
        assert len(req.messages) == 1
        assert req.temperature == 0.7
        assert req.max_tokens == 2048
        assert req.stream == True
        assert req.tools is None

    def test_chat_response_defaults(self):
        resp = ChatResponse()
        assert resp.content == ""
        assert resp.error == ""
        assert resp.usage.total_tokens == 0
        assert resp.model == ""

    def test_stream_chunk(self):
        chunk = StreamChunk(delta="Hello", done=False)
        assert chunk.delta == "Hello"
        assert chunk.done is False
        assert chunk.error == ""
        assert chunk.reasoning == ""

    def test_usage_info(self):
        usage = UsageInfo(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        assert usage.total_tokens == 30

    def test_completion_request(self):
        req = CompletionRequest(prompt="Complete this")
        assert req.prompt == "Complete this"
        assert req.temperature == 0.7
        assert req.stream is True

    def test_embedding_request(self):
        req = EmbeddingRequest(texts=["hello", "world"])
        assert len(req.texts) == 2
        assert req.encoding_format == "float"

    def test_health_report(self):
        report = HealthReport(healthy=True, state=DriverState.READY)
        assert report.healthy is True
        assert report.latency_ms == 0.0
        assert report.error_count == 0


# ═══════════════════════════════════════════════════════════════
# 2. Mock 驱动器（用于 Gateway/FaultTolerance 测试）
# ═══════════════════════════════════════════════════════════════

class MockDriver(ModelDriver):
    """模拟驱动器，用于测试"""

    def __init__(self, name: str, mode: DriverMode, healthy: bool = True):
        super().__init__(name, mode)
        self._should_be_healthy = healthy
        self._chat_history: List[ChatRequest] = []

    def initialize(self) -> bool:
        if self._should_be_healthy:
            self._set_state(DriverState.READY)
            return True
        self._set_state(DriverState.ERROR)
        self._record_error("simulated failure")
        return False

    def shutdown(self) -> None:
        self._set_state(DriverState.UNLOADED)

    def health_check(self) -> HealthReport:
        return self._build_health({"mock": True})

    def chat(self, request: ChatRequest) -> ChatResponse:
        self._chat_history.append(request)
        if not self._should_be_healthy:
            self._record_error("mock error")
            return ChatResponse(error="mock error")
        self._record_success(10.0)
        return ChatResponse(
            content=f"Response from {self.name}",
            model=request.model or "mock",
            usage=UsageInfo(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )

    def chat_stream(self, request: ChatRequest) -> Iterator[StreamChunk]:
        if not self._should_be_healthy:
            yield StreamChunk(error="mock error", done=True)
            return
        yield StreamChunk(delta=f"Hello from {self.name}", done=False)
        yield StreamChunk(done=True)

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(text=f"Completed by {self.name}")

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        return EmbeddingResponse(
            embeddings=[[0.1] * 10 for _ in request.texts],
            model="mock",
        )

    def list_models(self) -> List[Dict[str, Any]]:
        return [{"id": "mock-model", "driver": self.name}]

    def is_model_loaded(self, model: str) -> bool:
        return model == "mock-model" or model == ""


# ═══════════════════════════════════════════════════════════════
# 3. Gateway 测试
# ═══════════════════════════════════════════════════════════════

class TestModelGateway:
    """ModelGateway 测试"""

    def _make_gateway(self) -> ModelGateway:
        gw = ModelGateway("test")
        # 注册三种模式的驱动
        gw.register_driver(
            MockDriver("hard1", DriverMode.HARD_LOAD),
            models=["model-a"],
            priority=200,
        )
        gw.register_driver(
            MockDriver("local1", DriverMode.LOCAL_SERVICE),
            models=["model-a", "model-b"],
            priority=100,
        )
        gw.register_driver(
            MockDriver("cloud1", DriverMode.CLOUD_SERVICE),
            models=["model-a", "model-b", "model-c"],
            priority=50,
        )
        return gw

    def test_register_drivers(self):
        gw = self._make_gateway()
        assert len(gw.drivers) == 3
        assert "hard1" in gw.drivers
        assert "local1" in gw.drivers
        assert "cloud1" in gw.drivers

    def test_initialize(self):
        gw = self._make_gateway()
        ok = gw.initialize()
        assert ok is True
        assert gw.is_initialized

    def test_chat_routes_to_correct_driver(self):
        gw = self._make_gateway()
        gw.initialize()
        req = ChatRequest(messages=[ChatMessage(role="user", content="Hi")], model="model-a")
        resp = gw.chat(req)
        assert not resp.error
        assert resp.content  # 应该有内容

    def test_chat_without_model(self):
        gw = self._make_gateway()
        gw.initialize()
        req = ChatRequest(messages=[ChatMessage(role="user", content="Hi")])
        resp = gw.chat(req)
        assert not resp.error

    def test_chat_stream(self):
        gw = self._make_gateway()
        gw.initialize()
        req = ChatRequest(messages=[ChatMessage(role="user", content="Hi")])
        chunks = list(gw.chat_stream(req))
        assert len(chunks) >= 2
        assert chunks[-1].done is True

    def test_complete(self):
        gw = self._make_gateway()
        gw.initialize()
        req = CompletionRequest(prompt="Hello")
        resp = gw.complete(req)
        assert resp.text

    def test_embed(self):
        gw = self._make_gateway()
        gw.initialize()
        req = EmbeddingRequest(texts=["hello"])
        resp = gw.embed(req)
        assert len(resp.embeddings) == 1
        assert len(resp.embeddings[0]) == 10

    def test_chat_batch(self):
        gw = self._make_gateway()
        gw.initialize()
        reqs = [
            ChatRequest(messages=[ChatMessage(role="user", content=f"Msg {i}")])
            for i in range(3)
        ]
        resps = gw.chat_batch(reqs)
        assert len(resps) == 3
        for r in resps:
            assert not r.error

    def test_health_check(self):
        gw = self._make_gateway()
        gw.initialize()
        reports = gw.health_check()
        assert len(reports) == 3
        for name, report in reports.items():
            assert report.healthy is True

    def test_list_all_models(self):
        gw = self._make_gateway()
        gw.initialize()
        models = gw.list_all_models()
        assert len(models) >= 1
        # 每个模型应该有 driver 和 mode 字段
        for m in models:
            assert "driver" in m
            assert "mode" in m

    def test_unregister_driver(self):
        gw = self._make_gateway()
        gw.initialize()
        gw.unregister_driver("cloud1")
        assert "cloud1" not in gw.drivers
        assert len(gw.drivers) == 2

    def test_set_default_mode(self):
        gw = self._make_gateway()
        gw.set_default_mode(DriverMode.HARD_LOAD)
        assert gw._default_mode == DriverMode.HARD_LOAD

    def test_warmup(self):
        gw = self._make_gateway()
        gw.initialize()
        ok = gw.warmup(model="model-a")
        assert ok is True

    def test_shutdown(self):
        gw = self._make_gateway()
        gw.initialize()
        gw.shutdown()
        assert not gw.is_initialized
        # 所有驱动应该处于 UNLOADED 状态
        for d in gw.drivers.values():
            assert d.state == DriverState.UNLOADED

    def test_mode_fallback(self):
        """测试模式降级：cloud 不可用时，应路由到 local"""
        gw = ModelGateway("test-fallback")
        cloud = MockDriver("cloud-fail", DriverMode.CLOUD_SERVICE, healthy=False)
        gw.register_driver(cloud, models=["model-x"], priority=200)
        gw.register_driver(
            MockDriver("local-ok", DriverMode.LOCAL_SERVICE),
            models=["model-x"],
            priority=100,
        )
        gw.initialize()
        # cloud 应该 ERROR，local 应该 READY
        assert cloud.state == DriverState.ERROR
        req = ChatRequest(messages=[ChatMessage(role="user", content="Hi")], model="model-x")
        resp = gw.chat(req)
        assert not resp.error  # 应该路由到 local-ok


# ═══════════════════════════════════════════════════════════════
# 4. FaultTolerance 测试
# ═══════════════════════════════════════════════════════════════

class TestFaultTolerance:
    """故障容错测试"""

    def test_circuit_breaker_states(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

        # 连续失败 3 次应熔断
        for i in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_open is True
        assert cb.allow_request() is False

    def test_circuit_breaker_half_open(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # 等待恢复
        time.sleep(0.02)
        assert cb.is_open is False  # 应自动转为 HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request() is True

    def test_circuit_breaker_recovery(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.05)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.1)  # 等待超过 recovery_timeout
        # is_open 属性会自动触发 CLOSED -> HALF_OPEN 转换
        assert cb.is_open is False  # 触发转换
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    def test_circuit_breaker_reset(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_degradation_strategy_order(self):
        order = DegradationStrategy.LOCAL_FIRST.fallback_order
        assert order[0] == DriverMode.LOCAL_SERVICE
        assert order[1] == DriverMode.HARD_LOAD
        assert order[2] == DriverMode.CLOUD_SERVICE

    def test_ftm_safe_chat_fallback(self):
        ftm = FaultToleranceManager(strategy=DegradationStrategy.LOCAL_FIRST)
        # 第一个驱动会失败
        fail_driver = MockDriver("fail", DriverMode.CLOUD_SERVICE, healthy=True)
        fail_driver._should_be_healthy = False
        ok_driver = MockDriver("ok", DriverMode.LOCAL_SERVICE, healthy=True)

        ftm.register_driver(fail_driver)
        ftm.register_driver(ok_driver)
        # 初始化驱动使状态变为 READY
        fail_driver.initialize()  # 因 healthy=False 会 ERROR
        ok_driver.initialize()     # READY

        req = ChatRequest(messages=[ChatMessage(role="user", content="Hi")])
        resp = ftm.safe_chat(req, [fail_driver, ok_driver])

        # fail_driver 应该失败，ok_driver 应该成功
        assert not resp.error
        assert "ok" in resp.content

    def test_ftm_safe_chat_all_fail(self):
        ftm = FaultToleranceManager()
        d1 = MockDriver("fail1", DriverMode.LOCAL_SERVICE, healthy=False)
        d2 = MockDriver("fail2", DriverMode.CLOUD_SERVICE, healthy=False)
        d1.initialize()
        d2.initialize()
        ftm.register_driver(d1)
        ftm.register_driver(d2)

        req = ChatRequest(messages=[ChatMessage(role="user", content="Hi")])
        resp = ftm.safe_chat(req, [d1, d2])
        assert resp.error

    def test_ftm_safe_chat_stream(self):
        ftm = FaultToleranceManager(strategy=DegradationStrategy.LOCAL_FIRST)
        fail_driver = MockDriver("fail", DriverMode.CLOUD_SERVICE, healthy=False)
        ok_driver = MockDriver("ok", DriverMode.LOCAL_SERVICE, healthy=True)
        ftm.register_driver(fail_driver)
        ftm.register_driver(ok_driver)
        fail_driver.initialize()
        ok_driver.initialize()

        req = ChatRequest(messages=[ChatMessage(role="user", content="Hi")])
        chunks = list(ftm.safe_chat_stream(req, [fail_driver, ok_driver]))
        assert len(chunks) >= 2
        assert chunks[-1].done is True

    def test_ftm_health_check(self):
        ftm = FaultToleranceManager()
        d1 = MockDriver("d1", DriverMode.LOCAL_SERVICE)
        d1.initialize()  # 使其 READY
        ftm.register_driver(d1)
        reports = ftm.check_all_health()
        assert "d1" in reports
        assert reports["d1"].healthy is True

    def test_ftm_get_status(self):
        ftm = FaultToleranceManager(strategy=DegradationStrategy.HARD_LOAD_FIRST)
        d1 = MockDriver("d1", DriverMode.HARD_LOAD)
        ftm.register_driver(d1)
        status = ftm.get_status()
        assert status["strategy"] == "hard_load_first"
        assert "d1" in status["drivers"]
        assert "breaker" in status["drivers"]["d1"]


# ═══════════════════════════════════════════════════════════════
# 5. Monitor 测试
# ═══════════════════════════════════════════════════════════════

class TestResourceMonitor:
    """资源监控测试"""

    def test_snapshot_creation(self):
        snap = ResourceSnapshot()
        assert snap.gpus == []
        assert snap.cpu.utilization_pct == 0.0
        assert snap.memory.utilization_pct == 0.0
        assert snap.app.total_requests == 0

    def test_take_snapshot(self):
        monitor = ResourceMonitor(sample_interval=100)  # 不启动后台
        snap = monitor.take_snapshot()
        assert snap is not None
        assert snap.timestamp > 0
        # CPU 和 memory 可能不为 0（如果有 psutil）
        assert isinstance(snap.cpu.utilization_pct, float)

    def test_record_request(self):
        monitor = ResourceMonitor()
        monitor.record_request(100.0, tokens=50)
        monitor.record_request(200.0, tokens=30)
        monitor.record_request(50.0, tokens=20, error=True)
        assert monitor._total_requests == 3
        assert monitor._total_errors == 1
        assert len(monitor._latencies) == 3

    def test_get_latest(self):
        monitor = ResourceMonitor()
        assert monitor.get_latest() is None
        monitor.take_snapshot()
        assert monitor.get_latest() is not None

    def test_get_history(self):
        monitor = ResourceMonitor()
        for _ in range(5):
            monitor.take_snapshot()
        history = monitor.get_history(last_n=3)
        assert len(history) == 3

    def test_app_metrics_calculation(self):
        monitor = ResourceMonitor()
        for i in range(10):
            monitor.record_request(float(50 + i * 10))
        snap = monitor.take_snapshot()
        assert snap.app.total_requests == 10
        assert snap.app.avg_latency_ms > 0

    def test_get_summary_text(self):
        monitor = ResourceMonitor()
        monitor.take_snapshot()
        text = monitor.get_summary_text()
        assert "Resource Monitor" in text
        assert "RAM" in text

    def test_driver_summary(self):
        monitor = ResourceMonitor()
        drivers = {
            "d1": MockDriver("d1", DriverMode.LOCAL_SERVICE),
            "d2": MockDriver("d2", DriverMode.CLOUD_SERVICE),
        }
        summary = monitor.get_driver_summary(drivers)
        assert "d1" in summary
        assert summary["d1"]["mode"] == "local_service"

    def test_alert_callback(self):
        monitor = ResourceMonitor()
        alerts = []
        monitor.add_alert_callback(lambda msg, snap: alerts.append(msg))
        monitor.set_memory_threshold(0.0)  # 触发告警
        monitor.take_snapshot()
        # 如果有 psutil 且内存使用 > 0%，应该触发告警
        # 也可能不触发（无 psutil）
        # 这里只验证不崩溃


# ═══════════════════════════════════════════════════════════════
# 6. ConfigManager 测试
# ═══════════════════════════════════════════════════════════════

class TestConfigManager:
    """配置管理器测试"""

    def test_create_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_config.json")
            mgr = ProviderConfigManager.create_default(output_path=path)
            assert os.path.exists(path)
            assert len(mgr.config.slots) >= 1

    def test_load_from_dict(self):
        mgr = ProviderConfigManager()
        data = {
            "default_mode": "hard_load",
            "slots": [
                {
                    "slot_id": "test-slot",
                    "model_id": "qwen2.5:0.5b",
                    "mode": "hard_load",
                    "driver_name": "hardload",
                    "params": {"backend": "ollama"},
                    "priority": 200,
                }
            ],
        }
        mgr.load_from_dict(data)
        assert mgr.config.default_mode == "hard_load"
        assert len(mgr.config.slots) == 1
        assert mgr.config.slots[0].slot_id == "test-slot"

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            mgr = ProviderConfigManager(config_path=path)
            mgr.load_from_dict({
                "default_mode": "local_service",
                "slots": [
                    {"slot_id": "s1", "model_id": "m1", "mode": "local_service"},
                ],
            })
            mgr.save_to_file()
            assert os.path.exists(path)

            # 新管理器加载
            mgr2 = ProviderConfigManager(config_path=path)
            ok = mgr2.load_from_file()
            assert ok is True
            assert mgr2.config.default_mode == "local_service"
            assert len(mgr2.config.slots) == 1

    def test_add_remove_slot(self):
        mgr = ProviderConfigManager()
        mgr.load_from_dict({"default_mode": "local_service"})
        slot = ModelSlotConfig(
            slot_id="new-slot", model_id="new-model",
            mode="cloud_service", priority=150,
        )
        mgr.add_slot(slot)
        assert len(mgr.config.slots) == 1
        mgr.remove_slot("new-slot")
        assert len(mgr.config.slots) == 0

    def test_update_slot(self):
        mgr = ProviderConfigManager()
        mgr.add_slot(ModelSlotConfig(slot_id="s1", model_id="m1", mode="local_service"))
        ok = mgr.update_slot("s1", model_id="m2", priority=300)
        assert ok is True
        slot = mgr.config.get_slot("s1")
        assert slot.model_id == "m2"
        assert slot.priority == 300

    def test_enable_disable_slot(self):
        mgr = ProviderConfigManager()
        mgr.add_slot(ModelSlotConfig(slot_id="s1", model_id="m1", enabled=True))
        mgr.enable_slot("s1", False)
        slot = mgr.config.get_slot("s1")
        assert slot.enabled is False
        enabled = mgr.config.get_enabled_slots()
        assert len(enabled) == 0

    def test_switch_model(self):
        mgr = ProviderConfigManager()
        mgr.add_slot(ModelSlotConfig(slot_id="s1", model_id="old-model"))
        mgr.switch_model("s1", "new-model")
        assert mgr.config.get_slot("s1").model_id == "new-model"

    def test_ab_test(self):
        mgr = ProviderConfigManager()
        ab = ABTestConfig(
            experiment_id="exp1",
            model="gpt-4o",
            variants={"cloud-openai": 0.7, "cloud-deepseek": 0.3},
        )
        mgr.set_ab_test(ab)
        active = mgr.get_active_ab_tests()
        assert len(active) == 1
        assert active[0].experiment_id == "exp1"

        mgr.remove_ab_test("exp1")
        assert len(mgr.get_active_ab_tests()) == 0

    def test_to_dict(self):
        mgr = ProviderConfigManager()
        mgr.load_from_dict({
            "default_mode": "hard_load",
            "slots": [{"slot_id": "s1", "model_id": "m1"}],
        })
        data = mgr.to_dict()
        assert data["default_mode"] == "hard_load"
        assert len(data["slots"]) == 1

    def test_on_change_callback(self):
        mgr = ProviderConfigManager()
        changes = []
        mgr.set_on_change(lambda reason, config: changes.append(reason))
        mgr.update_default_mode("cloud_service")
        assert "default_mode" in changes

    def test_update_default_mode(self):
        mgr = ProviderConfigManager()
        mgr.update_default_mode("hard_load")
        assert mgr.config.default_mode == "hard_load"


# ═══════════════════════════════════════════════════════════════
# 7. 硬加载子模块测试
# ═══════════════════════════════════════════════════════════════

class TestHardLoadRegistry:
    """硬加载注册表测试"""

    def test_register_and_create(self):
        from livingtree.core.provider.hard_load.registry import (
            register_hard_backend,
            get_hard_backend,
            list_backends,
            create_hard_driver,
        )

        # 创建一个简单的 mock 驱动类（接受 name 和 mode）
        class SimpleMockDriver(ModelDriver):
            def __init__(self, name: str = "mock", mode: DriverMode = DriverMode.HARD_LOAD, healthy: bool = True):
                super().__init__(name, mode)
                self._healthy = healthy
            def initialize(self) -> bool:
                self._set_state(DriverState.READY if self._healthy else DriverState.ERROR)
                return self._healthy
            def shutdown(self) -> None:
                self._set_state(DriverState.UNLOADED)
            def health_check(self) -> HealthReport:
                return self._build_health()
            def chat(self, request: ChatRequest) -> ChatResponse:
                return ChatResponse(content="ok")
            def chat_stream(self, request: ChatRequest) -> Iterator[StreamChunk]:
                yield StreamChunk(done=True)
            def complete(self, request: CompletionRequest) -> CompletionResponse:
                return CompletionResponse(text="ok")
            def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
                return EmbeddingResponse()
            def list_models(self) -> List[Dict[str, Any]]:
                return []
            def is_model_loaded(self, model: str) -> bool:
                return True

        # 注册 mock 后端
        register_hard_backend(
            "mock_backend",
            SimpleMockDriver,
            {"healthy": True},
        )
        assert "mock_backend" in list_backends()
        info = get_hard_backend("mock_backend")
        assert info is not None

        # 创建驱动
        driver = create_hard_driver("mock_backend", name="test-mock")
        assert driver.name == "test-mock"

    def test_create_unknown_backend(self):        
        from livingtree.core.provider.hard_load.registry import create_hard_driver
        with pytest.raises(ValueError, match="未知硬加载后端"):
            create_hard_driver("nonexistent_backend")


# ═══════════════════════════════════════════════════════════════
# 8. 集成测试
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    """端到端集成测试"""

    def test_full_pipeline(self):
        """完整流程：Gateway + FaultTolerance + Monitor"""
        # 创建网关
        gw = ModelGateway("integration-test")
        gw.register_driver(
            MockDriver("hard-mock", DriverMode.HARD_LOAD),
            models=["test-model"],
        )
        gw.register_driver(
            MockDriver("local-mock", DriverMode.LOCAL_SERVICE),
            models=["test-model"],
        )
        gw.initialize()

        # 创建容错管理器
        ftm = FaultToleranceManager(strategy=DegradationStrategy.HARD_LOAD_FIRST)
        for d in gw.drivers.values():
            ftm.register_driver(d)

        # 创建监控器
        monitor = ResourceMonitor(sample_interval=100)
        monitor.take_snapshot()  # 先采一次快照

        # 发送请求
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="test-model",
        )
        t0 = time.time()
        resp = ftm.safe_chat(req, list(gw.drivers.values()))
        elapsed = (time.time() - t0) * 1000
        monitor.record_request(elapsed, tokens=10)
        monitor.take_snapshot()  # 请求后再采一次

        assert not resp.error
        assert resp.content

        # 检查健康
        reports = ftm.check_all_health()
        for name, report in reports.items():
            assert report.healthy is True

        # 获取状态
        status = ftm.get_status()
        assert "hard-mock" in status["drivers"]
        assert "local-mock" in status["drivers"]

        # 获取监控快照
        snap = monitor.get_latest()
        assert snap is not None
        assert snap.app.total_requests == 1

        # 关闭
        gw.shutdown()

    def test_gateway_with_config(self):
        """Gateway + ConfigManager 集成"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "provider.json")
            config_mgr = ProviderConfigManager.create_default(output_path=path)
            config_mgr.add_slot(ModelSlotConfig(
                slot_id="integration-slot",
                model_id="test-model",
                mode="local_service",
                driver_name="local-integration",
                priority=150,
            ))

            gw = ModelGateway("config-test")
            gw.register_driver(
                MockDriver("local-integration", DriverMode.LOCAL_SERVICE),
                models=["test-model"],
            )
            gw.initialize()

            req = ChatRequest(messages=[ChatMessage(role="user", content="Hi")])
            resp = gw.chat(req)
            assert not resp.error

            gw.shutdown()


# ═══════════════════════════════════════════════════════════════
# 运行入口
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
