"""
渐进网络模块 - Progressive Neural Networks

功能：
1. 增量添加任务模块
2. 知识迁移
3. 侧向连接
4. 模块化学习
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任务类型"""
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    REASONING = "reasoning"
    GENERATION = "generation"
    OTHER = "other"


@dataclass
class TaskModule:
    """任务模块"""
    module_id: str
    task_id: str
    task_name: str
    task_type: TaskType
    created_at: float = None
    performance: float = 0.0
    connections: List[str] = None  # 连接到其他模块的ID
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.connections is None:
            self.connections = []


class ProgressiveNetwork:
    """
    渐进网络 - Progressive Neural Networks
    
    核心思想：
    1. 每个新任务添加新的网络层
    2. 新层可以访问所有先前层的输出
    3. 侧向连接实现知识迁移
    4. 旧任务的参数保持不变
    """
    
    def __init__(self):
        self._modules: Dict[str, TaskModule] = {}
        self._connections: Dict[str, List[str]] = {}  # 模块ID -> 连接的模块ID列表
        self._module_order: List[str] = []  # 模块添加顺序
    
    def add_task(self, task_id: str, task_name: str, task_type: TaskType = TaskType.OTHER) -> str:
        """
        添加新任务模块
        
        Args:
            task_id: 任务ID
            task_name: 任务名称
            task_type: 任务类型
        
        Returns:
            模块ID
        """
        import uuid
        
        module_id = str(uuid.uuid4())
        
        module = TaskModule(
            module_id=module_id,
            task_id=task_id,
            task_name=task_name,
            task_type=task_type,
            connections=[]
        )
        
        self._modules[module_id] = module
        self._module_order.append(module_id)
        
        # 建立侧向连接（连接到所有先前的模块）
        for prev_module_id in self._module_order[:-1]:
            self._connect_modules(prev_module_id, module_id)
        
        logger.info(f"添加任务模块: {task_name} ({module_id})")
        return module_id
    
    def _connect_modules(self, source_id: str, target_id: str):
        """建立模块间的连接"""
        if source_id not in self._connections:
            self._connections[source_id] = []
        
        if target_id not in self._connections[source_id]:
            self._connections[source_id].append(target_id)
            
            # 更新目标模块的连接列表
            if target_id in self._modules:
                self._modules[target_id].connections.append(source_id)
    
    def get_module(self, module_id: str) -> Optional[TaskModule]:
        """获取模块"""
        return self._modules.get(module_id)
    
    def get_modules_by_task(self, task_id: str) -> List[TaskModule]:
        """按任务ID获取模块"""
        return [m for m in self._modules.values() if m.task_id == task_id]
    
    def get_modules_by_type(self, task_type: TaskType) -> List[TaskModule]:
        """按任务类型获取模块"""
        return [m for m in self._modules.values() if m.task_type == task_type]
    
    def update_performance(self, module_id: str, performance: float):
        """更新模块性能"""
        if module_id in self._modules:
            self._modules[module_id].performance = performance
    
    def get_task_sequence(self) -> List[TaskModule]:
        """获取任务学习顺序"""
        return [self._modules[mid] for mid in self._module_order]
    
    def transfer_knowledge(self, source_task_id: str, target_task_id: str) -> bool:
        """
        在任务间迁移知识
        
        Args:
            source_task_id: 源任务ID
            target_task_id: 目标任务ID
        
        Returns:
            是否成功
        """
        # 找到源任务和目标任务的模块
        source_modules = self.get_modules_by_task(source_task_id)
        target_modules = self.get_modules_by_task(target_task_id)
        
        if not source_modules or not target_modules:
            return False
        
        # 建立连接
        for source_module in source_modules:
            for target_module in target_modules:
                self._connect_modules(source_module.module_id, target_module.module_id)
        
        logger.info(f"知识迁移: {source_task_id} -> {target_task_id}")
        return True
    
    def prune_module(self, module_id: str):
        """移除模块"""
        if module_id in self._modules:
            # 移除连接
            for source_id, targets in list(self._connections.items()):
                if module_id in targets:
                    targets.remove(module_id)
                if source_id == module_id:
                    del self._connections[source_id]
            
            # 从顺序列表中移除
            if module_id in self._module_order:
                self._module_order.remove(module_id)
            
            # 删除模块
            del self._modules[module_id]
            
            logger.info(f"移除模块: {module_id}")
    
    def get_network_summary(self) -> Dict:
        """获取网络摘要"""
        by_type = {}
        total_connections = 0
        
        for module in self._modules.values():
            by_type[module.task_type.value] = by_type.get(module.task_type.value, 0) + 1
            total_connections += len(module.connections)
        
        return {
            'total_modules': len(self._modules),
            'total_connections': total_connections,
            'task_order': [self._modules[mid].task_name for mid in self._module_order],
            'by_type': by_type,
            'avg_connections': total_connections / len(self._modules) if self._modules else 0
        }
    
    def get_path_between_tasks(self, task_id1: str, task_id2: str) -> List[str]:
        """获取任务间的路径"""
        modules1 = self.get_modules_by_task(task_id1)
        modules2 = self.get_modules_by_task(task_id2)
        
        if not modules1 or not modules2:
            return []
        
        # 找到最短路径
        visited = set()
        queue = [(modules1[0].module_id, [modules1[0].module_id])]
        
        while queue:
            current_id, path = queue.pop(0)
            
            if current_id in visited:
                continue
            visited.add(current_id)
            
            # 检查是否到达目标
            for module2 in modules2:
                if current_id == module2.module_id:
                    return [self._modules[mid].task_name for mid in path]
            
            # 继续搜索
            if current_id in self._connections:
                for neighbor_id in self._connections[current_id]:
                    if neighbor_id not in visited:
                        queue.append((neighbor_id, path + [neighbor_id]))
        
        return []