# -*- coding: utf-8 -*-
"""
团队任务管理 - Team Task Management
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set
import uuid


class TaskStatus(Enum):
    """任务状态"""
    TODO = "todo"              # 待处理
    IN_PROGRESS = "in_progress"  # 进行中
    IN_REVIEW = "in_review"    # 审核中
    DONE = "done"              # 已完成
    CANCELLED = "cancelled"    # 已取消


class TaskPriority(Enum):
    """优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class TaskAssignment:
    """任务分配"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    user_id: str = ""
    user_name: str = ""
    assigned_by: str = ""
    assigned_at: datetime = field(default_factory=datetime.now)
    is_primary: bool = True
    notified: bool = False


@dataclass
class TeamTask:
    """团队任务"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    workspace_id: str = ""
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 分配
    assignments: List[TaskAssignment] = field(default_factory=list)
    
    # 关联
    document_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    subtasks: List[str] = field(default_factory=list)  # 子任务ID列表
    
    # 标签和项目
    tags: List[str] = field(default_factory=list)
    project: str = ""
    
    # 统计
    comment_count: int = 0
    attachment_count: int = 0
    
    # 元数据
    metadata: Dict = field(default_factory=dict)
    
    def add_assignee(
        self,
        user_id: str,
        user_name: str,
        assigned_by: str,
        is_primary: bool = True
    ) -> TaskAssignment:
        """添加分配"""
        # 检查是否已分配
        for a in self.assignments:
            if a.user_id == user_id:
                return a
        
        assignment = TaskAssignment(
            user_id=user_id,
            user_name=user_name,
            assigned_by=assigned_by,
            is_primary=is_primary
        )
        self.assignments.append(assignment)
        self.updated_at = datetime.now()
        
        return assignment
    
    def remove_assignee(self, user_id: str) -> bool:
        """移除分配"""
        for i, a in enumerate(self.assignments):
            if a.user_id == user_id:
                del self.assignments[i]
                self.updated_at = datetime.now()
                return True
        return False
    
    def get_assignee_ids(self) -> List[str]:
        """获取所有分配者ID"""
        return [a.user_id for a in self.assignments]
    
    def get_primary_assignee(self) -> Optional[TaskAssignment]:
        """获取主要分配者"""
        for a in self.assignments:
            if a.is_primary:
                return a
        return self.assignments[0] if self.assignments else None
    
    def is_overdue(self) -> bool:
        """是否逾期"""
        if self.due_date and self.status not in [TaskStatus.DONE, TaskStatus.CANCELLED]:
            return datetime.now() > self.due_date
        return False
    
    def get_days_until_due(self) -> Optional[int]:
        """距离截止日期天数"""
        if self.due_date:
            delta = self.due_date - datetime.now()
            return delta.days
        return None
    
    def complete(self):
        """完成任务"""
        self.status = TaskStatus.DONE
        self.completed_at = datetime.now()
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict:
        """转字典"""
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "assignments": [
                {"user_id": a.user_id, "user_name": a.user_name, "is_primary": a.is_primary}
                for a in self.assignments
            ],
            "document_id": self.document_id,
            "parent_task_id": self.parent_task_id,
            "subtasks": self.subtasks,
            "tags": self.tags,
            "project": self.project,
            "is_overdue": self.is_overdue(),
            "days_until_due": self.get_days_until_due()
        }


class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self._tasks: Dict[str, TeamTask] = {}
        self._workspace_tasks: Dict[str, Set[str]] = {}  # workspace_id -> task_ids
        self._user_tasks: Dict[str, Dict[str, str]] = {}  # user_id -> {task_id -> role}
    
    def create_task(
        self,
        workspace_id: str,
        title: str,
        created_by: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date: Optional[datetime] = None,
        assignee_id: Optional[str] = None,
        assignee_name: Optional[str] = None,
        **kwargs
    ) -> TeamTask:
        """创建任务"""
        task = TeamTask(
            workspace_id=workspace_id,
            title=title,
            description=description,
            created_by=created_by,
            priority=priority,
            due_date=due_date,
            document_id=kwargs.get('document_id'),
            parent_task_id=kwargs.get('parent_task_id'),
            tags=kwargs.get('tags', []),
            project=kwargs.get('project', '')
        )
        
        self._tasks[task.id] = task
        
        # 跟踪工作空间
        if workspace_id not in self._workspace_tasks:
            self._workspace_tasks[workspace_id] = set()
        self._workspace_tasks[workspace_id].add(task.id)
        
        # 添加分配
        if assignee_id and assignee_name:
            task.add_assignee(assignee_id, assignee_name, created_by)
            self._track_user_task(assignee_id, task.id, 'assignee')
        
        return task
    
    def get_task(self, task_id: str) -> Optional[TeamTask]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def update_task(self, task_id: str, **updates) -> Optional[TeamTask]:
        """更新任务"""
        task = self._tasks.get(task_id)
        if not task:
            return None
        
        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        task.updated_at = datetime.now()
        return task
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        
        # 清理跟踪
        if task.workspace_id in self._workspace_tasks:
            self._workspace_tasks[task.workspace_id].discard(task_id)
        
        for user_id in self._user_tasks:
            if task_id in self._user_tasks[user_id]:
                del self._user_tasks[user_id][task_id]
        
        # 删除子任务
        for subtask_id in task.subtasks:
            if subtask_id in self._tasks:
                del self._tasks[subtask_id]
        
        del self._tasks[task_id]
        return True
    
    def get_workspace_tasks(
        self,
        workspace_id: str,
        status: Optional[TaskStatus] = None,
        assignee_id: Optional[str] = None
    ) -> List[TeamTask]:
        """获取工作空间任务"""
        task_ids = self._workspace_tasks.get(workspace_id, set())
        tasks = [self._tasks[tid] for tid in task_ids if tid in self._tasks]
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        if assignee_id:
            tasks = [t for t in tasks if assignee_id in t.get_assignee_ids()]
        
        # 排序：优先按状态，再按优先级
        tasks.sort(key=lambda t: (t.status.value, t.priority.value), reverse=True)
        
        return tasks
    
    def get_user_tasks(
        self,
        user_id: str,
        status: Optional[TaskStatus] = None
    ) -> List[TeamTask]:
        """获取用户任务"""
        task_ids = self._user_tasks.get(user_id, {}).keys()
        tasks = [self._tasks[tid] for tid in task_ids if tid in self._tasks]
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        return tasks
    
    def get_overdue_tasks(self, workspace_id: str) -> List[TeamTask]:
        """获取逾期任务"""
        tasks = self.get_workspace_tasks(workspace_id)
        return [t for t in tasks if t.is_overdue()]
    
    def get_tasks_by_project(self, workspace_id: str, project: str) -> List[TeamTask]:
        """按项目获取任务"""
        tasks = self.get_workspace_tasks(workspace_id)
        return [t for t in tasks if t.project == project]
    
    def assign_task(
        self,
        task_id: str,
        user_id: str,
        user_name: str,
        assigned_by: str
    ) -> bool:
        """分配任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        task.add_assignee(user_id, user_name, assigned_by)
        self._track_user_task(user_id, task_id, 'assignee')
        
        return True
    
    def _track_user_task(self, user_id: str, task_id: str, role: str):
        """跟踪用户任务"""
        if user_id not in self._user_tasks:
            self._user_tasks[user_id] = {}
        self._user_tasks[user_id][task_id] = role


# ── 全局实例 ──────────────────────────────────────────────────────────────────

_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """获取任务管理器"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
