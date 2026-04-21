"""
文档类型注册系统

注册和管理各种文档类型，支持动态添加新文档类型。
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum


# ==================== 数据模型 ====================

class DocumentCategory(Enum):
    """文档分类"""
    BUSINESS = "business"           # 商业文档
    PLANNING = "planning"           # 规划文档
    COMPLIANCE = "compliance"       # 合规文档
    TECHNICAL = "technical"         # 技术文档
    FINANCIAL = "financial"         # 财务文档
    LEGAL = "legal"               # 法律文档
    OTHER = "other"               # 其他


@dataclass
class DocumentTypeInfo:
    """文档类型信息"""
    type_id: str                   # 类型ID
    name: str                      # 显示名称
    description: str = ""          # 描述
    category: DocumentCategory = DocumentCategory.OTHER
    version: str = "1.0"
    icon: str = "📄"
    required_sections: List[str] = field(default_factory=list)
    ai_models: List[str] = field(default_factory=list)
    export_formats: List[str] = field(default_factory=lambda: ["word", "pdf"])
    metadata_schema: Dict[str, Any] = field(default_factory=dict)
    custom_fields: Dict[str, Any] = field(default_factory=dict)


# ==================== 文档类型注册表 ====================

class DocumentTypeRegistry:
    """
    文档类型注册表

    提供文档类型的注册、查询和管理功能。
    """

    # 内置文档类型
    BUILT_IN_TYPES: Dict[str, DocumentTypeInfo] = {
        "feasibility_report": DocumentTypeInfo(
            type_id="feasibility_report",
            name="可行性研究报告",
            description="建设项目可行性研究报告，用于项目投资决策",
            category=DocumentCategory.BUSINESS,
            icon="📊",
            required_sections=["overview", "market_analysis", "technical_scheme",
                             "financial_analysis", "risk_analysis", "conclusion"],
            ai_models=["market_analysis", "financial_forecast", "risk_assessment"],
            export_formats=["word", "pdf", "html"]
        ),
        "project_proposal": DocumentTypeInfo(
            type_id="project_proposal",
            name="项目建议书",
            description="项目建议书，用于项目立项申请",
            category=DocumentCategory.PLANNING,
            icon="📝",
            required_sections=["background", "objectives", "scope", "budget"],
            ai_models=["budget_estimation", "timeline_planning"],
            export_formats=["word", "pdf"]
        ),
        "eia_report": DocumentTypeInfo(
            type_id="eia_report",
            name="环境影响评价报告",
            description="环境影响评价报告，用于项目环境审批",
            category=DocumentCategory.COMPLIANCE,
            icon="🌿",
            required_sections=["project_overview", "environment_baseline",
                             "impact_prediction", "mitigation_measures"],
            ai_models=["source_strength_calculation", "dispersion_modeling",
                      "environmental_impact_assessment"],
            export_formats=["word", "pdf", "html"]
        ),
        "implementation_plan": DocumentTypeInfo(
            type_id="implementation_plan",
            name="实施方案",
            description="项目实施方案，用于项目执行指导",
            category=DocumentCategory.PLANNING,
            icon="⚙️",
            required_sections=["project_summary", "implementation_content",
                             "timeline", "resource_plan", "quality_assurance"],
            ai_models=["timeline_optimization", "resource_allocation"],
            export_formats=["word", "pdf"]
        ),
        "environmental_emergency": DocumentTypeInfo(
            type_id="environmental_emergency",
            name="环境应急预案",
            description="环境突发事件应急预案，用于环境安全管理",
            category=DocumentCategory.COMPLIANCE,
            icon="🚨",
            required_sections=["hazard_analysis", "emergency_organization",
                             "response_procedures", "resource保障"],
            ai_models=["risk_assessment", "emergency_scenario_generation"],
            export_formats=["word", "pdf"]
        ),
        "pollution_permit": DocumentTypeInfo(
            type_id="pollution_permit",
            name="排污许可证申请表",
            description="排污许可证申请表，用于排污许可申请",
            category=DocumentCategory.COMPLIANCE,
            icon="🏭",
            required_sections=["company_info", "pollution_sources",
                             "discharge_quality", "treatment_measures"],
            ai_models=["emission_calculation", "permit_quantity_forecast"],
            export_formats=["word", "pdf", "html"]
        ),
        "acceptance_monitoring": DocumentTypeInfo(
            type_id="acceptance_monitoring",
            name="竣工验收监测报告",
            description="项目竣工环境保护验收监测报告",
            category=DocumentCategory.COMPLIANCE,
            icon="✅",
            required_sections=["project_overview", "monitoring_plan",
                             "monitoring_results", "evaluation_conclusion"],
            ai_models=["monitoring_optimization", "data_validation"],
            export_formats=["word", "pdf"]
        ),
        "project_charter": DocumentTypeInfo(
            type_id="project_charter",
            name="项目章程",
            description="项目章程，定义项目基本信息和授权",
            category=DocumentCategory.BUSINESS,
            icon="📜",
            required_sections=["project概要", "objectives", "scope",
                             "budget", "stakeholders"],
            ai_models=["project_risk_initial"],
            export_formats=["word", "pdf"]
        ),
    }

    # 注册表
    _registry: Dict[str, DocumentTypeInfo] = {}

    # 自定义注册函数
    _custom_initializers: Dict[str, Callable] = {}

    @classmethod
    def register(cls, doc_type: DocumentTypeInfo):
        """
        注册文档类型

        Args:
            doc_type: 文档类型信息
        """
        cls._registry[doc_type.type_id] = doc_type

    @classmethod
    def register_custom(cls, type_id: str, initializer: Callable):
        """
        注册自定义文档类型初始化函数

        Args:
            type_id: 类型ID
            initializer: 初始化函数
        """
        cls._custom_initializers[type_id] = initializer

    @classmethod
    def get(cls, type_id: str) -> Optional[DocumentTypeInfo]:
        """
        获取文档类型

        Args:
            type_id: 类型ID

        Returns:
            Optional[DocumentTypeInfo]: 文档类型信息
        """
        # 先检查注册表
        if type_id in cls._registry:
            return cls._registry[type_id]

        # 再检查内置类型
        if type_id in cls.BUILT_IN_TYPES:
            return cls.BUILT_IN_TYPES[type_id]

        return None

    @classmethod
    def get_all(cls) -> Dict[str, DocumentTypeInfo]:
        """
        获取所有文档类型

        Returns:
            Dict[str, DocumentTypeInfo]: 所有文档类型
        """
        # 合并注册表和内置类型
        result = dict(cls.BUILT_IN_TYPES)
        result.update(cls._registry)
        return result

    @classmethod
    def get_by_category(cls, category: DocumentCategory) -> Dict[str, DocumentTypeInfo]:
        """
        按分类获取文档类型

        Args:
            category: 文档分类

        Returns:
            Dict[str, DocumentTypeInfo]: 该分类下的文档类型
        """
        all_types = cls.get_all()
        return {
            type_id: doc_type
            for type_id, doc_type in all_types.items()
            if doc_type.category == category
        }

    @classmethod
    def list_categories(cls) -> List[DocumentCategory]:
        """
        列出所有分类

        Returns:
            List[DocumentCategory]: 分类列表
        """
        return list(DocumentCategory)

    @classmethod
    def search(cls, keyword: str) -> Dict[str, DocumentTypeInfo]:
        """
        搜索文档类型

        Args:
            keyword: 关键词

        Returns:
            Dict[str, DocumentTypeInfo]: 匹配的文档类型
        """
        all_types = cls.get_all()
        keyword_lower = keyword.lower()

        result = {}
        for type_id, doc_type in all_types.items():
            if (keyword_lower in doc_type.name.lower() or
                keyword_lower in doc_type.description.lower() or
                keyword_lower in type_id.lower()):
                result[type_id] = doc_type

        return result

    @classmethod
    def is_registered(cls, type_id: str) -> bool:
        """
        检查类型是否已注册

        Args:
            type_id: 类型ID

        Returns:
            bool: 是否已注册
        """
        return type_id in cls._registry or type_id in cls.BUILT_IN_TYPES


# ==================== 注册函数 ====================

def register_document_type(doc_type: DocumentTypeInfo):
    """注册文档类型的便捷函数"""
    DocumentTypeRegistry.register(doc_type)


def get_document_types() -> Dict[str, DocumentTypeInfo]:
    """获取所有文档类型"""
    return DocumentTypeRegistry.get_all()


def get_document_type(type_id: str) -> Optional[DocumentTypeInfo]:
    """获取指定文档类型"""
    return DocumentTypeRegistry.get(type_id)
