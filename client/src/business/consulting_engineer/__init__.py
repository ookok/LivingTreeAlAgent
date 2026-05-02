"""
Full migration complete. → livingtree.core.consulting_engineer

核心功能：解析环评/可研文档、生成配套代码、生成结构化报告、验证数据准确性
"""
from .consulting_engineer import ConsultingEngineer, ProjectContext, TaskResult

__all__ = [
    "ConsultingEngineer",
    "ProjectContext",
    "TaskResult",
]