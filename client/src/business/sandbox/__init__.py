"""
Sandbox Module - 沙箱验证模块

实现"探索未知"能力：
- 基于知识边界生成假设
- 在安全的模拟环境中快速试错
- 将假设验证结果反馈到记忆库

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from .sandbox_environment import (
    SandboxEnvironment,
    HypothesisGenerator,
    Hypothesis,
    HypothesisStatus,
    ExecutionResult,
    ExecutionStatus,
    SimulationResult,
    sandbox_environment,
    hypothesis_generator,
    get_sandbox_environment,
    get_hypothesis_generator
)

__all__ = [
    "SandboxEnvironment",
    "HypothesisGenerator",
    "Hypothesis",
    "HypothesisStatus",
    "ExecutionResult",
    "ExecutionStatus",
    "SimulationResult",
    "sandbox_environment",
    "hypothesis_generator",
    "get_sandbox_environment",
    "get_hypothesis_generator"
]