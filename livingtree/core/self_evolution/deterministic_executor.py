"""
DeterministicExecutor - 确定性执行器
提供有状态、可干预的运行时保障

核心功能：
1. 有状态执行追踪
2. 执行快照和回滚
3. 断点设置和调试
4. 可干预的执行流程
5. 确定性执行保障

遵循自我进化原则：
- 记录执行历史，支持反思和学习
- 允许外部干预，支持人工反馈
- 从执行数据中学习优化策略
"""

import json
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger
from enum import Enum
from collections import OrderedDict


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InterventionType(Enum):
    """干预类型"""
    CONTINUE = "continue"
    PAUSE = "pause"
    STEP = "step"
    SKIP = "skip"
    REWIND = "rewind"
    MODIFY = "modify"
    CANCEL = "cancel"


@dataclass
class ExecutionSnapshot:
    """执行快照"""
    snapshot_id: str
    timestamp: float
    step: int
    state: Dict[str, Any]
    context: Dict[str, Any]
    stack_trace: List[str] = field(default_factory=list)


@dataclass
class ExecutionStep:
    """执行步骤"""
    step_id: str
    step_number: int
    operation: str
    args: Dict[str, Any]
    result: Any = None
    error: Optional[Exception] = None
    duration: float = 0.0
    status: str = "pending"


@dataclass
class ExecutionContext:
    """执行上下文"""
    execution_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    steps: List[ExecutionStep] = field(default_factory=list)
    current_step: int = 0
    snapshots: Dict[str, ExecutionSnapshot] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class DeterministicExecutor:
    """
    确定性执行器
    
    提供有状态、可干预的运行时保障：
    - 完整的执行状态追踪
    - 支持断点设置和单步执行
    - 执行快照和回滚能力
    - 允许外部干预执行流程
    
    遵循自我进化原则：
    - 记录执行历史用于反思学习
    - 支持人工干预和反馈
    - 从执行数据中学习优化策略
    """

    def __init__(self):
        self._logger = logger.bind(component="DeterministicExecutor")
        self._executions: Dict[str, ExecutionContext] = {}
        self._breakpoints: Dict[str, List[Callable]] = {}
        self._intervention_queue: List[Dict[str, Any]] = []

    async def create_execution(self, operations: List[Dict[str, Any]]) -> str:
        """
        创建新的执行上下文
        
        Args:
            operations: 操作列表，每个操作包含 type 和 args
            
        Returns:
            执行 ID
        """
        execution_id = f"exec_{int(time.time() * 1000)}_{id(operations)}"
        
        steps = []
        for i, op in enumerate(operations):
            steps.append(ExecutionStep(
                step_id=f"step_{i}",
                step_number=i,
                operation=op.get("type", "unknown"),
                args=op.get("args", {})
            ))

        ctx = ExecutionContext(
            execution_id=execution_id,
            steps=steps,
            state={},
            metadata={"operations_count": len(operations)}
        )
        
        self._executions[execution_id] = ctx
        self._logger.info(f"创建执行上下文: {execution_id}")
        return execution_id

    async def execute(self, execution_id: str, max_steps: int = 100) -> ExecutionContext:
        """
        执行操作序列
        
        Args:
            execution_id: 执行 ID
            max_steps: 最大执行步数
            
        Returns:
            执行上下文
        """
        ctx = self._executions.get(execution_id)
        if not ctx:
            raise ValueError(f"执行上下文不存在: {execution_id}")

        ctx.status = ExecutionStatus.RUNNING
        ctx.started_at = time.time()

        self._logger.info(f"开始执行: {execution_id}")

        try:
            while ctx.current_step < len(ctx.steps) and ctx.current_step < max_steps:
                # 检查干预请求
                intervention = await self._check_intervention(execution_id)
                if intervention:
                    await self._handle_intervention(ctx, intervention)
                    if ctx.status in [ExecutionStatus.CANCELLED, ExecutionStatus.PAUSED]:
                        break

                # 检查断点
                if await self._check_breakpoint(ctx):
                    ctx.status = ExecutionStatus.PAUSED
                    break

                # 执行当前步骤
                await self._execute_step(ctx)

                # 保存快照
                await self._save_snapshot(ctx)

            if ctx.current_step >= len(ctx.steps):
                ctx.status = ExecutionStatus.COMPLETED
                ctx.completed_at = time.time()

        except Exception as e:
            ctx.status = ExecutionStatus.FAILED
            ctx.completed_at = time.time()
            if ctx.steps:
                ctx.steps[ctx.current_step].error = e
            self._logger.error(f"执行失败: {e}")

        return ctx

    async def _execute_step(self, ctx: ExecutionContext):
        """执行单个步骤"""
        step = ctx.steps[ctx.current_step]
        step.status = "running"
        start_time = time.time()

        try:
            # 根据操作类型执行
            operation = step.operation
            args = step.args

            # 模拟执行（实际实现中会调用具体的工具/函数）
            if operation == "tool_call":
                result = await self._execute_tool_call(args)
            elif operation == "thought":
                result = await self._execute_thought(args)
            elif operation == "finish":
                result = await self._execute_finish(args)
            else:
                result = {"status": "unknown_operation"}

            step.result = result
            step.status = "completed"

        except Exception as e:
            step.error = e
            step.status = "failed"
            raise

        step.duration = time.time() - start_time
        ctx.current_step += 1

    async def _execute_tool_call(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具调用"""
        return {
            "tool_name": args.get("tool_name"),
            "args": args.get("args", {}),
            "result": "模拟工具执行结果",
            "timestamp": time.time()
        }

    async def _execute_thought(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """执行思考步骤"""
        return {
            "thought": args.get("thought", ""),
            "timestamp": time.time()
        }

    async def _execute_finish(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """执行结束步骤"""
        return {
            "finish_reason": args.get("finish_reason", "completed"),
            "summary": args.get("summary", ""),
            "timestamp": time.time()
        }

    async def _save_snapshot(self, ctx: ExecutionContext):
        """保存执行快照"""
        snapshot_id = f"snapshot_{ctx.current_step}_{int(time.time() * 1000)}"
        snapshot = ExecutionSnapshot(
            snapshot_id=snapshot_id,
            timestamp=time.time(),
            step=ctx.current_step,
            state=dict(ctx.state),
            context={
                "execution_id": ctx.execution_id,
                "status": ctx.status.value,
                "current_step": ctx.current_step
            },
            stack_trace=[s.step_id for s in ctx.steps[:ctx.current_step]]
        )
        ctx.snapshots[snapshot_id] = snapshot

        # 限制快照数量
        if len(ctx.snapshots) > 100:
            oldest = min(ctx.snapshots.keys(), key=lambda k: ctx.snapshots[k].timestamp)
            del ctx.snapshots[oldest]

    async def _check_intervention(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """检查是否有干预请求"""
        for intervention in list(self._intervention_queue):
            if intervention.get("execution_id") == execution_id:
                self._intervention_queue.remove(intervention)
                return intervention
        return None

    async def _handle_intervention(self, ctx: ExecutionContext, intervention: Dict[str, Any]):
        """处理干预请求"""
        intervention_type = intervention.get("type")

        if intervention_type == InterventionType.CONTINUE.value:
            ctx.status = ExecutionStatus.RUNNING

        elif intervention_type == InterventionType.PAUSE.value:
            ctx.status = ExecutionStatus.PAUSED

        elif intervention_type == InterventionType.STEP.value:
            # 单步执行，执行完当前步骤后暂停
            pass  # 会在下一次循环中暂停

        elif intervention_type == InterventionType.SKIP.value:
            step_idx = intervention.get("step_idx", ctx.current_step)
            if step_idx < len(ctx.steps):
                ctx.steps[step_idx].status = "skipped"
                ctx.current_step = step_idx + 1

        elif intervention_type == InterventionType.REWIND.value:
            snapshot_id = intervention.get("snapshot_id")
            if snapshot_id in ctx.snapshots:
                snapshot = ctx.snapshots[snapshot_id]
                ctx.current_step = snapshot.step
                ctx.state = dict(snapshot.state)
                self._logger.info(f"回滚到快照: {snapshot_id}")

        elif intervention_type == InterventionType.MODIFY.value:
            step_idx = intervention.get("step_idx", ctx.current_step)
            new_args = intervention.get("new_args", {})
            if step_idx < len(ctx.steps):
                ctx.steps[step_idx].args = new_args
                self._logger.info(f"修改步骤参数: step_{step_idx}")

        elif intervention_type == InterventionType.CANCEL.value:
            ctx.status = ExecutionStatus.CANCELLED
            ctx.completed_at = time.time()

    async def _check_breakpoint(self, ctx: ExecutionContext) -> bool:
        """检查是否需要断点"""
        breakpoints = self._breakpoints.get(ctx.execution_id, [])
        for breakpoint in breakpoints:
            if breakpoint(ctx):
                self._logger.info(f"触发断点: step_{ctx.current_step}")
                return True
        return False

    async def add_intervention(self, execution_id: str, intervention_type: str, **kwargs):
        """
        添加干预请求
        
        Args:
            execution_id: 执行 ID
            intervention_type: 干预类型
            kwargs: 额外参数
        """
        self._intervention_queue.append({
            "execution_id": execution_id,
            "type": intervention_type,
            **kwargs
        })
        self._logger.info(f"添加干预: {intervention_type} -> {execution_id}")

    async def add_breakpoint(self, execution_id: str, condition: Callable):
        """
        添加断点
        
        Args:
            execution_id: 执行 ID
            condition: 断点条件函数，返回 True 时触发断点
        """
        if execution_id not in self._breakpoints:
            self._breakpoints[execution_id] = []
        self._breakpoints[execution_id].append(condition)

    async def get_execution_status(self, execution_id: str) -> Optional[ExecutionContext]:
        """获取执行状态"""
        return self._executions.get(execution_id)

    async def rollback_to_snapshot(self, execution_id: str, snapshot_id: str) -> bool:
        """
        回滚到指定快照
        
        Args:
            execution_id: 执行 ID
            snapshot_id: 快照 ID
            
        Returns:
            是否成功回滚
        """
        ctx = self._executions.get(execution_id)
        if not ctx:
            return False

        if snapshot_id not in ctx.snapshots:
            return False

        snapshot = ctx.snapshots[snapshot_id]
        ctx.current_step = snapshot.step
        ctx.state = dict(snapshot.state)
        ctx.status = ExecutionStatus.PAUSED

        # 重置后续步骤的状态
        for i in range(ctx.current_step, len(ctx.steps)):
            ctx.steps[i].status = "pending"
            ctx.steps[i].result = None
            ctx.steps[i].error = None
            ctx.steps[i].duration = 0.0

        self._logger.info(f"回滚到快照: {snapshot_id}")
        return True

    def get_stats(self) -> Dict[str, Any]:
        """获取执行器统计信息"""
        stats = {
            "total_executions": len(self._executions),
            "active_executions": sum(
                1 for ctx in self._executions.values()
                if ctx.status in [ExecutionStatus.RUNNING, ExecutionStatus.PAUSED]
            ),
            "completed_executions": sum(
                1 for ctx in self._executions.values()
                if ctx.status == ExecutionStatus.COMPLETED
            ),
            "failed_executions": sum(
                1 for ctx in self._executions.values()
                if ctx.status == ExecutionStatus.FAILED
            ),
        }
        return stats