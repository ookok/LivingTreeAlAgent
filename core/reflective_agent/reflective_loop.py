"""
反思式Agent执行循环 (ReflectiveAgentLoop)

核心能力：执行-反思-改进的迭代循环
"""

import asyncio
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field

from .execution_result import (
    ExecutionResult, ExecutionStep, ExecutionError,
    ExecutionStatus, ErrorCategory, ErrorSeverity
)
from .execution_plan import ExecutionPlan, PlanStep
from .reflection_engine import ReflectionEngine, ReflectionResult
from .improvement_generator import ImprovementGenerator, ImprovementPlan, Improvement
from .error_handlers import ErrorHandlerRegistry


# 类型别名
ExecutorFunc = Callable[[PlanStep], Awaitable[Dict[str, Any]]]
PlannerFunc = Callable[[str], Awaitable[ExecutionPlan]]
FallbackFunc = Callable[[str, list], Awaitable[Dict[str, Any]]]


@dataclass
class ReflectiveLoopConfig:
    """反思循环配置"""

    # 执行控制
    max_attempts: int = 3                    # 最大尝试次数
    step_timeout_ms: int = 30000             # 单步超时(ms)
    plan_timeout_ms: int = 300000            # 计划总超时(ms)

    # 反思控制
    reflection_threshold: float = 0.7         # 反思触发阈值
    quality_threshold: float = 0.6           # 质量阈值

    # 改进控制
    max_improvements: int = 5                # 最大改进数量
    improvement_confidence_threshold: float = 0.5  # 改进置信度阈值

    # 调试选项
    verbose: bool = False
    log_execution: bool = True


class ReflectiveAgentLoop:
    """
    反思式Agent执行循环

    核心能力：
    1. 执行-反思-改进的迭代模式
    2. 自动错误检测和恢复
    3. 基于历史的学习和改进

    使用示例：
    ```python
    loop = ReflectiveAgentLoop()

    # 注册执行器
    loop.register_executor("search", search_handler)
    loop.register_executor("write", write_handler)

    # 执行任务
    result = await loop.execute_with_reflection("帮我搜索AI的最新进展")
    logger.info(result.final_result)
    ```
    """

    def __init__(self, config: Optional[ReflectiveLoopConfig] = None):
        self.config = config or ReflectiveLoopConfig()

        # 执行器注册
        self._executors: Dict[str, ExecutorFunc] = {}

        # 组件
        self._reflection_engine = ReflectionEngine()
        self._improvement_generator = ImprovementGenerator()
        self._error_registry = ErrorHandlerRegistry()

        # 执行历史
        self.execution_history: list[ExecutionResult] = []

        # 统计信息
        self.stats = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "total_reflections": 0,
            "total_improvements": 0,
            "average_attempts": 0.0
        }

    # ==================== 注册接口 ====================

    def register_executor(self, action: str, handler: ExecutorFunc):
        """
        注册执行器

        Args:
            action: 动作名称
            handler: 异步执行函数
        """
        self._executors[action] = handler
        if self.config.verbose:
            logger.info(f"[ReflectiveLoop] Registered executor: {action}")

    def register_planner(self, planner: PlannerFunc):
        """注册规划器"""
        self._planner = planner

    def register_fallback(self, fallback: FallbackFunc):
        """注册降级处理器"""
        self._fallback = fallback

    # ==================== 核心执行接口 ====================

    async def execute_with_reflection(self, task: str) -> ExecutionResult:
        """
        反思式执行主入口

        执行-反思-改进的迭代循环

        Args:
            task: 用户任务

        Returns:
            执行结果
        """
        self.stats["total_tasks"] += 1

        # 初始化结果容器
        result = ExecutionResult(
            task=task,
            status=ExecutionStatus.RUNNING,
            max_attempts=self.config.max_attempts
        )

        current_plan: Optional[ExecutionPlan] = None

        for attempt in range(1, self.config.max_attempts + 1):
            result.attempt_number = attempt

            if self.config.verbose:
                logger.info(f"\n[ReflectiveLoop] Attempt {attempt}/{self.config.max_attempts}")

            try:
                # ==================== 阶段1：规划 ====================
                if current_plan is None:
                    current_plan = await self._plan_execution(task)

                # ==================== 阶段2：执行 ====================
                step_results, errors, metrics = await self._execute_with_monitoring(
                    current_plan
                )

                # 更新结果
                for step_res in step_results:
                    result.add_step(step_res)
                for err in errors:
                    result.add_error(err)
                result.metrics = metrics

                # ==================== 阶段3：反思 ====================
                reflection = self._reflection_engine.reflect(
                    result=result,
                    plan=current_plan
                )

                self.stats["total_reflections"] += 1

                if self.config.verbose:
                    logger.info(f"[ReflectiveLoop] Reflection: success={reflection.success}")

                # 检查是否成功
                if reflection.success:
                    result.mark_success()
                    result.final_result = step_results[-1].result if step_results else None
                    result.reflection_notes = reflection.summary
                    break

                # ==================== 阶段4：生成改进 ====================
                improvement_plan = self._improvement_generator.generate(
                    reflection,
                    current_plan
                )

                self.stats["total_improvements"] += len(improvement_plan.improvements)

                if self.config.verbose:
                    logger.info(f"[ReflectiveLoop] Generated {len(improvement_plan.improvements)} improvements")

                # 应用改进到计划
                current_plan = self._improvement_generator.apply_improvements(
                    current_plan,
                    improvement_plan.get_sorted_improvements()
                )

                result.improvements_applied.extend([
                    imp.description for imp in improvement_plan.improvements
                ])

                # 记录执行历史
                result.execution_history.append({
                    "attempt": attempt,
                    "plan_id": current_plan.plan_id,
                    "reflection": reflection.to_dict(),
                    "improvements": [i.to_dict() for i in improvement_plan.improvements]
                })

            except Exception as e:
                # 即时错误处理
                error = ExecutionError(
                    error_id=str(uuid.uuid4()),
                    category=ErrorCategory.UNKNOWN,
                    severity=ErrorSeverity.HIGH,
                    message=str(e)
                )
                result.add_error(error)

                if self.config.verbose:
                    logger.info(f"[ReflectiveLoop] Error during attempt {attempt}: {e}")

        # ==================== 最终结果 ====================
        if result.status == ExecutionStatus.RUNNING:
            # 所有尝试完成但未明确成功
            if result.completion_rate >= self.config.quality_threshold:
                result.status = ExecutionStatus.PARTIAL
            else:
                result.mark_failed("Max attempts reached without success")

        # 调用降级方案
        if result.status != ExecutionStatus.SUCCESS:
            result = await self._execute_fallback(task, result.execution_history)

        # 记录到历史
        self.execution_history.append(result)
        self._update_stats(result)

        return result

    # ==================== 规划阶段 ====================

    async def _plan_execution(self, task: str) -> ExecutionPlan:
        """规划执行步骤"""
        # 如果注册了外部规划器，使用它
        if hasattr(self, "_planner"):
            return await self._planner(task)

        # 默认规划：简单分解
        plan = ExecutionPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            task=task,
            original_task=task
        )

        # 简单分解为单个步骤
        # 优先使用已注册的执行器，否则使用通用执行器
        if "echo" in self._executors:
            action = "echo"
        elif len(self._executors) > 0:
            action = list(self._executors.keys())[0]
        else:
            # 如果没有任何执行器，创建一个不做任何事的步骤
            action = "noop"

        step = PlanStep(
            step_id=f"step_{uuid.uuid4().hex[:8]}",
            name="main_task",
            action=action,
            params={"task": task},
            description=task,
            expected_result="完成用户任务"
        )
        plan.add_step(step)

        return plan

    # ==================== 执行阶段 ====================

    async def _execute_with_monitoring(
        self,
        plan: ExecutionPlan
    ) -> tuple[list[ExecutionStep], list[ExecutionError], Any]:
        """
        带监控的执行

        Args:
            plan: 执行计划

        Returns:
            (步骤结果列表, 错误列表, 指标)
        """
        step_results: list[ExecutionStep] = []
        errors: list[ExecutionError] = []
        completed_steps: set = set()

        # 创建指标对象
        from .execution_result import ExecutionMetrics
from core.logger import get_logger
logger = get_logger('reflective_agent.reflective_loop')

        metrics = ExecutionMetrics()

        for step in plan.steps:
            # 检查依赖
            if not step.can_execute(completed_steps):
                continue

            step_result = await self._execute_step(step)
            step_results.append(step_result)

            # 更新指标
            metrics.total_steps += 1
            if step_result.status == ExecutionStatus.SUCCESS:
                metrics.completed_steps += 1
                completed_steps.add(step.step_id)
            else:
                metrics.failed_steps += 1

            # 检查是否应该停止
            if step_result.status == ExecutionStatus.FAILED:
                # 记录错误
                error = ExecutionError(
                    error_id=str(uuid.uuid4()),
                    category=ErrorCategory.LOGIC,
                    severity=ErrorSeverity.MEDIUM,
                    message=step_result.error or "Step failed",
                    context={"step_id": step.step_id}
                )
                errors.append(error)

                # 如果步骤不可跳过，停止执行
                if step.priority.value <= 2:
                    break

        metrics.total_duration_ms = sum(
            s.duration_ms for s in step_results
        )

        return step_results, errors, metrics

    async def _execute_step(self, step: PlanStep) -> ExecutionStep:
        """
        执行单个步骤

        Args:
            step: 步骤定义

        Returns:
            步骤执行结果
        """
        result = ExecutionStep(
            step_id=step.step_id,
            name=step.name,
            description=step.description,
            status=ExecutionStatus.RUNNING,
            start_time=datetime.now()
        )

        # 获取执行器
        executor = self._executors.get(step.action)

        if executor is None:
            # 使用默认执行器
            result.status = ExecutionStatus.FAILED
            result.error = f"No executor registered for action: {step.action}"
            result.end_time = datetime.now()
            return result

        # 执行（带超时）
        try:
            exec_result = await asyncio.wait_for(
                executor(step),
                timeout=step.timeout_ms / 1000
            )

            result.status = ExecutionStatus.SUCCESS
            result.result = exec_result

        except asyncio.TimeoutError:
            result.status = ExecutionStatus.TIMEOUT
            result.error = f"Step timeout after {step.timeout_ms}ms"

        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = str(e)

        result.end_time = datetime.now()
        result.duration_ms = (result.end_time - result.start_time).total_seconds() * 1000

        return result

    # ==================== 降级处理 ====================

    async def _execute_fallback(
        self,
        task: str,
        history: list
    ) -> ExecutionResult:
        """
        执行降级方案

        当所有尝试都失败时调用
        """
        result = ExecutionResult(
            task=task,
            status=ExecutionStatus.PARTIAL
        )

        if hasattr(self, "_fallback"):
            try:
                fallback_result = await self._fallback(task, history)
                result.final_result = fallback_result
                result.reflection_notes = "Executed fallback strategy"
            except Exception as e:
                result.mark_failed(f"Fallback failed: {e}")
        else:
            result.mark_failed("No fallback strategy available")

        return result

    # ==================== 统计和辅助 ====================

    def _update_stats(self, result: ExecutionResult):
        """更新统计信息"""
        if result.success:
            self.stats["successful_tasks"] += 1
        else:
            self.stats["failed_tasks"] += 1

        # 计算平均尝试次数
        total = self.stats["total_tasks"]
        if total > 0:
            current_avg = self.stats["average_attempts"]
            new_avg = ((total - 1) * current_avg + result.attempt_number) / total
            self.stats["average_attempts"] = new_avg

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.copy()

    def get_learning_insights(self) -> Dict[str, Any]:
        """
        获取学习洞察

        基于执行历史生成改进建议
        """
        if not self.execution_history:
            return {"message": "No execution history available"}

        insights = {
            "total_tasks": self.stats["total_tasks"],
            "success_rate": (
                self.stats["successful_tasks"] / self.stats["total_tasks"]
                if self.stats["total_tasks"] > 0 else 0
            ),
            "common_errors": [],
            "average_attempts": self.stats["average_attempts"],
            "recommendations": []
        }

        # 分析常见错误
        error_counts: Dict[str, int] = {}
        for result in self.execution_history:
            for error in result.errors:
                category = error.category.value
                error_counts[category] = error_counts.get(category, 0) + 1

        insights["common_errors"] = [
            {"category": k, "count": v}
            for k, v in sorted(error_counts.items(), key=lambda x: -x[1])
        ][:5]

        # 生成建议
        if insights["success_rate"] < 0.7:
            insights["recommendations"].append(
                "考虑增加重试次数或优化执行策略"
            )
        if self.stats["average_attempts"] > 2:
            insights["recommendations"].append(
                "执行通常需要多次尝试，考虑简化任务分解"
            )

        return insights


# ==================== 便捷函数 ====================

def create_reflective_loop(**kwargs) -> ReflectiveAgentLoop:
    """
    创建反思循环的便捷函数

    示例：
    ```python
    loop = create_reflective_loop(
        max_attempts=3,
        reflection_threshold=0.7,
        verbose=True
    )
    ```
    """
    config = ReflectiveLoopConfig(**kwargs)
    return ReflectiveAgentLoop(config)
