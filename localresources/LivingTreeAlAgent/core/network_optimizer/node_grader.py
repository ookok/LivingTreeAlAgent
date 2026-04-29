"""
智能节点分级系统

根据节点资源、网络状况、稳定性等指标进行智能分级
"""

import asyncio
import hashlib
import platform
import psutil
from dataclasses import dataclass, field
from typing import Optional

from .models import NodeLevel, NodeInfo


@dataclass
class NodeGrader:
    """
    智能节点分级器
    
    Features:
    - 自动评估本节点级别
    - 超级节点发现与管理
    - 最优节点选择
    - 节点信誉系统
    """
    
    node_id: str
    _my_level: NodeLevel = field(default=NodeLevel.NORMAL, init=False)
    _known_nodes: dict[str, NodeInfo] = field(default_factory=dict, init=False)
    _super_nodes: list[NodeInfo] = field(default_factory=list, init=False)
    _node_reputation: dict[str, float] = field(default_factory=dict, init=False)
    
    # 超级节点阈值
    SUPER_LATENCY_MS = 100
    SUPER_BANDWIDTH_MBPS = 5
    SUPER_UPTIME_HOURS = 24
    
    # 边缘节点阈值
    EDGE_BANDWIDTH_MBPS = 1
    EDGE_UPTIME_HOURS = 1
    
    async def assess_node_level(self) -> NodeLevel:
        """
        评估本节点级别
        
        检测:
        - 公网IP
        - 带宽
        - CPU/内存
        - 稳定性
        """
        node_info = await self._gather_node_info()
        
        # 判断是否为超级节点
        if (node_info.public_ip and 
            node_info.bandwidth_mbps >= self.SUPER_BANDWIDTH_MBPS and
            node_info.uptime_seconds >= self.SUPER_UPTIME_HOURS * 3600):
            self._my_level = NodeLevel.SUPER
            node_info.level = NodeLevel.SUPER
            node_info.is_super_node = True
        # 判断是否为边缘节点
        elif node_info.bandwidth_mbps < self.EDGE_BANDWIDTH_MBPS:
            self._my_level = NodeLevel.EDGE
            node_info.level = NodeLevel.EDGE
        # 判断是否为移动节点
        elif platform.system() in ['Android', 'iOS'] or self._is_mobile_network():
            self._my_level = NodeLevel.MOBILE
            node_info.level = NodeLevel.MOBILE
        else:
            self._my_level = NodeLevel.NORMAL
            node_info.level = NodeLevel.NORMAL
        
        self._known_nodes[self.node_id] = node_info
        return self._my_level
    
    async def _gather_node_info(self) -> NodeInfo:
        """收集本节点信息"""
        try:
            # 获取网络接口信息
            net_io = psutil.net_io_counters()
            bandwidth = self._estimate_bandwidth(net_io)
            
            # 获取公网IP
            public_ip = await self._get_public_ip()
            
            return NodeInfo(
                node_id=self.node_id,
                host=self._get_local_ip(),
                port=0,
                public_ip=public_ip,
                latency_ms=0,  # 本地节点延迟为0
                bandwidth_mbps=bandwidth,
                stability=1.0,
                cpu_usage=psutil.cpu_percent(),
                memory_usage=psutil.virtual_memory().percent,
                uptime_seconds=self._get_uptime(),
                is_online=True,
                is_super_node=False,
                capabilities=self._get_capabilities(),
            )
        except Exception:
            return NodeInfo(node_id=self.node_id)
    
    def _estimate_bandwidth(self, net_io) -> float:
        """估算带宽（MB/s转Mbps）"""
        try:
            # 简单估算：上传速度 × 8 = Mbps
            # 实际应该用速度测试
            return 10.0  # 默认10Mbps
        except Exception:
            return 1.0
    
    async def _get_public_ip(self) -> Optional[str]:
        """获取公网IP"""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None
    
    def _get_local_ip(self) -> str:
        """获取局域网IP"""
        try:
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            return local_ip
        except Exception:
            return "127.0.0.1"
    
    def _get_uptime(self) -> int:
        """获取系统运行时间（秒）"""
        try:
            boot_time = psutil.boot_time()
            return int(asyncio.get_event_loop().time() - boot_time)
        except Exception:
            return 0
    
    def _get_capabilities(self) -> list[str]:
        """获取节点能力"""
        caps = ["relay", "storage", "compute"]
        if self._my_level == NodeLevel.SUPER:
            caps.extend(["cache", "coordination"])
        return caps
    
    def _is_mobile_network(self) -> bool:
        """判断是否为移动网络"""
        # 可以通过检测网络接口类型判断
        return False
    
    def register_node(self, node: NodeInfo) -> bool:
        """
        注册已知节点
        
        Args:
            node: 节点信息
            
        Returns:
            bool: 是否注册成功
        """
        node.level = self._calculate_node_level(node)
        self._known_nodes[node.node_id] = node
        
        # 如果是超级节点，加入超级节点列表
        if node.level == NodeLevel.SUPER:
            self._super_nodes.append(node)
        
        return True
    
    def _calculate_node_level(self, node: NodeInfo) -> NodeLevel:
        """计算节点级别"""
        # 超级节点
        if (node.public_ip and 
            node.bandwidth_mbps >= self.SUPER_BANDWIDTH_MBPS and
            node.uptime_seconds >= self.SUPER_UPTIME_HOURS * 3600):
            return NodeLevel.SUPER
        # 边缘节点
        elif node.bandwidth_mbps < self.EDGE_BANDWIDTH_MBPS:
            return NodeLevel.EDGE
        # 移动节点
        elif "mobile" in node.capabilities:
            return NodeLevel.MOBILE
        else:
            return NodeLevel.NORMAL
    
    def update_node_reputation(self, node_id: str, delta: float):
        """
        更新节点信誉
        
        Args:
            node_id: 节点ID
            delta: 信誉变化（正负）
        """
        current = self._node_reputation.get(node_id, 0.5)
        new_reputation = max(0, min(1, current + delta))
        self._node_reputation[node_id] = new_reputation
    
    def get_optimal_nodes(
        self, 
        count: int = 5,
        prefer_super: bool = True,
        exclude_self: bool = True,
    ) -> list[NodeInfo]:
        """
        获取最优节点列表
        
        Args:
            count: 返回数量
            prefer_super: 是否优先选择超级节点
            exclude_self: 是否排除自己
            
        Returns:
            list[NodeInfo]: 最优节点列表
        """
        nodes = []
        
        for node in self._known_nodes.values():
            if exclude_self and node.node_id == self.node_id:
                continue
            if not node.is_online:
                continue
            nodes.append(node)
        
        # 排序
        if prefer_super:
            # 超级节点优先，然后按质量分数
            nodes.sort(
                key=lambda n: (
                    -int(n.level == NodeLevel.SUPER),
                    -n.quality_score,
                )
            )
        else:
            nodes.sort(key=lambda n: -n.quality_score)
        
        return nodes[:count]
    
    def get_super_nodes(self) -> list[NodeInfo]:
        """获取所有超级节点"""
        return [n for n in self._super_nodes if n.is_online]
    
    def get_my_level(self) -> NodeLevel:
        """获取本节点级别"""
        return self._my_level
    
    def get_stats(self) -> dict:
        """获取节点统计"""
        level_counts = {level: 0 for level in NodeLevel}
        for node in self._known_nodes.values():
            level_counts[node.level] += 1
        
        return {
            "my_level": self._my_level.value,
            "total_nodes": len(self._known_nodes),
            "online_nodes": sum(1 for n in self._known_nodes.values() if n.is_online),
            "super_nodes": len(self._super_nodes),
            "level_distribution": {k.value: v for k, v in level_counts.items()},
        }
