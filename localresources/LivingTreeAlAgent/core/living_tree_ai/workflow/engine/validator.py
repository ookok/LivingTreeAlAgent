"""工作流验证器"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from ..models.workflow import Workflow
from ..models.node import WorkflowNodeModel
from ..models.types import NodeType


@dataclass
class ValidationError:
    """验证错误"""
    error_type: str
    message: str
    node_id: Optional[str] = None
    connection_id: Optional[str] = None


class WorkflowValidator:
    """工作流验证器"""
    
    def validate(self, workflow: Workflow) -> Tuple[bool, List[ValidationError]]:
        """
        验证工作流
        
        Args:
            workflow: 工作流对象
            
        Returns:
            Tuple[bool, List[ValidationError]]: 验证是否通过，错误列表
        """
        errors = []
        
        # 1. 检查工作流基本结构
        errors.extend(self._validate_structure(workflow))
        
        # 2. 检查节点配置
        errors.extend(self._validate_nodes(workflow))
        
        # 3. 检查连接
        errors.extend(self._validate_connections(workflow))
        
        # 4. 检查控制流
        errors.extend(self._validate_control_flow(workflow))
        
        return len(errors) == 0, errors
    
    def _validate_structure(self, workflow: Workflow) -> List[ValidationError]:
        """验证基本结构"""
        errors = []
        
        # 检查工作流名称
        if not workflow.name or not workflow.name.strip():
            errors.append(ValidationError(
                error_type="structure",
                message="工作流名称不能为空"
            ))
        
        # 检查节点列表
        if not workflow.nodes or len(workflow.nodes) == 0:
            errors.append(ValidationError(
                error_type="structure",
                message="工作流至少需要一个节点"
            ))
        
        return errors
    
    def _validate_nodes(self, workflow: Workflow) -> List[ValidationError]:
        """验证节点"""
        errors = []
        node_ids = set()
        
        for node in workflow.nodes:
            node_id = node.node_id if hasattr(node, 'node_id') else node.get("node_id")
            node_type = node.node_type.value if hasattr(node.node_type, 'value') else node.node_type
            
            # 检查节点 ID 唯一性
            if node_id in node_ids:
                errors.append(ValidationError(
                    error_type="node",
                    message=f"节点 ID 重复: {node_id}",
                    node_id=node_id
                ))
            node_ids.add(node_id)
            
            # 检查开始节点
            if node_type == "start":
                if len(node.inputs if hasattr(node, 'inputs') else node.get("inputs", [])) > 0:
                    errors.append(ValidationError(
                        error_type="node",
                        message=f"开始节点不能有输入端口",
                        node_id=node_id
                    ))
            
            # 检查结束节点
            if node_type == "end":
                if len(node.outputs if hasattr(node, 'outputs') else node.get("outputs", [])) > 0:
                    errors.append(ValidationError(
                        error_type="node",
                        message=f"结束节点不能有输出端口",
                        node_id=node_id
                    ))
            
            # 检查 LLM 节点配置
            if node_type == "llm":
                config = node.config if hasattr(node, 'config') else node.get("config", {})
                if not config.get("model"):
                    errors.append(ValidationError(
                        error_type="node",
                        message=f"LLM 节点缺少模型配置",
                        node_id=node_id
                    ))
            
            # 检查工具节点配置
            if node_type == "tool":
                config = node.config if hasattr(node, 'config') else node.get("config", {})
                if not config.get("tool_name"):
                    errors.append(ValidationError(
                        error_type="node",
                        message=f"工具节点缺少工具名称配置",
                        node_id=node_id
                    ))
        
        return errors
    
    def _validate_connections(self, workflow: Workflow) -> List[ValidationError]:
        """验证连接"""
        errors = []
        node_ids = {n.node_id if hasattr(n, 'node_id') else n.get("node_id") for n in workflow.nodes}
        
        for conn in workflow.connections:
            source_id = conn.source_node_id if hasattr(conn, 'source_node_id') else conn.get("source_node_id")
            target_id = conn.target_node_id if hasattr(conn, 'target_node_id') else conn.get("target_node_id")
            conn_id = conn.connection_id if hasattr(conn, 'connection_id') else conn.get("connection_id")
            
            # 检查源节点存在
            if source_id not in node_ids:
                errors.append(ValidationError(
                    error_type="connection",
                    message=f"连接源节点不存在: {source_id}",
                    connection_id=conn_id
                ))
            
            # 检查目标节点存在
            if target_id not in node_ids:
                errors.append(ValidationError(
                    error_type="connection",
                    message=f"连接目标节点不存在: {target_id}",
                    connection_id=conn_id
                ))
            
            # 检查自连接
            if source_id == target_id:
                errors.append(ValidationError(
                    error_type="connection",
                    message=f"节点不能连接到自己",
                    connection_id=conn_id
                ))
        
        return errors
    
    def _validate_control_flow(self, workflow: Workflow) -> List[ValidationError]:
        """验证控制流"""
        errors = []
        
        # 检查是否有开始节点
        start_nodes = [
            n for n in workflow.nodes
            if (n.node_type.value if hasattr(n.node_type, 'value') else n.node_type) == "start"
        ]
        
        if len(start_nodes) == 0:
            errors.append(ValidationError(
                error_type="control_flow",
                message="工作流缺少开始节点"
            ))
        elif len(start_nodes) > 1:
            errors.append(ValidationError(
                error_type="control_flow",
                message="工作流有多个开始节点"
            ))
        
        # 检查是否有结束节点
        end_nodes = [
            n for n in workflow.nodes
            if (n.node_type.value if hasattr(n.node_type, 'value') else n.node_type) == "end"
        ]
        
        if len(end_nodes) == 0:
            errors.append(ValidationError(
                error_type="control_flow",
                message="工作流缺少结束节点"
            ))
        
        # 检查循环依赖
        if self._has_cycle(workflow):
            errors.append(ValidationError(
                error_type="control_flow",
                message="工作流存在循环依赖"
            ))
        
        return errors
    
    def _has_cycle(self, workflow: Workflow) -> bool:
        """检查是否存在循环依赖"""
        nodes = workflow.nodes
        connections = workflow.connections
        
        adjacency = {n.node_id if hasattr(n, 'node_id') else n.get("node_id"): [] for n in nodes}
        
        for conn in connections:
            source_id = conn.source_node_id if hasattr(conn, 'source_node_id') else conn.get("source_node_id")
            target_id = conn.target_node_id if hasattr(conn, 'target_node_id') else conn.get("target_node_id")
            
            if source_id in adjacency and target_id in adjacency:
                adjacency[source_id].append(target_id)
        
        visited = set()
        rec_stack = set()
        
        def dfs(node_id):
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for neighbor in adjacency.get(node_id, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        for node in nodes:
            node_id = node.node_id if hasattr(node, 'node_id') else node.get("node_id")
            if node_id not in visited:
                if dfs(node_id):
                    return True
        
        return False
