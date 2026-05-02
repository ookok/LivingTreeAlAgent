"""
LivingTree Core Integration Tests
===================================

Tests for the livingtree/ package core modules.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfig:
    def test_config_loads(self):
        from livingtree.infrastructure.config import get_config, LTAIConfig
        config = get_config(reload=True)
        assert config.version == "1.0.0"
        assert config.ollama.base_url == "http://localhost:11434"
        assert config.retries.default == 3

    def test_config_singleton(self):
        from livingtree.infrastructure.config import get_config, config
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2

    def test_config_compute_optimal(self):
        from livingtree.infrastructure.config import get_config
        config = get_config()
        optimal = config.compute_optimal(depth=5)
        assert optimal.depth == 5
        assert optimal.max_context > 0
        assert optimal.max_tokens > 0


class TestEventBus:
    def test_subscribe_and_publish(self):
        from livingtree.infrastructure.event_bus import EventBus
        bus = EventBus()
        received = []

        bus.subscribe("test_event", lambda e: received.append(e.data))
        bus.publish("test_event", {"key": "value"})
        assert len(received) == 1
        assert received[0]["key"] == "value"

    def test_event_history(self):
        from livingtree.infrastructure.event_bus import EventBus
        bus = EventBus()
        bus.publish("e1", {"a": 1})
        bus.publish("e2", {"b": 2})
        history = bus.get_history()
        assert len(history) >= 2

    def test_global_bus(self):
        from livingtree.infrastructure.event_bus import get_event_bus
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2


class TestIntentParser:
    def test_parse_writing(self):
        from livingtree.core.intent.parser import IntentParser
        parser = IntentParser()
        result = parser.parse("帮我写一份关于AI安全的报告")
        assert result.type.value == "writing"
        assert result.complexity > 0

    def test_parse_code(self):
        from livingtree.core.intent.parser import IntentParser
        parser = IntentParser()
        result = parser.parse("用Python实现一个排序算法")
        assert result.type.value == "code"
        assert result.confidence > 0

    def test_parse_empty(self):
        from livingtree.core.intent.parser import IntentParser
        parser = IntentParser()
        result = parser.parse("")
        assert result.type.value == "chat"

    def test_intent_tracker(self):
        from livingtree.core.intent.parser import IntentParser, IntentTracker
        parser = IntentParser()
        tracker = IntentTracker()

        for text in ["写报告", "帮我写", "需要什么格式"]:
            intent = parser.parse(text)
            tracker.track(intent, text)

        ctx = tracker.get_current_context()
        assert ctx["active"] is True
        assert ctx["turn_count"] == 3


class TestModelRouter:
    def test_tier_classification(self):
        from livingtree.core.model.router import get_model_router, ComputeTier
        router = get_model_router()

        assert router.classify_complexity(0.1) == ComputeTier.LOCAL
        assert router.classify_complexity(0.4) == ComputeTier.EDGE
        assert router.classify_complexity(0.8) == ComputeTier.CLOUD

    def test_route_returns_endpoint(self):
        from livingtree.core.model.router import get_model_router
        router = get_model_router()
        ep = router.route("test task", 0.5)
        assert ep is not None
        assert ep.model_name

    def test_model_cache(self):
        from livingtree.core.model.router import get_model_router, AIResponse
        router = get_model_router()
        resp = AIResponse(content="test", tier_used=None, model_used="qwen")
        router.set_cache("prompt_abc", "model_x", resp)
        cached = router.get_cached("prompt_abc", "model_x")
        assert cached is not None
        assert cached.content == "test"


class TestMemoryStore:
    def test_store_and_search(self):
        from livingtree.core.memory.store import MemoryStore, MemoryItem, MemoryQuery, MemoryType
        store = MemoryStore()

        item = MemoryItem(id="m1", content="AI安全是一个重要话题",
                          memory_type=MemoryType.MID_TERM)
        store.store(item)

        result = store.search(MemoryQuery(text="AI安全", limit=5))
        assert len(result.items) >= 1
        assert "AI安全" in result.items[0].content

    def test_session_store(self):
        from livingtree.core.memory.store import MemoryStore
        store = MemoryStore()

        store.sessions.create_session("s1")
        store.sessions.add_message("s1", "user", "你好")
        store.sessions.add_message("s1", "assistant", "你好！")

        history = store.sessions.get_history("s1")
        assert len(history) == 2
        assert history[0]["role"] == "user"

    def test_stats(self):
        from livingtree.core.memory.store import MemoryStore
        store = MemoryStore()
        stats = store.stats()
        assert "total_items" in stats
        assert "vector_count" in stats


class TestSkills:
    def test_repository(self):
        from livingtree.core.skills.matcher import SkillRepository, SkillInfo
        repo = SkillRepository()
        skill = SkillInfo(
            name="test_skill", description="A test skill",
            category="testing", tags=["test"],
        )
        repo.register(skill)
        assert repo.count() == 1
        assert repo.get("test_skill") is not None

    def test_skill_loader_defaults(self):
        from livingtree.core.skills.matcher import SkillRepository, SkillLoader
        repo = SkillRepository()
        loader = SkillLoader(repo)
        loader.load_default_skills()
        assert repo.count() >= 5

    def test_skill_matcher(self):
        from livingtree.core.skills.matcher import SkillRepository, SkillLoader, SkillMatcher
        repo = SkillRepository()
        loader = SkillLoader(repo)
        loader.load_default_skills()

        matcher = SkillMatcher(repo)
        results = matcher.match("writing")
        assert len(results) >= 1


class TestPlanning:
    def test_task_decomposer(self):
        from livingtree.core.planning.decomposer import TaskDecomposer
        dec = TaskDecomposer(max_depth=3, complexity_threshold=0.3)
        steps = dec.decompose("test", "writing", 0.6, depth=0)
        assert len(steps) > 0

    def test_task_planner(self):
        from livingtree.core.planning.decomposer import TaskPlanner
        planner = TaskPlanner(max_depth=2, complexity_threshold=0.3)
        plan = planner.plan("test task", "writing", 0.6)
        assert plan.total_steps > 0
        assert plan.estimated_total_tokens > 0

    def test_cot_templates(self):
        from livingtree.core.planning.decomposer import COT_TEMPLATES
        assert "writing" in COT_TEMPLATES
        assert "code" in COT_TEMPLATES
        assert "analysis" in COT_TEMPLATES


class TestEvolution:
    def test_evolution_engine(self):
        from livingtree.core.evolution.reflection import EvolutionEngine, ExecutionRecord
        engine = EvolutionEngine()

        for i in range(10):
            record = ExecutionRecord(
                success=(i % 3 != 0),
                duration_ms=100.0,
                tokens_used=500,
                errors=[] if i % 3 != 0 else ["timeout"],
            )
            engine.record_execution(record)

        report = engine.reflect(batch_size=10)
        assert report.batch_size == 10
        assert report.success_rate > 0

    def test_should_evolve(self):
        from livingtree.core.evolution.reflection import EvolutionEngine, ExecutionRecord
        engine = EvolutionEngine()

        # Not enough history
        assert engine.should_evolve() is False

        # Add failures
        for i in range(10):
            engine.record_execution(ExecutionRecord(
                success=(i < 4),
                errors=[] if i < 4 else ["error"],
            ))

        assert engine.should_evolve() is True


class TestLifeEngine:
    def test_instantiation(self):
        from livingtree.core.life_engine import LifeEngine
        engine = LifeEngine()
        health = engine.get_health()
        assert health["version"] == "1.0.0"
        assert len(health["cells"]) == 5

    def test_handle_request(self):
        from livingtree.core.life_engine import LifeEngine
        engine = LifeEngine()
        response = engine.handle_request("你好")
        assert response.trace_id
        assert response.text

    def test_full_task_chain(self):
        from livingtree.core.life_engine import LifeEngine
        engine = LifeEngine()

        response = engine.handle_request("帮我写一份关于AI安全的报告")
        assert response.trace_id
        assert response.text
        assert response.learning.score > 0
        assert len(response.learning.insights) > 0

    def test_singleton(self):
        from livingtree.core.life_engine import LifeEngine
        e1 = LifeEngine.get_instance()
        e2 = LifeEngine.get_instance()
        assert e1 is e2


class TestObservability:
    def test_logger(self):
        from livingtree.core.observability.logger import StructuredLogger
        logger = StructuredLogger(module="test")
        logger.info("test_action", input_summary="test input")

    def test_tracer(self):
        from livingtree.core.observability.tracer import get_tracer
        tracer = get_tracer()
        ctx = tracer.start_trace("req1")
        span = tracer.start_span(ctx, "test_span")
        tracer.end_span(span, True, output_summary="done")
        tracer.end_trace(ctx, True)

    def test_metrics(self):
        from livingtree.core.observability.metrics import get_metrics
        m = get_metrics()
        m.record_request(True, 100.0)
        m.record_request(False, 200.0)
        snapshot = m.snapshot()
        assert snapshot["requests"]["total"] >= 2
        assert snapshot["success_rate"] <= 1.0


class TestWorldModel:
    def test_predictor(self):
        from livingtree.core.world_model.predictor import StatePredictor, Action, ActionType
        predictor = StatePredictor()

        action = Action(type=ActionType.FILE_DELETE, description="delete test.txt",
                        predicted_duration_ms=50.0)
        outcome = predictor.predict_outcome(action)
        assert outcome.success_likelihood > 0
        assert outcome.should_proceed

    def test_simulator(self):
        from livingtree.core.world_model.predictor import OutcomeSimulator, Action, ActionType
        simulator = OutcomeSimulator()

        actions = [
            Action(type=ActionType.FILE_DELETE, description="delete a"),
            Action(type=ActionType.COMMAND_EXECUTE, description="run cmd"),
        ]
        assessment = simulator.risk_assessment(actions)
        assert assessment["total_actions"] == 2
        assert "overall_risk_score" in assessment


class TestTools:
    def test_registry(self):
        from livingtree.core.tools.registry import ToolRegistry
        assert ToolRegistry.count() >= 4

    def test_search(self):
        from livingtree.core.tools.registry import ToolRegistry
        results = ToolRegistry.search("read")
        assert len(results) > 0

    def test_dispatcher(self):
        from livingtree.core.tools.registry import ToolRegistry, ToolDispatcher
        dispatcher = ToolDispatcher()
        result = dispatcher.dispatch("read_file", {"path": "nonexistent.txt"})
        assert result is not None
