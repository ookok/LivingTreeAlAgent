"""
对抗性评审系统
模拟最严格的评审专家，对报告进行压力测试
"""

from .adversarial_review_system import (
    # 枚举
    ReviewPerspective,
    QuestionType,
    QuestionStatus,
    # 数据模型
    ReviewQuestion,
    ReplyDraft,
    ReviewFocus,
    AdversarialReview,
    # 核心类
    QuestionGenerator,
    ReplyGenerator,
    FocusPredictor,
    AdversarialReviewEngine,
    # 工厂函数
    get_adversarial_engine,
    start_adversarial_review_async,
    generate_review_reply_async,
)

__all__ = [
    "ReviewPerspective",
    "QuestionType",
    "QuestionStatus",
    "ReviewQuestion",
    "ReplyDraft",
    "ReviewFocus",
    "AdversarialReview",
    "QuestionGenerator",
    "ReplyGenerator",
    "FocusPredictor",
    "AdversarialReviewEngine",
    "get_adversarial_engine",
    "start_adversarial_review_async",
    "generate_review_reply_async",
]
