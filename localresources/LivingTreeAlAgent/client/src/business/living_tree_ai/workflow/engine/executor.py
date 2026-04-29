"""工作流执行器"""

import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass

from ..models.workflow import Workflow, WorkflowExecution
from ..models.node import WorkflowNodeModel
from ..models.types import WorkflowStatus, NodeStatus
from .converter import TaskChainConverter, TaskItem


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    workflow_id: str
    execution_id: str
    node_results: Dict[str, Any]
    error: str = ""


class WorkflowExecutor:
    """工作流执行器"""
    
    def __init__(self, node=None):
        """
        初始化执行器
        
        Args:
            node: LivingTreeNode 实例，用于执行任务
        """
        self.node = node
        self.converter = TaskChainConverter()
        self.current_execution: Optional[WorkflowExecution] = None
        self.execution_callback: Optional[Callable] = None
    
    async def execute(
        self,
        workflow: Workflow,
        context: Dict[str, Any] = None,
        callback: Optional[Callable] = None
    ) -> ExecutionResult:
        """
        执行工作流
        
        Args:
            workflow: 工作流对象
            context: 执行上下文
            callback: 执行状态回调函数，格式: callback(node_id, status, result)
            
        Returns:
            ExecutionResult: 执行结果
        """
        if context is None:
            context = {}
        
        self.execution_callback = callback
        execution_id = f"exec_{workflow.workflow_id}"
        
        # 创建执行记录
        self.current_execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow.workflow_id,
            status=WorkflowStatus.RUNNING,
            start_time=asyncio.get_event_loop().time()
        )
        
        try:
            # 转换为任务链
            task_chain = self.converter.convert(workflow, context)
            
            # 执行任务链
            node_results = {}
            
            for task in task_chain:
                # 更新节点状态
                self._update_node_status(workflow, task.node_id, NodeStatus.RUNNING)
                
                # 调用回调
                if callback:
                    callback(task.node_id, "running", {"task_id": task.task_id})
                
                # 执行任务
                try:
                    if self.node:
                        # 通过节点执行
                        result = await self._execute_task_via_node(task)
                    else:
                        # 直接执行（模拟）
                        result = await self._execute_task_direct(task)
                    
                    node_results[task.node_id] = result
                    self._update_node_status(workflow, task.node_id, NodeStatus.COMPLETED)
                    
                    # 调用回调
                    if callback:
                        callback(task.node_id, "completed", result)
                        
                except Exception as e:
                    error_msg = str(e)
                    node_results[task.node_id] = {"error": error_msg}
                    self._update_node_status(workflow, task.node_id, NodeStatus.FAILED)
                    
                    if callback:
                        callback(task.node_id, "failed", error_msg)
            
            # 执行完成
            self.current_execution.status = WorkflowStatus.COMPLETED
            self.current_execution.node_results = node_results
            self.current_execution.end_time = asyncio.get_event_loop().time()
            
            # 调用完成回调
            if callback:
                callback("workflow", "completed", node_results)
            
            return ExecutionResult(
                success=True,
                workflow_id=workflow.workflow_id,
                execution_id=execution_id,
                node_results=node_results
            )
            
        except Exception as e:
            error_msg = str(e)
            self.current_execution.status = WorkflowStatus.FAILED
            self.current_execution.error = error_msg
            self.current_execution.end_time = asyncio.get_event_loop().time()
            
            # 调用失败回调
            if callback:
                callback("workflow", "failed", error_msg)
            
            return ExecutionResult(
                success=False,
                workflow_id=workflow.workflow_id,
                execution_id=execution_id,
                node_results={},
                error=error_msg
            )
    
    async def _execute_task_via_node(self, task: TaskItem) -> Any:
        """通过节点执行任务"""
        if task.task_type == "inference":
            # 推理任务
            result = await self.node._do_inference({
                "task_id": task.task_id,
                "input_data": task.input_data
            })
            return result
        elif task.task_type == "tool":
            # 工具任务
            config = task.input_data.get("config", {})
            tool_name = config.get("tool_name", "")
            result = await self.node.execute_tool(tool_name, **task.input_data.get("context", {}))
            return result
        elif task.task_type == "coordination":
            # 协调任务
            result = await self.node._do_coordination({
                "task_id": task.task_id,
                "input_data": task.input_data
            })
            return result
        else:
            return {"result": "unknown task type"}
    
    async def _execute_task_direct(self, task: TaskItem) -> Any:
        """直接执行任务（模拟）"""
        # 模拟执行时间
        await asyncio.sleep(0.5)
        
        # 模拟不同类型任务的执行结果
        if task.task_type == "inference":
            return {
                "task_id": task.task_id,
                "node_id": task.node_id,
                "task_type": task.task_type,
                "result": "模拟推理结果",
                "model": "gpt-4",
                "response": "这是一个模拟的 LLM 响应"
            }
        elif task.task_type == "tool":
            return {
                "task_id": task.task_id,
                "node_id": task.node_id,
                "task_type": task.task_type,
                "result": "模拟工具执行结果",
                "tool_name": task.input_data.get("config", {}).get("tool_name", "unknown")
            }
        elif task.task_type == "coordination":
            return {
                "task_id": task.task_id,
                "node_id": task.node_id,
                "task_type": task.task_type,
                "result": "模拟协调结果"
            }
        else:
            return {
                "task_id": task.task_id,
                "node_id": task.node_id,
                "task_type": task.task_type,
                "result": "模拟执行结果"
            }
    
    def _update_node_status(self, workflow: Workflow, node_id: str, status: NodeStatus):
        """更新节点状态"""
        for node in workflow.nodes:
            if (node.node_id if hasattr(node, 'node_id') else node.get("node_id")) == node_id:
                if hasattr(node, 'set_status'):
                    node.set_status(status)
                elif isinstance(node, dict):
                    node["status"] = status.value if isinstance(status, NodeStatus) else status
                break
    
    def get_execution_status(self) -> Optional[WorkflowExecution]:
        """获取当前执行状态"""
        return self.current_execution
