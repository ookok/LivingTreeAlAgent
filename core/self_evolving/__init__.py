# -*- coding: utf-8 -*-
"""
自进化系统模块入口
==================

统一导出所有自进化相关组件：

核心系统：
- SelfEvolvingSystem: 统一自进化系统
- EvolutionMiddleware: Agent集成中间件

便捷函数：
- get_evolution_system(): 获取全局实例
- quick_evolve(): 快速执行任务
- wrap_agent_chat(): 包装AgentChat

使用示例：
```python
from core.self_evolving import (
    SelfEvolvingSystem,
    EvolutionMiddleware,
    get_evolution_system,
    quick_evolve,
)

# 方式1：使用全局系统
system = get_evolution_system()
result = await system.execute("帮我写一个排序算法")

# 方式2：包装AgentChat
middleware = wrap_agent_chat(agent_chat)
response = middleware.chat("你好")

# 方式3：快速执行
result = quick_evolve("解释量子计算")
```

Author: LivingTreeAI Team
Date: 2026-04-24
"""

# 核心系统
from .self_evolving_system import (
    SelfEvolvingSystem,
    EvolutionResult,
    ExecutionContext,
    ExecutionStage,
    QualityLevel,
    get_evolution_system,
    create_evolution_system,
    quick_evolve,
    evolve_sync,
)

# 集成中间件
from .agent_integration import (
    EvolutionMiddleware,
    EvolvedResponse,
    Intervention,
    InterventionType,
    wrap_agent_chat,
    AutoEvolutionMixIn,
)

# 模块信息
__version__ = "1.0.0"
__author__ = "LivingTreeAI Team"

__all__ = [
    # 核心系统
    "SelfEvolvingSystem",
    "EvolutionResult",
    "ExecutionContext",
    "ExecutionStage",
    "QualityLevel",
    "get_evolution_system",
    "create_evolution_system",
    "quick_evolve",
    "evolve_sync",
    
    # 集成中间件
    "EvolutionMiddleware",
    "EvolvedResponse",
    "Intervention",
    "InterventionType",
    "wrap_agent_chat",
    "AutoEvolutionMixIn",
]
