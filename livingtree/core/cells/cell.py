"""
Cell 基类 - 细胞AI的基础单元

每个细胞具有：
- 唯一标识符
- 专业领域（specialization）
- 状态（活跃/休眠/死亡）
- 连接网络
- 信号处理能力
- 能量消耗管理
"""

import uuid
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime


class CellType(Enum):
    """细胞类型枚举"""
    REASONING = "reasoning"           # 推理细胞
    MEMORY = "memory"                 # 记忆细胞
    LEARNING = "learning"             # 学习细胞
    PERCEPTION = "perception"         # 感知细胞
    ACTION = "action"                 # 行动细胞
    PREDICTION = "prediction"         # 预测细胞


class CellState(Enum):
    """细胞状态枚举"""
    ACTIVE = "active"                 # 活跃状态
    DORMANT = "dormant"               # 休眠状态（节能模式）
    LEARNING = "learning"             # 学习中
    DEGRADED = "degraded"             # 性能下降
    DEAD = "dead"                     # 死亡状态


@dataclass
class Connection:
    """细胞连接"""
    target_cell_id: str
    weight: float = 1.0               # 连接强度 (0-1)
    last_used: datetime = field(default_factory=datetime.now)
    signal_count: int = 0             # 信号传递次数
    
    def strengthen(self, delta: float = 0.05):
        """增强连接强度（Hebbian学习）"""
        self.weight = min(1.0, self.weight + delta)
    
    def weaken(self, delta: float = 0.05):
        """减弱连接强度"""
        self.weight = max(0.0, self.weight - delta)


class Cell:
    """
    细胞基类
    
    所有细胞类型都继承此类，提供统一的接口和生命周期管理。
    """
    
    def __init__(self, specialization: str = "general"):
        self.id = str(uuid.uuid4())[:8]  # 短ID
        self.specialization = specialization
        self.state = CellState.ACTIVE
        self.connections: List[Connection] = []
        self.signal_history: List[dict] = []
        
        # 能量管理
        self.energy_level = 1.0        # 能量水平 (0-1)
        self.energy_consumption = 0.01 # 基础消耗率
        self.last_activity = datetime.now()
        
        # 性能指标
        self.processing_time = 0.0
        self.success_rate = 1.0
        self.total_processed = 0
        self.errors = 0
        
        # 配置
        self.max_signal_history = 100
        self.max_connections = 20
        self.dormancy_threshold = 300  # 5分钟无活动进入休眠
    
    @property
    def cell_type(self) -> CellType:
        """返回细胞类型"""
        return CellType.REASONING  # 子类覆盖
    
    @property
    def is_alive(self) -> bool:
        """判断细胞是否存活"""
        return self.state != CellState.DEAD
    
    @property
    def is_active(self) -> bool:
        """判断细胞是否活跃"""
        return self.state == CellState.ACTIVE
    
    def connect(self, target_cell: 'Cell', initial_weight: float = 0.5):
        """
        连接到另一个细胞
        
        Args:
            target_cell: 目标细胞
            initial_weight: 初始连接强度
        """
        if target_cell.id == self.id:
            return
        
        # 检查是否已存在连接
        for conn in self.connections:
            if conn.target_cell_id == target_cell.id:
                return
        
        if len(self.connections) < self.max_connections:
            self.connections.append(Connection(
                target_cell_id=target_cell.id,
                weight=initial_weight
            ))
    
    def disconnect(self, target_cell_id: str):
        """断开与指定细胞的连接"""
        self.connections = [
            conn for conn in self.connections
            if conn.target_cell_id != target_cell_id
        ]
    
    def get_connection_weight(self, target_cell_id: str) -> float:
        """获取与目标细胞的连接强度"""
        for conn in self.connections:
            if conn.target_cell_id == target_cell_id:
                return conn.weight
        return 0.0
    
    def update_connection_weight(self, target_cell_id: str, weight: float):
        """更新连接强度"""
        for conn in self.connections:
            if conn.target_cell_id == target_cell_id:
                conn.weight = max(0.0, min(1.0, weight))
                conn.last_used = datetime.now()
                conn.signal_count += 1
    
    async def send_signal(self, target_cell: 'Cell', message: dict):
        """
        向目标细胞发送信号
        
        Args:
            target_cell: 目标细胞
            message: 消息内容
        """
        if not self.is_alive or not target_cell.is_alive:
            return
        
        # 更新连接强度（Hebbian学习）
        self.update_connection_weight(target_cell.id, 
                                     self.get_connection_weight(target_cell.id) + 0.02)
        
        await target_cell.receive_signal(message, self.id)
    
    async def broadcast_signal(self, message: dict):
        """向所有连接的细胞广播信号"""
        from .assembler import CellRegistry
        registry = CellRegistry.get_instance()
        for conn in self.connections:
            # 通过细胞注册表获取目标细胞
            target_cell = registry.get_cell(conn.target_cell_id)
            if target_cell and conn.weight > 0.1:  # 只向强连接发送
                await self.send_signal(target_cell, message)
    
    async def receive_signal(self, message: dict, sender_id: str = None):
        """
        接收信号并处理
        
        Args:
            message: 消息内容
            sender_id: 发送者ID
        """
        self.last_activity = datetime.now()
        
        if self.state == CellState.DORMANT:
            self.activate()
        
        # 记录信号历史
        signal_record = {
            'timestamp': datetime.now(),
            'sender_id': sender_id,
            'message': message,
            'processed': False
        }
        self.signal_history.append(signal_record)
        
        # 限制历史记录数量
        if len(self.signal_history) > self.max_signal_history:
            self.signal_history = self.signal_history[-self.max_signal_history:]
        
        # 处理信号
        result = await self._process_signal(message)
        
        # 更新记录
        for record in self.signal_history:
            if not record['processed']:
                record['processed'] = True
                break
        
        return result
    
    async def _process_signal(self, message: dict) -> Any:
        """
        子类实现具体的信号处理逻辑
        
        Args:
            message: 消息内容
        
        Returns:
            处理结果
        """
        raise NotImplementedError("Subclasses must implement _process_signal")
    
    def activate(self):
        """激活细胞（从休眠状态唤醒）"""
        self.state = CellState.ACTIVE
        self.energy_level = min(1.0, self.energy_level + 0.2)
    
    def deactivate(self):
        """使细胞进入休眠状态"""
        self.state = CellState.DORMANT
    
    def kill(self):
        """杀死细胞（释放资源）"""
        self.state = CellState.DEAD
        self.connections = []
        self.signal_history = []
    
    def consume_energy(self, amount: float):
        """消耗能量"""
        self.energy_level = max(0.0, self.energy_level - amount)
        
        if self.energy_level < 0.1:
            self.state = CellState.DORMANT
    
    def recharge(self, amount: float = 0.1):
        """补充能量"""
        self.energy_level = min(1.0, self.energy_level + amount)
    
    def update_activity(self):
        """更新活动状态（定期调用）"""
        now = datetime.now()
        time_since_activity = (now - self.last_activity).total_seconds()
        
        # 检查是否需要进入休眠
        if self.state == CellState.ACTIVE and time_since_activity > self.dormancy_threshold:
            self.deactivate()
        
        # 基础能量消耗
        if self.state == CellState.ACTIVE:
            self.consume_energy(self.energy_consumption)
    
    def record_success(self, processing_time: float = 0.0):
        """记录成功处理"""
        self.total_processed += 1
        self.processing_time = processing_time
        self.success_rate = (self.success_rate * (self.total_processed - 1) + 1.0) / self.total_processed
    
    def record_error(self):
        """记录错误"""
        self.total_processed += 1
        self.errors += 1
        self.success_rate = (self.success_rate * (self.total_processed - 1) + 0.0) / self.total_processed
    
    def get_stats(self) -> Dict[str, Any]:
        """获取细胞统计信息"""
        return {
            'id': self.id,
            'type': self.cell_type.value,
            'specialization': self.specialization,
            'state': self.state.value,
            'energy_level': round(self.energy_level, 2),
            'success_rate': round(self.success_rate, 2),
            'total_processed': self.total_processed,
            'errors': self.errors,
            'connection_count': len(self.connections),
            'avg_processing_time': round(self.processing_time, 2),
        }
    
    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.id} type={self.cell_type.value} state={self.state.value}>"
    
    def __str__(self):
        return f"{self.__class__.__name__}[{self.id}]"


class EnergyMonitor:
    """能量监控器"""
    
    def __init__(self):
        self.cells = []
    
    def register_cell(self, cell: Cell):
        """注册细胞"""
        if cell not in self.cells:
            self.cells.append(cell)
    
    def unregister_cell(self, cell: Cell):
        """注销细胞"""
        if cell in self.cells:
            self.cells.remove(cell)
    
    def get_total_energy(self) -> float:
        """获取所有细胞的总能量"""
        return sum(cell.energy_level for cell in self.cells)
    
    def get_average_energy(self) -> float:
        """获取平均能量水平"""
        if not self.cells:
            return 0.0
        return self.get_total_energy() / len(self.cells)
    
    def balance_energy(self):
        """能量均衡（将能量从高能量细胞转移到低能量细胞）"""
        avg_energy = self.get_average_energy()
        
        for cell in self.cells:
            if cell.energy_level > avg_energy + 0.2:
                surplus = cell.energy_level - avg_energy
                cell.energy_level = avg_energy
                # 分配给低能量细胞
                for target in self.cells:
                    if target.energy_level < avg_energy - 0.1:
                        target.recharge(surplus / len(self.cells))
    
    def update_all(self):
        """更新所有细胞的活动状态"""
        for cell in self.cells:
            cell.update_activity()