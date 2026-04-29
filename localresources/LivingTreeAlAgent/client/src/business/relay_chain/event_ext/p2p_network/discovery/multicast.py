"""
UDP 多播自动发现 - Multicast Discovery

核心功能：
1. UDP 多播广播自己的存在
2. 监听并响应其他节点的广播
3. 自动建立 TCP 连接

零配置的关键：
- 使用标准的 multicast 组播地址（224.0.0.1 - 本地链路）
- 无需指定任何 IP/端口/节点列表
- 节点启动时自动广播，自动发现邻居

协议格式：
{
    "type": "DISCOVER",
    "node_id": "node-xxx",
    "endpoint": "192.168.1.x:xxxxx",
    "port": xxxxx,
    "capabilities": ["cpu", "gpu"],
    "load": 0.3,
    "timestamp": 1234567890.123,
    "version": "1.0"
}
"""

import socket
import asyncio
import json
import time
import uuid
import logging
from typing import Dict, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from threading import Thread, RLock

# 日志配置
logger = logging.getLogger(__name__)


@dataclass
class DiscoveredNode:
    """发现的节点信息"""
    node_id: str
    ip: str
    port: int
    endpoint: str  # "ip:port"
    capabilities: set = field(default_factory=set)
    load: float = 0.0  # 0.0 ~ 1.0
    last_seen: float = field(default_factory=time.time)
    is_connected: bool = False

    def is_alive(self, timeout: float = 30.0) -> bool:
        """检查节点是否还存活"""
        return time.time() - self.last_seen < timeout

    def update(self, data: Dict[str, Any]):
        """更新节点信息"""
        self.load = data.get("load", self.load)
        self.capabilities = set(data.get("capabilities", []))
        self.last_seen = data.get("timestamp", time.time())


class MulticastDiscover:
    """
    UDP 多播自动发现

    使用 UDP 多播在局域网内广播节点存在，实现零配置自动发现。

    使用示例：
    ```python
    discover = MulticastDiscover(node_id="node-001")

    # 设置回调
    discover.on_node_discovered = lambda node: print(f"发现节点: {node.node_id}")

    # 启动
    discover.start()

    # 手动广播（自动定时广播）
    discover.broadcast()

    # 停止
    discover.stop()
    ```
    """

    # 多播地址（本地链路，仅在同一网段内传播）
    MULTICAST_GROUP = "224.0.0.1"
    MULTICAST_PORT = 9999

    # 广播间隔（秒）
    BROADCAST_INTERVAL = 5.0

    # 节点超时（秒）
    NODE_TIMEOUT = 30.0

    def __init__(
        self,
        node_id: Optional[str] = None,
        multicast_group: str = None,
        multicast_port: int = None,
        broadcast_interval: float = None,
    ):
        """
        Args:
            node_id: 节点ID，如果不指定则自动生成
            multicast_group: 多播地址
            multicast_port: 多播端口
            broadcast_interval: 广播间隔
        """
        self.node_id = node_id or f"node-{uuid.uuid4().hex[:8]}"
        self.multicast_group = multicast_group or self.MULTICAST_GROUP
        self.multicast_port = multicast_port or self.MULTICAST_PORT
        self.broadcast_interval = broadcast_interval or self.BROADCAST_INTERVAL

        # 发现的节点
        self.discovered_nodes: Dict[str, DiscoveredNode] = {}
        self._lock = RLock()

        # Socket
        self._sock: Optional[socket.socket] = None
        self._running = False
        self._broadcast_thread: Optional[Thread] = None

        # 回调
        self.on_node_discovered: Optional[Callable[[DiscoveredNode], None]] = None
        self.on_node_lost: Optional[Callable[[str], None]] = None
        self.on_broadcast_sent: Optional[Callable[[], None]] = None

        # 本机信息
        self._local_ip: Optional[str] = None
        self._local_port: int = 0

    @property
    def local_ip(self) -> Optional[str]:
        """获取本机 IP"""
        if self._local_ip:
            return self._local_ip
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            self._local_ip = s.getsockname()[0]
            s.close()
        except:
            self._local_ip = "127.0.0.1"
        return self._local_ip

    def _create_socket(self) -> socket.socket:
        """创建 UDP socket"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            # 绑定到多播端口
            sock.bind(("", self.multicast_port))
        except OSError:
            # 端口可能被占用，尝试其他端口
            sock.bind(("", 0))

        # 加入多播组
        mreq = socket.inet_aton(self.multicast_group) + socket.inet_aton("0.0.0.0")
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        # 设置超时
        sock.settimeout(1.0)

        # 获取实际绑定的端口
        self._local_port = sock.getsockname()[1]

        return sock

    def _create_broadcast_socket(self) -> socket.socket:
        """创建广播 socket"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", 0))
        return sock

    def start(self):
        """启动发现服务"""
        if self._running:
            return

        self._running = True

        # 创建监听 socket
        self._sock = self._create_socket()

        # 启动监听线程
        self._listen_thread = Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()

        # 启动广播线程
        self._broadcast_thread = Thread(target=self._broadcast_loop, daemon=True)
        self._broadcast_thread.start()

        # 立即广播一次
        self.broadcast()

        logger.info(f"[{self.node_id}] 多播发现服务已启动")
        logger.info(f"[{self.node_id}] 多播地址: {self.multicast_group}:{self.multicast_port}")
        logger.info(f"[{self.node_id}] 本机IP: {self.local_ip}")

    def stop(self):
        """停止发现服务"""
        self._running = False

        if self._sock:
            self._sock.close()
            self._sock = None

        logger.info(f"[{self.node_id}] 多播发现服务已停止")

    def _listen_loop(self):
        """监听循环"""
        while self._running:
            try:
                data, addr = self._sock.recvfrom(4096)
                self._handle_message(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"[{self.node_id}] 监听错误: {e}")
                break

    def _handle_message(self, data: bytes, addr: tuple):
        """处理收到的消息"""
        try:
            msg = json.loads(data.decode("utf-8"))
            msg_type = msg.get("type")

            if msg_type == "DISCOVER":
                self._handle_discover(msg, addr)
            elif msg_type == "HELLO":
                self._handle_hello(msg, addr)
            elif msg_type == "GOODBYE":
                self._handle_goodbye(msg, addr)

        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.error(f"[{self.node_id}] 处理消息错误: {e}")

    def _handle_discover(self, msg: Dict[str, Any], addr: tuple):
        """处理 DISCOVER 广播"""
        from_node_id = msg.get("node_id")

        # 忽略自己
        if from_node_id == self.node_id:
            return

        ip = addr[0]
        port = msg.get("port", self.multicast_port)

        logger.info(f"[{self.node_id}] 发现节点: {from_node_id} @ {ip}:{port}")

        # 更新节点信息
        with self._lock:
            if from_node_id in self.discovered_nodes:
                self.discovered_nodes[from_node_id].update(msg)
            else:
                node = DiscoveredNode(
                    node_id=from_node_id,
                    ip=ip,
                    port=port,
                    endpoint=f"{ip}:{port}",
                    capabilities=set(msg.get("capabilities", [])),
                    load=msg.get("load", 0.0),
                    last_seen=msg.get("timestamp", time.time()),
                )
                self.discovered_nodes[from_node_id] = node

                # 触发回调
                if self.on_node_discovered:
                    self.on_node_discovered(node)

        # 回复 HELLO
        self._send_hello(ip, port)

    def _handle_hello(self, msg: Dict[str, Any], addr: tuple):
        """处理 HELLO 响应"""
        from_node_id = msg.get("node_id")

        # 忽略自己
        if from_node_id == self.node_id:
            return

        ip = addr[0]
        port = msg.get("port", self.multicast_port)

        with self._lock:
            if from_node_id not in self.discovered_nodes:
                node = DiscoveredNode(
                    node_id=from_node_id,
                    ip=ip,
                    port=port,
                    endpoint=f"{ip}:{port}",
                    capabilities=set(msg.get("capabilities", [])),
                    load=msg.get("load", 0.0),
                    last_seen=time.time(),
                )
                self.discovered_nodes[from_node_id] = node

                logger.info(f"[{self.node_id}] 节点响应 HELLO: {from_node_id}")

                if self.on_node_discovered:
                    self.on_node_discovered(node)

    def _handle_goodbye(self, msg: Dict[str, Any], addr: tuple):
        """处理 GOODBYE（节点离开）"""
        from_node_id = msg.get("node_id")

        with self._lock:
            if from_node_id in self.discovered_nodes:
                del self.discovered_nodes[from_node_id]
                logger.info(f"[{self.node_id}] 节点离开: {from_node_id}")

                if self.on_node_lost:
                    self.on_node_lost(from_node_id)

    def _broadcast_loop(self):
        """广播循环"""
        sock = self._create_broadcast_socket()

        while self._running:
            try:
                self.broadcast(sock)
                time.sleep(self.broadcast_interval)
            except Exception as e:
                if self._running:
                    logger.error(f"[{self.node_id}] 广播错误: {e}")

        sock.close()

    def broadcast(self, sock: socket.socket = None):
        """
        广播自己的存在

        Args:
            sock: 可选的 socket，如果不指定则创建新的
        """
        msg = {
            "type": "DISCOVER",
            "node_id": self.node_id,
            "ip": self.local_ip,
            "port": self._local_port or self.multicast_port,
            "capabilities": [],  # 可扩展
            "load": 0.0,  # 可扩展
            "timestamp": time.time(),
            "version": "1.0",
        }

        data = json.dumps(msg).encode("utf-8")

        try:
            if sock is None:
                sock = self._create_broadcast_socket()
                sock.sendto(data, (self.multicast_group, self.multicast_port))
                sock.close()
            else:
                sock.sendto(data, (self.multicast_group, self.multicast_port))

            if self.on_broadcast_sent:
                self.on_broadcast_sent()

        except Exception as e:
            logger.error(f"[{self.node_id}] 广播失败: {e}")

    def _send_hello(self, ip: str, port: int):
        """发送 HELLO 响应"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            msg = {
                "type": "HELLO",
                "node_id": self.node_id,
                "ip": self.local_ip,
                "port": self._local_port or self.multicast_port,
                "capabilities": [],
                "load": 0.0,
                "timestamp": time.time(),
                "version": "1.0",
            }
            sock.sendto(json.dumps(msg).encode("utf-8"), (ip, port))
            sock.close()
        except Exception as e:
            logger.error(f"[{self.node_id}] 发送 HELLO 失败: {e}")

    def send_goodbye(self):
        """发送 GOODBYE 消息（节点离开）"""
        try:
            sock = self._create_broadcast_socket()
            msg = {
                "type": "GOODBYE",
                "node_id": self.node_id,
                "timestamp": time.time(),
            }
            sock.sendto(json.dumps(msg).encode("utf-8"), (self.multicast_group, self.multicast_port))
            sock.close()
        except Exception as e:
            logger.error(f"[{self.node_id}] 发送 GOODBYE 失败: {e}")

    def get_alive_nodes(self) -> Dict[str, DiscoveredNode]:
        """获取所有存活节点"""
        with self._lock:
            return {
                node_id: node
                for node_id, node in self.discovered_nodes.items()
                if node.is_alive(self.NODE_TIMEOUT)
            }

    def get_best_node(self, capability: str = None) -> Optional[DiscoveredNode]:
        """
        获取最佳节点（负载最低）

        Args:
            capability: 需要的 capability（如 "gpu"）

        Returns:
            负载最低的存活节点
        """
        alive = self.get_alive_nodes()

        if not alive:
            return None

        if capability:
            # 筛选有特定能力的节点
            candidates = [
                n for n in alive.values()
                if capability in n.capabilities
            ]
            if not candidates:
                candidates = list(alive.values())
        else:
            candidates = list(alive.values())

        return min(candidates, key=lambda n: n.load)

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        alive = self.get_alive_nodes()
        return {
            "node_id": self.node_id,
            "multicast_group": self.multicast_group,
            "multicast_port": self.multicast_port,
            "local_ip": self.local_ip,
            "local_port": self._local_port,
            "discovered_nodes": len(self.discovered_nodes),
            "alive_nodes": len(alive),
            "running": self._running,
        }
