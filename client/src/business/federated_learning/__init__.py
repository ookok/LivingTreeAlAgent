"""
联邦学习模块

工作流程：
1. 本地训练（每个智能体在本地训练模型）
2. 上传模型参数（不上传原始数据）
3. 聚合模型参数（中继服务器聚合所有智能体的参数）
4. 分发全局模型（所有智能体下载并更新模型）

保护隐私的同时提升整体模型性能
"""

from .federated_learning_manager import (
    FederatedLearningManager,
    ModelParameters
)

__all__ = [
    "FederatedLearningManager",
    "ModelParameters"
]