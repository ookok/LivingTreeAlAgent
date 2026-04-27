"""
强化学习模块 (Reinforcement Learning Module)
===========================================

为代码进化提供基于PPO算法的强化学习能力。

包含:
1. CodeEvolutionEnv - 代码进化环境
2. PolicyNetwork & ValueNetwork - 策略和价值网络
3. PPOAgent - PPO算法智能体
4. RLTrainer - 训练器
"""

from pathlib import Path

__all__ = [
    "CodeEvolutionEnv",
    "PolicyNetwork", 
    "ValueNetwork",
    "PPOAgent",
    "RLTrainer",
    "TrainingConfig",
]

MODULE_DIR = Path(__file__).parent

# 延迟导入
def __getattr__(name):
    """延迟导入，避免torch依赖问题"""
    if name == "CodeEvolutionEnv":
        from .rl_environment import CodeEvolutionEnv
        return CodeEvolutionEnv
    elif name in ("PolicyNetwork", "ValueNetwork"):
        from .rl_agent import PolicyNetwork, ValueNetwork
        return locals()[name]
    elif name == "PPOAgent":
        from .rl_agent import PPOAgent
        return PPOAgent
    elif name in ("RLTrainer", "TrainingConfig"):
        from .trainer import RLTrainer, TrainingConfig
        return locals()[name]
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
