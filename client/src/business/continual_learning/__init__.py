"""
持续学习系统 (Continual Learning System)

核心能力：
1. EWC保护 - Elastic Weight Consolidation防止灾难性遗忘
2. 渐进网络 - Progressive Neural Networks增量学习
3. 元学习 - MAML风格学习如何学习
4. 课程学习 - Curriculum Learning从简单到复杂

学习策略：
- 任务增量学习
- 知识迁移
- 自适应学习率
"""

from .ewc_protection import EWCProtection, EWCWeight
from .progressive_net import ProgressiveNetwork, TaskModule
from .meta_learning import MetaLearner, MAMLConfig
from .curriculum_manager import CurriculumManager, Lesson, CurriculumOrder
from .task_memory import TaskMemory, LearnedTask
from .learning_router import LearningRouter, get_learning_router

__all__ = [
    # EWC保护
    'EWCProtection',
    'EWCWeight',
    
    # 渐进网络
    'ProgressiveNetwork',
    'TaskModule',
    
    # 元学习
    'MetaLearner',
    'MAMLConfig',
    
    # 课程学习
    'CurriculumManager',
    'Lesson',
    'CurriculumOrder',
    
    # 任务记忆
    'TaskMemory',
    'LearnedTask',
    
    # 学习路由
    'LearningRouter',
    'get_learning_router',
]


def learn_task(task_id: str, task_name: str, knowledge: dict) -> bool:
    """学习新任务"""
    router = get_learning_router()
    return router.learn_task(task_id, task_name, knowledge)


def recall_task(task_id: str) -> dict:
    """回忆任务"""
    router = get_learning_router()
    return router.recall_task(task_id)