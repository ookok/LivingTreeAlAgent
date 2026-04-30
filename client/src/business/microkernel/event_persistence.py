"""
Event Persistence - 事件持久化 + 死信队列 + 事件重放

通过组合（而不是修改）现有 EventBus，添加：
1. 事件持久化（SQLite 存储）
2. 死信队列（失败事件处理）
3. 事件重放（从持久化存储重放事件）

设计理念：
- 不修改现有 EventBus（避免引入 bug）
- 通过包装器（Wrapper）提供增强功能
- 可选启用（通过配置）
"""

import os
import sqlite3
import threading
import time
import traceback
import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

# 延迟导入：避免循环导入
# from client.src.business.plugin_framework.event_bus import EventBus, Event, EventPriority

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# 数据模型
# ──────────────────────────────────────────────────────────────


@dataclass
class PersistedEvent:
    """持久化的事件"""
    id: int = 0  # 数据库 ID
    event_id: str = ""  # Event.id
    event_type: str = ""
    event_data: str = ""  # JSON 字符串
    source: str = ""
    target: str = ""
    priority: int = 1
    timestamp: float = 0.0
    processed: bool = False
    failed: bool = False
    error_message: str = ""
    retry_count: int = 0


@dataclass
class DeadLetter:
    """死信（处理失败的事件）"""
    id: int = 0
    event_id: str = ""
    event_type: str = ""
    error_message: str = ""
    traceback: str = ""
    created_at: float = 0.0
    retry_count: int = 0
    max_retries: int = 3
    status: str = "pending"  # pending | retrying | discarded


# ──────────────────────────────────────────────────────────────
# 事件持久化管理器
# ──────────────────────────────────────────────────────────────


class EventPersistence:
    """
    事件持久化管理器

    将事件保存到 SQLite 数据库，支持：
    - 持久化存储（防止事件丢失）
    - 事件重放（从数据库重放事件）
    - 死信队列（处理失败的事件）

    使用示例：
        persistence = EventPersistence("events.db")
        persistence.init_db()

        # 保存事件
        persistence.save_event(event, processed=False)

        # 标记事件为已处理
        persistence.mark_processed(event.id)

        # 保存死信
        persistence.save_dead_letter(event, error_message="Handler failed")

        # 重放事件
        events = persistence.replay_events(event_type="user_login")
    """

    def __init__(self, db_path: str = "kernel_events.db"):
        self._db_path = db_path
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._logger = logging.getLogger("EventPersistence")

    def init_db(self) -> None:
        """初始化数据库"""
        with self._lock:
            try:
                self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
                cursor = self._conn.cursor()

                # 创建事件表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT UNIQUE NOT NULL,
                        event_type TEXT NOT NULL,
                        event_data TEXT NOT NULL,
                        source TEXT,
                        target TEXT,
                        priority INTEGER DEFAULT 1,
                        timestamp REAL NOT NULL,
                        processed BOOLEAN DEFAULT 0,
                        failed BOOLEAN DEFAULT 0,
                        error_message TEXT,
                        retry_count INTEGER DEFAULT 0,
                        created_at REAL DEFAULT (strftime('%s', 'now'))
                    )
                """)

                # 创建死信表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS dead_letters (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        error_message TEXT,
                        traceback TEXT,
                        created_at REAL NOT NULL,
                        retry_count INTEGER DEFAULT 0,
                        max_retries INTEGER DEFAULT 3,
                        status TEXT DEFAULT 'pending',
                        last_retry_at REAL,
                        last_error TEXT
                    )
                """)

                # 创建索引
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_processed ON events(processed)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_dead_letters_status ON dead_letters(status)")

                self._conn.commit()
                self._logger.info(f"[EventPersistence] Database initialized: {self._db_path}")

            except Exception as e:
                self._logger.error(f"[EventPersistence] Failed to initialize database: {e}")
                self._logger.error(traceback.format_exc())
                raise

    def save_event(self, event: Any, processed: bool = False) -> bool:
        """
        保存事件

        Args:
            event: Event 对象
            processed: 是否已处理

        Returns:
            是否成功保存
        """
        with self._lock:
            if not self._conn:
                self._logger.warning("[EventPersistence] Database not initialized")
                return False

            try:
                import json
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO events
                    (event_id, event_type, event_data, source, target, priority, timestamp, processed, failed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.id,
                    event.type,
                    json.dumps(event.data) if hasattr(event, 'data') else "{}",
                    event.source if hasattr(event, 'source') else "",
                    event.target if hasattr(event, 'target') else "",
                    event.priority.value if hasattr(event, 'priority') else 1,
                    event.timestamp if hasattr(event, 'timestamp') else time.time(),
                    processed,
                    False,
                ))
                self._conn.commit()
                return True

            except Exception as e:
                self._logger.error(f"[EventPersistence] Failed to save event: {e}")
                return False

    def mark_processed(self, event_id: str) -> bool:
        """
        标记事件为已处理

        Args:
            event_id: 事件ID

        Returns:
            是否成功标记
        """
        with self._lock:
            if not self._conn:
                return False

            try:
                cursor = self._conn.cursor()
                cursor.execute("""
                    UPDATE events SET processed = 1 WHERE event_id = ?
                """, (event_id,))
                self._conn.commit()
                return cursor.rowcount > 0

            except Exception as e:
                self._logger.error(f"[EventPersistence] Failed to mark processed: {e}")
                return False

    def mark_failed(self, event_id: str, error_message: str = "") -> bool:
        """
        标记事件为失败

        Args:
            event_id: 事件ID
            error_message: 错误信息

        Returns:
            是否成功标记
        """
        with self._lock:
            if not self._conn:
                return False

            try:
                cursor = self._conn.cursor()
                cursor.execute("""
                    UPDATE events SET failed = 1, error_message = ? WHERE event_id = ?
                """, (error_message, event_id))
                self._conn.commit()
                return cursor.rowcount > 0

            except Exception as e:
                self._logger.error(f"[EventPersistence] Failed to mark failed: {e}")
                return False

    def save_dead_letter(self, event: Any, error_message: str = "", tb: str = "") -> bool:
        """
        保存死信

        Args:
            event: Event 对象
            error_message: 错误信息
            tb: traceback 字符串

        Returns:
            是否成功保存
        """
        with self._lock:
            if not self._conn:
                return False

            try:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT INTO dead_letters
                    (event_id, event_type, error_message, traceback, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    event.id,
                    event.type,
                    error_message,
                    tb,
                    time.time(),
                ))
                self._conn.commit()
                self._logger.warning(f"[EventPersistence] Dead letter saved: {event.type} - {error_message}")
                return True

            except Exception as e:
                self._logger.error(f"[EventPersistence] Failed to save dead letter: {e}")
                return False

    def get_dead_letters(self, status: Optional[str] = None, limit: int = 100) -> List[DeadLetter]:
        """
        获取死信列表

        Args:
            status: 按状态过滤（pending / retrying / discarded）
            limit: 返回数量限制

        Returns:
            死信列表
        """
        with self._lock:
            if not self._conn:
                return []

            try:
                cursor = self._conn.cursor()
                if status:
                    cursor.execute("""
                        SELECT * FROM dead_letters WHERE status = ? ORDER BY created_at DESC LIMIT ?
                    """, (status, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM dead_letters ORDER BY created_at DESC LIMIT ?
                    """, (limit,))

                rows = cursor.fetchall()
                # 注意：这里简化了，实际需要映射列名
                result = []
                for row in rows:
                    result.append(DeadLetter(
                        id=row[0],
                        event_id=row[1],
                        event_type=row[2],
                        error_message=row[3],
                        traceback=row[4],
                        created_at=row[5],
                        retry_count=row[6],
                        max_retries=row[7],
                        status=row[8],
                    ))
                return result

            except Exception as e:
                self._logger.error(f"[EventPersistence] Failed to get dead letters: {e}")
                return []

    def retry_dead_letter(self, dead_letter_id: int) -> bool:
        """
        重试死信

        Args:
            dead_letter_id: 死信ID

        Returns:
            是否成功标记为重试中
        """
        with self._lock:
            if not self._conn:
                return False

            try:
                cursor = self._conn.cursor()
                cursor.execute("""
                    UPDATE dead_letters
                    SET status = 'retrying', last_retry_at = ?, retry_count = retry_count + 1
                    WHERE id = ? AND status = 'pending'
                """, (time.time(), dead_letter_id))
                self._conn.commit()
                return cursor.rowcount > 0

            except Exception as e:
                self._logger.error(f"[EventPersistence] Failed to retry dead letter: {e}")
                return False

    def discard_dead_letter(self, dead_letter_id: int) -> bool:
        """
        丢弃死信（标记为 discarded）

        Args:
            dead_letter_id: 死信ID

        Returns:
            是否成功丢弃
        """
        with self._lock:
            if not self._conn:
                return False

            try:
                cursor = self._conn.cursor()
                cursor.execute("""
                    UPDATE dead_letters SET status = 'discarded' WHERE id = ?
                """, (dead_letter_id,))
                self._conn.commit()
                return cursor.rowcount > 0

            except Exception as e:
                self._logger.error(f"[EventPersistence] Failed to discard dead letter: {e}")
                return False

    def replay_events(self, event_type: Optional[str] = None,
                     start_time: Optional[float] = None,
                     end_time: Optional[float] = None,
                     limit: int = 1000) -> List[PersistedEvent]:
        """
        重放事件（从数据库读取）

        Args:
            event_type: 按事件类型过滤
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制

        Returns:
            持久化事件列表
        """
        with self._lock:
            if not self._conn:
                return []

            try:
                cursor = self._conn.cursor()
                query = "SELECT * FROM events WHERE 1=1"
                params = []

                if event_type:
                    query += " AND event_type = ?"
                    params.append(event_type)

                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time)

                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time)

                query += " ORDER BY timestamp ASC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                result = []
                for row in rows:
                    result.append(PersistedEvent(
                        id=row[0],
                        event_id=row[1],
                        event_type=row[2],
                        event_data=row[3],
                        source=row[4],
                        target=row[5],
                        priority=row[6],
                        timestamp=row[7],
                        processed=bool(row[8]),
                        failed=bool(row[9]),
                        error_message=row[10],
                        retry_count=row[11],
                    ))
                return result

            except Exception as e:
                self._logger.error(f"[EventPersistence] Failed to replay events: {e}")
                return []

    def clear_old_events(self, older_than: float) -> int:
        """
        清理旧事件

        Args:
            older_than: 清理此时间之前的事件（Unix 时间戳）

        Returns:
            清理的事件数
        """
        with self._lock:
            if not self._conn:
                return 0

            try:
                cursor = self._conn.cursor()
                cursor.execute("""
                    DELETE FROM events WHERE timestamp < ? AND processed = 1
                """, (older_than,))
                self._conn.commit()
                return cursor.rowcount

            except Exception as e:
                self._logger.error(f"[EventPersistence] Failed to clear old events: {e}")
                return 0

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            if not self._conn:
                return {}

            try:
                cursor = self._conn.cursor()
                stats = {}

                # 事件统计
                cursor.execute("SELECT COUNT(*) FROM events")
                stats["total_events"] = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM events WHERE processed = 1")
                stats["processed_events"] = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM events WHERE failed = 1")
                stats["failed_events"] = cursor.fetchone()[0]

                # 死信统计
                cursor.execute("SELECT COUNT(*) FROM dead_letters")
                stats["total_dead_letters"] = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM dead_letters WHERE status = 'pending'")
                stats["pending_dead_letters"] = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM dead_letters WHERE status = 'retrying'")
                stats["retrying_dead_letters"] = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM dead_letters WHERE status = 'discarded'")
                stats["discarded_dead_letters"] = cursor.fetchone()[0]

                return stats

            except Exception as e:
                self._logger.error(f"[EventPersistence] Failed to get stats: {e}")
                return {}

    def close(self) -> None:
        """关闭数据库连接"""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
                self._logger.info("[EventPersistence] Database connection closed")


# ──────────────────────────────────────────────────────────────
# 持久化 EventBus 包装器
# ──────────────────────────────────────────────────────────────


class PersistentEventBus:
    """
    持久化 EventBus 包装器

    包装现有 EventBus，添加持久化支持。

    使用示例：
        from client.src.business.plugin_framework.event_bus import get_event_bus

        event_bus = get_event_bus()
        persistent_bus = PersistentEventBus(event_bus, db_path="events.db")
        persistent_bus.init()

        # 发布事件（自动持久化）
        persistent_bus.publish(event)

        # 重放事件
        persistent_bus.replay(event_type="user_login")
    """

    def __init__(self, event_bus: Any, db_path: str = "kernel_events.db"):
        self._event_bus = event_bus
        self._persistence = EventPersistence(db_path)
        self._logger = logging.getLogger("PersistentEventBus")

    def init(self) -> None:
        """初始化"""
        self._persistence.init_db()
        self._logger.info("[PersistentEventBus] Initialized")

    def publish(self, event: Any, persist: bool = True) -> int:
        """
        发布事件（自动持久化）

        Args:
            event: Event 对象
            persist: 是否持久化

        Returns:
            接收事件的订阅者数量
        """
        # 持久化
        if persist:
            self._persistence.save_event(event, processed=False)

        # 发布
        try:
            received = self._event_bus.publish(event)

            # 标记已处理
            if persist:
                self._persistence.mark_processed(event.id)

            return received

        except Exception as e:
            # 标记失败
            if persist:
                self._persistence.mark_failed(event.id, str(e))
                self._persistence.save_dead_letter(event, error_message=str(e), tb=traceback.format_exc())

            self._logger.error(f"[PersistentEventBus] Publish failed: {e}")
            return 0

    def replay(self, event_type: Optional[str] = None,
               callback: Optional[Callable[[Any], None]] = None) -> int:
        """
        重放事件

        Args:
            event_type: 按事件类型过滤
            callback: 自定义回调函数（可选，默认调用原始 handler）

        Returns:
            重放的事件数
        """
        events = self._persistence.replay_events(event_type=event_type)
        count = 0

        for persisted_event in events:
            try:
                # 重建 Event 对象
                from client.src.business.plugin_framework.event_bus import Event
                import json
                event = Event(
                    type=persisted_event.event_type,
                    data=json.loads(persisted_event.event_data),
                    source=persisted_event.source,
                    target=persisted_event.target,
                )

                # 回调或重新发布
                if callback:
                    callback(event)
                else:
                    self._event_bus.publish(event)

                count += 1

            except Exception as e:
                self._logger.error(f"[PersistentEventBus] Replay failed for {persisted_event.event_id}: {e}")

        self._logger.info(f"[PersistentEventBus] Replayed {count} events")
        return count

    def get_persistence(self) -> EventPersistence:
        """获取持久化管理器"""
        return self._persistence

    def close(self) -> None:
        """关闭"""
        self._persistence.close()
        self._logger.info("[PersistentEventBus] Closed")


# ──────────────────────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────────────────────


def create_persistent_event_bus(db_path: str = "kernel_events.db") -> PersistentEventBus:
    """
    创建持久化 EventBus

    Args:
        db_path: 数据库路径

    Returns:
        PersistentEventBus 实例
    """
    from client.src.business.plugin_framework.event_bus import get_event_bus
    event_bus = get_event_bus()
    persistent_bus = PersistentEventBus(event_bus, db_path)
    persistent_bus.init()
    return persistent_bus
