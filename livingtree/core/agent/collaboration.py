"""
LivingTree — Multi-Agent Collaboration Scheduler
==================================================

Full migration from client/src/business/multi_agent/collaboration.py

Task distribution, result aggregation, and conflict resolution for
multi-agent collaboration:
- TaskScheduler: skill-based agent matching with load balancing
- ResultAggregator: collects and merges agent execution results
- ConflictResolver: pluggable conflict resolution strategies
"""

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class TaskPriority(Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


class TaskState(Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledTask:
    task_id: str
    description: str
    priority: TaskPriority
    state: TaskState = TaskState.PENDING
    assigned_agent: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentCapabilities:
    agent_id: str
    skills: List[str]
    load: float = 0.0
    max_concurrent: int = 1
    current_tasks: int = 0


class TaskScheduler:
    """Task scheduler — distributes tasks to agents with skill matching and load balancing."""

    def __init__(self):
        self.tasks: Dict[str, ScheduledTask] = {}
        self.agents: Dict[str, AgentCapabilities] = {}
        self.task_queue: List[str] = []
        self._lock = threading.RLock()

    def register_agent(self, agent_id: str, skills: List[str],
                       max_concurrent: int = 1) -> bool:
        with self._lock:
            if agent_id in self.agents:
                return False
            self.agents[agent_id] = AgentCapabilities(
                agent_id=agent_id, skills=skills, max_concurrent=max_concurrent,
            )
            return True

    def submit_task(self, description: str, priority: TaskPriority,
                    required_skills: List[str] = None,
                    dependencies: List[str] = None) -> str:
        task_id = str(uuid.uuid4())[:8]
        task = ScheduledTask(
            task_id=task_id, description=description, priority=priority,
            dependencies=dependencies or [],
        )
        with self._lock:
            self.tasks[task_id] = task
            self._reorder_queue()
        return task_id

    def _reorder_queue(self):
        self.task_queue = sorted(
            self.tasks.keys(),
            key=lambda tid: (self.tasks[tid].priority.value, self.tasks[tid].created_at),
            reverse=True,
        )

    def _find_best_agent(self, required_skills: List[str]) -> Optional[str]:
        with self._lock:
            candidates = []
            for agent_id, caps in self.agents.items():
                if caps.current_tasks >= caps.max_concurrent:
                    continue
                if required_skills:
                    match_count = sum(1 for s in required_skills if s in caps.skills)
                    if match_count == 0:
                        continue
                    match_ratio = match_count / len(required_skills)
                else:
                    match_ratio = 1.0
                candidates.append((agent_id, match_ratio, caps.load))
            if not candidates:
                return None
            candidates.sort(key=lambda x: (x[1], -x[2]), reverse=True)
            return candidates[0][0]

    def _can_schedule(self, task_id: str) -> bool:
        task = self.tasks[task_id]
        if task.state != TaskState.PENDING:
            return False
        for dep_id in task.dependencies:
            if dep_id not in self.tasks:
                continue
            if self.tasks[dep_id].state != TaskState.COMPLETED:
                return False
        return True

    def schedule_next(self) -> Optional[str]:
        with self._lock:
            for task_id in self.task_queue:
                if self._can_schedule(task_id):
                    task = self.tasks[task_id]
                    agent_id = self._find_best_agent(self._extract_skills(task.description))
                    if agent_id:
                        task.state = TaskState.SCHEDULED
                        task.assigned_agent = agent_id
                        self.agents[agent_id].current_tasks += 1
                        self._reorder_queue()
                        return task_id
            return None

    def _extract_skills(self, description: str) -> List[str]:
        skill_keywords = {
            "coding": ["代码", "编程", "写", "code", "implement", "实现"],
            "testing": ["测试", "test", "验证", "verify"],
            "review": ["审查", "review", "审核", "audit"],
            "deploy": ["部署", "deploy", "发布", "release"],
            "design": ["设计", "design", "架构", "architecture"],
        }
        skills = []
        desc_lower = description.lower()
        for skill, keywords in skill_keywords.items():
            if any(kw in desc_lower for kw in keywords):
                skills.append(skill)
        return skills

    def complete_task(self, task_id: str, result: Any) -> bool:
        with self._lock:
            if task_id not in self.tasks:
                return False
            task = self.tasks[task_id]
            task.state = TaskState.COMPLETED
            task.result = result
            task.completed_at = time.time()
            if task.assigned_agent:
                self.agents[task.assigned_agent].current_tasks -= 1
            return True

    def fail_task(self, task_id: str, error: str) -> bool:
        with self._lock:
            if task_id not in self.tasks:
                return False
            task = self.tasks[task_id]
            task.state = TaskState.FAILED
            task.error = error
            task.completed_at = time.time()
            if task.assigned_agent:
                self.agents[task.assigned_agent].current_tasks -= 1
            return True

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return None
            return {
                "task_id": task.task_id,
                "description": task.description,
                "priority": task.priority.name,
                "state": task.state.value,
                "assigned_agent": task.assigned_agent,
                "result": task.result,
                "error": task.error,
                "duration": self._calc_duration(task),
            }

    def _calc_duration(self, task: ScheduledTask) -> Optional[float]:
        if task.started_at and task.completed_at:
            return task.completed_at - task.started_at
        return None

    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            caps = self.agents.get(agent_id)
            if not caps:
                return None
            return {
                "agent_id": agent_id,
                "skills": caps.skills,
                "load": caps.load,
                "max_concurrent": caps.max_concurrent,
                "current_tasks": caps.current_tasks,
            }

    def get_all_tasks(self, state: TaskState = None) -> List[Dict[str, Any]]:
        with self._lock:
            tasks = list(self.tasks.values())
            if state:
                tasks = [t for t in tasks if t.state == state]
            return [{
                "task_id": t.task_id,
                "description": t.description,
                "priority": t.priority.name,
                "state": t.state.value,
                "assigned_agent": t.assigned_agent,
            } for t in tasks]


class ResultAggregator:
    """Result aggregator — collects and merges results from multiple agents."""

    def __init__(self):
        self.results: Dict[str, Any] = {}
        self._lock = threading.RLock()

    def add_result(self, task_id: str, agent_id: str, result: Any) -> None:
        with self._lock:
            self.results[task_id] = {
                "agent_id": agent_id,
                "result": result,
                "timestamp": time.time(),
            }

    def get_result(self, task_id: str) -> Optional[Any]:
        with self._lock:
            entry = self.results.get(task_id)
            return entry["result"] if entry else None

    def get_all_results(self) -> Dict[str, Any]:
        with self._lock:
            return self.results.copy()

    def aggregate(self, task_ids: List[str]) -> Dict[str, Any]:
        with self._lock:
            return {
                tid: self.results[tid]["result"]
                for tid in task_ids if tid in self.results
            }


class ConflictResolver:
    """Conflict resolver — pluggable strategies for resolving multi-agent conflicts."""

    def __init__(self):
        self.conflict_rules: Dict[str, Callable] = {}

    def register_rule(self, conflict_type: str, resolver: Callable) -> None:
        self.conflict_rules[conflict_type] = resolver

    def resolve(self, conflict_type: str, options: List[Any]) -> Any:
        if conflict_type in self.conflict_rules:
            return self.conflict_rules[conflict_type](options)
        return options[0] if options else None


__all__ = [
    "TaskScheduler",
    "ResultAggregator",
    "ConflictResolver",
    "TaskPriority",
    "TaskState",
    "ScheduledTask",
    "AgentCapabilities",
]
