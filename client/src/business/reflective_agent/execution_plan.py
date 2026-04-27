"""
反思式Agent执行计划数据模型

定义执行计划的结构
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class PlanType(Enum):
    """计划类型"""
    LINEAR = "linear"           # 线性计划
    PARALLEL = "parallel"       # 并行计划
    DAG = "dag"                 # DAG依赖计划
    CONDITIONAL = "conditional"  # 条件分支计划
    ADAPTIVE = "adaptive"        # 自适应计划


class StepPriority(Enum):
    """步骤优先级"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class PlanStep:
    """
    计划步骤定义

    包含一个可执行步骤的所有信息
    """

    step_id: str
    name: str
    action: str                  # 执行动作
    params: Dict[str, Any] = field(default_factory=dict)  # 执行参数
    dependencies: List[str] = field(default_factory=list)  # 依赖的步骤ID

    # 优先级和策略
    priority: StepPriority = StepPriority.MEDIUM
    timeout_ms: int = 30000      # 超时时间(ms)

    # 执行策略
    retry_on_failure: bool = True
    max_retries: int = 2
    fallback_action: Optional[str] = None

    # 元数据
    description: str = ""
    expected_result: str = ""
    tags: List[str] = field(default_factory=list)

    # 执行追踪
    status: str = "pending"
    attempt_count: int = 0
    last_error: Optional[str] = None

    def can_execute(self, completed_steps: set) -> bool:
        """检查是否满足执行条件"""
        # 检查依赖是否完成
        for dep_id in self.dependencies:
            if dep_id not in completed_steps:
                return False
        return self.status == "pending"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "action": self.action,
            "params": self.params,
            "dependencies": self.dependencies,
            "priority": self.priority.name,
            "timeout_ms": self.timeout_ms,
            "retry_on_failure": self.retry_on_failure,
            "max_retries": self.max_retries,
            "description": self.description,
            "expected_result": self.expected_result,
            "tags": self.tags,
            "status": self.status,
            "attempt_count": self.attempt_count,
            "last_error": self.last_error
        }


@dataclass
class ExecutionPlan:
    """
    执行计划容器

    包含完整的任务执行计划
    """

    # 基础信息
    plan_id: str
    task: str
    created_at: datetime = field(default_factory=datetime.now)

    # 计划类型
    plan_type: PlanType = PlanType.LINEAR

    # 步骤列表
    steps: List[PlanStep] = field(default_factory=list)

    # 原始输入
    original_task: str = ""

    # 上下文信息
    context: Dict[str, Any] = field(default_factory=dict)

    # 预估信息
    estimated_steps: int = 0
    estimated_duration_ms: float = 0.0
    complexity_score: float = 0.0  # 0.0 - 1.0

    # 版本追踪
    version: int = 1
    parent_plan_id: Optional[str] = None  # 修正前的计划ID

    # 反思信息
    reflection_summary: str = ""
    improvement_notes: List[str] = field(default_factory=list)

    def add_step(self, step: PlanStep):
        """添加步骤"""
        self.steps.append(step)
        self.estimated_steps = len(self.steps)

    def get_step(self, step_id: str) -> Optional[PlanStep]:
        """根据ID获取步骤"""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_executable_steps(self, completed: set) -> List[PlanStep]:
        """获取可执行的步骤列表"""
        executable = []
        for step in self.steps:
            if step.can_execute(completed):
                executable.append(step)

        # 按优先级排序
        executable.sort(key=lambda s: s.priority.value)
        return executable

    def mark_completed(self, step_id: str):
        """标记步骤完成"""
        step = self.get_step(step_id)
        if step:
            step.status = "completed"

    def mark_failed(self, step_id: str, error: str):
        """标记步骤失败"""
        step = self.get_step(step_id)
        if step:
            step.status = "failed"
            step.last_error = error
            step.attempt_count += 1

    def create_corrected_plan(self, corrections: List[str]) -> "ExecutionPlan":
        """
        创建修正后的计划

        基于反思结果生成新的执行计划
        """
        new_plan = ExecutionPlan(
            plan_id=f"{self.plan_id}_v{self.version + 1}",
            task=self.task,
            plan_type=self.plan_type,
            original_task=self.original_task,
            parent_plan_id=self.plan_id,
            version=self.version + 1
        )

        # 复制步骤，但根据修正进行调整
        for step in self.steps:
            new_step = PlanStep(
                step_id=f"{step.step_id}_v{self.version + 1}",
                name=step.name,
                action=step.action,
                params=step.params.copy(),
                dependencies=step.dependencies.copy(),
                priority=step.priority,
                timeout_ms=step.timeout_ms,
                retry_on_failure=step.retry_on_failure,
                max_retries=step.max_retries,
                fallback_action=step.fallback_action,
                description=step.description,
                expected_result=step.expected_result,
                tags=step.tags.copy()
            )
            new_plan.add_step(new_step)

        # 添加修正说明
        new_plan.improvement_notes = corrections.copy()
        new_plan.reflection_summary = "; ".join(corrections)

        return new_plan

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "task": self.task,
            "created_at": self.created_at.isoformat(),
            "plan_type": self.plan_type.value,
            "steps": [s.to_dict() for s in self.steps],
            "original_task": self.original_task,
            "estimated_steps": self.estimated_steps,
            "estimated_duration_ms": self.estimated_duration_ms,
            "complexity_score": self.complexity_score,
            "version": self.version,
            "parent_plan_id": self.parent_plan_id,
            "reflection_summary": self.reflection_summary,
            "improvement_notes": self.improvement_notes
        }

    def __len__(self) -> int:
        return len(self.steps)

    def __getitem__(self, index: int) -> PlanStep:
        return self.steps[index]
