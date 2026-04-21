"""
Fault Tolerance System - Consensus Protocol
强容错分布式任务处理系统 - 一致性协议

实现Gossip、Raft等一致性协议
"""

import asyncio
import json
import logging
import random
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from threading import Lock

from .models import (
    Node, NodeStatus, NodeRole,
    ConsensusAlgorithm, NetworkPartition
)


logger = logging.getLogger(__name__)


class MessageType(Enum):
    """消息类型"""
    HEARTBEAT = "heartbeat"
    VOTE_REQUEST = "vote_request"
    VOTE_RESPONSE = "vote_response"
    APPEND_ENTRIES = "append_entries"
    APPEND_RESPONSE = "append_response"
    GOSSIP = "gossip"
    GOSSIP_RESPONSE = "gossip_response"
    STATE_SYNC = "state_sync"
    PARTITION_DETECT = "partition_detect"


@dataclass
class Message:
    """消息"""
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    msg_type: MessageType = MessageType.HEARTBEAT
    sender_id: str = ""
    receiver_id: Optional[str] = None  # None表示广播
    
    # Raft相关
    term: int = 0
    leader_id: Optional[str] = None
    
    # 数据
    data: Dict[str, Any] = field(default_factory=dict)
    
    # 时间戳
    timestamp: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None


class ConsensusProtocol(ABC):
    """一致性协议基类"""
    
    def __init__(self, node: Node):
        self.node = node
        self._lock = Lock()
        self._running = False
    
    @abstractmethod
    async def start(self) -> None:
        """启动协议"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止协议"""
        pass
    
    @abstractmethod
    async def send_message(self, message: Message) -> bool:
        """发送消息"""
        pass
    
    @abstractmethod
    def is_leader(self) -> bool:
        """是否是领导者"""
        pass
    
    @abstractmethod
    def get_leader(self) -> Optional[str]:
        """获取领导者"""
        pass


class GossipProtocol(ConsensusProtocol):
    """
    Gossip协议实现
    
    特点:
    - 最终一致性
    - 去中心化
    - 容错性强
    - 扩展性好
    """
    
    def __init__(self, node: Node):
        super().__init__(node)
        
        # Gossip配置
        self.fanout = 3  # 每轮传播目标数
        self.interval = 1.0  # 传播间隔(秒)
        self.ttl = 3  # 消息TTL
        self.max_state_size = 1000  # 最大状态条目数
        
        # 状态
        self._known_states: Dict[str, Dict[str, Any]] = {}  # topic -> state
        self._state_metadata: Dict[str, Dict[str, Any]] = {}  # topic -> metadata
        self._message_buffer: Dict[str, Set[str]] = {}  # msg_id -> received_from
        
        # 节点视图(部分视图)
        self._peers: Dict[str, Node] = {}
        self._peer_weights: Dict[str, float] = {}  # 节点权重
        
        # 统计
        self.messages_sent = 0
        self.messages_received = 0
        self.state_sync_count = 0
    
    async def start(self) -> None:
        """启动Gossip协议"""
        self._running = True
        asyncio.create_task(self._gossip_loop())
        logger.info(f"Gossip protocol started for node {self.node.node_id}")
    
    async def stop(self) -> None:
        """停止Gossip协议"""
        self._running = False
        logger.info(f"Gossip protocol stopped for node {self.node.node_id}")
    
    def add_peer(self, peer: Node) -> None:
        """添加对等节点"""
        with self._lock:
            self._peers[peer.node_id] = peer
            # 初始权重为可靠性分数
            self._peer_weights[peer.node_id] = peer.reliability_score / 100
    
    def remove_peer(self, peer_id: str) -> None:
        """移除对等节点"""
        with self._lock:
            self._peers.pop(peer_id, None)
            self._peer_weights.pop(peer_id, None)
    
    def update_state(self, topic: str, state: Dict[str, Any],
                     metadata: Optional[Dict[str, Any]] = None) -> None:
        """更新本地状态"""
        with self._lock:
            self._known_states[topic] = state
            self._state_metadata[topic] = {
                'version': self._state_metadata.get(topic, {}).get('version', 0) + 1,
                'updated_at': datetime.now().isoformat(),
                'updated_by': self.node.node_id,
                **(metadata or {})
            }
            
            # 限制状态大小
            if len(self._known_states) > self.max_state_size:
                self._prune_old_states()
    
    def get_state(self, topic: str) -> Optional[Dict[str, Any]]:
        """获取状态"""
        with self._lock:
            return self._known_states.get(topic)
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """获取所有状态"""
        with self._lock:
            return dict(self._known_states)
    
    async def send_message(self, message: Message) -> bool:
        """发送消息(广播)"""
        message.sender_id = self.node.node_id
        message.msg_type = MessageType.GOSSIP
        
        # 选择目标节点
        targets = self._select_targets(self.fanout)
        
        for target_id in targets:
            asyncio.create_task(self._send_to_peer(target_id, message))
        
        return len(targets) > 0
    
    def is_leader(self) -> bool:
        """Gossip无领导者"""
        return False
    
    def get_leader(self) -> Optional[str]:
        """Gossip无领导者"""
        return None
    
    async def _gossip_loop(self) -> None:
        """Gossip传播循环"""
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                
                # 选择要传播的主题
                topics = list(self._known_states.keys())
                if not topics:
                    continue
                
                topic = random.choice(topics)
                
                # 构建消息
                message = Message(
                    msg_type=MessageType.GOSSIP,
                    sender_id=self.node.node_id,
                    data={
                        'topic': topic,
                        'state': self._known_states[topic],
                        'metadata': self._state_metadata.get(topic, {}),
                        'ttl': self.ttl
                    }
                )
                
                # 传播
                await self.send_message(message)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Gossip loop error: {e}")
    
    def _select_targets(self, count: int) -> List[str]:
        """选择目标节点"""
        with self._lock:
            if not self._peers:
                return []
            
            # 过滤活跃节点
            active_peers = [
                pid for pid, peer in self._peers.items()
                if peer.status == NodeStatus.ACTIVE
            ]
            
            if len(active_peers) <= count:
                return active_peers
            
            # 基于权重的选择
            weights = [self._peer_weights.get(pid, 1.0) for pid in active_peers]
            total_weight = sum(weights)
            
            if total_weight == 0:
                return random.sample(active_peers, count)
            
            # 加权随机选择
            targets = []
            remaining = active_peers.copy()
            
            for _ in range(count):
                r = random.uniform(0, total_weight)
                cumsum = 0
                
                for i, pid in enumerate(remaining):
                    cumsum += weights[active_peers.index(pid)]
                    if cumsum >= r:
                        targets.append(pid)
                        remaining.remove(pid)
                        total_weight -= weights[active_peers.index(pid)]
                        break
            
            return targets
    
    async def _send_to_peer(self, peer_id: str, message: Message) -> None:
        """发送消息到对等节点"""
        # 实际实现需要通过网络层
        # 这里只是日志记录
        logger.debug(f"Gossip: {self.node.node_id} -> {peer_id}")
        self.messages_sent += 1
    
    async def receive_message(self, message: Message) -> None:
        """接收消息"""
        self.messages_received += 1
        
        with self._lock:
            # 检查是否已处理
            if message.msg_id in self._message_buffer:
                return
            
            if message.msg_id not in self._message_buffer:
                self._message_buffer[message.msg_id] = set()
            self._message_buffer[message.msg_id].add(message.sender_id)
        
        if message.msg_type == MessageType.GOSSIP:
            await self._handle_gossip(message)
    
    async def _handle_gossip(self, message: Message) -> None:
        """处理Gossip消息"""
        data = message.data
        topic = data.get('topic')
        state = data.get('state')
        metadata = data.get('metadata', {})
        ttl = data.get('ttl', 0)
        
        if not topic or not state:
            return
        
        # 比较版本，决定是否更新
        with self._lock:
            local_meta = self._state_metadata.get(topic, {})
            remote_version = metadata.get('version', 0)
            local_version = local_meta.get('version', 0)
            
            if remote_version > local_version:
                # 更新本地状态
                self._known_states[topic] = state
                self._state_metadata[topic] = metadata
                self.state_sync_count += 1
                
                logger.debug(f"Gossip state update: {topic} v{remote_version}")
                
                # 继续传播(TTL > 0)
                if ttl > 0:
                    new_message = Message(
                        msg_type=MessageType.GOSSIP,
                        sender_id=self.node.node_id,
                        data={
                            'topic': topic,
                            'state': state,
                            'metadata': metadata,
                            'ttl': ttl - 1
                        }
                    )
                    await self.send_message(new_message)
    
    def _prune_old_states(self) -> None:
        """清理旧状态"""
        # 按更新时间排序，删除最旧的
        sorted_topics = sorted(
            self._state_metadata.items(),
            key=lambda x: x[1].get('updated_at', '')
        )
        
        # 删除最旧的50%
        to_remove = len(sorted_topics) // 2
        for topic, _ in sorted_topics[:to_remove]:
            self._known_states.pop(topic, None)
            self._state_metadata.pop(topic, None)


class RaftProtocol(ConsensusProtocol):
    """
    Raft协议实现
    
    特点:
    - 强一致性
    - 领导者选举
    - 日志复制
    - 成员变更
    """
    
    def __init__(self, node: Node):
        super().__init__(node)
        
        # Raft配置
        self.election_timeout_min = 1.5  # 选举超时最小值(秒)
        self.election_timeout_max = 3.0   # 选举超时最大值(秒)
        self.heartbeat_interval = 0.5      # 心跳间隔(秒)
        
        # 角色
        self._role: NodeRole = NodeRole.WORKER
        self._term = 0
        self._voted_for: Optional[str] = None
        self._leader_id: Optional[str] = None
        
        # 日志
        self._log: List[Dict[str, Any]] = []
        self._commit_index = 0
        self._last_applied = 0
        
        # 节点信息
        self._peers: Dict[str, Node] = {}
        self._next_index: Dict[str, int] = {}  # 对于每个节点，下一个要复制的日志索引
        self._match_index: Dict[str, int] = {}  # 对于每个节点，已复制匹配的最高索引
        
        # 选举计时器
        self._last_heartbeat: Optional[datetime] = None
        self._election_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # 回调
        self._apply_callback: Optional[Callable] = None
    
    async def start(self) -> None:
        """启动Raft协议"""
        self._running = True
        self._last_heartbeat = datetime.now()
        
        # 成为候选者，开始选举计时
        self._role = NodeRole.CANDIDATE if self.node.role == NodeRole.WORKER else self.node.role
        self._election_task = asyncio.create_task(self._election_loop())
        
        logger.info(f"Raft protocol started for node {self.node.node_id}")
    
    async def stop(self) -> None:
        """停止Raft协议"""
        self._running = False
        
        if self._election_task:
            self._election_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        
        logger.info(f"Raft protocol stopped for node {self.node.node_id}")
    
    def add_peer(self, peer: Node) -> None:
        """添加对等节点"""
        with self._lock:
            self._peers[peer.node_id] = peer
            self._next_index[peer.node_id] = len(self._log) + 1
            self._match_index[peer.node_id] = 0
    
    def set_apply_callback(self, callback: Callable) -> None:
        """设置应用回调"""
        self._apply_callback = callback
    
    async def propose(self, command: Dict[str, Any]) -> bool:
        """提议(仅领导者)"""
        if not self.is_leader():
            return False
        
        # 添加到本地日志
        with self._lock:
            entry = {
                'term': self._term,
                'command': command,
                'index': len(self._log) + 1
            }
            self._log.append(entry)
        
        # 复制到其他节点
        await self._replicate_log()
        
        return True
    
    async def send_message(self, message: Message) -> bool:
        """发送消息"""
        message.sender_id = self.node.node_id
        message.term = self._term
        
        # 实际实现需要通过网络层
        return True
    
    def is_leader(self) -> bool:
        """是否是领导者"""
        return self._role == NodeRole.COORDINATOR and self._leader_id == self.node.node_id
    
    def get_leader(self) -> Optional[str]:
        """获取领导者"""
        return self._leader_id
    
    def get_role(self) -> NodeRole:
        """获取当前角色"""
        return self._role
    
    def get_term(self) -> int:
        """获取当前任期"""
        return self._term
    
    async def _election_loop(self) -> None:
        """选举循环"""
        while self._running:
            try:
                # 等待选举超时
                timeout = random.uniform(
                    self.election_timeout_min,
                    self.election_timeout_max
                )
                await asyncio.sleep(timeout)
                
                # 检查是否应该发起选举
                if self._role != NodeRole.COORDINATOR:
                    await self._start_election()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Election loop error: {e}")
    
    async def _start_election(self) -> None:
        """开始选举"""
        with self._lock:
            self._term += 1
            self._role = NodeRole.CANDIDATE
            self._voted_for = self.node.node_id
            self._last_heartbeat = datetime.now()
        
        logger.info(f"Node {self.node.node_id} starting election for term {self._term}")
        
        # 发送投票请求
        votes = 1  # 自己投自己
        
        for peer_id, peer in list(self._peers.items()):
            granted = await self._request_vote(peer)
            if granted:
                votes += 1
        
        # 检查是否获得多数票
        majority = len(self._peers) // 2 + 1
        if votes >= majority:
            await self._become_leader()
        else:
            # 选举失败，回到跟随者
            with self._lock:
                self._role = NodeRole.WORKER
    
    async def _request_vote(self, peer: Node) -> bool:
        """请求投票"""
        # 实际实现需要发送RPC
        last_log_index = len(self._log)
        last_log_term = self._log[-1]['term'] if self._log else 0
        
        # 模拟投票响应
        # 在实际实现中，这应该是一个RPC调用
        return random.random() > 0.5  # 简化模拟
    
    async def _become_leader(self) -> None:
        """成为领导者"""
        with self._lock:
            self._role = NodeRole.COORDINATOR
            self._leader_id = self.node.node_id
            self.node.role = NodeRole.COORDINATOR
            self.node.is_leader = True
        
        logger.info(f"Node {self.node.node_id} became leader for term {self._term}")
        
        # 停止选举计时器，启动心跳
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        # 初始化复制状态
        for peer_id in self._peers:
            self._next_index[peer_id] = len(self._log) + 1
            self._match_index[peer_id] = 0
    
    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        while self._running and self.is_leader():
            try:
                await self._send_heartbeat()
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
    
    async def _send_heartbeat(self) -> None:
        """发送心跳"""
        for peer_id in self._peers:
            await self._send_append_entries(peer_id)
    
    async def _send_append_entries(self, peer_id: str) -> None:
        """发送追加条目"""
        # 实际实现需要发送RPC
        pass
    
    async def _replicate_log(self) -> None:
        """复制日志到其他节点"""
        if not self.is_leader():
            return
        
        for peer_id in self._peers:
            await self._replicate_to_peer(peer_id)
    
    async def _replicate_to_peer(self, peer_id: str) -> None:
        """复制日志到指定节点"""
        # 实际实现需要发送RPC
        pass
    
    async def handle_vote_request(self, request: Dict[str, Any]) -> bool:
        """处理投票请求"""
        term = request.get('term', 0)
        candidate_id = request.get('candidate_id')
        last_log_index = request.get('last_log_index', 0)
        last_log_term = request.get('last_log_term', 0)
        
        with self._lock:
            # 如果term更小，转换为跟随者
            if term > self._term:
                self._term = term
                self._role = NodeRole.WORKER
                self._voted_for = None
            
            # 检查是否可以投票
            if term >= self._term:
                if self._voted_for is None or self._voted_for == candidate_id:
                    # 检查日志是否至少一样新
                    if last_log_index >= len(self._log):
                        self._voted_for = candidate_id
                        self._last_heartbeat = datetime.now()
                        return True
        
        return False
    
    async def handle_append_entries(self, entries: List[Dict[str, Any]]) -> bool:
        """处理追加条目"""
        # 实际实现需要处理日志复制
        return True


# 全局协议管理器
_protocol_registry: Dict[str, ConsensusProtocol] = {}


def get_protocol(node: Node, algorithm: ConsensusAlgorithm) -> ConsensusProtocol:
    """获取一致性协议实例"""
    if algorithm == ConsensusAlgorithm.GOSSIP:
        return GossipProtocol(node)
    elif algorithm in (ConsensusAlgorithm.RAFT, ConsensusAlgorithm.PAXOS):
        return RaftProtocol(node)
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
