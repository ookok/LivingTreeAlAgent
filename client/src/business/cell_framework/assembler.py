"""
模型组装流水线

负责根据任务描述自动选择和组合细胞模块。
"""

from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import asyncio
from .cell import Cell, CellType
from .reasoning_cell import ReasoningCell, CausalReasoningCell, SymbolicReasoningCell
from .memory_cell import MemoryCell, HippocampusCell, NeocortexCell
from .learning_cell import LearningCell, EWCCell, ProgressiveCell, MetaLearningCell
from .perception_cell import PerceptionCell, MultimodalCell, IntentCell
from .action_cell import ActionCell, CodeCell, ToolCell, GenerationCell


class TaskComplexity(Enum):
    """任务复杂度"""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    EXPERT = "expert"


class TaskType(Enum):
    """任务类型"""
    REASONING = "reasoning"
    MEMORY = "memory"
    LEARNING = "learning"
    PERCEPTION = "perception"
    ACTION = "action"
    MULTIMODAL = "multimodal"


class CellRegistry:
    """
    细胞注册表
    
    管理所有细胞的注册和查询。
    """
    
    _instance = None
    _cells: Dict[str, Cell] = {}
    
    def __init__(self):
        self._cells = {}
    
    @classmethod
    def get_instance(cls) -> 'CellRegistry':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def register_cell(self, cell: Cell):
        """注册细胞"""
        self._cells[cell.id] = cell
    
    def unregister_cell(self, cell_id: str):
        """注销细胞"""
        if cell_id in self._cells:
            del self._cells[cell_id]
    
    def get_cell(self, cell_id: str) -> Optional[Cell]:
        """获取细胞"""
        return self._cells.get(cell_id)
    
    def get_cells_by_type(self, cell_type: CellType) -> List[Cell]:
        """按类型获取细胞"""
        return [cell for cell in self._cells.values() if cell.cell_type == cell_type]
    
    def get_all_cells(self) -> List[Cell]:
        """获取所有细胞"""
        return list(self._cells.values())
    
    def get_cell_stats(self) -> Dict[str, Any]:
        """获取细胞统计信息"""
        stats = {}
        for cell_type in CellType:
            cells = self.get_cells_by_type(cell_type)
            stats[cell_type.value] = {
                'count': len(cells),
                'active': sum(1 for c in cells if c.is_active),
                'dormant': sum(1 for c in cells if c.state == 'dormant')
            }
        return stats
    
    def clear(self):
        """清空所有细胞"""
        self._cells = {}


class ModelAssemblyLine:
    """
    模型组装流水线
    
    根据任务描述自动分析需求、选择细胞、组合模型。
    """
    
    def __init__(self):
        self.cell_registry = CellRegistry.get_instance()
        self.assembly_rules = self._load_assembly_rules()
    
    def _load_assembly_rules(self) -> List[Dict[str, Any]]:
        """加载组装规则"""
        return [
            # 推理任务
            {
                'task_type': TaskType.REASONING,
                'complexity': TaskComplexity.SIMPLE,
                'cells': ['reasoning'],
                'configuration': {'max_depth': 3}
            },
            {
                'task_type': TaskType.REASONING,
                'complexity': TaskComplexity.MEDIUM,
                'cells': ['reasoning', 'memory'],
                'configuration': {'max_depth': 5}
            },
            {
                'task_type': TaskType.REASONING,
                'complexity': TaskComplexity.COMPLEX,
                'cells': ['causal', 'symbolic', 'memory'],
                'configuration': {'max_depth': 10}
            },
            
            # 记忆任务
            {
                'task_type': TaskType.MEMORY,
                'complexity': TaskComplexity.SIMPLE,
                'cells': ['hippocampus'],
                'configuration': {}
            },
            {
                'task_type': TaskType.MEMORY,
                'complexity': TaskComplexity.COMPLEX,
                'cells': ['hippocampus', 'neocortex'],
                'configuration': {}
            },
            
            # 学习任务
            {
                'task_type': TaskType.LEARNING,
                'complexity': TaskComplexity.SIMPLE,
                'cells': ['learning'],
                'configuration': {'learning_rate': 0.01}
            },
            {
                'task_type': TaskType.LEARNING,
                'complexity': TaskComplexity.COMPLEX,
                'cells': ['ewc', 'progressive', 'metalearning'],
                'configuration': {'learning_rate': 0.001}
            },
            
            # 感知任务
            {
                'task_type': TaskType.PERCEPTION,
                'complexity': TaskComplexity.SIMPLE,
                'cells': ['perception'],
                'configuration': {}
            },
            {
                'task_type': TaskType.PERCEPTION,
                'complexity': TaskComplexity.COMPLEX,
                'cells': ['multimodal', 'intent'],
                'configuration': {}
            },
            
            # 行动任务
            {
                'task_type': TaskType.ACTION,
                'complexity': TaskComplexity.SIMPLE,
                'cells': ['action'],
                'configuration': {}
            },
            {
                'task_type': TaskType.ACTION,
                'complexity': TaskComplexity.COMPLEX,
                'cells': ['code', 'tool', 'generation'],
                'configuration': {}
            },
            
            # 多模态任务
            {
                'task_type': TaskType.MULTIMODAL,
                'complexity': TaskComplexity.COMPLEX,
                'cells': ['multimodal', 'reasoning', 'generation'],
                'configuration': {}
            },
        ]
    
    def _analyze_task(self, task_description: str) -> Dict[str, Any]:
        """
        分析任务需求
        
        Args:
            task_description: 任务描述
        
        Returns:
            分析结果
        """
        task_desc_lower = task_description.lower()
        
        # 识别任务类型
        task_type = self._detect_task_type(task_desc_lower)
        
        # 评估复杂度
        complexity = self._evaluate_complexity(task_desc_lower)
        
        # 提取关键特征
        features = self._extract_features(task_desc_lower)
        
        return {
            'task_type': task_type,
            'complexity': complexity,
            'features': features,
            'raw_description': task_description
        }
    
    def _detect_task_type(self, task_desc: str) -> TaskType:
        """检测任务类型"""
        # 推理相关关键词
        reasoning_keywords = ['reason', 'infer', 'logic', 'analyze', 'solve', 'prove', 'deduce']
        if any(kw in task_desc for kw in reasoning_keywords):
            return TaskType.REASONING
        
        # 记忆相关关键词
        memory_keywords = ['remember', 'recall', 'store', 'retrieve', 'knowledge', 'memory']
        if any(kw in task_desc for kw in memory_keywords):
            return TaskType.MEMORY
        
        # 学习相关关键词
        learning_keywords = ['learn', 'train', 'adapt', 'evolve', 'improve', 'update']
        if any(kw in task_desc for kw in learning_keywords):
            return TaskType.LEARNING
        
        # 感知相关关键词
        perception_keywords = ['understand', 'parse', 'recognize', 'interpret', 'input']
        if any(kw in task_desc for kw in perception_keywords):
            return TaskType.PERCEPTION
        
        # 行动相关关键词
        action_keywords = ['generate', 'create', 'code', 'write', 'execute', 'call']
        if any(kw in task_desc for kw in action_keywords):
            return TaskType.ACTION
        
        # 多模态相关关键词
        multimodal_keywords = ['image', 'audio', 'video', 'multimodal', 'vision']
        if any(kw in task_desc for kw in multimodal_keywords):
            return TaskType.MULTIMODAL
        
        return TaskType.REASONING  # 默认
    
    def _evaluate_complexity(self, task_desc: str) -> TaskComplexity:
        """评估任务复杂度"""
        # 简单任务：简短描述，单一动作
        if len(task_desc.split()) <= 5:
            return TaskComplexity.SIMPLE
        
        # 复杂任务：包含多个动作或需要专业知识
        complex_keywords = ['complex', 'detailed', 'advanced', 'expert', 'multi-step', 'comprehensive']
        if any(kw in task_desc for kw in complex_keywords):
            return TaskComplexity.COMPLEX
        
        # 专家任务：涉及高级技术或深度分析
        expert_keywords = ['deep', 'research', 'thesis', 'algorithm', 'optimization']
        if any(kw in task_desc for kw in expert_keywords):
            return TaskComplexity.EXPERT
        
        return TaskComplexity.MEDIUM  # 默认
    
    def _extract_features(self, task_desc: str) -> List[str]:
        """提取任务特征"""
        features = []
        
        if 'code' in task_desc:
            features.append('code')
        if 'image' in task_desc:
            features.append('image')
        if 'video' in task_desc:
            features.append('video')
        if 'audio' in task_desc:
            features.append('audio')
        if 'api' in task_desc:
            features.append('api')
        if 'database' in task_desc:
            features.append('database')
        
        return features
    
    def _select_cells(self, requirements: Dict[str, Any]) -> List[Cell]:
        """
        根据需求选择细胞
        
        Args:
            requirements: 任务需求
        
        Returns:
            选中的细胞列表
        """
        task_type = requirements['task_type']
        complexity = requirements['complexity']
        features = requirements.get('features', [])
        
        # 查找匹配的组装规则
        matching_rules = [
            rule for rule in self.assembly_rules
            if rule['task_type'] == task_type and rule['complexity'] == complexity
        ]
        
        if not matching_rules:
            # 如果没有精确匹配，找同类型的最低复杂度规则
            matching_rules = [
                rule for rule in self.assembly_rules
                if rule['task_type'] == task_type
            ]
            if matching_rules:
                matching_rules.sort(key=lambda r: r['complexity'].value)
                matching_rules = [matching_rules[0]]
        
        selected_cells = []
        
        if matching_rules:
            rule = matching_rules[0]
            cell_names = rule['cells']
            
            for cell_name in cell_names:
                # 尝试从注册表获取，否则创建新细胞
                cell = self._get_or_create_cell(cell_name)
                if cell:
                    selected_cells.append(cell)
        
        return selected_cells
    
    def _get_or_create_cell(self, cell_name: str) -> Optional[Cell]:
        """获取或创建细胞"""
        # 先检查注册表中是否有空闲细胞
        cell_map = {
            'reasoning': ReasoningCell,
            'causal': CausalReasoningCell,
            'symbolic': SymbolicReasoningCell,
            'memory': MemoryCell,
            'hippocampus': HippocampusCell,
            'neocortex': NeocortexCell,
            'learning': LearningCell,
            'ewc': EWCCell,
            'progressive': ProgressiveCell,
            'metalearning': MetaLearningCell,
            'perception': PerceptionCell,
            'multimodal': MultimodalCell,
            'intent': IntentCell,
            'action': ActionCell,
            'code': CodeCell,
            'tool': ToolCell,
            'generation': GenerationCell,
        }
        
        cell_class = cell_map.get(cell_name)
        if cell_class:
            cell = cell_class()
            self.cell_registry.register_cell(cell)
            return cell
        
        return None
    
    def _combine_cells(self, selected_cells: List[Cell]) -> 'AssembledModel':
        """
        组合细胞
        
        Args:
            selected_cells: 选中的细胞列表
        
        Returns:
            组装好的模型
        """
        return AssembledModel(selected_cells)
    
    def _optimize(self, model: 'AssembledModel') -> 'AssembledModel':
        """
        优化配置
        
        Args:
            model: 待优化的模型
        
        Returns:
            优化后的模型
        """
        # 连接细胞
        model.connect_cells()
        
        # 设置能量均衡
        model.balance_energy()
        
        return model
    
    def assemble(self, task_description: str) -> 'AssembledModel':
        """
        根据任务自动组装模型
        
        Args:
            task_description: 任务描述
        
        Returns:
            组装好的模型
        """
        # 1. 分析任务需求
        requirements = self._analyze_task(task_description)
        
        # 2. 智能选择细胞
        selected_cells = self._select_cells(requirements)
        
        # 3. 动态组合
        combined_model = self._combine_cells(selected_cells)
        
        # 4. 优化配置
        optimized_model = self._optimize(combined_model)
        
        return optimized_model


class AssembledModel:
    """
    组装好的模型
    
    由多个细胞组成的协作网络。
    """
    
    def __init__(self, cells: List[Cell]):
        self.cells = cells
        self.model_id = f"model_{hash(tuple(c.id for c in cells)):08x}"
        self.connections = []
    
    def connect_cells(self):
        """建立细胞间连接"""
        # 创建全连接网络
        for i, cell1 in enumerate(self.cells):
            for j, cell2 in enumerate(self.cells):
                if i != j:
                    cell1.connect(cell2, initial_weight=0.3)
    
    def balance_energy(self):
        """均衡能量"""
        if not self.cells:
            return
        
        avg_energy = sum(cell.energy_level for cell in self.cells) / len(self.cells)
        
        for cell in self.cells:
            if cell.energy_level > avg_energy + 0.2:
                surplus = cell.energy_level - avg_energy
                cell.energy_level = avg_energy
                # 分配给低能量细胞
                for target in self.cells:
                    if target.energy_level < avg_energy:
                        target.recharge(surplus / len(self.cells))
    
    async def execute(self, input_data: Any) -> Dict[str, Any]:
        """
        执行模型
        
        Args:
            input_data: 输入数据
        
        Returns:
            执行结果
        """
        results = []
        
        # 首先通过感知细胞处理输入
        perception_cells = [c for c in self.cells if c.cell_type == CellType.PERCEPTION]
        if perception_cells:
            for cell in perception_cells:
                result = await cell.receive_signal({
                    'type': 'parse',
                    'input': input_data,
                    'input_type': 'text'
                })
                results.append({'cell_id': cell.id, 'type': 'perception', 'result': result})
        
        # 然后通过推理细胞处理
        reasoning_cells = [c for c in self.cells if c.cell_type == CellType.REASONING]
        if reasoning_cells:
            for cell in reasoning_cells:
                result = await cell.receive_signal({
                    'type': 'reason',
                    'query': input_data,
                    'mode': 'deductive'
                })
                results.append({'cell_id': cell.id, 'type': 'reasoning', 'result': result})
        
        # 最后通过行动细胞生成输出
        action_cells = [c for c in self.cells if c.cell_type == CellType.ACTION]
        if action_cells:
            for cell in action_cells:
                result = await cell.receive_signal({
                    'type': 'generate',
                    'prompt': input_data,
                    'format': 'text'
                })
                results.append({'cell_id': cell.id, 'type': 'action', 'result': result})
        
        return {
            'model_id': self.model_id,
            'cell_count': len(self.cells),
            'results': results,
            'summary': self._summarize_results(results)
        }
    
    def _summarize_results(self, results: List[Dict[str, Any]]) -> str:
        """总结结果"""
        success_count = sum(1 for r in results if r.get('result', {}).get('success', False))
        return f"Executed {len(results)} cells, {success_count} succeeded."
    
    def get_stats(self) -> Dict[str, Any]:
        """获取模型统计信息"""
        return {
            'model_id': self.model_id,
            'cell_count': len(self.cells),
            'cell_types': [c.cell_type.value for c in self.cells],
            'total_connections': sum(len(c.connections) for c in self.cells),
            'avg_energy': sum(c.energy_level for c in self.cells) / len(self.cells) if self.cells else 0
        }
    
    def __repr__(self):
        return f"<AssembledModel id={self.model_id} cells={len(self.cells)}>"