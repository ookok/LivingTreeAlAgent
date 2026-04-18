"""
通用文档模板引擎

从P2P知识库加载文档模板，支持多种文档类型的结构化定义。
以可行性研究报告为例展示默认模板结构。
"""

import json
import hashlib
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, AsyncGenerator
from enum import Enum


# ==================== 数据模型 ====================

class FieldType(Enum):
    """字段类型枚举"""
    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    ADDRESS = "address"
    DATE = "date"
    DATE_RANGE = "date_range"
    TABLE = "table"
    FILE = "file"
    RICH_TEXT = "rich_text"
    SIGNATURE = "signature"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    PHONE = "phone"
    EMAIL = "email"
    URL = "url"


class ValidationRule(Enum):
    """验证规则"""
    REQUIRED = "required"
    POSITIVE = "positive"
    PHONE = "phone"
    EMAIL = "email"
    URL = "url"
    CREDIT_CODE = "credit_code"
    ID_CARD = "id_card"
    MIN_VALUE = "min_value"
    MAX_VALUE = "max_value"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"
    PATTERN = "pattern"


class AICapability(Enum):
    """AI能力"""
    AUTO_COMPLETE = "auto_complete"
    DATA_VALIDATION = "data_validation"
    CROSS_REFERENCE = "cross_reference"
    SMART_RECOMMEND = "smart_recommend"
    CONSISTENCY_CHECK = "consistency_check"
    GRAMMAR_CHECK = "grammar_check"
    FORMAT_CONVERT = "format_convert"


@dataclass
class SectionField:
    """章节字段定义"""
    id: str
    label: str
    field_type: FieldType = FieldType.TEXT
    required: bool = False
    placeholder: str = ""
    help_text: str = ""
    default_value: Any = None
    options: List[Any] = field(default_factory=list)
    validation_rules: List[str] = field(default_factory=list)
    ai_enabled: bool = False
    cross_ref_enabled: bool = False
    unit: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: str = ""
    columns: List[Dict] = field(default_factory=list)
    visible_when: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentSection:
    """文档章节定义"""
    id: str
    title: str
    description: str = ""
    fields: List[SectionField] = field(default_factory=list)
    required: bool = True
    order: int = 0
    expandable: bool = False
    repeatable: bool = False
    ai_summary_enabled: bool = False
    conditions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TemplateCapability:
    """模板能力"""
    auto_complete: bool = True
    data_validation: bool = True
    cross_reference: bool = True
    smart_recommend: bool = True
    consistency_check: bool = True
    grammar_check: bool = True
    format_convert: bool = True
    export_formats: List[str] = field(default_factory=list)


@dataclass
class TemplateSchema:
    """文档模板结构"""
    name: str
    version: str = "1.0"
    description: str = ""
    category: str = "general"
    sections: List[DocumentSection] = field(default_factory=list)
    capabilities: TemplateCapability = field(default_factory=TemplateCapability)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ==================== 默认模板库 ====================

class DefaultTemplates:
    """默认模板库"""

    @classmethod
    def get_feasibility_report(cls) -> TemplateSchema:
        """可行性研究报告模板"""
        return TemplateSchema(
            name="可行性研究报告",
            version="1.0",
            description="建设项目可行性研究报告标准模板",
            category="business",
            sections=[
                DocumentSection(
                    id="overview",
                    title="一、项目概况",
                    description="项目基本信息",
                    order=1,
                    fields=[
                        SectionField(id="project_name", label="项目名称", field_type=FieldType.TEXT,
                                   required=True, placeholder="请输入项目全称"),
                        SectionField(id="project_type", label="项目类型", field_type=FieldType.SELECT,
                                   required=True, options=["新建", "改建", "扩建", "技术改造"]),
                        SectionField(id="location", label="建设地点", field_type=FieldType.ADDRESS,
                                   required=True, ai_enabled=True),
                        SectionField(id="total_investment", label="总投资（万元）", field_type=FieldType.NUMBER,
                                   required=True, min_value=0, unit="万元"),
                        SectionField(id="construction_period", label="建设周期", field_type=FieldType.TEXT,
                                   placeholder="如：2024.01-2025.12"),
                        SectionField(id="main_content", label="主要建设内容", field_type=FieldType.TEXTAREA,
                                   required=True, ai_enabled=True),
                    ]
                ),
                DocumentSection(
                    id="market_analysis",
                    title="二、市场分析",
                    description="项目市场前景分析",
                    order=2,
                    ai_summary_enabled=True,
                    fields=[
                        SectionField(id="market_size", label="市场规模", field_type=FieldType.TEXTAREA,
                                   ai_enabled=True),
                        SectionField(id="market_trend", label="市场趋势", field_type=FieldType.TEXTAREA,
                                   ai_enabled=True),
                        SectionField(id="competition_analysis", label="竞争分析", field_type=FieldType.TEXTAREA,
                                   ai_enabled=True),
                        SectionField(id="market_share", label="目标市场份额", field_type=FieldType.PERCENTAGE,
                                   min_value=0, max_value=100),
                    ]
                ),
                DocumentSection(
                    id="technical_scheme",
                    title="三、技术方案",
                    description="项目技术路线和方案",
                    order=3,
                    fields=[
                        SectionField(id="technology_source", label="技术来源", field_type=FieldType.SELECT,
                                   options=["自主研发", "引进技术", "合作开发", "其他"]),
                        SectionField(id="technical_route", label="技术路线", field_type=FieldType.TEXTAREA,
                                   required=True, ai_enabled=True),
                        SectionField(id="technical_specs", label="主要技术参数", field_type=FieldType.TABLE,
                                   columns=[
                                       {"id": "param_name", "label": "参数名称", "type": "text"},
                                       {"id": "unit", "label": "单位", "type": "text"},
                                       {"id": "value", "label": "数值", "type": "text"},
                                   ]),
                        SectionField(id="equipment_list", label="主要设备清单", field_type=FieldType.TEXTAREA,
                                   ai_enabled=True),
                    ]
                ),
                DocumentSection(
                    id="financial_analysis",
                    title="四、财务分析",
                    description="项目投资估算和经济效益分析",
                    order=4,
                    fields=[
                        SectionField(id="investment_breakdown", label="投资构成", field_type=FieldType.TABLE,
                                   columns=[
                                       {"id": "item", "label": "项目", "type": "text"},
                                       {"id": "amount", "label": "金额(万元)", "type": "number"},
                                       {"id": "ratio", "label": "占比(%)", "type": "percentage"},
                                   ]),
                        SectionField(id="fund_source", label="资金来源", field_type=FieldType.TEXTAREA,
                                   required=True),
                        SectionField(id="revenue_forecast", label="收入预测", field_type=FieldType.TEXTAREA,
                                   ai_enabled=True),
                        SectionField(id="cost_estimate", label="成本估算", field_type=FieldType.TEXTAREA,
                                   ai_enabled=True),
                        SectionField(id="payback_period", label="投资回收期(年)", field_type=FieldType.NUMBER,
                                   min_value=0, unit="年"),
                        SectionField(id="irr", label="内部收益率(%)", field_type=FieldType.PERCENTAGE,
                                   min_value=0, max_value=100),
                    ]
                ),
                DocumentSection(
                    id="risk_analysis",
                    title="五、风险分析",
                    description="项目风险评估和应对措施",
                    order=5,
                    fields=[
                        SectionField(id="risk_factors", label="风险因素", field_type=FieldType.TEXTAREA,
                                   ai_enabled=True),
                        SectionField(id="risk_level", label="风险等级", field_type=FieldType.SELECT,
                                   options=["低", "中等", "高", "极高"]),
                        SectionField(id="mitigation_measures", label="风险应对措施", field_type=FieldType.TEXTAREA,
                                   required=True, ai_enabled=True),
                    ]
                ),
                DocumentSection(
                    id="conclusion",
                    title="六、结论与建议",
                    description="项目综合评价和结论",
                    order=6,
                    ai_summary_enabled=True,
                    fields=[
                        SectionField(id="comprehensive_evaluation", label="综合评价", field_type=FieldType.TEXTAREA,
                                   required=True, ai_enabled=True),
                        SectionField(id="main_conclusion", label="主要结论", field_type=FieldType.TEXTAREA,
                                   required=True),
                        SectionField(id="suggestions", label="建议", field_type=FieldType.TEXTAREA,
                                   ai_enabled=True),
                    ]
                ),
            ],
            capabilities=TemplateCapability(
                auto_complete=True,
                data_validation=True,
                cross_reference=True,
                smart_recommend=True,
                consistency_check=True,
                export_formats=["word", "pdf", "html"]
            )
        )

    @classmethod
    def get_project_proposal(cls) -> TemplateSchema:
        """项目建议书模板"""
        return TemplateSchema(
            name="项目建议书",
            version="1.0",
            description="项目建议书标准模板",
            category="planning",
            sections=[
                DocumentSection(
                    id="background",
                    title="一、项目背景",
                    order=1,
                    fields=[
                        SectionField(id="project_name", label="项目名称", field_type=FieldType.TEXT,
                                   required=True),
                        SectionField(id="background", label="项目背景", field_type=FieldType.TEXTAREA,
                                   required=True, ai_enabled=True),
                        SectionField(id="necessity", label="项目必要性", field_type=FieldType.TEXTAREA,
                                   required=True, ai_enabled=True),
                    ]
                ),
                DocumentSection(
                    id="objectives",
                    title="二、项目目标",
                    order=2,
                    fields=[
                        SectionField(id="overall_goal", label="总体目标", field_type=FieldType.TEXTAREA,
                                   required=True),
                        SectionField(id="specific_goals", label="具体目标", field_type=FieldType.TEXTAREA,
                                   ai_enabled=True),
                    ]
                ),
                DocumentSection(
                    id="scope",
                    title="三、项目范围",
                    order=3,
                    fields=[
                        SectionField(id="main_content", label="主要内容", field_type=FieldType.TEXTAREA,
                                   required=True),
                        SectionField(id="deliverables", label="交付物", field_type=FieldType.TEXTAREA,
                                   ai_enabled=True),
                    ]
                ),
                DocumentSection(
                    id="budget",
                    title="四、投资估算",
                    order=4,
                    fields=[
                        SectionField(id="total_budget", label="总投资(万元)", field_type=FieldType.NUMBER,
                                   required=True, min_value=0, unit="万元"),
                    ]
                ),
            ],
            capabilities=TemplateCapability(
                auto_complete=True,
                data_validation=True,
                export_formats=["word", "pdf"]
            )
        )

    @classmethod
    def get_eia_report(cls) -> TemplateSchema:
        """环境影响评价报告模板"""
        return TemplateSchema(
            name="环境影响评价报告",
            version="1.0",
            description="环境影响评价报告标准模板",
            category="compliance",
            sections=[
                DocumentSection(
                    id="project_overview",
                    title="一、项目概况",
                    order=1,
                    fields=[
                        SectionField(id="project_name", label="项目名称", field_type=FieldType.TEXT,
                                   required=True),
                        SectionField(id="construction_unit", label="建设单位", field_type=FieldType.TEXT,
                                   required=True),
                        SectionField(id="location", label="建设地点", field_type=FieldType.ADDRESS,
                                   required=True),
                        SectionField(id="industry_type", label="行业类别", field_type=FieldType.SELECT,
                                   required=True, options=["化工", "电力", "钢铁", "建材", "轻工", "医药", "其他"]),
                        SectionField(id="construction_scale", label="建设规模", field_type=FieldType.TEXTAREA,
                                   required=True),
                    ]
                ),
                DocumentSection(
                    id="environment_baseline",
                    title="二、环境现状",
                    order=2,
                    ai_summary_enabled=True,
                    fields=[
                        SectionField(id="air_quality", label="环境空气质量", field_type=FieldType.TEXTAREA,
                                   ai_enabled=True),
                        SectionField(id="water_quality", label="地表水环境质量", field_type=FieldType.TEXTAREA,
                                   ai_enabled=True),
                    ]
                ),
                DocumentSection(
                    id="impact_prediction",
                    title="三、环境影响预测",
                    order=3,
                    fields=[
                        SectionField(id="pollution_sources", label="污染源分析", field_type=FieldType.TEXTAREA,
                                   required=True, ai_enabled=True),
                        SectionField(id="air_impact", label="大气环境影响", field_type=FieldType.TEXTAREA,
                                   ai_enabled=True),
                    ]
                ),
                DocumentSection(
                    id="mitigation_measures",
                    title="四、环境保护措施",
                    order=4,
                    fields=[
                        SectionField(id="air_mitigation", label="大气污染防治措施", field_type=FieldType.TEXTAREA,
                                   ai_enabled=True),
                        SectionField(id="water_mitigation", label="水污染防治措施", field_type=FieldType.TEXTAREA,
                                   ai_enabled=True),
                    ]
                ),
            ],
            capabilities=TemplateCapability(
                auto_complete=True,
                data_validation=True,
                cross_reference=True,
                smart_recommend=True,
                export_formats=["word", "pdf", "html"]
            )
        )

    @classmethod
    def get_implementation_plan(cls) -> TemplateSchema:
        """实施方案模板"""
        return TemplateSchema(
            name="实施方案",
            version="1.0",
            description="项目实施方案标准模板",
            category="planning",
            sections=[
                DocumentSection(
                    id="project_summary",
                    title="一、项目概述",
                    order=1,
                    fields=[
                        SectionField(id="project_name", label="项目名称", field_type=FieldType.TEXT, required=True),
                        SectionField(id="background", label="背景说明", field_type=FieldType.TEXTAREA, required=True),
                    ]
                ),
                DocumentSection(
                    id="implementation_content",
                    title="二、实施内容",
                    order=2,
                    fields=[
                        SectionField(id="main_tasks", label="主要任务", field_type=FieldType.TEXTAREA, required=True),
                        SectionField(id="work_breakdown", label="工作分解", field_type=FieldType.TABLE,
                                   columns=[
                                       {"id": "task", "label": "任务", "type": "text"},
                                       {"id": "responsibility", "label": "责任单位", "type": "text"},
                                       {"id": "timeline", "label": "时间安排", "type": "text"},
                                   ]),
                    ]
                ),
                DocumentSection(
                    id="timeline",
                    title="三、实施进度",
                    order=3,
                    fields=[
                        SectionField(id="phase_plan", label="分阶段计划", field_type=FieldType.TEXTAREA, ai_enabled=True),
                    ]
                ),
            ],
            capabilities=TemplateCapability(
                auto_complete=True,
                data_validation=True,
                export_formats=["word", "pdf"]
            )
        )

    @classmethod
    def get_all_templates(cls) -> Dict[str, TemplateSchema]:
        """获取所有默认模板"""
        return {
            "feasibility_report": cls.get_feasibility_report(),
            "project_proposal": cls.get_project_proposal(),
            "eia_report": cls.get_eia_report(),
            "implementation_plan": cls.get_implementation_plan(),
        }


# ==================== 模板引擎 ====================

class UniversalDocumentTemplate:
    """
    通用文档模板引擎

    从P2P知识库加载文档模板，支持多种文档类型的结构化定义。
    """

    def __init__(self, template_type: str, p2p_kb=None):
        self.template_type = template_type
        self.kb = p2p_kb
        self._use_mock = p2p_kb is None
        self._schema: Optional[TemplateSchema] = None

    async def load_template_schema(self) -> TemplateSchema:
        """从P2P知识库加载文档模板"""
        if not self._use_mock:
            template = await self.kb.get_template(self.template_type)
            if template:
                self._schema = self._parse_template(template)
                return self._schema

        self._schema = self._get_default_schema()
        return self._schema

    def _get_default_schema(self) -> TemplateSchema:
        """获取默认模板"""
        templates = DefaultTemplates.get_all_templates()
        return templates.get(self.template_type, templates["feasibility_report"])

    def _parse_template(self, template_data: Dict) -> TemplateSchema:
        """解析模板数据"""
        sections = []
        for sec_data in template_data.get("sections", []):
            fields = []
            for field_data in sec_data.get("fields", []):
                field = SectionField(
                    id=field_data["id"],
                    label=field_data.get("label", field_data["id"]),
                    field_type=FieldType(field_data.get("type", "text")),
                    required=field_data.get("required", False),
                    placeholder=field_data.get("placeholder", ""),
                    help_text=field_data.get("help_text", ""),
                    options=field_data.get("options", []),
                    validation_rules=field_data.get("validation_rules", []),
                    ai_enabled=field_data.get("ai_enabled", False),
                    unit=field_data.get("unit", ""),
                    min_value=field_data.get("min_value"),
                    max_value=field_data.get("max_value"),
                )
                fields.append(field)

            section = DocumentSection(
                id=sec_data["id"],
                title=sec_data.get("title", sec_data["id"]),
                description=sec_data.get("description", ""),
                fields=fields,
                required=sec_data.get("required", True),
                order=sec_data.get("order", 0),
                expandable=sec_data.get("expandable", False),
                repeatable=sec_data.get("repeatable", False),
            )
            sections.append(section)

        capabilities_data = template_data.get("capabilities", {})
        capabilities = TemplateCapability(
            auto_complete=capabilities_data.get("auto_complete", True),
            data_validation=capabilities_data.get("data_validation", True),
            cross_reference=capabilities_data.get("cross_reference", True),
            smart_recommend=capabilities_data.get("smart_recommend", True),
            consistency_check=capabilities_data.get("consistency_check", True),
            export_formats=capabilities_data.get("export_formats", ["word", "pdf"]),
        )

        return TemplateSchema(
            name=template_data.get("name", "未知模板"),
            version=template_data.get("version", "1.0"),
            description=template_data.get("description", ""),
            category=template_data.get("category", "general"),
            sections=sorted(sections, key=lambda s: s.order),
            capabilities=capabilities,
        )

    def get_schema(self) -> Optional[TemplateSchema]:
        """获取当前模板结构"""
        return self._schema

    def get_section(self, section_id: str) -> Optional[DocumentSection]:
        """获取指定章节"""
        if not self._schema:
            return None
        for section in self._schema.sections:
            if section.id == section_id:
                return section
        return None

    def to_dict(self) -> Dict:
        """转换为字典"""
        if not self._schema:
            return {}

        return {
            "name": self._schema.name,
            "version": self._schema.version,
            "description": self._schema.description,
            "category": self._schema.category,
            "sections": [
                {
                    "id": s.id,
                    "title": s.title,
                    "description": s.description,
                    "required": s.required,
                    "order": s.order,
                    "fields": [
                        {
                            "id": f.id,
                            "label": f.label,
                            "type": f.field_type.value,
                            "required": f.required,
                            "placeholder": f.placeholder,
                            "options": f.options,
                            "ai_enabled": f.ai_enabled,
                            "unit": f.unit,
                            "min_value": f.min_value,
                            "max_value": f.max_value,
                        }
                        for f in s.fields
                    ]
                }
                for s in self._schema.sections
            ],
            "capabilities": {
                "auto_complete": self._schema.capabilities.auto_complete,
                "data_validation": self._schema.capabilities.data_validation,
                "export_formats": self._schema.capabilities.export_formats,
            }
        }


# ==================== 导出函数 ====================

_template_engine_instance: Optional[UniversalDocumentTemplate] = None


def get_template_engine(template_type: str = "feasibility_report", p2p_kb=None) -> UniversalDocumentTemplate:
    """获取模板引擎实例"""
    return UniversalDocumentTemplate(template_type, p2p_kb)


async def load_template_async(template_type: str, p2p_kb=None) -> TemplateSchema:
    """异步加载模板"""
    engine = get_template_engine(template_type, p2p_kb)
    return await engine.load_template_schema()