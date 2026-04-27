"""
自我学习模块 (Self-Learning Module)
======================================

为 EvolutionEngine 提供强化学习、知识图谱和迁移学习能力。

包含:
1. reinforcement/ - 强化学习模块 (PPO算法)
2. knowledge_graph/ - 代码知识图谱 (内存版本)
3. transfer/ - 迁移学习模块 (领域适配)
"""

from pathlib import Path

# 版本信息
__version__ = "1.0.0"
__author__ = "LivingTreeAI Team"

# 模块根目录
MODULE_ROOT = Path(__file__).parent

# 导入主要接口类
__all__ = [
    # 强化学习
    "CodeEvolutionEnv",
    "PPOAgent", 
    "RLTrainer",
    "TrainingConfig",
    
    # 知识图谱
    "CodeKnowledgeGraph",
    "ASTParser",
    "ImpactAnalyzer",
    
    # 迁移学习
    "DomainAdapter",
    "TransferTrainer",
    "CodeBERTAdapter",
]

# 延迟导入，避免启动时的依赖问题
def __getattr__(name):
    """延迟导入模块"""
    if name in ("CodeEvolutionEnv", "PPOAgent", "RLTrainer", "TrainingConfig"):
        from .reinforcement import CodeEvolutionEnv, PPOAgent, RLTrainer, TrainingConfig
        return locals()[name]
    
    elif name in ("CodeKnowledgeGraph", "ASTParser", "ImpactAnalyzer"):
        from .knowledge_graph import CodeKnowledgeGraph, ASTParser, ImpactAnalyzer
        return locals()[name]
        
    elif name in ("DomainAdapter", "TransferTrainer", "CodeBERTAdapter"):
        from .transfer import DomainAdapter, TransferTrainer, CodeBERTAdapter
        return locals()[name]
        
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
