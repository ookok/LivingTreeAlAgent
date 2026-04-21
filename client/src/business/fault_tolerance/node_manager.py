"""
Fault Tolerance System - Node Manager
强容错分布式任务处理系统 - 节点管理器

管理分布式节点的生命周期、健康状态、选举
"""

import asyncio
import json
import logging
import psutil
import random
import socket
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set
from threading import Lock

from .models import (
    Node, NodeStatus, NodeRole, 
    ConsensusAlgorithm, Fault, FaultType
)
from .fault_detector import FaultDetector, get_fault_detector
from .consensus_protocol import (
    ConsensusProtocol, GossipProtocol, RaftProtocol,
    get_protocol, Message, MessageType
)


logger = logging.getLogger(__name__)


class NodeManager:
    """
    节点管理器
    
    功能:
    - 节点注册与注销
    - 心跳管理
    - 健康监控
    - 领导者选举
    - 节点分组
    """
    
    def __init__(self, node: Optional[Node] = None,
                 consensus_algorithm: ConsensusAlgorithm = ConsensusAlgorithm.RAFT):
        # 初始化本节点
        self._node = node or self._create_local_node()
        
        # 协议配置
        self._consensus_algorithm = consensus_algorithm
        self._consensus_protocol: Optional[ConsensusProtocol] = None
        
        # 节点管理
        self._nodes: Dict[str, Node] = {}
        self._nodes_lock = Lock()
        
        # 心跳配置
        self._heartbeat_interval = 1.0  # 秒
        self._heartbeat_timeout = 5.0   # 秒
        
        # 故障检测器
        self._fault_detector = get_fault_detector()
        
        # 回调函数
        self._node_callbacks: Dict[str, List[Callable]] = {
            'node_joined': [],
            'node_left': [],
            'leader_changed': [],
            'health_changed': [],
        }
        
        # 状态
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        
        # 注册本节点
        self.register_node(self._node)
    
    # ==================== 公共API ====================
    
    def get_node(self) -> Node:
        """获取本节点"""
        return self._node
    
    def get_node_id(self) -> str:
        """获取本节点ID"""
        return self._node.node_id
    
    def register_node(self, node: Node) -> None:
        """注册节点"""
        with self._nodes_lock:
            self._nodes[node.node_id] = node
        
        # 注册到故障检测器
        self._fault_detector.register_node(node)
        
        # 触发回调
        self._trigger_callback('node_joined', node)
        
        logger.info(f"Node registered: {node.node_id} ({node.role.value})")
    
    def unregister_node(self, node_id: str) -> bool:
        """注销节点"""
        with self._nodes_lock:
            node = self._nodes.pop(node_id, None)
        
        if node:
            # 从故障检测器移除
            self._fault_detector.unregister_node(node_id)
            
            # 触发回调
            self._trigger_callback('node_left', node)
            
            logger.info(f"Node unregistered: {node_id}")
            return True
        
        return False
    
    def get_node_info(self, node_id: str) -> Optional[Node]:
        """获取节点信息"""
        with self._nodes_lock:
            return self._nodes.get(node_id)
    
    def get_all_nodes(self) -> List[Node]:
        """获取所有节点"""
        with self._nodes_lock:
            return list(self._nodes.values())
    
    def get_active_nodes(self) -> List[Node]:
        """获取活跃节点"""
        with self._nodes_lock:
            return [
                n for n in self._nodes.values()
                if n.status == NodeStatus.ACTIVE
            ]
    
    def get_nodes_by_role(self, role: NodeRole) -> List[Node]:
        """按角色获取节点"""
        with self._nodes_lock:
            return [
                n for n in self._nodes.values()
                if n.role == role
            ]
    
    def get_coordinator(self) -> Optional[Node]:
        """获取协调节点"""
        with self._nodes_lock:
            for node in self._nodes.values():
                if node.role == NodeRole.COORDINATOR and node.status == NodeStatus.ACTIVE:
                    return node
        return None
    
    def is_coordinator(self) -> bool:
        """是否是协调节点"""
        return self._node.role == NodeRole.COORDINATOR
    
    def update_node_status(self, node_id: str, status: NodeStatus) -> None:
        """更新节点状态"""
        with self._nodes_lock:
            if node_id in self._nodes:
                node = self._nodes[node_id]
                old_status = node.status
                node.status = status
                node.updated_at = datetime.now()
                
                # 触发健康变化回调
                if old_status != status:
                    self._trigger_callback('health_changed', node, old_status)
                
                # 特殊处理协调节点故障
                if node.role == NodeRole.COORDINATOR and status == NodeStatus.PERMANENT_FAILURE:
                    asyncio.create_task(self._handle_coordinator_failure())
    
    def update_local_resources(self) -> None:
        """更新本地资源使用"""
        try:
            self._node.cpu_usage = psutil.cpu_percent(interval=0.1)
            self._node.memory_usage = psutil.virtual_memory().percent
            
            memory = psutil.virtual_memory()
            self._node.memory_gb = memory.total / (1024**3)
            
        except Exception as e:
            logger.error(f"Failed to update local resources: {e}")
    
    def register_callback(self, event: str, callback: Callable) -> None:
        """注册节点事件回调"""
        if event in self._node_callbacks:
            self._node_callbacks[event].append(callback)
    
    async def start(self) -> None:
        """启动节点管理器"""
        if self._running:
            return
        
        self._running = True
        
        # 启动共识协议
        self._consensus_protocol = get_protocol(self._node, self._consensus_algorithm)
        await self._consensus_protocol.start()
        
        # 启动心跳
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        # 启动监控
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        logger.info(f"Node manager started: {self._node.node_id}")
    
    async def stop(self) -> None:
        """停止节点管理器"""
        self._running = False
        
        # 停止共识协议
        if self._consensus_protocol:
            await self._consensus_protocol.stop()
        
        # 停止心跳
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # 停止监控
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        # 注销本节点
        self.unregister_node(self._node.node_id)
        
        logger.info(f"Node manager stopped: {self._node.node_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._nodes_lock:
            return {
                'local_node': {
                    'id': self._node.node_id,
                    'role': self._node.role.value,
                    'status': self._node.status.value,
                    'cpu_usage': self._node.cpu_usage,
                    'memory_usage': self._node.memory_usage,
                    'active_tasks': self._node.active_tasks,
                    'health_score': self._node.health_score,
                },
                'total_nodes': len(self._nodes),
                'active_nodes': sum(
                    1 for n in self._nodes.values()
                    if n.status == NodeStatus.ACTIVE
                ),
                'coordinators': sum(
                    1 for n in self._nodes.values()
                    if n.role == NodeRole.COORDINATOR
                ),
                'workers': sum(
                    1 for n in self._nodes.values()
                    if n.role == NodeRole.WORKER
                ),
            }
    
    # ==================== 私有方法 ====================
    
    def _create_local_node(self) -> Node:
        """创建本地节点"""
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
        except:
            hostname = "unknown"
            local_ip = "127.0.0.1"
        
        # 获取系统资源
        try:
            cpu_cores = psutil.cpu_count()
            memory_gb = psutil.virtual_memory().total / (1024**3)
            storage_gb = psutil.disk_usage('/').total / (1024**3) if hasattr(psutil, 'disk_usage') else 100
        except:
            cpu_cores = 4
            memory_gb = 8
            storage_gb = 100
        
        return Node(
            node_id=str(uuid.uuid4()),
            node_name=f"node-{hostname}",
            role=NodeRole.WORKER,
            status=NodeStatus.ACTIVE,
            cpu_cores=cpu_cores,
            memory_gb=memory_gb,
            storage_gb=storage_gb,
            host=local_ip,
            port=8766,
            last_heartbeat=datetime.now(),
            reliability_score=100.0,
            tags=['local', 'default']
        )
    
    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        while self._running:
            try:
                # 更新本地资源
                self.update_local_resources()
                
                # 发送心跳
                self._node.last_heartbeat = datetime.now()
                self._fault_detector.record_heartbeat(self._node.node_id)
                
                # 广播心跳(通过共识协议)
                if self._consensus_protocol:
                    message = Message(
                        msg_type=MessageType.HEARTBEAT,
                        sender_id=self._node.node_id,
                        data={
                            'status': self._node.status.value,
                            'cpu_usage': self._node.cpu_usage,
                            'memory_usage': self._node.memory_usage,
                            'active_tasks': self._node.active_tasks,
                            'timestamp': datetime.now().isoformat()
                        }
                    )
                    await self._consensus_protocol.send_message(message)
                
                await asyncio.sleep(self._heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
    
    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                # 检查节点健康状态
                await self._check_nodes_health()
                
                # 检查领导者
                await self._check_leader()
                
                await asyncio.sleep(self._heartbeat_interval * 2)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
    
    async def _check_nodes_health(self) -> None:
        """检查节点健康"""
        now = datetime.now()
        timeout = timedelta(seconds=self._heartbeat_timeout)
        
        with self._nodes_lock:
            for node_id, node in self._nodes.items():
                if node_id == self._node.node_id:
                    continue
                
                if node.last_heartbeat:
                    elapsed = now - node.last_heartbeat
                    if elapsed > timeout:
                        # 节点疑似故障
                        if node.status == NodeStatus.ACTIVE:
                            node.status = NodeStatus.SUSPECTED
                            logger.warning(f"Node {node_id} marked as suspicious")
                            
                            # 记录故障
                            fault = Fault(
                                fault_type=FaultType.NETWORK_TEMPORARY,
                                node_id=node_id,
                                description=f"Node {node_id} heartbeat timeout",
                                severity="medium"
                            )
                            
                            # 触发健康变化
                            self._trigger_callback('health_changed', node, NodeStatus.ACTIVE)
    
    async def _check_leader(self) -> None:
        """检查领导者"""
        if not self._consensus_protocol:
            return
        
        leader_id = self._consensus_protocol.get_leader()
        
        if leader_id and leader_id != self._node.node_id:
            # 检查领导者是否活跃
            with self._nodes_lock:
                leader = self._nodes.get(leader_id)
                
                if leader and leader.status != NodeStatus.ACTIVE:
                    logger.warning(f"Leader {leader_id} is not active")
                    # 触发领导者变化回调
                    self._trigger_callback('leader_changed', None, leader_id)
    
    async def _handle_coordinator_failure(self) -> None:
        """处理协调节点故障"""
        logger.warning("Coordinator failure detected, initiating election")
        
        # 通过共识协议发起选举
        if self._consensus_protocol and isinstance(self._consensus_protocol, RaftProtocol):
            # Raft协议会自动处理选举
            pass
        else:
            # 简单的领导者选举
            await self._simple_election()
    
    async def _simple_election(self) -> None:
        """简单领导者选举"""
        with self._nodes_lock:
            active_nodes = [
                n for n in self._nodes.values()
                if n.status == NodeStatus.ACTIVE
            ]
        
        if not active_nodes:
            return
        
        # 选择可靠性最高的节点
        best_node = max(active_nodes, key=lambda n: n.reliability_score)
        
        # 如果本节点是最佳选择，尝试成为协调者
        if best_node.node_id == self._node.node_id:
            self._node.role = NodeRole.COORDINATOR
            self._node.is_leader = True
            
            with self._nodes_lock:
                self._nodes[self._node.node_id] = self._node
            
            logger.info(f"Node {self._node.node_id} became coordinator")
            self._trigger_callback('leader_changed', self._node, None)
    
    def _trigger_callback(self, event: str, *args) -> None:
        """触发回调"""
        callbacks = self._node_callbacks.get(event, [])
        for callback in callbacks:
            try:
                result = callback(*args)
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(result)
            except Exception as e:
                logger.error(f"Node callback error for {event}: {e}")


class NodeGroup:
    """
    节点分组
    
    用于管理不同类型的节点组
    """
    
    def __init__(self, name: str):
        self.name = name
        self._members: Set[str] = set()
        self._lock = Lock()
    
    def add_node(self, node_id: str) -> None:
        """添加节点到组"""
        with self._lock:
            self._members.add(node_id)
    
    def remove_node(self, node_id: str) -> None:
        """从组移除节点"""
        with self._lock:
            self._members.discard(node_id)
    
    def has_node(self, node_id: str) -> bool:
        """检查节点是否在组中"""
        with self._lock:
            return node_id in self._members
    
    def get_members(self) -> List[str]:
        """获取所有成员"""
        with self._lock:
            return list(self._members)
    
    def size(self) -> int:
        """获取成员数量"""
        with self._lock:
            return len(self._members)


# 全局实例
_node_manager: Optional[NodeManager] = None


def get_node_manager(node: Optional[Node] = None,
                     algorithm: ConsensusAlgorithm = ConsensusAlgorithm.RAFT) -> NodeManager:
    """获取节点管理器实例"""
    global _node_manager
    if _node_manager is None:
        _node_manager = NodeManager(node, algorithm)
    return _node_manager
