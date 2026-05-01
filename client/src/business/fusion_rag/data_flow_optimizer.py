"""
数据流优化器 (Data Flow Optimizer)
===================================

实现模块间数据流的优化：
1. 模块依赖分析
2. 执行图构建
3. 拓扑排序优化

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class DataNode:
    """数据节点"""
    module_name: str
    input_keys: Set[str] = field(default_factory=set)
    output_keys: Set[str] = field(default_factory=set)
    dependencies: List[str] = field(default_factory=list)
    
    def can_execute(self, available_data: Set[str]) -> bool:
        """检查是否可以执行"""
        return self.input_keys.issubset(available_data)


@dataclass
class ExecutionPlan:
    """执行计划"""
    steps: List[str]
    data_flow: Dict[str, Set[str]]
    estimated_latency: float = 0.0


class DataFlowOptimizer:
    """
    数据流优化器
    
    分析模块间的数据依赖，构建最优执行顺序：
    - 依赖分析
    - 执行图构建
    - 拓扑排序
    """
    
    def __init__(self):
        """初始化优化器"""
        self._nodes: Dict[str, DataNode] = {}
        self._execution_graph: Dict[str, List[str]] = {}
        
    def register_node(self, module_name: str, input_keys: Set[str], output_keys: Set[str], dependencies: Optional[List[str]] = None):
        """
        注册数据节点
        
        Args:
            module_name: 模块名称
            input_keys: 输入数据键
            output_keys: 输出数据键
            dependencies: 依赖模块列表
        """
        node = DataNode(
            module_name=module_name,
            input_keys=input_keys,
            output_keys=output_keys,
            dependencies=dependencies or []
        )
        self._nodes[module_name] = node
        
        # 构建执行图
        self._execution_graph[module_name] = dependencies or []
        
        logger.debug(f"[DataFlowOptimizer] 注册节点: {module_name}")
        
    def analyze_dependencies(self, task_context: Any) -> Dict[str, List[str]]:
        """
        分析模块间依赖关系
        
        Args:
            task_context: 任务上下文
            
        Returns:
            依赖关系字典
        """
        dependencies = {}
        
        for module_name, node in self._nodes.items():
            # 检查模块是否适合当前任务
            if not self._is_module_suitable(module_name, task_context):
                continue
                
            # 获取依赖
            deps = []
            
            # 数据依赖
            for other_name, other_node in self._nodes.items():
                if module_name == other_name:
                    continue
                    
                # 如果当前模块的输入是其他模块的输出，则有依赖
                if node.input_keys.intersection(other_node.output_keys):
                    deps.append(other_name)
            
            # 显式依赖
            if node.dependencies:
                deps.extend(node.dependencies)
                
            # 去重
            dependencies[module_name] = list(set(deps))
            
        return dependencies
        
    def _is_module_suitable(self, module_name: str, task_context: Any) -> bool:
        """
        检查模块是否适合当前任务
        
        Args:
            module_name: 模块名称
            task_context: 任务上下文
            
        Returns:
            是否适合
        """
        # 简化实现：默认所有模块都适合
        return True
        
    def build_execution_graph(self, dependencies: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        构建执行图
        
        Args:
            dependencies: 依赖关系
            
        Returns:
            执行图
        """
        # 反转依赖关系，构建执行顺序图
        execution_graph = {}
        
        for module, deps in dependencies.items():
            for dep in deps:
                if dep not in execution_graph:
                    execution_graph[dep] = []
                if module not in execution_graph[dep]:
                    execution_graph[dep].append(module)
                    
        return execution_graph
        
    def topological_sort(self, graph: Dict[str, List[str]]) -> List[str]:
        """
        拓扑排序
        
        Args:
            graph: 执行图
            
        Returns:
            排序后的模块列表
        """
        # 使用 Kahn 算法进行拓扑排序
        in_degree = {node: 0 for node in graph}
        reverse_graph = {node: [] for node in graph}
        
        # 计算入度和反向图
        for node, neighbors in graph.items():
            for neighbor in neighbors:
                if neighbor not in in_degree:
                    in_degree[neighbor] = 0
                if neighbor not in reverse_graph:
                    reverse_graph[neighbor] = []
                in_degree[neighbor] += 1
                reverse_graph[neighbor].append(node)
                
        # 添加所有节点到反向图
        for node in in_degree:
            if node not in reverse_graph:
                reverse_graph[node] = []
                
        # 初始化队列（入度为0的节点）
        queue = [node for node in in_degree if in_degree[node] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in graph.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    
        # 检查是否有环
        if len(result) != len(in_degree):
            logger.warning("[DataFlowOptimizer] 检测到依赖环")
            
        return result
        
    def optimize(self, task_context: Any, candidates: List[str]) -> ExecutionPlan:
        """
        优化执行顺序
        
        Args:
            task_context: 任务上下文
            candidates: 候选模块列表
            
        Returns:
            执行计划
        """
        logger.info("[DataFlowOptimizer] 开始优化执行顺序")
        
        # 分析依赖
        dependencies = self.analyze_dependencies(task_context)
        
        # 过滤候选模块
        filtered_deps = {k: v for k, v in dependencies.items() if k in candidates}
        
        # 构建执行图
        graph = self.build_execution_graph(filtered_deps)
        
        # 添加所有候选模块到图中
        for candidate in candidates:
            if candidate not in graph:
                graph[candidate] = []
                
        # 拓扑排序
        execution_order = self.topological_sort(graph)
        
        # 确保所有候选模块都在执行顺序中
        for candidate in candidates:
            if candidate not in execution_order:
                execution_order.append(candidate)
                
        # 构建数据流信息
        data_flow = {}
        available_data = set()
        
        for module_name in execution_order:
            node = self._nodes.get(module_name)
            if node:
                data_flow[module_name] = available_data.copy()
                available_data.update(node.output_keys)
        
        plan = ExecutionPlan(
            steps=execution_order,
            data_flow=data_flow,
            estimated_latency=self._estimate_latency(execution_order)
        )
        
        logger.info(f"[DataFlowOptimizer] 优化完成，执行顺序: {execution_order}")
        return plan
        
    def _estimate_latency(self, modules: List[str]) -> float:
        """
        估算执行延迟
        
        Args:
            modules: 模块列表
            
        Returns:
            估算延迟（秒）
        """
        # 简化估算：每个模块平均0.5秒
        return len(modules) * 0.5
        
    def get_data_flow_info(self) -> Dict[str, Dict[str, Any]]:
        """获取数据流信息"""
        result = {}
        for name, node in self._nodes.items():
            result[name] = {
                'input_keys': list(node.input_keys),
                'output_keys': list(node.output_keys),
                'dependencies': node.dependencies
            }
        return result
