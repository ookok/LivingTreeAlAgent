"""
TCP 连接池管理 - Connection Pool

负责：
1. 管理与其他节点的 TCP 连接
2. 连接复用和心跳保活
3. 自动重连
4. 连接状态监控

使用示例：
```python
pool = ConnectionPool(node_id="node-001")

# 设置消息处理
pool.on_message = lambda from_node, data: handle(data)
pool.on_connected = lambda node_id: logger.info(f"Connected to {node_id}")
pool.on_disconnected = lambda node_id: logger.info(f"Disconnected from {node_id}")

# 连接到节点
pool.connect("192.168.1.10", 8080, node_id="node-002")

# 发送消息
pool.send("node-002", b"hello")

# 关闭
pool.close()
```
"""

import socket
import json
import time
import uuid
import logging
import threading
from typing import Dict, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from threading import Thread, RLock
from core.logger import get_logger
logger = get_logger('relay_chain.event_ext.p2p_network.network.connection')


logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """连接状态"""
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"


@dataclass
class Connection:
    """
    TCP 连接

    Attributes:
        node_id: 节点ID
        sock: socket 对象
        state: 连接状态
        last_active: 最后活跃时间
        reconnect_attempts: 重连次数
    """
    node_id: str
    ip: str
    port: int
    sock: Optional[socket.socket] = None
    state: ConnectionState = ConnectionState.DISCONNECTED
    last_active: float = field(default_factory=time.time)
    reconnect_attempts: int = 0
    max_reconnect_attempts: int = 5

    def is_alive(self) -> bool:
        """检查连接是否存活"""
        return (
            self.state == ConnectionState.CONNECTED
            and self.sock is not None
        )

    def touch(self):
        """更新最后活跃时间"""
        self.last_active = time.time()


class ConnectionPool:
    """
    TCP 连接池

    功能：
    1. 维护与所有对等节点的连接
    2. 自动重连
    3. 心跳保活
    4. 消息收发
    """

    # 连接超时（秒）
    CONNECT_TIMEOUT = 5.0

    # 读操作超时（秒）
    READ_TIMEOUT = 30.0

    # 心跳间隔（秒）
    HEARTBEAT_INTERVAL = 5.0

    # 连接空闲超时（秒）
    IDLE_TIMEOUT = 60.0

    # 最大重连次数
    MAX_RECONNECT = 5

    # 最大连接数
    MAX_CONNECTIONS = 50

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._lock = RLock()

        # 连接表
        self._connections: Dict[str, Connection] = {}

        # 节点信息
        self._node_info: Dict[str, Dict[str, Any]] = {}

        # 运行状态
        self._running = False
        self._worker_thread: Optional[Thread] = None

        # 回调
        self.on_message: Optional[Callable[[str, bytes], None]] = None
        self.on_connected: Optional[Callable[[str], None]] = None
        self.on_disconnected: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str, Exception], None]] = None

    def start(self):
        """启动连接池"""
        if self._running:
            return

        self._running = True
        self._worker_thread = Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

        logger.info(f"[{self.node_id}] 连接池已启动")

    def stop(self):
        """停止连接池"""
        self._running = False

        with self._lock:
            for conn in self._connections.values():
                self._close_connection(conn)

        logger.info(f"[{self.node_id}] 连接池已停止")

    def connect(
        self,
        ip: str,
        port: int,
        node_id: str = None,
        timeout: float = None,
    ) -> bool:
        """
        连接到节点

        Args:
            ip: 节点 IP
            port: 节点端口
            node_id: 节点ID（可选）
            timeout: 连接超时

        Returns:
            是否连接成功
        """
        timeout = timeout or self.CONNECT_TIMEOUT
        node_id = node_id or f"{ip}:{port}"

        with self._lock:
            # 检查是否已有连接
            if node_id in self._connections:
                conn = self._connections[node_id]
                if conn.is_alive():
                    return True

            # 检查连接数限制
            if len(self._connections) >= self.MAX_CONNECTIONS:
                logger.warning(
                    f"[{self.node_id}] 连接数已达上限: {self.MAX_CONNECTIONS}"
                )
                return False

        logger.info(f"[{self.node_id}] 连接到 {node_id} @ {ip}:{port}")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, port))
            sock.settimeout(self.READ_TIMEOUT)

            conn = Connection(
                node_id=node_id,
                ip=ip,
                port=port,
                sock=sock,
                state=ConnectionState.CONNECTED,
            )

            with self._lock:
                self._connections[node_id] = conn

            logger.info(f"[{self.node_id}] 已连接到 {node_id}")

            if self.on_connected:
                self.on_connected(node_id)

            return True

        except Exception as e:
            logger.error(f"[{self.node_id}] 连接失败 {node_id}: {e}")

            with self._lock:
                if node_id in self._connections:
                    conn = self._connections[node_id]
                    conn.state = ConnectionState.DISCONNECTED
                    conn.reconnect_attempts += 1

            if self.on_error:
                self.on_error(node_id, e)

            return False

    def disconnect(self, node_id: str):
        """
        断开连接

        Args:
            node_id: 节点ID
        """
        with self._lock:
            if node_id not in self._connections:
                return

            conn = self._connections[node_id]
            self._close_connection(conn)
            del self._connections[node_id]

        logger.info(f"[{self.node_id}] 断开连接: {node_id}")

        if self.on_disconnected:
            self.on_disconnected(node_id)

    def send(self, node_id: str, data: bytes) -> bool:
        """
        发送数据

        Args:
            node_id: 节点ID
            data: 数据

        Returns:
            是否发送成功
        """
        with self._lock:
            if node_id not in self._connections:
                logger.warning(f"[{self.node_id}] 未知节点: {node_id}")
                return False

            conn = self._connections[node_id]

            if not conn.is_alive():
                logger.warning(f"[{self.node_id}] 连接已断开: {node_id}")
                return False

            try:
                # 发送长度前缀 + 数据
                msg = struct.pack(">I", len(data)) + data
                conn.sock.sendall(msg)
                conn.touch()
                return True

            except Exception as e:
                logger.error(f"[{self.node_id}] 发送失败 -> {node_id}: {e}")
                conn.state = ConnectionState.DISCONNECTED
                return False

    def broadcast(self, data: bytes):
        """
        广播数据到所有连接

        Args:
            data: 数据
        """
        with self._lock:
            nodes = list(self._connections.keys())

        for node_id in nodes:
            self.send(node_id, data)

    def get_connection(self, node_id: str) -> Optional[Connection]:
        """获取连接信息"""
        with self._lock:
            return self._connections.get(node_id)

    def get_alive_connections(self) -> Dict[str, Connection]:
        """获取所有存活连接"""
        with self._lock:
            return {
                node_id: conn
                for node_id, conn in self._connections.items()
                if conn.is_alive()
            }

    def get_all_connections(self) -> Dict[str, Connection]:
        """获取所有连接"""
        with self._lock:
            return dict(self._connections)

    def _close_connection(self, conn: Connection):
        """关闭连接"""
        if conn.sock:
            try:
                conn.sock.close()
            except:
                pass
            conn.sock = None
        conn.state = ConnectionState.DISCONNECTED

    def _worker_loop(self):
        """工作循环：读取数据、处理心跳、自动重连"""
        while self._running:
            try:
                # 收集需要处理的可读连接
                with self._lock:
                    alive_conns = [
                        (node_id, conn)
                        for node_id, conn in self._connections.items()
                        if conn.is_alive()
                    ]

                for node_id, conn in alive_conns:
                    try:
                        # 非阻塞读取
                        self._try_read(conn)
                    except socket.timeout:
                        pass
                    except Exception as e:
                        logger.error(
                            f"[{self.node_id}] 读取错误 {node_id}: {e}"
                        )
                        conn.state = ConnectionState.DISCONNECTED

                # 检查需要重连的连接
                self._check_reconnect()

                # 发送心跳
                self._send_heartbeats()

                time.sleep(0.1)

            except Exception as e:
                logger.error(f"[{self.node_id}] 工作循环错误: {e}")

    def _try_read(self, conn: Connection):
        """尝试读取数据"""
        sock = conn.sock

        # 先读取 4 字节长度
        sock.setblocking(False)
        try:
            header = sock.recv(4)
        except BlockingIOError:
            return

        if not header:
            conn.state = ConnectionState.DISCONNECTED
            return

        if len(header) < 4:
            return

        length = struct.unpack(">I", header)[0]

        # 读取数据
        data = b""
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                break
            data += chunk

        if data:
            conn.touch()
            if self.on_message:
                self.on_message(conn.node_id, data)

    def _check_reconnect(self):
        """检查并重连断开的连接"""
        with self._lock:
            for node_id, conn in self._connections.items():
                if (
                    conn.state == ConnectionState.DISCONNECTED
                    and conn.reconnect_attempts < conn.max_reconnect_attempts
                ):
                    conn.state = ConnectionState.RECONNECTING
                    # 在锁外进行重连
                    Thread(
                        target=self._reconnect,
                        args=(node_id, conn),
                        daemon=True
                    ).start()

    def _reconnect(self, node_id: str, conn: Connection):
        """重连"""
        logger.info(f"[{self.node_id}] 尝试重连: {node_id}")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.CONNECT_TIMEOUT)
            sock.connect((conn.ip, conn.port))
            sock.settimeout(self.READ_TIMEOUT)

            with self._lock:
                conn.sock = sock
                conn.state = ConnectionState.CONNECTED
                conn.reconnect_attempts = 0

            logger.info(f"[{self.node_id}] 重连成功: {node_id}")

            if self.on_connected:
                self.on_connected(node_id)

        except Exception as e:
            logger.error(f"[{self.node_id}] 重连失败: {node_id}: {e}")

            with self._lock:
                conn.reconnect_attempts += 1

    def _send_heartbeats(self):
        """发送心跳"""
        now = time.time()

        with self._lock:
            for conn in self._connections.values():
                if conn.is_alive() and now - conn.last_active > self.HEARTBEAT_INTERVAL:
                    try:
                        heartbeat = b"ping"
                        conn.sock.sendall(heartbeat)
                        conn.touch()
                    except:
                        conn.state = ConnectionState.DISCONNECTED

    def set_node_info(self, node_id: str, info: Dict[str, Any]):
        """设置节点信息"""
        with self._lock:
            self._node_info[node_id] = info

    def get_node_info(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点信息"""
        with self._lock:
            return self._node_info.get(node_id)

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        with self._lock:
            return {
                "node_id": self.node_id,
                "total_connections": len(self._connections),
                "alive_connections": sum(
                    1 for c in self._connections.values() if c.is_alive()
                ),
                "connections": [
                    {
                        "node_id": c.node_id,
                        "ip": c.ip,
                        "port": c.port,
                        "state": c.state.value,
                        "last_active": c.last_active,
                        "reconnect_attempts": c.reconnect_attempts,
                    }
                    for c in self._connections.values()
                ],
            }
