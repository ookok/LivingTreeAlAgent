"""
自主学习系统 - 向后兼容层

⚠️ 已迁移至 livingtree.core.self_learning
本模块保留为兼容层，所有导入将自动重定向到新位置。
"""

from livingtree.core.self_learning.knowledge_graph import kg_builder, kg_auto_builder
from livingtree.core.self_learning.reinforcement import rl_agent, rl_environment, rl_trainer, trainer
from livingtree.core.self_learning.transfer import domain_adapter, pretrained_model, transfer_trainer

__all__ = []
