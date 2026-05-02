"""
涌现引擎模块

实现细胞群体的自组织和涌现智能。
"""

from typing import Any, Dict, List, Optional
import asyncio
import random
from collections import defaultdict
from .cell import Cell, CellType, Connection, EnergyMonitor
from .cell_signal import Signal, SignalType, SignalRouter


class SelfOrganization:
    """
    自组织系统
    
    实现细胞间的自组织行为，包括：
    - Hebbian学习规则
    - 连接强度动态调整
    - 功能模块形成
    """
    
    def __init__(self):
        self.connection_history: Dict[str, List[float]] = defaultdict(list)
        self.hebbian_learning_rate = 0.05
        self.decay_rate = 0.01
        self.min_connection_weight = 0.05
        self.max_connection_weight = 1.0
    
    async def process_connections(self, cells: List[Cell]):
        """
        处理所有细胞的连接
        
        Args:
            cells: 细胞列表
        """
        for cell in cells:
            await self._update_cell_connections(cell, cells)
    
    async def _update_cell_connections(self, cell: Cell, all_cells: List[Cell]):
        """
        更新单个细胞的连接
        
        Args:
            cell: 目标细胞
            all_cells: 所有细胞列表
        """
        for conn in cell.connections:
            target_cell = next((c for c in all_cells if c.id == conn.target_cell_id), None)
            if target_cell:
                # Hebbian学习：同时活跃的细胞连接增强
                if cell.is_active and target_cell.is_active:
                    conn.strengthen(self.hebbian_learning_rate)
                else:
                    conn.weaken(self.decay_rate)
                
                # 限制连接强度范围
                conn.weight = max(self.min_connection_weight, min(self.max_connection_weight, conn.weight))
                
                # 记录连接历史
                self._record_connection_history(cell.id, conn.target_cell_id, conn.weight)
    
    def _record_connection_history(self, source_id: str, target_id: str, weight: float):
        """记录连接历史"""
        key = f"{source_id}-{target_id}"
        self.connection_history[key].append(weight)
        # 保持最近100条记录
        if len(self.connection_history[key]) > 100:
            self.connection_history[key] = self.connection_history[key][-100:]
    
    def detect_communities(self, cells: List[Cell]) -> List[List[Cell]]:
        """
        检测细胞社区（功能模块）
        
        Args:
            cells: 细胞列表
        
        Returns:
            社区列表，每个社区是一组紧密连接的细胞
        """
        visited = set()
        communities = []
        
        for cell in cells:
            if cell.id not in visited:
                community = self._find_community(cell, cells, visited)
                if len(community) > 1:  # 至少2个细胞才构成社区
                    communities.append(community)
        
        return communities
    
    def _find_community(self, start_cell: Cell, all_cells: List[Cell], 
                       visited: set) -> List[Cell]:
        """
        使用深度优先搜索查找社区
        
        Args:
            start_cell: 起始细胞
            all_cells: 所有细胞
            visited: 已访问集合
        
        Returns:
            社区成员列表
        """
        community = []
        stack = [start_cell]
        
        while stack:
            cell = stack.pop()
            if cell.id in visited:
                continue
            
            visited.add(cell.id)
            community.append(cell)
            
            # 查找强连接的邻居
            for conn in cell.connections:
                if conn.weight > 0.5:  # 强连接阈值
                    neighbor = next((c for c in all_cells if c.id == conn.target_cell_id), None)
                    if neighbor and neighbor.id not in visited:
                        stack.append(neighbor)
        
        return community
    
    def get_connection_strength_matrix(self, cells: List[Cell]) -> Dict[str, Dict[str, float]]:
        """
        获取连接强度矩阵
        
        Args:
            cells: 细胞列表
        
        Returns:
            连接强度矩阵
        """
        matrix = {}
        for cell in cells:
            matrix[cell.id] = {}
            for other in cells:
                if cell.id == other.id:
                    matrix[cell.id][other.id] = 0.0
                else:
                    conn = next((c for c in cell.connections if c.target_cell_id == other.id), None)
                    matrix[cell.id][other.id] = conn.weight if conn else 0.0
        
        return matrix


class EmergenceEngine:
    """
    涌现引擎
    
    负责管理细胞群体的涌现行为：
    - 自组织模式形成
    - 群体智能涌现
    - 自适应行为调整
    """
    
    def __init__(self):
        self.self_organization = SelfOrganization()
        self.signal_router = SignalRouter()
        self.energy_monitor = EnergyMonitor()
        self.emergent_patterns = []
        self.pattern_detection_threshold = 0.7
    
    def register_cells(self, cells: List[Cell]):
        """注册细胞到引擎"""
        for cell in cells:
            self.energy_monitor.register_cell(cell)
    
    async def run(self, iterations: int = 100):
        """
        运行涌现引擎
        
        Args:
            iterations: 迭代次数
        """
        for i in range(iterations):
            await self._step()
            
            if (i + 1) % 10 == 0:
                await self._detect_emergent_patterns()
    
    async def _step(self):
        """执行单步涌现过程"""
        # 获取所有注册的细胞
        cells = self.energy_monitor.cells
        
        # 更新连接
        await self.self_organization.process_connections(cells)
        
        # 更新能量
        self.energy_monitor.update_all()
        
        # 发送心跳信号
        await self._send_heartbeat()
    
    async def _send_heartbeat(self):
        """发送心跳信号"""
        heartbeat_signal = Signal(
            type=SignalType.HEARTBEAT,
            priority=1,
            content={'timestamp': asyncio.get_event_loop().time()}
        )
        await self.signal_router.route_signal(heartbeat_signal)
    
    async def _detect_emergent_patterns(self):
        """检测涌现模式"""
        cells = self.energy_monitor.cells
        
        # 检测社区
        communities = self.self_organization.detect_communities(cells)
        
        for community in communities:
            pattern = self._analyze_community(community)
            if pattern['strength'] >= self.pattern_detection_threshold:
                if pattern not in self.emergent_patterns:
                    self.emergent_patterns.append(pattern)
    
    def _analyze_community(self, community: List[Cell]) -> Dict[str, Any]:
        """
        分析社区特征
        
        Args:
            community: 社区成员列表
        
        Returns:
            社区特征描述
        """
        cell_types = [c.cell_type for c in community]
        type_counts = defaultdict(int)
        for ct in cell_types:
            type_counts[ct.value] += 1
        
        avg_energy = sum(c.energy_level for c in community) / len(community)
        avg_connections = sum(len(c.connections) for c in community) / len(community)
        
        return {
            'cell_ids': [c.id for c in community],
            'cell_types': dict(type_counts),
            'size': len(community),
            'avg_energy': round(avg_energy, 2),
            'avg_connections': round(avg_connections, 2),
            'strength': self._calculate_pattern_strength(community)
        }
    
    def _calculate_pattern_strength(self, community: List[Cell]) -> float:
        """
        计算模式强度
        
        Args:
            community: 社区成员列表
        
        Returns:
            模式强度 (0-1)
        """
        if len(community) < 2:
            return 0.0
        
        # 计算内部连接密度
        total_possible = len(community) * (len(community) - 1)
        actual_connections = sum(len(c.connections) for c in community)
        density = actual_connections / total_possible if total_possible > 0 else 0.0
        
        # 计算连接强度的平均值
        all_weights = []
        for cell in community:
            for conn in cell.connections:
                if conn.target_cell_id in [c.id for c in community]:
                    all_weights.append(conn.weight)
        
        avg_strength = sum(all_weights) / len(all_weights) if all_weights else 0.0
        
        # 综合强度
        return (density + avg_strength) / 2.0
    
    def get_emergent_patterns(self) -> List[Dict[str, Any]]:
        """获取检测到的涌现模式"""
        return self.emergent_patterns
    
    def get_system_state(self) -> Dict[str, Any]:
        """获取系统状态"""
        cells = self.energy_monitor.cells
        
        return {
            'total_cells': len(cells),
            'active_cells': sum(1 for c in cells if c.is_active),
            'avg_energy': self.energy_monitor.get_average_energy(),
            'emergent_patterns': len(self.emergent_patterns),
            'communities': self.self_organization.detect_communities(cells)
        }
    
    async def trigger_emergence(self, stimulus: str):
        """
        触发涌现行为
        
        Args:
            stimulus: 刺激信号
        """
        # 创建刺激信号
        stimulus_signal = Signal(
            type=SignalType.DATA,
            priority=3,
            content={'stimulus': stimulus, 'type': 'emergence_trigger'}
        )
        
        await self.signal_router.route_signal(stimulus_signal)


class SwarmIntelligence:
    """
    群体智能模块
    
    实现基于蚁群/蜂群算法的群体决策机制。
    """
    
    def __init__(self):
        self.pheromone_trails = defaultdict(float)
        self.evaporation_rate = 0.01
        self.discovery_rate = 0.1
    
    async def collective_decision(self, cells: List[Cell], options: List[str]) -> str:
        """
        群体决策
        
        Args:
            cells: 参与决策的细胞
            options: 可选选项
        
        Returns:
            群体选择的结果
        """
        votes = defaultdict(int)
        
        # 每个细胞投票
        for cell in cells:
            vote = await self._cell_vote(cell, options)
            votes[vote] += 1
        
        # 返回票数最多的选项
        if votes:
            return max(votes, key=votes.get)
        
        return options[0] if options else ""
    
    async def _cell_vote(self, cell: Cell, options: List[str]) -> str:
        """
        单个细胞投票
        
        Args:
            cell: 投票细胞
            options: 可选选项
        
        Returns:
            细胞选择的选项
        """
        # 基于信息素的决策
        pheromone_values = []
        
        for option in options:
            trail_key = f"{cell.id}-{option}"
            pheromone = self.pheromone_trails[trail_key]
            
            # 随机探索
            if random.random() < self.discovery_rate:
                pheromone += random.random() * 0.1
            
            pheromone_values.append((option, pheromone))
        
        # 选择信息素最高的选项
        pheromone_values.sort(key=lambda x: x[1], reverse=True)
        chosen = pheromone_values[0][0]
        
        # 更新信息素
        self._update_pheromone(cell.id, chosen, 0.1)
        
        return chosen
    
    def _update_pheromone(self, cell_id: str, option: str, delta: float):
        """
        更新信息素
        
        Args:
            cell_id: 细胞ID
            option: 选项
            delta: 变化量
        """
        key = f"{cell_id}-{option}"
        self.pheromone_trails[key] = max(0.0, min(1.0, self.pheromone_trails[key] + delta))
        
        # 全局蒸发
        for k in list(self.pheromone_trails.keys()):
            self.pheromone_trails[k] = max(0.0, self.pheromone_trails[k] - self.evaporation_rate)
    
    def reward_option(self, option: str, reward: float = 0.1):
        """
        奖励某个选项
        
        Args:
            option: 选项
            reward: 奖励值
        """
        for key in self.pheromone_trails:
            if key.endswith(f"-{option}"):
                self.pheromone_trails[key] = min(1.0, self.pheromone_trails[key] + reward)
    
    def punish_option(self, option: str, penalty: float = 0.1):
        """
        惩罚某个选项
        
        Args:
            option: 选项
            penalty: 惩罚值
        """
        for key in self.pheromone_trails:
            if key.endswith(f"-{option}"):
                self.pheromone_trails[key] = max(0.0, self.pheromone_trails[key] - penalty)