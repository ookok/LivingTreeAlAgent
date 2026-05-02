"""
SICA (Self-Improving Coding Agent) 自我改进代码生成引擎

核心功能：
1. 代码生成与优化
2. 单元测试自动生成
3. 自我反思与修复循环
4. 代码质量评估
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