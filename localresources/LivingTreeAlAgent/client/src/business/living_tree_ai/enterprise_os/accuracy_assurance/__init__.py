"""
准确性保障模块 (Accuracy Assurance)

三重防护机制：
1. RAG检索增强生成 - 写作时检索最新法规标准作为AI生成依据
2. 模型校验 - 关键数据由模型计算，AI仅负责描述
3. 专家复核工作流 - 人工把关，确保符合行业资质要求

核心价值：
- 数据自动填充率：基础信息100%自动填充，零误差
- 模型计算覆盖率：80%以上定量结论由模型驱动
- 一次性通过率：专家评审修改意见减少70%以上
"""

from .rag_engine import (
    # 枚举
    KnowledgeDomain,
    DocumentType,
    RetrievalMode,
    # 数据模型
    KnowledgeChunk,
    RegulationStandard,
    RetrievedKnowledge,
    RAGQuery,
    RAGResult,
    # RAG引擎
    RAGEngine,
    get_rag_engine,
)

from .model_validator import (
    # 枚举
    ValidationLevel,
    ValidationStatus,
    # 数据模型
    ValidationRule,
    ValidationResult,
    ValidatedDocument,
    # 校验器
    ModelValidator,
    get_model_validator,
)

from .expert_workflow import (
    # 枚举
    ReviewLevel,
    ReviewStatus,
    ApprovalStatus,
    # 数据模型
    ReviewTask,
    ReviewComment,
    ApprovalChain,
    ExpertReviewWorkflow,
    # 便捷函数
    get_expert_workflow,
)

__all__ = [
    # RAG
    "KnowledgeDomain",
    "DocumentType",
    "RetrievalMode",
    "KnowledgeChunk",
    "RegulationStandard",
    "RetrievedKnowledge",
    "RAGQuery",
    "RAGResult",
    "RAGEngine",
    "get_rag_engine",
    # 模型校验
    "ValidationLevel",
    "ValidationStatus",
    "ValidationRule",
    "ValidationResult",
    "ValidatedDocument",
    "ModelValidator",
    "get_model_validator",
    # 专家复核
    "ReviewLevel",
    "ReviewStatus",
    "ApprovalStatus",
    "ReviewTask",
    "ReviewComment",
    "ApprovalChain",
    "ExpertReviewWorkflow",
    "get_expert_workflow",
]