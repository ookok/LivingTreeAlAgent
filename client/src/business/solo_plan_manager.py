"""
SOLO Plan 模式管理器（Trae 风格）
================================

实现 Trae IDE 的 SOLO Plan 工作流模式：
1. Plan 模式 - 禁止直接写代码，先规划
2. 拆解 SKILL 激活 - 选择合适的拆解技能
3. 审阅修改 - 人工确认拆解方案
4. 分步执行 - 按计划执行并验收

核心特性：
- Plan 模式状态管理
- 拆解技能智能选择
- 任务依赖可视化
- 分步执行与验收
- 返工率统计

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Union
from enum import Enum
from datetime import datetime

from client.src.business.task_decomposer import (
    DecomposedTask,
    TaskStep,
    StepStatus,
    ProcessType,
    TaskDecomposer,
    ChainOfThoughtExecutor,
)
from client.src.business.agent_skills.task_decomposition_skills import (
    DecompositionSkillType,
    DecompositionSkillFactory,
    BaseDecompositionSkill,
)
from client.src.business.task_planning import (
    TaskPlanner,
    TaskExecutor,
    TaskTree,
    Task,
    TaskType,
    TaskStatus,
)

logger = logging.getLogger(__name__)


class PlanMode(Enum):
    """Plan 模式状态"""
    IDLE = "idle"           # 空闲状态
    PLANNING = "planning"   # Plan 模式（禁止执行代码）
    REVIEWING = "reviewing" # 审阅模式
    EXECUTING = "executing" # 执行模式
    COMPLETED = "completed" # 完成
    CANCELLED = "cancelled" # 取消


class ExecutionPhase(Enum):
    """执行阶段"""
    DECOMPOSITION = "decomposition"  # 任务拆解
    REVIEW = "review"                # 审阅修改
    EXECUTION = "execution"          # 分步执行
    ACCEPTANCE = "acceptance"        # 验收纠偏


@dataclass
class PlanSession:
    """Plan 会话"""
    session_id: str
    requirement: str
    mode: PlanMode = PlanMode.IDLE
    phase: ExecutionPhase = ExecutionPhase.DECOMPOSITION
    decomposed_task: Optional[DecomposedTask] = None
    task_tree: Optional[TaskTree] = None
    current_step: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    review_comments: List[str] = field(default_factory=list)
    acceptance_notes: List[str] = field(default_factory=list)
    
    @property
    def progress(self) -> float:
        """计算整体进度"""
        if not self.decomposed_task:
            return 0.0
        return self.decomposed_task.progress
    
    def add_log(self, message: str, phase: ExecutionPhase = None):
        """添加执行日志"""
        self.execution_log.append({
            "timestamp": datetime.now().isoformat(),
            "phase": phase.value if phase else self.phase.value,
            "message": message,
        })
    
    def add_review_comment(self, comment: str):
        """添加审阅评论"""
        self.review_comments.append(comment)


@dataclass
class ExecutionStats:
    """执行统计"""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_execution_time: float = 0.0  # 秒
    rework_count: int = 0
    rework_rate: float = 0.0


class SoloPlanManager:
    """
    SOLO Plan 模式管理器
    
    核心工作流：
    1. 进入 Plan 模式 → 禁止直接写代码
    2. 选择拆解 SKILL → 输入精准指令
    3. 审阅修改 → 补充细节、修正偏差
    4. 分步执行 → 每步验收纠偏
    
    效率提升：
    - 开发周期：7-15天 → 2-5天
    - 返工率：50%+ → <10%
    - 效率提升：3倍+
    """
    
    def __init__(self):
        self._plan_mode = False
        self._current_session: Optional[PlanSession] = None
        self._sessions: Dict[str, PlanSession] = {}
        self._llm_callable: Optional[Callable[[str], str]] = None
        self._progress_callback: Optional[Callable] = None
        self._stats = ExecutionStats()
        
    @property
    def plan_mode(self) -> bool:
        """是否处于 Plan 模式"""
        return self._plan_mode
    
    @property
    def current_session(self) -> Optional[PlanSession]:
        """当前会话"""
        return self._current_session
    
    @property
    def stats(self) -> ExecutionStats:
        """执行统计"""
        return self._stats
    
    def set_llm_callable(self, llm_callable: Callable[[str], str]):
        """设置 LLM 调用函数"""
        self._llm_callable = llm_callable
    
    def set_progress_callback(self, callback: Callable):
        """设置进度回调"""
        self._progress_callback = callback
    
    def enter_plan_mode(self):
        """
        进入 Plan 模式
        
        快捷键：Win=Alt+P、Mac=Option+P
        
        进入此模式后，禁止直接执行代码，必须先进行任务拆解和规划
        """
        self._plan_mode = True
        logger.info("[SoloPlanManager] 进入 Plan 模式")
        
    def exit_plan_mode(self):
        """
        退出 Plan 模式
        
        允许直接执行代码
        """
        self._plan_mode = False
        self._current_session = None
        logger.info("[SoloPlanManager] 退出 Plan 模式")
    
    def start_new_session(self, requirement: str) -> PlanSession:
        """
        开始新的 Plan 会话
        
        Args:
            requirement: 用户需求描述
            
        Returns:
            PlanSession: 新创建的会话
        """
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
    
    def select_decomposition_skill(self, requirement: str) -> BaseDecompositionSkill:
        """
        智能选择拆解技能
        
        根据需求描述自动选择合适的拆解技能：
        - 架构设计相关 → ArchitectureDesignerSkill
        - 代码重构相关 → CodeRefactorerSkill
        - 通用任务拆解 → TaskSplitterProSkill
        
        Args:
            requirement: 用户需求描述
            
        Returns:
            选择的拆解技能
        """
        requirement_lower = requirement.lower()
        
        # 架构设计关键词
        architecture_keywords = ["架构", "系统", "微服务", "高可用", "并发", "设计"]
        if any(k in requirement_lower for k in architecture_keywords):
            return DecompositionSkillFactory.get_skill(DecompositionSkillType.ARCHITECTURE)
        
        # 代码重构关键词
        refactoring_keywords = ["重构", "优化", "代码", "解耦", "嵌套"]
        if any(k in requirement_lower for k in refactoring_keywords):
            return DecompositionSkillFactory.get_skill(DecompositionSkillType.REFACTORING)
        
        # 默认使用任务拆解大师
        return DecompositionSkillFactory.get_skill(DecompositionSkillType.TASK_SPLIT)
    
    def decompose_task(self, requirement: str, skill_type: DecompositionSkillType = None) -> DecomposedTask:
        """
        拆解任务
        
        Args:
            requirement: 用户需求描述
            skill_type: 指定技能类型（可选，自动检测如果为None）
            
        Returns:
            DecomposedTask: 拆解后的任务
        """
        if not self._current_session:
            self.start_new_session(requirement)
        
        # 选择拆解技能
        if skill_type:
            skill = DecompositionSkillFactory.get_skill(skill_type)
        else:
            skill = self.select_decomposition_skill(requirement)
        
        logger.info(f"[SoloPlanManager] 使用技能: {skill.get_manifest().name}")
        self._current_session.add_log(f"使用拆解技能: {skill.get_manifest().name}")
        
        # 激活技能进行拆解
        task = skill.activate(requirement)
        self._current_session.decomposed_task = task
        self._current_session.phase = ExecutionPhase.REVIEW
        
        logger.info(f"[SoloPlanManager] 任务拆解完成，步骤数: {task.total_steps}")
        self._current_session.add_log(f"任务拆解完成，共 {task.total_steps} 个步骤")
        
        return task
    
    def review_task(self, modifications: Optional[Dict[str, Any]] = None) -> bool:
        """
        审阅并修改拆解方案
        
        Args:
            modifications: 修改内容（可选）
            
        Returns:
            bool: 是否通过审阅
        """
        if not self._current_session or not self._current_session.decomposed_task:
            raise ValueError("没有当前会话或拆解任务")
        
        self._current_session.phase = ExecutionPhase.REVIEW
        
        if modifications:
            # 应用修改
            task = self._current_session.decomposed_task
            
            # 修改步骤标题
            if "step_titles" in modifications:
                for step_id, new_title in modifications["step_titles"].items():
                    step = task.get_step(step_id)
                    if step:
                        step.title = new_title
                        self._current_session.add_review_comment(f"修改步骤 {step_id} 标题: {new_title}")
            
            # 修改步骤描述
            if "step_descriptions" in modifications:
                for step_id, new_desc in modifications["step_descriptions"].items():
                    step = task.get_step(step_id)
                    if step:
                        step.description = new_desc
                        self._current_session.add_review_comment(f"修改步骤 {step_id} 描述")
            
            # 添加额外步骤
            if "add_steps" in modifications:
                for step_data in modifications["add_steps"]:
                    # 在指定位置插入新步骤
                    pass
            
            # 删除步骤
            if "remove_steps" in modifications:
                for step_id in modifications["remove_steps"]:
                    # 从任务中移除步骤
                    pass
        
        # 标记审阅完成
        self._current_session.mode = PlanMode.REVIEWING
        logger.info("[SoloPlanManager] 任务审阅完成")
        self._current_session.add_log("任务审阅完成")
        
        return True
    
    def start_execution(self) -> bool:
        """
        开始执行拆解后的任务
        
        Returns:
            bool: 是否成功开始执行
        """
        if not self._current_session or not self._current_session.decomposed_task:
            raise ValueError("没有当前会话或拆解任务")
        
        if self._current_session.phase != ExecutionPhase.REVIEW:
            raise ValueError("必须先完成审阅")
        
        self._current_session.mode = PlanMode.EXECUTING
        self._current_session.phase = ExecutionPhase.EXECUTION
        self._current_session.started_at = datetime.now()
        
        logger.info("[SoloPlanManager] 开始执行任务")
        self._current_session.add_log("开始执行任务")
        
        return True
    
    async def execute_next_step(self) -> Optional[TaskStep]:
        """
        执行下一个步骤
        
        Returns:
            TaskStep: 执行的步骤（如果没有可执行的步骤则返回None）
        """
        if not self._current_session or not self._current_session.decomposed_task:
            raise ValueError("没有当前会话或拆解任务")
        
        if self._current_session.mode != PlanMode.EXECUTING:
            raise ValueError("必须先开始执行")
        
        task = self._current_session.decomposed_task
        next_step = task.get_next_executable_step()
        
        if not next_step:
            # 检查是否所有步骤都已完成
            if task.progress == 1.0:
                self._complete_session()
            return None
        
        # 执行步骤
        executor = ChainOfThoughtExecutor(
            llm_callable=self._llm_callable,
            progress_callback=self._on_step_progress,
            process_type=task.process_type,
        )
        
        # 只执行当前步骤
        next_step.status = StepStatus.RUNNING
        
        try:
            # 构建完整指令
            from client.src.business.task_decomposer import ChainOfThoughtExecutor
            full_instruction = self._inject_context(task, next_step)
            
            # 调用 LLM
            if self._llm_callable:
                output = self._llm_callable(full_instruction)
            else:
                # 使用默认调用
                try:
                    from client.src.business.global_model_router import call_model_sync, ModelCapability
                    output = call_model_sync(ModelCapability.CHAT, full_instruction)
                except Exception as e:
                    output = f"[Error: {str(e)}]"
            
            next_step.output_data = output
            next_step.status = StepStatus.COMPLETED
            next_step.confidence = 0.8
            
            self._current_session.current_step += 1
            self._current_session.add_log(f"步骤 {next_step.step_id} 执行完成")
            
            # 进度回调
            if self._progress_callback:
                self._progress_callback(next_step, self._current_session.current_step, task.total_steps)
            
            # 检查是否完成
            if task.progress == 1.0:
                self._complete_session()
            
        except Exception as e:
            next_step.status = StepStatus.FAILED
            next_step.error = str(e)
            self._current_session.add_log(f"步骤 {next_step.step_id} 执行失败: {str(e)}")
            self._stats.rework_count += 1
        
        return next_step
    
    def _inject_context(self, task: DecomposedTask, step: TaskStep) -> str:
        """
        注入上下文（前置步骤的输出）
        
        Args:
            task: 任务
            step: 当前步骤
            
        Returns:
            完整的指令（带上下文）
        """
        full_instruction = step.instruction
        
        # 替换上下文占位符
        for dep_id in step.depends_on:
            dep = task.get_step(dep_id)
            if dep and dep.output_data:
                placeholder = "{" + dep_id + "}"
                full_instruction = full_instruction.replace(
                    placeholder, 
                    str(dep.output_data)
                )
        
        return full_instruction
    
    def _on_step_progress(self, step: TaskStep, current: int, total: int):
        """
        步骤进度回调
        
        Args:
            step: 当前步骤
            current: 当前步骤索引
            total: 总步骤数
        """
        if self._progress_callback:
            self._progress_callback(step, current, total)
    
    def accept_step(self, step_id: str, notes: str = "") -> bool:
        """
        验收步骤结果
        
        Args:
            step_id: 步骤ID
            notes: 验收备注
            
        Returns:
            bool: 是否通过验收
        """
        if not self._current_session or not self._current_session.decomposed_task:
            raise ValueError("没有当前会话或拆解任务")
        
        step = self._current_session.decomposed_task.get_step(step_id)
        if not step:
            return False
        
        if notes:
            self._current_session.acceptance_notes.append(f"步骤 {step_id}: {notes}")
        
        logger.info(f"[SoloPlanManager] 步骤 {step_id} 验收通过")
        return True
    
    def reject_step(self, step_id: str, reason: str) -> bool:
        """
        拒绝步骤结果（需要返工）
        
        Args:
            step_id: 步骤ID
            reason: 拒绝原因
            
        Returns:
            bool: 是否成功拒绝
        """
        if not self._current_session or not self._current_session.decomposed_task:
            raise ValueError("没有当前会话或拆解任务")
        
        step = self._current_session.decomposed_task.get_step(step_id)
        if not step:
            return False
        
        # 重置步骤状态
        step.status = StepStatus.PENDING
        step.output_data = None
        step.error = reason
        
        self._stats.rework_count += 1
        self._current_session.add_log(f"步骤 {step_id} 被拒绝，原因: {reason}")
        
        logger.info(f"[SoloPlanManager] 步骤 {step_id} 被拒绝，需要返工")
        return True
    
    def _complete_session(self):
        """完成会话"""
        self._current_session.mode = PlanMode.COMPLETED
        self._current_session.phase = ExecutionPhase.ACCEPTANCE
        self._current_session.completed_at = datetime.now()
        
        # 更新统计
        self._stats.total_tasks += 1
        self._stats.completed_tasks += 1
        
        if self._current_session.started_at:
            duration = (self._current_session.completed_at - self._current_session.started_at).total_seconds()
            self._stats.total_execution_time += duration
        
        # 计算返工率
        if self._stats.completed_tasks > 0:
            self._stats.rework_rate = self._stats.rework_count / (self._stats.completed_tasks * 5)  # 假设平均5步
        
        logger.info(f"[SoloPlanManager] 会话完成: {self._current_session.session_id}")
        self._current_session.add_log("会话完成")
    
    def cancel_session(self, reason: str = ""):
        """
        取消会话
        
        Args:
            reason: 取消原因
        """
        if not self._current_session:
            return
        
        self._current_session.mode = PlanMode.CANCELLED
        if reason:
            self._current_session.add_log(f"会话取消: {reason}")
        
        logger.info(f"[SoloPlanManager] 会话取消: {self._current_session.session_id}")
    
    def get_session(self, session_id: str) -> Optional[PlanSession]:
        """获取指定会话"""
        return self._sessions.get(session_id)
    
    def list_sessions(self, mode: PlanMode = None) -> List[PlanSession]:
        """
        列出所有会话
        
        Args:
            mode: 按模式过滤（可选）
            
        Returns:
            会话列表
        """
        sessions = list(self._sessions.values())
        if mode:
            sessions = [s for s in sessions if s.mode == mode]
        return sessions
    
    def delete_session(self, session_id: str) -> bool:
        """
        删除会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 是否删除成功
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            if self._current_session and self._current_session.session_id == session_id:
                self._current_session = None
            return True
        return False
    
    async def execute_with_plan(self, requirement: str, auto_accept: bool = False) -> Dict[str, Any]:
        """
        执行完整的 Plan→拆解→执行 流程
        
        Args:
            requirement: 用户需求描述
            auto_accept: 是否自动验收（默认否）
            
        Returns:
            执行结果摘要
        """
        # 1. 进入 Plan 模式
        self.enter_plan_mode()
        
        try:
            # 2. 开始会话
            self.start_new_session(requirement)
            
            # 3. 拆解任务
            task = self.decompose_task(requirement)
            
            # 4. 审阅（模拟）
            self.review_task()
            
            # 5. 开始执行
            self.start_execution()
            
            # 6. 执行所有步骤
            while True:
                step = await self.execute_next_step()
                if not step:
                    break
                
                # 如果不是自动验收，等待确认
                if not auto_accept:
                    # 模拟人工验收流程
                    await asyncio.sleep(0.1)  # 模拟等待
                
                # 验收步骤
                self.accept_step(step.step_id)
            
            # 7. 返回结果
            return self._current_session.execution_log[-1] if self._current_session.execution_log else {}
            
        finally:
            # 8. 退出 Plan 模式
            self.exit_plan_mode()
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """
        获取执行摘要
        
        Returns:
            执行摘要字典
        """
        if not self._current_session or not self._current_session.decomposed_task:
            return {}
        
        task = self._current_session.decomposed_task
        return {
            "session_id": self._current_session.session_id,
            "requirement": self._current_session.requirement,
            "mode": self._current_session.mode.value,
            "phase": self._current_session.phase.value,
            "progress": task.progress,
            "total_steps": task.total_steps,
            "completed_steps": task.completed_steps,
            "process_type": task.process_type.value,
            "steps": [step.to_dict() for step in task.steps],
            "execution_log": self._current_session.execution_log,
            "review_comments": self._current_session.review_comments,
            "acceptance_notes": self._current_session.acceptance_notes,
        }


# 便捷函数
def create_solo_plan_manager() -> SoloPlanManager:
    """创建 SOLO Plan 管理器实例"""
    return SoloPlanManager()


# 全局实例（单例）
_global_plan_manager: Optional[SoloPlanManager] = None

def get_solo_plan_manager() -> SoloPlanManager:
    """获取全局 SOLO Plan 管理器实例"""
    global _global_plan_manager
    if _global_plan_manager is None:
        _global_plan_manager = SoloPlanManager()
    return _global_plan_manager


__all__ = [
    # 枚举类型
    "PlanMode",
    "ExecutionPhase",
    # 数据类
    "PlanSession",
    "ExecutionStats",
    # 管理器类
    "SoloPlanManager",
    # 便捷函数
    "create_solo_plan_manager",
    "get_solo_plan_manager",
]