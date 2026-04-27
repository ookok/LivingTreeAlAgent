#!/usr/bin/env python3
"""
LivingTreeAI Phase 1 集成测试
测试各核心模块间的集成
"""

import unittest
import sys
import os

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.src.business.intent_engine import IntentEngine
from client.src.business.agent import AgentOrchestrator, AgentFactory, TaskPriority
from client.src.business.evolution_engine import create_evolution_engine
from client.src.business.self_awareness import SelfAwarenessSystem
from client.src.business.a2a_protocol import A2AProtocol, AgentMessage


class TestIntentEngineIntegration(unittest.TestCase):
    """IntentEngine 集成测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.engine = IntentEngine()
    
    def test_intent_parsing(self):
        """测试意图解析"""
        intent = self.engine.parse("帮我写一个用户登录接口")
        self.assertIsNotNone(intent)
        self.assertIn(intent.action, ['编写', '创建', '生成', '写'])
    
    def test_intent_with_tech_stack(self):
        """测试技术栈检测"""
        intent = self.engine.parse("用 FastAPI 写一个登录接口")
        self.assertIn('fastapi', intent.tech_stack)
    
    def test_model_selection(self):
        """测试模型选择"""
        intent = self.engine.parse("优化这个复杂算法")
        model = self.engine.suggest_model(intent)
        self.assertIsNotNone(model)


class TestAgentOrchestratorIntegration(unittest.TestCase):
    """AgentOrchestrator 集成测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.factory = AgentFactory()
        cls.orchestrator = AgentOrchestrator(agent_factory=cls.factory)
    
    def test_create_agent(self):
        """测试创建代理"""
        agent = self.factory.create_agent("coder", {"name": "TestCoder"})
        self.assertIsNotNone(agent)
        self.assertEqual(agent.name, "TestCoder")
    
    def test_task_creation(self):
        """测试任务创建"""
        task = self.orchestrator.create_task(
            description="测试任务",
            priority=TaskPriority.HIGH
        )
        self.assertIsNotNone(task)
        self.assertEqual(task.priority, TaskPriority.HIGH)
    
    def test_workflow_execution(self):
        """测试工作流执行"""
        workflow = self.orchestrator.create_workflow("test_workflow")
        workflow.add_step("step1", lambda ctx: {"result": "ok"})
        workflow.add_step("step2", lambda ctx: {"result": "done"})
        
        result = workflow.execute({})
        self.assertEqual(len(result), 2)


class TestEvolutionEngineIntegration(unittest.TestCase):
    """EvolutionEngine 集成测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.engine = create_evolution_engine(
            project_root=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            enable_performance=False,
            enable_architecture=False
        )
    
    def test_engine_initialization(self):
        """测试引擎初始化"""
        self.assertIsNotNone(self.engine)
        self.assertFalse(self.engine._running)
    
    def test_proposal_generation(self):
        """测试提案生成"""
        result = self.engine.scan_once()
        self.assertIn('proposals', result)
    
    def test_proposal_execution(self):
        """测试提案执行（需要批准）"""
        proposals = self.engine.get_proposals()
        if proposals:
            proposal_id = proposals[0]['id']
            status = self.engine.get_execution_status(proposal_id)
            self.assertIsNotNone(status)


class TestSelfAwarenessIntegration(unittest.TestCase):
    """SelfAwarenessSystem 集成测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.system = SelfAwarenessSystem(
            project_root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    
    def test_system_initialization(self):
        """测试系统初始化"""
        self.assertIsNotNone(self.system)
        self.assertIn('mirror_launcher', self.system._components)
    
    def test_health_check(self):
        """测试健康检查"""
        health = self.system.get_health_status()
        self.assertIn('status', health)


class TestA2AProtocolIntegration(unittest.TestCase):
    """A2A 协议集成测试"""
    
    def test_protocol_initialization(self):
        """测试协议初始化"""
        protocol = A2AProtocol()
        self.assertIsNotNone(protocol)
    
    def test_message_creation(self):
        """测试消息创建"""
        msg = AgentMessage(
            sender="agent1",
            receiver="agent2",
            action="execute",
            payload={"task": "test"}
        )
        self.assertEqual(msg.sender, "agent1")
        self.assertEqual(msg.action, "execute")


class TestIntegrationFlow(unittest.TestCase):
    """端到端集成流程测试"""
    
    def test_intent_to_agent_flow(self):
        """测试 Intent → Agent 流程"""
        # 1. 解析意图
        engine = IntentEngine()
        intent = engine.parse("写一个登录功能")
        self.assertIsNotNone(intent)
        
        # 2. 创建任务
        factory = AgentFactory()
        orchestrator = AgentOrchestrator(agent_factory=factory)
        task = orchestrator.create_task(
            description=f"执行意图: {intent.description}",
            priority=TaskPriority.MEDIUM
        )
        self.assertIsNotNone(task)
    
    def test_agent_collaboration_flow(self):
        """测试多代理协作流程"""
        factory = AgentFactory()
        orchestrator = AgentOrchestrator(agent_factory=factory)
        
        # 创建多个代理
        agents = [
            factory.create_agent("coder", {"name": f"coder_{i}"})
            for i in range(3)
        ]
        
        # 创建协作任务
        task = orchestrator.create_task(
            description="多代理协作任务",
            priority=TaskPriority.HIGH
        )
        
        # 分配给多个代理
        for agent in agents:
            orchestrator.assign_task(task.id, agent.id)
        
        self.assertEqual(len(orchestrator.get_task_assignments(task.id)), 3)


def run_integration_tests():
    """运行所有集成测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestIntentEngineIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestAgentOrchestratorIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestEvolutionEngineIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestSelfAwarenessIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestA2AProtocolIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationFlow))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出摘要
    print("\n" + "="*60)
    print("Phase 1 集成测试摘要")
    print("="*60)
    print(f"测试总数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print("="*60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
