"""
LivingTree — Agent Workflow Engine
===================================

Full migration from client/src/business/agent_workflow/__init__.py

Declarative workflow orchestration with:
- Sequential workflow: nodes execute in order
- Decision workflow: condition-based branching
- Parallel workflow: concurrent branch execution
- WorkflowBuilder: fluent API for constructing workflows
- WorkflowEngine: centralized workflow registry and execution
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class WorkflowStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeType(Enum):
    START = "start"
    END = "end"
    ACTION = "action"
    DECISION = "decision"
    PARALLEL = "parallel"
    LOOP = "loop"


@dataclass
class WorkflowNode:
    node_id: str
    node_type: NodeType
    label: str = ""
    action: Optional[Callable] = None
    next_nodes: List[str] = field(default_factory=list)
    condition: Optional[Callable[[Dict], bool]] = None
    loop_condition: Optional[Callable[[Dict], bool]] = None
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowContext:
    workflow_id: str
    variables: Dict[str, Any] = field(default_factory=dict)
    status: WorkflowStatus = WorkflowStatus.IDLE
    current_node: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class WorkflowResult:
    success: bool
    context: WorkflowContext
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BaseWorkflow(ABC):
    """Base class for all workflows."""

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.nodes: Dict[str, WorkflowNode] = {}
        self.start_node: Optional[str] = None
        self.end_nodes: List[str] = []

    def add_node(self, node: WorkflowNode):
        self.nodes[node.node_id] = node
        if node.node_type == NodeType.START:
            self.start_node = node.node_id
        elif node.node_type == NodeType.END:
            self.end_nodes.append(node.node_id)

    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        return self.nodes.get(node_id)

    @abstractmethod
    async def execute(self, input_data: Optional[Dict] = None) -> WorkflowResult:
        pass


class SequentialWorkflow(BaseWorkflow):
    """Sequential workflow — nodes execute one after another."""

    async def execute(self, input_data: Optional[Dict] = None) -> WorkflowResult:
        context = WorkflowContext(workflow_id=self.workflow_id)
        context.status = WorkflowStatus.RUNNING

        if input_data:
            context.variables.update(input_data)

        current_node_id = self.start_node

        while current_node_id:
            node = self.get_node(current_node_id)
            if not node:
                context.status = WorkflowStatus.FAILED
                context.error = f"Node not found: {current_node_id}"
                return WorkflowResult(success=False, context=context, error=context.error)

            context.current_node = current_node_id

            try:
                if node.action:
                    result = node.action(context.variables)
                    if isinstance(result, dict):
                        context.variables.update(result)

                context.history.append({
                    "node_id": current_node_id,
                    "node_type": node.node_type.value,
                    "variables": dict(context.variables),
                })

                if node.node_type == NodeType.END:
                    context.status = WorkflowStatus.COMPLETED
                    break

                if node.next_nodes:
                    current_node_id = node.next_nodes[0]
                else:
                    current_node_id = None

            except Exception as e:
                context.status = WorkflowStatus.FAILED
                context.error = str(e)
                return WorkflowResult(success=False, context=context, error=str(e))

        return WorkflowResult(
            success=context.status == WorkflowStatus.COMPLETED,
            context=context,
            output=context.variables,
        )


class DecisionWorkflow(BaseWorkflow):
    """Decision workflow — condition-based branching."""

    async def execute(self, input_data: Optional[Dict] = None) -> WorkflowResult:
        context = WorkflowContext(workflow_id=self.workflow_id)
        context.status = WorkflowStatus.RUNNING

        if input_data:
            context.variables.update(input_data)

        current_node_id = self.start_node

        while current_node_id:
            node = self.get_node(current_node_id)
            if not node:
                context.status = WorkflowStatus.FAILED
                context.error = f"Node not found: {current_node_id}"
                return WorkflowResult(success=False, context=context, error=context.error)

            context.current_node = current_node_id

            try:
                if node.action:
                    result = node.action(context.variables)
                    if isinstance(result, dict):
                        context.variables.update(result)

                context.history.append({
                    "node_id": current_node_id,
                    "node_type": node.node_type.value,
                    "variables": dict(context.variables),
                })

                if node.node_type == NodeType.END:
                    context.status = WorkflowStatus.COMPLETED
                    break

                if node.node_type == NodeType.DECISION and node.condition and node.next_nodes:
                    if node.condition(context.variables):
                        current_node_id = node.next_nodes[0]
                    else:
                        current_node_id = node.next_nodes[1] if len(node.next_nodes) > 1 else None
                elif node.next_nodes:
                    current_node_id = node.next_nodes[0]
                else:
                    current_node_id = None

            except Exception as e:
                context.status = WorkflowStatus.FAILED
                context.error = str(e)
                return WorkflowResult(success=False, context=context, error=str(e))

        return WorkflowResult(
            success=context.status == WorkflowStatus.COMPLETED,
            context=context,
            output=context.variables,
        )


class ParallelWorkflow(BaseWorkflow):
    """Parallel workflow — concurrent branch execution."""

    async def execute(self, input_data: Optional[Dict] = None) -> WorkflowResult:
        context = WorkflowContext(workflow_id=self.workflow_id)
        context.status = WorkflowStatus.RUNNING

        if input_data:
            context.variables.update(input_data)

        current_node_id = self.start_node

        while current_node_id:
            node = self.get_node(current_node_id)
            if not node:
                context.status = WorkflowStatus.FAILED
                context.error = f"Node not found: {current_node_id}"
                return WorkflowResult(success=False, context=context, error=context.error)

            context.current_node = current_node_id

            try:
                if node.action:
                    result = node.action(context.variables)
                    if isinstance(result, dict):
                        context.variables.update(result)

                context.history.append({
                    "node_id": current_node_id,
                    "node_type": node.node_type.value,
                    "variables": dict(context.variables),
                })

                if node.node_type == NodeType.END:
                    context.status = WorkflowStatus.COMPLETED
                    break

                if node.node_type == NodeType.PARALLEL and node.next_nodes:
                    tasks = []
                    for next_node_id in node.next_nodes:
                        sub_workflow = SequentialWorkflow(f"{self.workflow_id}_{next_node_id}")
                        sub_workflow.start_node = next_node_id
                        sub_workflow.nodes = self.nodes
                        tasks.append(sub_workflow.execute(dict(context.variables)))

                    results = await asyncio.gather(*tasks)
                    for result in results:
                        if result.success and result.output:
                            context.variables.update(result.output)

                    current_node_id = self._find_next_after_parallel(node.node_id)
                elif node.next_nodes:
                    current_node_id = node.next_nodes[0]
                else:
                    current_node_id = None

            except Exception as e:
                context.status = WorkflowStatus.FAILED
                context.error = str(e)
                return WorkflowResult(success=False, context=context, error=str(e))

        return WorkflowResult(
            success=context.status == WorkflowStatus.COMPLETED,
            context=context,
            output=context.variables,
        )

    def _find_next_after_parallel(self, parallel_node_id: str) -> Optional[str]:
        if self.end_nodes:
            return self.end_nodes[0]
        return None


class WorkflowBuilder:
    """Fluent API builder for constructing workflows."""

    def __init__(self, workflow_id: str, workflow_type: str = "sequential"):
        self.workflow_id = workflow_id
        self.workflow_type = workflow_type

        if workflow_type == "sequential":
            self.workflow = SequentialWorkflow(workflow_id)
        elif workflow_type == "decision":
            self.workflow = DecisionWorkflow(workflow_id)
        elif workflow_type == "parallel":
            self.workflow = ParallelWorkflow(workflow_id)
        else:
            self.workflow = SequentialWorkflow(workflow_id)

        self._last_node_id = None
        self._last_decision_node_id = None
        self._pending_end_nodes = []

    def start(self, label: str = "Start") -> "WorkflowBuilder":
        node = WorkflowNode(node_id="start", node_type=NodeType.START, label=label)
        self.workflow.add_node(node)
        self._last_node_id = "start"
        return self

    def action(self, node_id: str, action: Callable, label: str = "") -> "WorkflowBuilder":
        node = WorkflowNode(node_id=node_id, node_type=NodeType.ACTION, label=label, action=action)
        self.workflow.add_node(node)
        if self._last_node_id:
            last_node = self.workflow.get_node(self._last_node_id)
            if last_node:
                last_node.next_nodes.append(node_id)
        self._last_node_id = node_id
        return self

    def decision(self, node_id: str, condition: Callable[[Dict], bool],
                 label: str = "") -> "WorkflowBuilder":
        node = WorkflowNode(
            node_id=node_id, node_type=NodeType.DECISION,
            label=label, condition=condition, next_nodes=[],
        )
        self.workflow.add_node(node)
        if self._last_node_id:
            last_node = self.workflow.get_node(self._last_node_id)
            if last_node:
                last_node.next_nodes.append(node_id)
        self._last_node_id = node_id
        self._last_decision_node_id = node_id
        return self

    def then(self, node_id: str, action: Callable, label: str = "") -> "WorkflowBuilder":
        node = WorkflowNode(node_id=node_id, node_type=NodeType.ACTION, label=label, action=action)
        self.workflow.add_node(node)
        if self._last_node_id:
            last_node = self.workflow.get_node(self._last_node_id)
            if last_node and last_node.node_type == NodeType.DECISION:
                if len(last_node.next_nodes) < 1:
                    last_node.next_nodes.append(node_id)
        self._pending_end_nodes.append(node_id)
        self._last_node_id = node_id
        return self

    def else_(self, node_id: str, action: Callable, label: str = "") -> "WorkflowBuilder":
        node = WorkflowNode(node_id=node_id, node_type=NodeType.ACTION, label=label, action=action)
        self.workflow.add_node(node)
        if self._last_decision_node_id:
            decision_node = self.workflow.get_node(self._last_decision_node_id)
            if decision_node and len(decision_node.next_nodes) < 2:
                decision_node.next_nodes.append(node_id)
        self._pending_end_nodes.append(node_id)
        self._last_node_id = node_id
        return self

    def end(self, label: str = "End") -> "WorkflowBuilder":
        node = WorkflowNode(node_id="end", node_type=NodeType.END, label=label)
        self.workflow.add_node(node)
        if self._pending_end_nodes:
            for pending_id in self._pending_end_nodes:
                pending_node = self.workflow.get_node(pending_id)
                if pending_node:
                    pending_node.next_nodes.append("end")
            self._pending_end_nodes = []
        if self._last_node_id:
            last_node = self.workflow.get_node(self._last_node_id)
            if last_node and last_node.node_id != "end":
                last_node.next_nodes.append("end")
        self._last_node_id = "end"
        return self

    def build(self) -> BaseWorkflow:
        return self.workflow


class WorkflowEngine:
    """Central workflow engine — manages workflow registry and execution."""

    def __init__(self):
        self.workflows: Dict[str, BaseWorkflow] = {}

    def register_workflow(self, workflow: BaseWorkflow):
        self.workflows[workflow.workflow_id] = workflow

    async def execute_workflow(self, workflow_id: str,
                               input_data: Optional[Dict] = None) -> WorkflowResult:
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        return await workflow.execute(input_data)

    def get_workflow_status(self, workflow_id: str) -> Optional[WorkflowStatus]:
        workflow = self.workflows.get(workflow_id)
        if workflow:
            return WorkflowStatus.IDLE
        return None


_workflow_engine = WorkflowEngine()


def register_workflow(workflow: BaseWorkflow):
    _workflow_engine.register_workflow(workflow)


async def execute_workflow(workflow_id: str,
                           input_data: Optional[Dict] = None) -> WorkflowResult:
    return await _workflow_engine.execute_workflow(workflow_id, input_data)


def get_workflow_engine() -> WorkflowEngine:
    return _workflow_engine


__all__ = [
    "WorkflowStatus",
    "NodeType",
    "WorkflowNode",
    "WorkflowContext",
    "WorkflowResult",
    "BaseWorkflow",
    "SequentialWorkflow",
    "DecisionWorkflow",
    "ParallelWorkflow",
    "WorkflowBuilder",
    "WorkflowEngine",
    "register_workflow",
    "execute_workflow",
    "get_workflow_engine",
]
