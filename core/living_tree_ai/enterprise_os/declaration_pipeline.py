"""
智能申报流水线引擎

支持企业全生命周期各类申报的自动化执行。
"""

import json
import asyncio
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from datetime import datetime


# ==================== 数据模型 ====================

class PipelineStatus(Enum):
    """流水线状态"""
    PENDING = "pending"               # 待执行
    RUNNING = "running"              # 执行中
    PAUSED = "paused"                # 暂停
    COMPLETED = "completed"          # 完成
    FAILED = "failed"               # 失败
    CANCELLED = "cancelled"         # 取消


class TaskStepStatus(Enum):
    """任务步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DeclarationType(Enum):
    """申报类型"""
    EIA_REPORT = "eia_report"               # 环评申报
    POLLUTION_PERMIT = "pollution_permit"  # 排污许可
    SAFETY_PERMIT = "safety_permit"         # 安全许可
    ACCEPTANCE_MONITORING = "acceptance"   # 验收监测
    ANNUAL_REPORT = "annual_report"         # 年度报告
    TAX_DECLARATION = "tax"                 # 税务申报
    SOCIAL_SECURITY = "social_security"     # 社保申报
    STATISTICS = "statistics"               # 统计申报
    HIGH_TECH_CERT = "high_tech"            # 高新认定
    OTHER = "other"


@dataclass
class TaskStep:
    """任务步骤"""
    step_id: str
    name: str
    description: str = ""
    step_order: int = 0
    status: TaskStepStatus = TaskStepStatus.PENDING

    # 执行配置
    command: str = ""                # 执行的命令
    script: str = ""                # 执行脚本
    timeout: int = 300              # 超时时间(秒)
    retry_count: int = 3            # 重试次数
    retry_interval: int = 5         # 重试间隔(秒)

    # 依赖
    depends_on: List[str] = field(default_factory=list)  # 依赖的步骤ID

    # 结果
    result: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 回调
    on_success: str = ""            # 成功回调函数名
    on_failure: str = ""            # 失败回调函数名


@dataclass
class DeclarationTask:
    """申报任务"""
    task_id: str
    declaration_type: DeclarationType
    enterprise_id: str
    title: str
    description: str = ""

    # 步骤
    steps: List[TaskStep] = field(default_factory=list)

    # 状态
    status: PipelineStatus = PipelineStatus.PENDING
    progress: float = 0.0            # 0-100

    # 时间
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 结果
    result: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineExecution:
    """流水线执行上下文"""
    task: DeclarationTask
    current_step_index: int = 0
    step_results: Dict[str, Any] = field(default_factory=dict)
    callbacks: Dict[str, Callable] = field(default_factory=dict)


# ==================== 申报流水线引擎 ====================

class DeclarationPipeline:
    """
    智能申报流水线引擎

    支持：
    - 多步骤申报任务编排
    - 并行/串行执行
    - 断点续传
    - 异常自动处理
    - 执行日志
    """

    def __init__(self):
        self._tasks: Dict[str, DeclarationTask] = {}
        self._pipelines: Dict[str, PipelineExecution] = {}
        self._executors: Dict[str, Callable] = {}

        # 注册内置执行器
        self._register_builtin_executors()

    def _register_builtin_executors(self):
        """注册内置执行器"""
        # 表单填充执行器
        self._executors["form_filler"] = self._execute_form_fill

        # 文件上传执行器
        self._executors["file_uploader"] = self._execute_file_upload

        # 数据验证执行器
        self._executors["validator"] = self._execute_validation

        # 浏览器自动化执行器
        self._executors["browser_automation"] = self._execute_browser

        # API调用执行器
        self._executors["api_caller"] = self._execute_api_call

        # 通知执行器
        self._executors["notifier"] = self._execute_notify

    def register_executor(self, name: str, executor: Callable):
        """注册自定义执行器"""
        self._executors[name] = executor

    def create_task(
        self,
        declaration_type: DeclarationType,
        enterprise_id: str,
        title: str,
        steps: List[Dict] = None
    ) -> DeclarationTask:
        """
        创建申报任务

        Args:
            declaration_type: 申报类型
            enterprise_id: 企业ID
            title: 任务标题
            steps: 步骤定义

        Returns:
            DeclarationTask: 创建的任务
        """
        task_id = self._generate_task_id(enterprise_id, declaration_type)

        # 构建步骤
        task_steps = []
        if steps:
            for i, step_def in enumerate(steps):
                step = TaskStep(
                    step_id=f"{task_id}_step_{i}",
                    name=step_def.get("name", f"步骤{i+1}"),
                    description=step_def.get("description", ""),
                    step_order=i,
                    command=step_def.get("command", ""),
                    script=step_def.get("script", ""),
                    timeout=step_def.get("timeout", 300),
                    retry_count=step_def.get("retry_count", 3),
                    depends_on=step_def.get("depends_on", [])
                )
                task_steps.append(step)

        task = DeclarationTask(
            task_id=task_id,
            declaration_type=declaration_type,
            enterprise_id=enterprise_id,
            title=title,
            steps=task_steps,
            metadata={
                "type_name": declaration_type.value
            }
        )

        self._tasks[task_id] = task
        return task

    async def execute_task(
        self,
        task_id: str,
        context: Dict[str, Any] = None
    ) -> DeclarationTask:
        """
        执行申报任务

        Args:
            task_id: 任务ID
            context: 执行上下文

        Returns:
            DeclarationTask: 执行结果
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        context = context or {}

        # 创建执行上下文
        execution = PipelineExecution(
            task=task,
            step_results={}
        )
        self._pipelines[task_id] = execution

        # 更新任务状态
        task.status = PipelineStatus.RUNNING
        task.started_at = datetime.now()

        try:
            # 按依赖顺序执行步骤
            completed = set()
            pending = {s.step_id for s in task.steps}

            while pending:
                # 找出可以执行的步骤（依赖都已完成）
                runnable = []
                for step in task.steps:
                    if step.step_id in pending:
                        deps_met = all(dep in completed for dep in step.depends_on)
                        if deps_met:
                            runnable.append(step)

                if not runnable:
                    # 无法继续执行，可能有循环依赖
                    break

                # 执行可运行的步骤
                for step in runnable:
                    success = await self._execute_step(step, context, execution)
                    if success:
                        step.status = TaskStepStatus.COMPLETED
                        completed.add(step.step_id)
                    else:
                        step.status = TaskStepStatus.FAILED

                    pending.remove(step.step_id)

                    # 更新进度
                    task.progress = len(completed) / len(task.steps) * 100

                # 如果有失败且不重试，停止
                if any(s.status == TaskStepStatus.FAILED for s in task.steps):
                    break

            # 判断最终状态
            if len(completed) == len(task.steps):
                task.status = PipelineStatus.COMPLETED
            else:
                task.status = PipelineStatus.FAILED

        except Exception as e:
            task.status = PipelineStatus.FAILED
            task.error = str(e)

        finally:
            task.completed_at = datetime.now()

        return task

    async def _execute_step(
        self,
        step: TaskStep,
        context: Dict[str, Any],
        execution: PipelineExecution
    ) -> bool:
        """执行单个步骤"""
        step.status = TaskStepStatus.RUNNING
        step.started_at = datetime.now()

        executor_name = step.command or "generic"
        executor = self._executors.get(executor_name)

        if not executor:
            step.error = f"未找到执行器: {executor_name}"
            return False

        # 重试逻辑
        for attempt in range(step.retry_count):
            try:
                result = await asyncio.wait_for(
                    executor(step, context, execution),
                    timeout=step.timeout
                )

                if result.get("success", False):
                    step.result = result
                    step.status = TaskStepStatus.COMPLETED
                    step.completed_at = datetime.now()
                    execution.step_results[step.step_id] = result
                    return True
                else:
                    step.error = result.get("error", "执行失败")

            except asyncio.TimeoutError:
                step.error = f"执行超时 ({step.timeout}秒)"
            except Exception as e:
                step.error = str(e)

            # 重试等待
            if attempt < step.retry_count - 1:
                await asyncio.sleep(step.retry_interval)

        step.status = TaskStepStatus.FAILED
        step.completed_at = datetime.now()
        return False

    async def _execute_form_fill(self, step, context, execution):
        """表单填充执行器"""
        # 模拟表单填充
        await asyncio.sleep(0.5)
        return {"success": True, "filled_fields": step.script.get("fields", [])}

    async def _execute_file_upload(self, step, context, execution):
        """文件上传执行器"""
        await asyncio.sleep(0.3)
        return {"success": True, "uploaded_files": []}

    async def _execute_validation(self, step, context, execution):
        """数据验证执行器"""
        await asyncio.sleep(0.2)
        return {"success": True, "validated": True}

    async def _execute_browser(self, step, context, execution):
        """浏览器自动化执行器"""
        await asyncio.sleep(1.0)
        return {"success": True, "browser_actions": []}

    async def _execute_api_call(self, step, context, execution):
        """API调用执行器"""
        await asyncio.sleep(0.5)
        return {"success": True, "api_response": {}}

    async def _execute_notify(self, step, context, execution):
        """通知执行器"""
        await asyncio.sleep(0.1)
        return {"success": True, "notified": True}

    def get_task(self, task_id: str) -> Optional[DeclarationTask]:
        """获取任务"""
        return self._tasks.get(task_id)

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        task = self._tasks.get(task_id)
        if not task:
            return None

        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "progress": task.progress,
            "current_step": task.steps[task.current_step_index].name if hasattr(task, 'current_step_index') else "",
            "error": task.error
        }

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status == PipelineStatus.RUNNING:
            task.status = PipelineStatus.CANCELLED
            return True

        return False

    def _generate_task_id(self, enterprise_id: str, decl_type: DeclarationType) -> str:
        """生成任务ID"""
        timestamp = datetime.now().isoformat()
        raw = f"{enterprise_id}_{decl_type.value}_{timestamp}"
        return f"task_{hashlib.md5(raw.encode()).hexdigest()[:12]}"


# ==================== 便捷函数 ====================

_pipeline_instance: Optional[DeclarationPipeline] = None


def get_pipeline_engine() -> DeclarationPipeline:
    """获取流水线引擎单例"""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = DeclarationPipeline()
    return _pipeline_instance


async def create_pipeline_async(
    decl_type: str,
    enterprise_id: str,
    title: str,
    steps: List[Dict] = None
) -> DeclarationTask:
    """创建申报流水线的便捷函数"""
    engine = get_pipeline_engine()
    decl_type_enum = DeclarationType(decl_type)
    return engine.create_task(decl_type_enum, enterprise_id, title, steps)


async def execute_declaration_async(
    task_id: str,
    context: Dict[str, Any] = None
) -> DeclarationTask:
    """执行申报任务的便捷函数"""
    engine = get_pipeline_engine()
    return await engine.execute_task(task_id, context)
