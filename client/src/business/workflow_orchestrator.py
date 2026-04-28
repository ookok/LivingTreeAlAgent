"""
WorkflowOrchestrator - 工作流编排器

参考 Archon 的工作流设计，支持 YAML 格式定义工作流。

核心功能：
1. 支持 YAML 格式定义工作流
2. 工作流可复用、可共享、可版本管理
3. 支持条件分支、循环、并行执行
4. 工作流状态管理和追踪
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum
import yaml
import json
import os
import asyncio


class NodeType(Enum):
    """节点类型"""
    START = "start"
    END = "end"
    ACTION = "action"
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"
    SUBWORKFLOW = "subworkflow"


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowNode:
    """工作流节点"""
    id: str
    type: NodeType
    name: str
    tool_name: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    next_node: Optional[str] = None
    condition: Optional[str] = None
    loop_condition: Optional[str] = None
    loop_max_iterations: int = 1
    parallel_nodes: List[str] = field(default_factory=list)
    subworkflow: Optional[str] = None


@dataclass
class Workflow:
    """工作流定义"""
    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    nodes: Dict[str, WorkflowNode] = field(default_factory=dict)
    start_node: str = "start"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


@dataclass
class WorkflowInstance:
    """工作流实例"""
    instance_id: str
    workflow_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    current_node: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class WorkflowOrchestrator:
    """
    工作流编排器
    
    核心功能：
    1. 加载和解析 YAML 工作流定义
    2. 创建和管理工作流实例
    3. 执行工作流节点
    4. 处理条件分支、循环、并行执行
    5. 工作流状态追踪和管理
    """
    
    def __init__(self, workflows_dir: str = None):
        self._logger = logger.bind(component="WorkflowOrchestrator")
        self._workflows: Dict[str, Workflow] = {}
        self._instances: Dict[str, WorkflowInstance] = {}
        self._workflows_dir = workflows_dir or self._get_default_workflows_dir()
        self._tool_registry = None
        
        os.makedirs(self._workflows_dir, exist_ok=True)
        self._load_workflows()
    
    def _get_default_workflows_dir(self) -> str:
        """获取默认工作流目录"""
        return os.path.join(os.path.expanduser("~"), ".livingtree", "workflows")
    
    def _load_workflows(self):
        """加载工作流定义"""
        try:
            for filename in os.listdir(self._workflows_dir):
                if filename.endswith(".yaml") or filename.endswith(".yml"):
                    filepath = os.path.join(self._workflows_dir, filename)
                    self.load_workflow_from_file(filepath)
        except Exception as e:
            self._logger.error(f"加载工作流失败: {e}")
    
    def set_tool_registry(self, tool_registry):
        """设置工具注册中心"""
        self._tool_registry = tool_registry
    
    def load_workflow_from_file(self, filepath: str) -> Optional[Workflow]:
        """
        从文件加载工作流
        
        Args:
            filepath: YAML 文件路径
            
        Returns:
            工作流对象
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            workflow = self._parse_workflow(data)
            self._workflows[workflow.id] = workflow
            self._logger.info(f"加载工作流: {workflow.name} ({workflow.id})")
            
            return workflow
        except Exception as e:
            self._logger.error(f"加载工作流文件失败 {filepath}: {e}")
            return None
    
    def _parse_workflow(self, data: Dict[str, Any]) -> Workflow:
        """解析工作流数据"""
        workflow = Workflow(
            id=data.get("id", data.get("name", "unnamed").lower().replace(" ", "_")),
            name=data.get("name", "Unnamed Workflow"),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0")
        )
        
        # 解析节点
        nodes_data = data.get("nodes", {})
        for node_id, node_data in nodes_data.items():
            workflow.nodes[node_id] = self._parse_node(node_id, node_data)
        
        # 设置开始节点
        workflow.start_node = data.get("start", "start")
        
        return workflow
    
    def _parse_node(self, node_id: str, data: Dict[str, Any]) -> WorkflowNode:
        """解析节点数据"""
        node_type = NodeType(data.get("type", "action"))
        
        return WorkflowNode(
            id=node_id,
            type=node_type,
            name=data.get("name", node_id),
            tool_name=data.get("tool"),
            parameters=data.get("parameters", {}),
            next_node=data.get("next"),
            condition=data.get("condition"),
            loop_condition=data.get("loop_condition"),
            loop_max_iterations=data.get("loop_max_iterations", 1),
            parallel_nodes=data.get("parallel", []),
            subworkflow=data.get("subworkflow")
        )
    
    def save_workflow_to_file(self, workflow: Workflow):
        """保存工作流到文件"""
        filename = f"{workflow.id}.yaml"
        filepath = os.path.join(self._workflows_dir, filename)
        
        data = {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "version": workflow.version,
            "start": workflow.start_node,
            "nodes": {}
        }
        
        for node_id, node in workflow.nodes.items():
            data["nodes"][node_id] = {
                "type": node.type.value,
                "name": node.name,
                "tool": node.tool_name,
                "parameters": node.parameters,
                "next": node.next_node,
                "condition": node.condition,
                "loop_condition": node.loop_condition,
                "loop_max_iterations": node.loop_max_iterations,
                "parallel": node.parallel_nodes,
                "subworkflow": node.subworkflow
            }
        
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        
        self._logger.info(f"保存工作流: {filepath}")
    
    def create_workflow(self, name: str, description: str = "", version: str = "1.0.0") -> Workflow:
        """
        创建新工作流
        
        Args:
            name: 工作流名称
            description: 描述
            version: 版本号
            
        Returns:
            工作流对象
        """
        workflow_id = name.lower().replace(" ", "_")
        
        workflow = Workflow(
            id=workflow_id,
            name=name,
            description=description,
            version=version
        )
        
        # 添加默认的开始和结束节点
        workflow.nodes["start"] = WorkflowNode(
            id="start",
            type=NodeType.START,
            name="开始"
        )
        
        workflow.nodes["end"] = WorkflowNode(
            id="end",
            type=NodeType.END,
            name="结束"
        )
        
        self._workflows[workflow_id] = workflow
        self._logger.info(f"创建工作流: {name}")
        
        return workflow
    
    def add_node(self, workflow_id: str, node: WorkflowNode):
        """添加节点到工作流"""
        if workflow_id in self._workflows:
            self._workflows[workflow_id].nodes[node.id] = node
            self._workflows[workflow_id].updated_at = datetime.now()
    
    def create_instance(self, workflow_id: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        创建工作流实例
        
        Args:
            workflow_id: 工作流 ID
            context: 初始上下文
            
        Returns:
            实例 ID
        """
        if workflow_id not in self._workflows:
            raise ValueError(f"工作流不存在: {workflow_id}")
        
        instance_id = f"instance_{workflow_id}_{int(datetime.now().timestamp())}"
        workflow = self._workflows[workflow_id]
        
        instance = WorkflowInstance(
            instance_id=instance_id,
            workflow_id=workflow_id,
            current_node=workflow.start_node,
            context=context or {}
        )
        
        self._instances[instance_id] = instance
        self._logger.info(f"创建工作流实例: {instance_id}")
        
        return instance_id
    
    async def execute_instance(self, instance_id: str) -> Dict[str, Any]:
        """
        执行工作流实例
        
        Args:
            instance_id: 实例 ID
            
        Returns:
            执行结果
        """
        if instance_id not in self._instances:
            return {"error": f"实例不存在: {instance_id}"}
        
        instance = self._instances[instance_id]
        workflow = self._workflows[instance.workflow_id]
        
        instance.status = ExecutionStatus.RUNNING
        instance.started_at = datetime.now()
        
        try:
            await self._execute_node(instance, workflow, instance.current_node)
            
            instance.status = ExecutionStatus.COMPLETED
            instance.completed_at = datetime.now()
            
            self._logger.info(f"工作流执行完成: {instance_id}")
            
            return {
                "success": True,
                "instance_id": instance_id,
                "context": instance.context,
                "history": instance.execution_history
            }
        except Exception as e:
            instance.status = ExecutionStatus.FAILED
            self._logger.error(f"工作流执行失败 {instance_id}: {e}")
            
            return {
                "success": False,
                "instance_id": instance_id,
                "error": str(e),
                "history": instance.execution_history
            }
    
    async def _execute_node(self, instance: WorkflowInstance, workflow: Workflow, node_id: str):
        """执行单个节点"""
        if node_id not in workflow.nodes:
            return
        
        node = workflow.nodes[node_id]
        instance.current_node = node_id
        
        # 记录执行历史
        instance.execution_history.append({
            "node_id": node_id,
            "node_name": node.name,
            "timestamp": datetime.now().isoformat(),
            "context_before": dict(instance.context)
        })
        
        self._logger.debug(f"执行节点: {node.name} ({node_id})")
        
        if node.type == NodeType.START:
            # 开始节点，直接跳转到下一个节点
            if node.next_node:
                await self._execute_node(instance, workflow, node.next_node)
        
        elif node.type == NodeType.END:
            # 结束节点，退出执行
            return
        
        elif node.type == NodeType.ACTION:
            # 动作节点，执行工具
            await self._execute_action(node, instance)
            
            # 执行完成后跳转到下一个节点
            if node.next_node:
                await self._execute_node(instance, workflow, node.next_node)
        
        elif node.type == NodeType.CONDITION:
            # 条件节点
            result = self._evaluate_condition(node.condition, instance.context)
            
            if result:
                # 条件为真，执行 next_node
                if node.next_node:
                    await self._execute_node(instance, workflow, node.next_node)
            else:
                # 条件为假，检查是否有 else 分支
                else_node = node.parameters.get("else")
                if else_node:
                    await self._execute_node(instance, workflow, else_node)
        
        elif node.type == NodeType.LOOP:
            # 循环节点
            for _ in range(node.loop_max_iterations):
                if node.next_node:
                    await self._execute_node(instance, workflow, node.next_node)
                
                # 检查循环条件
                if node.loop_condition:
                    if not self._evaluate_condition(node.loop_condition, instance.context):
                        break
        
        elif node.type == NodeType.PARALLEL:
            # 并行节点
            tasks = []
            for parallel_node_id in node.parallel_nodes:
                tasks.append(self._execute_node(instance, workflow, parallel_node_id))
            
            await asyncio.gather(*tasks)
            
            if node.next_node:
                await self._execute_node(instance, workflow, node.next_node)
        
        elif node.type == NodeType.SUBWORKFLOW:
            # 子工作流节点
            if node.subworkflow:
                sub_instance_id = self.create_instance(node.subworkflow, instance.context)
                result = await self.execute_instance(sub_instance_id)
                
                if result.get("success"):
                    instance.context.update(result.get("context", {}))
                
                if node.next_node:
                    await self._execute_node(instance, workflow, node.next_node)
    
    async def _execute_action(self, node: WorkflowNode, instance: WorkflowInstance):
        """执行动作节点"""
        if not node.tool_name or not self._tool_registry:
            return
        
        # 获取工具参数，支持上下文变量引用
        params = {}
        for key, value in node.parameters.items():
            params[key] = self._resolve_value(value, instance.context)
        
        # 执行工具
        result = await self._tool_registry.execute(node.tool_name, **params)
        
        # 将结果存入上下文
        if result.success and result.data:
            instance.context[f"tool_result_{node.id}"] = result.data
    
    def _resolve_value(self, value: Any, context: Dict[str, Any]) -> Any:
        """解析值，支持上下文变量引用"""
        if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            var_name = value[2:-2].strip()
            return context.get(var_name, value)
        return value
    
    def _evaluate_condition(self, condition: Optional[str], context: Dict[str, Any]) -> bool:
        """评估条件表达式"""
        if not condition:
            return True
        
        try:
            # 简单的条件评估，支持上下文变量
            for key, value in context.items():
                condition = condition.replace(f"{{{{{key}}}}}", str(value))
            
            return eval(condition)
        except Exception as e:
            self._logger.error(f"条件评估失败 {condition}: {e}")
            return False
    
    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """获取工作流"""
        return self._workflows.get(workflow_id)
    
    def get_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        """获取工作流实例"""
        return self._instances.get(instance_id)
    
    def list_workflows(self) -> List[Dict[str, Any]]:
        """列出所有工作流"""
        result = []
        for workflow in self._workflows.values():
            result.append({
                "id": workflow.id,
                "name": workflow.name,
                "description": workflow.description,
                "version": workflow.version,
                "node_count": len(workflow.nodes),
                "created_at": workflow.created_at.isoformat()
            })
        return result
    
    def get_instance_status(self, instance_id: str) -> Dict[str, Any]:
        """获取实例状态"""
        instance = self._instances.get(instance_id)
        if not instance:
            return {"error": "实例不存在"}
        
        return {
            "instance_id": instance.instance_id,
            "workflow_id": instance.workflow_id,
            "status": instance.status.value,
            "current_node": instance.current_node,
            "context": instance.context,
            "execution_history": instance.execution_history,
            "started_at": instance.started_at.isoformat() if instance.started_at else None,
            "completed_at": instance.completed_at.isoformat() if instance.completed_at else None
        }