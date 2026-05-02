"""
渐进网络模块 - Progressive Neural Networks
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(Enum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    REASONING = "reasoning"
    GENERATION = "generation"
    OTHER = "other"


@dataclass
class TaskModule:
    module_id: str
    task_id: str
    task_name: str
    task_type: TaskType
    created_at: float = None
    performance: float = 0.0
    connections: List[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.connections is None:
            self.connections = []


class ProgressiveNetwork:

    def __init__(self):
        self._modules: Dict[str, TaskModule] = {}
        self._connections: Dict[str, List[str]] = {}
        self._module_order: List[str] = []

    def add_task(self, task_id: str, task_name: str, task_type: TaskType = TaskType.OTHER) -> str:
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
        for prev_module_id in self._module_order[:-1]:
            self._connect_modules(prev_module_id, module_id)
        logger.info(f"添加任务模块: {task_name} ({module_id})")
        return module_id

    def _connect_modules(self, source_id: str, target_id: str):
        if source_id not in self._connections:
            self._connections[source_id] = []
        if target_id not in self._connections[source_id]:
            self._connections[source_id].append(target_id)
            if target_id in self._modules:
                self._modules[target_id].connections.append(source_id)

    def get_module(self, module_id: str) -> Optional[TaskModule]:
        return self._modules.get(module_id)

    def get_modules_by_task(self, task_id: str) -> List[TaskModule]:
        return [m for m in self._modules.values() if m.task_id == task_id]

    def get_modules_by_type(self, task_type: TaskType) -> List[TaskModule]:
        return [m for m in self._modules.values() if m.task_type == task_type]

    def update_performance(self, module_id: str, performance: float):
        if module_id in self._modules:
            self._modules[module_id].performance = performance

    def get_task_sequence(self) -> List[TaskModule]:
        return [self._modules[mid] for mid in self._module_order]

    def transfer_knowledge(self, source_task_id: str, target_task_id: str) -> bool:
        source_modules = self.get_modules_by_task(source_task_id)
        target_modules = self.get_modules_by_task(target_task_id)
        if not source_modules or not target_modules:
            return False
        for source_module in source_modules:
            for target_module in target_modules:
                self._connect_modules(source_module.module_id, target_module.module_id)
        logger.info(f"知识迁移: {source_task_id} -> {target_task_id}")
        return True

    def prune_module(self, module_id: str):
        if module_id in self._modules:
            for source_id, targets in list(self._connections.items()):
                if module_id in targets:
                    targets.remove(module_id)
                if source_id == module_id:
                    del self._connections[source_id]
            if module_id in self._module_order:
                self._module_order.remove(module_id)
            del self._modules[module_id]
            logger.info(f"移除模块: {module_id}")

    def get_network_summary(self) -> Dict:
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
        modules1 = self.get_modules_by_task(task_id1)
        modules2 = self.get_modules_by_task(task_id2)
        if not modules1 or not modules2:
            return []
        visited = set()
        queue = [(modules1[0].module_id, [modules1[0].module_id])]
        while queue:
            current_id, path = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)
            for module2 in modules2:
                if current_id == module2.module_id:
                    return [self._modules[mid].task_name for mid in path]
            if current_id in self._connections:
                for neighbor_id in self._connections[current_id]:
                    if neighbor_id not in visited:
                        queue.append((neighbor_id, path + [neighbor_id]))
        return []
