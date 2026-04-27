#!/usr/bin/env python3
"""
LivingTreeAI Phase 2 Multi-Agent 测试套件
"""

import unittest
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.src.business.multi_agent import (
    MultiAgentWorkflow,
    DynamicTaskDecomposer,
    AgentLifecycleManager,
    TaskStatus,
    AgentRole,
)


class TestMultiAgentWorkflow(unittest.TestCase):
    """MultiAgentWorkflow 测试"""
    
    def setUp(self):
        self.workflow = MultiAgentWorkflow("test_wf", "测试工作流")
    
    def test_workflow_creation(self):
        """测试工作流创建"""
        self.assertEqual(self.workflow.name, "测试工作流")
        self.assertEqual(self.workflow.status, "initialized")
    
    def test_agent_registration(self):
        """测试代理注册"""
        result = self.workflow.register_agent(
            "agent1", "测试代理", AgentRole.EXECUTOR,
            ["coding", "testing"]
        )
        self.assertTrue(result)
        self.assertIn("agent1", self.workflow.agents)
    
    def test_task_creation(self):
        """测试任务创建"""
        task = self.workflow.create_task("测试任务", priority=1)
        self.assertIsNotNone(task)
        self.assertEqual(task.description, "测试任务")
    
    def test_task_assignment(self):
        """测试任务分配"""
        self.workflow.register_agent("agent1", "测试代理", AgentRole.EXECUTOR, [])
        task = self.workflow.create_task("测试任务")
        
        result = self.workflow.assign_task(task.id, "agent1")
        self.assertTrue(result)
        self.assertEqual(task.assigned_agent, "agent1")
    
    def test_task_dependencies(self):
        """测试任务依赖"""
        task1 = self.workflow.create_task("任务1")
        task2 = self.workflow.create_task("任务2", dependencies=[task1.id])
        
        self.assertEqual(task2.dependencies, [task1.id])
        
        # 任务2还不能开始
        self.assertFalse(self.workflow.can_start_task(task2.id))
        
        # 完成任务1后，任务2可以开始
        self.workflow.complete_task(task1.id, "完成")
        self.assertTrue(self.workflow.can_start_task(task2.id))


class TestDynamicTaskDecomposer(unittest.TestCase):
    """DynamicTaskDecomposer 测试"""
    
    def setUp(self):
        self.decomposer = DynamicTaskDecomposer()
    
    def test_decomposer_creation(self):
        """测试分解器创建"""
        self.assertIsNotNone(self.decomposer)
    
    def test_parallel_decomposition(self):
        """测试并行分解"""
        tasks = self.decomposer.decompose("写代码 和 测试代码 和 部署代码", mode='parallel')
        self.assertEqual(len(tasks), 3)
    
    def test_sequential_decomposition(self):
        """测试顺序分解"""
        tasks = self.decomposer.decompose("首先写代码 然后测试代码", mode='sequential')
        self.assertGreaterEqual(len(tasks), 2)
    
    def test_auto_mode_detection(self):
        """测试自动模式检测"""
        # 并行关键词
        mode = self.decomposer._detect_decomposition_mode("写代码 和 测试代码")
        self.assertEqual(mode, 'parallel')
        
        # 顺序关键词
        mode = self.decomposer._detect_decomposition_mode("首先分析 然后实现")
        self.assertEqual(mode, 'sequential')


class TestAgentLifecycleManager(unittest.TestCase):
    """AgentLifecycleManager 测试"""
    
    def setUp(self):
        self.manager = AgentLifecycleManager()
    
    def test_manager_creation(self):
        """测试管理器创建"""
        self.assertIsNotNone(self.manager)
    
    def test_factory_registration(self):
        """测试工厂注册"""
        def test_factory(name, **kwargs):
            from client.src.business.multi_agent import Agent, AgentRole
            return Agent(
                id="test_id",
                name=name,
                role=AgentRole.EXECUTOR,
                capabilities=[]
            )
        
        result = self.manager.register_factory("test", test_factory)
        self.assertTrue(result)
        self.assertIn("test", self.manager.agent_creation_factory)
    
    def test_agent_pool(self):
        """测试代理池"""
        from client.src.business.multi_agent import Agent, AgentRole
        
        agent = Agent(
            id="pool_agent",
            name="池代理",
            role=AgentRole.EXECUTOR,
            capabilities=[]
        )
        
        self.manager.add_to_pool("default", agent)
        pool = self.manager.get_agent_pool("default")
        self.assertEqual(len(pool), 1)
        
        retrieved = self.manager.get_from_pool("default")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, "pool_agent")
    
    def test_lifecycle_hooks(self):
        """测试生命周期钩子"""
        hook_called = []
        
        def test_hook(agent):
            hook_called.append(agent.id)
        
        self.manager.register_hook('on_create', test_hook)


def run_phase2_tests():
    """运行 Phase 2 测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestMultiAgentWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestDynamicTaskDecomposer))
    suite.addTests(loader.loadTestsFromTestCase(TestAgentLifecycleManager))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    print("Phase 2 Multi-Agent 测试报告")
    print("="*60)
    print(f"测试总数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print("="*60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_phase2_tests()
    sys.exit(0 if success else 1)
