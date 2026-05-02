"""
SOLO Plan 模式管理器（Trae 风格）

实现 SOLO Plan 工作流模式：
1. Plan 模式 - 禁止直接写代码，先规划
2. 拆解 SKILL 激活 - 选择合适的拆解技能
3. 审阅修改 - 人工确认拆解方案
4. 分步执行 - 按计划执行并验收
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from livingtree.core.planning.task_decomposer import (
    DecomposedTask, TaskStep, StepStatus, ProcessType,
    TaskDecomposer, ChainOfThoughtExecutor,
)

logger = logging.getLogger(__name__)


class PlanMode(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    REVIEWING = "reviewing"
    EXECUTING = "executing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ExecutionPhase(Enum):
    DECOMPOSITION = "decomposition"
    REVIEW = "review"
    EXECUTION = "execution"
    ACCEPTANCE = "acceptance"


@dataclass
class PlanSession:
    session_id: str
    requirement: str
    mode: PlanMode = PlanMode.IDLE
    phase: ExecutionPhase = ExecutionPhase.DECOMPOSITION
    decomposed_task: Optional[DecomposedTask] = None
    current_step: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    review_comments: List[str] = field(default_factory=list)
    acceptance_notes: List[str] = field(default_factory=list)

    @property
    def progress(self) -> float:
        if not self.decomposed_task:
            return 0.0
        return self.decomposed_task.progress

    def add_log(self, message: str, phase: ExecutionPhase = None):
        self.execution_log.append({
            "timestamp": datetime.now().isoformat(),
            "phase": phase.value if phase else self.phase.value,
            "message": message,
        })

    def add_review_comment(self, comment: str):
        self.review_comments.append(comment)


@dataclass
class ExecutionStats:
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_execution_time: float = 0.0
    rework_count: int = 0
    rework_rate: float = 0.0


class SoloPlanManager:
    """SOLO Plan 模式管理器"""

    def __init__(self):
        self._plan_mode = False
        self._current_session: Optional[PlanSession] = None
        self._sessions: Dict[str, PlanSession] = {}
        self._llm_callable: Optional[Callable[[str], str]] = None
        self._progress_callback: Optional[Callable] = None
        self._stats = ExecutionStats()

    @property
    def plan_mode(self) -> bool:
        return self._plan_mode

    @property
    def current_session(self) -> Optional[PlanSession]:
        return self._current_session

    @property
    def stats(self) -> ExecutionStats:
        return self._stats

    def set_llm_callable(self, llm_callable: Callable[[str], str]):
        self._llm_callable = llm_callable

    def set_progress_callback(self, callback: Callable):
        self._progress_callback = callback

    def enter_plan_mode(self):
        self._plan_mode = True
        logger.info("[SoloPlanManager] 进入 Plan 模式")

    def exit_plan_mode(self):
        self._plan_mode = False
        self._current_session = None
        logger.info("[SoloPlanManager] 退出 Plan 模式")

    def start_new_session(self, requirement: str) -> PlanSession:
        import uuid
        session_id = f"plan_{uuid.uuid4().hex[:8]}"
        session = PlanSession(
            session_id=session_id,
            requirement=requirement,
            mode=PlanMode.PLANNING,
            phase=ExecutionPhase.DECOMPOSITION,
        )
        self._current_session = session
        self._sessions[session_id] = session
        session.add_log(f"会话创建，需求: {requirement[:50]}...")
        logger.info(f"[SoloPlanManager] 开始新会话: {session_id}")
        return session

    def decompose_task(self, requirement: str) -> DecomposedTask:
        if not self._current_session:
            self.start_new_session(requirement)

        decomposer = TaskDecomposer(default_process_type=ProcessType.HIERARCHICAL)
        task = decomposer.decompose(question=requirement)

        self._current_session.decomposed_task = task
        self._current_session.phase = ExecutionPhase.REVIEW
        self._current_session.add_log(f"任务拆解完成，共 {task.total_steps} 个步骤")
        return task

    def review_task(self, modifications: Optional[Dict[str, Any]] = None) -> bool:
        if not self._current_session or not self._current_session.decomposed_task:
            raise ValueError("没有当前会话或拆解任务")

        self._current_session.phase = ExecutionPhase.REVIEW
        self._current_session.mode = PlanMode.REVIEWING
        self._current_session.add_log("任务审阅完成")
        return True

    def start_execution(self) -> bool:
        if not self._current_session or not self._current_session.decomposed_task:
            raise ValueError("没有当前会话或拆解任务")

        self._current_session.mode = PlanMode.EXECUTING
        self._current_session.phase = ExecutionPhase.EXECUTION
        self._current_session.started_at = datetime.now()
        self._current_session.add_log("开始执行任务")
        return True

    async def execute_next_step(self) -> Optional[TaskStep]:
        if not self._current_session or not self._current_session.decomposed_task:
            raise ValueError("没有当前会话或拆解任务")

        task = self._current_session.decomposed_task
        next_step = task.get_next_executable_step()

        if not next_step:
            if task.progress == 1.0:
                self._complete_session()
            return None

        next_step.status = StepStatus.RUNNING

        try:
            full_instruction = self._inject_context(task, next_step)
            if self._llm_callable:
                output = self._llm_callable(full_instruction)
            else:
                try:
                    from livingtree.core.model.router import get_model_router
                    output = get_model_router().route(full_instruction)
                except Exception as e:
                    output = f"[Error: {str(e)}]"

            next_step.output_data = output
            next_step.status = StepStatus.COMPLETED
            next_step.confidence = 0.8
            self._current_session.current_step += 1
            self._current_session.add_log(f"步骤 {next_step.step_id} 执行完成")

            if task.progress == 1.0:
                self._complete_session()

        except Exception as e:
            next_step.status = StepStatus.FAILED
            next_step.error = str(e)
            self._current_session.add_log(f"步骤 {next_step.step_id} 执行失败: {str(e)}")
            self._stats.rework_count += 1

        return next_step

    def _inject_context(self, task: DecomposedTask, step: TaskStep) -> str:
        full_instruction = step.instruction
        for dep_id in step.depends_on:
            dep = task.get_step(dep_id)
            if dep and dep.output_data:
                placeholder = "{" + dep_id + "}"
                full_instruction = full_instruction.replace(
                    placeholder, str(dep.output_data))
        return full_instruction

    def accept_step(self, step_id: str, notes: str = "") -> bool:
        if not self._current_session or not self._current_session.decomposed_task:
            return False
        if notes:
            self._current_session.acceptance_notes.append(f"步骤 {step_id}: {notes}")
        return True

    def reject_step(self, step_id: str, reason: str) -> bool:
        if not self._current_session or not self._current_session.decomposed_task:
            return False
        step = self._current_session.decomposed_task.get_step(step_id)
        if not step:
            return False
        step.status = StepStatus.PENDING
        step.output_data = None
        step.error = reason
        self._stats.rework_count += 1
        self._current_session.add_log(f"步骤 {step_id} 被拒绝，原因: {reason}")
        return True

    def _complete_session(self):
        self._current_session.mode = PlanMode.COMPLETED
        self._current_session.phase = ExecutionPhase.ACCEPTANCE
        self._current_session.completed_at = datetime.now()
        self._stats.total_tasks += 1
        self._stats.completed_tasks += 1

    def cancel_session(self, reason: str = ""):
        if not self._current_session:
            return
        self._current_session.mode = PlanMode.CANCELLED
        if reason:
            self._current_session.add_log(f"会话取消: {reason}")

    def get_session(self, session_id: str) -> Optional[PlanSession]:
        return self._sessions.get(session_id)

    def list_sessions(self, mode: PlanMode = None) -> List[PlanSession]:
        sessions = list(self._sessions.values())
        if mode:
            sessions = [s for s in sessions if s.mode == mode]
        return sessions

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            if self._current_session and self._current_session.session_id == session_id:
                self._current_session = None
            return True
        return False


def create_solo_plan_manager() -> SoloPlanManager:
    return SoloPlanManager()


_global_plan_manager: Optional[SoloPlanManager] = None


def get_solo_plan_manager() -> SoloPlanManager:
    global _global_plan_manager
    if _global_plan_manager is None:
        _global_plan_manager = SoloPlanManager()
    return _global_plan_manager


__all__ = [
    "PlanMode", "ExecutionPhase", "PlanSession", "ExecutionStats",
    "SoloPlanManager", "create_solo_plan_manager", "get_solo_plan_manager",
]
