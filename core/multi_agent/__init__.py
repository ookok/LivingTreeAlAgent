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

__all__ = [
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
]
