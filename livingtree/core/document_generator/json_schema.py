"""
JSON Schema 定义和验证

定义报告的结构化Schema，确保文档格式统一。
"""
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    logger.warning("jsonschema not installed, validation will be limited")


class ReportType(Enum):
    """报告类型"""
    FEASIBILITY_STUDY = "feasibility_study"
    EIA_REPORT = "eia_report"
    FINANCIAL_ANALYSIS = "financial_analysis"
    TECHNICAL_DESIGN = "technical_design"
    PROJECT_PROPOSAL = "project_proposal"
    CUSTOM = "custom"


class ContentType(Enum):
    """内容类型"""
    TEXT = "text"
    TABLE = "table"
    CHART = "chart"
    IMAGE = "image"
    CODE = "code"
    LIST = "list"
    SECTION = "section"


@dataclass
class ChartSpec:
    """图表规格"""
    type: str  # bar, line, pie, scatter
    title: str
    data_source: str
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TableSpec:
    """表格规格"""
    caption: Optional[str] = None
    headers: List[str] = field(default_factory=list)
    data_source: Optional[str] = None
    columns: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ReportSection:
    """报告章节"""
    id: str
    title: str
    level: int = 1
    content_type: ContentType = ContentType.TEXT
    content: Optional[str] = None
    table_spec: Optional[TableSpec] = None
    chart_spec: Optional[ChartSpec] = None
    code: Optional[str] = None
    code_language: str = "python"
    items: List[str] = field(default_factory=list)
    children: List['ReportSection'] = field(default_factory=list)
    required: bool = False
    reference: Optional[str] = None  # 引用法规/标准编号
    data_fields: List[str] = field(default_factory=list)  # 需要的数据字段


@dataclass
class ReportSchema:
    """报告Schema定义"""
    report_type: ReportType
    title: str
    version: str = "1.0.0"
    sections: List[ReportSection] = field(default_factory=list)
    required_sections: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    data_sources: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "report_type": self.report_type.value,
            "title": self.title,
            "version": self.version,
            "sections": [self._section_to_dict(s) for s in self.sections],
            "required_sections": self.required_sections,
            "metadata": self.metadata,
            "data_sources": self.data_sources,
        }
    
    def _section_to_dict(self, section: ReportSection) -> Dict[str, Any]:
        """递归转换章节"""
        result = {
            "id": section.id,
            "title": section.title,
            "level": section.level,
            "content_type": section.content_type.value,
            "required": section.required,
        }
        
        if section.content:
            result["content"] = section.content
        if section.table_spec:
            result["table_spec"] = {
                "caption": section.table_spec.caption,
                "headers": section.table_spec.headers,
                "data_source": section.table_spec.data_source,
                "columns": section.table_spec.columns,
            }
        if section.chart_spec:
            result["chart_spec"] = {
                "type": section.chart_spec.type,
                "title": section.chart_spec.title,
                "data_source": section.chart_spec.data_source,
                "x_label": section.chart_spec.x_label,
                "y_label": section.chart_spec.y_label,
                "options": section.chart_spec.options,
            }
        if section.code:
            result["code"] = section.code
            result["code_language"] = section.code_language
        if section.items:
            result["items"] = section.items
        if section.children:
            result["children"] = [self._section_to_dict(c) for c in section.children]
        if section.reference:
            result["reference"] = section.reference
        if section.data_fields:
            result["data_fields"] = section.data_fields
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReportSchema':
        """从字典创建"""
        sections = []
        for s_data in data.get("sections", []):
            sections.append(cls._section_from_dict(s_data))
        
        return cls(
            report_type=ReportType(data["report_type"]),
            title=data["title"],
            version=data.get("version", "1.0.0"),
            sections=sections,
            required_sections=data.get("required_sections", []),
            metadata=data.get("metadata", {}),
            data_sources=data.get("data_sources", []),
        )
    
    @classmethod
    def _section_from_dict(cls, data: Dict[str, Any]) -> ReportSection:
        """从字典创建章节"""
        children = []
        for c_data in data.get("children", []):
            children.append(cls._section_from_dict(c_data))
        
        table_spec = None
        if "table_spec" in data:
            table_spec = TableSpec(
                caption=data["table_spec"].get("caption"),
                headers=data["table_spec"].get("headers", []),
                data_source=data["table_spec"].get("data_source"),
                columns=data["table_spec"].get("columns", []),
            )
        
        chart_spec = None
        if "chart_spec" in data:
            chart_spec = ChartSpec(
                type=data["chart_spec"]["type"],
                title=data["chart_spec"]["title"],
                data_source=data["chart_spec"].get("data_source"),
                x_label=data["chart_spec"].get("x_label"),
                y_label=data["chart_spec"].get("y_label"),
                options=data["chart_spec"].get("options", {}),
            )
        
        return ReportSection(
            id=data["id"],
            title=data["title"],
            level=data.get("level", 1),
            content_type=ContentType(data.get("content_type", "text")),
            content=data.get("content"),
            table_spec=table_spec,
            chart_spec=chart_spec,
            code=data.get("code"),
            code_language=data.get("code_language", "python"),
            items=data.get("items", []),
            children=children,
            required=data.get("required", False),
            reference=data.get("reference"),
            data_fields=data.get("data_fields", []),
        )


class SchemaValidator:
    """Schema验证器"""
    
    @staticmethod
    def validate_schema(schema: ReportSchema) -> List[str]:
        """验证Schema的完整性"""
        errors = []
        
        # 检查必填字段
        if not schema.title:
            errors.append("报告标题不能为空")
        
        # 检查章节ID唯一性
        ids_seen = set()
        for section in schema.sections:
            errors.extend(SchemaValidator._validate_section(section, ids_seen))
        
        # 检查必填章节是否存在
        for req_id in schema.required_sections:
            if not SchemaValidator._section_exists(schema.sections, req_id):
                errors.append(f"必填章节 '{req_id}' 不存在")
        
        return errors
    
    @staticmethod
    def _validate_section(section: ReportSection, ids_seen: set) -> List[str]:
        """验证单个章节"""
        errors = []
        
        if not section.id:
            errors.append("章节ID不能为空")
        elif section.id in ids_seen:
            errors.append(f"章节ID重复: {section.id}")
        else:
            ids_seen.add(section.id)
        
        if not section.title:
            errors.append(f"章节 '{section.id}' 标题不能为空")
        
        # 递归检查子章节
        for child in section.children:
            errors.extend(SchemaValidator._validate_section(child, ids_seen))
        
        return errors
    
    @staticmethod
    def _section_exists(sections: List[ReportSection], section_id: str) -> bool:
        """检查章节是否存在"""
        for section in sections:
            if section.id == section_id:
                return True
            if SchemaValidator._section_exists(section.children, section_id):
                return True
        return False
    
    @staticmethod
    def validate_data(data: Dict[str, Any], schema: ReportSchema) -> List[str]:
        """验证数据是否符合Schema要求"""
        errors = []
        
        # 检查是否缺少必填数据字段
        required_fields = SchemaValidator._collect_required_fields(schema)
        
        for field in required_fields:
            if field not in data:
                errors.append(f"缺少必填数据字段: {field}")
        
        return errors
    
    @staticmethod
    def _collect_required_fields(schema: ReportSchema) -> List[str]:
        """收集所有需要的数据字段"""
        fields = set()
        
        def collect(sections):
            for section in sections:
                fields.update(section.data_fields)
                collect(section.children)
        
        collect(schema.sections)
        return list(fields)


# 预设报告模板
class ReportTemplates:
    """预设报告模板库"""
    
    @staticmethod
    def get_eia_report_schema() -> ReportSchema:
        """获取环评报告模板"""
        return ReportSchema(
            report_type=ReportType.EIA_REPORT,
            title="环境影响评价报告",
            version="1.0.0",
            required_sections=["project_overview", "pollutant_analysis", "impact_assessment"],
            data_sources=["project_data", "emission_data", "standards"],
            sections=[
                ReportSection(
                    id="project_overview",
                    title="一、项目概况",
                    level=1,
                    content_type=ContentType.SECTION,
                    required=True,
                    children=[
                        ReportSection(
                            id="project_basic_info",
                            title="1.1 项目基本信息",
                            level=2,
                            content_type=ContentType.TEXT,
                            data_fields=["project_name", "location", "scale", "construction_period"],
                        ),
                        ReportSection(
                            id="project_description",
                            title="1.2 项目内容描述",
                            level=2,
                            content_type=ContentType.TEXT,
                            data_fields=["project_description"],
                        ),
                    ],
                ),
                ReportSection(
                    id="pollutant_analysis",
                    title="二、污染源分析",
                    level=1,
                    content_type=ContentType.SECTION,
                    required=True,
                    children=[
                        ReportSection(
                            id="pollutant_identification",
                            title="2.1 污染源识别",
                            level=2,
                            content_type=ContentType.TEXT,
                            data_fields=["pollutants", "sources"],
                        ),
                        ReportSection(
                            id="emission_calculation",
                            title="2.2 排放量计算",
                            level=2,
                            content_type=ContentType.TABLE,
                            table_spec=TableSpec(
                                caption="污染物排放量计算表",
                                headers=["污染物名称", "产生量(t/a)", "处理效率(%)", "排放量(t/a)", "排放浓度(mg/m³)"],
                                data_source="emission_data",
                            ),
                            data_fields=["emission_table"],
                        ),
                    ],
                ),
                ReportSection(
                    id="impact_assessment",
                    title="三、环境影响预测与评价",
                    level=1,
                    content_type=ContentType.SECTION,
                    required=True,
                    children=[
                        ReportSection(
                            id="air_impact",
                            title="3.1 大气环境影响",
                            level=2,
                            content_type=ContentType.SECTION,
                            children=[
                                ReportSection(
                                    id="air_model",
                                    title="3.1.1 预测模型",
                                    level=3,
                                    content_type=ContentType.CODE,
                                    data_fields=["dispersion_model"],
                                ),
                                ReportSection(
                                    id="air_results",
                                    title="3.1.2 预测结果",
                                    level=3,
                                    content_type=ContentType.CHART,
                                    chart_spec=ChartSpec(
                                        type="line",
                                        title="污染物浓度分布图",
                                        data_source="air_quality_data",
                                        x_label="距离(m)",
                                        y_label="浓度(mg/m³)",
                                    ),
                                ),
                            ],
                        ),
                    ],
                ),
                ReportSection(
                    id="mitigation_measures",
                    title="四、污染防治措施",
                    level=1,
                    content_type=ContentType.SECTION,
                    children=[
                        ReportSection(
                            id="treatment_methods",
                            title="4.1 治理措施",
                            level=2,
                            content_type=ContentType.LIST,
                            data_fields=["mitigation_methods"],
                        ),
                    ],
                ),
            ],
        )
    
    @staticmethod
    def get_feasibility_study_schema() -> ReportSchema:
        """获取可行性研究报告模板"""
        return ReportSchema(
            report_type=ReportType.FEASIBILITY_STUDY,
            title="项目可行性研究报告",
            version="1.0.0",
            required_sections=["market_analysis", "financial_analysis"],
            data_sources=["market_data", "financial_data", "industry_data"],
            sections=[
                ReportSection(
                    id="executive_summary",
                    title="一、项目概述",
                    level=1,
                    content_type=ContentType.TEXT,
                    data_fields=["project_summary"],
                ),
                ReportSection(
                    id="market_analysis",
                    title="二、市场分析",
                    level=1,
                    content_type=ContentType.SECTION,
                    required=True,
                    children=[
                        ReportSection(
                            id="market_overview",
                            title="2.1 市场概况",
                            level=2,
                            content_type=ContentType.TEXT,
                        ),
                        ReportSection(
                            id="competitor_analysis",
                            title="2.2 竞争分析",
                            level=2,
                            content_type=ContentType.TABLE,
                            table_spec=TableSpec(
                                caption="竞争对手分析表",
                                headers=["竞争对手", "市场份额", "优势", "劣势"],
                                data_source="competitor_data",
                            ),
                        ),
                    ],
                ),
                ReportSection(
                    id="financial_analysis",
                    title="三、财务分析",
                    level=1,
                    content_type=ContentType.SECTION,
                    required=True,
                    children=[
                        ReportSection(
                            id="investment_estimate",
                            title="3.1 投资估算",
                            level=2,
                            content_type=ContentType.TABLE,
                            table_spec=TableSpec(
                                caption="投资估算表",
                                headers=["项目", "金额(万元)", "占比(%)"],
                                data_source="investment_data",
                            ),
                        ),
                        ReportSection(
                            id="npv_calculation",
                            title="3.2 净现值计算",
                            level=2,
                            content_type=ContentType.CODE,
                            code_language="python",
                            data_fields=["npv_parameters"],
                        ),
                        ReportSection(
                            id="sensitivity_analysis",
                            title="3.3 敏感性分析",
                            level=2,
                            content_type=ContentType.CHART,
                            chart_spec=ChartSpec(
                                type="bar",
                                title="敏感性分析结果",
                                data_source="sensitivity_data",
                                x_label="变量",
                                y_label="NPV变化(%)",
                            ),
                        ),
                    ],
                ),
            ],
        )