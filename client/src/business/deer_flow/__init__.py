"""
DeerFlow 集成模块

参考 DeerFlow 架构设计，实现：
1. 中间件管道系统 - 标准化的 Middleware Pipeline
2. 子智能体执行系统 - SubAgentExecutor
"""

from .middleware_pipeline import (
    MiddlewareType,
    MiddlewareResult,
    BaseMiddleware,
    ThreadDataMiddleware,
    MemoryMiddleware,
    GuardrailMiddleware,
    ToolErrorHandlingMiddleware,
    SummarizationMiddleware,
    TodoListMiddleware,
    SubagentLimitMiddleware,
    ClarificationMiddleware,
    MiddlewarePipeline,
    PipelineBuilder,
)

from .subagent_system import (
    SubAgentType,
    SubAgentTask,
    SubAgentResult,
    BaseSubAgent,
    GeneralSubAgent,
    BashSubAgent,
    ResearchSubAgent,
    CodingSubAgent,
    AnalysisSubAgent,
    SubAgentRegistry,
    SubAgentExecutor,
    TaskTool,
)

__all__ = [
    # 中间件管道
    "MiddlewareType",
    "MiddlewareResult",
    "BaseMiddleware",
    "ThreadDataMiddleware",
    "MemoryMiddleware",
    "GuardrailMiddleware",
    "ToolErrorHandlingMiddleware",
    "SummarizationMiddleware",
    "TodoListMiddleware",
    "SubagentLimitMiddleware",
    "ClarificationMiddleware",
    "MiddlewarePipeline",
    "PipelineBuilder",
    # 子智能体系统
    "SubAgentType",
    "SubAgentTask",
    "SubAgentResult",
    "BaseSubAgent",
    "GeneralSubAgent",
    "BashSubAgent",
    "ResearchSubAgent",
    "CodingSubAgent",
    "AnalysisSubAgent",
    "SubAgentRegistry",
    "SubAgentExecutor",
    "TaskTool",
]
