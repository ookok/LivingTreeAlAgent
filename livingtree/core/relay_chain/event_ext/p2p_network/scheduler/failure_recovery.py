"""
故障恢复 - Failure Recovery

核心功能：
1. 故障检测（基于心跳超时）
2. 故障节点的任务重新分配
3. 数据备份与恢复
4. 协调者故障处理

使用示例：
```python
recovery = FailureRecovery(node_id="node-001")

# 设置任务分发器
recovery.set_task_distributor(distributor)

# 设置选举模块
recovery.set_election(election)

# 节点故障时调用
recovery.on_node_failed("node-002")

# 协调者故障时调用
recovery.on_coordinator_failed()
```
"""

import time
import logging
from typing import Dict, Any, Optional, Set, Callable, List
from dataclasses import dataclass, field
from threading import RLock

logger = logging.getLogger(__name__)


@dataclass
class FailureRecord:
    """故障记录"""
    node_id: str
    failed_at: float = field(default_factory=time.time)
    reason: str = ""
    tasks_assigned: List[str] = field(default_factory=list)
    recovered_at: float = 0


class FailureRecovery:
    """
    故障恢复机制

    功能：
    1. 跟踪节点故障
    2. 重新分配失败任务
    3. 协调者故障时触发选举
    4. 故障节点恢复后重新加入
    """

    # 故障阈值（连续 N 次心跳超时则判定为故障）
    FAILURE_THRESHOLD = 3

    # 节点恢复时间
    RECOVERY_TIMEOUT = 300.0  # 5分钟

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._lock = RLock()

        # 故障记录
        self._failure_records: Dict[str, FailureRecord] = {}

        # 心跳计数
        self._heartbeat_counts: Dict[str, int] = {}  # node_id -> 连续失败次数

        # 依赖模块
        self._task_distributor = None
        self._election = None
        self._load_balancer = None

        # 回调
        self.on_node_failed: Optional[Callable[[str], None]] = None
        self.on_node_recovered: Optional[Callable[[str], None]] = None
        self.on_tasks_redistributed: Optional[Callable[[str, List], None]] = None

    def set_task_distributor(self, distributor):
        """设置任务分发器"""
        self._task_distributor = distributor

    def set_election(self, election):
        """设置选举模块"""
        self._election = election

    def set_load_balancer(self, load_balancer):
        """设置负载均衡器"""
        self._load_balancer = load_balancer

    def record_heartbeat_success(self, node_id: str):
        """
        记录心跳成功

        Args:
            node_id: 节点ID
        """
        with self._lock:
            if node_id in self._heartbeat_counts:
                del self._heartbeat_counts[node_id]

            # 检查是否从故障恢复
            if node_id in self._failure_records:
                record = self._failure_records[node_id]
                if record.recovered_at == 0:
                    record.recovered_at = time.time()
                    logger.info(f"[{self.node_id}] 节点恢复: {node_id}")

                    if self.on_node_recovered:
                        self.on_node_recovered(node_id)

    def record_heartbeat_failure(self, node_id: str):
        """
        记录心跳失败

        Args:
            node_id: 节点ID

        Returns:
            True 如果节点被判定为故障
        """
        with self._lock:
            count = self._heartbeat_counts.get(node_id, 0) + 1
            self._heartbeat_counts[node_id] = count

            if count >= self.FAILURE_THRESHOLD:
                self._handle_node_failure(node_id, "heartbeat_timeout")
                return True

        return False

    def _handle_node_failure(self, node_id: str, reason: str):
        """处理节点故障"""
        with self._lock:
            if node_id in self._failure_records:
                record = self._failure_records[node_id]
                if record.recovered_at == 0:
                    # 节点已经在故障状态
                    return

            # 获取该节点负责的任务
            tasks = []
            if self._task_distributor:
                running = self._task_distributor.get_running_tasks()
                tasks = [
                    tid for tid, executor in running.items()
                    if executor == node_id
                ]

            record = FailureRecord(
                node_id=node_id,
                reason=reason,
                tasks_assigned=tasks,
            )
            self._failure_records[node_id] = record

            # 清除心跳计数
            if node_id in self._heartbeat_counts:
                del self._heartbeat_counts[node_id]

        logger.warning(
            f"[{self.node_id}] 🚨 节点故障: {node_id}, 原因: {reason}, "
            f"任务数: {len(tasks)}"
        )

        # 触发回调
        if self.on_node_failed:
            self.on_node_failed(node_id)

        # 重新分配任务
        if tasks:
            self._redistribute_tasks(node_id, tasks)

    def _redistribute_tasks(self, failed_node: str, task_ids: List[str]):
        """重新分配失败的任务"""
        if not self._task_distributor:
            return

        redistributed = []

        for task_id in task_ids:
            # 获取新执行者
            if self._load_balancer:
                best = self._load_balancer.select_best_node()
                if best and best["node_id"] != failed_node:
                    success = self._task_distributor.dispatch_task(
                        task_id, best["node_id"]
                    )
                    if success:
                        redistributed.append(task_id)
                        logger.info(
                            f"[{self.node_id}] 任务重新分配: {task_id} -> {best['node_id']}"
                        )
                        continue

            # 如果负载均衡器没有可用节点，放回待分发队列
            self._task_distributor.cancel_task(task_id)
            new_task_id = self._task_distributor.submit_task(
                task_type="retry",
                task_data={"original_task_id": task_id},
                priority=10,  # 最高优先级
                submitter=self.node_id,
            )
            redistributed.append(f"{task_id}->{new_task_id}")
            logger.info(
                f"[{self.node_id}] 任务重新提交: {task_id} -> 新任务 {new_task_id}"
            )

        if redistributed:
            if self.on_tasks_redistributed:
                self.on_tasks_redistributed(failed_node, redistributed)

    def on_coordinator_failed(self):
        """协调者故障处理"""
        logger.warning(f"[{self.node_id}] ⚠️ 协调者故障，触发选举")

        # 触发选举
        if self._election:
            self._election.force_election()

    def mark_node_dead(self, node_id: str, reason: str = ""):
        """
        标记节点为死亡（主动调用）

        Args:
            node_id: 节点ID
            reason: 原因
        """
        self._handle_node_failure(node_id, reason)

    def mark_node_alive(self, node_id: str):
        """
        标记节点为存活（恢复）

        Args:
            node_id: 节点ID
        """
        with self._lock:
            if node_id in self._failure_records:
                record = self._failure_records[node_id]
                if record.recovered_at == 0:
                    record.recovered_at = time.time()
                    logger.info(f"[{self.node_id}] 节点恢复: {node_id}")

                    if self.on_node_recovered:
                        self.on_node_recovered(node_id)

        # 清除心跳计数
        with self._lock:
            if node_id in self._heartbeat_counts:
                del self._heartbeat_counts[node_id]

    def get_failed_nodes(self) -> List[str]:
        """获取故障节点列表"""
        with self._lock:
            return [
                node_id
                for node_id, record in self._failure_records.items()
                if record.recovered_at == 0
            ]

    def get_recovered_nodes(self) -> List[str]:
        """获取已恢复节点列表"""
        with self._lock:
            return [
                node_id
                for node_id, record in self._failure_records.items()
                if record.recovered_at > 0
            ]

    def get_failure_history(self, node_id: str = None) -> List[Dict[str, Any]]:
        """
        获取故障历史

        Args:
            node_id: 节点ID，如果为 None 则返回所有

        Returns:
            故障记录列表
        """
        with self._lock:
            records = self._failure_records.values()

            if node_id:
                records = [r for r in records if r.node_id == node_id]

            return [
                {
                    "node_id": r.node_id,
                    "failed_at": r.failed_at,
                    "reason": r.reason,
                    "tasks_count": len(r.tasks_assigned),
                    "recovered_at": r.recovered_at,
                    "downtime": (
                        r.recovered_at - r.failed_at
                        if r.recovered_at > 0 else
                        time.time() - r.failed_at
                    ),
                }
                for r in records
            ]

    def cleanup_old_records(self, max_age: float = 3600.0):
        """
        清理旧故障记录

        Args:
            max_age: 最大保留时间（秒）
        """
        now = time.time()
        to_remove = []

        with self._lock:
            for node_id, record in self._failure_records.items():
                if record.recovered_at > 0:
                    age = now - record.recovered_at
                else:
                    age = now - record.failed_at

                if age > max_age:
                    to_remove.append(node_id)

            for node_id in to_remove:
                del self._failure_records[node_id]

        if to_remove:
            logger.debug(
                f"[{self.node_id}] 清理故障记录: {len(to_remove)}"
            )

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        with self._lock:
            failed = self.get_failed_nodes()
            recovered = self.get_recovered_nodes()

            return {
                "node_id": self.node_id,
                "failed_nodes": failed,
                "recovered_nodes": recovered,
                "total_failures": len(self._failure_records),
                "pending_heartbeats": dict(self._heartbeat_counts),
            }
