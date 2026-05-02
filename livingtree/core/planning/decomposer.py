"""
LivingTree 统一任务规划器
=========================

整合 task_router 的 TaskNode + TaskRouter + task_decomposer 的 CoT +
task_planning 的调度逻辑

P2 增强:
- ExecutionPlanner: 并行执行策略 + 关键路径分析
- RetryManager: 指数退避重试 + 熔断
- MilestoneTracker: 里程碑进度追踪
- ExecutionMetrics: 执行统计聚合
"""

import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class TaskStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class ExecutionStrategy(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DEPENDENCY_DRIVEN = "dependency_driven"
    PIPELINE = "pipeline"


@dataclass
class TaskNode:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    category: str = "general"
    depth: int = 0
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    result: str = ""
    error: str = ""
    estimated_tokens: int = 500
    actual_tokens: int = 0
    duration_ms: float = 0.0
    retry_count: int = 0
    max_retries: int = 3
    milestone: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def can_execute(self, completed: Set[str]) -> bool:
        return all(dep in completed for dep in self.dependencies)


@dataclass
class TaskPlan:
    root_id: str = ""
    steps: List[TaskNode] = field(default_factory=list)
    strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL
    estimated_total_tokens: int = 0
    actual_total_tokens: int = 0
    max_depth: int = 3
    complexity_threshold: float = 0.5
    fallback_enabled: bool = True
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    milestones: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps
                   if s.status == TaskStatus.COMPLETED)

    @property
    def failed_steps(self) -> int:
        return sum(1 for s in self.steps
                   if s.status == TaskStatus.FAILED)

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        return self.completed_steps / len(self.steps)

    @property
    def is_complete(self) -> bool:
        return all(s.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
                   for s in self.steps)

    @property
    def elapsed_ms(self) -> float:
        if self.started_at == 0:
            return 0.0
        end = self.completed_at or time.time()
        return (end - self.started_at) * 1000


COT_TEMPLATES: Dict[str, str] = {
    "writing": """请按照以下步骤思考：
1. 理解写作主题和要求
2. 搜集相关的背景知识
3. 规划文章结构（开头-正文-结尾）
4. 逐部分撰写内容
5. 检查逻辑连贯性和语言表达""",

    "code": """请按照以下步骤思考：
1. 明确编程需求
2. 设计算法/数据结构
3. 编写核心代码
4. 处理边界情况和错误
5. 优化代码性能""",

    "analysis": """请按照以下步骤思考：
1. 理解分析目标和范围
2. 收集相关数据/信息
3. 选择合适的分析方法
4. 执行分析并验证结果
5. 归纳结论和建议""",

    "default": """请按照以下步骤思考：
1. 理解用户需求
2. 检索相关知识
3. 规划执行方案
4. 逐步实施
5. 验证结果并总结""",
}


class TaskDecomposer:
    """任务分解器 — CoT 引导的多层分解."""

    def __init__(self, max_depth: int = 3,
                 complexity_threshold: float = 0.5):
        self.max_depth = max_depth
        self.complexity_threshold = complexity_threshold

    def decompose(self, description: str, intent_type: str = "default",
                  complexity: float = 0.0,
                  depth: int = 0) -> List[TaskNode]:
        steps = []

        if depth >= self.max_depth or complexity < self.complexity_threshold:
            steps.append(TaskNode(
                description=description, depth=depth,
                estimated_tokens=self._estimate_tokens(description, complexity),
            ))
            return steps

        cot = COT_TEMPLATES.get(intent_type, COT_TEMPLATES["default"])
        cot_lines = [l.strip() for l in cot.split("\n")
                     if l.strip().startswith(("1.", "2.", "3.", "4.", "5."))]

        sub_complexity = complexity / max(len(cot_lines), 1)
        prev_id: Optional[str] = None

        for i, line in enumerate(cot_lines):
            sub_task = TaskNode(
                description=line.lstrip("12345. "),
                depth=depth + 1,
                estimated_tokens=self._estimate_tokens(line, sub_complexity),
                milestone=f"step_{i+1}" if depth == 0 else "",
            )
            if prev_id and depth > 0:
                sub_task.dependencies = [prev_id]
            steps.append(sub_task)
            prev_id = sub_task.id

        return steps

    def _estimate_tokens(self, description: str, complexity: float) -> int:
        base = max(200, len(description) * 8)
        return int(base * (1.0 + complexity))


class ExecutionPlanner:
    """执行规划器 — 分析依赖，确定并行/串行策略."""

    def __init__(self):
        pass

    def analyze(self, plan: TaskPlan) -> Dict[str, Any]:
        """分析 TaskPlan 的执行特征."""
        all_ids = {s.id for s in plan.steps}
        dep_count = sum(len(s.dependencies) for s in plan.steps)

        independent = [s for s in plan.steps
                       if not s.dependencies
                       and s.status == TaskStatus.PENDING]

        return {
            "total_steps": len(plan.steps),
            "dependency_edges": dep_count,
            "independent_steps": len(independent),
            "suggested_strategy": (
                ExecutionStrategy.PARALLEL.value
                if len(independent) >= 3 else
                ExecutionStrategy.SEQUENTIAL.value
            ),
            "critical_path_length": self._critical_path(plan),
        }

    def _critical_path(self, plan: TaskPlan) -> int:
        dep_map: Dict[str, List[str]] = defaultdict(list)
        for step in plan.steps:
            for dep in step.dependencies:
                dep_map[dep].append(step.id)

        longest: Dict[str, int] = {}

        def dfs(node_id: str) -> int:
            if node_id in longest:
                return longest[node_id]
            max_child = 0
            for child in dep_map.get(node_id, []):
                max_child = max(max_child, dfs(child))
            longest[node_id] = max_child + 1
            return longest[node_id]

        roots = [s.id for s in plan.steps if not s.dependencies]
        if not roots:
            return len(plan.steps)
        return max(dfs(r) for r in roots)

    def get_ready_steps(self, plan: TaskPlan,
                        completed: Set[str]) -> List[TaskNode]:
        return [s for s in plan.steps
                if s.status in (TaskStatus.PENDING, TaskStatus.QUEUED)
                and s.can_execute(completed)]


class RetryManager:
    """重试管理器 — 指数退避 + 熔断."""

    def __init__(self, base_delay_ms: float = 500,
                 max_delay_ms: float = 30000,
                 backoff_factor: float = 2.0):
        self.base_delay_ms = base_delay_ms
        self.max_delay_ms = max_delay_ms
        self.backoff_factor = backoff_factor
        self._failure_count: Dict[str, int] = {}
        self._circuit_open: Set[str] = set()

    def delay_for(self, step: TaskNode) -> float:
        delay = self.base_delay_ms * (self.backoff_factor ** step.retry_count)
        return min(delay, self.max_delay_ms) / 1000.0

    def should_retry(self, step: TaskNode) -> bool:
        step_key = f"{step.id}:{step.description[:20]}"
        return (step.retry_count < step.max_retries
                and step_key not in self._circuit_open)

    def record_failure(self, step: TaskNode):
        step_key = f"{step.id}:{step.description[:20]}"
        self._failure_count[step_key] = self._failure_count.get(step_key, 0) + 1
        if self._failure_count[step_key] > step.max_retries * 2:
            self._circuit_open.add(step_key)

    def record_success(self, step: TaskNode):
        step_key = f"{step.id}:{step.description[:20]}"
        self._failure_count.pop(step_key, None)
        self._circuit_open.discard(step_key)


class MilestoneTracker:
    """里程碑追踪 — 进度报告."""

    def __init__(self):
        self._milestones: Dict[str, Dict[str, Any]] = {}

    def register(self, milestone: str, description: str, steps: List[str]):
        self._milestones[milestone] = {
            "description": description,
            "steps": steps,
            "completed": [],
            "status": "pending",
        }

    def mark_step(self, step_id: str):
        for name, ms in self._milestones.items():
            if step_id in ms["steps"] and step_id not in ms["completed"]:
                ms["completed"].append(step_id)
                if len(ms["completed"]) >= len(ms["steps"]):
                    ms["status"] = "completed"
                else:
                    ms["status"] = "in_progress"

    def progress(self) -> Dict[str, Any]:
        total = len(self._milestones)
        completed = sum(1 for m in self._milestones.values()
                        if m["status"] == "completed")
        return {
            "total_milestones": total,
            "completed_milestones": completed,
            "progress": completed / max(total, 1),
            "details": {
                name: {"status": m["status"],
                       "completed": len(m["completed"]),
                       "total": len(m["steps"])}
                for name, m in self._milestones.items()
            },
        }


class TaskScheduler:
    """任务调度器 — 拓扑排序 + 优先级感知."""

    def __init__(self):
        self._queue: deque = deque()
        self._pending: Dict[str, TaskNode] = {}
        self._completed: Set[str] = set()

    def schedule(self, plan: TaskPlan) -> TaskPlan:
        self._completed.clear()
        ready = [s for s in plan.steps
                 if s.status == TaskStatus.PENDING
                 and s.can_execute(self._completed)]
        sorted_steps = []
        visited: Set[str] = set()

        ready.sort(key=lambda s: -s.priority.value)

        while ready:
            step = ready.pop(0)
            if step.id in visited:
                continue
            visited.add(step.id)
            sorted_steps.append(step)
            self._completed.add(step.id)

            newly_ready = [s for s in plan.steps
                          if s.status == TaskStatus.PENDING
                          and s.id not in visited
                          and s.can_execute(self._completed)]
            newly_ready.sort(key=lambda s: -s.priority.value)
            ready.extend(newly_ready)

        for step in plan.steps:
            if step.id not in visited:
                sorted_steps.append(step)

        plan.steps = sorted_steps
        return plan

    def next_task(self, plan: TaskPlan) -> Optional[TaskNode]:
        for step in plan.steps:
            if step.status == TaskStatus.PENDING:
                return step
        return None

    def mark_completed(self, step: TaskNode):
        self._completed.add(step.id)

    def get_executable(self, plan: TaskPlan) -> List[TaskNode]:
        return [s for s in plan.steps
                if s.status == TaskStatus.PENDING
                and s.can_execute(self._completed)]


class TaskPlanner:
    """统一任务规划器 — 分解 + 调度."""

    def __init__(self, max_depth: int = 3,
                 complexity_threshold: float = 0.5):
        self.decomposer = TaskDecomposer(
            max_depth=max_depth, complexity_threshold=complexity_threshold)
        self.scheduler = TaskScheduler()
        self.retry_manager = RetryManager()
        self.execution_planner = ExecutionPlanner()
        self.milestones = MilestoneTracker()

    def plan(self, description: str, intent_type: str = "default",
             complexity: float = 0.0,
             strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL) -> TaskPlan:
        steps = self.decomposer.decompose(
            description=description, intent_type=intent_type,
            complexity=complexity)

        for step in steps:
            if step.milestone:
                self.milestones.register(step.milestone, step.description, [step.id])

        plan = TaskPlan(
            root_id=steps[0].id if steps else "",
            steps=steps,
            strategy=strategy,
            estimated_total_tokens=sum(s.estimated_tokens for s in steps),
            max_depth=self.decomposer.max_depth,
            complexity_threshold=self.decomposer.complexity_threshold,
            created_at=time.time(),
            metadata={
                "intent_type": intent_type,
                "input_complexity": complexity,
            },
        )

        plan = self.scheduler.schedule(plan)
        return plan

    def analyze(self, plan: TaskPlan) -> Dict[str, Any]:
        return self.execution_planner.analyze(plan)

    def get_ready_batch(self, plan: TaskPlan,
                        max_batch: int = 5) -> List[TaskNode]:
        ready = self.execution_planner.get_ready_steps(
            plan, self.scheduler._completed)
        if plan.strategy == ExecutionStrategy.PARALLEL:
            return ready[:max_batch]
        return ready[:1]


__all__ = [
    "TaskPlanner",
    "TaskDecomposer",
    "TaskScheduler",
    "ExecutionPlanner",
    "RetryManager",
    "MilestoneTracker",
    "TaskNode",
    "TaskPlan",
    "TaskStatus",
    "TaskPriority",
    "ExecutionStrategy",
    "COT_TEMPLATES",
]
