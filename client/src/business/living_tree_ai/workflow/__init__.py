"""工作流模块"""

from .models.workflow import Workflow, WorkflowExecution, WorkflowStatus
from .models.connection import NodeConnection
from .models.node import WorkflowNodeModel, WorkflowNode
from .models.node import NodeType, NodeStatus, Port, Position
from .models.types import Variable, VariableType
from .registry.node_registry import NodeRegistry, get_registry
from .registry.builtin_nodes import register_builtin_nodes
from .registry.ai_templates import register_ai_templates
from .registry.node_discovery import NodeDiscoverer, get_node_discoverer
from .engine.converter import TaskChainConverter, TaskItem
from .engine.executor import WorkflowExecutor, ExecutionResult
from .engine.validator import WorkflowValidator, ValidationError
from .engine.generator import WorkflowGenerator, get_workflow_generator
from .template_manager import WorkflowTemplate, TemplateManager

__all__ = [
    'Workflow',
    'WorkflowExecution',
    'WorkflowNode',
    'NodeConnection',
    'WorkflowStatus',
    'WorkflowNodeModel',
    'NodeType',
    'NodeStatus',
    'Port',
    'Position',
    'Variable',
    'VariableType',
    'NodeRegistry',
    'get_registry',
    'register_builtin_nodes',
    'register_ai_templates',
    'NodeDiscoverer',
    'get_node_discoverer',
    'TaskChainConverter',
    'TaskItem',
    'WorkflowExecutor',
    'ExecutionResult',
    'WorkflowValidator',
    'ValidationError',
    'WorkflowGenerator',
    'get_workflow_generator',
    'WorkflowTemplate',
    'TemplateManager'
]