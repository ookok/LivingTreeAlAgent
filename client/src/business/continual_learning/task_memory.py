"""
任务记忆模块 - Task Memory

功能：
1. 存储已学习的任务
2. 任务检索
3. 任务性能跟踪
4. 任务知识管理
"""

import logging
import time
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任务类型"""
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    REASONING = "reasoning"
    GENERATION = "generation"


@dataclass
class LearnedTask:
    """已学习的任务"""
    task_id: str
    task_name: str
    task_type: TaskType
    knowledge_weight: Dict[str, float] = None  # EWC权重
    learned_at: float = None
    performance: float = 0.0
    last_used: float = None
    usage_count: int = 0
    
    def __post_init__(self):
        if self.learned_at is None:
            self.learned_at = time.time()
        if self.last_used is None:
            self.last_used = self.learned_at
        if self.knowledge_weight is None:
            self.knowledge_weight = {}


class TaskMemory:
    """
    任务记忆 - 存储和管理已学习的任务
    
    功能：
    1. 存储任务信息
    2. 检索任务
    3. 跟踪性能
    4. 支持EWC权重存储
    """
    
    def __init__(self, storage_path: str = "data/learning/tasks"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self._tasks: Dict[str, LearnedTask] = {}
        self._load_tasks()
    
    def add_task(self, task_id: str, task_name: str, task_type: TaskType,
                knowledge: Dict[str, Any] = None) -> bool:
        """
        添加任务
        
        Args:
            task_id: 任务ID
            task_name: 任务名称
            task_type: 任务类型
            knowledge: 知识内容
        
        Returns:
            是否成功
        """
        if task_id in self._tasks:
            logger.warning(f"任务已存在: {task_id}")
            return False
        
        # 创建知识权重（简化）
        knowledge_weight = {}
        if knowledge:
            for key, value in knowledge.items():
                if isinstance(value, (int, float)):
                    knowledge_weight[key] = abs(value)
        
        task = LearnedTask(
            task_id=task_id,
            task_name=task_name,
            task_type=task_type,
            knowledge_weight=knowledge_weight,
            performance=0.7  # 初始性能
        )
        
        self._tasks[task_id] = task
        self._save_task(task)
        
        logger.info(f"添加任务: {task_name} ({task_type.value})")
        return True
    
    def get_task(self, task_id: str) -> Optional[LearnedTask]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def update_performance(self, task_id: str, performance: float):
        """更新任务性能"""
        if task_id in self._tasks:
            self._tasks[task_id].performance = min(1.0, max(0.0, performance))
            self._tasks[task_id].last_used = time.time()
            self._tasks[task_id].usage_count += 1
            self._save_task(self._tasks[task_id])
    
    def retrieve_tasks(self, query: str = None, task_type: TaskType = None) -> List[LearnedTask]:
        """
        检索任务
        
        Args:
            query: 查询关键词
            task_type: 任务类型过滤
        
        Returns:
            匹配的任务列表
        """
        tasks = list(self._tasks.values())
        
        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]
        
        if query:
            query_lower = query.lower()
            tasks = [t for t in tasks 
                    if query_lower in t.task_name.lower()]
        
        # 按性能排序
        tasks.sort(key=lambda t: t.performance, reverse=True)
        
        return tasks
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self._tasks:
            del self._tasks[task_id]
            
            # 删除文件
            file_path = self.storage_path / f"{task_id}.json"
            if file_path.exists():
                file_path.unlink()
            
            logger.info(f"删除任务: {task_id}")
            return True
        
        return False
    
    def get_all_tasks(self) -> List[LearnedTask]:
        """获取所有任务"""
        return list(self._tasks.values())
    
    def get_tasks_by_type(self, task_type: TaskType) -> List[LearnedTask]:
        """按类型获取任务"""
        return [t for t in self._tasks.values() if t.task_type == task_type]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        by_type = {}
        total_performance = 0.0
        
        for task in self._tasks.values():
            by_type[task.task_type.value] = by_type.get(task.task_type.value, 0) + 1
            total_performance += task.performance
        
        return {
            'total_tasks': len(self._tasks),
            'by_type': by_type,
            'avg_performance': total_performance / len(self._tasks) if self._tasks else 0,
            'active_tasks': sum(1 for t in self._tasks.values() 
                              if time.time() - t.last_used < 86400)  # 24小时内使用
        }
    
    def _save_task(self, task: LearnedTask):
        """保存任务"""
        data = {
            'task_id': task.task_id,
            'task_name': task.task_name,
            'task_type': task.task_type.value,
            'knowledge_weight': task.knowledge_weight,
            'learned_at': task.learned_at,
            'performance': task.performance,
            'last_used': task.last_used,
            'usage_count': task.usage_count
        }
        
        file_path = self.storage_path / f"{task.task_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    
    def _load_tasks(self):
        """加载任务"""
        if not self.storage_path.exists():
            return
        
        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                data['task_type'] = TaskType(data['task_type'])
                self._tasks[data['task_id']] = LearnedTask(**data)
            
            except Exception as e:
                logger.error(f"加载任务失败: {e}")