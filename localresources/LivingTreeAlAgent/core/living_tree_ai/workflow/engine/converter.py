"""任务链转换器 - 将工作流转换为任务链"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from ..models.workflow import Workflow
from ..models.node import WorkflowNodeModel
from ..models.connection import NodeConnection
from ..models.types import NodeType


@dataclass
class TaskItem:
    """任务项"""
    task_id: str
    node_id: str
    task_type: str
    input_data: Dict[str, Any]
    priority: int = 1


class TaskChainConverter:
    """任务链转换器"""
    
    def __init__(self):
        self.node_registry = None
    
    def convert(self, workflow: Workflow, context: Dict[str, Any] = None) -> List[TaskItem]:
        """将工作流转换为任务链"""
        if context is None:
            context = {}
        
        # 1. 拓扑排序获取执行顺序
        execution_order = self._topological_sort(workflow)
        
        # 2. 按顺序转换每个节点
        task_chain = []
        execution_context = context.copy()
        
        for node in execution_order:
            if isinstance(node, dict):
                node_type = node.get("node_type", "")
            elif hasattr(node, "node_type"):
                node_type = node.node_type.value if hasattr(node.node_type, 'value') else node.node_type
            else:
                continue
            
            # 跳过开始和结束节点
            if node_type == "start":
                execution_context.update(self._get_node_outputs(node, execution_context))
                continue
            elif node_type == "end":
                break
            
            # 转换节点为任务
            task = self._convert_node_to_task(node, execution_context)
            if task:
                task_chain.append(task)
                # 更新上下文
                execution_context[node.node_id if hasattr(node, 'node_id') else node.get("node_id")] = task
        
        return task_chain
    
    def _topological_sort(self, workflow: Workflow) -> List[Any]:
        """拓扑排序获取执行顺序"""
        nodes = workflow.nodes
        connections = workflow.connections
        
        # 构建邻接表
        adjacency = {n.node_id if hasattr(n, 'node_id') else n.get("node_id"): [] for n in nodes}
        in_degree = {n.node_id if hasattr(n, 'node_id') else n.get("node_id"): 0 for n in nodes}
        
        for conn in connections:
            source_id = conn.source_node_id if hasattr(conn, 'source_node_id') else conn.get("source_node_id")
            target_id = conn.target_node_id if hasattr(conn, 'target_node_id') else conn.get("target_node_id")
            
            if source_id in adjacency and target_id in adjacency:
                adjacency[source_id].append(target_id)
                in_degree[target_id] += 1
        
        # Kahn 算法
        queue = [n for n in in_degree if in_degree[n] == 0]
        result = []
        
        while queue:
            node_id = queue.pop(0)
            # 找到对应节点
            for n in nodes:
                if (n.node_id if hasattr(n, 'node_id') else n.get("node_id")) == node_id:
                    result.append(n)
                    break
            
            for neighbor in adjacency[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 检查循环依赖
        if len(result) != len(nodes):
            raise ValueError("工作流存在循环依赖")
        
        return result
    
    def _convert_node_to_task(self, node: Any, context: Dict[str, Any]) -> Optional[TaskItem]:
        """将节点转换为任务"""
        node_id = node.node_id if hasattr(node, 'node_id') else node.get("node_id")
        node_type = node.node_type.value if hasattr(node.node_type, 'value') else node.node_type
        config = node.config if hasattr(node, 'config') else node.get("config", {})
        
        # 确定任务类型
        task_type_map = {
            "llm": "inference",
            "tool": "tool",
            "knowledge": "storage",
            "condition": "coordination",
            "loop": "coordination",
            "template": "inference",
            "transformer": "storage"
        }
        
        task_type = task_type_map.get(node_type, "inference")
        
        # 构建输入数据
        input_data = {
            "node_id": node_id,
            "node_type": node_type,
            "config": config,
            "context": context
        }
        
        return TaskItem(
            task_id=f"task_{node_id}",
            node_id=node_id,
            task_type=task_type,
            input_data=input_data,
            priority=1
        )
    
    def _get_node_outputs(self, node: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """获取节点输出"""
        node_id = node.node_id if hasattr(node, 'node_id') else node.get("node_id")
        return {f"{node_id}_output": context.get(node_id)}
