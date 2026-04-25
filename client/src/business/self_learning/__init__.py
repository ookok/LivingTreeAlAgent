"""
自我学习模块
包含强化学习、知识图谱、迁移学习等子模块
"""

from .reinforcement.rl_environment import CodeEvolutionEnv, CodeObservation, CodeAction
from .reinforcement.rl_agent import PPOAgent
from .reinforcement.rl_trainer import RLTrainer, TrainingConfig
from .knowledge_graph.kg_builder import KnowledgeGraphBuilder, KnowledgeGraph, Entity, Relation
from .knowledge_graph.kg_auto_builder import AutoKnowledgeGraphBuilder
from .transfer.domain_adapter import DomainAdapter, TransferLearningPipeline, SourceDomain, TargetDomain

__all__ = [
    # 强化学习
    'CodeEvolutionEnv',
    'CodeObservation',
    'CodeAction',
    'PPOAgent',
    'RLTrainer',
    'TrainingConfig',
    # 知识图谱
    'KnowledgeGraphBuilder',
    'KnowledgeGraph',
    'Entity',
    'Relation',
    'AutoKnowledgeGraphBuilder',
    # 迁移学习
    'DomainAdapter',
    'TransferLearningPipeline',
    'SourceDomain',
    'TargetDomain',
]
