"""
持续学习管理器 - 防止灾难性遗忘
"""

import logging
import time
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
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
    knowledge_weight: Dict[str, float] = field(default_factory=dict)  # EWC权重
    learned_at: float = None
    performance: float = 0.0
    
    def __post_init__(self):
        if self.learned_at is None:
            self.learned_at = time.time()


class ContinualLearningManager:
    """
    持续学习管理器 - 使用EWC和渐进网络
    """
    
    def __init__(self, storage_path: str = "data/learning"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self._tasks: Dict[str, LearnedTask] = {}
        self._load_tasks()
        
        # 重要权重（模拟EWC）
        self._important_weights: Dict[str, float] = {}
        
    def learn_new_task(
        self,
        task_id: str,
        task_name: str,
        task_type: TaskType,
        knowledge: Dict[str, Any]
    ) -> bool:
        """学习新任务"""
        logger.info(f"Learning new task: {task_name}")
        
        # 保存当前重要权重（保护旧知识）
        self._save_important_weights(task_id)
        
        # 创建任务记录
        task = LearnedTask(
            task_id=task_id,
            task_name=task_name,
            task_type=task_type,
            performance=0.8  # 模拟初始性能
        )
        
        # 学习新知识（简化）
        for key, value in knowledge.items():
            if isinstance(value, (int, float)):
                # 模拟学习过程
                if key in self._important_weights:
                    # 旧知识 - 受保护，变化小
                    self._important_weights[key] = (
                        self._important_weights[key] * 0.9 + value * 0.1
                    )
                else:
                    # 新知识 - 可以快速学习
                    self._important_weights[key] = value
        
        self._tasks[task_id] = task
        self._save_tasks()
        
        logger.info(f"Task learned: {task_id}")
        return True
    
    def _save_important_weights(self, task_id: str):
        """保存重要权重（EWC）"""
        # 这里简单模拟，实际会计算Fisher信息矩阵
        for key, value in self._important_weights.items():
            if f"{task_id}_protection" not in self._important_weights:
                # 为当前任务创建保护权重
                self._important_weights[f"{task_id}_protection_{key}"] = value
    
    def recall_task(self, task_id: str) -> Optional[LearnedTask]:
        """回忆任务"""
        if task_id in self._tasks:
            logger.debug(f"Recalled task: {task_id}")
            return self._tasks[task_id]
        return None
    
    def get_all_tasks(self) -> List[LearnedTask]:
        """获取所有任务"""
        return list(self._tasks.values())
    
    def meta_learn(self, training_tasks: List[str]) -> Dict:
        """
        元学习 - 学习如何学习
        使用MAML风格的元学习
        """
        logger.info(f"Meta-learning from {len(training_tasks)} tasks")
        
        # 简单模拟元学习过程
        learnings = {
            'strategy_improvement': 0.15,
            'faster_adaptation': True,
            'better_generalization': True,
            'meta_knowledge': {
                'learning_rate': 0.01,
                'regularization': 0.001
            }
        }
        
        return learnings
    
    def curriculum_learn(
        self,
        lessons: List[Dict],
        difficulty_order: Optional[List[int]] = None
    ) -> Dict:
        """
        课程学习 - 从简单到复杂
        """
        if difficulty_order is None:
            difficulty_order = list(range(len(lessons)))
        
        results = []
        for lesson_idx in difficulty_order:
            lesson = lessons[lesson_idx]
            logger.debug(f"Learning lesson: {lesson.get('name', 'unnamed')}")
            
            # 模拟课程学习
            self.learn_new_task(
                task_id=lesson.get('task_id', f"lesson_{lesson_idx}"),
                task_name=lesson.get('name', 'lesson'),
                task_type=TaskType.CLASSIFICATION,
                knowledge=lesson.get('knowledge', {})
            )
            
            results.append({
                'lesson': lesson.get('name'),
                'status': 'completed',
                'score': 0.85
            })
        
        return {
            'completed': len(results),
            'lessons': results,
            'final_performance': 0.9
        }
    
    def _save_tasks(self):
        """保存任务"""
        data = {
            task_id: {
                'task_id': task.task_id,
                'task_name': task.task_name,
                'task_type': task.task_type.value,
                'learned_at': task.learned_at,
                'performance': task.performance
            }
            for task_id, task in self._tasks.items()
        }
        
        with open(self.storage_path / "tasks.json", 'w', encoding='utf-8') as f:
            json.dump(data, f)
    
    def _load_tasks(self):
        """加载任务"""
        file_path = self.storage_path / "tasks.json"
        if not file_path.exists():
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for task_id, task_data in data.items():
                task_data['task_type'] = TaskType(task_data['task_type'])
                self._tasks[task_id] = LearnedTask(**task_data)
        except Exception as e:
            logger.error(f"Load tasks error: {e}")
    
    def get_statistics(self) -> Dict:
        """获取学习统计"""
        return {
            'total_tasks': len(self._tasks),
            'tasks': [
                {'id': t.task_id, 'name': t.task_name, 'performance': t.performance}
                for t in self._tasks.values()
            ],
            'avg_performance': sum(t.performance for t in self._tasks.values()) / len(self._tasks) if self._tasks else 0
        }
