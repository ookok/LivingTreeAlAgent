"""
Smart Fallback 智能降级链系统
============================

四级降级策略:
1. 本地模型处理 → 评估响应质量
2. 质量不满意 → 优化提示词重试
3. 仍不满意 → 返回优化提示词，建议使用外部AI
4. 用户选择 → GUI自动化调用豆包/元宝 或 复制提示词手动使用

架构:
    FallbackChainController (主控制器)
        ├── ResponseQualityEvaluator (质量评估)
        ├── EnhancedPromptOptimizer (提示词优化)
        ├── ExternalAIClient (外部AI调用)
        │   ├── DoubaoClient (豆包)
        │   ├── YuanbaoClient (元宝)
        │   └── GUIAutomator (GUI自动化)
        └── ClipboardManager (剪贴板管理)
"""

from .quality_evaluator import ResponseQualityEvaluator, QualityLevel, QualityScore
from .prompt_optimizer import EnhancedPromptOptimizer, OptimizationResult
from .external_ai_client import ExternalAIClient, ExternalAIResult
from .schedule_nlp import NLPScheduleParser, ParsedSchedule, CommandType, ScheduleType
from .schedule_command import ScheduleCommandExecutor, TaskInfo

__all__ = [
    # Quality
    "ResponseQualityEvaluator",
    "QualityLevel",
    "QualityScore",
    # Prompt
    "EnhancedPromptOptimizer",
    "OptimizationResult",
    # External AI
    "ExternalAIClient",
    "ExternalAIResult",
    # Schedule
    "NLPScheduleParser",
    "ParsedSchedule",
    "CommandType",
    "ScheduleType",
    "ScheduleCommandExecutor",
    "TaskInfo",
]