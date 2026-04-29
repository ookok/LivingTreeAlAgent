"""
领导者选举算法 - Leader Election

实现 Bully 算法 + Raft 心跳机制：

1. Bully 算法：
   - 节点ID最大的成为领导者
   - 所有节点都知道领导者是谁
   - 领导者故障时自动重新选举

2. 心跳机制：
   - 领导者定期发送心跳
   - 其他节点检测心跳超时触发选举

节点角色：
- FOLLOWER: 跟随者
- CANDIDATE: 候选者（选举中）
- COORDINATOR: 协调者/领导者

使用示例：
```python
election = Election(node_id="node-001")

# 设置回调
election.on_become_coordinator = lambda: print("我成为领导者了")
election.on_become_follower = lambda: print("我变成跟随者了")

# 启动
election.start()

# 模拟节点发现
election.add_peer("node-002")
election.add_peer("node-003")

# 主动发起选举（可选）
election.start_election()
```
"""

import time
import logging
import uuid
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from threading import Thread, RLock

logger = logging.getLogger(__name__)


class NodeRole(Enum):
    """节点角色"""
    FOLLOWER = "FOLLOWER"       # 跟随者
    CANDIDATE = "CANDIDATE"     # 候选者
    COORDINATOR = "COORDINATOR" # 协调者/领导者


class ElectionMessageType(Enum):
    """选举消息类型"""
    ELECTION = "ELECTION"           # 发起选举
    ELECTION_OK = "ELECTION_OK"     # 选举响应
    COORDINATOR = "COORDINATOR"    # 协调者声明
    HEARTBEAT = "HEARTBEAT"        # 心跳
    VOTE_REQUEST = "VOTE_REQUEST"  # 投票请求（Raft风格）
    VOTE_RESPONSE = "VOTE_RESPONSE"  # 投票响应


@dataclass
class ElectionMessage:
    """选举消息"""
    msg_type: ElectionMessageType
    from_node_id: str
    to_node_id: str = ""  # 空表示广播
    term: int = 0         # 任期号（Raft风格）
    node_load: float = 0.0
    timestamp: float = field(default_factory=time.time)
    node_count: int = 0    # 节点数量
    payload: Dict[str, Any] = field(default_factory=dict)


class Election:
    """
    领导者选举（结合 Bully + Raft）

    选举规则：
    1. 节点启动时都是 FOLLOWER
    2. FOLLOWER 收不到心跳则变成 CANDIDATE 并发起选举
    3. CANDIDATE 获得多数票成为 COORDINATOR
    4. 节点ID最大的成为 COORDINATOR（Bully 规则）
    5. COORDINATOR 故障 → 重新选举

    选举优先级：
    1. 任期号（term）更高的优先
    2. 任期号相同，节点ID更大的优先（Bully）
    """

    # 心跳间隔（秒）
    HEARTBEAT_INTERVAL = 2.0

    # 心跳超时（秒），超过此时间没收到心跳则发起选举
    HEARTBEAT_TIMEOUT = 6.0

    # 选举超时（秒）
    ELECTION_TIMEOUT = 3.0

    # 最大任期号
    MAX_TERM = 1000000

    def __init__(
        self,
        node_id: str,
        heartbeat_interval: float = None,
        heartbeat_timeout: float = None,
    ):
        self.node_id = node_id
        self.heartbeat_interval = heartbeat_interval or self.HEARTBEAT_INTERVAL
        self.heartbeat_timeout = heartbeat_timeout or self.HEARTBEAT_TIMEOUT

        # 角色
        self._role = NodeRole.FOLLOWER
        self._lock = RLock()

        # 选举相关
        self._current_term = 0
        self._voted_for: Optional[str] = None
        self._coordinator_id: Optional[str] = None

        # 投票记录
        self._votes_received: Set[str] = set()

        # 已知节点
        self._peers: Set[str] = set()

        # 心跳
        self._last_heartbeat: float = time.time()
        self._heartbeat_thread: Optional[Thread] = None
        self._running = False

        # 回调
        self.on_become_coordinator: Optional[Callable[[], None]] = None
        self.on_become_candidate: Optional[Callable[[], None]] = None
        self.on_become_follower: Optional[Callable[[], None]] = None
        self.on_election_started: Optional[Callable[[int], None]] = None
        self.on_coordinator_changed: Optional[Callable[[Optional[str]], None]] = None
        self.on_message: Optional[Callable[[ElectionMessage], None]] = None

    @property
    def role(self) -> NodeRole:
        """获取当前角色"""
        with self._lock:
            return self._role

    @property
    def is_coordinator(self) -> bool:
        """是否是协调者"""
        return self.role == NodeRole.COORDINATOR

    @property
    def coordinator_id(self) -> Optional[str]:
        """获取协调者ID"""
        with self._lock:
            return self._coordinator_id

    @property
    def term(self) -> int:
        """获取当前任期"""
        with self._lock:
            return self._current_term

    def add_peer(self, peer_id: str):
        """添加对等节点"""
        with self._lock:
            self._peers.add(peer_id)
            logger.info(f"[{self.node_id}] 添加选举节点: {peer_id}")

    def remove_peer(self, peer_id: str):
        """移除对等节点"""
        with self._lock:
            self._peers.discard(peer_id)
            logger.info(f"[{self.node_id}] 移除选举节点: {peer_id}")

    def set_peers(self, peer_ids: Set[str]):
        """设置所有对等节点"""
        with self._lock:
            self._peers = peer_ids.copy()
            logger.info(f"[{self.node_id}] 设置选举节点: {peer_ids}")

    def start(self):
        """启动选举服务"""
        if self._running:
            return

        self._running = True
        self._last_heartbeat = time.time()

        # 启动心跳检测线程
        self._heartbeat_thread = Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

        logger.info(f"[{self.node_id}] 选举服务已启动, 角色: {self._role.value}")

    def stop(self):
        """停止选举服务"""
        self._running = False
        logger.info(f"[{self.node_id}] 选举服务已停止")

    def _heartbeat_loop(self):
        """心跳检测循环"""
        while self._running:
            try:
                self._check_heartbeat()
                time.sleep(self.heartbeat_interval)
            except Exception as e:
                logger.error(f"[{self.node_id}] 心跳循环错误: {e}")

    def _check_heartbeat(self):
        """检查心跳"""
        with self._lock:
            if self._role == NodeRole.COORDINATOR:
                # 协调者发送心跳
                self._send_heartbeat()
                self._last_heartbeat = time.time()

            elif self._role in (NodeRole.FOLLOWER, NodeRole.CANDIDATE):
                # 跟随者/候选者检测心跳超时
                elapsed = time.time() - self._last_heartbeat

                if elapsed > self.heartbeat_timeout:
                    logger.info(
                        f"[{self.node_id}] 心跳超时 ({elapsed:.1f}s), "
                        f"发起选举"
                    )
                    self._start_election_internal()

    def _send_heartbeat(self):
        """发送心跳"""
        msg = ElectionMessage(
            msg_type=ElectionMessageType.HEARTBEAT,
            from_node_id=self.node_id,
            term=self._current_term,
            node_load=0.0,
            node_count=len(self._peers) + 1,
        )

        logger.debug(f"[{self.node_id}] 发送心跳, term={self._current_term}")

        if self.on_message:
            self.on_message(msg)

    def _start_election_internal(self):
        """内部：开始选举"""
        with self._lock:
            self._become_candidate()

        self.start_election()

    def start_election(self):
        """
        发起选举（手动触发或超时触发）

        Bully 算法：
        1. 增加 term
        2. 给自己投票
        3. 向所有比自己ID大的节点发送 ELECTION
        4. 如果没人响应，自己成为协调者
        5. 如果收到比自己ID大的节点的协调者声明，承认其地位
        """
        with self._lock:
            # 已经是协调者
            if self._role == NodeRole.COORDINATOR:
                return

            # 已经是候选者，正在选举中
            if self._role == NodeRole.CANDIDATE:
                return

            self._become_candidate()

        # 增加任期号
        with self._lock:
            self._current_term += 1
            term = self._current_term

        logger.info(f"[{self.node_id}] 发起选举, term={term}")

        # 给自己投票
        with self._lock:
            self._votes_received.add(self.node_id)
            self._voted_for = self.node_id

        if self.on_election_started:
            self.on_election_started(term)

        # 向所有节点发送选举请求
        # Bully: 只向 ID 比自己大的节点发送
        msg = ElectionMessage(
            msg_type=ElectionMessageType.ELECTION,
            from_node_id=self.node_id,
            term=term,
            node_load=0.0,
            node_count=len(self._peers) + 1,
        )

        if self.on_message:
            self.on_message(msg)

        # 启动超时检测（如果在 ELECTION_TIMEOUT 内没收到足够票数，重新选举）
        Thread(target=self._election_timeout, args=(term,), daemon=True).start()

    def _become_candidate(self):
        """成为候选者"""
        with self._lock:
            if self._role == NodeRole.CANDIDATE:
                return

            old_role = self._role
            self._role = NodeRole.CANDIDATE
            self._votes_received.clear()

        logger.info(f"[{self.node_id}] 角色变更: {old_role} -> CANDIDATE")

        if self.on_become_candidate:
            self.on_become_candidate()

    def handle_message(self, msg: ElectionMessage):
        """
        处理选举消息

        Args:
            msg: 选举消息
        """
        with self._lock:
            msg_term = msg.term
            msg_from = msg.from_node_id

            # 任期号比较
            if msg_term > self._current_term:
                # 发现更高任期，更新自己的任期
                self._current_term = msg_term
                if self._role == NodeRole.COORDINATOR:
                    self._become_follower()

            # 处理不同类型的消息
            if msg.msg_type == ElectionMessageType.ELECTION:
                self._handle_election(msg)
            elif msg.msg_type == ElectionMessageType.ELECTION_OK:
                self._handle_election_ok(msg)
            elif msg.msg_type == ElectionMessageType.COORDINATOR:
                self._handle_coordinator(msg)
            elif msg.msg_type == ElectionMessageType.HEARTBEAT:
                self._handle_heartbeat(msg)
            elif msg.msg_type == ElectionMessageType.VOTE_REQUEST:
                self._handle_vote_request(msg)
            elif msg.msg_type == ElectionMessageType.VOTE_RESPONSE:
                self._handle_vote_response(msg)

    def _handle_election(self, msg: ElectionMessage):
        """处理 ELECTION 消息"""
        with self._lock:
            # Bully 规则：如果收到比自己 ID 大的节点的选举请求，回复 OK
            if msg.from_node_id > self.node_id:
                logger.info(
                    f"[{self.node_id}] 收到 {msg.from_node_id} 的选举请求，回复 OK"
                )

                # 重置心跳
                self._last_heartbeat = time.time()

                # 发送 ELECTION_OK
                response = ElectionMessage(
                    msg_type=ElectionMessageType.ELECTION_OK,
                    from_node_id=self.node_id,
                    to_node_id=msg.from_node_id,
                    term=msg.term,
                )
                if self.on_message:
                    self.on_message(response)
            else:
                logger.debug(
                    f"[{self.node_id}] 忽略 {msg.from_node_id} 的选举请求 "
                    f"（ID小于等于自己）"
                )

    def _handle_election_ok(self, msg: ElectionMessage):
        """处理 ELECTION_OK 消息"""
        with self._lock:
            if self._role != NodeRole.CANDIDATE:
                return

            if msg.term != self._current_term:
                # 任期不匹配，忽略
                return

            # 记录投票
            self._votes_received.add(msg.from_node_id)

            # 计算是否获得多数票
            quorum = (len(self._peers) + 1) // 2 + 1

            logger.info(
                f"[{self.node_id}] 收到投票: {msg.from_node_id}, "
                f"当前票数: {len(self._votes_received)}/{quorum}"
            )

            if len(self._votes_received) >= quorum:
                self._become_coordinator()

    def _handle_coordinator(self, msg: ElectionMessage):
        """处理 COORDINATOR 消息"""
        with self._lock:
            # 更新协调者
            old_coord = self._coordinator_id
            self._coordinator_id = msg.from_node_id
            self._role = NodeRole.FOLLOWER
            self._last_heartbeat = time.time()

        logger.info(
            f"[{self.node_id}] 协调者变更: {old_coord} -> {msg.from_node_id}, "
            f"term={msg.term}"
        )

        if self.on_coordinator_changed:
            self.on_coordinator_changed(msg.from_node_id)

    def _handle_heartbeat(self, msg: ElectionMessage):
        """处理心跳"""
        with self._lock:
            self._last_heartbeat = time.time()

            # 如果收到协调者的心跳
            if msg.from_node_id == self._coordinator_id:
                logger.debug(
                    f"[{self.node_id}] 收到协调者心跳, term={msg.term}"
                )

    def _handle_vote_request(self, msg: ElectionMessage):
        """处理投票请求（Raft 风格）"""
        with self._lock:
            # 检查是否可以投票
            can_vote = (
                self._voted_for is None or
                self._voted_for == msg.from_node_id or
                msg.term > self._current_term
            )

            if can_vote and msg.term >= self._current_term:
                self._voted_for = msg.from_node_id
                self._last_heartbeat = time.time()

                response = ElectionMessage(
                    msg_type=ElectionMessageType.VOTE_RESPONSE,
                    from_node_id=self.node_id,
                    to_node_id=msg.from_node_id,
                    term=self._current_term,
                    payload={"vote_granted": True},
                )
            else:
                response = ElectionMessage(
                    msg_type=ElectionMessageType.VOTE_RESPONSE,
                    from_node_id=self.node_id,
                    to_node_id=msg.from_node_id,
                    term=self._current_term,
                    payload={"vote_granted": False},
                )

        if self.on_message:
            self.on_message(response)

    def _handle_vote_response(self, msg: ElectionMessage):
        """处理投票响应"""
        with self._lock:
            if self._role != NodeRole.CANDIDATE:
                return

            if msg.term != self._current_term:
                return

            granted = msg.payload.get("vote_granted", False)
            if granted:
                self._votes_received.add(msg.from_node_id)

                # 检查是否获得多数票
                quorum = (len(self._peers) + 1) // 2 + 1
                if len(self._votes_received) >= quorum:
                    self._become_coordinator()

    def _become_follower(self):
        """成为跟随者"""
        with self._lock:
            old_role = self._role
            self._role = NodeRole.FOLLOWER
            self._votes_received.clear()

        logger.info(f"[{self.node_id}] 角色变更: {old_role} -> FOLLOWER")

        if self.on_become_follower:
            self.on_become_follower()

    def _become_coordinator(self):
        """成为协调者"""
        with self._lock:
            old_role = self._role
            old_coord = self._coordinator_id

            self._role = NodeRole.COORDINATOR
            self._coordinator_id = self.node_id
            self._votes_received.clear()
            self._last_heartbeat = time.time()

        logger.info(
            f"[{self.node_id}] 🎉 成为协调者! term={self._current_term}"
        )

        if self.on_become_coordinator:
            self.on_become_coordinator()

        if self.on_coordinator_changed:
            self.on_coordinator_changed(self.node_id)

        # 向所有节点广播协调者声明
        msg = ElectionMessage(
            msg_type=ElectionMessageType.COORDINATOR,
            from_node_id=self.node_id,
            term=self._current_term,
            node_count=len(self._peers) + 1,
        )

        if self.on_message:
            self.on_message(msg)

    def _election_timeout(self, term: int):
        """选举超时处理"""
        time.sleep(self.ELECTION_TIMEOUT)

        with self._lock:
            # 检查是否已经是协调者或任期已变化
            if self._role == NodeRole.COORDINATOR:
                return
            if term != self._current_term:
                return

        # 票数不够，重新选举
        logger.info(
            f"[{self.node_id}] 选举超时，票数不足，重新发起选举"
        )
        self.start_election()

    def force_election(self):
        """强制发起选举（用于测试或手动触发）"""
        self._start_election_internal()

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        with self._lock:
            return {
                "node_id": self.node_id,
                "role": self._role.value,
                "term": self._current_term,
                "coordinator_id": self._coordinator_id,
                "is_coordinator": self._role == NodeRole.COORDINATOR,
                "votes_received": list(self._votes_received),
                "peer_count": len(self._peers),
                "last_heartbeat": self._last_heartbeat,
                "time_since_heartbeat": time.time() - self._last_heartbeat,
            }
