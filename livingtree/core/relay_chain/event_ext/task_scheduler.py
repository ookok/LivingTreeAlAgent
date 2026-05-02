"""
任务调度器 - Task Scheduler

基于事件账本的分布式任务调度系统，替代 Redis 分布式锁

核心思路：
1. 任务执行 = 交易
2. task_id 作为 biz_id，确保同一任务只能被执行一次
3. nonce 确保任务的串行执行
4. 任意中继节点都可以派发任务，只要交易上链，其他节点就能执行

对比 Redis 锁：
| 特性 | Redis 锁 | 事件账本调度 |
|------|---------|-------------|
| 可用性 | Redis挂了全系统挂 | 任意中继可派发，P2P |
| 锁粒度 | 单机/集群 | 全网唯一 |
| 状态持久化 | 内存 | 账本持久化 |
| 审计追溯 | 需额外日志 | 天然全网记账 |
| 锁续期 | 需要 | 不需要（链式结构）|

防重放机制：
1. task_id 唯一性：同一 task_id 只能有一个 DISPATCH
2. nonce 连续性：任务执行必须按序
3. prev_hash 链：执行链完整性

任务状态机：
PENDING -> DISPATCHED -> EXECUTING -> COMPLETED/FAILED/CANCELLED
              |
              +-> RETRY -> EXECUTING -> ...

使用示例：
```python
scheduler = TaskScheduler(event_ledger)

# 派发任务
task = scheduler.dispatch_task(
    dispatcher="user_001",
    task_id="order_process_12345",
    executor="worker_001",
    task_type="process_order",
    task_data={"order_id": "12345"}
)

# 执行任务
scheduler.execute_task(
    worker="worker_001",
    task_id="order_process_12345"
)

# 完成/失败
scheduler.complete_task(
    worker="worker_001",
    task_id="order_process_12345",
    result="success",
    output={"processed": 100}
)
```
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable, Any, Tuple
from decimal import Decimal
from enum import Enum
from collections import defaultdict

from .event_transaction import EventTx, OpType, EventTxBuilder
from .event_ledger import EventLedger


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "PENDING"           # 待派发
    DISPATCHED = "DISPATCHED"     # 已派发
    EXECUTING = "EXECUTING"       # 执行中
    COMPLETED = "COMPLETED"       # 已完成
    FAILED = "FAILED"            # 失败
    CANCELLED = "CANCELLED"      # 已取消
    RETRY = "RETRY"             # 重试中


class TaskType(Enum):
    """任务类型"""
    GENERAL = "general"           # 通用任务
    CRON = "cron"                # 定时任务
    DELAYED = "delayed"          # 延迟任务
    WORKFLOW = "workflow"         # 工作流任务


@dataclass
class TaskDefinition:
    """任务定义"""
    task_id: str                  # 任务唯一ID
    task_type: TaskType = TaskType.GENERAL

    # 任务内容
    task_name: str = ""           # 任务名称
    task_data: Dict = field(default_factory=dict)  # 任务参数

    # 执行者
    dispatcher: str = ""          # 派发者
    executor: str = ""            # 指定执行者（可选，空表示任意）

    # 时间控制
    dispatch_at: float = 0       # 派发时间
    execute_before: float = 0     # 最晚执行时间
    retry_count: int = 0          # 重试次数
    max_retries: int = 3          # 最大重试次数

    # 依赖
    depends_on: List[str] = field(default_factory=list)  # 依赖的任务ID

    # 元数据
    metadata: Dict = field(default_factory=dict)


@dataclass
class TaskExecution:
    """任务执行记录"""
    task_id: str
    task_def: TaskDefinition

    # 执行状态
    status: TaskStatus = TaskStatus.PENDING

    # 交易记录
    dispatch_tx: Optional[EventTx] = None
    execute_tx: Optional[EventTx] = None
    complete_tx: Optional[EventTx] = None

    # 执行信息
    dispatched_at: float = 0
    executing_at: float = 0
    completed_at: float = 0

    # 结果
    result: str = ""              # success/failed/cancelled
    output: Dict = field(default_factory=dict)
    error: str = ""

    @property
    def duration(self) -> float:
        """执行耗时"""
        if self.executing_at and self.completed_at:
            return self.completed_at - self.executing_at
        return 0


class TaskScheduler:
    """
    任务调度器

    基于事件账本的分布式任务调度

    核心方法：
    - dispatch_task: 派发任务
    - claim_task: 认领任务
    - complete_task: 完成执行
    - cancel_task: 取消任务
    - retry_task: 重试任务
    - get_task_status: 查询状态
    - get_pending_tasks: 获取待执行任务
    """

    def __init__(
        self,
        ledger: EventLedger,
        relay_id: Optional[str] = None,
        default_max_retries: int = 3
    ):
        """
        初始化任务调度器

        Args:
            ledger: 事件账本
            relay_id: 当前中继ID
            default_max_retries: 默认最大重试次数
        """
        self.ledger = ledger
        self.relay_id = relay_id or "relay_default"
        self.default_max_retries = default_max_retries

        # 内存缓存
        self._task_cache: Dict[str, TaskExecution] = {}
        self._lock = threading.RLock()

        # 回调
        self.on_task_dispatched: Optional[Callable] = None
        self.on_task_executed: Optional[Callable] = None
        self.on_task_completed: Optional[Callable] = None
        self.on_task_failed: Optional[Callable] = None

        # 预加载已有任务
        self._load_existing_tasks()

    def _load_existing_tasks(self):
        """加载已存在的任务"""
        # 扫描所有 TASK_* 类型交易
        for tx in self.ledger.txs.values():
            if tx.op_type in (
                OpType.TASK_DISPATCH,
                OpType.TASK_EXECUTE,
                OpType.TASK_COMPLETE,
                OpType.TASK_CANCEL
            ):
                if tx.biz_id and tx.biz_id not in self._task_cache:
                    self._task_cache[tx.biz_id] = TaskExecution(
                        task_id=tx.biz_id,
                        task_def=TaskDefinition(
                            task_id=tx.biz_id,
                            task_type=TaskType.GENERAL,
                            dispatcher=tx.user_id,
                            task_data=tx.get_metadata().get("task_params", {}),
                        )
                    )

    # ───────────────────────────────────────────────────────────
    # 任务派发
    # ───────────────────────────────────────────────────────────

    def dispatch_task(
        self,
        dispatcher: str,
        task_id: str,
        task_type: TaskType = TaskType.GENERAL,
        task_name: str = "",
        task_data: Optional[Dict] = None,
        executor: str = "",
        execute_before: float = 0,
        max_retries: Optional[int] = None,
        depends_on: Optional[List[str]] = None,
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """
        派发任务

        Args:
            dispatcher: 派发者ID
            task_id: 任务唯一ID（biz_id，用于防重放）
            task_type: 任务类型
            task_name: 任务名称
            task_data: 任务参数
            executor: 指定执行者（可选）
            execute_before: 最晚执行时间
            max_retries: 最大重试次数
            depends_on: 依赖的任务ID

        Returns:
            (success, message, tx)
        """
        with self._lock:
            # 1. 检查任务是否已存在
            if task_id in self._task_cache:
                existing = self._task_cache[task_id]
                if existing.status != TaskStatus.FAILED:
                    return False, f"任务{task_id}已存在", None

            # 2. 获取用户状态
            nonce = self.ledger.get_nonce(dispatcher)
            prev_hash = self.ledger.get_prev_hash(dispatcher)

            # 3. 构建任务派发交易
            task_def = TaskDefinition(
                task_id=task_id,
                task_type=task_type,
                task_name=task_name,
                task_data=task_data or {},
                dispatcher=dispatcher,
                executor=executor,
                execute_before=execute_before,
                max_retries=max_retries or self.default_max_retries,
                depends_on=depends_on or [],
            )

            tx = EventTxBuilder.build_task_dispatch(
                user_id=dispatcher,
                task_id=task_id,
                nonce=nonce,
                prev_tx_hash=prev_hash,
                executor=executor,
                task_type=task_type.value,
                task_data=task_def.task_data,
                relay_id=self.relay_id,
            )

            # 4. 提交账本
            ok, msg = self.ledger.add_tx(tx)
            if not ok:
                return False, f"账本提交失败: {msg}", None

            # 5. 更新缓存
            task_exec = TaskExecution(
                task_id=task_id,
                task_def=task_def,
                status=TaskStatus.DISPATCHED,
                dispatch_tx=tx,
                dispatched_at=time.time(),
            )
            self._task_cache[task_id] = task_exec

            # 6. 触发回调
            if self.on_task_dispatched:
                try:
                    self.on_task_dispatched(task_exec)
                except Exception:
                    pass  # 忽略回调异常

            return True, "任务已派发", tx

    def claim_task(
        self,
        worker: str,
        task_id: str,
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """
        认领任务（工作节点主动拉取）

        Args:
            worker: 工作节点ID
            task_id: 任务ID

        Returns:
            (success, message, tx)
        """
        with self._lock:
            # 1. 检查任务是否存在
            if task_id not in self._task_cache:
                return False, f"任务{task_id}不存在", None

            task_exec = self._task_cache[task_id]

            # 2. 检查任务状态
            if task_exec.status not in (TaskStatus.DISPATCHED, TaskStatus.RETRY):
                return False, f"任务状态不允许认领: {task_exec.status.value}", None

            # 3. 检查执行者限制
            if task_exec.task_def.executor and task_exec.task_def.executor != worker:
                return False, f"任务指定了执行者: {task_exec.task_def.executor}", None

            # 4. 构建执行交易
            nonce = self.ledger.get_nonce(worker)
            prev_hash = self.ledger.get_prev_hash(worker)

            tx = EventTxBuilder.build_task_execute(
                user_id=worker,
                task_id=task_id,
                nonce=nonce,
                prev_tx_hash=prev_hash,
                relay_id=self.relay_id,
            )

            # 5. 提交账本
            ok, msg = self.ledger.add_tx(tx)
            if not ok:
                return False, f"账本提交失败: {msg}", None

            # 6. 更新缓存
            task_exec.status = TaskStatus.EXECUTING
            task_exec.execute_tx = tx
            task_exec.executing_at = time.time()

            return True, "任务已认领", tx

    # ───────────────────────────────────────────────────────────
    # 任务执行完成
    # ───────────────────────────────────────────────────────────

    def complete_task(
        self,
        worker: str,
        task_id: str,
        result: str = "success",
        output: Optional[Dict] = None,
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """
        完成任务

        Args:
            worker: 执行者ID
            task_id: 任务ID
            result: 结果（success/failed）
            output: 输出数据

        Returns:
            (success, message, tx)
        """
        with self._lock:
            # 1. 检查任务
            if task_id not in self._task_cache:
                return False, f"任务{task_id}不存在", None

            task_exec = self._task_cache[task_id]

            # 2. 检查状态
            if task_exec.status != TaskStatus.EXECUTING:
                return False, f"任务状态不允许完成: {task_exec.status.value}", None

            # 3. 构建完成交易
            nonce = self.ledger.get_nonce(worker)
            prev_hash = self.ledger.get_prev_hash(worker)

            tx = EventTxBuilder.build_task_complete(
                user_id=worker,
                task_id=task_id,
                nonce=nonce,
                prev_tx_hash=prev_hash,
                result=result,
                output=output,
                relay_id=self.relay_id,
            )

            # 4. 提交账本
            ok, msg = self.ledger.add_tx(tx)
            if not ok:
                return False, f"账本提交失败: {msg}", None

            # 5. 更新缓存
            task_exec.status = TaskStatus.COMPLETED if result == "success" else TaskStatus.FAILED
            task_exec.complete_tx = tx
            task_exec.completed_at = time.time()
            task_exec.result = result
            task_exec.output = output or {}

            # 6. 触发回调
            if result == "success" and self.on_task_completed:
                try:
                    self.on_task_completed(task_exec)
                except Exception:
                    pass
            elif result == "failed" and self.on_task_failed:
                try:
                    self.on_task_failed(task_exec)
                except Exception:
                    pass

            return True, "任务已完成", tx

    def cancel_task(
        self,
        operator: str,
        task_id: str,
        reason: str = "cancelled",
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """
        取消任务

        Args:
            operator: 操作者
            task_id: 任务ID
            reason: 取消原因

        Returns:
            (success, message, tx)
        """
        with self._lock:
            if task_id not in self._task_cache:
                return False, f"任务{task_id}不存在", None

            task_exec = self._task_cache[task_id]

            if task_exec.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
                return False, f"任务已结束，无法取消", None

            # 构建取消交易
            nonce = self.ledger.get_nonce(operator)
            prev_hash = self.ledger.get_prev_hash(operator)

            tx = EventTxBuilder.build_task_cancel(
                user_id=operator,
                task_id=task_id,
                nonce=nonce,
                prev_tx_hash=prev_hash,
                reason=reason,
                relay_id=self.relay_id,
            )

            ok, msg = self.ledger.add_tx(tx)
            if not ok:
                return False, f"账本提交失败: {msg}", None

            task_exec.status = TaskStatus.CANCELLED
            task_exec.completed_at = time.time()
            task_exec.error = reason

            return True, "任务已取消", tx

    def retry_task(
        self,
        operator: str,
        task_id: str,
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """
        重试任务

        Args:
            operator: 操作者
            task_id: 任务ID

        Returns:
            (success, message, tx)
        """
        with self._lock:
            if task_id not in self._task_cache:
                return False, f"任务{task_id}不存在", None

            task_exec = self._task_cache[task_id]

            if task_exec.status != TaskStatus.FAILED:
                return False, f"任务状态不允许重试", None

            if task_exec.task_def.retry_count >= task_exec.task_def.max_retries:
                return False, f"已达最大重试次数", None

            # 重新派发
            return self.dispatch_task(
                dispatcher=operator,
                task_id=f"{task_id}_retry_{task_exec.task_def.retry_count + 1}",
                task_type=task_exec.task_def.task_type,
                task_name=task_exec.task_def.task_name,
                task_data=task_exec.task_def.task_data,
                executor=task_exec.task_def.executor,
                max_retries=task_exec.task_def.max_retries,
            )

    # ───────────────────────────────────────────────────────────
    # 任务查询
    # ───────────────────────────────────────────────────────────

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        if task_id in self._task_cache:
            return self._task_cache[task_id].status
        return None

    def get_task_execution(self, task_id: str) -> Optional[TaskExecution]:
        """获取任务执行记录"""
        return self._task_cache.get(task_id)

    def get_pending_tasks(
        self,
        worker: Optional[str] = None,
        limit: int = 100,
    ) -> List[TaskExecution]:
        """
        获取待执行任务

        Args:
            worker: 限定工作节点（可选）
            limit: 返回数量

        Returns:
            待执行任务列表
        """
        pending = []

        for task_id, task_exec in self._task_cache.items():
            if task_exec.status not in (TaskStatus.DISPATCHED, TaskStatus.RETRY):
                continue

            # 检查执行者限制
            if worker and task_exec.task_def.executor:
                if task_exec.task_def.executor != worker:
                    continue

            # 检查执行时间
            if task_exec.task_def.execute_before:
                if time.time() > task_exec.task_def.execute_before:
                    continue

            pending.append(task_exec)

            if len(pending) >= limit:
                break

        return pending

    def get_worker_tasks(
        self,
        worker: str,
        status: Optional[TaskStatus] = None,
        limit: int = 100,
    ) -> List[TaskExecution]:
        """获取工作节点的任务"""
        tasks = []

        for task_exec in self._task_cache.values():
            # 检查执行者
            if task_exec.task_def.executor == worker:
                if status and task_exec.status != status:
                    continue
                tasks.append(task_exec)

                if len(tasks) >= limit:
                    break

        return tasks

    def get_task_history(self, task_id: str) -> List[EventTx]:
        """获取任务的所有交易历史"""
        return self.ledger.get_biz_txs(task_id)

    # ───────────────────────────────────────────────────────────
    # 统计
    # ───────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """获取调度统计"""
        stats = defaultdict(int)

        for task_exec in self._task_cache.values():
            stats[task_exec.status.value] += 1

        return dict(stats)

    def get_worker_stats(self, worker: str) -> Dict[str, Any]:
        """获取工作节点统计"""
        stats = defaultdict(int)

        for task_exec in self._task_cache.values():
            if task_exec.task_def.executor == worker:
                stats[task_exec.status.value] += 1

        return dict(stats)