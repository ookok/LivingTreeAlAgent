"""
课程学习模块 - Curriculum Learning

功能：
1. 课程编排 - 从简单到复杂
2. 学习路径规划
3. 难度自适应
4. 学习进度跟踪
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CurriculumOrder(Enum):
    """课程顺序类型"""
    LINEAR = "linear"           # 线性顺序
    ADAPTIVE = "adaptive"       # 自适应顺序
    SPIRAL = "spiral"           # 螺旋式学习
    RANDOM = "random"           # 随机顺序


@dataclass
class Lesson:
    """课程"""
    lesson_id: str
    name: str
    difficulty: float  # 0-1
    knowledge: Dict[str, Any]
    prerequisites: List[str] = None
    estimated_time: float = 0.0  # 分钟
    completed: bool = False
    score: float = 0.0
    
    def __post_init__(self):
        if self.prerequisites is None:
            self.prerequisites = []


@dataclass
class LearningPath:
    """学习路径"""
    path_id: str
    name: str
    lessons: List[str]
    order_type: CurriculumOrder = CurriculumOrder.LINEAR
    progress: float = 0.0


class CurriculumManager:
    """
    课程学习管理器 - Curriculum Learning
    
    核心思想：
    1. 从简单任务开始
    2. 逐步增加难度
    3. 自适应调整学习顺序
    4. 确保知识的循序渐进
    """
    
    def __init__(self):
        self._lessons: Dict[str, Lesson] = {}
        self._learning_paths: Dict[str, LearningPath] = {}
        self._current_path = None
    
    def add_lesson(self, name: str, difficulty: float, knowledge: Dict[str, Any],
                  prerequisites: List[str] = None, estimated_time: float = 30.0) -> str:
        """
        添加课程
        
        Args:
            name: 课程名称
            difficulty: 难度 (0-1)
            knowledge: 知识内容
            prerequisites: 前置课程ID列表
            estimated_time: 预计学习时间（分钟）
        
        Returns:
            课程ID
        """
        import uuid
        
        lesson_id = str(uuid.uuid4())
        
        lesson = Lesson(
            lesson_id=lesson_id,
            name=name,
            difficulty=difficulty,
            knowledge=knowledge,
            prerequisites=prerequisites or [],
            estimated_time=estimated_time
        )
        
        self._lessons[lesson_id] = lesson
        logger.info(f"添加课程: {name} (难度: {difficulty})")
        
        return lesson_id
    
    def add_lessons(self, lessons_data: List[Dict]) -> List[str]:
        """批量添加课程"""
        ids = []
        for data in lessons_data:
            lesson_id = self.add_lesson(
                name=data['name'],
                difficulty=data['difficulty'],
                knowledge=data['knowledge'],
                prerequisites=data.get('prerequisites'),
                estimated_time=data.get('estimated_time', 30.0)
            )
            ids.append(lesson_id)
        return ids
    
    def create_learning_path(self, name: str, lesson_ids: List[str],
                           order_type: CurriculumOrder = CurriculumOrder.LINEAR) -> str:
        """
        创建学习路径
        
        Args:
            name: 路径名称
            lesson_ids: 课程ID列表
            order_type: 顺序类型
        
        Returns:
            路径ID
        """
        import uuid
        
        path_id = str(uuid.uuid4())
        
        # 根据顺序类型排序课程
        ordered_lessons = self._order_lessons(lesson_ids, order_type)
        
        path = LearningPath(
            path_id=path_id,
            name=name,
            lessons=ordered_lessons,
            order_type=order_type
        )
        
        self._learning_paths[path_id] = path
        logger.info(f"创建学习路径: {name} (课程数: {len(ordered_lessons)})")
        
        return path_id
    
    def _order_lessons(self, lesson_ids: List[str], order_type: CurriculumOrder) -> List[str]:
        """根据顺序类型排序课程"""
        if order_type == CurriculumOrder.LINEAR:
            # 按难度排序
            return sorted(lesson_ids, key=lambda id: self._lessons[id].difficulty)
        
        elif order_type == CurriculumOrder.ADAPTIVE:
            # 自适应顺序（考虑前置条件）
            return self._adaptive_order(lesson_ids)
        
        elif order_type == CurriculumOrder.SPIRAL:
            # 螺旋式（简单-复杂交替）
            return self._spiral_order(lesson_ids)
        
        else:
            # 随机顺序
            import random
            return random.sample(lesson_ids, len(lesson_ids))
    
    def _adaptive_order(self, lesson_ids: List[str]) -> List[str]:
        """自适应排序（考虑前置条件）"""
        ordered = []
        remaining = set(lesson_ids)
        
        while remaining:
            # 找到所有前置条件已满足的课程
            available = []
            for lesson_id in remaining:
                lesson = self._lessons[lesson_id]
                prereqs_met = all(p in ordered for p in lesson.prerequisites)
                if prereqs_met:
                    available.append(lesson_id)
            
            if not available:
                # 如果没有可用课程，选择难度最低的
                available = [min(remaining, key=lambda id: self._lessons[id].difficulty)]
            
            # 选择难度最低的可用课程
            selected = min(available, key=lambda id: self._lessons[id].difficulty)
            ordered.append(selected)
            remaining.remove(selected)
        
        return ordered
    
    def _spiral_order(self, lesson_ids: List[str]) -> List[str]:
        """螺旋式排序"""
        # 按难度分组
        easy = [id for id in lesson_ids if self._lessons[id].difficulty < 0.4]
        medium = [id for id in lesson_ids if 0.4 <= self._lessons[id].difficulty < 0.7]
        hard = [id for id in lesson_ids if self._lessons[id].difficulty >= 0.7]
        
        # 螺旋式排列
        ordered = []
        max_len = max(len(easy), len(medium), len(hard))
        
        for i in range(max_len):
            if i < len(easy):
                ordered.append(easy[i])
            if i < len(medium):
                ordered.append(medium[i])
            if i < len(hard):
                ordered.append(hard[i])
        
        return ordered
    
    def start_path(self, path_id: str):
        """开始学习路径"""
        if path_id in self._learning_paths:
            self._current_path = path_id
            logger.info(f"开始学习路径: {self._learning_paths[path_id].name}")
    
    def get_next_lesson(self) -> Optional[Lesson]:
        """获取下一个要学习的课程"""
        if not self._current_path or self._current_path not in self._learning_paths:
            return None
        
        path = self._learning_paths[self._current_path]
        
        # 找到第一个未完成的课程
        for lesson_id in path.lessons:
            if not self._lessons[lesson_id].completed:
                return self._lessons[lesson_id]
        
        return None
    
    def complete_lesson(self, lesson_id: str, score: float = 0.0) -> bool:
        """标记课程完成"""
        if lesson_id in self._lessons:
            self._lessons[lesson_id].completed = True
            self._lessons[lesson_id].score = score
            
            # 更新学习路径进度
            if self._current_path in self._learning_paths:
                path = self._learning_paths[self._current_path]
                completed = sum(1 for lid in path.lessons if self._lessons[lid].completed)
                path.progress = completed / len(path.lessons)
            
            logger.info(f"完成课程: {self._lessons[lesson_id].name} (得分: {score})")
            return True
        
        return False
    
    def get_lesson(self, lesson_id: str) -> Optional[Lesson]:
        """获取课程"""
        return self._lessons.get(lesson_id)
    
    def get_path_progress(self, path_id: str) -> Dict:
        """获取学习路径进度"""
        if path_id not in self._learning_paths:
            return {}
        
        path = self._learning_paths[path_id]
        completed = []
        pending = []
        
        for lesson_id in path.lessons:
            lesson = self._lessons[lesson_id]
            if lesson.completed:
                completed.append({'id': lesson_id, 'name': lesson.name, 'score': lesson.score})
            else:
                pending.append({'id': lesson_id, 'name': lesson.name, 'difficulty': lesson.difficulty})
        
        return {
            'path_id': path_id,
            'name': path.name,
            'progress': path.progress,
            'completed': completed,
            'pending': pending,
            'total_lessons': len(path.lessons),
            'completed_count': len(completed)
        }
    
    def get_all_lessons(self) -> List[Dict]:
        """获取所有课程"""
        return [
            {
                'lesson_id': lesson.lesson_id,
                'name': lesson.name,
                'difficulty': lesson.difficulty,
                'completed': lesson.completed,
                'score': lesson.score,
                'prerequisites': lesson.prerequisites,
                'estimated_time': lesson.estimated_time
            }
            for lesson in self._lessons.values()
        ]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self._lessons)
        completed = sum(1 for l in self._lessons.values() if l.completed)
        avg_difficulty = sum(l.difficulty for l in self._lessons.values()) / total if total > 0 else 0
        avg_score = sum(l.score for l in self._lessons.values() if l.completed) / completed if completed > 0 else 0
        
        return {
            'total_lessons': total,
            'completed_lessons': completed,
            'completion_rate': completed / total if total > 0 else 0,
            'avg_difficulty': avg_difficulty,
            'avg_score': avg_score,
            'learning_paths': len(self._learning_paths),
            'current_path': self._current_path
        }