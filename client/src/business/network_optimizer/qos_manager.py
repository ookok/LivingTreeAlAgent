"""
QoS Service Quality Assurance

服务质量保障
- 流量分类
- 优先级调度
- 带宽保障
- 延迟控制
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional
import heapq

from .models import QoSPriority, TrafficType


@dataclass
class QoSManager:
    """
    QoS服务质量管理器
    
    Features:
    - Traffic classification
    - Priority queuing
    - Bandwidth guarantee
    - Latency control
    """
    
    # 优先级队列: {priority: list}
    _queues: dict[QoSPriority, list] = field(default_factory=lambda: defaultdict(list))
    
    # 活跃连接
    _connections: dict[str, dict] = field(default_factory=dict)
    
    # 流量整形
    _rate_limiters: dict[str, float] = field(default_factory=dict)  # 字节/秒
    _last_send_time: dict[str, float] = field(default_factory=dict)
    
    # 统计
    _stats = field(default_factory=lambda: defaultdict(int))
    
    # 分类器
    classifier: 'TrafficClassifier' = field(default_factory=TrafficClassifier)
    
    # 运行状态
    _running: bool = False
    _scheduler_task: Optional[asyncio.Task] = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    
    async def start(self):
        """启动QoS管理器"""
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
    
    async def stop(self):
        """停止QoS管理器"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
    
    async def enqueue(
        self,
        traffic_type: TrafficType,
        priority: QoSPriority,
        data: bytes,
        target_id: str,
    ):
        """
        将数据加入优先级队列
        
        Args:
            traffic_type: 流量类型
            priority: QoS优先级
            data: 数据内容
            target_id: 目标节点ID
        """
        async with self._lock:
            item = {
                "traffic_type": traffic_type,
                "data": data,
                "target_id": target_id,
                "enqueue_time": time.time(),
                "size": len(data),
            }
            self._queues[priority].append(item)
            self._stats[f"enqueued_{priority.name}"] += 1
    
    async def dequeue(self) -> Optional[dict]:
        """
        取出最高优先级数据
        
        Returns:
            dict: 队列项
        """
        async with self._lock:
            # 按优先级顺序查找
            for priority in QoSPriority:
                if self._queues[priority]:
                    item = self._queues[priority].pop(0)
                    self._stats[f"dequeued_{priority.name}"] += 1
                    return item
            return None
    
    async def _scheduler_loop(self):
        """调度循环"""
        while self._running:
            try:
                # 获取最高优先级数据
                item = await self.dequeue()
                if not item:
                    await asyncio.sleep(0.01)
                    continue
                
                # 检查流量整形
                if not self._can_send(item):
                    # 重新入队
                    self._queues[item.get("priority", QoSPriority.NORMAL)].insert(0, item)
                    await asyncio.sleep(0.01)
                    continue
                
                # 发送数据
                # TODO: 实际发送逻辑
                
                # 更新统计
                self._stats["total_sent"] += item["size"]
                
            except asyncio.CancelledError:
                break
            except Exception:
                pass
    
    def _can_send(self, item: dict) -> bool:
        """检查是否可以发送"""
        target_id = item.get("target_id", "")
        
        # 检查速率限制
        rate_limit = self._rate_limiters.get(target_id, float('inf'))
        if rate_limit <= 0:
            return False
        
        # 检查最后发送时间
        last_time = self._last_send_time.get(target_id, 0)
        elapsed = time.time() - last_time
        
        # 计算允许的发送间隔
        min_interval = item["size"] / rate_limit if rate_limit > 0 else 0
        
        return elapsed >= min_interval
    
    def assign_connection(self, conn):
        """为连接分配QoS策略"""
        self._connections[conn.conn_id] = {
            "conn": conn,
            "priority": QoSPriority.NORMAL,
            "rate_limit": float('inf'),
            "assigned_at": time.time(),
        }
    
    def set_connection_priority(self, conn_id: str, priority: QoSPriority):
        """设置连接优先级"""
        if conn_id in self._connections:
            self._connections[conn_id]["priority"] = priority
    
    def set_rate_limit(self, target_id: str, rate_bytes_per_sec: float):
        """设置速率限制"""
        self._rate_limiters[target_id] = rate_bytes_per_sec
    
    def get_queue_depth(self, priority: QoSPriority = None) -> int:
        """获取队列深度"""
        if priority:
            return len(self._queues[priority])
        return sum(len(q) for q in self._queues.values())
    
    def get_status(self) -> dict:
        """获取QoS状态"""
        return {
            "running": self._running,
            "total_queues": sum(len(q) for q in self._queues.values()),
            "queue_by_priority": {
                p.name: len(self._queues[p])
                for p in QoSPriority
            },
            "total_sent_bytes": self._stats["total_sent"],
            "connections": len(self._connections),
        }


@dataclass
class TrafficClassifier:
    """
    流量分类器
    
    基于内容特征识别流量类型
    """
    
    # 特征签名
    SIGNATURES = {
        TrafficType.CONTROL: [b"PING", b"PONG", b"HELLO", b"BYE"],
        TrafficType.REALTIME: [b"audio", b"video", b"rtp://"],
        TrafficType.FILE_TRANSFER: [b"file:", b"chunk:", b"GET:"],
        TrafficType.BACKGROUND: [b"sync", b"backup", b"cache"],
    }
    
    def classify_traffic(self, data: bytes) -> TrafficType:
        """
        分类流量类型
        
        Args:
            data: 数据内容
            
        Returns:
            TrafficType: 流量类型
        """
        if not data:
            return TrafficType.INTERACTIVE
        
        # 检查特征签名
        for traffic_type, signatures in self.SIGNATURES.items():
            for sig in signatures:
                if sig in data[:100]:  # 只检查头部
                    return traffic_type
        
        # 基于大小判断
        if len(data) > 1024 * 1024:  # > 1MB
            return TrafficType.FILE_TRANSFER
        elif len(data) < 64:
            return TrafficType.CONTROL
        
        return TrafficType.INTERACTIVE
    
    def get_priority_for_traffic(self, traffic_type: TrafficType) -> QoSPriority:
        """获取流量类型对应的优先级"""
        mapping = {
            TrafficType.CONTROL: QoSPriority.CRITICAL,
            TrafficType.REALTIME: QoSPriority.HIGH,
            TrafficType.INTERACTIVE: QoSPriority.NORMAL,
            TrafficType.FILE_TRANSFER: QoSPriority.LOW,
            TrafficType.BACKGROUND: QoSPriority.BACKGROUND,
        }
        return mapping.get(traffic_type, QoSPriority.NORMAL)
