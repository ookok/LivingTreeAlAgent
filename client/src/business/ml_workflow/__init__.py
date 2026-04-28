"""
ML 工作流模块

参考 ml-intern 的"ML 实习生"设计，实现自动化 ML 工作流。

核心功能：
1. ML 任务管理（训练/评估/部署）
2. 工作流编排
3. 自动化流程
4. 模型版本管理
5. 实验追踪

工作流流程：
1. 数据预处理 → 训练 → 评估 → 部署
2. 超参数调优 → 训练 → 评估 → 部署
"""

from .ml_workflow_manager import (
    MLWorkflowManager,
    MLTask,
    MLExperiment,
    ModelVersion,
    MLTaskType,
    TaskStatus
)

__all__ = [
    "MLWorkflowManager",
    "MLTask",
    "MLExperiment",
    "ModelVersion",
    "MLTaskType",
    "TaskStatus"
]