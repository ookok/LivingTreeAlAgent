"""
细胞AI框架 - 革命性的模块化AI架构

核心思想：
1. 将AI能力拆分为独立的"细胞"模块
2. 每个细胞专注于特定功能
3. 通过细胞群体协作涌现高级智能
4. 支持自主进化和持续学习
5. 具备未来预测和情景推演能力

细胞类型：
- ReasoningCell: 逻辑推理
- MemoryCell: 知识存储
- LearningCell: 知识获取
- PerceptionCell: 输入处理
- ActionCell: 输出执行
- PredictionCell: 未来预测与情景推演

架构层次：
┌─────────────────────────────────────────────────────┐
│                    涌现智能层                        │
│  (细胞群体协作产生的高级认知能力)                     │
├─────────────────────────────────────────────────────┤
│                    预测推演层                        │
│  (时间序列预测、情景分析、趋势识别)                   │
├─────────────────────────────────────────────────────┤
│                    细胞通信层                        │
│  (信号传递、连接强度、Hebbian学习)                   │
├─────────────────────────────────────────────────────┤
│                    细胞执行层                        │
│  (推理、记忆、学习、感知、行动、预测细胞)             │
├─────────────────────────────────────────────────────┤
│                    基础资源层                        │
│  (内存管理、计算资源、能量效率)                      │
└─────────────────────────────────────────────────────┘
"""

from .cell import Cell, CellType, CellState, EnergyMonitor
from .reasoning_cell import ReasoningCell, CausalReasoningCell, SymbolicReasoningCell
from .memory_cell import MemoryCell, HippocampusCell, NeocortexCell
from .learning_cell import LearningCell, EWCCell, ProgressiveCell, MetaLearningCell
from .perception_cell import PerceptionCell, MultimodalCell, IntentCell
from .action_cell import ActionCell, CodeCell, ToolCell, GenerationCell
from .prediction_cell import PredictionCell, TimeSeriesPredictor, ResourcePredictor, HealthPredictor, ScenarioType, PredictionMethod
from .cell_signal import Signal, SignalType, SignalPriority
from .assembler import ModelAssemblyLine, CellRegistry
from .emergence import EmergenceEngine, SelfOrganization
from .evolution import EvolutionEngine, CellDivision, NaturalSelection
from .life_engine import LifeEngine, NeuralSymbolicIntegrator, BayesianPosterior, BeliefState, InferenceMode
from .self_consciousness import SelfConsciousness, SelfModel, ConsciousnessLevel, ReflectionMode
from .immune_system import ImmuneSystem, Threat, Antibody, ThreatLevel, ThreatType, DefenseStatus
from .metabolic_system import MetabolicSystem, ResourcePool, EnergyLevel, MetabolicState, ResourceType
from .autonomous_evolution import AutonomousEvolution, EvolutionPhase, MutationType, EvolutionRecord, Mutation
from .dynamic_assembly import DynamicAssembly, AssemblyStrategy, AssemblyQuality, TaskRequirement, AssemblyResult, AssemblyCache
from .self_regeneration import SelfRegeneration, RegenerationStatus, DamageLevel, RegenerationRecord
from .drive_system import DriveSystem, DriveType, get_drive_system
from .living_system import LivingSystem, SystemState, get_living_system, create_and_start

__all__ = [
    # 基础类型
    'Cell',
    'CellType',
    'CellState',

    # 细胞类型
    'ReasoningCell',
    'CausalReasoningCell',
    'SymbolicReasoningCell',
    'MemoryCell',
    'HippocampusCell',
    'NeocortexCell',
    'LearningCell',
    'EWCCell',
    'ProgressiveCell',
    'MetaLearningCell',
    'PerceptionCell',
    'MultimodalCell',
    'IntentCell',
    'ActionCell',
    'CodeCell',
    'ToolCell',
    'GenerationCell',
    'PredictionCell',
    'TimeSeriesPredictor',
    'ResourcePredictor',
    'HealthPredictor',

    # 预测相关类型
    'ScenarioType',
    'PredictionMethod',

    # 信号系统
    'Signal',
    'SignalType',
    'SignalPriority',

    # 组装流水线
    'ModelAssemblyLine',
    'CellRegistry',

    # 涌现引擎
    'EmergenceEngine',
    'SelfOrganization',

    # 进化引擎
    'EvolutionEngine',
    'CellDivision',
    'NaturalSelection',

    # 生命系统引擎
    'LifeEngine',
    'NeuralSymbolicIntegrator',
    'BayesianPosterior',
    'BeliefState',
    'InferenceMode',

    # 自我意识系统
    'SelfConsciousness',
    'SelfModel',
    'ConsciousnessLevel',
    'ReflectionMode',

    # 免疫系统
    'ImmuneSystem',
    'Threat',
    'Antibody',
    'ThreatLevel',
    'ThreatType',
    'DefenseStatus',

    # 代谢系统
    'MetabolicSystem',
    'ResourcePool',
    'EnergyLevel',
    'MetabolicState',
    'ResourceType',

    # 自主进化系统
    'AutonomousEvolution',
    'EvolutionPhase',
    'MutationType',
    'EvolutionRecord',
    'Mutation',

    # 动态组装系统
    'DynamicAssembly',
    'AssemblyStrategy',
    'AssemblyQuality',
    'TaskRequirement',
    'AssemblyResult',
    'AssemblyCache',

    # 自我再生系统
    'SelfRegeneration',
    'RegenerationStatus',
    'DamageLevel',
    'RegenerationRecord',

    # 内驱力系统
    'DriveSystem',
    'DriveType',
    'get_drive_system',

    # 生命系统
    'LivingSystem',
    'SystemState',
    'get_living_system',
    'create_and_start',

    # 能量监控
    'EnergyMonitor',
]


def create_cell(cell_type: str, **kwargs):
    """
    工厂函数：根据类型创建细胞

    Args:
        cell_type: 细胞类型名称
        **kwargs: 细胞初始化参数

    Returns:
        Cell实例
    """
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
        'prediction': PredictionCell,
        'timeseries': TimeSeriesPredictor,
        'resource': ResourcePredictor,
        'health': HealthPredictor,
    }

    cell_class = cell_map.get(cell_type.lower())
    if cell_class:
        return cell_class(**kwargs)
    raise ValueError(f"Unknown cell type: {cell_type}")


def assemble_model(task_description: str):
    """
    根据任务描述自动组装模型

    Args:
        task_description: 任务描述

    Returns:
        组装好的模型
    """
    assembler = ModelAssemblyLine()
    return assembler.assemble(task_description)
