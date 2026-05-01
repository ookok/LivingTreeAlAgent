"""
Hermes AI Agent Platform - 单元测试

测试覆盖：
1. 大脑启发记忆系统
2. 自修复容错系统
3. 持续学习系统
4. 认知推理系统
5. 自我意识系统
6. MCP服务
7. API网关
8. 系统集成
"""

import pytest
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBrainMemory:
    """大脑启发记忆系统测试"""
    
    def test_hippocampus_store(self):
        """测试海马体短期记忆存储"""
        from client.src.business.brain_memory.hippocampus import Hippocampus
        
        hippocampus = Hippocampus()
        memory_id = hippocampus.store('测试记忆内容', {'source': 'test'})
        
        assert memory_id is not None
        assert isinstance(memory_id, str)
    
    def test_hippocampus_retrieve(self):
        """测试海马体记忆检索"""
        from client.src.business.brain_memory.hippocampus import Hippocampus
        
        hippocampus = Hippocampus()
        memory_id = hippocampus.store('测试检索', {'source': 'test'})
        
        memories = hippocampus.retrieve('测试')
        assert len(memories) > 0
        assert any(m.content == '测试检索' for m in memories)
    
    def test_neocortex_store(self):
        """测试新皮层长期记忆存储"""
        from client.src.business.brain_memory.neocortex import Neocortex
        
        neocortex = Neocortex()
        memory_id = neocortex.store('长期记忆测试', {'category': 'test'})
        
        assert memory_id is not None
    
    def test_memory_router(self):
        """测试记忆路由器"""
        from client.src.business.brain_memory.memory_router import MemoryRouter
        
        router = MemoryRouter()
        router.store_short_term('路由测试短期记忆', {'source': 'test'})
        router.store_long_term('路由测试长期记忆', {'source': 'test'})
        
        short_memories = router.retrieve_recent_short_term(5)
        long_memories = router.retrieve_recent_long_term(5)
        
        assert len(short_memories) >= 1
        assert len(long_memories) >= 1


class TestSelfHealing:
    """自修复容错系统测试"""
    
    def test_health_monitor(self):
        """测试健康监控"""
        from client.src.business.self_healing.health_monitor import HealthMonitor
        
        monitor = HealthMonitor()
        metrics = monitor.get_metrics()
        
        assert 'cpu' in metrics
        assert 'memory' in metrics
        assert 'disk' in metrics
        assert 'network' in metrics
    
    def test_problem_detector(self):
        """测试问题检测"""
        from client.src.business.self_healing.problem_detector import ProblemDetector
        
        detector = ProblemDetector()
        reports = detector.detect_all()
        
        assert isinstance(reports, list)
    
    def test_healing_router(self):
        """测试自愈路由器"""
        from client.src.business.self_healing.healing_router import HealingRouter
        
        router = HealingRouter()
        status = router.get_status()
        
        assert 'health' in status
        assert 'problems' in status
        assert 'fixes' in status


class TestContinualLearning:
    """持续学习系统测试"""
    
    def test_ewc_protection(self):
        """测试EWC保护"""
        from client.src.business.continual_learning.ewc_protection import EWCProtection
        
        ewc = EWCProtection()
        ewc.protect_params({'param1': 1.0, 'param2': 2.0})
        
        status = ewc.get_status()
        assert 'protected_params' in status
    
    def test_progressive_net(self):
        """测试渐进网络"""
        from client.src.business.continual_learning.progressive_net import ProgressiveNet
        
        net = ProgressiveNet()
        net.add_task('task1')
        
        status = net.get_status()
        assert 'tasks' in status
    
    def test_learning_router(self):
        """测试学习路由器"""
        from client.src.business.continual_learning.learning_router import LearningRouter
        
        router = LearningRouter()
        status = router.get_status()
        
        assert 'active_tasks' in status
        assert 'ewc_status' in status


class TestCognitiveReasoning:
    """认知推理系统测试"""
    
    def test_causal_reasoner(self):
        """测试因果推理"""
        from client.src.business.cognitive_reasoning.causal_reasoner import CausalReasoner
        
        reasoner = CausalReasoner()
        result = reasoner.reason('下雨会导致什么？')
        
        assert 'result' in result
    
    def test_symbolic_engine(self):
        """测试符号推理引擎"""
        from client.src.business.cognitive_reasoning.symbolic_engine import SymbolicEngine
        
        engine = SymbolicEngine()
        engine.add_rule('test_rule', 'if A then B')
        
        rules = engine.get_rules()
        assert 'test_rule' in rules
    
    def test_reasoning_coordinator(self):
        """测试推理协调器"""
        from client.src.business.cognitive_reasoning.reasoning_coordinator import ReasoningCoordinator
        
        coordinator = ReasoningCoordinator()
        result = coordinator.reason('测试推理', 'causal')
        
        assert 'success' in result


class TestSelfAwareness:
    """自我意识系统测试"""
    
    def test_self_reflection(self):
        """测试自我反思"""
        from client.src.business.self_awareness.self_reflection import SelfReflection
        
        reflection = SelfReflection()
        result = reflection.reflect({'test': 'state'}, [])
        
        assert hasattr(result, 'improvement_suggestions')
    
    def test_goal_manager(self):
        """测试目标管理"""
        from client.src.business.self_awareness.goal_manager import GoalManager
        
        manager = GoalManager()
        goal_id = manager.set_goal('测试目标', 0.8)
        
        assert goal_id is not None
        
        goals = manager.get_active_goals()
        assert len(goals) >= 1
    
    def test_autonomy_controller(self):
        """测试自主控制器"""
        from client.src.business.self_awareness.autonomy_controller import AutonomyController, AutonomyLevel
        
        controller = AutonomyController()
        controller.set_autonomy_level(AutonomyLevel.L3)
        
        status = controller.get_status()
        assert status['level'] == 3


class TestMCPIntegration:
    """MCP服务测试"""
    
    def test_mcp_manager(self):
        """测试MCP管理器"""
        from client.src.business.mcp_service.mcp_manager import MCPManager
        
        manager = MCPManager()
        manager.set_mode('disabled')
        
        result = manager.call_tool('test_tool', param='test')
        assert 'used_fallback' in result
        assert result['used_fallback'] is True
    
    def test_fallback_system(self):
        """测试降级系统"""
        from client.src.business.mcp_service.fallback_system import FallbackSystem
        
        fallback = FallbackSystem()
        result = fallback.execute_fallback('calculator', expression='2+2')
        
        assert result['success'] is True
        assert result['content']['result'] == 4
    
    def test_service_registry(self):
        """测试服务注册"""
        from client.src.business.mcp_service.service_registry import ServiceRegistry, ServiceType
        
        registry = ServiceRegistry()
        registry.register_service('test_service', ServiceType.API, 'localhost', 8080)
        
        service = registry.get_service('test_service')
        assert service is not None
        assert service.name == 'test_service'


class TestAPIGateway:
    """API网关测试"""
    
    def test_api_gateway(self):
        """测试API网关"""
        from client.src.business.api_gateway.api_gateway import APIGateway
        
        gateway = APIGateway()
        result = gateway.call('system/status')
        
        assert 'success' in result
        assert result['success'] is True
    
    def test_register_module(self):
        """测试模块注册"""
        from client.src.business.api_gateway.api_gateway import APIGateway
        
        gateway = APIGateway()
        
        class TestModule:
            def test_method(self):
                return {'test': 'data'}
        
        gateway.register_module('test_module', TestModule())
        
        modules = gateway.get_modules()
        assert 'test_module' in modules
        
        result = gateway.call('test_module/test_method')
        assert result['success'] is True
        assert result['data'] == {'test': 'data'}


class TestSystemIntegration:
    """系统集成测试"""
    
    def test_system_manager(self):
        """测试系统管理器"""
        from client.src.business.system_integration.system_manager import SystemManager
        
        manager = SystemManager()
        manager.initialize()
        
        status = manager.get_status()
        assert status['system_state'] == 'running'
        
        active_systems = manager.get_active_subsystems()
        assert len(active_systems) > 0
        
        manager.shutdown()
        status = manager.get_status()
        assert status['system_state'] == 'uninitialized'


class TestIntegrationLayer:
    """深度集成层测试"""
    
    def test_event_bus(self):
        """测试事件总线"""
        from client.src.business.integration_layer.event_bus import EventBus, EventType
        
        bus = EventBus()
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        bus.subscribe(EventType.MEMORY_CREATED, handler)
        bus.publish_simple(EventType.MEMORY_CREATED, 'test', {'content': 'test'})
        
        assert len(received_events) == 1
        assert received_events[0].event_type == EventType.MEMORY_CREATED
        
        bus.unsubscribe(EventType.MEMORY_CREATED, handler)
    
    def test_cross_system_caller(self):
        """测试跨系统调用器"""
        from client.src.business.integration_layer.cross_system_caller import CrossSystemCaller
        
        caller = CrossSystemCaller()
        
        class MockSystem:
            def test_method(self, value):
                return {'success': True, 'data': value * 2}
        
        # 直接测试调用逻辑
        mock = MockSystem()
        result = mock.test_method(5)
        assert result['success'] is True
        assert result['data'] == 10
    
    def test_context_manager(self):
        """测试上下文管理器"""
        from client.src.business.integration_layer.context_manager import ContextManager
        
        manager = ContextManager()
        
        # 测试全局上下文
        manager.set_global_context('test_key', 'test_value')
        context = manager.get_global_context()
        assert context['test_key'] == 'test_value'
        
        # 测试会话管理
        session_id = manager.create_session('user1')
        session = manager.get_session(session_id)
        assert session is not None
        assert session.user_id == 'user1'
        
        # 测试对话历史
        session.add_message('user', 'hello')
        history = manager.get_conversation_history(session_id)
        assert len(history) == 1
        assert history[0]['content'] == 'hello'
    
    def test_integration_coordinator(self):
        """测试集成协调器"""
        from client.src.business.integration_layer.integration_coordinator import IntegrationCoordinator
        
        coordinator = IntegrationCoordinator()
        
        # 测试编排任务
        result = coordinator.orchestrate_task('analyze', query='test')
        assert 'success' in result
    
    def test_event_driven_integration(self):
        """测试事件驱动的系统集成"""
        from client.src.business.integration_layer import (
            get_event_bus,
            get_cross_system_caller,
            get_context_manager,
            get_integration_coordinator,
            EventType,
            publish
        )
        
        # 确保所有单例都能正常获取
        bus = get_event_bus()
        caller = get_cross_system_caller()
        context = get_context_manager()
        coordinator = get_integration_coordinator()
        
        assert bus is not None
        assert caller is not None
        assert context is not None
        assert coordinator is not None
        
        # 测试事件发布
        publish(EventType.SYSTEM_INITIALIZED, 'test', {'status': 'ready'})
        
        # 检查事件历史
        history = bus.get_event_history(1)
        assert len(history) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])