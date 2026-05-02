"""
细胞AI框架 - 向后兼容层

⚠️ 已迁移至 livingtree.core.cells
本模块保留为兼容层，所有导入将自动重定向到新位置。
"""

from livingtree.core.cells import (
    Cell, CellType, CellState, EnergyMonitor,
    ReasoningCell, CausalReasoningCell, SymbolicReasoningCell,
    MemoryCell, HippocampusCell, NeocortexCell,
    LearningCell, EWCCell, ProgressiveCell, MetaLearningCell,
    PerceptionCell, MultimodalCell, IntentCell,
    ActionCell, CodeCell, ToolCell, GenerationCell,
    PredictionCell, TimeSeriesPredictor, ResourcePredictor, HealthPredictor,
    ScenarioType, PredictionMethod,
    Signal, SignalType, SignalPriority,
    ModelAssemblyLine, CellRegistry,
    EmergenceEngine, SelfOrganization,
    EvolutionEngine, CellDivision, NaturalSelection,
    LifeEngine, NeuralSymbolicIntegrator, BayesianPosterior, BeliefState, InferenceMode,
    SelfConsciousness, SelfModel, ConsciousnessLevel, ReflectionMode,
    ImmuneSystem, Threat, Antibody, ThreatLevel, ThreatType, DefenseStatus,
    MetabolicSystem, ResourcePool, EnergyLevel, MetabolicState, ResourceType,
    AutonomousEvolution, EvolutionPhase, MutationType, EvolutionRecord, Mutation,
    DynamicAssembly, AssemblyStrategy, AssemblyQuality, TaskRequirement, AssemblyResult, AssemblyCache,
    SelfRegeneration, RegenerationStatus, DamageLevel, RegenerationRecord,
    DriveSystem, DriveType, get_drive_system,
    LivingSystem, SystemState, get_living_system, create_and_start,
    create_cell, assemble_model,
)

__all__ = [
    'Cell', 'CellType', 'CellState',
    'ReasoningCell', 'CausalReasoningCell', 'SymbolicReasoningCell',
    'MemoryCell', 'HippocampusCell', 'NeocortexCell',
    'LearningCell', 'EWCCell', 'ProgressiveCell', 'MetaLearningCell',
    'PerceptionCell', 'MultimodalCell', 'IntentCell',
    'ActionCell', 'CodeCell', 'ToolCell', 'GenerationCell',
    'PredictionCell', 'TimeSeriesPredictor', 'ResourcePredictor', 'HealthPredictor',
    'ScenarioType', 'PredictionMethod',
    'Signal', 'SignalType', 'SignalPriority',
    'ModelAssemblyLine', 'CellRegistry',
    'EmergenceEngine', 'SelfOrganization',
    'EvolutionEngine', 'CellDivision', 'NaturalSelection',
    'LifeEngine', 'NeuralSymbolicIntegrator', 'BayesianPosterior', 'BeliefState', 'InferenceMode',
    'SelfConsciousness', 'SelfModel', 'ConsciousnessLevel', 'ReflectionMode',
    'ImmuneSystem', 'Threat', 'Antibody', 'ThreatLevel', 'ThreatType', 'DefenseStatus',
    'MetabolicSystem', 'ResourcePool', 'EnergyLevel', 'MetabolicState', 'ResourceType',
    'AutonomousEvolution', 'EvolutionPhase', 'MutationType', 'EvolutionRecord', 'Mutation',
    'DynamicAssembly', 'AssemblyStrategy', 'AssemblyQuality', 'TaskRequirement', 'AssemblyResult', 'AssemblyCache',
    'SelfRegeneration', 'RegenerationStatus', 'DamageLevel', 'RegenerationRecord',
    'DriveSystem', 'DriveType', 'get_drive_system',
    'LivingSystem', 'SystemState', 'get_living_system', 'create_and_start',
    'EnergyMonitor',
    'create_cell', 'assemble_model',
]
