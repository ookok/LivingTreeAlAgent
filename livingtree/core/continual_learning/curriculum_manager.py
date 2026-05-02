"""
课程学习模块 - Curriculum Learning
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CurriculumOrder(Enum):
    LINEAR = "linear"
    ADAPTIVE = "adaptive"
    SPIRAL = "spiral"
    RANDOM = "random"


@dataclass
class Lesson:
    lesson_id: str
    name: str
    difficulty: float
    knowledge: Dict[str, Any]
    prerequisites: List[str] = None
    estimated_time: float = 0.0
    completed: bool = False
    score: float = 0.0

    def __post_init__(self):
        if self.prerequisites is None:
            self.prerequisites = []


@dataclass
class LearningPath:
    path_id: str
    name: str
    lessons: List[str]
    order_type: CurriculumOrder = CurriculumOrder.LINEAR
    progress: float = 0.0


class CurriculumManager:

    def __init__(self):
        self._lessons: Dict[str, Lesson] = {}
        self._learning_paths: Dict[str, LearningPath] = {}
        self._current_path = None

    def add_lesson(self, name: str, difficulty: float, knowledge: Dict[str, Any],
                  prerequisites: List[str] = None, estimated_time: float = 30.0) -> str:
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
        import uuid
        path_id = str(uuid.uuid4())
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
        if order_type == CurriculumOrder.LINEAR:
            return sorted(lesson_ids, key=lambda id: self._lessons[id].difficulty)
        elif order_type == CurriculumOrder.ADAPTIVE:
            return self._adaptive_order(lesson_ids)
        elif order_type == CurriculumOrder.SPIRAL:
            return self._spiral_order(lesson_ids)
        else:
            import random
            return random.sample(lesson_ids, len(lesson_ids))

    def _adaptive_order(self, lesson_ids: List[str]) -> List[str]:
        ordered = []
        remaining = set(lesson_ids)
        while remaining:
            available = []
            for lesson_id in remaining:
                lesson = self._lessons[lesson_id]
                prereqs_met = all(p in ordered for p in lesson.prerequisites)
                if prereqs_met:
                    available.append(lesson_id)
            if not available:
                available = [min(remaining, key=lambda id: self._lessons[id].difficulty)]
            selected = min(available, key=lambda id: self._lessons[id].difficulty)
            ordered.append(selected)
            remaining.remove(selected)
        return ordered

    def _spiral_order(self, lesson_ids: List[str]) -> List[str]:
        easy = [id for id in lesson_ids if self._lessons[id].difficulty < 0.4]
        medium = [id for id in lesson_ids if 0.4 <= self._lessons[id].difficulty < 0.7]
        hard = [id for id in lesson_ids if self._lessons[id].difficulty >= 0.7]
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
        if path_id in self._learning_paths:
            self._current_path = path_id
            logger.info(f"开始学习路径: {self._learning_paths[path_id].name}")

    def get_next_lesson(self) -> Optional[Lesson]:
        if not self._current_path or self._current_path not in self._learning_paths:
            return None
        path = self._learning_paths[self._current_path]
        for lesson_id in path.lessons:
            if not self._lessons[lesson_id].completed:
                return self._lessons[lesson_id]
        return None

    def complete_lesson(self, lesson_id: str, score: float = 0.0) -> bool:
        if lesson_id in self._lessons:
            self._lessons[lesson_id].completed = True
            self._lessons[lesson_id].score = score
            if self._current_path in self._learning_paths:
                path = self._learning_paths[self._current_path]
                completed = sum(1 for lid in path.lessons if self._lessons[lid].completed)
                path.progress = completed / len(path.lessons)
            logger.info(f"完成课程: {self._lessons[lesson_id].name} (得分: {score})")
            return True
        return False

    def get_lesson(self, lesson_id: str) -> Optional[Lesson]:
        return self._lessons.get(lesson_id)

    def get_path_progress(self, path_id: str) -> Dict:
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
