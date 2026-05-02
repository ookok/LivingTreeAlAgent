"""
进化引擎模块

实现细胞的进化机制：
- 细胞分裂
- 变异
- 自然选择
- 知识传承
"""

import uuid
import copy
import random
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime
from .cell import Cell, CellType, EnergyMonitor
from .reasoning_cell import ReasoningCell, CausalReasoningCell, SymbolicReasoningCell
from .memory_cell import MemoryCell, HippocampusCell, NeocortexCell
from .learning_cell import LearningCell, EWCCell, ProgressiveCell, MetaLearningCell
from .perception_cell import PerceptionCell, MultimodalCell, IntentCell
from .action_cell import ActionCell, CodeCell, ToolCell, GenerationCell


class MutationType(Enum):
    """变异类型"""
    NONE = "none"
    SMALL = "small"       # 小变异（参数微调）
    MEDIUM = "medium"     # 中等变异（结构调整）
    LARGE = "large"       # 大变异（功能扩展）
    RADICAL = "radical"   # 激进变异（全新功能）


class EvolutionStrategy(Enum):
    """进化策略"""
    SURVIVAL_OF_FITTEST = "survival_of_fittest"  # 适者生存
    STABILIZING = "stabilizing"                  # 稳定选择
    DIRECTIONAL = "directional"                  # 定向选择
    DISRUPTIVE = "disruptive"                    # 分裂选择


class CellDivision:
    """
    细胞分裂机制
    
    成功的细胞可以复制自身并产生变异。
    """
    
    def __init__(self):
        self.mutation_rates = {
            MutationType.SMALL: 0.6,
            MutationType.MEDIUM: 0.3,
            MutationType.LARGE: 0.08,
            MutationType.RADICAL: 0.02
        }
        
        self.min_success_rate_for_division = 0.8
        self.min_processed_for_division = 10
    
    def can_divide(self, cell: Cell) -> bool:
        """
        判断细胞是否可以分裂
        
        Args:
            cell: 待判断的细胞
        
        Returns:
            是否可以分裂
        """
        return (cell.success_rate >= self.min_success_rate_for_division and
                cell.total_processed >= self.min_processed_for_division)
    
    def divide(self, parent_cell: Cell) -> Optional[Cell]:
        """
        细胞分裂
        
        Args:
            parent_cell: 父细胞
        
        Returns:
            子细胞（带变异）
        """
        if not self.can_divide(parent_cell):
            return None
        
        # 创建子细胞（深拷贝）
        child_cell = copy.deepcopy(parent_cell)
        child_cell.id = str(uuid.uuid4())[:8]  # 新ID
        child_cell.specialization = f"{parent_cell.specialization}_child"
        
        # 重置一些属性
        child_cell.signal_history = []
        child_cell.total_processed = 0
        child_cell.errors = 0
        child_cell.success_rate = 0.5
        child_cell.energy_level = 0.5
        
        # 应用变异
        mutation_type = self._select_mutation_type()
        self._apply_mutation(child_cell, mutation_type)
        
        return child_cell
    
    def _select_mutation_type(self) -> MutationType:
        """选择变异类型"""
        rand = random.random()
        cumulative = 0.0
        
        for mutation_type, rate in self.mutation_rates.items():
            cumulative += rate
            if rand <= cumulative:
                return mutation_type
        
        return MutationType.SMALL
    
    def _apply_mutation(self, cell: Cell, mutation_type: MutationType):
        """
        应用变异
        
        Args:
            cell: 目标细胞
            mutation_type: 变异类型
        """
        if mutation_type == MutationType.NONE:
            return
        
        # 根据细胞类型应用不同的变异
        if isinstance(cell, ReasoningCell):
            self._mutate_reasoning_cell(cell, mutation_type)
        elif isinstance(cell, MemoryCell):
            self._mutate_memory_cell(cell, mutation_type)
        elif isinstance(cell, LearningCell):
            self._mutate_learning_cell(cell, mutation_type)
        elif isinstance(cell, PerceptionCell):
            self._mutate_perception_cell(cell, mutation_type)
        elif isinstance(cell, ActionCell):
            self._mutate_action_cell(cell, mutation_type)
    
    def _mutate_reasoning_cell(self, cell: ReasoningCell, mutation_type: MutationType):
        """变异推理细胞"""
        if mutation_type == MutationType.SMALL:
            cell.max_depth = max(1, min(20, cell.max_depth + random.randint(-2, 2)))
            cell.confidence_threshold = max(0.1, min(0.95, cell.confidence_threshold + random.uniform(-0.05, 0.05)))
        
        elif mutation_type == MutationType.MEDIUM:
            # 切换推理模式
            modes = [m for m in ['deductive', 'inductive', 'abductive', 'analogical']]
            cell.reasoning_mode = cell.reasoning_mode
        
        elif mutation_type == MutationType.LARGE:
            # 增强因果推理能力
            if isinstance(cell, ReasoningCell) and not isinstance(cell, CausalReasoningCell):
                cell.specialization = "enhanced_reasoning"
    
    def _mutate_memory_cell(self, cell: MemoryCell, mutation_type: MutationType):
        """变异记忆细胞"""
        if mutation_type == MutationType.SMALL:
            cell.max_items = max(10, min(10000, cell.max_items + random.randint(-50, 50)))
        
        elif mutation_type == MutationType.MEDIUM:
            cell.ttl_days = max(1, min(365, cell.ttl_days + random.randint(-30, 30)))
        
        elif mutation_type == MutationType.LARGE:
            # 添加知识图谱能力
            cell.specialization = "memory_with_graph"
    
    def _mutate_learning_cell(self, cell: LearningCell, mutation_type: MutationType):
        """变异学习细胞"""
        if mutation_type == MutationType.SMALL:
            cell.learning_rate = max(0.0001, min(0.1, cell.learning_rate * random.uniform(0.8, 1.2)))
        
        elif mutation_type == MutationType.MEDIUM:
            cell.min_samples_for_learning = max(1, min(100, cell.min_samples_for_learning + random.randint(-5, 5)))
        
        elif mutation_type == MutationType.LARGE:
            # 切换学习策略
            strategies = ['supervised', 'reinforcement', 'unsupervised', 'imitation']
            cell.learning_strategy = cell.learning_strategy
    
    def _mutate_perception_cell(self, cell: PerceptionCell, mutation_type: MutationType):
        """变异感知细胞"""
        if mutation_type == MutationType.SMALL:
            cell.max_input_size = max(1024, min(10*1024*1024, cell.max_input_size * random.uniform(0.9, 1.1)))
        
        elif mutation_type == MutationType.MEDIUM:
            # 添加新的输入类型支持
            pass
        
        elif mutation_type == MutationType.LARGE:
            cell.specialization = "multimodal_enhanced"
    
    def _mutate_action_cell(self, cell: ActionCell, mutation_type: MutationType):
        """变异行动细胞"""
        if mutation_type == MutationType.SMALL:
            pass
        
        elif mutation_type == MutationType.MEDIUM:
            # 添加新的输出格式支持
            pass
        
        elif mutation_type == MutationType.LARGE:
            cell.specialization = "multi_action"


class NaturalSelection:
    """
    自然选择机制
    
    根据细胞的表现选择保留或淘汰。
    """
    
    def __init__(self):
        self.selection_pressure = 0.2  # 每代淘汰比例
        self.min_energy_threshold = 0.1
        self.max_age_for_reproduction = 1000  # 最大处理次数
    
    def select(self, cells: List[Cell]) -> List[Cell]:
        """
        自然选择
        
        Args:
            cells: 细胞群体
        
        Returns:
            存活的细胞列表
        """
        # 计算适应度
        fitness_scores = [(cell, self._calculate_fitness(cell)) for cell in cells]
        
        # 按适应度排序
        fitness_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 确定淘汰数量
        survival_count = max(1, int(len(cells) * (1 - self.selection_pressure)))
        
        # 选择适应度最高的细胞
        survivors = [fs[0] for fs in fitness_scores[:survival_count]]
        
        return survivors
    
    def _calculate_fitness(self, cell: Cell) -> float:
        """
        计算细胞适应度
        
        Args:
            cell: 目标细胞
        
        Returns:
            适应度分数 (0-1)
        """
        # 基础适应度 = 成功率
        fitness = cell.success_rate
        
        # 能量惩罚
        if cell.energy_level < self.min_energy_threshold:
            fitness *= 0.5
        
        # 年龄惩罚（太老的细胞适应性降低）
        age_factor = max(0.5, 1.0 - (cell.total_processed / self.max_age_for_reproduction) * 0.5)
        fitness *= age_factor
        
        # 活跃度奖励
        if cell.is_active:
            fitness *= 1.1
        
        return min(1.0, max(0.0, fitness))
    
    def should_eliminated(self, cell: Cell) -> bool:
        """
        判断细胞是否应该被淘汰
        
        Args:
            cell: 目标细胞
        
        Returns:
            是否应该淘汰
        """
        # 死亡细胞直接淘汰
        if cell.state == 'dead':
            return True
        
        # 能量耗尽
        if cell.energy_level < self.min_energy_threshold:
            return True
        
        # 成功率太低
        if cell.total_processed > 10 and cell.success_rate < 0.3:
            return True
        
        return False


class EvolutionEngine:
    """
    进化引擎
    
    管理整个细胞群体的进化过程。
    """
    
    def __init__(self):
        self.cell_division = CellDivision()
        self.natural_selection = NaturalSelection()
        self.energy_monitor = EnergyMonitor()
        self.evolution_strategy = EvolutionStrategy.SURVIVAL_OF_FITTEST
        self.generation = 0
        self.max_population = 100
    
    def set_cell_registry(self, registry):
        """设置细胞注册表"""
        self.cell_registry = registry
    
    async def run_generation(self):
        """运行一代进化"""
        self.generation += 1
        
        # 获取当前细胞群体
        cells = self.energy_monitor.cells
        
        # 自然选择
        survivors = self.natural_selection.select(cells)
        
        # 淘汰不合格细胞
        for cell in cells:
            if cell not in survivors:
                cell.kill()
                self.energy_monitor.unregister_cell(cell)
        
        # 细胞分裂
        new_cells = []
        for cell in survivors:
            if self.cell_division.can_divide(cell):
                child = self.cell_division.divide(cell)
                if child:
                    new_cells.append(child)
        
        # 添加新细胞（不超过最大种群数量）
        current_count = len(survivors)
        for i, child in enumerate(new_cells):
            if current_count + i < self.max_population:
                self.energy_monitor.register_cell(child)
        
        # 均衡能量
        self.energy_monitor.balance_energy()
    
    def get_evolution_stats(self) -> Dict[str, Any]:
        """获取进化统计信息"""
        cells = self.energy_monitor.cells
        
        type_counts = {}
        for ct in CellType:
            type_counts[ct.value] = sum(1 for c in cells if c.cell_type == ct)
        
        avg_success_rate = sum(c.success_rate for c in cells) / len(cells) if cells else 0
        avg_energy = sum(c.energy_level for c in cells) / len(cells) if cells else 0
        
        return {
            'generation': self.generation,
            'population_size': len(cells),
            'cell_types': type_counts,
            'avg_success_rate': round(avg_success_rate, 2),
            'avg_energy': round(avg_energy, 2),
            'strategy': self.evolution_strategy.value
        }
    
    def set_strategy(self, strategy: EvolutionStrategy):
        """设置进化策略"""
        self.evolution_strategy = strategy
    
    def save_population(self, filepath: str):
        """保存种群状态"""
        import pickle
        
        population_data = {
            'generation': self.generation,
            'cells': self.energy_monitor.cells,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(population_data, f)
    
    def load_population(self, filepath: str) -> bool:
        """加载种群状态"""
        import pickle
        
        try:
            with open(filepath, 'rb') as f:
                population_data = pickle.load(f)
            
            self.generation = population_data['generation']
            
            # 注册加载的细胞
            for cell in population_data['cells']:
                self.energy_monitor.register_cell(cell)
            
            return True
        except Exception:
            return False


class SpeciesTracker:
    """
    物种追踪器
    
    追踪细胞类型的演化历史。
    """
    
    def __init__(self):
        self.species_history = []
        self.species_diversity = {}
    
    def record_generation(self, cells: List[Cell]):
        """记录一代的物种分布"""
        generation_data = {
            'generation': len(self.species_history),
            'timestamp': datetime.now().isoformat(),
            'species_counts': {}
        }
        
        for cell in cells:
            species_key = f"{cell.cell_type.value}:{cell.specialization}"
            generation_data['species_counts'][species_key] = \
                generation_data['species_counts'].get(species_key, 0) + 1
        
        self.species_history.append(generation_data)
        
        # 更新物种多样性统计
        for species in generation_data['species_counts']:
            if species not in self.species_diversity:
                self.species_diversity[species] = {
                    'first_seen': len(self.species_history),
                    'last_seen': len(self.species_history),
                    'total_generations': 1
                }
            else:
                self.species_diversity[species]['last_seen'] = len(self.species_history)
                self.species_diversity[species]['total_generations'] += 1
    
    def get_diversity_report(self) -> Dict[str, Any]:
        """获取物种多样性报告"""
        return {
            'total_species': len(self.species_diversity),
            'current_species': self.species_history[-1]['species_counts'] if self.species_history else {},
            'endangered_species': [
                species for species, data in self.species_diversity.items()
                if data['total_generations'] < 3
            ],
            'dominant_species': [
                species for species, data in self.species_diversity.items()
                if data['total_generations'] > len(self.species_history) * 0.5
            ]
        }