"""
任务分发器 - Task Distributor

核心功能：
1. 接收任务提交
2. 根据负载选择执行节点
3. 分发任务到目标节点
4. 跟踪任务状态
5. 收集任务结果

任务状态机：
PENDING → DISPATCHED → RUNNING → COMPLETED/FAILED
                ↓
              RETRY

使用示例：
```python
distributor = TaskDistributor(node_id="node-001")

# 设置执行器
distributor.set_executor(lambda task: execute_task(task))

# 提交任务
task_id = distributor.submit_task(
    task_type="compute",
    task_data={"input": "data"},
    requirements={"capability": "gpu"}
)

# 查询任务状态
status = distributor.get_task_status(task_id)
print(f"任务状态: {status['state']}")
```
"""

import time
import uuid
import logging
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock

logger = logging.getLogger(__name__)


class TaskState(Enum):
    """任务状态"""
    PENDING = "PENDING"         # 等待分发
    DISPATCHED = "DISPATCHED"   # 已分发
    RUNNING = "RUNNING"        # 执行中
    COMPLETED = "COMPLETED"    # 已完成
    FAILED = "FAILED"          # 失败
    CANCELLED = "CANCELLED"    # 已取消
    RETRY = "RETRY"            # 重试中


@dataclass
class Task:
    """
    任务

    Attributes:
        task_id: 任务ID
        task_type: 任务类型
        task_data: 任务数据
        requirements: 任务要求（capability 等）
        priority: 优先级（1-10，10最高）
        state: 当前状态
        submitter: 提交者节点ID
        executor: 执行者节点ID
        result: 执行结果
        error: 错误信息
        retry_count: 重试次数
        created_at: 创建时间
        started_at: 开始执行时间
        completed_at: 完成时间
    """
    task_id: str
    task_type: str
    task_data: Dict[str, Any]
    requirements: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5

    # 状态
    state: TaskState = TaskState.PENDING
    submitter: str = ""
    executor: str = ""

    # 结果
    result: Any = None
    error: str = ""

    # 重试
    retry_count: int = 0
    max_retries: int = 3

    # 时间戳
    created_at: float = field(default_factory=time.time)
    started_at: float = 0
    completed_at: float = 0

    def is_finished(self) -> bool:
        """是否已结束（完成/失败/取消）"""
        return self.state in (
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        )

    def can_retry(self) -> bool:
        """是否可以重试"""
        return (
            self.retry_count < self.max_retries
            and self.state == TaskState.FAILED
        )


@dataclass
class TaskDistributor:
    """
    任务分发器

    功能：
    1. 任务队列管理
    2. 任务分发逻辑
    3. 状态跟踪
    4. 结果收集
    """

    # 任务过期时间（秒）
    TASK_EXPIRY = 3600.0

    # 最大并发任务数
    MAX_CONCURRENT = 100

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._lock = RLock()

        # 任务存储
        self._tasks: Dict[str, Task] = {}
        self._pending_queue: List[str] = []  # 等待分发的任务ID
        self._running_tasks: Dict[str, str] = {}  # task_id -> executor

        # 执行器（用于本地执行）
        self._local_executor: Optional[Callable] = None

        # 消息发送回调（用于分发到其他节点）
        self.on_dispatch: Optional[Callable[[str, Dict], None]] = None  # (executor, task_data)

        # 回调
        self.on_task_completed: Optional[Callable[[Task], None]] = None
        self.on_task_failed: Optional[Callable[[Task], None]] = None

    def set_local_executor(self, executor: Callable):
        """
        设置本地执行器

        Args:
            executor: 执行函数，签名为 executor(task: Task) -> result
        """
        self._local_executor = executor
        logger.info(f"[{self.node_id}] 本地执行器已设置")

    def submit_task(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        requirements: Dict[str, Any] = None,
        priority: int = 5,
        submitter: str = None,
    ) -> str:
        """
        提交任务

        Args:
            task_type: 任务类型
            task_data: 任务数据
            requirements: 任务要求（如 {"capability": "gpu"}）
            priority: 优先级
            submitter: 提交者节点ID

        Returns:
            task_id: 任务ID
        """
        task_id = f"task-{uuid.uuid4().hex[:12]}"

        task = Task(
            task_id=task_id,
            task_type=task_type,
            task_data=task_data,
            requirements=requirements or {},
            priority=priority,
            submitter=submitter or self.node_id,
        )

        with self._lock:
            self._tasks[task_id] = task
            self._pending_queue.append(task_id)
            # 按优先级排序
            self._pending_queue.sort(
                key=lambda tid: self._tasks[tid].priority,
                reverse=True
            )

        logger.info(
            f"[{self.node_id}] 提交任务: {task_id}, "
            f"类型: {task_type}, 优先级: {priority}"
        )

        return task_id

    def dispatch_task(self, task_id: str, executor: str) -> bool:
        """
        分发任务到指定节点

        Args:
            task_id: 任务ID
            executor: 执行者节点ID

        Returns:
            是否分发成功
        """
        with self._lock:
            if task_id not in self._tasks:
                logger.warning(f"[{self.node_id}] 未知任务: {task_id}")
                return False

            task = self._tasks[task_id]

            if task.state != TaskState.PENDING:
                logger.warning(
                    f"[{self.node_id}] 任务 {task_id} 状态不允许分发: "
                    f"{task.state.value}"
                )
                return False

            # 更新状态
            task.state = TaskState.DISPATCHED
            task.executor = executor
            task.started_at = time.time()

            # 从待分发队列移除
            if task_id in self._pending_queue:
                self._pending_queue.remove(task_id)

            # 记录运行中任务
            self._running_tasks[task_id] = executor

        logger.info(
            f"[{self.node_id}] 分发任务: {task_id} -> {executor}"
        )

        # 触发分发回调
        if self.on_dispatch:
            self.on_dispatch(executor, {
                "task_id": task_id,
                "task_type": task.task_type,
                "task_data": task.task_data,
                "requirements": task.requirements,
                "priority": task.priority,
            })

        return True

    def execute_local_task(self, task_id: str) -> bool:
        """
        在本地执行任务

        Args:
            task_id: 任务ID

        Returns:
            是否执行成功
        """
        if not self._local_executor:
            logger.warning(f"[{self.node_id}] 未设置本地执行器")
            return False

        with self._lock:
            if task_id not in self._tasks:
                return False

            task = self._tasks[task_id]
            task.state = TaskState.RUNNING
            task.executor = self.node_id
            task.started_at = time.time()

            if task_id in self._pending_queue:
                self._pending_queue.remove(task_id)

        logger.info(f"[{self.node_id}] 本地执行任务: {task_id}")

        try:
            result = self._local_executor(task)
            self._complete_task(task_id, result=result)
            return True
        except Exception as e:
            logger.error(f"[{self.node_id}] 任务执行失败: {task_id}: {e}")
            self._fail_task(task_id, error=str(e))
            return False

    def complete_task(self, task_id: str, result: Any = None):
        """
        完成任务（外部调用）

        Args:
            task_id: 任务ID
            result: 执行结果
        """
        self._complete_task(task_id, result)

    def _complete_task(self, task_id: str, result: Any = None):
        """内部：完成任务"""
        with self._lock:
            if task_id not in self._tasks:
                return

            task = self._tasks[task_id]
            task.state = TaskState.COMPLETED
            task.result = result
            task.completed_at = time.time()

            if task_id in self._running_tasks:
                del self._running_tasks[task_id]

        logger.info(f"[{self.node_id}] 任务完成: {task_id}")

        if self.on_task_completed:
            self.on_task_completed(task)

    def fail_task(self, task_id: str, error: str = ""):
        """
        标记任务失败（外部调用）

        Args:
            task_id: 任务ID
            error: 错误信息
        """
        self._fail_task(task_id, error)

    def _fail_task(self, task_id: str, error: str = ""):
        """内部：标记任务失败"""
        with self._lock:
            if task_id not in self._tasks:
                return

            task = self._tasks[task_id]
            task.state = TaskState.FAILED
            task.error = error
            task.retry_count += 1

            if task_id in self._running_tasks:
                del self._running_tasks[task_id]

        logger.error(f"[{self.node_id}] 任务失败: {task_id}, 错误: {error}")

        if self.on_task_failed:
            self.on_task_failed(task)

        # 检查是否需要重试
        if task.can_retry():
            self._retry_task(task_id)

    def _retry_task(self, task_id: str):
        """重试任务"""
        with self._lock:
            if task_id not in self._tasks:
                return

            task = self._tasks[task_id]
            task.state = TaskState.RETRY
            task.completed_at = 0  # 重置完成时间
            self._pending_queue.append(task_id)
            # 优先级提升
            task.priority = min(10, task.priority + 1)

        logger.info(
            f"[{self.node_id}] 任务重试: {task_id}, "
            f"重试次数: {task.retry_count}/{task.max_retries}"
        )

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否取消成功
        """
        with self._lock:
            if task_id not in self._tasks:
                return False

            task = self._tasks[task_id]

            if task.is_finished():
                return False

            task.state = TaskState.CANCELLED
            task.completed_at = time.time()

            if task_id in self._pending_queue:
                self._pending_queue.remove(task_id)
            if task_id in self._running_tasks:
                del self._running_tasks[task_id]

        logger.info(f"[{self.node_id}] 任务取消: {task_id}")
        return True

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态信息
        """
        with self._lock:
            if task_id not in self._tasks:
                return None

            task = self._tasks[task_id]

            return {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "state": task.state.value,
                "executor": task.executor,
                "priority": task.priority,
                "retry_count": task.retry_count,
                "created_at": task.created_at,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
                "result": task.result if task.is_finished() else None,
                "error": task.error if task.state == TaskState.FAILED else None,
            }

    def get_pending_tasks(self) -> List[str]:
        """获取待分发任务列表"""
        with self._lock:
            return list(self._pending_queue)

    def get_running_tasks(self) -> Dict[str, str]:
        """获取运行中任务"""
        with self._lock:
            return dict(self._running_tasks)

    def cleanup_expired(self):
        """清理过期的任务"""
        now = time.time()
        expired = []

        with self._lock:
            for task_id, task in self._tasks.items():
                if task.is_finished():
                    age = now - task.completed_at
                    if age > self.TASK_EXPIRY:
                        expired.append(task_id)

            for task_id in expired:
                del self._tasks[task_id]

        if expired:
            logger.debug(f"[{self.node_id}] 清理过期任务: {len(expired)}")

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        with self._lock:
            total = len(self._tasks)
            pending = len(self._pending_queue)
            running = len(self._running_tasks)
            completed = sum(
                1 for t in self._tasks.values()
                if t.state == TaskState.COMPLETED
            )
            failed = sum(
                1 for t in self._tasks.values()
                if t.state == TaskState.FAILED
            )

            return {
                "node_id": self.node_id,
                "total_tasks": total,
                "pending": pending,
                "running": running,
                "completed": completed,
                "failed": failed,
                "concurrent_limit": self.MAX_CONCURRENT,
            }
