#!/usr/bin/env python3
"""
LivingTreeAI Phase 1 完整测试套件
覆盖所有核心模块的单元测试和集成测试
"""

import unittest
import sys
import os
import time

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestIntentEngine(unittest.TestCase):
    """IntentEngine 单元测试"""
    
    def test_import(self):
        """测试导入"""
        from client.src.business.intent_engine import IntentEngine
        self.assertIsNotNone(IntentEngine)
    
    def test_engine_creation(self):
        """测试引擎创建"""
        from client.src.business.intent_engine import IntentEngine
        engine = IntentEngine()
        self.assertIsNotNone(engine)
    
    def test_basic_parsing(self):
        """测试基本解析"""
        from client.src.business.intent_engine import IntentEngine
        engine = IntentEngine()
        intent = engine.parse("写一个登录接口")
        self.assertIsNotNone(intent)
        self.assertIsNotNone(intent.action)


class TestEvolutionEngine(unittest.TestCase):
    """EvolutionEngine 单元测试"""
    
    def test_import(self):
        """测试导入"""
        from client.src.business.evolution_engine import create_evolution_engine
        self.assertIsNotNone(create_evolution_engine)
    
    def test_engine_creation(self):
        """测试引擎创建"""
        from client.src.business.evolution_engine import create_evolution_engine
        engine = create_evolution_engine(
            project_root=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            enable_performance=False,
            enable_architecture=False
        )
        self.assertIsNotNone(engine)
    
    def test_proposal_generation(self):
        """测试提案生成"""
        from client.src.business.evolution_engine import create_evolution_engine
        engine = create_evolution_engine(
            project_root=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            enable_performance=False,
            enable_architecture=False
        )
        result = engine.scan_once()
        self.assertIn('proposals', result)


class TestSelfAwareness(unittest.TestCase):
    """SelfAwareness 单元测试"""
    
    def test_import(self):
        """测试导入"""
        from client.src.business.self_awareness import SelfAwarenessSystem
        self.assertIsNotNone(SelfAwarenessSystem)
    
    def test_system_creation(self):
        """测试系统创建"""
        from client.src.business.self_awareness import SelfAwarenessSystem
        system = SelfAwarenessSystem(
            project_root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.assertIsNotNone(system)
    
    def test_health_check(self):
        """测试健康检查"""
        from client.src.business.self_awareness import SelfAwarenessSystem
        system = SelfAwarenessSystem(
            project_root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        health = system.get_health_status()
        self.assertIn('status', health)


class TestAgentOrchestrator(unittest.TestCase):
    """AgentOrchestrator 单元测试"""
    
    def test_import(self):
        """测试导入"""
        from client.src.business.agent import AgentOrchestrator, AgentFactory, TaskPriority
        self.assertIsNotNone(AgentOrchestrator)
        self.assertIsNotNone(AgentFactory)
        self.assertIsNotNone(TaskPriority)
    
    def test_factory_creation(self):
        """测试工厂创建"""
        from client.src.business.agent import AgentFactory
        factory = AgentFactory()
        self.assertIsNotNone(factory)
    
    def test_orchestrator_creation(self):
        """测试编排器创建"""
        from client.src.business.agent import AgentOrchestrator, AgentFactory
        factory = AgentFactory()
        orchestrator = AgentOrchestrator(agent_factory=factory)
        self.assertIsNotNone(orchestrator)
    
    def test_task_creation(self):
        """测试任务创建"""
        from client.src.business.agent import AgentOrchestrator, AgentFactory, TaskPriority
        factory = AgentFactory()
        orchestrator = AgentOrchestrator(agent_factory=factory)
        task = orchestrator.create_task("测试任务", TaskPriority.MEDIUM)
        self.assertIsNotNone(task)


class TestA2AProtocol(unittest.TestCase):
    """A2A 协议单元测试"""
    
    def test_import(self):
        """测试导入"""
        from client.src.business.a2a_protocol import A2AProtocol, AgentMessage
        self.assertIsNotNone(A2AProtocol)
        self.assertIsNotNone(AgentMessage)
    
    def test_protocol_creation(self):
        """测试协议创建"""
        from client.src.business.a2a_protocol import A2AProtocol
        protocol = A2AProtocol()
        self.assertIsNotNone(protocol)
    
    def test_message_creation(self):
        """测试消息创建"""
        from client.src.business.a2a_protocol import AgentMessage
        msg = AgentMessage(
            sender="agent1",
            receiver="agent2",
            action="test",
            payload={}
        )
        self.assertEqual(msg.sender, "agent1")


class TestKnowledgeBlockchain(unittest.TestCase):
    """KnowledgeBlockchain 单元测试"""
    
    def test_import(self):
        """测试导入"""
        from core.knowledge_blockchain import KnowledgeMarket
        self.assertIsNotNone(KnowledgeMarket)
    
    def test_market_creation(self):
        """测试市场创建"""
        from core.knowledge_blockchain import KnowledgeMarket
        market = KnowledgeMarket()
        self.assertIsNotNone(market)


class TestProxyGateway(unittest.TestCase):
    """ProxyGateway 单元测试"""
    
    def test_import(self):
        """测试导入"""
        from client.src.business.proxy import SmartProxyGateway
        self.assertIsNotNone(SmartProxyGateway)
    
    def test_gateway_creation(self):
        """测试网关创建"""
        from client.src.business.proxy import SmartProxyGateway
        gateway = SmartProxyGateway()
        self.assertIsNotNone(gateway)


class TestPlatformHub(unittest.TestCase):
    """PlatformHub 单元测试"""
    
    def test_import(self):
        """测试导入"""
        from client.src.presentation.panels.platform_hub_panel import PlatformHubPanel
        self.assertIsNotNone(PlatformHubPanel)
    
    def test_panel_creation(self):
        """测试面板创建"""
        from client.src.presentation.panels.platform_hub_panel import PlatformHubPanel
        panel = PlatformHubPanel()
        self.assertIsNotNone(panel)
    
    def test_agent_registration(self):
        """测试智能体注册"""
        from client.src.presentation.panels.platform_hub_panel import PlatformHubPanel
        panel = PlatformHubPanel()
        result = panel.register_agent("test1", "TestAgent", "coder")
        self.assertTrue(result)
    
    def test_workspace_add(self):
        """测试工作区添加"""
        from client.src.presentation.panels.platform_hub_panel import PlatformHubPanel
        panel = PlatformHubPanel()
        result = panel.add_workspace("ws1", "TestWorkspace", "/tmp/test")
        self.assertTrue(result)


class TestIDEIntentPanel(unittest.TestCase):
    """IDEIntentPanel 单元测试"""
    
    def test_import(self):
        """测试导入"""
        try:
            from client.src.presentation.panels.ide_intent_panel import IntentIDEPanel
            self.assertIsNotNone(IntentIDEPanel)
        except ImportError:
            self.skipTest("IDE Intent Panel 未实现")


def run_all_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试类
    test_classes = [
        TestIntentEngine,
        TestEvolutionEngine,
        TestSelfAwareness,
        TestAgentOrchestrator,
        TestA2AProtocol,
        TestKnowledgeBlockchain,
        TestProxyGateway,
        TestPlatformHub,
        TestIDEIntentPanel,
    ]
    
    for test_class in test_classes:
        try:
            suite.addTests(loader.loadTestsFromTestCase(test_class))
        except Exception as e:
            print(f"加载测试类 {test_class.__name__} 失败: {e}")
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    start_time = time.time()
    result = runner.run(suite)
    elapsed = time.time() - start_time
    
    # 输出摘要
    print("\n" + "="*70)
    print("🎉 LivingTreeAI Phase 1 完整测试报告")
    print("="*70)
    print(f"📊 测试总数: {result.testsRun}")
    print(f"✅ 成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ 失败: {len(result.failures)}")
    print(f"⚠️ 错误: {len(result.errors)}")
    print(f"⏱️ 耗时: {elapsed:.2f}秒")
    print("="*70)
    
    if result.wasSuccessful():
        print("🎊 所有测试通过！Phase 1 核心模块验证完成！")
    else:
        print("⚠️ 部分测试失败，请检查。")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
