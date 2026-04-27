# -*- coding: utf-8 -*-
"""
Error Memory System - 智能错误修复记忆系统
==========================================

提供错误模式学习 + 修复方案模板 + 智能匹配功能。

核心组件：
1. ErrorPattern - 错误模式数据模型
2. ErrorPatternMatcher - 错误模式匹配器
3. ErrorKnowledgeBase - 错误知识库
4. ErrorLearningSystem - 错误学习系统

使用示例：
```python
from client.src.business.error_memory import (
    ErrorLearningSystem,
    ErrorKnowledgeBase,
    quick_learn,
    quick_fix_from_message,
)

# 方式1：完整系统
els = ErrorLearningSystem()
result = els.learn_and_fix(
    error=UnicodeDecodeError(...),
    context={"operation": "file_read"}
)
print(f"匹配模式: {result['matched_pattern']['pattern_name']}")

# 方式2：快速学习
solution = quick_learn(exception, {"operation": "json_parse"})

# 方式3：从消息快速修复
solution = quick_fix_from_message(
    "UnicodeDecodeError: 'utf-8' codec can't decode",
    {"operation": "file_read"}
)
```

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

from __future__ import annotations

# 版本信息
__version__ = "1.0.0"
__author__ = "LivingTreeAI Agent"

# ═══════════════════════════════════════════════════════════════════════════════
# 导出主要组件
# ═══════════════════════════════════════════════════════════════════════════════

# 错误模型
try:
    from .error_models import (
        ErrorSurfaceFeatures,
        ErrorPattern,
        FixTemplate,
        FixStep,
        ErrorRecord,
        ErrorCategory,
        ErrorSeverity,
        FixStatus,
        FixConfidence,
        PatternMatchResult,
        PRESET_PATTERNS,
        PRESET_TEMPLATES,
    )
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from error_models import (
            ErrorSurfaceFeatures,
            ErrorPattern,
            FixTemplate,
            FixStep,
            ErrorRecord,
            ErrorCategory,
            ErrorSeverity,
            FixStatus,
            FixConfidence,
            PatternMatchResult,
            PRESET_PATTERNS,
            PRESET_TEMPLATES,
        )
    except ImportError:
        raise

# 模式匹配器
try:
    from .pattern_matcher import (
        ErrorPatternMatcher,
        MatcherConfig,
        FeatureExtractor,
        SimilarityCalculator,
        get_matcher,
    )
except ImportError:
    try:
        from pattern_matcher import (
            ErrorPatternMatcher,
            MatcherConfig,
            FeatureExtractor,
            SimilarityCalculator,
            get_matcher,
        )
    except ImportError:
        pass

# 知识库
try:
    from .error_knowledge_base import (
        ErrorKnowledgeBase,
        KnowledgeBaseConfig,
        get_knowledge_base,
    )
except ImportError:
    try:
        from error_knowledge_base import (
            ErrorKnowledgeBase,
            KnowledgeBaseConfig,
            get_knowledge_base,
        )
    except ImportError:
        pass

# 学习系统
try:
    from .error_learning_system import (
        ErrorLearningSystem,
        ErrorLearningContext,
        ErrorWithSolution,
        get_error_system,
        quick_learn,
        quick_fix_from_message,
        quick_fix_from_exception,
    )
except ImportError:
    try:
        from error_learning_system import (
            ErrorLearningSystem,
            ErrorLearningContext,
            ErrorWithSolution,
            get_error_system,
            quick_learn,
            quick_fix_from_message,
            quick_fix_from_exception,
        )
    except ImportError:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# 模块元数据
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # 版本
    "__version__",
    "__author__",
    
    # 错误模型
    "ErrorSurfaceFeatures",
    "ErrorPattern",
    "FixTemplate",
    "FixStep",
    "ErrorRecord",
    "ErrorCategory",
    "ErrorSeverity",
    "FixStatus",
    "FixConfidence",
    "PatternMatchResult",
    "PRESET_PATTERNS",
    "PRESET_TEMPLATES",
    
    # 模式匹配器
    "ErrorPatternMatcher",
    "MatcherConfig",
    "FeatureExtractor",
    "SimilarityCalculator",
    "get_matcher",
    
    # 知识库
    "ErrorKnowledgeBase",
    "KnowledgeBaseConfig",
    "get_knowledge_base",
    
    # 学习系统
    "ErrorLearningSystem",
    "ErrorLearningContext",
    "ErrorWithSolution",
    "get_error_system",
    "quick_learn",
    "quick_fix_from_message",
    "quick_fix_from_exception",
]
