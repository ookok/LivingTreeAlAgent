"""
任务分解系统 - Task Decomposition System

将复杂任务自动分解为可执行的子任务，支持：
- 智能任务分析
- 子任务依赖管理
- 并行/串行执行策略
- 进度追踪
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterator, List, Optional, Dict
from threading import Event
import asyncio

try:
    from core.config.unified_config import get_config as _get_unified_config
    _uconfig_td = _get_unified_config()
    _POLL_SHORT_TD = _uconfig_td.get("delays.polling_short", 0.1)
except Exception:
    _uconfig_td = None
    _POLL_SHORT_TD = 0.1

# ── 枚举定义 ────────────────────────────────────────────────────────────────


class TaskStatus(Enum):
    """子任务状态"""
    PENDING = "pending"      # 待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"        # 失败
    SKIPPED = "skipped"      # 跳过


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class ExecutionStrategy(Enum):
    """执行策略"""
    SEQUENTIAL = "sequential"   # 串行执行
    PARALLEL = "parallel"         # 并行执行
    DAG = "dag"                   # 依赖图执行


# ── 数据模型 ────────────────────────────────────────────────────────────────


@dataclass
class SubTask:
    """
    子任务数据模型

    Attributes:
        task_id: 唯一标识
        title: 任务标题
        description: 详细描述
        status: 执行状态
        priority: 优先级
        depends_on: 依赖的其他任务 ID
        result: 执行结果
        error: 错误信息
        created_at: 创建时间
        started_at: 开始时间
        completed_at: 完成时间
        progress: 进度百分比 (0-100)
    """
    title: str
    description: str = ""
    task_id: str = field(default_factory=lambda: f"subtask_{uuid.uuid4().hex[:8]}")
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    depends_on: List[str] = field(default_factory=list)
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    progress: int = 0

    @property
    def duration(self) -> Optional[float]:
        """计算执行耗时（秒）"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "depends_on": self.depends_on,
            "progress": self.progress,
            "duration": self.duration,
            "error": self.error,
            "result_preview": str(self.result)[:200] if self.result else None,
        }


@dataclass
class TaskDecomposition:
    """
    任务分解结果

    Attributes:
        original_task: 原始任务描述
        subtasks: 子任务列表
        strategy: 执行策略
        estimated_steps: 预估步骤数
        estimated_complexity: 预估复杂度 (1-10)
        created_at: 分解时间
    """
    original_task: str
    subtasks: List[SubTask] = field(default_factory=list)
    strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL
    estimated_steps: int = 0
    estimated_complexity: int = 1
    created_at: float = field(default_factory=time.time)

    @property
    def total_tasks(self) -> int:
        return len(self.subtasks)

    @property
    def completed_tasks(self) -> int:
        return sum(1 for t in self.subtasks if t.status == TaskStatus.COMPLETED)

    @property
    def progress_percent(self) -> float:
        """计算总体进度"""
        if not self.subtasks:
            return 0
        return sum(t.progress for t in self.subtasks) / len(self.subtasks)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "original_task": self.original_task,
            "subtasks": [t.to_dict() for t in self.subtasks],
            "strategy": self.strategy.value,
            "estimated_steps": self.estimated_steps,
            "estimated_complexity": self.estimated_complexity,
            "progress_percent": self.progress_percent,
            "completed_tasks": self.completed_tasks,
            "total_tasks": self.total_tasks,
        }


# ── 回调定义 ────────────────────────────────────────────────────────────────


@dataclass
class TaskDecompositionCallbacks:
    """
    任务分解回调接口

    用于与 UI 层交互，显示分解过程和执行进度
    """
    on_decomposition_start: Optional[Callable[[str], None]] = None
    """开始分解时的回调，参数为原始任务"""

    on_decomposition_complete: Optional[Callable[[TaskDecomposition], None]] = None
    """分解完成时的回调，参数为分解结果"""

    on_subtask_start: Optional[Callable[[SubTask], None]] = None
    """子任务开始执行"""

    on_subtask_progress: Optional[Callable[[SubTask, int], None]] = None
    """子任务进度更新 (task, progress_percent)"""

    on_subtask_complete: Optional[Callable[[SubTask], None]] = None
    """子任务完成"""

    on_subtask_error: Optional[Callable[[SubTask, str], None]] = None
    """子任务出错"""

    on_all_complete: Optional[Callable[[TaskDecomposition], None]] = None
    """所有任务完成"""


# ── 任务分解器 ──────────────────────────────────────────────────────────────


class TaskDecomposer:
    """
    任务分解器

    使用 LLM 分析任务并分解为可执行的子任务
    """

    # 分解提示模板
    DECOMPOSE_PROMPT = """你是一个任务分解专家。请将以下复杂任务分解为多个可执行的子任务。

原始任务: {task}

请分析这个任务并按以下 JSON 格式输出分解结果：
{{
    "strategy": "sequential" | "parallel" | "dag",
    "estimated_complexity": 1-10,
    "subtasks": [
        {{
            "title": "子任务标题（简短）",
            "description": "子任务详细描述",
            "priority": 1-4,
            "depends_on": ["task_id1", "task_id2"]  // 依赖的任务 ID，可为空
        }}
    ]
}}

分解原则：
1. 每个子任务应该是独立的、可执行的
2. 子任务之间如果有依赖关系，用 depends_on 表示
3. 可以并行的任务用 "parallel" 策略
4. 有先后顺序的用 "sequential" 策略
5. 复杂的依赖关系用 "dag" 策略

请直接输出 JSON，不要有其他内容。"""

    def __init__(
        self,
        llm_client: Any = None,
        min_task_length: int = 20,
        max_subtasks: int = 10,
    ):
        """
        初始化任务分解器

        Args:
            llm_client: LLM 客户端（可选，用于智能分解）
            min_task_length: 触发分解的最小任务长度
            max_subtasks: 最大子任务数量
        """
        self.llm_client = llm_client
        self.min_task_length = min_task_length
        self.max_subtasks = max_subtasks

        # 简单任务的快速分解规则
        self._quick_patterns = [
            (r"创建.*文件", [("创建文件", "生成指定的文件内容")]),
            (r"修改.*文件", [("分析文件", "读取并分析目标文件"), ("修改内容", "按要求修改文件")]),
            (r"搜索.*代码", [("搜索代码", "在代码库中搜索相关内容")]),
            (r"写.*测试", [("编写测试", "编写单元测试或集成测试"), ("运行测试", "执行测试验证功能")]),
        ]

    def should_decompose(self, task: str) -> bool:
        """
        判断任务是否需要分解

        Args:
            task: 任务描述

        Returns:
            True 如果需要分解
        """
        # 检查是否包含复杂动词（暗示多步骤）
        # 这些动词优先级高，即使任务较短也需要分解
        high_priority_verbs = [
            "实现", "开发", "构建", "设计", "架构", "搭建",
            "重构", "迁移", "集成", "部署",
        ]

        # 如果包含高优先级动词，直接分解
        if any(verb in task for verb in high_priority_verbs):
            return True

        # 太短的任务不需要分解
        if len(task) < self.min_task_length:
            return False

        # 检查是否包含其他复杂动词
        complex_verbs = [
            "重构", "优化", "迁移", "集成", "部署",
            "分析", "调研", "研究", "比较", "评估",
            "修复", "调试", "排查", "解决",
            "配置", "安装", "设置",
        ]

        return any(verb in task for verb in complex_verbs)

    def decompose(self, task: str) -> TaskDecomposition:
        """
        分解任务

        Args:
            task: 原始任务描述

        Returns:
            TaskDecomposition: 分解结果
        """
        logger.info(f"[TaskDecomposer] 分解任务: {task[:50]}...")

        # 尝试 LLM 智能分解
        if self.llm_client:
            try:
                return self._decompose_with_llm(task)
            except Exception as e:
                logger.info(f"[TaskDecomposer] LLM 分解失败: {e}")

        # 回退到规则分解
        return self._decompose_with_rules(task)

    def decompose_stream(
        self,
        task: str,
        callbacks: TaskDecompositionCallbacks = None,
    ) -> Iterator[TaskDecomposition]:
        """
        流式分解任务，逐步返回进度

        Args:
            task: 原始任务描述
            callbacks: 回调接口

        Yields:
            TaskDecomposition: 分解过程中的状态
        """
        if callbacks and callbacks.on_decomposition_start:
            callbacks.on_decomposition_start(task)

        # 模拟分解过程（实际可集成 LLM 流式输出）
        decomposition = self.decompose(task)

        if callbacks and callbacks.on_decomposition_complete:
            callbacks.on_decomposition_complete(decomposition)

        yield decomposition

    def _decompose_with_llm(self, task: str) -> TaskDecomposition:
        """使用 LLM 分解任务"""
        prompt = self.DECOMPOSE_PROMPT.format(task=task)

        response = self.llm_client.chat([{"role": "user", "content": prompt}])

        # 解析 JSON
        try:
            # 提取 JSON
            text = response if isinstance(response, str) else response.get("content", "")
            json_str = self._extract_json(text)
            data = json.loads(json_str)

            # 构建子任务
            subtasks = []
            for i, item in enumerate(data.get("subtasks", [])):
                task_id = f"step_{i + 1}"
                subtask = SubTask(
                    task_id=task_id,
                    title=item["title"],
                    description=item.get("description", ""),
                    priority=TaskPriority(item.get("priority", 2)),
                    depends_on=item.get("depends_on", []),
                )
                subtasks.append(subtask)

            strategy = ExecutionStrategy(data.get("strategy", "sequential"))
            complexity = data.get("estimated_complexity", 1)

        except (json.JSONDecodeError, KeyError) as e:
            logger.info(f"[TaskDecomposer] 解析 LLM 输出失败: {e}")
            return self._decompose_with_rules(task)

        return TaskDecomposition(
            original_task=task,
            subtasks=subtasks[:self.max_subtasks],
            strategy=strategy,
            estimated_steps=len(subtasks),
            estimated_complexity=complexity,
        )

    def _decompose_with_rules(self, task: str) -> TaskDecomposition:
        """使用规则快速分解简单任务"""
        subtasks = []

        # 简单模式匹配
        for pattern, steps in self._quick_patterns:
            import re
            if re.search(pattern, task):
                for i, (title, desc) in enumerate(steps):
                    subtasks.append(SubTask(
                        task_id=f"step_{i + 1}",
                        title=title,
                        description=desc,
                    ))
                break

        # 如果没有匹配到模式，创建默认步骤
        if not subtasks:
            # 通用分解
            steps = [
                ("理解需求", "分析并理解任务的具体需求"),
                ("制定计划", "规划实现步骤和方法"),
                ("执行任务", "按照计划执行具体操作"),
                ("验证结果", "检查和验证执行结果"),
            ]
            for i, (title, desc) in enumerate(steps):
                subtasks.append(SubTask(
                    task_id=f"step_{i + 1}",
                    title=title,
                    description=desc,
                ))

        return TaskDecomposition(
            original_task=task,
            subtasks=subtasks,
            strategy=ExecutionStrategy.SEQUENTIAL,
            estimated_steps=len(subtasks),
            estimated_complexity=min(len(subtasks), 10),
        )

    def _extract_json(self, text: str) -> str:
        """从文本中提取 JSON"""
        import re

        # 尝试提取 ```json ... ```
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1)

        # 尝试直接解析
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return match.group(0)

        return text


# ── 子任务执行器 ─────────────────────────────────────────────────────────────


class SubTaskExecutor:
    """
    子任务执行器

    负责执行分解后的子任务，支持：
    - 串行执行
    - 并行执行
    - 依赖图执行
    - 进度追踪
    """

    def __init__(
        self,
        task_handler: Callable[[SubTask], Any] = None,
        callbacks: TaskDecompositionCallbacks = None,
    ):
        """
        初始化执行器

        Args:
            task_handler: 任务处理函数，接收 SubTask，返回结果
            callbacks: 回调接口
        """
        self.task_handler = task_handler or self._default_handler
        self.callbacks = callbacks or TaskDecompositionCallbacks()

        # 执行状态
        self._interrupt_event = Event()
        self._running_tasks: Dict[str, SubTask] = {}

    def execute(
        self,
        decomposition: TaskDecomposition,
        task_handler: Callable[[SubTask], Any] = None,
    ) -> TaskDecomposition:
        """
        执行任务分解结果

        Args:
            decomposition: 分解结果
            task_handler: 可选的覆盖处理函数

        Returns:
            TaskDecomposition: 更新后的分解结果
        """
        handler = task_handler or self.task_handler
        strategy = decomposition.strategy

        logger.info(f"[SubTaskExecutor] 开始执行，策略: {strategy.value}")

        if strategy == ExecutionStrategy.PARALLEL:
            self._execute_parallel(decomposition, handler)
        elif strategy == ExecutionStrategy.DAG:
            self._execute_dag(decomposition, handler)
        else:
            self._execute_sequential(decomposition, handler)

        # 触发完成回调
        if self.callbacks.on_all_complete:
            self.callbacks.on_all_complete(decomposition)

        return decomposition

    def execute_stream(
        self,
        decomposition: TaskDecomposition,
        task_handler: Callable[[SubTask], Any] = None,
    ) -> Iterator[TaskDecomposition]:
        """
        流式执行，逐步返回进度

        Yields:
            TaskDecomposition: 每个子任务完成后的状态
        """
        handler = task_handler or self.task_handler
        strategy = decomposition.strategy

        logger.info(f"[SubTaskExecutor] 开始流式执行，策略: {strategy.value}")

        if strategy == ExecutionStrategy.PARALLEL:
            iterator = self._execute_parallel_stream(decomposition, handler)
        elif strategy == ExecutionStrategy.DAG:
            iterator = self._execute_dag_stream(decomposition, handler)
        else:
            iterator = self._execute_sequential_stream(decomposition, handler)

        for state in iterator:
            yield state

    def interrupt(self):
        """中断执行"""
        self._interrupt_event.set()
        logger.info("[SubTaskExecutor] 收到中断信号")

    def _execute_sequential(
        self,
        decomposition: TaskDecomposition,
        handler: Callable[[SubTask], Any],
    ):
        """串行执行"""
        for subtask in decomposition.subtasks:
            if self._interrupt_event.is_set():
                subtask.status = TaskStatus.SKIPPED
                continue

            self._execute_single(subtask, handler)

    def _execute_sequential_stream(
        self,
        decomposition: TaskDecomposition,
        handler: Callable[[SubTask], Any],
    ) -> Iterator[TaskDecomposition]:
        """串行执行（流式）"""
        for subtask in decomposition.subtasks:
            if self._interrupt_event.is_set():
                subtask.status = TaskStatus.SKIPPED
                yield decomposition
                continue

            self._execute_single(subtask, handler)
            yield decomposition

    def _execute_parallel(
        self,
        decomposition: TaskDecomposition,
        handler: Callable[[SubTask], Any],
    ):
        """并行执行"""
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(self._execute_single, subtask, handler): subtask
                for subtask in decomposition.subtasks
            }

            for future in concurrent.futures.as_completed(futures):
                if self._interrupt_event.is_set():
                    break

    def _execute_parallel_stream(
        self,
        decomposition: TaskDecomposition,
        handler: Callable[[SubTask], Any],
    ) -> Iterator[TaskDecomposition]:
        """并行执行（流式，返回当前状态）"""
        import concurrent.futures


        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(self._execute_single, subtask, handler): subtask
                for subtask in decomposition.subtasks
            }

            # 定期返回当前状态
            while futures:
                done = []
                for future in list(futures.keys()):
                    if future.done():
                        done.append(future)

                for future in done:
                    del futures[future]

                yield decomposition

                if not futures:
                    break

                time.sleep(_POLL_SHORT_TD)

    def _execute_dag(
        self,
        decomposition: TaskDecomposition,
        handler: Callable[[SubTask], Any],
    ):
        """依赖图执行"""
        task_map = {t.task_id: t for t in decomposition.subtasks}
        completed = set()

        while len(completed) < len(decomposition.subtasks):
            if self._interrupt_event.is_set():
                break

            made_progress = False

            for subtask in decomposition.subtasks:
                if subtask.task_id in completed:
                    continue

                # 检查依赖是否满足
                deps_satisfied = all(
                    task_map.get(dep_id) and
                    task_map[dep_id].status == TaskStatus.COMPLETED
                    for dep_id in subtask.depends_on
                )

                if deps_satisfied:
                    self._execute_single(subtask, handler)
                    completed.add(subtask.task_id)
                    made_progress = True

            if not made_progress:
                # 死锁检测
                remaining = [t.task_id for t in decomposition.subtasks
                             if t.task_id not in completed]
                logger.info(f"[SubTaskExecutor] 警告: 可能的死锁，剩余任务: {remaining}")
                break

    def _execute_dag_stream(
        self,
        decomposition: TaskDecomposition,
        handler: Callable[[SubTask], Any],
    ) -> Iterator[TaskDecomposition]:
        """依赖图执行（流式）"""
        task_map = {t.task_id: t for t in decomposition.subtasks}
        completed = set()

        while len(completed) < len(decomposition.subtasks):
            if self._interrupt_event.is_set():
                yield decomposition
                break

            made_progress = False

            for subtask in decomposition.subtasks:
                if subtask.task_id in completed:
                    continue

                deps_satisfied = all(
                    task_map.get(dep_id) and
                    task_map[dep_id].status == TaskStatus.COMPLETED
                    for dep_id in subtask.depends_on
                )

                if deps_satisfied:
                    self._execute_single(subtask, handler)
                    completed.add(subtask.task_id)
                    made_progress = True
                    yield decomposition

            if not made_progress:
                break

    def _execute_single(
        self,
        subtask: SubTask,
        handler: Callable[[SubTask], Any],
    ):
        """执行单个子任务"""
        logger.info(f"[SubTaskExecutor] 执行子任务: {subtask.title}")

        # 更新状态
        subtask.status = TaskStatus.RUNNING
        subtask.started_at = time.time()
        subtask.progress = 0

        # 触发开始回调
        if self.callbacks.on_subtask_start:
            self.callbacks.on_subtask_start(subtask)

        # 执行任务（支持带进度的执行）
        try:
            result = handler(subtask)

            # 更新状态
            subtask.result = result
            subtask.status = TaskStatus.COMPLETED
            subtask.progress = 100
            subtask.completed_at = time.time()

            # 触发完成回调
            if self.callbacks.on_subtask_complete:
                self.callbacks.on_subtask_complete(subtask)

            logger.info(f"[SubTaskExecutor] 子任务完成: {subtask.title} (耗时: {subtask.duration:.2f}s)")

        except Exception as e:
            subtask.error = str(e)
            subtask.status = TaskStatus.FAILED
            subtask.completed_at = time.time()

            # 触发错误回调
            if self.callbacks.on_subtask_error:
                self.callbacks.on_subtask_error(subtask, str(e))

            logger.info(f"[SubTaskExecutor] 子任务失败: {subtask.title} - {e}")

    def _default_handler(self, subtask: SubTask) -> Any:
        """默认任务处理器"""
        # 模拟执行
        for i in range(1, 11):
            if self._interrupt_event.is_set():
                break
            time.sleep(_POLL_SHORT_TD)
            subtask.progress = i * 10

            # 触发进度回调
            if self.callbacks.on_subtask_progress:
                self.callbacks.on_subtask_progress(subtask, i * 10)

        return f"Completed: {subtask.title}"


# ── 便捷函数 ────────────────────────────────────────────────────────────────


def decompose_task(
    task: str,
    llm_client: Any = None,
) -> TaskDecomposition:
    """
    便捷函数：分解任务

    Args:
        task: 任务描述
        llm_client: 可选的 LLM 客户端

    Returns:
        TaskDecomposition: 分解结果
    """
    decomposer = TaskDecomposer(llm_client=llm_client)
    return decomposer.decompose(task)


# ── 测试 ─────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    # 测试任务分解
    decomposer = TaskDecomposer()

    test_tasks = [
        "帮我写一个 Python 函数来计算斐波那契数列",
        "实现一个用户认证系统，包括注册、登录、权限管理",
        "优化数据库查询性能",
    ]

    logger.info("=" * 60)
    logger.info("任务分解测试")
    logger.info("=" * 60)

    for task in test_tasks:
        logger.info(f"\n[Original Task] {task}")
        logger.info(f"[Should Decompose] {decomposer.should_decompose(task)}")

        decomposition = decomposer.decompose(task)
        logger.info(f"[Strategy] {decomposition.strategy.value}")
        logger.info(f"[Complexity] {decomposition.estimated_complexity}")
        logger.info(f"[Subtasks] {len(decomposition.subtasks)}")

        for i, subtask in enumerate(decomposition.subtasks, 1):
            logger.info(f"  {i}. [{subtask.priority.name}] {subtask.title}")
            if subtask.depends_on:
                logger.info(f"     依赖: {subtask.depends_on}")

        print()

    # 测试执行
    logger.info("=" * 60)
    logger.info("任务执行测试")
    logger.info("=" * 60)

    executor = SubTaskExecutor()
    test_decomp = decomposer.decompose("实现一个简单的计算器")

    for state in executor.execute_stream(test_decomp):
        logger.info(f"[Progress] {state.progress_percent:.0f}% - "
              f"{state.completed_tasks}/{state.total_tasks}")
