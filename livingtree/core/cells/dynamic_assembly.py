"""
动态细胞重组系统 - DynamicAssembly

实现细胞的动态组装和重组能力：
1. 任务分析和需求提取
2. 智能细胞选择
3. 动态连接建立
4. 组装优化

核心思想：根据任务需求自动选择和组合细胞模块，形成最优的处理流水线。
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from enum import Enum
import random


class AssemblyStrategy(Enum):
    """组装策略"""
    OPTIMAL = "optimal"           # 最优组合
    FAST = "fast"                 # 快速组装
    ROBUST = "robust"             # 稳健组合
    ADAPTIVE = "adaptive"         # 自适应组合


class AssemblyQuality(Enum):
    """组装质量"""
    EXCELLENT = "excellent"       # 优秀
    GOOD = "good"                 # 良好
    ACCEPTABLE = "acceptable"     # 可接受
    POOR = "poor"                 # 较差


class TaskRequirement:
    """任务需求"""
    
    def __init__(self, requirement_id: str, category: str, importance: float, threshold: float):
        self.id = requirement_id
        self.category = category
        self.importance = importance
        self.threshold = threshold
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'category': self.category,
            'importance': self.importance,
            'threshold': self.threshold
        }


class AssemblyResult:
    """组装结果"""
    
    def __init__(self, assembly_id: str, cells: List['Cell'], connections: List[Dict]):
        self.id = assembly_id
        self.cells = cells
        self.connections = connections
        self.created_at = datetime.now()
        self.quality = AssemblyQuality.ACCEPTABLE
        self.efficiency = 0.0
        self.performance = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'cell_count': len(self.cells),
            'connection_count': len(self.connections),
            'created_at': self.created_at.isoformat(),
            'quality': self.quality.value,
            'efficiency': self.efficiency,
            'performance': self.performance,
            'cell_types': [c.cell_type.value for c in self.cells]
        }


class DynamicAssembly:
    """
    动态细胞组装器
    
    负责根据任务需求智能选择和组合细胞。
    """
    
    def __init__(self):
        self.id = str(uuid.uuid4())[:8]
        self.assembly_history: List[AssemblyResult] = []
        self.strategy = AssemblyStrategy.ADAPTIVE
        
        # 细胞能力映射
        self.cell_capabilities: Dict[str, List[str]] = {
            'reasoning': ['logic', 'causal', 'symbolic', 'problem_solving'],
            'memory': ['storage', 'retrieval', 'knowledge', 'pattern_matching'],
            'learning': ['adaptation', 'generalization', 'continual', 'meta_learning'],
            'perception': ['multimodal', 'intent', 'recognition', 'parsing'],
            'action': ['execution', 'generation', 'tool_use', 'code'],
            'prediction': ['forecasting', 'trend_analysis', 'scenario', 'time_series']
        }
    
    async def assemble_for_task(self, task_description: str) -> AssemblyResult:
        """
        根据任务描述组装细胞
        
        Args:
            task_description: 任务描述
        
        Returns:
            组装结果
        """
        assembly_id = f"assembly_{str(uuid.uuid4())[:8]}"
        
        # 1. 分析任务需求
        requirements = await self._analyze_task(task_description)
        
        # 2. 智能选择细胞
        selected_cells = await self._select_cells(requirements)
        
        # 3. 建立连接
        connections = await self._establish_connections(selected_cells)
        
        # 4. 优化配置
        await self._optimize_assembly(selected_cells, connections)
        
        # 5. 创建组装结果
        result = AssemblyResult(assembly_id, selected_cells, connections)
        result.quality = self._evaluate_quality(selected_cells, requirements)
        result.efficiency = self._calculate_efficiency(selected_cells, connections)
        
        self.assembly_history.append(result)
        
        return result
    
    async def _analyze_task(self, task_description: str) -> List[TaskRequirement]:
        """分析任务需求"""
        requirements = []
        
        # 关键词匹配
        keywords = {
            'reasoning': ['推理', '分析', '逻辑', '证明', '论证'],
            'memory': ['记忆', '回忆', '存储', '知识', '历史'],
            'learning': ['学习', '训练', '适应', '改进', '优化'],
            'perception': ['理解', '识别', '解析', '感知', '输入'],
            'action': ['执行', '生成', '调用', '创建', '输出'],
            'prediction': ['预测', '未来', '趋势', '推演', '预估']
        }
        
        for category, kw_list in keywords.items():
            score = sum(1 for kw in kw_list if kw in task_description)
            if score > 0:
                importance = min(1.0, score / len(kw_list))
                requirements.append(TaskRequirement(
                    requirement_id=str(uuid.uuid4())[:8],
                    category=category,
                    importance=importance,
                    threshold=0.5
                ))
        
        # 如果没有匹配到任何需求，添加默认需求
        if not requirements:
            requirements.append(TaskRequirement(
                requirement_id=str(uuid.uuid4())[:8],
                category='reasoning',
                importance=0.5,
                threshold=0.5
            ))
        
        return requirements
    
    async def _select_cells(self, requirements: List[TaskRequirement]) -> List['Cell']:
        """智能选择细胞"""
        from .reasoning_cell import ReasoningCell
        from .memory_cell import MemoryCell
        from .learning_cell import LearningCell
        from .perception_cell import PerceptionCell
        from .action_cell import ActionCell
        from .prediction_cell import PredictionCell
        from .assembler import CellRegistry
        
        registry = CellRegistry.get_instance()
        selected_cells: List['Cell'] = []
        
        cell_map = {
            'reasoning': ReasoningCell,
            'memory': MemoryCell,
            'learning': LearningCell,
            'perception': PerceptionCell,
            'action': ActionCell,
            'prediction': PredictionCell
        }
        
        for req in requirements:
            cell_class = cell_map.get(req.category)
            if cell_class:
                # 尝试从注册表获取现有细胞
                existing_cells = registry.get_cells_by_type(
                    self._category_to_cell_type(req.category)
                )
                
                if existing_cells and req.importance < 0.8:
                    # 使用现有细胞
                    cell = random.choice(existing_cells)
                else:
                    # 创建新细胞
                    cell = cell_class()
                    registry.register_cell(cell)
                
                selected_cells.append(cell)
        
        return selected_cells
    
    def _category_to_cell_type(self, category: str) -> 'CellType':
        """将类别转换为细胞类型"""
        from .cell import CellType
        
        type_map = {
            'reasoning': CellType.REASONING,
            'memory': CellType.MEMORY,
            'learning': CellType.LEARNING,
            'perception': CellType.PERCEPTION,
            'action': CellType.ACTION,
            'prediction': CellType.PREDICTION
        }
        return type_map.get(category, CellType.REASONING)
    
    async def _establish_connections(self, cells: List['Cell']) -> List[Dict]:
        """建立细胞间连接"""
        connections = []
        
        if len(cells) < 2:
            return connections
        
        # 创建连接图
        for i, source_cell in enumerate(cells):
            for j, target_cell in enumerate(cells):
                if i != j:
                    # 基于能力匹配确定连接权重
                    weight = self._calculate_connection_weight(source_cell, target_cell)
                    
                    if weight > 0.3:
                        source_cell.connect(target_cell, initial_weight=weight)
                        connections.append({
                            'source': source_cell.id,
                            'target': target_cell.id,
                            'weight': weight,
                            'bidirectional': False
                        })
        
        return connections
    
    def _calculate_connection_weight(self, source: 'Cell', target: 'Cell') -> float:
        """计算连接权重"""
        source_capabilities = self.cell_capabilities.get(source.cell_type.value, [])
        target_capabilities = self.cell_capabilities.get(target.cell_type.value, [])
        
        # 计算能力匹配度
        overlap = set(source_capabilities) & set(target_capabilities)
        similarity = len(overlap) / max(len(source_capabilities), len(target_capabilities))
        
        # 添加随机性
        return min(1.0, max(0.1, similarity + random.uniform(-0.2, 0.2)))
    
    async def _optimize_assembly(self, cells: List['Cell'], connections: List[Dict]):
        """优化组装配置"""
        # 1. 剪枝弱连接
        for conn in connections[:]:
            if conn['weight'] < 0.3:
                connections.remove(conn)
        
        # 2. 优化细胞状态
        for cell in cells:
            cell.energy_level = min(1.0, cell.energy_level + 0.1)
        
        await asyncio.sleep(0.1)
    
    def _evaluate_quality(self, cells: List['Cell'], requirements: List[TaskRequirement]) -> AssemblyQuality:
        """评估组装质量"""
        cell_types = [c.cell_type.value for c in cells]
        matched_requirements = sum(1 for req in requirements if req.category in cell_types)
        
        match_ratio = matched_requirements / len(requirements)
        
        if match_ratio >= 0.9:
            return AssemblyQuality.EXCELLENT
        elif match_ratio >= 0.7:
            return AssemblyQuality.GOOD
        elif match_ratio >= 0.5:
            return AssemblyQuality.ACCEPTABLE
        else:
            return AssemblyQuality.POOR
    
    def _calculate_efficiency(self, cells: List['Cell'], connections: List[Dict]) -> float:
        """计算组装效率"""
        if not cells:
            return 0.0
        
        avg_energy = sum(c.energy_level for c in cells) / len(cells)
        connection_efficiency = sum(conn['weight'] for conn in connections) / max(len(connections), 1)
        
        return (avg_energy + connection_efficiency) / 2
    
    async def disassemble(self, assembly_id: str):
        """拆解组装"""
        for result in self.assembly_history:
            if result.id == assembly_id:
                # 断开连接
                for conn in result.connections:
                    source_cell = next((c for c in result.cells if c.id == conn['source']), None)
                    target_cell = next((c for c in result.cells if c.id == conn['target']), None)
                    if source_cell and target_cell:
                        source_cell.disconnect(target_cell)
                
                # 标记拆解
                result.quality = AssemblyQuality.POOR
                return True
        
        return False
    
    def get_assembly_history(self, limit: int = 10) -> List[Dict]:
        """获取组装历史"""
        return [r.to_dict() for r in self.assembly_history[-limit:]]
    
    def get_assembly_stats(self) -> Dict[str, Any]:
        """获取组装统计"""
        if not self.assembly_history:
            return {
                'total_assemblies': 0,
                'avg_quality': 0.0,
                'avg_efficiency': 0.0
            }
        
        qualities = [r.quality for r in self.assembly_history]
        avg_quality = sum(self._quality_to_score(q) for q in qualities) / len(qualities)
        avg_efficiency = sum(r.efficiency for r in self.assembly_history) / len(self.assembly_history)
        
        return {
            'total_assemblies': len(self.assembly_history),
            'avg_quality': avg_quality,
            'avg_efficiency': avg_efficiency,
            'excellent_count': sum(1 for q in qualities if q == AssemblyQuality.EXCELLENT),
            'good_count': sum(1 for q in qualities if q == AssemblyQuality.GOOD)
        }
    
    def _quality_to_score(self, quality: AssemblyQuality) -> float:
        """将质量转换为分数"""
        scores = {
            AssemblyQuality.EXCELLENT: 1.0,
            AssemblyQuality.GOOD: 0.8,
            AssemblyQuality.ACCEPTABLE: 0.6,
            AssemblyQuality.POOR: 0.3
        }
        return scores.get(quality, 0.5)


class AssemblyCache:
    """组装缓存"""
    
    def __init__(self):
        self.cache: Dict[str, AssemblyResult] = {}
        self.max_size = 100
    
    def get(self, task_description: str) -> Optional[AssemblyResult]:
        """从缓存获取组装"""
        key = self._generate_key(task_description)
        return self.cache.get(key)
    
    def put(self, task_description: str, result: AssemblyResult):
        """存入缓存"""
        key = self._generate_key(task_description)
        
        # 清理旧缓存
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k].created_at)
            del self.cache[oldest_key]
        
        self.cache[key] = result
    
    def _generate_key(self, task_description: str) -> str:
        """生成缓存键"""
        return str(hash(task_description))[:16]