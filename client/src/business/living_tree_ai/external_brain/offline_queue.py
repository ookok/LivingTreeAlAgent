"""
OfflineQueue - 离线队列
=====================

当所有通道均失败时，将任务存入本地SQLite队列，
待网络恢复后自动重试。

功能：
1. 任务持久化存储
2. 网络恢复检测
3. 自动重试
4. 手动清空/重试

Author: LivingTreeAI Community
from __future__ import annotations
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import asyncio
import json
import logging
import sqlite3
import uuid
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"      # 待处理
    QUEUED = "queued"       # 已入队
    RETRYING = "retrying"   # 重试中
    COMPLETED = "completed" # 已完成
    FAILED = "failed"       # 失败
    CANCELLED = "cancelled" # 已取消


@dataclass
class OfflineTask:
    """离线任务"""
    task_id: str
    task_name: str
    request_data: Dict[str, Any]
    target_url: str = ""
    method: str = "POST"
    headers: str = ""       # JSON序列化的headers
    status: TaskStatus = TaskStatus.QUEUED
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_error: str = ""
    result_data: str = ""    # JSON序列化的结果

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "request_data": self.request_data,
            "target_url": self.target_url,
            "method": self.method,
            "headers": json.loads(self.headers) if self.headers else {},
            "status": self.status.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_error": self.last_error,
            "result_data": json.loads(self.result_data) if self.result_data else None,
        }

    @classmethod
    def from_row(cls, row: tuple) -> "OfflineTask":
        """从数据库行创建任务"""
        return cls(
            task_id=row[0],
            task_name=row[1],
            request_data=json.loads(row[2]),
            target_url=row[3] or "",
            method=row[4] or "POST",
            headers=row[5] or "",
            status=TaskStatus(row[6]),
            retry_count=row[7],
            max_retries=row[8] or 3,
            created_at=datetime.fromisoformat(row[9]) if row[9] else datetime.now(),
            updated_at=datetime.fromisoformat(row[10]) if row[10] else datetime.now(),
            last_error=row[11] or "",
            result_data=row[12] or "",
        )


class OfflineQueue:
    """
    离线任务队列

    当所有外脑通道均失败时，将任务存入本地SQLite队列，
    待网络恢复后自动重试，或由用户手动触发重试。
    """

    def __init__(self, db_path: str = None):
        """
        初始化离线队列

        Args:
            db_path: 数据库路径，默认使用 ~/.hermes-desktop/offline_queue.db
        """
        if db_path is None:
            home = Path.home()
            data_dir = home / ".hermes-desktop"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "offline_queue.db")

        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

        # 监听器
        self._listeners: List[Callable] = []

        # 初始化数据库
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS offline_tasks (
                    task_id TEXT PRIMARY KEY,
                    task_name TEXT NOT NULL,
                    request_data TEXT NOT NULL,
                    target_url TEXT DEFAULT '',
                    method TEXT DEFAULT 'POST',
                    headers TEXT DEFAULT '',
                    status TEXT DEFAULT 'queued',
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_error TEXT DEFAULT '',
                    result_data TEXT DEFAULT ''
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON offline_tasks(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at ON offline_tasks(created_at)
            """)

            conn.commit()
            conn.close()

            logger.info(f"离线队列数据库已初始化: {self._db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path)
        return self._conn

    async def add_task(
        self,
        task_name: str,
        request_data: Dict[str, Any],
        target_url: str = "",
        method: str = "POST",
        headers: Dict[str, str] = None,
        max_retries: int = 3,
    ) -> str:
        """
        添加任务到离线队列

        Args:
            task_name: 任务名称
            request_data: 请求数据
            target_url: 目标URL
            method: HTTP方法
            headers: 请求头
            max_retries: 最大重试次数

        Returns:
            str: 任务ID
        """
        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        headers_json = json.dumps(headers or {})

        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO offline_tasks
                (task_id, task_name, request_data, target_url, method, headers,
                 status, retry_count, max_retries, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                task_name,
                json.dumps(request_data),
                target_url,
                method,
                headers_json,
                TaskStatus.QUEUED.value,
                0,
                max_retries,
                now,
                now,
            ))
            conn.commit()

        logger.info(f"任务已加入离线队列: {task_id} ({task_name})")
        self._notify_listeners("task_added", {"task_id": task_id, "task_name": task_name})

        return task_id

    async def get_task(self, task_id: str) -> Optional[OfflineTask]:
        """获取任务"""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM offline_tasks WHERE task_id = ?",
                (task_id,)
            )
            row = cursor.fetchone()

        if row:
            return OfflineTask.from_row(row)
        return None

    async def get_pending_tasks(self) -> List[OfflineTask]:
        """获取所有待处理任务"""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM offline_tasks
                WHERE status IN ('queued', 'retrying')
                ORDER BY created_at ASC
            """)
            rows = cursor.fetchall()

        return [OfflineTask.from_row(row) for row in rows]

    async def get_all_tasks(self) -> List[OfflineTask]:
        """获取所有任务"""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM offline_tasks
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()

        return [OfflineTask.from_row(row) for row in rows]

    async def get_queue_count(self) -> int:
        """获取队列中的任务数量"""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM offline_tasks
                WHERE status IN ('queued', 'retrying')
            """)
            result = cursor.fetchone()
            return result[0] if result else 0

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        error: str = None,
        result_data: Any = None,
    ):
        """更新任务状态"""
        now = datetime.now().isoformat()

        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            if error is not None:
                cursor.execute("""
                    UPDATE offline_tasks
                    SET status = ?, updated_at = ?, last_error = ?
                    WHERE task_id = ?
                """, (status.value, now, error, task_id))
            elif result_data is not None:
                cursor.execute("""
                    UPDATE offline_tasks
                    SET status = ?, updated_at = ?, result_data = ?
                    WHERE task_id = ?
                """, (status.value, now, json.dumps(result_data), task_id))
            else:
                cursor.execute("""
                    UPDATE offline_tasks
                    SET status = ?, updated_at = ?
                    WHERE task_id = ?
                """, (status.value, now, task_id))

            conn.commit()

        self._notify_listeners("status_changed", {
            "task_id": task_id,
            "status": status.value,
        })

    async def increment_retry(self, task_id: str) -> int:
        """增加重试计数"""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE offline_tasks
                SET retry_count = retry_count + 1, updated_at = ?, status = ?
                WHERE task_id = ?
            """, (datetime.now().isoformat(), TaskStatus.RETRYING.value, task_id))
            conn.commit()

            cursor.execute(
                "SELECT retry_count FROM offline_tasks WHERE task_id = ?",
                (task_id,)
            )
            result = cursor.fetchone()
            return result[0] if result else 0

    async def delete_task(self, task_id: str):
        """删除任务"""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM offline_tasks WHERE task_id = ?", (task_id,))
            conn.commit()

        logger.info(f"任务已删除: {task_id}")
        self._notify_listeners("task_deleted", {"task_id": task_id})

    async def clear_completed(self):
        """清除已完成的任务"""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM offline_tasks WHERE status = ?",
                (TaskStatus.COMPLETED.value,)
            )
            deleted = cursor.rowcount
            conn.commit()

        logger.info(f"已清除 {deleted} 个已完成任务")
        self._notify_listeners("tasks_cleared", {"count": deleted})

    async def clear_all(self):
        """清空所有任务"""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM offline_tasks")
            deleted = cursor.rowcount
            conn.commit()

        logger.info(f"已清空 {deleted} 个任务")
        self._notify_listeners("all_cleared", {"count": deleted})

    async def retry_task(self, task_id: str) -> bool:
        """
        重试单个任务

        Returns:
            bool: 是否成功（加入重试队列）
        """
        task = await self.get_task(task_id)
        if not task:
            return False

        if task.retry_count >= task.max_retries:
            await self.update_task_status(task_id, TaskStatus.FAILED, "超过最大重试次数")
            return False

        await self.update_task_status(task_id, TaskStatus.RETRYING)
        return True

    def get_stats(self) -> Dict[str, int]:
        """获取队列统计"""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            stats = {}
            for status in TaskStatus:
                cursor.execute(
                    "SELECT COUNT(*) FROM offline_tasks WHERE status = ?",
                    (status.value,)
                )
                result = cursor.fetchone()
                stats[status.value] = result[0] if result else 0

            return stats

    # ==================== 事件监听 ====================

    def subscribe(self, callback: Callable):
        """订阅事件"""
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback)

    def _notify_listeners(self, event: str, data: Any):
        """通知监听器"""
        for listener in self._listeners:
            try:
                listener(event, data)
            except Exception as e:
                logger.error(f"监听器回调错误: {e}")

    # ==================== 上下文管理器 ====================

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None


# 单例实例
_offline_queue: Optional[OfflineQueue] = None


def get_offline_queue() -> OfflineQueue:
    """获取离线队列单例"""
    global _offline_queue
    if _offline_queue is None:
        _offline_queue = OfflineQueue()
    return _offline_queue