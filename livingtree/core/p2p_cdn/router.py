"""
CDN 路由器

负责智能选择最优节点来获取数据
"""

from __future__ import annotations


import logging
import time
from typing import Dict, Optional, List

from .models import CDNNode, NetworkMetrics

logger = logging.getLogger(__name__)


class RouteStrategy:
    """
    路由策略枚举
    """
    LATENCY = "latency"  # 基于延迟
    BANDWIDTH = "bandwidth"  # 基于带宽
    CAPABILITY = "capability"  # 基于节点能力
    HYBRID = "hybrid"  # 混合策略


class CDNRouter:
    """
    CDN 路由器
    负责智能选择最优节点来获取数据
    """
    
    def __init__(self):
        self.network_metrics: Dict[str, NetworkMetrics] = {}
        self.strategy = RouteStrategy.HYBRID
    
    async def find_best_node(self, data_id: str, known_nodes: Dict[str, CDNNode]) -> Optional[CDNNode]:
        """
        找到最佳节点来获取数据
        
        Args:
            data_id: 数据 ID
            known_nodes: 已知节点列表
            
        Returns:
            最佳节点，如果没有找到则返回 None
        """
        if not known_nodes:
            return None
        
        # 过滤活跃节点（例如，最后 seen 时间不超过 5 分钟）
        current_time = time.time()
        active_nodes = [
            node for node in known_nodes.values()
            if current_time - node.last_seen < 300  # 5 分钟
        ]
        
        if not active_nodes:
            return None
        
        # 根据策略选择最佳节点
        if self.strategy == RouteStrategy.LATENCY:
            return self._select_by_latency(active_nodes)
        elif self.strategy == RouteStrategy.BANDWIDTH:
            return self._select_by_bandwidth(active_nodes)
        elif self.strategy == RouteStrategy.CAPABILITY:
            return self._select_by_capability(active_nodes)
        else:  # 混合策略
            return self._select_by_hybrid(active_nodes)
    
    def _select_by_latency(self, nodes: List[CDNNode]) -> CDNNode:
        """
        基于延迟选择最佳节点
        """
        # 这里需要实际的网络延迟测量
        # 目前使用模拟数据
        return min(nodes, key=lambda x: self._get_node_latency(x.node_id))
    
    def _select_by_bandwidth(self, nodes: List[CDNNode]) -> CDNNode:
        """
        基于带宽选择最佳节点
        """
        return max(nodes, key=lambda x: x.capability.bandwidth)
    
    def _select_by_capability(self, nodes: List[CDNNode]) -> CDNNode:
        """
        基于节点能力选择最佳节点
        """
        # 计算节点能力得分
        def calculate_score(node: CDNNode) -> float:
            score = 0
            # 存储容量权重 0.3
            score += node.capability.storage_available / 1024 / 1024 / 1024 * 0.3  # GB
            # 带宽权重 0.3
            score += node.capability.bandwidth * 0.3
            # 在线时间权重 0.2
            score += node.capability.uptime / 3600 * 0.2  # 小时
            # 可靠性权重 0.2
            score += node.capability.reliability * 0.2
            return score
        
        return max(nodes, key=calculate_score)
    
    def _select_by_hybrid(self, nodes: List[CDNNode]) -> CDNNode:
        """
        基于混合策略选择最佳节点
        """
        # 计算混合得分
        def calculate_hybrid_score(node: CDNNode) -> float:
            # 延迟得分（越低越好，转换为越高越好）
            latency = self._get_node_latency(node.node_id)
            latency_score = 100 / (latency + 1)  # 避免除零
            
            # 能力得分
            capability_score = (
                node.capability.storage_available / 1024 / 1024 / 1024 * 0.3 +  # GB
                node.capability.bandwidth * 0.3 +
                node.capability.uptime / 3600 * 0.2 +  # 小时
                node.capability.reliability * 0.2
            )
            
            # 混合得分
            return latency_score * 0.4 + capability_score * 0.6
        
        return max(nodes, key=calculate_hybrid_score)
    
    def _get_node_latency(self, node_id: str) -> float:
        """
        获取节点延迟
        
        Args:
            node_id: 节点 ID
            
        Returns:
            延迟（毫秒）
        """
        if node_id in self.network_metrics:
            return self.network_metrics[node_id].latency
        
        # 模拟延迟数据
        return 50.0  # 默认 50ms
    
    def update_network_metrics(self, metrics: NetworkMetrics):
        """
        更新网络指标
        
        Args:
            metrics: 网络指标
        """
        self.network_metrics[metrics.node_id] = metrics
        logger.debug(f"Updated network metrics for node {metrics.node_id}: latency={metrics.latency}ms, bandwidth={metrics.bandwidth}Mbps")
    
    def get_network_metrics(self, node_id: str) -> Optional[NetworkMetrics]:
        """
        获取节点的网络指标
        
        Args:
            node_id: 节点 ID
            
        Returns:
            网络指标，如果没有则返回 None
        """
        return self.network_metrics.get(node_id)
    
    def set_strategy(self, strategy: RouteStrategy):
        """
        设置路由策略
        
        Args:
            strategy: 路由策略
        """
        self.strategy = strategy
        logger.info(f"Set route strategy to {strategy}")
