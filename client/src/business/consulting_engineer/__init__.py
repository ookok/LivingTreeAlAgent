"""
数字咨询工程师 - 主控制器

整合所有模块，提供统一的咨询文档生成能力。

核心功能：
1. 解析环评/可研文档
2. 生成配套Python代码
3. 生成结构化报告
4. 验证数据准确性
"""
from .consulting_engineer import ConsultingEngineer, ProjectContext, TaskResult

__all__ = [
    "ConsultingEngineer",
    "ProjectContext",
    "TaskResult",
]