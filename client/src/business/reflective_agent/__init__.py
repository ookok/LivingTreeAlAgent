"""
反思式Agent模块 (Reflective Agent)

核心能力：执行-反思-改进的迭代循环

模块结构：
- ReflectiveAgentLoop: 核心反思执行循环
- ReflectionEngine: 深度反思引擎
- ImprovementGenerator: 改进策略生成器
- ErrorHandlerRegistry: 错误处理注册表
- ExecutionResult: 执行结果数据模型
- ExecutionPlan: 执行计划数据模型

使用示例：
```python
from client.src.business.reflective_agent import ReflectiveAgentLoop, create_reflective_loop

# 创建反思循环
loop = ReflectiveAgentLoop()

# 注册执行器
async def search_handler(step):
    return await search(step.params["query"])

loop.register_executor("search", search_handler)

# 执行任务
result = await loop.execute_with_reflection("搜索最新的AI技术")
print(result.final_result)
```
"""

# 核心组件
from .reflective_loop import (
    ReflectiveAgentLoop,
    ReflectiveLoopConfig,
    create_reflective_loop
)

# 反思引擎
from .reflection_engine import (
    ReflectionEngine,
    ReflectionResult
)

# 改进生成器
from .improvement_generator import (
    ImprovementGenerator,
    ImprovementPlan,
    Improvement
)

# 错误处理
from .error_handlers import (
    ErrorHandlerRegistry,
    BaseErrorHandler,
    SyntaxErrorHandler,
    LogicErrorHandler,
    ResourceErrorHandler,
    TimeoutErrorHandler,
    KnowledgeGapHandler,
    APIErrorHandler,
    ModelErrorHandler,
    GenericErrorHandler
)

# 数据模型
from .execution_result import (
    ExecutionResult,
    ExecutionStep,
    ExecutionError,
    ExecutionMetrics,
    ExecutionStatus,
    ErrorCategory,
    ErrorSeverity
)

from .execution_plan import (
    ExecutionPlan,
    PlanStep,
    PlanType,
    StepPriority
)

# 版本信息
__version__ = "1.0.0"
__author__ = "LivingTreeAI"

# 公开API
__all__ = [
    # 核心
    "ReflectiveAgentLoop",
    "ReflectiveLoopConfig",
    "create_reflective_loop",

    # 反思
    "ReflectionEngine",
    "ReflectionResult",

    # 改进
    "ImprovementGenerator",
    "ImprovementPlan",
    "Improvement",

    # 错误处理
    "ErrorHandlerRegistry",
    "BaseErrorHandler",

    # 数据模型
    "ExecutionResult",
    "ExecutionStep",
    "ExecutionError",
    "ExecutionMetrics",
    "ExecutionPlan",
    "PlanStep",

    # 枚举
    "ExecutionStatus",
    "ErrorCategory",
    "ErrorSeverity",
    "PlanType",
    "StepPriority",
]
