"""
持续学习系统 (Continual Learning System)
"""

from .ewc_protection import EWCProtection, EWCWeight
from .progressive_net import ProgressiveNetwork, TaskModule
from .meta_learning import MetaLearner, MAMLConfig
from .curriculum_manager import CurriculumManager, Lesson, CurriculumOrder
from .task_memory import TaskMemory, LearnedTask
from .learning_router import LearningRouter, get_learning_router

__all__ = [
    "EWCProtection",
    "EWCWeight",
    "ProgressiveNetwork",
    "TaskModule",
    "MetaLearner",
    "MAMLConfig",
    "CurriculumManager",
    "Lesson",
    "CurriculumOrder",
    "TaskMemory",
    "LearnedTask",
    "LearningRouter",
    "get_learning_router",
]
