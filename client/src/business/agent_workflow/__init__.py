"""
AgentWorkflow 框架 (Agent Workflow Framework)

提供统一的工作流编排能力，支持：
1. 顺序工作流
2. 分支工作流
3. 循环工作流
4. 条件工作流
5. 并行工作流

核心设计：声明式工作流定义 + 自动执行
"""

from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import asyncio


class WorkflowStatus(Enum):
    """工作流状态"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeType(Enum):
    """节点类型"""
    START = "start"
    END = "end"
    ACTION = "action"
    DECISION = "decision"
    PARALLEL = "parallel"
    LOOP = "loop"


@dataclass
class WorkflowNode:
    """工作流节点"""
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
    """工作流上下文"""
    workflow_id: str
    variables: Dict[str, Any] = field(default_factory=dict)
    status: WorkflowStatus = WorkflowStatus.IDLE
    current_node: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class WorkflowResult:
    """工作流执行结果"""
    success: bool
    context: WorkflowContext
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BaseWorkflow(ABC):
    """
    工作流基类
    
    所有工作流必须实现此类
    """
    
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.nodes: Dict[str, WorkflowNode] = {}
        self.start_node: Optional[str] = None
        self.end_nodes: List[str] = []
    
    def add_node(self, node: WorkflowNode):
        """添加节点"""
        self.nodes[node.node_id] = node
        
        if node.node_type == NodeType.START:
            self.start_node = node.node_id
        elif node.node_type == NodeType.END:
            self.end_nodes.append(node.node_id)
    
    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        """获取节点"""
        return self.nodes.get(node_id)
    
    @abstractmethod
    async def execute(self, input_data: Optional[Dict] = None) -> WorkflowResult:
        """执行工作流"""
        pass


class SequentialWorkflow(BaseWorkflow):
    """
    顺序工作流
    
    节点按顺序依次执行
    """
    
    async def execute(self, input_data: Optional[Dict] = None) -> WorkflowResult:
        """执行顺序工作流"""
        context = WorkflowContext(workflow_id=self.workflow_id)
        context.status = WorkflowStatus.RUNNING
        
        if input_data:
            context.variables.update(input_data)
        
        current_node_id = self.start_node
        
        while current_node_id:
            node = self.get_node(current_node_id)
            if not node:
                context.status = WorkflowStatus.FAILED
                context.error = f"节点不存在: {current_node_id}"
                return WorkflowResult(success=False, context=context, error=context.error)
            
            context.current_node = current_node_id
            
            try:
                # 执行节点动作
                if node.action:
                    result = node.action(context.variables)
                    if isinstance(result, dict):
                        context.variables.update(result)
                
                # 记录历史
                context.history.append({
                    "node_id": current_node_id,
                    "node_type": node.node_type.value,
                    "variables": dict(context.variables)
                })
                
                # 检查是否到达终点
                if node.node_type == NodeType.END:
                    context.status = WorkflowStatus.COMPLETED
                    break
                
                # 移动到下一个节点
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
            output=context.variables
        )


class DecisionWorkflow(BaseWorkflow):
    """
    决策工作流
    
    根据条件选择不同的执行路径
    """
    
    async def execute(self, input_data: Optional[Dict] = None) -> WorkflowResult:
        """执行决策工作流"""
        context = WorkflowContext(workflow_id=self.workflow_id)
        context.status = WorkflowStatus.RUNNING
        
        if input_data:
            context.variables.update(input_data)
        
        current_node_id = self.start_node
        
        while current_node_id:
            node = self.get_node(current_node_id)
            if not node:
                context.status = WorkflowStatus.FAILED
                context.error = f"节点不存在: {current_node_id}"
                return WorkflowResult(success=False, context=context, error=context.error)
            
            context.current_node = current_node_id
            
            try:
                # 执行节点动作
                if node.action:
                    result = node.action(context.variables)
                    if isinstance(result, dict):
                        context.variables.update(result)
                
                # 记录历史
                context.history.append({
                    "node_id": current_node_id,
                    "node_type": node.node_type.value,
                    "variables": dict(context.variables)
                })
                
                # 检查是否到达终点
                if node.node_type == NodeType.END:
                    context.status = WorkflowStatus.COMPLETED
                    break
                
                # 决策节点：根据条件选择路径
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
            output=context.variables
        )


class ParallelWorkflow(BaseWorkflow):
    """
    并行工作流
    
    多个分支并行执行
    """
    
    async def execute(self, input_data: Optional[Dict] = None) -> WorkflowResult:
        """执行并行工作流"""
        context = WorkflowContext(workflow_id=self.workflow_id)
        context.status = WorkflowStatus.RUNNING
        
        if input_data:
            context.variables.update(input_data)
        
        current_node_id = self.start_node
        
        while current_node_id:
            node = self.get_node(current_node_id)
            if not node:
                context.status = WorkflowStatus.FAILED
                context.error = f"节点不存在: {current_node_id}"
                return WorkflowResult(success=False, context=context, error=context.error)
            
            context.current_node = current_node_id
            
            try:
                # 执行节点动作
                if node.action:
                    result = node.action(context.variables)
                    if isinstance(result, dict):
                        context.variables.update(result)
                
                # 记录历史
                context.history.append({
                    "node_id": current_node_id,
                    "node_type": node.node_type.value,
                    "variables": dict(context.variables)
                })
                
                # 检查是否到达终点
                if node.node_type == NodeType.END:
                    context.status = WorkflowStatus.COMPLETED
                    break
                
                # 并行节点：同时执行多个分支
                if node.node_type == NodeType.PARALLEL and node.next_nodes:
                    # 并行执行所有分支
                    tasks = []
                    for next_node_id in node.next_nodes:
                        sub_workflow = SequentialWorkflow(f"{self.workflow_id}_{next_node_id}")
                        sub_workflow.start_node = next_node_id
                        sub_workflow.nodes = self.nodes
                        tasks.append(sub_workflow.execute(dict(context.variables)))
                    
                    # 等待所有分支完成
                    results = await asyncio.gather(*tasks)
                    
                    # 合并结果
                    for result in results:
                        if result.success and result.output:
                            context.variables.update(result.output)
                    
                    # 找到并行后的下一个节点
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
            output=context.variables
        )
    
    def _find_next_after_parallel(self, parallel_node_id: str) -> Optional[str]:
        """找到并行节点之后的下一个节点"""
        # 简化实现：返回第一个 END 节点
        if self.end_nodes:
            return self.end_nodes[0]
        return None


class WorkflowBuilder:
    """
    工作流构建器
    
    提供流畅的 API 来构建工作流
    """
    
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
    
    def start(self, label: str = "开始") -> "WorkflowBuilder":
        """添加开始节点"""
        node = WorkflowNode(
            node_id="start",
            node_type=NodeType.START,
            label=label
        )
        self.workflow.add_node(node)
        self._last_node_id = "start"
        return self
    
    def action(self, node_id: str, action: Callable, label: str = "") -> "WorkflowBuilder":
        """添加动作节点"""
        node = WorkflowNode(
            node_id=node_id,
            node_type=NodeType.ACTION,
            label=label,
            action=action
        )
        self.workflow.add_node(node)
        
        if self._last_node_id:
            last_node = self.workflow.get_node(self._last_node_id)
            if last_node:
                last_node.next_nodes.append(node_id)
        
        self._last_node_id = node_id
        return self
    
    def decision(self, node_id: str, condition: Callable[[Dict], bool], 
                 label: str = "") -> "WorkflowBuilder":
        """添加决策节点"""
        node = WorkflowNode(
            node_id=node_id,
            node_type=NodeType.DECISION,
            label=label,
            condition=condition,
            next_nodes=[]  # 后续通过 then/else 设置
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
        """设置决策节点的肯定分支"""
        node = WorkflowNode(
            node_id=node_id,
            node_type=NodeType.ACTION,
            label=label,
            action=action
        )
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
        """设置决策节点的否定分支"""
        node = WorkflowNode(
            node_id=node_id,
            node_type=NodeType.ACTION,
            label=label,
            action=action
        )
        self.workflow.add_node(node)
        
        if self._last_decision_node_id:
            decision_node = self.workflow.get_node(self._last_decision_node_id)
            if decision_node and len(decision_node.next_nodes) < 2:
                decision_node.next_nodes.append(node_id)
        
        self._pending_end_nodes.append(node_id)
        self._last_node_id = node_id
        return self
    
    def end(self, label: str = "结束") -> "WorkflowBuilder":
        """添加结束节点"""
        node = WorkflowNode(
            node_id="end",
            node_type=NodeType.END,
            label=label
        )
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
        """构建工作流"""
        return self.workflow


class WorkflowEngine:
    """
    工作流引擎
    
    负责管理和执行工作流
    """
    
    def __init__(self):
        self.workflows: Dict[str, BaseWorkflow] = {}
    
    def register_workflow(self, workflow: BaseWorkflow):
        """注册工作流"""
        self.workflows[workflow.workflow_id] = workflow
        print(f"[WorkflowEngine] 注册工作流: {workflow.workflow_id}")
    
    async def execute_workflow(self, workflow_id: str, input_data: Optional[Dict] = None) -> WorkflowResult:
        """执行工作流"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"工作流不存在: {workflow_id}")
        
        print(f"[WorkflowEngine] 执行工作流: {workflow_id}")
        result = await workflow.execute(input_data)
        print(f"[WorkflowEngine] 工作流完成: {workflow_id} - {'成功' if result.success else '失败'}")
        
        return result
    
    def get_workflow_status(self, workflow_id: str) -> Optional[WorkflowStatus]:
        """获取工作流状态"""
        workflow = self.workflows.get(workflow_id)
        if workflow:
            # 简化实现：返回工作流定义状态
            return WorkflowStatus.IDLE
        return None


# 创建全局工作流引擎实例
_workflow_engine = WorkflowEngine()


def register_workflow(workflow: BaseWorkflow):
    """注册工作流（便捷函数）"""
    _workflow_engine.register_workflow(workflow)


async def execute_workflow(workflow_id: str, input_data: Optional[Dict] = None) -> WorkflowResult:
    """执行工作流（便捷函数）"""
    return await _workflow_engine.execute_workflow(workflow_id, input_data)


def get_workflow_engine() -> WorkflowEngine:
    """获取工作流引擎实例"""
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
    "get_workflow_engine"
]