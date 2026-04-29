#!/usr/bin/env python3
"""
Agent 闭环系统 - 参考 Ralph 风格设计
实现外部持久化、PRD驱动任务、质量门禁、Git版本控制
"""

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"           # 待处理
    IN_PROGRESS = "in_progress"  # 进行中
    REVIEW = "review"             # 审核中
    APPROVED = "approved"         # 已批准
    REJECTED = "rejected"         # 已拒绝
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败


class TaskPriority(Enum):
    """任务优先级"""
    URGENT = 5    # 紧急
    HIGH = 4      # 高
    MEDIUM = 3   # 中
    LOW = 2      # 低
    TRIVIAL = 1  # 琐碎


class QualityGate(Enum):
    """质量门禁"""
    SYNTAX = "syntax"       # 语法检查
    STYLE = "style"         # 代码风格
    TEST = "test"          # 单元测试
    SECURITY = "security"   # 安全检查
    PERFORMANCE = "performance"  # 性能检查


@dataclass
class Task:
    """任务单元"""
    task_id: str
    title: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    prd_id: Optional[str] = None
    subtasks: List[str] = field(default_factory=list)
    comments: List[Dict[str, Any]] = field(default_factory=list)
    attachments: List[Dict[str, str]] = field(default_factory=list)
    quality_gates: Dict[QualityGate, bool] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
        }


@dataclass
class PRD:
    """产品需求文档"""
    prd_id: str
    title: str
    content: str
    version: int = 1
    status: str = "draft"  # draft, active, archived
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    tasks: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prd_id": self.prd_id,
            "title": self.title,
            "content": self.content,
            "version": self.version,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class RalphAgentLoop:
    """
    Ralph 风格 Agent 闭环系统

    特性:
    1. PRD 驱动任务分解
    2. 外部持久化存储
    3. 质量门禁检查
    4. Git 版本控制
    5. 任务追踪与审核
    """

    def __init__(self, storage_path: str = None, git_repo: str = None):
        self.storage_path = storage_path
        self.git_repo = git_repo
        self._tasks: Dict[str, Task] = {}
        self._prds: Dict[str, PRD] = {}
        self._next_task_id = 1
        self._next_prd_id = 1
        self._quality_gates: Dict[QualityGate, Callable] = {}
        self._event_handlers: Dict[str, List[Callable]] = {
            "task_created": [],
            "task_updated": [],
            "task_completed": [],
            "prd_created": [],
            "quality_gate_passed": [],
            "quality_gate_failed": [],
        }

    def set_quality_gate(self, gate: QualityGate, checker: Callable[[str], bool]):
        """设置质量门禁"""
        self._quality_gates[gate] = checker

    def register_handler(self, event: str, handler: Callable):
        """注册事件处理器"""
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    def _trigger_event(self, event: str, *args, **kwargs):
        """触发事件"""
        for handler in self._event_handlers.get(event, []):
            try:
                handler(*args, **kwargs)
            except Exception as e:
                print(f"Event handler error: {e}")

    def create_prd(
        self,
        title: str,
        content: str,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """
        创建 PRD

        Args:
            title: PRD标题
            content: PRD内容
            metadata: 元数据

        Returns:
            prd_id: PRD ID
        """
        prd_id = f"prd_{self._next_prd_id:05d}"
        self._next_prd_id += 1

        prd = PRD(
            prd_id=prd_id,
            title=title,
            content=content,
            metadata=metadata or {},
        )

        self._prds[prd_id] = prd
        self._save_to_git(f"prd/{prd_id}.json", prd.to_dict())

        self._trigger_event("prd_created", prd_id, prd)

        return prd_id

    def create_task(
        self,
        title: str,
        description: str,
        priority: str = "medium",
        prd_id: str = None,
        assignee: str = None,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """
        创建任务

        Args:
            title: 任务标题
            description: 任务描述
            priority: 优先级 (urgent/high/medium/low/trivial)
            prd_id: 关联的 PRD ID
            assignee: 负责人
            metadata: 元数据

        Returns:
            task_id: 任务 ID
        """
        task_id = f"task_{self._next_task_id:05d}"
        self._next_task_id += 1

        task = Task(
            task_id=task_id,
            title=title,
            description=description,
            priority=TaskPriority[priority.upper()],
            prd_id=prd_id,
            assignee=assignee,
            metadata=metadata or {},
        )

        if prd_id and prd_id in self._prds:
            self._prds[prd_id].tasks.append(task_id)

        self._tasks[task_id] = task
        self._save_to_git(f"tasks/{task_id}.json", task.to_dict())

        self._trigger_event("task_created", task_id, task)

        return task_id

    def update_task(
        self,
        task_id: str,
        status: str = None,
        priority: str = None,
        assignee: str = None,
        **kwargs
    ) -> bool:
        """
        更新任务

        Args:
            task_id: 任务 ID
            status: 新状态
            priority: 新优先级
            assignee: 新负责人
            **kwargs: 其他更新

        Returns:
            是否成功
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        if status:
            task.status = TaskStatus(status)
        if priority:
            task.priority = TaskPriority[priority.upper()]
        if assignee:
            task.assignee = assignee

        task.updated_at = datetime.now()
        task.version += 1

        for key, value in kwargs.items():
            task.metadata[key] = value

        self._save_to_git(f"tasks/{task_id}.json", task.to_dict())

        self._trigger_event("task_updated", task_id, task)

        return True

    def complete_task(self, task_id: str) -> bool:
        """
        完成任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        if self._run_quality_gates(task):
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.updated_at = datetime.now()
            task.quality_gates = {gate: True for gate in self._quality_gates}

            self._save_to_git(f"tasks/{task_id}.json", task.to_dict())

            self._trigger_event("task_completed", task_id, task)

            return True
        else:
            task.status = TaskStatus.FAILED
            self._save_to_git(f"tasks/{task_id}.json", task.to_dict())

            for gate in self._quality_gates:
                if gate not in task.quality_gates or not task.quality_gates[gate]:
                    self._trigger_event("quality_gate_failed", task_id, gate)

            return False

    def _run_quality_gates(self, task: Task) -> bool:
        """运行质量门禁"""
        if not self._quality_gates:
            return True

        for gate, checker in self._quality_gates.items():
            try:
                passed = checker(task.description)
                task.quality_gates[gate] = passed
                if passed:
                    self._trigger_event("quality_gate_passed", task.task_id, gate)
            except Exception:
                task.quality_gates[gate] = False

        return all(task.quality_gates.values())

    def review_task(
        self,
        task_id: str,
        decision: str,  # approved/rejected
        comment: str = None,
        reviewer: str = None,
    ) -> bool:
        """
        审核任务

        Args:
            task_id: 任务 ID
            decision: 决定
            comment: 审核意见
            reviewer: 审核人

        Returns:
            是否成功
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        if decision == "approved":
            task.status = TaskStatus.APPROVED
        elif decision == "rejected":
            task.status = TaskStatus.REJECTED

        task.updated_at = datetime.now()

        if comment:
            task.comments.append({
                "reviewer": reviewer or "anonymous",
                "comment": comment,
                "decision": decision,
                "timestamp": datetime.now().isoformat(),
            })

        self._save_to_git(f"tasks/{task_id}.json", task.to_dict())

        return True

    def _save_to_git(self, path: str, data: Dict[str, Any]):
        """保存数据到 Git"""
        if not self.git_repo:
            return

        try:
            content = json.dumps(data, indent=2, ensure_ascii=False)

            full_path = f"{self.git_repo}/{path}"
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            subprocess.run(
                ["git", "add", path],
                cwd=self.git_repo,
                capture_output=True,
                check=False,
            )

            commit_msg = f"Update {path} at {datetime.now().isoformat()}"
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=self.git_repo,
                capture_output=True,
                check=False,
            )

        except Exception as e:
            print(f"Git save error: {e}")

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)

    def get_tasks_by_prd(self, prd_id: str) -> List[Task]:
        """获取 PRD 关联的任务"""
        prd = self._prds.get(prd_id)
        if not prd:
            return []
        return [self._tasks[tid] for tid in prd.tasks if tid in self._tasks]

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """获取指定状态的任务"""
        return [t for t in self._tasks.values() if t.status == status]

    def get_pending_tasks(self, assignee: str = None) -> List[Task]:
        """获取待处理任务"""
        tasks = self.get_tasks_by_status(TaskStatus.PENDING)
        tasks += self.get_tasks_by_status(TaskStatus.IN_PROGRESS)

        if assignee:
            tasks = [t for t in tasks if t.assignee == assignee]

        return sorted(tasks, key=lambda t: (t.priority.value, t.created_at), reverse=True)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        status_counts = {}
        for status in TaskStatus:
            status_counts[status.value] = len(
                [t for t in self._tasks.values() if t.status == status]
            )

        return {
            "total_tasks": len(self._tasks),
            "total_prds": len(self._prds),
            "by_status": status_counts,
        }

    def decompose_prd(self, prd_id: str) -> List[str]:
        """
        将 PRD 分解为任务

        Args:
            prd_id: PRD ID

        Returns:
            任务 ID 列表
        """
        prd = self._prds.get(prd_id)
        if not prd:
            return []

        task_ids = []

        lines = prd.content.split("\n")
        current_section = ""
        current_description = []

        for line in lines:
            line = line.strip()
            if line.startswith("# ") or line.startswith("## "):
                if current_section and current_description:
                    task_id = self.create_task(
                        title=current_section,
                        description="\n".join(current_description),
                        priority="medium",
                        prd_id=prd_id,
                    )
                    task_ids.append(task_id)

                current_section = line.lstrip("# ").strip()
                current_description = []
            elif line.startswith("- "):
                current_description.append(line[2:])
            elif line:
                current_description.append(line)

        if current_section and current_description:
            task_id = self.create_task(
                title=current_section,
                description="\n".join(current_description),
                priority="medium",
                prd_id=prd_id,
            )
            task_ids.append(task_id)

        return task_ids


import os


def test_ralph_agent_loop():
    """测试 Ralph Agent 循环"""
    print("=== 测试 Ralph Agent 闭环系统 ===")

    loop = RalphAgentLoop()

    print("\n1. 测试创建 PRD")
    prd_id = loop.create_prd(
        title="用户认证系统",
        content="""
# 用户认证系统

## 功能需求
- 用户注册
- 用户登录
- 密码重置

## 技术需求
- 使用 JWT
- 支持 OAuth2
- 数据加密存储
        """,
    )
    print(f"  PRD ID: {prd_id}")

    print("\n2. 测试 PRD 分解为任务")
    task_ids = loop.decompose_prd(prd_id)
    print(f"  分解为 {len(task_ids)} 个任务:")
    for tid in task_ids:
        task = loop.get_task(tid)
        print(f"    - {task.title}")

    print("\n3. 测试更新任务")
    success = loop.update_task(task_ids[0], status="in_progress", assignee="zhangsan")
    print(f"  更新成功: {success}")

    print("\n4. 测试设置质量门禁")
    loop.set_quality_gate(QualityGate.SYNTAX, lambda x: len(x) > 10)
    loop.set_quality_gate(QualityGate.STYLE, lambda x: "描述" in x or "description" in x.lower())

    print("\n5. 测试完成任务")
    success = loop.complete_task(task_ids[0])
    print(f"  完成任务成功: {success}")

    print("\n6. 测试审核任务")
    success = loop.review_task(task_ids[0], "approved", "代码质量良好", "lisi")
    print(f"  审核成功: {success}")

    print("\n7. 测试统计")
    stats = loop.get_stats()
    print(f"  统计: {stats}")

    print("\n8. 测试获取待处理任务")
    pending = loop.get_pending_tasks()
    print(f"  待处理任务: {len(pending)}")

    print("\nRalph Agent 闭环系统测试完成！")


if __name__ == "__main__":
    test_ralph_agent_loop()