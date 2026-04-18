"""
分布式节点 - Distributed Node

整合所有组件的主节点类，实现零配置、自发现、自组织的分布式系统。

核心组件：
1. MulticastDiscover: UDP 多播自动发现
2. PeerExchange: 节点信息交换
3. Election: 领导者选举
4. ConnectionPool: TCP 连接池
5. RoutingTable: 路由表
6. LoadBalancer: 负载均衡
7. TaskDistributor: 任务分发
8. FailureRecovery: 故障恢复

使用示例：
```python
# 零配置启动
node = DistributedNode()

# 设置任务执行器
node.set_task_executor(lambda task: process_task(task))

# 启动
node.start()

# 自动发现邻居
# 自动选举协调者
# 自动分配任务

# 提交任务（如果有协调者，任务会被分发）
task_id = node.submit_task("compute", {"data": "xxx"})

# 停止
node.stop()
```
"""

import time
import uuid
import logging
import threading
from typing import Dict, Any, Optional, Callable, List, Set
from threading import RLock

from .discovery.multicast import MulticastDiscover, DiscoveredNode
from .discovery.peer_exchange import PeerExchange
from .discovery.election import Election, NodeRole, ElectionMessageType
from .network.protocol import Protocol, MessageType
from .network.connection import ConnectionPool
from .network.routing import RoutingTable
from .scheduler.load_balancer import LoadBalancer
from .scheduler.task_distributor import TaskDistributor, Task, TaskState
from .scheduler.failure_recovery import FailureRecovery

logger = logging.getLogger(__name__)


class DistributedNode:
    """
    分布式节点

    整合所有 P2P 网络组件，实现：
    1. 零配置启动
    2. 自动发现邻居
    3. 自组织网络拓扑
    4. 自动领导者选举
    5. 负载均衡任务分配
    6. 故障自动恢复
    """

    # 节点版本
    VERSION = "1.0"

    def __init__(
        self,
        node_id: str = None,
        port: int = 0,
        capabilities: List[str] = None,
    ):
        """
        Args:
            node_id: 节点ID，不指定则自动生成
            port: TCP 监听端口，0 表示自动选择
            capabilities: 节点能力列表
        """
        self.node_id = node_id or f"node-{uuid.uuid4().hex[:8]}"
        self.port = port
        self.capabilities = capabilities or []

        self._lock = RLock()
        self._running = False

        # 初始化各组件
        self._init_components()

        # 回调
        self.on_node_discovered: Optional[Callable[[str], None]] = None
        self.on_coordinator_changed: Optional[Callable[[Optional[str]], None]] = None
        self.on_task_received: Optional[Callable[[Task], None]] = None
        self.on_message: Optional[Callable[[str, Dict], None]] = None

    def _init_components(self):
        """初始化所有组件"""
        # 自动发现
        self.discoverer = MulticastDiscover(node_id=self.node_id)
        self.discoverer.on_node_discovered = self._on_node_discovered
        self.discoverer.on_node_lost = self._on_node_lost

        # 节点交换
        self.peer_exchange = PeerExchange(node_id=self.node_id)
        self.peer_exchange.on_new_peer = self._on_new_peer

        # 选举
        self.election = Election(node_id=self.node_id)
        self.election.on_become_coordinator = self._on_become_coordinator
        self.election.on_become_follower = self._on_become_follower
        self.election.on_election_started = self._on_election_started
        self.election.on_coordinator_changed = self._on_coordinator_changed
        self.election.on_message = self._on_election_message

        # 网络协议
        self.protocol = Protocol(node_id=self.node_id)
        self.protocol.on_send = self._on_protocol_send
        self.protocol.on_broadcast = self._on_protocol_broadcast

        # 连接池
        self.connection_pool = ConnectionPool(node_id=self.node_id)
        self.connection_pool.on_message = self._on_connection_message
        self.connection_pool.on_connected = self._on_connected
        self.connection_pool.on_disconnected = self._on_disconnected

        # 路由表
        self.routing_table = RoutingTable(node_id=self.node_id)
        self.routing_table.on_neighbor_added = self._on_neighbor_added

        # 负载均衡
        self.load_balancer = LoadBalancer(node_id=self.node_id)

        # 任务分发
        self.task_distributor = TaskDistributor(node_id=self.node_id)
        self.task_distributor.set_local_executor(self._execute_task)
        self.task_distributor.on_task_completed = self._on_task_completed
        self.task_distributor.on_task_failed = self._on_task_failed

        # 故障恢复
        self.failure_recovery = FailureRecovery(node_id=self.node_id)
        self.failure_recovery.set_task_distributor(self.task_distributor)
        self.failure_recovery.set_election(self.election)
        self.failure_recovery.set_load_balancer(self.load_balancer)
        self.failure_recovery.on_tasks_redistributed = self._on_tasks_redistributed

        # 注册协议处理器
        self._register_protocol_handlers()

    def _register_protocol_handlers(self):
        """注册协议消息处理器"""
        self.protocol.register_handler(MessageType.TASK_DISPATCH, self._handle_task_dispatch)
        self.protocol.register_handler(MessageType.TASK_RESULT, self._handle_task_result)
        self.protocol.register_handler(MessageType.LOAD_REPORT, self._handle_load_report)
        self.protocol.register_handler(MessageType.PEER_EXCHANGE, self._handle_peer_exchange)

    # ═══════════════════════════════════════════════════════════════════════════
    # 生命周期
    # ═══════════════════════════════════════════════════════════════════════════

    def start(self):
        """启动节点"""
        if self._running:
            return

        self._running = True

        logger.info(f"[{self.node_id}] 🚀 启动分布式节点...")

        # 启动各组件
        self.discoverer.start()
        self.connection_pool.start()
        self.election.start()

        # 启动工作线程
        self._worker_thread = threading.Thread(target=self._work_loop, daemon=True)
        self._worker_thread.start()

        # 定期上报负载
        self._load_thread = threading.Thread(target=self._load_report_loop, daemon=True)
        self._load_report_thread.start()

        logger.info(f"[{self.node_id}] ✅ 节点已启动")
        logger.info(f"[{self.node_id}]    版本: {self.VERSION}")
        logger.info(f"[{self.node_id}]    能力: {self.capabilities or '无'}")

    def stop(self):
        """停止节点"""
        if not self._running:
            return

        self._running = False

        logger.info(f"[{self.node_id}] 🛑 停止节点...")

        # 发送离开消息
        self.discoverer.send_goodbye()

        # 停止各组件
        self.discoverer.stop()
        self.connection_pool.stop()
        self.election.stop()

        logger.info(f"[{self.node_id}] ✅ 节点已停止")

    def _work_loop(self):
        """工作循环"""
        last_load_update = 0
        last_routing_update = 0
        last_cleanup = 0

        while self._running:
            try:
                now = time.time()

                # 定期更新本地负载
                if now - last_load_update > 5.0:
                    self._update_local_load()
                    last_load_update = now

                # 定期广播路由
                if now - last_routing_update > 30.0:
                    self._broadcast_routing()
                    last_routing_update = now

                # 定期清理
                if now - last_cleanup > 60.0:
                    self.peer_exchange.cleanup_expired()
                    self.routing_table.cleanup_expired()
                    self.task_distributor.cleanup_expired()
                    self.failure_recovery.cleanup_old_records()
                    last_cleanup = now

                # 处理待分发任务（协调者角色）
                if self.election.is_coordinator:
                    self._process_pending_tasks()

                time.sleep(1.0)

            except Exception as e:
                logger.error(f"[{self.node_id}] 工作循环错误: {e}")

    def _load_report_loop(self):
        """负载上报循环"""
        while self._running:
            try:
                # 上报本地负载
                self._update_local_load()

                # 广播负载信息
                msg = self.protocol.create_load_report(
                    load=self.load_balancer._local_load.load_score,
                    metrics={
                        "cpu": self.load_balancer._local_load.cpu,
                        "memory": self.load_balancer._local_load.memory,
                        "queue": self.load_balancer._local_load.queue,
                        "capabilities": self.capabilities,
                    }
                )
                self.protocol.broadcast(MessageType.LOAD_REPORT, msg.payload)

                time.sleep(5.0)

            except Exception as e:
                logger.error(f"[{self.node_id}] 负载上报错误: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 任务处理
    # ═══════════════════════════════════════════════════════════════════════════

    def set_task_executor(self, executor: Callable):
        """
        设置任务执行器

        Args:
            executor: 执行函数，签名为 executor(task: Task) -> result
        """
        self.task_distributor.set_local_executor(executor)
        logger.info(f"[{self.node_id}] 任务执行器已设置")

    def submit_task(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        requirements: Dict[str, Any] = None,
        priority: int = 5,
    ) -> str:
        """
        提交任务

        Args:
            task_type: 任务类型
            task_data: 任务数据
            requirements: 任务要求
            priority: 优先级

        Returns:
            task_id: 任务ID
        """
        task_id = self.task_distributor.submit_task(
            task_type=task_type,
            task_data=task_data,
            requirements=requirements,
            priority=priority,
            submitter=self.node_id,
        )

        logger.info(f"[{self.node_id}] 提交任务: {task_id}")

        return task_id

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        return self.task_distributor.get_task_status(task_id)

    def _execute_task(self, task: Task):
        """执行任务（本地）"""
        logger.info(f"[{self.node_id}] 执行任务: {task.task_id}")

        if self.on_task_received:
            result = self.on_task_received(task)
            return result

        # 默认执行：直接返回成功
        return {"status": "completed", "task_id": task.task_id}

    def _process_pending_tasks(self):
        """处理待分发任务（协调者执行）"""
        pending = self.task_distributor.get_pending_tasks()

        for task_id in pending[:10]:  # 每次最多处理10个
            task = self.task_distributor.get_task_status(task_id)
            if not task:
                continue

            # 选择最佳节点
            capability = None
            if task.get("requirements"):
                capability = task["requirements"].get("capability")

            best = self.load_balancer.select_best_node(capability=capability)

            if best and best["node_id"] != self.node_id:
                # 分发到其他节点
                self.task_distributor.dispatch_task(task_id, best["node_id"])
            elif not best or best["node_id"] == self.node_id:
                # 本地执行
                self.task_distributor.execute_local_task(task_id)

    def _on_task_completed(self, task: Task):
        """任务完成回调"""
        logger.info(f"[{self.node_id}] 任务完成: {task.task_id}")

        # 如果是协调者，通知提交者
        # （实际应该通过 P2P 消息通知，这里简化处理）

    def _on_task_failed(self, task: Task):
        """任务失败回调"""
        logger.error(f"[{self.node_id}] 任务失败: {task.task_id}, {task.error}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 节点发现与连接
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_node_discovered(self, node: DiscoveredNode):
        """节点发现回调"""
        logger.info(f"[{self.node_id}] 发现节点: {node.node_id} @ {node.endpoint}")

        # 添加到选举
        self.election.add_peer(node.node_id)

        # 添加到节点交换
        self.peer_exchange.add_peer(
            node.node_id,
            node.endpoint,
            capabilities=list(node.capabilities),
            load=node.load,
        )

        # 连接到该节点
        ip, port = node.ip, node.port
        if ":" in node.endpoint:
            ip, port_str = node.endpoint.rsplit(":", 1)
            port = int(port_str)

        self.connection_pool.connect(ip, port, node.node_id)

        # 触发回调
        if self.on_node_discovered:
            self.on_node_discovered(node.node_id)

    def _on_node_lost(self, node_id: str):
        """节点丢失回调"""
        logger.info(f"[{self.node_id}] 节点丢失: {node_id}")

        # 记录心跳失败
        self.failure_recovery.record_heartbeat_failure(node_id)

        # 断开连接
        self.connection_pool.disconnect(node_id)

    def _on_new_peer(self, endpoint: str):
        """新节点回调"""
        # 尝试连接到新节点
        try:
            if ":" in endpoint:
                ip, port_str = endpoint.rsplit(":", 1)
                port = int(port_str)
                self.connection_pool.connect(ip, port)
        except:
            pass

    def _on_connected(self, node_id: str):
        """连接成功回调"""
        logger.info(f"[{self.node_id}] 已连接到: {node_id}")

        # 发送节点交换
        msg = self.peer_exchange.create_exchange_message()
        self.protocol.send_message(node_id, MessageType.PEER_EXCHANGE, msg)

        # 添加路由
        self.routing_table.add_neighbor(node_id, "")

    def _on_disconnected(self, node_id: str):
        """断开连接回调"""
        logger.info(f"[{self.node_id}] 断开连接: {node_id}")
        self.routing_table.remove_neighbor(node_id)

    def _on_neighbor_added(self, node_id: str):
        """邻居添加回调"""
        logger.debug(f"[{self.node_id}] 新邻居: {node_id}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 选举相关
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_become_coordinator(self):
        """成为协调者"""
        logger.info(f"[{self.node_id}] 🎉 成为协调者!")

    def _on_become_follower(self):
        """成为跟随者"""
        logger.info(f"[{self.node_id}] 成为跟随者")

    def _on_election_started(self, term: int):
        """选举开始"""
        logger.info(f"[{self.node_id}] 选举开始, term={term}")

    def _on_coordinator_changed(self, new_coord: Optional[str]):
        """协调者变更"""
        if self.on_coordinator_changed:
            self.on_coordinator_changed(new_coord)

        if new_coord == self.node_id:
            logger.info(f"[{self.node_id}] 我成为协调者")
        elif new_coord:
            logger.info(f"[{self.node_id}] 新协调者: {new_coord}")
        else:
            logger.warning(f"[{self.node_id}] 协调者故障，需要重新选举")

    def _on_election_message(self, msg):
        """选举消息"""
        # 通过连接池发送选举消息
        if msg.to_node:
            self.protocol.send_message(msg.to_node, MessageType.ELECTION, msg.payload)
        else:
            self.protocol.broadcast(MessageType.ELECTION, msg.payload)

    # ═══════════════════════════════════════════════════════════════════════════
    # 协议消息处理
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_protocol_send(self, to_node: str, data: bytes):
        """协议发送回调"""
        self.connection_pool.send(to_node, data)

    def _on_protocol_broadcast(self, data: bytes):
        """协议广播回调"""
        self.connection_pool.broadcast(data)

    def _on_connection_message(self, from_node: str, data: bytes):
        """连接消息回调"""
        msg = self.protocol.receive_message(data)
        if msg and self.on_message:
            self.on_message(from_node, msg.payload)

    def _handle_task_dispatch(self, msg):
        """处理任务分发消息"""
        payload = msg.payload
        task_id = payload.get("task_id")
        task_data = payload.get("task_data")

        logger.info(f"[{self.node_id}] 收到任务: {task_id}")

        # 创建任务并执行
        task = Task(
            task_id=task_id,
            task_type=payload.get("task_type"),
            task_data=task_data,
            requirements=payload.get("requirements", {}),
            priority=payload.get("priority", 5),
            submitter=msg.from_node,
            executor=self.node_id,
            state=TaskState.RUNNING,
            started_at=time.time(),
        )

        # 执行任务
        try:
            result = self._execute_task(task)
            self.task_distributor.complete_task(task_id, result)

            # 发送结果
            self.protocol.send_message(
                msg.from_node,
                MessageType.TASK_RESULT,
                {"task_id": task_id, "result": result, "success": True}
            )
        except Exception as e:
            logger.error(f"[{self.node_id}] 任务执行失败: {task_id}: {e}")
            self.task_distributor.fail_task(task_id, str(e))

            self.protocol.send_message(
                msg.from_node,
                MessageType.TASK_RESULT,
                {"task_id": task_id, "error": str(e), "success": False}
            )

    def _handle_task_result(self, msg):
        """处理任务结果"""
        payload = msg.payload
        task_id = payload.get("task_id")
        success = payload.get("success", False)

        if success:
            self.task_distributor.complete_task(task_id, payload.get("result"))
        else:
            self.task_distributor.fail_task(task_id, payload.get("error", ""))

    def _handle_load_report(self, msg):
        """处理负载上报"""
        payload = msg.payload
        from_node = msg.from_node

        self.load_balancer.update_node_load(
            from_node,
            load=payload.get("load", 0.5),
            cpu=payload.get("metrics", {}).get("cpu", 0),
            memory=payload.get("metrics", {}).get("memory", 0),
            queue=payload.get("metrics", {}).get("queue", 0),
            capabilities=payload.get("metrics", {}).get("capabilities", []),
        )

    def _handle_peer_exchange(self, msg):
        """处理节点交换"""
        self.peer_exchange.handle_exchange_message(msg.payload)

    # ═══════════════════════════════════════════════════════════════════════════
    # 辅助
    # ═══════════════════════════════════════════════════════════════════════════

    def _update_local_load(self):
        """更新本地负载"""
        # 这里应该从系统获取真实的 CPU、内存使用率
        # 简化处理：使用模拟值
        import random
        cpu = 0.2 + random.random() * 0.3  # 0.2 ~ 0.5
        mem = 0.3 + random.random() * 0.2  # 0.3 ~ 0.5

        queue = len(self.task_distributor.get_running_tasks())

        self.load_balancer.report_local_load(
            cpu=cpu,
            memory=mem,
            queue=queue,
        )

    def _broadcast_routing(self):
        """广播路由信息"""
        # 简化处理：路由信息通过 PEER_EXCHANGE 一起广播

    def _on_tasks_redistributed(self, failed_node: str, task_ids: List[str]):
        """任务重新分配回调"""
        logger.info(
            f"[{self.node_id}] 任务重新分配 (从 {failed_node}): {len(task_ids)}"
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # 状态
    # ═══════════════════════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """获取节点状态"""
        return {
            "node_id": self.node_id,
            "version": self.VERSION,
            "running": self._running,
            "role": self.election.role.value,
            "is_coordinator": self.election.is_coordinator,
            "coordinator": self.election.coordinator_id,
            "term": self.election.term,
            "connections": self.connection_pool.get_alive_connections().__len__(),
            "discoverer": self.discoverer.get_status(),
            "peer_exchange": self.peer_exchange.get_status(),
            "election": self.election.get_status(),
            "load_balancer": self.load_balancer.get_status(),
            "task_distributor": self.task_distributor.get_status(),
            "failure_recovery": self.failure_recovery.get_status(),
            "routing": self.routing_table.get_status(),
        }

    def get_peers(self) -> List[str]:
        """获取对等节点列表"""
        return list(self.connection_pool.get_alive_connections().keys())
