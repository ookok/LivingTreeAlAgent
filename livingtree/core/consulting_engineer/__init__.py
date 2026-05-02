"""
LivingTree 数字咨询工程师
========================

Full migration from client/src/business/consulting_engineer/

整合文档解析、代码生成、文档生成、形式化验证，提供端到端咨询文档自动化。
"""

from .consulting_engineer import (
    ConsultingEngineer,
    ProjectContext,
    ProjectType,
    TaskType,
    TaskResult,
    get_consulting_engineer,
    create_eia_project,
    create_feasibility_project,
    process_eia_document,
)

__all__ = [
    "ConsultingEngineer",
    "ProjectContext",
    "ProjectType",
    "TaskType",
    "TaskResult",
    "get_consulting_engineer",
    "create_eia_project",
    "create_feasibility_project",
    "process_eia_document",
]
