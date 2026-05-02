"""
LivingTree SICA 自我改进代码生成引擎
====================================

Full migration from client/src/business/sica_engine/

核心功能：代码生成与优化、单元测试自动生成、自我反思与修复循环。
"""

from .sica_engine import SICACodeGenerator, CodeGenerationResult, TestResult
from .self_reflection import SelfReflectionEngine, ReflectionResult

__all__ = [
    "SICACodeGenerator",
    "CodeGenerationResult",
    "TestResult",
    "SelfReflectionEngine",
    "ReflectionResult",
]
