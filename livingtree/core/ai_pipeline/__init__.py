"""
AI 工作流引擎 (AI Workflow Engine)

核心 AI 流程调度引擎：
1. 任务分解 (Task Decomposition) - 将复杂任务拆解为子任务
2. 渐进式思考 (Progressive Thinking) - CoT 逐步推理
3. 知识管理 (Knowledge Management) - 知识库和上下文管理
4. 代码生成 (Code Generation Unit) - 模板和 AI 驱动的代码生成
"""

from .ai_workflow_engine import AIWorkflowEngine, WorkflowStage
from .progressive_thinking import ProgressiveThinker, ThinkingStep
from .knowledge_management import KnowledgeManager, KnowledgeItem
from .code_generation_unit import CodeGenerationUnit, CodeTemplate

__all__ = [
    "AIWorkflowEngine", "WorkflowStage",
    "ProgressiveThinker", "ThinkingStep",
    "KnowledgeManager", "KnowledgeItem",
    "CodeGenerationUnit", "CodeTemplate",
]
