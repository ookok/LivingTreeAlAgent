"""
高性能分布式网络优化系统

分层网络拓扑、智能节点分级、连接优化、P2P网络优化、
数据同步优化、拥塞避免、QoS保障、资源调度、监控与自愈
"""

from .models import (
    NodeLevel,
    ConnectionQuality,
    NetworkTier,
    CongestionLevel,
    QoSPriority,
    NodeInfo,
    ConnectionInfo,
    SyncChunk,
    TaskInfo,
    NetworkStats,
)

from .node_grader import NodeGrader
from .connection_pool import ConnectionPool, Connection
from .dht_optimizer import DHTOptimizer
from .cdn_p2p_hybrid import CDNP2PHybrid
from .sync_protocol import MerkleSyncProtocol
from .flow_control import AdaptiveFlowController, CongestionDetector
from .qos_manager import QoSManager, TrafficClassifier
from .task_scheduler import TaskScheduler
from .light_protocol import LightProtocol, MessagePackCodec
from .monitor import NetworkMonitor, SelfHealingManager

# 统一调度器
class NetworkOptimizer:
    """
    高性能分布式网络优化系统统一调度器
    
    Features:
    - 智能节点分级与调度
    - 连接池管理与优化
    - DHT网络优化
    - P2P-CDN混合分发
    - Merkle树增量同步
    - 自适应流控与拥塞避免
    - QoS服务保障
    - 轻量级协议
    - 实时监控与自愈
    """
    
    def __init__(
        self,
        node_id: str,
        max_connections: int = 100,
        enable_quic: bool = True,
        enable_qos: bool = True,
    ):
        self.node_id = node_id
        self.node_grader = NodeGrader(node_id)
        self.connection_pool = ConnectionPool(max_connections)
        self.dht_optimizer = DHTOptimizer(node_id)
        self.cdn_p2p = CDNP2PHybrid(node_id)
        self.sync_protocol = MerkleSyncProtocol(node_id)
        self.flow_controller = AdaptiveFlowController()
        self.congestion_detector = CongestionDetector()
        self.qos_manager = QoSManager() if enable_qos else None
        self.task_scheduler = TaskScheduler(node_id)
        self.light_protocol = LightProtocol(node_id, enable_quic)
        self.network_monitor = NetworkMonitor(node_id)
        self.self_healing = SelfHealingManager(self)
        
        self._running = False
        self._stats = NetworkStats()
    
    async def start(self):
        """启动网络优化系统"""
        self._running = True
        
        # 评估本节点级别
        my_level = await self.node_grader.assess_node_level()
        
        # 初始化各组件
        await self.network_monitor.start()
        await self.light_protocol.start()
        
        if self.qos_manager:
            await self.qos_manager.start()
        
        # 启动自愈监控
        await self.self_healing.start()
        
        return my_level
    
    async def stop(self):
        """停止网络优化系统"""
        self._running = False
        
        await self.network_monitor.stop()
        await self.light_protocol.stop()
        if self.qos_manager:
            await self.qos_manager.stop()
        await self.self_healing.stop()
        await self.connection_pool.close_all()
    
    async def connect_to_peer(self, peer_id: str, address: tuple) -> Connection:
        """
        连接到对等节点
        
        Args:
            peer_id: 对等节点ID
            address: (host, port) 地址
            
        Returns:
            Connection: 建立好的连接
        """
        # 评估连接质量
        quality = await self.connection_pool.assess_connection_quality(address)
        
        # 选择最优协议
        protocol = self.light_protocol.select_protocol(quality)
        
        # 建立连接
        conn = await self.connection_pool.create_connection(
            peer_id=peer_id,
            address=address,
            protocol=protocol,
        )
        
        # 如果QoS启用，应用QoS策略
        if self.qos_manager:
            self.qos_manager.assign_connection(conn)
        
        return conn
    
    async def send_data(
        self,
        data: bytes,
        target_id: str,
        priority: QoSPriority = QoSPriority.NORMAL,
        compressed: bool = True,
    ) -> bool:
        """
        发送数据到目标节点
        
        Args:
            data: 数据内容
            target_id: 目标节点ID
            priority: QoS优先级
            compressed: 是否压缩
            
        Returns:
            bool: 是否发送成功
        """
        # 流量分类
        if self.qos_manager:
            traffic_type = self.qos_manager.classifier.classify_traffic(data)
            await self.qos_manager.enqueue(traffic_type, priority, data, target_id)
            return True
        
        # 获取连接
        conn = await self.connection_pool.get_connection(target_id)
        if not conn:
            return False
        
        # 流控检查
        if not await self.flow_controller.can_send(conn):
            return False
        
        # 拥塞检测
        congestion = await self.congestion_detector.detect(conn)
        if congestion.level != CongestionLevel.NONE:
            self.flow_controller.adjust_for_congestion(conn, congestion)
        
        # 应用QoS优先级
        await conn.set_priority(priority.value)
        
        # 发送数据
        success = await self.light_protocol.send(conn, data, compressed)
        
        # 更新统计
        if success:
            self._stats.bytes_sent += len(data)
            self._stats.packets_sent += 1
        else:
            self._stats.packets_failed += 1
        
        return success
    
    async def sync_data(
        self,
        local_files: dict[str, bytes],
        peer_ids: list[str],
        incremental: bool = True,
    ) -> dict:
        """
        同步数据到多个节点
        
        Args:
            local_files: {file_path: content} 本地文件
            peer_ids: 目标节点列表
            incremental: 是否增量同步
            
        Returns:
            dict: 同步结果统计
        """
        if incremental:
            # 使用Merkle树进行增量同步
            result = await self.sync_protocol.incremental_sync(
                local_files=local_files,
                peers=peer_ids,
                connection_pool=self.connection_pool,
            )
        else:
            # 全量同步
            result = await self.sync_protocol.full_sync(
                local_files=local_files,
                peers=peer_ids,
                connection_pool=self.connection_pool,
            )
        
        return result
    
    async def schedule_task(self, task: TaskInfo) -> str:
        """
        调度分布式任务
        
        Args:
            task: 任务信息
            
        Returns:
            str: 任务ID
        """
        return await self.task_scheduler.schedule_task(
            task=task,
            node_grader=self.node_grader,
            connection_pool=self.connection_pool,
        )
    
    async def lookup_in_dht(self, key: str, parallel: bool = True) -> list:
        """
        在DHT网络查找
        
        Args:
            key: 查找的键
            parallel: 是否并行查询
            
        Returns:
            list: 找到的值列表
        """
        return await self.dht_optimizer.lookup(key, parallel=parallel)
    
    async def store_in_dht(self, key: str, value: bytes, peers: list[str]) -> bool:
        """
        存储到DHT网络
        
        Args:
            key: 存储的键
            value: 存储的值
            peers: 存储到的目标节点
            
        Returns:
            bool: 是否存储成功
        """
        return await self.dht_optimizer.store(key, value, peers)
    
    async def fetch_content(
        self,
        content_id: str,
        prefer_p2p: bool = True,
    ) -> bytes | None:
        """
        获取内容（优先P2P，自动降级CDN）
        
        Args:
            content_id: 内容ID
            prefer_p2p: 是否优先使用P2P
            
        Returns:
            bytes: 内容数据
        """
        return await self.cdn_p2p.fetch(
            content_id=content_id,
            prefer_p2p=prefer_p2p,
            connection_pool=self.connection_pool,
        )
    
    async def publish_content(self, content_id: str, data: bytes) -> bool:
        """
        发布内容到网络
        
        Args:
            content_id: 内容ID
            data: 内容数据
            
        Returns:
            bool: 是否发布成功
        """
        return await self.cdn_p2p.publish(
            content_id=content_id,
            data=data,
            connection_pool=self.connection_pool,
            dht_optimizer=self.dht_optimizer,
        )
    
    def get_network_stats(self) -> NetworkStats:
        """获取网络统计"""
        self._stats.connection_count = len(self.connection_pool.connections)
        self._stats.flow_controller_state = self.flow_controller.get_state()
        self._stats.congestion_state = self.congestion_detector.get_state()
        self._stats.monitor_state = self.network_monitor.get_state()
        return self._stats
    
    def get_optimal_nodes(self, count: int = 5) -> list[NodeInfo]:
        """获取最优节点列表"""
        return self.node_grader.get_optimal_nodes(count)
    
    def get_qos_status(self) -> dict:
        """获取QoS状态"""
        if not self.qos_manager:
            return {"enabled": False}
        return self.qos_manager.get_status()


# 便捷函数
async def create_network_optimizer(
    node_id: str,
    max_connections: int = 100,
    enable_quic: bool = True,
    enable_qos: bool = True,
) -> NetworkOptimizer:
    """
    创建网络优化器实例
    
    Args:
        node_id: 节点ID
        max_connections: 最大连接数
        enable_quic: 是否启用QUIC协议
        enable_qos: 是否启用QoS保障
        
    Returns:
        NetworkOptimizer: 优化器实例
    """
    optimizer = NetworkOptimizer(
        node_id=node_id,
        max_connections=max_connections,
        enable_quic=enable_quic,
        enable_qos=enable_qos,
    )
    await optimizer.start()
    return optimizer


__all__ = [
    # 模型
    "NodeLevel",
    "ConnectionQuality",
    "NetworkTier",
    "CongestionLevel",
    "QoSPriority",
    "NodeInfo",
    "ConnectionInfo",
    "SyncChunk",
    "TaskInfo",
    "NetworkStats",
    # 组件
    "NodeGrader",
    "ConnectionPool",
    "Connection",
    "DHTOptimizer",
    "CDNP2PHybrid",
    "MerkleSyncProtocol",
    "AdaptiveFlowController",
    "CongestionDetector",
    "QoSManager",
    "TrafficClassifier",
    "TaskScheduler",
    "LightProtocol",
    "MessagePackCodec",
    "NetworkMonitor",
    "SelfHealingManager",
    # 统一调度器
    "NetworkOptimizer",
    "create_network_optimizer",
]
