"""
Smart Help System - 智能求助系统

当AI无法满意回答用户问题时，自动将问题：
1. 脱敏处理（去除隐私信息）
2. 泛化描述（抽象为通用问题）
3. 选择合适平台（StackOverflow/知乎/GitHub等）
4. 生成规范提问
5. 发布并监控回复
6. 整合多源答案反馈给用户

核心理念：用户无需操心"去哪儿问"、"怎么问"，系统全代理。
"""

from .controller import SmartHelpController, HelpRequest, HelpStatus
from .question_sanitizer import QuestionSanitizer, SanitizedQuestion
from .platform_selector import PlatformSelector, Platform, QuestionType
from .question_generator import QuestionGenerator, GeneratedPost
from .answer_monitor import AnswerMonitor, MonitoredPost
from .answer_aggregator import AnswerAggregator, AggregatedAnswer

__all__ = [
    # 核心控制器
    "SmartHelpController",
    "HelpRequest",
    "HelpStatus",

    # 问题脱敏
    "QuestionSanitizer",
    "SanitizedQuestion",

    # 平台选择
    "PlatformSelector",
    "Platform",
    "QuestionType",

    # 提问生成
    "QuestionGenerator",
    "GeneratedPost",

    # 答案监控
    "AnswerMonitor",
    "MonitoredPost",

    # 答案整合
    "AnswerAggregator",
    "AggregatedAnswer",
]

# 全局单例
_controller_instance = None


def get_smart_help_controller() -> SmartHelpController:
    """获取智能求助控制器单例"""
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = SmartHelpController()
    return _controller_instance
