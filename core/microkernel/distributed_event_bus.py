"""
Distributed EventBus - 分布式事件总线

支持跨进程/跨机器事件通信，基于 Redis Pub/Sub。
同时支持事件溯源（Event Sourcing）：事件持久化到 Redis Stream。

架构：
┌─────────────┐     publish     ┌─────────────┐
│  Local      │ ────────────> │  Redis      │
│  EventBus   │                 │  Pub/Sub    │
└─────────────┘                 └─────────────┘
      │                              │
      │ subscribe                   │ publish
      v                              v
┌─────────────┐     callback    ┌─────────────┐
│  Distributed│ <──────────── │  Local      │
│  Listener   │                 │  EventBus   │
└─────────────┘                 └─────────────┘

事件溯源：
  事件 → Redis Stream → 持久化 → 可重放
"""

import asyncio
import json
import logging
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses_json import dataclass_json

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 分布式事件
# ─────────────────────────────────────────────────────────────

@dataclass_json
@dataclass
class DistributedEvent:
    """
    分布式事件（可序列化）

    比本地事件多了：
    - event_id: 全局唯一 ID
    - source_node: 来源节点 ID
    - timestamp: 时间戳（秒）
    - ttl: 存活时间（秒，0 表示永久）
    """
    event_type: str
    payload: Dict[str, Any]
    event_id: str = ""
    source_node: str = ""
    timestamp: float = 0.0
    ttl: int = 0

    def __post_init__(self):
        if not self.event_id:
            self.event_id = str(uuid.uuid4())
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def is_expired(self) -> bool:
        """检查事件是否过期"""
        if self.ttl <= 0:
            return False
        return (time.time() - self.timestamp) > self.ttl

    def to_json(self) -> str:
        """序列化为 JSON"""
        return json.dumps({
            "event_type": self.event_type,
            "payload": self.payload,
            "event_id": self.event_id,
            "source_node": self.source_node,
            "timestamp": self.timestamp,
            "ttl": self.ttl,
        })

    @classmethod
    def from_json(cls, json_str: str) -> "DistributedEvent":
        """从 JSON 反序列化"""
        data = json.loads(json_str)
        return cls(
            event_type=data["event_type"],
            payload=data["payload"],
            event_id=data.get("event_id", ""),
            source_node=data.get("source_node", ""),
            timestamp=data.get("timestamp", 0.0),
            ttl=data.get("ttl", 0),
        )


# ─────────────────────────────────────────────────────────────
# Redis 连接管理
# ─────────────────────────────────────────────────────────────

class RedisConfig:
    """Redis 配置"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        socket_timeout: float = 5.0,
        retry_on_timeout: bool = True,
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.socket_timeout = socket_timeout
        self.retry_on_timeout = retry_on_timeout

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "password": self.password,
            "socket_timeout": self.socket_timeout,
            "retry_on_timeout": self.retry_on_timeout,
        }


class RedisConnectionManager:
    """
    Redis 连接管理器

    管理 Redis 连接池，支持自动重连。
    """

    def __init__(self, config: RedisConfig):
        self._config = config
        self._pool = None
        self._lock = threading.RLock()
        self._connected = False

    def connect(self) -> bool:
        """建立连接"""
        try:
            import redis

            self._pool = redis.ConnectionPool(
                **self._config.to_dict(),
            )
            # 测试连接
            client = redis.Redis(connection_pool=self._pool)
            client.ping()

            self._connected = True
            logger.info(
                f"[Redis] Connected to {self._config.host}:{self._config.port}"
            )
            return True

        except ImportError:
            logger.error("[Redis] redis-py not installed. Run: pip install redis")
            return False
        except Exception as e:
            logger.error(f"[Redis] Connection failed: {e}")
            return False

    def get_client(self):
        """获取 Redis 客户端"""
        if not self._connected:
            if not self.connect():
                return None

        import redis
        return redis.Redis(connection_pool=self._pool)

    def is_connected(self) -> bool:
        return self._connected

    def disconnect(self) -> None:
        """断开连接"""
        if self._pool:
            self._pool.disconnect()
            self._connected = False
            logger.info("[Redis] Disconnected")


# ─────────────────────────────────────────────────────────────
# 分布式事件总线
# ─────────────────────────────────────────────────────────────

class DistributedEventBus:
    """
    分布式事件总线

    功能：
    1. 跨进程事件发布/订阅（基于 Redis Pub/Sub）
    2. 事件溯源（基于 Redis Stream）
    3. 事件分区（按 event_type 分区）
    4. 节点发现（注册节点心跳）
    """

    # Redis key 前缀
    KEY_PREFIX = "ltai:eventbus:"
    KEY_PUBSUB = KEY_PREFIX + "pubsub:"      # Pub/Sub channel
    KEY_STREAM = KEY_PREFIX + "stream:"       # Event Sourcing stream
    KEY_NODES = KEY_PREFIX + "nodes"          # 在线节点集合
    KEY_EVENTS = KEY_PREFIX + "events:"       # 事件计数

    def __init__(
        self,
        node_id: Optional[str] = None,
        redis_config: Optional[RedisConfig] = None,
    ):
        """
        初始化分布式事件总线

        Args:
            node_id: 节点 ID（不提供则自动生成）
            redis_config: Redis 配置
        """
        self._node_id = node_id or f"node:{uuid.uuid4().hex[:8]}"
        self._redis_config = redis_config or RedisConfig()
        self._redis_mgr = RedisConnectionManager(self._redis_config)

        # 本地事件总线（用于本地分发）
        from core.plugin_framework.event_bus import get_event_bus
        self._local_bus = get_event_bus()

        # 订阅者：event_type -> List[callback]
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()

        # Redis Pub/Sub 订阅线程
        self._pubsub_thread: Optional[threading.Thread] = None
        self._running = False

        # 事件溯源：是否启用
        self._event_sourcing_enabled = True

        logger.info(f"[DistributedEventBus] Created node: {self._node_id}")

    # ─────────────────────────────────────────────────────────
    # 连接管理
    # ─────────────────────────────────────────────────────────

    def start(self) -> bool:
        """
        启动分布式事件总线

        Returns:
            是否成功启动
        """
        if not self._redis_mgr.connect():
            logger.error("[DistributedEventBus] Failed to connect to Redis")
            return False

        self._running = True

        # 注册节点
        self._register_node()

        # 启动 Pub/Sub 订阅线程
        self._start_subscriber()

        logger.info(f"[DistributedEventBus] Node {self._node_id} started")
        return True

    def stop(self) -> None:
        """停止分布式事件总线"""
        self._running = False

        # 注销节点
        self._unregister_node()

        # 停止订阅线程
        if self._pubsub_thread and self._pubsub_thread.is_alive():
            # Pub/Sub 线程会在下次循环时退出
            pass

        self._redis_mgr.disconnect()
        logger.info(f"[DistributedEventBus] Node {self._node_id} stopped")

    # ─────────────────────────────────────────────────────────
    # 事件发布
    # ─────────────────────────────────────────────────────────

    def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        ttl: int = 0,
    ) -> bool:
        """
        发布分布式事件

        Args:
            event_type: 事件类型
            payload: 事件负载
            ttl: 事件存活时间（秒，0 表示永久）

        Returns:
            是否成功发布
        """
        if not self._running:
            logger.warning("[DistributedEventBus] Not started")
            return False

        # 创建分布式事件
        event = DistributedEvent(
            event_type=event_type,
            payload=payload,
            source_node=self._node_id,
            ttl=ttl,
        )

        try:
            client = self._redis_mgr.get_client()
            if not client:
                return False

            # 1. 发布到 Pub/Sub（实时通知）
            channel = f"{self.KEY_PUBSUB}{event_type}"
            client.publish(channel, event.to_json())

            # 2. 写入 Stream（事件溯源）
            if self._event_sourcing_enabled:
                stream_key = f"{self.KEY_STREAM}{event_type}"
                client.xadd(
                    stream_key,
                    fields={
                        "event_id": event.event_id,
                        "data": event.to_json(),
                    },
                    maxlen=10000,  # 保留最近 10000 条
                )

            # 3. 本地也分发（本地订阅者立即收到）
            self._dispatch_locally(event)

            # 4. 更新事件计数
            count_key = f"{self.KEY_EVENTS}{event_type}"
            client.incr(count_key)

            logger.debug(
                f"[DistributedEventBus] Published: {event_type} "
                f"(id={event.event_id[:8]})"
            )
            return True

        except Exception as e:
            logger.error(f"[DistributedEventBus] Publish failed: {e}")
            logger.error(traceback.format_exc())
            return False

    # ─────────────────────────────────────────────────────────
    # 事件订阅
    # ─────────────────────────────────────────────────────────

    def subscribe(self, event_type: str, callback: Callable[[DistributedEvent], None]) -> None:
        """
        订阅分布式事件

        Args:
            event_type: 事件类型（支持通配符 "*"）
            callback: 回调函数
        """
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

        logger.debug(f"[DistributedEventBus] Subscribed to: {event_type}")

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """取消订阅"""
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                except ValueError:
                    pass

    # ─────────────────────────────────────────────────────────
    # Pub/Sub 订阅线程
    # ─────────────────────────────────────────────────────────

    def _start_subscriber(self) -> None:
        """启动 Pub/Sub 订阅线程"""
        self._pubsub_thread = threading.Thread(
            target=self._pubsub_loop,
            name="DistributedEventBus-Subscriber",
            daemon=True,
        )
        self._pubsub_thread.start()
        logger.info("[DistributedEventBus] Subscriber thread started")

    def _pubsub_loop(self) -> None:
        """Pub/Sub 订阅循环"""
        while self._running:
            try:
                client = self._redis_mgr.get_client()
                if not client:
                    time.sleep(1)
                    continue

                pubsub = client.pubsub()

                # 订阅所有已注册的事件类型
                with self._lock:
                    channels = list(self._subscribers.keys())

                if not channels:
                    time.sleep(0.5)
                    continue

                # 构建订阅模式
                channel_patterns = []
                for ch in channels:
                    if "*" in ch:
                        channel_patterns.append(f"{self.KEY_PUBSUB}{ch}")
                    else:
                        pubsub.subscribe(f"{self.KEY_PUBSUB}{ch}")

                for pattern in channel_patterns:
                    pubsub.psubscribe(pattern)

                # 监听消息
                for message in pubsub.listen():
                    if not self._running:
                        break

                    if message["type"] == "message":
                        self._handle_pubsub_message(message)
                    elif message["type"] == "pmessage":
                        self._handle_pubsub_message(message)

            except Exception as e:
                logger.error(f"[DistributedEventBus] Pub/Sub error: {e}")
                time.sleep(1)  # 重连延迟

    def _handle_pubsub_message(self, message: dict) -> None:
        """处理 Pub/Sub 消息"""
        try:
            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode("utf-8")

            event = DistributedEvent.from_json(data)

            # 跳过自己发布的事件（已经在本地分发过）
            if event.source_node == self._node_id:
                return

            # 检查过期
            if event.is_expired():
                logger.debug(f"[DistributedEventBus] Skipping expired event: {event.event_type}")
                return

            # 分发到本地订阅者
            self._dispatch_locally(event)

        except Exception as e:
            logger.error(f"[DistributedEventBus] Handle message error: {e}")

    def _dispatch_locally(self, event: DistributedEvent) -> None:
        """分发事件到本地订阅者"""
        with self._lock:
            # 精确匹配
            callbacks = list(self._subscribers.get(event.event_type, []))

            # 通配符匹配
            for pattern, cbs in self._subscribers.items():
                if "*" in pattern:
                    import fnmatch
                    if fnmatch.fnmatch(event.event_type, pattern):
                        callbacks.extend(cbs)

        # 执行回调（不在锁内执行）
        for cb in callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"[DistributedEventBus] Callback error: {e}")
                logger.error(traceback.format_exc())

    # ─────────────────────────────────────────────────────────
    # 事件溯源（Event Sourcing）
    # ─────────────────────────────────────────────────────────

    def get_event_history(
        self,
        event_type: str,
        count: int = 100,
        from_beginning: bool = False,
    ) -> List[DistributedEvent]:
        """
        获取事件历史（事件溯源）

        Args:
            event_type: 事件类型
            count: 返回数量
            from_beginning: 是否从开头读取

        Returns:
            事件列表（按时间顺序）
        """
        try:
            client = self._redis_mgr.get_client()
            if not client:
                return []

            stream_key = f"{self.KEY_STREAM}{event_type}"

            # 读取 Stream
            if from_beginning:
                messages = client.xrange(stream_key, count=count)
            else:
                messages = client.xrevrange(stream_key, count=count)
                messages.reverse()  # 按时间正序

            # 解析事件
            events = []
            for msg_id, fields in messages:
                event_json = fields.get("data", "")
                if event_json:
                    if isinstance(event_json, bytes):
                        event_json = event_json.decode("utf-8")
                    events.append(DistributedEvent.from_json(event_json))

            return events

        except Exception as e:
            logger.error(f"[DistributedEventBus] Get history failed: {e}")
            return []

    def replay_events(
        self,
        event_type: str,
        handler: Callable[[DistributedEvent], None],
        from_beginning: bool = True,
    ) -> int:
        """
        重放事件

        Args:
            event_type: 事件类型
            handler: 事件处理器
            from_beginning: 是否从开头重放

        Returns:
            重放的事件数量
        """
        events = self.get_event_history(
            event_type=event_type,
            count=10000,
            from_beginning=from_beginning,
        )

        count = 0
        for event in events:
            try:
                handler(event)
                count += 1
            except Exception as e:
                logger.error(f"[DistributedEventBus] Replay error: {e}")

        logger.info(
            f"[DistributedEventBus] Replayed {count} events "
            f"for {event_type}"
        )
        return count

    def enable_event_sourcing(self, enabled: bool = True) -> None:
        """启用/禁用事件溯源"""
        self._event_sourcing_enabled = enabled
        logger.info(
            f"[DistributedEventBus] Event sourcing: "
            f"{'enabled' if enabled else 'disabled'}"
        )

    # ─────────────────────────────────────────────────────────
    # 节点管理
    # ─────────────────────────────────────────────────────────

    def _register_node(self) -> None:
        """注册节点（心跳）"""
        try:
            client = self._redis_mgr.get_client()
            if not client:
                return

            # 使用 Redis Set 存储在线节点
            client.sadd(self.KEY_NODES, self._node_id)

            # 设置过期时间（5 分钟，需定期刷新）
            client.expire(self.KEY_NODES, 300)

            logger.debug(f"[DistributedEventBus] Node registered: {self._node_id}")

        except Exception as e:
            logger.error(f"[DistributedEventBus] Register node failed: {e}")

    def _unregister_node(self) -> None:
        """注销节点"""
        try:
            client = self._redis_mgr.get_client()
            if not client:
                return

            client.srem(self.KEY_NODES, self._node_id)
            logger.debug(f"[DistributedEventBus] Node unregistered: {self._node_id}")

        except Exception as e:
            logger.error(f"[DistributedEventBus] Unregister node failed: {e}")

    def refresh_node_heartbeat(self) -> None:
        """刷新节点心跳（定期调用）"""
        try:
            client = self._redis_mgr.get_client()
            if not client:
                return

            # 刷新节点过期时间
            client.expire(self.KEY_NODES, 300)

        except Exception as e:
            logger.error(f"[DistributedEventBus] Refresh heartbeat failed: {e}")

    def get_online_nodes(self) -> List[str]:
        """获取所有在线节点"""
        try:
            client = self._redis_mgr.get_client()
            if not client:
                return []

            nodes = client.smembers(self.KEY_NODES)
            return [n.decode("utf-8") if isinstance(n, bytes) else n for n in nodes]

        except Exception as e:
            logger.error(f"[DistributedEventBus] Get nodes failed: {e}")
            return []

    # ─────────────────────────────────────────────────────────
    # 统计信息
    # ─────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            client = self._redis_mgr.get_client()
            if not client:
                return {"error": "Not connected"}

            # 统计每个事件类型的发布数量
            event_counts = {}
            for key in client.scan_iter(f"{self.KEY_EVENTS}*"):
                event_type = key.decode("utf-8").replace(self.KEY_EVENTS, "")
                event_counts[event_type] = int(client.get(key) or 0)

            return {
                "node_id": self._node_id,
                "connected": self._redis_mgr.is_connected(),
                "subscribers": list(self._subscribers.keys()),
                "online_nodes": self.get_online_nodes(),
                "event_counts": event_counts,
                "event_sourcing_enabled": self._event_sourcing_enabled,
            }

        except Exception as e:
            logger.error(f"[DistributedEventBus] Get stats failed: {e}")
            return {"error": str(e)}

    # ─────────────────────────────────────────────────────────
    # 关闭
    # ─────────────────────────────────────────────────────────

    def close(self) -> None:
        """关闭（别名）"""
        self.stop()


# ─────────────────────────────────────────────────────────────
# 全局单例
# ─────────────────────────────────────────────────────────────

_bus_instance: Optional[DistributedEventBus] = None
_bus_lock = threading.RLock()


def get_distributed_event_bus(
    node_id: Optional[str] = None,
    redis_config: Optional[RedisConfig] = None,
) -> Optional[DistributedEventBus]:
    """获取分布式事件总线单例"""
    global _bus_instance
    with _bus_lock:
        if _bus_instance is None:
            _bus_instance = DistributedEventBus(
                node_id=node_id,
                redis_config=redis_config,
            )
        return _bus_instance


def start_distributed_event_bus(
    node_id: Optional[str] = None,
    redis_config: Optional[RedisConfig] = None,
) -> bool:
    """启动分布式事件总线"""
    bus = get_distributed_event_bus(node_id, redis_config)
    if bus:
        return bus.start()
    return False


def stop_distributed_event_bus() -> None:
    """停止分布式事件总线"""
    global _bus_instance
    with _bus_lock:
        if _bus_instance:
            _bus_instance.stop()
            _bus_instance = None
