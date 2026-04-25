"""
A2A 协议集成测试
测试多智能体通信和协作

Author: LivingTreeAI Team
"""

import asyncio
import json
import pytest
import sys
sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent')

from core.a2a_protocol import (
    MessageType, AgentCapability, AgentInfo, A2AMessage,
    Task, A2AProtocol, AgentRegistry, TaskOrchestrator
)


class TestAgentInfo:
    """测试智能体信息"""
    
    def test_create_agent_info(self):
        """测试创建智能体信息"""
        agent = AgentInfo(
            agent_id="agent_001",
            name="TestAgent",
            capabilities=[AgentCapability.CODE_GENERATION, AgentCapability.CODE_REVIEW],
            description="A test agent"
        )
        
        assert agent.agent_id == "agent_001"
        assert agent.name == "TestAgent"
        assert len(agent.capabilities) == 2
        assert agent.status == "online"
    
    def test_to_dict_from_dict(self):
        """测试序列化/反序列化"""
        original = AgentInfo(
            agent_id="agent_001",
            name="TestAgent",
            capabilities=[AgentCapability.CODE_GENERATION]
        )
        
        data = original.to_dict()
        restored = AgentInfo.from_dict(data)
        
        assert restored.agent_id == original.agent_id
        assert restored.name == original.name
        assert restored.capabilities == original.capabilities


class TestA2AMessage:
    """测试 A2A 消息"""
    
    def test_create_task_request(self):
        """测试创建任务请求消息"""
        message = A2AMessage(
            method=MessageType.TASK_REQUEST,
            params={
                "task_type": "code_generation",
                "description": "Generate fibonacci function",
                "priority": 5
            }
        )
        
        assert message.method == MessageType.TASK_REQUEST
        assert message.params["task_type"] == "code_generation"
        assert message.jsonrpc == "2.0"
    
    def test_create_task_response(self):
        """测试创建任务响应消息"""
        message = A2AMessage(
            id="msg_001",
            result={
                "task_id": "task_001",
                "status": "accepted"
            }
        )
        
        assert message.result is not None
        assert message.result["task_id"] == "task_001"
    
    def test_to_dict_from_dict(self):
        """测试消息序列化"""
        original = A2AMessage(
            method=MessageType.HEART_BEAT,
            params={"agent_id": "agent_001"}
        )
        
        data = original.to_dict()
        restored = A2AMessage.from_dict(data)
        
        assert restored.method == original.method
        assert restored.params == original.params
        assert restored.jsonrpc == original.jsonrpc


class TestTask:
    """测试任务"""
    
    def test_create_task(self):
        """测试创建任务"""
        task = Task(
            task_type="code_generation",
            description="Generate factorial function",
            params={"language": "python"},
            priority=7
        )
        
        assert task.task_type == "code_generation"
        assert task.description == "Generate factorial function"
        assert task.priority == 7
        assert task.status == "pending"
        assert task.task_id is not None
    
    def test_task_serialization(self):
        """测试任务序列化"""
        task = Task(
            task_type="testing",
            description="Run unit tests",
            priority=5
        )
        
        data = task.to_dict()
        restored = Task.from_dict(data)
        
        assert restored.task_id == task.task_id
        assert restored.task_type == task.task_type
        assert restored.priority == task.priority
    
    def test_get_duration(self):
        """测试获取任务持续时间"""
        task = Task(
            task_type="test",
            description="Test task",
            started_at=1000.0,
            completed_at=1010.0
        )
        
        duration = task.get_duration()
        assert duration == 10.0


class TestAgentRegistry:
    """测试智能体注册表"""
    
    @pytest.fixture
    def registry(self):
        return AgentRegistry()
    
    def test_register_agent(self, registry):
        """测试注册智能体"""
        agent = AgentInfo(
            agent_id="agent_001",
            name="Coder",
            capabilities=[AgentCapability.CODE_GENERATION]
        )
        
        registry.register(agent)
        
        assert len(registry.agents) == 1
        assert registry.get_agent("agent_001") == agent
    
    def test_unregister_agent(self, registry):
        """测试注销智能体"""
        agent = AgentInfo(
            agent_id="agent_001",
            name="Coder",
            capabilities=[AgentCapability.CODE_GENERATION]
        )
        
        registry.register(agent)
        registry.unregister("agent_001")
        
        assert len(registry.agents) == 0
        assert registry.get_agent("agent_001") is None
    
    def test_find_agents_by_capability(self, registry):
        """测试按能力查找"""
        agents = [
            AgentInfo(
                agent_id=f"agent_{i}",
                name=f"Agent {i}",
                capabilities=[cap]
            )
            for i, cap in enumerate([
                AgentCapability.CODE_GENERATION,
                AgentCapability.CODE_REVIEW,
                AgentCapability.CODE_GENERATION
            ])
        ]
        
        for agent in agents:
            registry.register(agent)
        
        coders = registry.find_agents_by_capability(AgentCapability.CODE_GENERATION)
        assert len(coders) == 2
        
        reviewers = registry.find_agents_by_capability(AgentCapability.CODE_REVIEW)
        assert len(reviewers) == 1


class TestA2AProtocol:
    """测试 A2A 协议"""
    
    @pytest.fixture
    def protocol(self):
        agent = AgentInfo(
            agent_id="agent_001",
            name="TestAgent",
            capabilities=[AgentCapability.CODE_GENERATION]
        )
        return A2AProtocol(agent)
    
    @pytest.mark.asyncio
    async def test_create_task(self, protocol):
        """测试创建任务"""
        task = await protocol.create_task(
            task_type="code_generation",
            description="Generate sum function",
            priority=5
        )
        
        assert task.task_id is not None
        assert task.task_type == "code_generation"
        assert len(protocol.tasks) == 1
    
    @pytest.mark.asyncio
    async def test_receive_message(self, protocol):
        """测试接收消息"""
        data = {
            "jsonrpc": "2.0",
            "id": "msg_001",
            "method": "task_request",
            "params": {
                "task_type": "testing",
                "description": "Run tests"
            }
        }
        
        response = await protocol.receive_message(data)
        
        assert response.id == "msg_001"
        assert response.result is not None
        assert "task_id" in response.result
    
    @pytest.mark.asyncio
    async def test_heartbeat(self, protocol):
        """测试心跳"""
        data = {
            "jsonrpc": "2.0",
            "id": "hb_001",
            "method": "heartbeat"
        }
        
        response = await protocol.receive_message(data)
        
        assert response.result is not None
        assert response.result["agent_id"] == "agent_001"
        assert response.result["status"] == "online"


class TestTaskOrchestrator:
    """测试任务编排器"""
    
    @pytest.fixture
    def orchestrator(self):
        agent = AgentInfo(
            agent_id="agent_001",
            name="TestAgent",
            capabilities=[AgentCapability.CODE_GENERATION]
        )
        protocol = A2AProtocol(agent)
        registry = AgentRegistry()
        return TaskOrchestrator(registry, protocol)
    
    @pytest.mark.asyncio
    async def test_decompose_task(self, orchestrator):
        """测试任务分解"""
        task = await orchestrator.protocol.create_task(
            task_type="complex_task",
            description="A complex task"
        )
        
        subtasks = await orchestrator.decompose_task(task)
        
        assert len(subtasks) >= 1
    
    @pytest.mark.asyncio
    async def test_execute_workflow(self, orchestrator):
        """测试执行工作流"""
        workflow = [
            {"type": "planning", "description": "Plan the solution", "capability": "task_planning"},
            {"type": "coding", "description": "Write code", "capability": "code_generation", "priority": 7}
        ]
        
        results = await orchestrator.execute_workflow(workflow)
        
        assert len(results) == 2


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
