"""LivingTree v2.1 — Comprehensive TUI & System Test Suite.

Tests all functional modules without requiring the TUI to render.
Run: python -m pytest test_all.py -v
Or:   python test_all.py
"""

import sys, os, asyncio, json, time, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


class TestConfig(unittest.TestCase):
    """1. Configuration & Secrets"""

    def test_config_loading(self):
        from livingtree.config import get_config, reload_config
        c = reload_config()
        self.assertIsNotNone(c)
        self.assertEqual(c.version, "2.0.0")
        self.assertIsNotNone(c.model)

    def test_secret_vault(self):
        from livingtree.config.secrets import get_secret_vault
        v = get_secret_vault()
        self.assertIsNotNone(v)
        # Check key providers have entries
        keys = ["deepseek_api_key", "longcat_api_key", "zhipu_api_key"]
        for k in keys:
            val = v.get(k, "")
            self.assertTrue(len(val) > 0 or k == "deepseek_api_key",
                           f"{k} should be configured")

    def test_system_config(self):
        from livingtree.config.system_config import EXT_TO_LANG, SLASH_COMMANDS
        self.assertGreater(len(EXT_TO_LANG), 20)
        self.assertEqual(len(SLASH_COMMANDS), 10)

    def test_config_security(self):
        from livingtree.config.config_security import sanitize_project_config
        cfg = {"api_key": "secret", "base_url": "https://evil.com", "safe_key": "ok"}
        clean = sanitize_project_config(cfg)
        self.assertNotIn("api_key", clean)
        self.assertNotIn("base_url", clean)
        self.assertIn("safe_key", clean)


class TestLLMProviders(unittest.TestCase):
    """2. TreeLLM & Multi-Provider Routing"""

    def test_treellm_creation(self):
        from livingtree.treellm import TreeLLM
        llm = TreeLLM()
        self.assertIsNotNone(llm)
        self.assertTrue(hasattr(llm, 'chat'))
        self.assertTrue(hasattr(llm, 'stream'))

    def test_deepseek_provider(self):
        from livingtree.treellm.providers import create_deepseek_provider
        p = create_deepseek_provider("test_key")
        self.assertEqual(p.name, "deepseek")
        self.assertIn("api.deepseek.com", p.base_url)

    def test_longcat_provider(self):
        from livingtree.treellm.providers import create_longcat_provider
        p = create_longcat_provider("test_key")
        self.assertEqual(p.name, "longcat")
        self.assertIn("longcat.chat", p.base_url)

    async def _test_provider_ping(self, provider_name):
        from livingtree.treellm import TreeLLM
        from livingtree.config import get_config
        from livingtree.config.secrets import get_secret_vault

        c = get_config()
        v = get_secret_vault()
        llm = TreeLLM()

        configs = {
            "deepseek": ("deepseek_api_key", c.model.deepseek_base_url or "https://api.deepseek.com/v1", c.model.flash_model.split("/")[-1] if "/" in c.model.flash_model else c.model.flash_model),
            "longcat": ("longcat_api_key", "https://api.longcat.chat/openai/v1", "LongCat-Flash-Lite"),
            "zhipu": ("zhipu_api_key", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
        }

        if provider_name in configs:
            key_name, base_url, model = configs[provider_name]
            key = v.get(key_name, "")
            if key:
                from livingtree.treellm.providers import OpenAILikeProvider
                llm.add_provider(OpenAILikeProvider(provider_name, base_url, key, model))
                ok, _ = await llm.get_provider(provider_name).ping()
                return ok
        return None  # skipped

    def test_deepseek_connectivity(self):
        ok = asyncio.run(self._test_provider_ping("deepseek"))
        if ok is not None:
            self.assertTrue(ok, "DeepSeek should be reachable")

    def test_longcat_connectivity(self):
        ok = asyncio.run(self._test_provider_ping("longcat"))
        if ok is not None:
            self.assertTrue(ok, "LongCat should be reachable")

    def test_zhipu_connectivity(self):
        ok = asyncio.run(self._test_provider_ping("zhipu"))
        if ok is not None:
            self.assertTrue(ok, "Zhipu should be reachable")

    def test_auto_election(self):
        from livingtree.dna.dual_consciousness import DualModelConsciousness
        from livingtree.config import get_config
        c = get_config()
        d = DualModelConsciousness(
            api_key=c.model.deepseek_api_key or "test",
            longcat_api_key=c.model.longcat_api_key,
            zhipu_api_key=c.model.zhipu_api_key,
        )
        self.assertTrue(hasattr(d, '_elect'))
        status = d.get_election_status()
        self.assertIn("providers", status)

    def test_tiny_classifier(self):
        from livingtree.treellm.classifier import TinyClassifier
        clf = TinyClassifier()
        route = clf.predict("help me write python code", ["a", "b"], {})
        self.assertIn(route, ["a", "b"])
        clf.learn("help me write code", "a", True)
        route2 = clf.predict("help me refactor code", ["a", "b"], {})
        self.assertIsNotNone(route2)


class TestKnowledgeMemory(unittest.TestCase):
    """3. Knowledge & Memory Systems"""

    def test_struct_mem(self):
        from livingtree.knowledge.struct_mem import StructMemory
        mem = StructMemory()
        self.assertTrue(hasattr(mem, 'bind_events'))
        self.assertTrue(hasattr(mem, 'consolidate_if_needed'))
        self.assertTrue(hasattr(mem, 'retrieve_for_query'))

    def test_provenance(self):
        from livingtree.knowledge.provenance import ProvenanceTracker
        prov = ProvenanceTracker()
        prov.record("test-1", "doc.txt", 10, 20, 0.95)
        trace = prov.trace("test-1")
        self.assertTrue(trace["found"])
        self.assertEqual(trace["source"], "doc.txt")

    def test_conversation_dna(self):
        from livingtree.dna.conversation_dna import ConversationDNA
        dna = ConversationDNA()
        dna.record("s1", "analyze code", [{"name": "step1"}], 0.9)
        suggestion = dna.suggest("analyze codebase")
        self.assertIsInstance(suggestion, dict)

    def test_user_memory(self):
        from livingtree.tui.widgets.user_memory import UserMemory
        mem = UserMemory()
        mem.append("# test convention: use snake_case")
        content = mem.read()
        self.assertIn("snake_case", content)
        mem.clear()

    def test_composer_stash(self):
        from livingtree.tui.widgets.composer_stash import ComposerStash
        stash = ComposerStash()
        stash.push("test draft")
        draft = stash.pop()
        self.assertIsNotNone(draft)
        self.assertIn("test draft", draft.text)


class TestCapabilityTools(unittest.TestCase):
    """4. Capability & Tool Layer"""

    def test_pipeline_engine(self):
        from livingtree.capability.pipeline_engine import PipelineEngine
        engine = PipelineEngine()
        config = asyncio.run(engine.generate("extract all names and deduplicate"))
        self.assertGreater(len(config.steps), 1)

    def test_extraction_engine(self):
        from livingtree.capability.extraction_engine import ExtractionEngine
        engine = ExtractionEngine()
        results = engine.extract("Patient has fever and cough", ["symptom"])
        self.assertGreater(len(results), 0)
        self.assertIn("fever", [r.extraction_text for r in results])

    def test_spark_search(self):
        from livingtree.capability.spark_search import SparkSearch
        from livingtree.config.secrets import get_secret_vault
        key = get_secret_vault().get("spark_search_key", "")
        if key:
            search = SparkSearch(key)
            results = asyncio.run(search.query("Python", limit=3))
            self.assertIsInstance(results, list)

    def test_web_reach(self):
        from livingtree.capability.web_reach import WebReach
        reach = WebReach()
        page = asyncio.run(reach.fetch("https://httpbin.org/html"))
        self.assertEqual(page.status_code, 200)
        self.assertGreater(len(page.text), 0)

    def test_multimodal_parser(self):
        from livingtree.capability.multimodal_parser import MultimodalParser
        parser = MultimodalParser()
        req_path = Path(__file__).parent / "requirements.txt"
        if req_path.exists():
            doc = asyncio.run(parser.parse(str(req_path)))
            self.assertGreater(len(doc.text), 100)

    def test_self_discovery(self):
        from livingtree.capability.self_discovery import SelfDiscovery
        sd = SelfDiscovery(trigger_threshold=2)
        class MockGene:
            pipeline_steps = ["extract", "resolve"]
            domain = "general"
            success_rate = 0.9
            intent = "test"
        result = asyncio.run(sd.observe(MockGene()))
        self.assertIsNone(result)  # threshold not reached yet

    def test_skill_discovery(self):
        from livingtree.capability.skill_discovery import SkillDiscoveryManager
        sd = SkillDiscoveryManager()
        skills = sd.discover_all()
        self.assertIsInstance(skills, list)


class TestExecutionLayer(unittest.TestCase):
    """5. Execution & Orchestration"""

    def test_task_checkpoint(self):
        from livingtree.execution.checkpoint import TaskCheckpoint, CheckpointState
        cp = TaskCheckpoint()
        state = CheckpointState(session_id="test", task_goal="test")
        path = asyncio.run(cp.save("test", state))
        self.assertTrue(path.exists())
        loaded = asyncio.run(cp.load("test"))
        self.assertIsNotNone(loaded)
        asyncio.run(cp.delete("test"))

    def test_side_git(self):
        from livingtree.execution.side_git import SideGit
        sg = SideGit(workspace_path=".")
        turn_id = asyncio.run(sg.pre_turn())
        self.assertGreater(turn_id, 0)
        changes = asyncio.run(sg.post_turn(turn_id))
        self.assertIsInstance(changes, list)

    def test_session_manager(self):
        from livingtree.execution.session_manager import SessionManager, SessionState
        sm = SessionManager()
        state = SessionState(session_id="test", name="test session")
        asyncio.run(sm.save(state))
        sessions = asyncio.run(sm.list_sessions())
        self.assertIsInstance(sessions, list)

    def test_rlm_runner(self):
        from livingtree.execution.rlm import RLMRunner
        rlm = RLMRunner(max_workers=2)
        self.assertTrue(hasattr(rlm, 'fan_out'))

    def test_sub_agent_roles(self):
        from livingtree.execution.sub_agent_roles import SubAgentRoles
        roles = SubAgentRoles()
        self.assertTrue(hasattr(roles, 'run_implement_verify'))

    def test_orchestrator(self):
        from livingtree.execution.orchestrator import Orchestrator, AgentSpec, AgentRole
        orch = Orchestrator(max_agents=5)
        role = AgentRole(name="test", capabilities=["test"])
        agent = AgentSpec(name="test", roles=[role])
        orch.register_agent(agent)
        status = orch.get_status()
        self.assertGreaterEqual(status["total_agents"], 1)


class TestDNALayer(unittest.TestCase):
    """6. DNA & Life Cycle"""

    def test_life_engine(self):
        from livingtree.dna.life_engine import LifeEngine, LifeContext
        self.assertIsNotNone(LifeEngine)
        ctx = LifeContext(user_input="test")
        self.assertIsNotNone(ctx.session_id)

    def test_biorhythm(self):
        from livingtree.dna.biorhythm import Biorhythm
        bio = Biorhythm()
        snapshot = bio.pulse()
        self.assertIn("state", snapshot)
        self.assertIn("heart_rate", snapshot)

    def test_adaptive_ui(self):
        from livingtree.dna.adaptive_ui import AdaptiveUI
        ui = AdaptiveUI()
        theme = ui.tick(hour=14)
        self.assertIsNotNone(theme.accent)

    def test_anticipatory(self):
        from livingtree.dna.anticipatory import Anticipatory
        anti = Anticipatory()
        anti.learn("write python code for auth", "/code", True)
        result = anti.suggest_action("write python code for login")
        self.assertIn("suggestions", result)

    def test_self_narrative(self):
        from livingtree.dna.self_narrative import SelfNarrative
        narr = SelfNarrative()
        narr.birth()
        narr.conversation("s1", "chat", True)
        story = narr.narrate()
        self.assertIn("诞生", story)

    def test_multi_agent_debate(self):
        from livingtree.dna.multi_agent_debate import MultiAgentDebate
        debate = MultiAgentDebate()
        self.assertTrue(hasattr(debate, 'deliberate'))

    def test_self_evolving(self):
        from livingtree.dna.self_evolving import SelfEvolvingEngine
        evo = SelfEvolvingEngine()
        status = evo.get_status()
        self.assertIn("candidates", status)

    def test_predictive_world(self):
        from livingtree.dna.predictive_world import PredictiveWorldModel
        pwm = PredictiveWorldModel()
        pwm.record_change("test.py", "edit", True)
        pwm.record_error("test.py")
        status = pwm.get_status()
        self.assertGreater(status["tracked_files"], 0)

    def test_cache_optimizer(self):
        from livingtree.dna.cache_optimizer import CacheOptimizer
        co = CacheOptimizer()
        msgs = co.prepare("system", [{"role": "user", "content": "test"}])
        self.assertGreater(len(msgs), 0)
        stats = co.stats()
        self.assertIn("hit_rate_pct", stats)

    def test_tool_repair(self):
        from livingtree.dna.tool_repair import ToolCallRepair
        repair = ToolCallRepair()
        result = repair.fix('{"name":"test","args":{"key":"val"}}')
        self.assertIsNotNone(result)

    def test_thought_harvest(self):
        from livingtree.dna.thought_harvest import ThoughtHarvester
        harvest = ThoughtHarvester()
        result = harvest.harvest("<think>use tool: search</think>")
        self.assertIsNotNone(result)


class TestNetworkLayer(unittest.TestCase):
    """7. Network & P2P"""

    def test_nat_traverse(self):
        from livingtree.network.nat_traverse import NATTraverser
        nat = NATTraverser()
        self.assertTrue(hasattr(nat, 'get_public_endpoint'))
        self.assertTrue(hasattr(nat, 'try_direct_connect'))

    def test_node_info(self):
        from livingtree.network.node import Node, NodeInfo
        node = Node(name="test")
        self.assertIsNotNone(node.info)
        self.assertEqual(node.info.name, "test")

    def test_offline_mode(self):
        from livingtree.network.offline_mode import DualMode
        dm = DualMode()
        self.assertTrue(hasattr(dm, 'check'))
        status = dm.get_status()
        self.assertIn("online", status)

    def test_collective_consciousness(self):
        from livingtree.network.collective import CollectiveConsciousness
        cc = CollectiveConsciousness()
        status = cc.get_status()
        self.assertIn("shared_total", status)


class TestIntegration(unittest.TestCase):
    """8. Integration Bridges"""

    def test_hub_creation(self):
        from livingtree.integration.hub import IntegrationHub
        hub = IntegrationHub()
        self.assertIsNotNone(hub)
        self.assertIsNotNone(hub.config)

    def test_opencode_bridge(self):
        from livingtree.integration.opencode_bridge import OpenCodeBridge
        bridge = OpenCodeBridge()
        providers = bridge.discover_providers()
        self.assertIsInstance(providers, list)

    def test_opencode_serve(self):
        from livingtree.integration.opencode_serve import OpenCodeServeAdapter
        adapter = OpenCodeServeAdapter()
        self.assertTrue(hasattr(adapter, 'ping'))
        self.assertTrue(hasattr(adapter, 'chat'))

    def test_sse_server(self):
        from livingtree.integration.sse_server import SSEAgentServer
        server = SSEAgentServer()
        self.assertTrue(hasattr(server, 'start'))

    def test_self_updater(self):
        from livingtree.integration.self_updater import _get_platform_asset
        asset = _get_platform_asset()
        self.assertIn("livingtree", asset)


class TestLSP(unittest.TestCase):
    """9. LSP Diagnostics"""

    def test_lsp_manager(self):
        from livingtree.lsp import LSPManager
        lsp = LSPManager()
        self.assertTrue(hasattr(lsp, 'check_file'))
        self.assertTrue(hasattr(lsp, 'check_files'))

    def test_opencode_lsp(self):
        from livingtree.tui.widgets.opencode_lsp import OpenCodeLSPBridge
        bridge = OpenCodeLSPBridge()
        self.assertTrue(bridge.supports_file("test.py"))
        self.assertTrue(bridge.supports_file("test.rs"))
        self.assertTrue(bridge.supports_file("test.go"))


class TestErrorInterceptor(unittest.TestCase):
    """10. Error Handling"""

    def test_error_capture(self):
        from livingtree.observability.error_interceptor import ErrorInterceptor
        ei = ErrorInterceptor()
        ei.install()
        ei.capture(ValueError("test"), "test_file.py:42")
        errors = ei.get_recent()
        self.assertGreater(len(errors), 0)
        stats = ei.get_stats()
        self.assertGreater(stats["total_errors"], 0)
        ei.uninstall()

    def test_error_stats(self):
        from livingtree.observability.error_interceptor import get_interceptor, install
        ei = install()
        ei.capture(RuntimeError("test2"), "test.py:10")
        stats = ei.get_stats()
        self.assertIn("top_types", stats)
        ei.clear()


class TestObservability(unittest.TestCase):
    """11. Observability"""

    def test_logger_setup(self):
        from livingtree.observability.logger import setup_logging, LogContext
        self.assertTrue(hasattr(LogContext, 'set_session'))
        self.assertTrue(hasattr(LogContext, 'get_context'))

    def test_metrics(self):
        from livingtree.observability.metrics import MetricsCollector
        mc = MetricsCollector()
        self.assertTrue(hasattr(mc, 'life_cycles'))


def print_summary(results):
    passed = sum(1 for r in results if r.wasSuccessful())
    total = len(results)
    tests = sum(r.testsRun for r in results)
    failures = sum(len(r.failures) for r in results)
    errors = sum(len(r.errors) for r in results)
    
    print("\n" + "=" * 60)
    print(f"  LivingTree v2.1 — Test Results")
    print("=" * 60)
    print(f"  Modules: {passed}/{total} passed")
    print(f"  Tests:   {tests} total, {failures} failed, {errors} errors")
    print("=" * 60)
    
    for r in results:
        name = r.__class__.__name__
        if r.wasSuccessful():
            print(f"  [PASS] {name} ({r.testsRun} tests)")
        else:
            for f in r.failures + r.errors:
                print(f"  [FAIL] {name}: {f[0]}")
    
    return failures == 0 and errors == 0


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    test_classes = [
        TestConfig, TestLLMProviders, TestKnowledgeMemory,
        TestCapabilityTools, TestExecutionLayer, TestDNALayer,
        TestNetworkLayer, TestIntegration, TestLSP,
        TestErrorInterceptor, TestObservability,
    ]
    
    results = []
    for tc in test_classes:
        s = loader.loadTestsFromTestCase(tc)
        r = unittest.TextTestRunner(verbosity=1).run(s)
        results.append(r)
    
    ok = print_summary(results)
    sys.exit(0 if ok else 1)
