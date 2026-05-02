"""
信号系统模块

定义细胞间通信的信号格式和传递机制。
"""

import uuid
from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime


class SignalType(Enum):
    """信号类型"""
    # 控制信号
    HEARTBEAT = "heartbeat"           # 心跳信号
    SYNC = "sync"                     # 同步信号
    SHUTDOWN = "shutdown"             # 关闭信号
    
    # 数据信号
    DATA = "data"                     # 数据信号
    QUERY = "query"                   # 查询信号
    RESPONSE = "response"             # 响应信号
    
    # 控制信号
    LEARN = "learn"                   # 学习信号
    TRAIN = "train"                   # 训练信号
    EVALUATE = "evaluate"             # 评估信号
    
    # 协作信号
    REQUEST_HELP = "request_help"     # 请求帮助
    OFFER_HELP = "offer_help"         # 提供帮助
    COORDINATE = "coordinate"         # 协调信号
    
    # 进化信号
    DIVIDE = "divide"                 # 分裂信号
    MUTATE = "mutate"                 # 变异信号
    SELECT = "select"                 # 选择信号


class SignalPriority(Enum):
    """信号优先级"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Signal:
    """
    信号数据结构
    
    用于细胞间通信的标准化消息格式。
    """
    
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: SignalType = SignalType.DATA
    priority: SignalPriority = SignalPriority.MEDIUM
    sender_id: str = ""
    target_cell_id: Optional[str] = None  # None 表示广播
    content: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    ttl: int = 10  # 生存时间（跳数）
    hops: int = 0  # 已传递跳数
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'type': self.type.value,
            'priority': self.priority.value,
            'sender_id': self.sender_id,
            'target_cell_id': self.target_cell_id,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'ttl': self.ttl,
            'hops': self.hops
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Signal':
        """从字典创建信号"""
        return cls(
            id=data.get('id', str(uuid.uuid4())[:8]),
            type=SignalType(data.get('type', 'data')),
            priority=SignalPriority(data.get('priority', 2)),
            sender_id=data.get('sender_id', ''),
            target_cell_id=data.get('target_cell_id'),
            content=data.get('content', {}),
            timestamp=datetime.fromisoformat(data.get('timestamp', datetime.now().isoformat())),
            ttl=data.get('ttl', 10),
            hops=data.get('hops', 0)
        )
    
    def is_expired(self) -> bool:
        """检查信号是否过期"""
        return self.hops >= self.ttl
    
    def hop(self):
        """增加跳数"""
        self.hops += 1
    
    def __repr__(self):
        return f"<Signal id={self.id} type={self.type.value} priority={self.priority.name}>"


class SignalRouter:
    """
    信号路由器
    
    负责信号的路由和传递。
    """
    
    def __init__(self):
        self.cell_registry = None  # 延迟初始化
        self.signal_queue = []  # 信号队列（按优先级排序）
    
    def set_cell_registry(self, registry):
        """设置细胞注册表"""
        self.cell_registry = registry
    
    async def route_signal(self, signal: Signal) -> bool:
        """
        路由信号
        
        Args:
            signal: 待路由的信号
        
        Returns:
            是否路由成功
        """
        if signal.is_expired():
            return False
        
        signal.hop()
        
        if signal.target_cell_id:
            # 定向发送
            target_cell = self._find_cell(signal.target_cell_id)
            if target_cell:
                await target_cell.receive_signal(signal.content, signal.sender_id)
                return True
        else:
            # 广播发送
            await self._broadcast_signal(signal)
            return True
        
        return False
    
    def _find_cell(self, cell_id: str):
        """查找细胞"""
        if self.cell_registry:
            return self.cell_registry.get_cell(cell_id)
        return None
    
    async def _broadcast_signal(self, signal: Signal):
        """广播信号到所有细胞"""
        if not self.cell_registry:
            return
        
        for cell in self.cell_registry.get_all_cells():
            if cell.id != signal.sender_id:  # 不发送给自己
                await cell.receive_signal(signal.content, signal.sender_id)
    
    def enqueue_signal(self, signal: Signal):
        """将信号加入队列"""
        self.signal_queue.append(signal)
        # 按优先级排序（高优先级在前）
        self.signal_queue.sort(key=lambda s: s.priority.value, reverse=True)
    
    async def process_queue(self):
        """处理信号队列"""
        while self.signal_queue:
            signal = self.signal_queue.pop(0)
            await self.route_signal(signal)


class SignalMonitor:
    """
    信号监控器
    
    监控和记录信号流量。
    """
    
    def __init__(self):
        self.signal_counts: Dict[str, int] = {}
        self.latency_records: List[float] = []
        self.max_records = 1000
    
    def record_signal(self, signal_type: str, latency: float = 0.0):
        """记录信号"""
        self.signal_counts[signal_type] = self.signal_counts.get(signal_type, 0) + 1
        
        if latency > 0:
            self.latency_records.append(latency)
            # 保持记录数量限制
            if len(self.latency_records) > self.max_records:
                self.latency_records = self.latency_records[-self.max_records:]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'signal_counts': self.signal_counts,
            'total_signals': sum(self.signal_counts.values()),
            'avg_latency': sum(self.latency_records) / len(self.latency_records) if self.latency_records else 0,
            'max_latency': max(self.latency_records) if self.latency_records else 0,
            'min_latency': min(self.latency_records) if self.latency_records else 0
        }
    
    def reset(self):
        """重置统计"""
        self.signal_counts = {}
        self.latency_records = []


# 便捷函数
def create_signal(signal_type: str, content: Dict[str, Any] = None,
                 sender_id: str = "", target_cell_id: str = None,
                 priority: int = 2) -> Signal:
    """
    创建信号的便捷函数
    
    Args:
        signal_type: 信号类型
        content: 信号内容
        sender_id: 发送者ID
        target_cell_id: 目标细胞ID（可选，None为广播）
        priority: 优先级（1-4）
    
    Returns:
        Signal实例
    """
    return Signal(
        type=SignalType(signal_type.lower()),
        priority=SignalPriority(priority),
        sender_id=sender_id,
        target_cell_id=target_cell_id,
        content=content or {}
    )