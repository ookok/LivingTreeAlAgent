# -*- coding: utf-8 -*-
"""
Intent Engine - 意图处理器核心引擎
====================================

将自然语言转换为结构化、可执行的意图描述。

核心功能：
1. 意图类型识别 - 判断用户想要什么（生成/修改/调试/分析...）
2. 目标提取 - 提取核心操作目标（登录接口、用户管理、缓存模块...）
3. 技术栈推断 - 推断使用的技术/框架（FastAPI/Django/Vue/React...）
4. 约束条件解析 - 提取约束（性能要求、安全要求、兼容性...）
5. 复合意图检测 - 检测复合任务并分解

输入示例：
    "帮我写一个用户登录接口，要用 FastAPI，返回 JWT token"

输出示例：
    Intent(
        type=IntentType.CODE_GENERATION,
        action="登录接口",
        target="用户认证",
        tech_stack=["FastAPI", "JWT"],
        constraints={"auth": "JWT", "response": "token"},
        confidence=0.92
    )

作者：LivingTreeAI Team
日期：2026-04-24
"""

from .intent_types import IntentType, Intent, IntentConstraint, TechStack
from .intent_parser import IntentParser
from .tech_stack_detector import TechStackDetector
from .constraint_extractor import ConstraintExtractor
from .composite_detector import CompositeDetector
from .intent_engine import IntentEngine

__all__ = [
    # 类型定义
    "IntentType",
    "Intent", 
    "IntentConstraint",
    "TechStack",
    # 解析器
    "IntentParser",
    "TechStackDetector",
    "ConstraintExtractor",
    "CompositeDetector",
    # 主引擎
    "IntentEngine",
]

__version__ = "1.0.0"
