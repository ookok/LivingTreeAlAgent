"""
GSD 核心引擎

实现规格驱动开发的核心功能：
- 项目配置管理
- 阶段（Phase）管理
- 计划（Plan）管理
- 任务（Task）管理
- 工作区（Workspace）管理
"""

import json
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid
import shutil


class PhaseStatus(Enum):
    """阶段状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    BLOCKED = "blocked"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DEFERRED = "deferred"


class ExecutionMode(Enum):
    """执行模式"""
    YOLO = "yolo"           # 自动执行
    INTERACTIVE = "interactive"  # 交互确认


class Granularity(Enum):
    """粒度"""
    COARSE = "coarse"       # 粗粒度
    STANDARD = "standard"  # 标准
    FINE = "fine"          # 细粒度


@dataclass
class GSDConfig:
    """GSD 配置"""
    execution_mode: ExecutionMode = ExecutionMode.INTERACTIVE
    granularity: Granularity = Granularity.STANDARD
    parallelization_enabled: bool = True
    commit_docs: bool = True
    research_enabled: bool = True
    plan_check_enabled: bool = True
    verifier_enabled: bool = True
    auto_advance: bool = False
    context_warnings: bool = True
    planning_dir: str = ".planning"


@dataclass
class GSDTask:
    """GSD 任务"""
    task_id: str
    name: str
    files: List[str]
    action: str
    verify: str
    done: str
    status: TaskStatus = TaskStatus.PENDING
    wave: int = 0
    dependencies: List[str] = field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


@dataclass
class GSDPlan:
    """GSD 计划"""
    plan_id: str
    phase: int
    name: str
    tasks: List[GSDTask]
    status: TaskStatus = TaskStatus.PENDING
    wave: int = 0
    summary: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


@dataclass
class DiscussionContext:
    """讨论上下文"""
    phase: int
    visual_design: List[str] = field(default_factory=list)
    api_design: List[str] = field(default_factory=list)
    content_system: List[str] = field(default_factory=list)
    organization: List[str] = field(default_factory=list)
    decisions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchResult:
    """研究结果"""
    phase: int
    tech_stack: Dict[str, Any] = field(default_factory=dict)
    architecture: Dict[str, Any] = field(default_factory=dict)
    patterns: List[str] = field(default_factory=list)
    pitfalls: List[str] = field(default_factory=list)


@dataclass
class VerificationResult:
    """验证结果"""
    phase: int
    passed: bool
    items: List[Dict[str, Any]] = field(default_factory=list)
    failures: List[Dict[str, str]] = field(default_factory=list)
    fixes: List[str] = field(default_factory=list)


@dataclass
class GSDPhase:
    """GSD 阶段"""
    phase_id: int
    name: str
    description: str
    status: PhaseStatus = PhaseStatus.PENDING
    context: Optional[DiscussionContext] = None
    research: Optional[ResearchResult] = None
    plans: List[GSDPlan] = field(default_factory=list)
    verification: Optional[VerificationResult] = None
    assumptions: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


@dataclass
class ProjectMetadata:
    """项目元数据"""
    name: str
    description: str
    goals: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    tech_preferences: Dict[str, Any] = field(default_factory=dict)
    scope_v1: List[str] = field(default_factory=list)
    scope_v2: List[str] = field(default_factory=list)
    out_of_scope: List[str] = field(default_factory=list)


@dataclass
class GSDWorkspace:
    """GSD 工作区"""
    workspace_id: str
    name: str
    path: Path
    config: GSDConfig
    metadata: Optional[ProjectMetadata] = None
    phases: List[GSDPhase] = field(default_factory=list)
    current_phase: int = 1
    planning_dir: Path = None
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if self.planning_dir is None:
            self.planning_dir = self.path / self.config.planning_dir


class GSDEngine:
    """GSD 核心引擎"""

    def __init__(self, workspace_path: str | Path, config: Optional[GSDConfig] = None):
        self.workspace_path = Path(workspace_path)
        self.config = config or GSDConfig()
        self.workspace: Optional[GSDWorkspace] = None
        self._event_handlers: Dict[str, List[Callable]] = {}

        self._init_workspace()
        self._setup_directories()

    def _init_workspace(self):
        """初始化工作区"""
        workspace_id = str(uuid.uuid4())[:8]
        self.workspace = GSDWorkspace(
            workspace_id=workspace_id,
            name=self.workspace_path.name,
            path=self.workspace_path,
            config=self.config
        )

    def _setup_directories(self):
        """设置目录结构"""
        dirs = [
            self.workspace.planning_dir,
            self.workspace.planning_dir / "research",
            self.workspace.planning_dir / "phase_contexts",
            self.workspace.planning_dir / "plans",
            self.workspace.planning_dir / "summaries",
            self.workspace.planning_dir / "verifications",
            self.workspace.planning_dir / "quick",
        ]

        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def new_project(self, metadata: ProjectMetadata) -> str:
        """
        创建新项目

        Args:
            metadata: 项目元数据

        Returns:
            str: 项目 ID
        """
        self.workspace.metadata = metadata
        self._save_project_md()
        self._save_requirements_md()
        self._save_roadmap_md()
        self._save_state_md()
        return self.workspace.workspace_id

    def add_phase(self, name: str, description: str) -> GSDPhase:
        """
        添加阶段

        Args:
            name: 阶段名称
            description: 阶段描述

        Returns:
            GSDPhase: 创建的阶段
        """
        phase_id = len(self.workspace.phases) + 1
        phase = GSDPhase(
            phase_id=phase_id,
            name=name,
            description=description
        )
        self.workspace.phases.append(phase)
        self._save_roadmap_md()
        return phase

    def discuss_phase(self, phase_id: int, context: DiscussionContext):
        """
        讨论阶段

        Args:
            phase_id: 阶段 ID
            context: 讨论上下文
        """
        phase = self._get_phase(phase_id)
        phase.context = context
        self._save_phase_context(phase)
        self._emit("phase_discussed", phase)

    def plan_phase(
        self,
        phase_id: int,
        research: Optional[ResearchResult] = None,
        plans: List[GSDPlan] = None
    ) -> List[GSDPlan]:
        """
        规划阶段

        Args:
            phase_id: 阶段 ID
            research: 研究结果
            plans: 计划列表

        Returns:
            List[GSDPlan]: 创建的计划列表
        """
        phase = self._get_phase(phase_id)
        phase.status = PhaseStatus.IN_PROGRESS
        phase.research = research

        if plans:
            phase.plans = plans
            for i, plan in enumerate(plans):
                plan.wave = self._calculate_waves(plan.tasks)

        self._save_phase_research(phase)
        self._save_plans(phase)
        self._save_state_md()
        self._emit("phase_planned", phase)
        return phase.plans

    def execute_phase(
        self,
        phase_id: int,
        executor_fn: Optional[Callable[[GSDTask], Any]] = None
    ) -> Dict[str, Any]:
        """
        执行阶段

        Args:
            phase_id: 阶段 ID
            executor_fn: 执行器函数

        Returns:
            Dict: 执行结果
        """
        phase = self._get_phase(phase_id)
        results = {}

        waves = self._group_by_waves(phase.plans)

        for wave_num, plans_in_wave in waves.items():
            if self.config.parallelization_enabled:
                tasks = []
                for plan in plans_in_wave:
                    tasks.extend([(plan, task) for task in plan.tasks if task.wave == wave_num])

                if executor_fn:
                    for plan, task in tasks:
                        try:
                            result = executor_fn(task)
                            task.status = TaskStatus.COMPLETED
                            task.completed_at = time.time()
                            task.result = str(result)
                        except Exception as e:
                            task.status = TaskStatus.FAILED
                            task.error = str(e)
                else:
                    for plan, task in tasks:
                        task.status = TaskStatus.COMPLETED
                        task.completed_at = time.time()
                        task.result = "simulated"

            else:
                for plan in plans_in_wave:
                    for task in plan.tasks:
                        if task.wave == wave_num:
                            task.status = TaskStatus.COMPLETED
                            task.completed_at = time.time()
                            task.result = "simulated"

        phase.status = PhaseStatus.COMPLETED
        self._save_summaries(phase)
        self._save_state_md()
        self._emit("phase_executed", phase)
        return results

    def verify_phase(self, phase_id: int) -> VerificationResult:
        """
        验证阶段

        Args:
            phase_id: 阶段 ID

        Returns:
            VerificationResult: 验证结果
        """
        phase = self._get_phase(phase_id)
        result = VerificationResult(
            phase=phase_id,
            passed=True,
            items=[],
            failures=[],
            fixes=[]
        )

        for plan in phase.plans:
            for task in plan.tasks:
                result.items.append({
                    "task_id": task.task_id,
                    "name": task.name,
                    "status": task.status.value,
                    "done": task.done
                })
                if task.status != TaskStatus.COMPLETED:
                    result.passed = False
                    result.failures.append({
                        "task_id": task.task_id,
                        "name": task.name,
                        "error": task.error or "未完成"
                    })

        phase.verification = result
        phase.status = PhaseStatus.VERIFIED if result.passed else PhaseStatus.BLOCKED
        self._save_verification(phase)
        self._save_state_md()
        self._emit("phase_verified", phase)
        return result

    def ship_phase(self, phase_id: int) -> Dict[str, str]:
        """
        发布阶段

        Args:
            phase_id: 阶段 ID

        Returns:
            Dict: PR 信息
        """
        phase = self._get_phase(phase_id)
        return {
            "branch": f"gsd/phase-{phase_id}-{self._slugify(phase.name)}",
            "message": f"feat(phase-{phase_id}): complete {phase.name}",
            "phase": phase_id,
            "plans_count": len(phase.plans)
        }

    def complete_milestone(self) -> Dict[str, Any]:
        """
        完成里程碑

        Returns:
            Dict: 里程碑完成信息
        """
        completed = []
        for phase in self.workspace.phases:
            if phase.status == PhaseStatus.VERIFIED:
                completed.append(phase.phase_id)

        return {
            "completed_phases": completed,
            "total_phases": len(self.workspace.phases),
            "tag": f"v{len(self.workspace.phases)}.0.0"
        }

    def quick_task(self, description: str, plans: List[GSDPlan] = None) -> str:
        """
        快速任务

        Args:
            description: 任务描述
            plans: 计划列表

        Returns:
            str: 计划目录路径
        """
        task_dir = self.workspace.planning_dir / "quick" / f"001-{self._slugify(description)}"
        task_dir.mkdir(parents=True, exist_ok=True)

        plan_file = task_dir / "PLAN.md"
        plan_file.write_text(f"# {description}\n\nPlans: {plans or 'Quick task'}")

        return str(task_dir)

    def get_progress(self) -> Dict[str, Any]:
        """
        获取进度

        Returns:
            Dict: 进度信息
        """
        phases_summary = []
        for phase in self.workspace.phases:
            phases_summary.append({
                "phase_id": phase.phase_id,
                "name": phase.name,
                "status": phase.status.value,
                "plans_count": len(phase.plans),
                "completed_tasks": sum(1 for p in phase.plans for t in p.tasks if t.status == TaskStatus.COMPLETED),
                "total_tasks": sum(len(p.tasks) for p in phase.plans)
            })

        return {
            "current_phase": self.workspace.current_phase,
            "total_phases": len(self.workspace.phases),
            "phases": phases_summary,
            "workspace_id": self.workspace.workspace_id
        }

    def _get_phase(self, phase_id: int) -> GSDPhase:
        """获取阶段"""
        for phase in self.workspace.phases:
            if phase.phase_id == phase_id:
                return phase
        raise ValueError(f"Phase {phase_id} not found")

    def _calculate_waves(self, tasks: List[GSDTask]) -> Dict[int, List[int]]:
        """计算 wave 分组"""
        waves = {}
        task_waves = {}

        for i, task in enumerate(tasks):
            if not task.dependencies:
                task_waves[task.task_id] = 0
            else:
                max_dep_wave = max(
                    (task_waves.get(dep, 0) for dep in task.dependencies),
                    default=0
                )
                task_waves[task.task_id] = max_dep_wave + 1

            wave = task_waves[task.task_id]
            if wave not in waves:
                waves[wave] = []
            waves[wave].append(i)

        for task in tasks:
            task.wave = task_waves.get(task.task_id, 0)

        return waves

    def _group_by_waves(self, plans: List[GSDPlan]) -> Dict[int, List[GSDPlan]]:
        """按 wave 分组计划"""
        waves = {}
        for plan in plans:
            if plan.wave not in waves:
                waves[plan.wave] = []
            waves[plan.wave].append(plan)
        return dict(sorted(waves.items()))

    def _slugify(self, text: str) -> str:
        """转换为 slug"""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '-', text)
        text = re.sub(r'^-+|-+$', '', text)
        return text[:50]

    def _save_project_md(self):
        """保存 PROJECT.md"""
        if not self.workspace.metadata:
            return

        meta = self.workspace.metadata
        content = f"""# {meta.name}

## 项目愿景

{meta.description}

## 目标

{chr(10).join(f"- {goal}" for goal in meta.goals)}

## 约束

{chr(10).join(f"- {c}" for c in meta.constraints)}

## 技术偏好

{json.dumps(meta.tech_preferences, indent=2, ensure_ascii=False)}

## v1 范围

{chr(10).join(f"- {s}" for s in meta.scope_v1)}

## v2 范围

{chr(10).join(f"- {s}" for s in meta.scope_v2)}

## 范围外

{chr(10).join(f"- {s}" for s in meta.out_of_scope)}
"""

        (self.workspace.planning_dir / "PROJECT.md").write_text(content, encoding='utf-8')

    def _save_requirements_md(self):
        """保存 REQUIREMENTS.md"""
        if not self.workspace.metadata:
            return

        meta = self.workspace.metadata
        content = f"""# 需求文档

## v1 需求

{chr(10).join(f"{i+1}. {s}" for i, s in enumerate(meta.scope_v1))}

## v2 需求

{chr(10).join(f"{i+1}. {s}" for i, s in enumerate(meta.scope_v2))}

## 需求追踪

| 需求ID | 描述 | 阶段 | 状态 |
|--------|------|------|------|
"""

        for i, req in enumerate(meta.scope_v1):
            content += f"| REQ-{i+1:03d} | {req} | Phase TBD | Pending |\n"

        (self.workspace.planning_dir / "REQUIREMENTS.md").write_text(content, encoding='utf-8')

    def _save_roadmap_md(self):
        """保存 ROADMAP.md"""
        content = """# 路线图

## 阶段

| 阶段 | 名称 | 状态 | 计划数 | 完成度 |
|------|------|------|--------|--------|
"""

        for phase in self.workspace.phases:
            total_tasks = sum(len(p.tasks) for p in phase.plans)
            completed_tasks = sum(
                sum(1 for t in p.tasks if t.status == TaskStatus.COMPLETED)
                for p in phase.plans
            )
            progress = f"{completed_tasks}/{total_tasks}" if total_tasks > 0 else "-"
            content += f"| Phase {phase.phase_id} | {phase.name} | {phase.status.value} | {len(phase.plans)} | {progress} |\n"

        (self.workspace.planning_dir / "ROADMAP.md").write_text(content, encoding='utf-8')

    def _save_state_md(self):
        """保存 STATE.md"""
        content = f"""# 状态

## 当前阶段

Phase {self.workspace.current_phase}

## 阶段状态

"""
        for phase in self.workspace.phases:
            content += f"### Phase {phase.phase_id}: {phase.name}\n"
            content += f"- 状态: {phase.status.value}\n"
            content += f"- 阻塞: {', '.join(phase.blockers) if phase.blockers else '无'}\n"
            content += f"- 假设: {', '.join(phase.assumptions) if phase.assumptions else '无'}\n\n"

        (self.workspace.planning_dir / "STATE.md").write_text(content, encoding='utf-8')

    def _save_phase_context(self, phase: GSDPhase):
        """保存阶段上下文"""
        if not phase.context:
            return

        ctx = phase.context
        content = f"""# Phase {phase.phase_id} 上下文

## 视觉设计

{chr(10).join(f"- {d}" for d in ctx.visual_design)}

## API 设计

{chr(10).join(f"- {d}" for d in ctx.api_design)}

## 内容系统

{chr(10).join(f"- {d}" for d in ctx.content_system)}

## 组织

{chr(10).join(f"- {d}" for d in ctx.organization)}

## 决策

{json.dumps(ctx.decisions, indent=2, ensure_ascii=False)}
"""

        ctx_file = self.workspace.planning_dir / "phase_contexts" / f"phase-{phase.phase_id}-CONTEXT.md"
        ctx_file.write_text(content, encoding='utf-8')

    def _save_phase_research(self, phase: GSDPhase):
        """保存阶段研究"""
        if not phase.research:
            return

        research = phase.research
        content = f"""# Phase {phase.phase_id} 研究

## 技术栈

{json.dumps(research.tech_stack, indent=2, ensure_ascii=False)}

## 架构

{json.dumps(research.architecture, indent=2, ensure_ascii=False)}

## 模式

{chr(10).join(f"- {p}" for p in research.patterns)}

## 坑点

{chr(10).join(f"- {p}" for p in research.pitfalls)}
"""

        research_file = self.workspace.planning_dir / "research" / f"phase-{phase.phase_id}-RESEARCH.md"
        research_file.write_text(content, encoding='utf-8')

    def _save_plans(self, phase: GSDPhase):
        """保存计划"""
        for i, plan in enumerate(phase.plans):
            content = f"""# Phase {phase.phase_id} Plan {i+1}: {plan.name}

## 任务

"""
            for task in plan.tasks:
                content += f"""<task type="auto">
  <name>{task.name}</name>
  <files>{', '.join(task.files)}</files>
  <action>
{task.action}
  </action>
  <verify>{task.verify}</verify>
  <done>{task.done}</done>
</task>

"""

            plan_file = self.workspace.planning_dir / "plans" / f"phase-{phase.phase_id}-{i+1}-PLAN.md"
            plan_file.write_text(content, encoding='utf-8')

    def _save_summaries(self, phase: GSDPhase):
        """保存摘要"""
        content = f"""# Phase {phase.phase_id} 执行摘要

## 计划摘要

"""
        for i, plan in enumerate(phase.plans):
            content += f"### Plan {i+1}: {plan.name}\n"
            completed = sum(1 for t in plan.tasks if t.status == TaskStatus.COMPLETED)
            content += f"- 完成: {completed}/{len(plan.tasks)} 任务\n"
            content += f"- Wave: {plan.wave}\n\n"

        summary_file = self.workspace.planning_dir / "summaries" / f"phase-{phase.phase_id}-SUMMARY.md"
        summary_file.write_text(content, encoding='utf-8')

    def _save_verification(self, phase: GSDPhase):
        """保存验证"""
        if not phase.verification:
            return

        v = phase.verification
        content = f"""# Phase {phase.phase_id} 验证

## 状态

{'✅ 通过' if v.passed else '❌ 失败'}

## 验证项

"""
        for item in v.items:
            status = "✅" if item['status'] == 'completed' else "❌"
            content += f"- {status} {item['name']}: {item['done']}\n"

        if v.failures:
            content += "\n## 失败项\n\n"
            for f_item in v.failures:
                content += f"- {f_item['name']}: {f_item['error']}\n"

        if v.fixes:
            content += "\n## 修复计划\n\n"
            for fix in v.fixes:
                content += f"- {fix}\n"

        verification_file = self.workspace.planning_dir / "verifications" / f"phase-{phase.phase_id}-VERIFICATION.md"
        verification_file.write_text(content, encoding='utf-8')

    def on(self, event: str, handler: Callable):
        """注册事件处理器"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def _emit(self, event: str, *args):
        """触发事件"""
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                handler(*args)
            except Exception as e:
                print(f"[GSDEngine] Event handler error: {e}")


_global_engine: Optional[GSDEngine] = None


def get_gsd_engine(workspace_path: Optional[str] = None) -> GSDEngine:
    """获取 GSD 引擎"""
    global _global_engine
    if _global_engine is None:
        import os
        if workspace_path is None:
            workspace_path = os.getcwd()
        _global_engine = GSDEngine(workspace_path)
    return _global_engine


def create_gsd_task(
    name: str,
    files: List[str],
    action: str,
    verify: str,
    done: str,
    dependencies: Optional[List[str]] = None
) -> GSDTask:
    """创建 GSD 任务"""
    return GSDTask(
        task_id=str(uuid.uuid4())[:8],
        name=name,
        files=files,
        action=action,
        verify=verify,
        done=done,
        dependencies=dependencies or []
    )


def create_gsd_plan(
    phase: int,
    name: str,
    tasks: List[GSDTask]
) -> GSDPlan:
    """创建 GSD 计划"""
    return GSDPlan(
        plan_id=str(uuid.uuid4())[:8],
        phase=phase,
        name=name,
        tasks=tasks
    )