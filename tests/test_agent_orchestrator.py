"""
Agent Orchestrator 集成测试
测试多智能体协作和任务调度

Author: LivingTreeAI Team
"""

import asyncio
import time
import pytest
from typing import List, Dict, Any

# 导入被测模块
import sys
sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent')

from client.src.business.agent import (
    AgentType, AgentCapability, TaskStatus, TaskPriority,
    Agent, AgentFactory, AgentOrchestrator, MockTaskExecutor,
    WorkflowDefinition, TaskContext
)


class TestAgentFactory:
    """测试智能体工厂"""
    
    def test_create_agent(self):
        """测试创建单个智能体"""
        agent = AgentFactory.create_agent(AgentType.CODER, "TestCoder")
        
        assert agent.name == "TestCoder"
        assert agent.agent_type == AgentType.CODER
        assert AgentCapability.CODE_GENERATION in agent.capabilities
        assert agent.is_available()
    
    def test_create_development_team(self):
        """测试创开发团队"""
        team = AgentFactory.create_team("development")
        
        assert len(team) == 4
        types = [a.agent_type for a in team]
        assert AgentType.PLANNER in types
        assert AgentType.CODER in types
        assert AgentType.REVIEWER in types
        assert AgentType.TESTER in types
    
    def test_create_research_team(self):
        """测试创建研究团队"""
        team = AgentFactory.create_team("research")
        
        assert len(team) == 3
        types = [a.agent_type for a in team]
        assert AgentType.PLANNER in types
        assert AgentType.RESEARCHER in types
        assert AgentType.ANALYZER in types


class TestTaskQueue:
    """测试任务队列"""
    
    def test_enqueue_dequeue(self):
        """测试入队出队"""
        from client.src.business.agent import TaskQueue
        
        queue = TaskQueue()
        
        task1 = TaskContext(task_id="t1", description="Task 1", priority=TaskPriority.NORMAL)
        task2 = TaskContext(task_id="t2", description="Task 2", priority=TaskPriority.HIGH)
        task3 = TaskContext(task_id="t3", description="Task 3", priority=TaskPriority.LOW)
        
        queue.enqueue(task1)
        queue.enqueue(task2)
        queue.enqueue(task3)
        
        assert queue.size() == 3
        
        # 高优先级先出
        first = queue.dequeue()
        assert first.task_id == "t2"
        
        second = queue.dequeue()
        assert second.task_id == "t1"
    
    def test_priority_ordering(self):
        """测试优先级排序"""
        from client.src.business.agent import TaskQueue
        
        queue = TaskQueue()
        
        # 创建不同优先级的任务
        tasks = []
        for i, priority in enumerate([TaskPriority.LOW, TaskPriority.NORMAL, 
                                       TaskPriority.HIGH, TaskPriority.CRITICAL]):
            task = TaskContext(
                task_id=f"t{i}", 
                description=f"Task {i}",
                priority=priority
            )
            tasks.append(task)
            queue.enqueue(task)
        
        # 按优先级顺序出队
        dequeued = []
        while not queue.is_empty():
            task = queue.dequeue()
            dequeued.append(task.priority)
        
        # 应该是从高到低
        expected = [TaskPriority.CRITICAL, TaskPriority.HIGH, 
                   TaskPriority.NORMAL, TaskPriority.LOW]
        assert dequeued == expected


class TestWorkflowDefinition:
    """测试工作流定义"""
    
    def test_add_tasks(self):
        """测试添加任务"""
        workflow = WorkflowDefinition(name="Test Workflow")
        
        t1_id = workflow.add_task("Task 1", priority=TaskPriority.HIGH)
        t2_id = workflow.add_task("Task 2", priority=TaskPriority.NORMAL)
        t3_id = workflow.add_task("Task 3", priority=TaskPriority.LOW)
        
        assert len(workflow.tasks) == 3
        assert t1_id in workflow.tasks
        assert t2_id in workflow.tasks
        assert t3_id in workflow.tasks
    
    def test_add_dependencies(self):
        """测试添加依赖"""
        workflow = WorkflowDefinition(name="Test Workflow")
        
        t1_id = workflow.add_task("Task 1")
        t2_id = workflow.add_task("Task 2")
        t3_id = workflow.add_task("Task 3")
        
        # T2 和 T3 依赖 T1
        workflow.add_dependency(t1_id, t2_id)
        workflow.add_dependency(t1_id, t3_id)
        
        assert t2_id in workflow.tasks[t1_id].dependents
        assert t3_id in workflow.tasks[t1_id].dependents
        assert t1_id in workflow.tasks[t2_id].dependencies
        assert t1_id in workflow.tasks[t3_id].dependencies
    
    def test_get_execution_order(self):
        """测试执行顺序计算"""
        workflow = WorkflowDefinition(name="Test Workflow")
        
        t1_id = workflow.add_task("Task 1")  # 无依赖，最先执行
        t2_id = workflow.add_task("Task 2")
        t3_id = workflow.add_task("Task 3")
        t4_id = workflow.add_task("Task 4")
        
        # 依赖关系: T1 -> T2, T1 -> T3, T2 -> T4, T3 -> T4
        workflow.add_dependency(t1_id, t2_id)
        workflow.add_dependency(t1_id, t3_id)
        workflow.add_dependency(t2_id, t4_id)
        workflow.add_dependency(t3_id, t4_id)
        
        layers = workflow.get_execution_order()
        
        # 第一层: T1
        assert layers[0] == [t1_id]
        # 第二层: T2, T3 (可以并行)
        assert set(layers[1]) == {t2_id, t3_id}
        # 第三层: T4
        assert layers[2] == [t4_id]


class TestAgentOrchestrator:
    """测试智能体编排器"""
    
    @pytest.fixture
    def orchestrator(self):
        """创建编排器实例"""
        executor = MockTaskExecutor()
        orch = AgentOrchestrator(executor)
        
        # 注册测试智能体
        team = AgentFactory.create_team("development")
        for agent in team:
            orch.register_agent(agent)
        
        return orch
    
    @pytest.mark.asyncio
    async def test_register_agents(self, orchestrator):
        """测试注册智能体"""
        agents = orchestrator.get_all_agents()
        assert len(agents) == 4
    
    @pytest.mark.asyncio
    async def test_submit_task(self, orchestrator):
        """测试提交任务"""
        task_id = orchestrator.submit_task(
            "Generate Python code for factorial",
            priority=TaskPriority.NORMAL
        )
        
        assert task_id is not None
        assert orchestrator.task_queue.size() == 1
    
    @pytest.mark.asyncio
    async def test_task_execution(self, orchestrator):
        """测试任务执行"""
        # 提交任务
        task_id = orchestrator.submit_task(
            "Write a unit test",
            priority=TaskPriority.HIGH,
            timeout=10
        )
        
        # 启动编排器
        await orchestrator.start()
        
        # 等待任务完成
        await asyncio.sleep(6)
        
        # 检查任务状态
        status = orchestrator.get_task_status(task_id)
        assert status == TaskStatus.COMPLETED
        
        # 获取结果
        result = orchestrator.get_task_result(task_id)
        assert result is not None
        assert result["status"] == "completed"
        
        # 停止编排器
        await orchestrator.stop()
    
    @pytest.mark.asyncio
    async def test_workflow_execution(self, orchestrator):
        """测试工作流执行"""
        # 创建工作流
        workflow = WorkflowDefinition(name="Code Review Workflow")
        
        t1 = workflow.add_task("Write code", priority=TaskPriority.HIGH)
        t2 = workflow.add_task("Review code", priority=TaskPriority.NORMAL)
        t3 = workflow.add_task("Run tests", priority=TaskPriority.NORMAL)
        
        workflow.add_dependency(t1, t2)
        workflow.add_dependency(t2, t3)
        
        # 提交工作流
        workflow_id = orchestrator.submit_workflow(workflow)
        assert workflow_id is not None
        
        # 启动编排器
        await orchestrator.start()
        
        # 等待执行
        await asyncio.sleep(15)
        
        # 检查所有任务状态
        for task in workflow.tasks.values():
            status = orchestrator.get_task_status(task.task_id)
            assert status == TaskStatus.COMPLETED
        
        await orchestrator.stop()
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, orchestrator):
        """测试取消任务"""
        task_id = orchestrator.submit_task(
            "Long running task",
            priority=TaskPriority.LOW,
            timeout=100
        )
        
        await orchestrator.start()
        await asyncio.sleep(1)
        
        # 取消任务
        success = await orchestrator.cancel_task(task_id)
        assert success
        
        status = orchestrator.get_task_status(task_id)
        assert status == TaskStatus.CANCELLED
        
        await orchestrator.stop()
    
    @pytest.mark.asyncio
    async def test_get_stats(self, orchestrator):
        """测试统计信息"""
        # 提交几个任务
        for i in range(3):
            orchestrator.submit_task(f"Task {i}")
        
        stats = orchestrator.get_stats()
        
        assert stats["total_agents"] == 4
        assert stats["queue_size"] == 3
        assert stats["active_tasks"] == 0
        assert stats["total_tasks"] >= 3


class TestAgentCapabilities:
    """测试智能体能力匹配"""
    
    def test_find_available_agent(self):
        """测试查找可用智能体"""
        executor = MockTaskExecutor()
        orchestrator = AgentOrchestrator(executor)
        
        # 注册智能体
        coder = AgentFactory.create_agent(AgentType.CODER, "Coder1")
        reviewer = AgentFactory.create_agent(AgentType.REVIEWER, "Reviewer1")
        
        orchestrator.register_agent(coder)
        orchestrator.register_agent(reviewer)
        
        # 查找代码生成智能体
        agent = orchestrator.find_available_agent(AgentCapability.CODE_GENERATION)
        assert agent is not None
        assert agent.agent_type == AgentType.CODER
        
        # 查找代码审查智能体
        agent = orchestrator.find_available_agent(AgentCapability.CODE_REVIEW)
        assert agent is not None
        assert agent.agent_type == AgentType.REVIEWER
        
        # 查找不存在的智能体
        agent = orchestrator.find_available_agent(AgentCapability.DEPLOYMENT)
        assert agent is None


class TestTaskContext:
    """测试任务上下文"""
    
    def test_task_creation(self):
        """测试创建任务"""
        task = TaskContext(
            task_id="test_001",
            description="Test task",
            params={"key": "value"},
            priority=TaskPriority.HIGH,
            timeout=60
        )
        
        assert task.task_id == "test_001"
        assert task.description == "Test task"
        assert task.params["key"] == "value"
        assert task.priority == TaskPriority.HIGH
        assert task.timeout == 60
        assert task.status == TaskStatus.PENDING
    
    def test_task_to_dict(self):
        """测试任务序列化"""
        task = TaskContext(
            task_id="test_001",
            description="Test task",
            priority=TaskPriority.NORMAL
        )
        
        data = task.to_dict()
        
        assert data["task_id"] == "test_001"
        assert data["description"] == "Test task"
        assert data["priority"] == TaskPriority.NORMAL.value
        assert data["status"] == TaskStatus.PENDING.value


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
