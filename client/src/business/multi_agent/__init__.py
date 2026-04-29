#!/usr/bin/env python3
"""
Multi-Agent 模块
Phase 2 核心：多智能体协作、动态任务分解、代理生命周期管理
"""

from .workflow_engine import (
    MultiAgentWorkflow,
    DynamicTaskDecomposer,
    AgentLifecycleManager,
    Task,
    TaskStatus,
    Agent,
    AgentRole,
    WorkflowStep,
    get_multi_agent_workflow,
    get_task_decomposer,
    get_lifecycle_manager,
)

from .agent_memory import (
    AgentMemoryStore,
    SharedMemorySpace,
    AgentMemoryBridge,
    MemoryType,
    get_memory_bridge,
)

from .collaboration import (
    TaskScheduler,
    ResultAggregator,
    ConflictResolver,
)

from .protocol import (
    AgentProtocol,
    AgentMessage,
    MessageType,
    ProtocolRegistry,
    get_protocol_registry,
)

from .performance import (
    MetricsCollector,
    PerformanceMonitor,
    PerformanceDashboard,
    MetricType,
    get_metrics_collector,
    get_performance_monitor,
    get_performance_dashboard,
)

__all__ = [
    # Workflow
    'MultiAgentWorkflow',
    'DynamicTaskDecomposer',
    'AgentLifecycleManager',
    'Task',
    'TaskStatus',
    'Agent',
    'AgentRole',
    'WorkflowStep',
    'get_multi_agent_workflow',
    'get_task_decomposer',
    'get_lifecycle_manager',
    # Memory
    'AgentMemoryStore',
    'SharedMemorySpace',
    'AgentMemoryBridge',
    'MemoryType',
    'get_memory_bridge',
    # Collaboration
    'TaskScheduler',
    'ResultAggregator',
    'ConflictResolver',
    # Protocol
    'AgentProtocol',
    'AgentMessage',
    'MessageType',
    'ProtocolRegistry',
    'get_protocol_registry',
    # Performance
    'MetricsCollector',
    'PerformanceMonitor',
    'PerformanceDashboard',
    'MetricType',
    'get_metrics_collector',
    'get_performance_monitor',
    'get_performance_dashboard',
]
