"""
Multi-Agent 模块 - 多智能体协作系统

Phase 2 核心：多智能体协作、动态任务分解、代理生命周期管理
"""

from .workflow_engine import (
    MultiAgentWorkflow, DynamicTaskDecomposer, AgentLifecycleManager,
    Task, TaskStatus, Agent, AgentRole, WorkflowStep,
    get_multi_agent_workflow, get_task_decomposer, get_lifecycle_manager,
)
from .agent_memory import (
    AgentMemoryStore, SharedMemorySpace, AgentMemoryBridge, MemoryType,
    get_memory_bridge,
)
from .collaboration import TaskScheduler, ResultAggregator, ConflictResolver
from .protocol import (
    AgentProtocol, AgentMessage, MessageType, ProtocolRegistry,
    get_protocol_registry,
)
from .performance import (
    MetricsCollector, PerformanceMonitor, PerformanceDashboard, MetricType,
    get_metrics_collector, get_performance_monitor, get_performance_dashboard,
)

__all__ = [
    'MultiAgentWorkflow', 'DynamicTaskDecomposer', 'AgentLifecycleManager',
    'Task', 'TaskStatus', 'Agent', 'AgentRole', 'WorkflowStep',
    'get_multi_agent_workflow', 'get_task_decomposer', 'get_lifecycle_manager',
    'AgentMemoryStore', 'SharedMemorySpace', 'AgentMemoryBridge', 'MemoryType',
    'get_memory_bridge',
    'TaskScheduler', 'ResultAggregator', 'ConflictResolver',
    'AgentProtocol', 'AgentMessage', 'MessageType', 'ProtocolRegistry',
    'get_protocol_registry',
    'MetricsCollector', 'PerformanceMonitor', 'PerformanceDashboard', 'MetricType',
    'get_metrics_collector', 'get_performance_monitor', 'get_performance_dashboard',
]
