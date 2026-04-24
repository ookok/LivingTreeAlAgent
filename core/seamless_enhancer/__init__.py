"""
SeamlessEnhancer Module
无缝自动增强层 - 集成渐进式学习和反思式学习

用户只需调用 chat()，内部自动完成：
1. 任务分析 + 增强决策
2. 反思循环 (失败时)
3. 多路径探索 (复杂任务)
4. 世界模型模拟 (高风险)
5. 渐进式学习 (成功后)
"""

from .trigger_decider import (
    TriggerDecider,
    EnhancementType,
    TaskAnalysis,
    create_decider
)

from .seamless_enhancer import (
    SeamlessEnhancer,
    EnhancementResult,
    EnhancementContext,
    ExecutionStatus,
    ProgressiveLoop
)

from .enhanced_integration import (
    EnhancedIntegration,
    LearnedSkill,
    FailureLesson,
    create_enhanced_agent,
    quick_chat
)


__all__ = [
    # 触发决策器
    "TriggerDecider",
    "EnhancementType",
    "TaskAnalysis",
    "create_decider",
    
    # 无缝增强器
    "SeamlessEnhancer",
    "EnhancementResult",
    "EnhancementContext",
    "ExecutionStatus",
    "ProgressiveLoop",
    
    # 集成层
    "EnhancedIntegration",
    "LearnedSkill",
    "FailureLesson",
    "create_enhanced_agent",
    "quick_chat"
]
