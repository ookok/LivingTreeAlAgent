# -*- coding: utf-8 -*-
"""
场地污染源调查与环境评估报告生成器
Pollution Source Investigation & Environmental Assessment Report Generator
======================================================================

功能：
- 场地污染源调查数据建模
- 环境评估报告结构定义
- 多格式报告生成 (DOCX/PDF/HTML/Markdown)
- 报告模板管理

Author: Hermes Desktop Team
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# 报告格式枚举
# =============================================================================

class AssessmentReportFormat(Enum):
    """评估报告格式"""
    DOCX = "docx"
    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"


class PollutionLevel(Enum):
    """污染等级"""
    CLEAN = "clean"           # 未污染
    LIGHT = "light"           # 轻度污染
    MODERATE = "moderate"     # 中度污染
    SEVERE = "severe"         # 重度污染
    UNKNOWN = "unknown"


class MediaType(Enum):
    """环境介质类型"""
    AIR = "air"              # 大气
    SURFACE_WATER = "surface_water"   # 地表水
    GROUNDWATER = "groundwater"       # 地下水
    SOIL = "soil"            # 土壤
    SEDIMENT = "sediment"     # 沉积物
    NOISE = "noise"          # 噪声


# =============================================================================
# 数据模型 - 污染源信息
# =============================================================================

@dataclass
class PollutionSource:
    """污染源信息"""
    source_id: str                           # 污染源编号
    source_name: str                          # 污染源名称
    source_type: str                          # 污染源类型（工业/农业/生活/交通等）
    location: str                            # 位置描述
    coordinates: Optional[Tuple[float, float]] = None  # 经纬度
    contaminants: List[str] = field(default_factory=list)  # 污染物类型
    emission_mode: str = ""                  # 排放方式
    emission_point: str = ""                  # 排放口位置
    design_capacity: str = ""                 # 设计能力
    actual_capacity: str = ""                 # 实际产能
    operation_status: str = "在产"            # 生产状态（在产/停产/关闭）
    shutdown_date: Optional[str] = None       # 停产/关闭日期
    historical_activities: List[str] = field(default_factory=list)  # 历史活动
    risk_level: str = "中"                   # 风险等级（高/中/低）
    remarks: str = ""                         # 备注


@dataclass
class SamplingPoint:
    """采样点信息"""
    point_id: str                            # 采样点编号
    point_name: str                          # 采样点名称
    location: str                            # 位置描述
    coordinates: Optional[Tuple[float, float]] = None
    media_type: MediaType                    # 介质类型
    sampling_date: str                        # 采样日期
    depth: str = ""                          # 采样深度（土壤/地下水）
    depth_unit: str = "m"                    # 深度单位
    samples: List['Sample'] = field(default_factory=list)  # 样品列表


@dataclass
class Sample:
    """样品检测结果"""
    sample_id: str                           # 样品编号
    sample_name: str                          # 样品名称
    parameter: str                           # 检测参数
    unit: str                                # 单位
    value: float                             # 检测值
    detection_limit: float = 0.0             # 检测检出限
    standard_value: float = 0.0              # 标准限值
    exceedance_ratio: float = 0.0            # 超标倍数
    is_exceeded: bool = False                # 是否超标
    detection_method: str = ""               # 检测方法
    remarks: str = ""


@dataclass
class PollutionAssessment:
    """污染评估结果"""
    media_type: MediaType                    # 评估介质
    assessment_area: str = ""                # 评估范围
    assessment_area_unit: str = "m²"         # 评估面积单位
    pollution_level: PollutionLevel = PollutionLevel.UNKNOWN  # 污染等级
    total_contaminants: List[str] = field(default_factory=list)  # 检出污染物
    main_contaminants: List[str] = field(default_factory=list)  # 主要污染物
    exceedance_parameters: List[str] = field(default_factory=list)  # 超标参数
    max_exceedance_ratio: float = 0.0        # 最大超标倍数
    affected_area: str = ""                   # 影响范围
    assessment_conclusion: str = ""           # 评估结论


# =============================================================================
# 数据模型 - 环境质量现状
# =============================================================================

@dataclass
class EnvironmentalQuality:
    """环境质量现状数据"""
    media_type: MediaType                    # 介质类型
    monitoring_date: str                      # 监测日期
    monitoring_locations: int = 0            # 监测点位数量
    samples_count: int = 0                    # 样品数量
    parameters: List[str] = field(default_factory=list)  # 监测参数
    standard_type: str = ""                  # 执行标准
    standard_values: Dict[str, float] = field(default_factory=dict)  # 标准限值
    monitoring_results: List[Dict] = field(default_factory=list)  # 监测结果
    quality_level: str = ""                   # 质量等级/达标情况
    remarks: str = ""


@dataclass
class AirQuality(EnvironmentalQuality):
    """大气环境质量"""
    def __init__(self):
        super().__init__(media_type=MediaType.AIR)
        self.ambient_air_standard = ""       # 环境空气质量标准
        self.emission_standard = ""          # 排放标准


@dataclass
class WaterQuality(EnvironmentalQuality):
    """水环境质量"""
    def __init__(self, media_type: MediaType = MediaType.SURFACE_WATER):
        super().__init__(media_type=media_type)
        self.surface_water_standard = ""     # 地表水环境质量标准
        self.groundwater_standard = ""        # 地下水质量标准


@dataclass
class SoilQuality(EnvironmentalQuality):
    """土壤环境质量"""
    def __init__(self):
        super().__init__(media_type=MediaType.SOIL)
        self.soil_environment_standard = ""  # 土壤环境质量标准
        self.soil_background_value = ""      # 土壤背景值


@dataclass
class NoiseQuality(EnvironmentalQuality):
    """声环境质量"""
    def __init__(self):
        super().__init__(media_type=MediaType.NOISE)
        self.environmental_noise_standard = ""  # 环境噪声标准


# =============================================================================
# 数据模型 - 报告章节
# =============================================================================

@dataclass
class ReportChapter:
    """报告章节"""
    chapter_number: str                       # 章节编号 (如 "1", "2.1", "3.1.2")
    title: str                                # 章节标题
    content: str = ""                         # 正文内容 (Markdown格式)
    sections: List['ReportChapter'] = field(default_factory=list)  # 子章节
    tables: List[Dict] = field(default_factory=list)  # 表格数据
    figures: List[Dict] = field(default_factory=list)  # 图表引用
    attachments: List[str] = field(default_factory=list)  # 附件列表
    metadata: Dict = field(default_factory=dict)  # 附加信息


@dataclass
class ReportCover:
    """报告封面信息"""
    report_title: str                         # 报告标题
    report_subtitle: str = ""                 # 报告副标题
    project_name: str = ""                    # 项目名称
    project_address: str = ""                  # 项目地址
    report_number: str = ""                    # 报告编号
    entrust_unit: str = ""                    # 委托单位
    entrust_unit_address: str = ""            # 委托单位地址
    entrust_unit_contact: str = ""             # 联系人/电话
    assessment_unit: str = ""                 # 评估单位
    assessment_unit_license: str = ""          # 评估资质证书号
    legal_representative: str = ""             # 法人代表
    assessment_person: str = ""                # 项目负责人
    report_author: str = ""                    # 报告编制人
    approval_date: str = ""                   # 批准日期
    version: str = "V1.0"                     # 报告版本


# =============================================================================
# 数据模型 - 项目信息
# =============================================================================

@dataclass
class ProjectInfo:
    """项目基本信息"""
    project_name: str                         # 项目名称
    project_type: str = ""                    # 项目类别
    project_address: str = ""                # 项目地址
    construction_scale: str = ""              # 建设规模
    total_investment: str = ""               # 总投资
    capital_source: str = ""                  # 资金来源
    construction_period: str = ""            # 建设周期
    operation_period: str = ""               # 运营期
    contact_person: str = ""                  # 联系人
    contact_phone: str = ""                   # 联系电话
    latitude: Optional[float] = None         # 纬度
    longitude: Optional[float] = None         # 经度
    area: str = ""                            # 占地面积 (m²)
    building_area: str = ""                   # 建筑面积 (m²)
    historical_use: List[str] = field(default_factory=list)  # 历史用途


@dataclass
class AssessmentScope:
    """评估范围"""
    assessment_area: str = ""                 # 评估范围描述
    assessment_area_unit: str = "m²"         # 评估面积单位
    horizontal_extent: str = ""              # 水平范围
    vertical_extent: str = ""                # 垂直范围（深度）
    assessment_duration: str = ""            # 评估时段


# =============================================================================
# 数据模型 - 完整报告数据
# =============================================================================

@dataclass
class PollutionAssessmentReportData:
    """场地污染源调查与环境评估报告完整数据"""
    # 基本信息
    report_id: str                            # 报告ID
    report_cover: ReportCover                 # 封面信息
    project_info: ProjectInfo                 # 项目信息
    assessment_scope: AssessmentScope         # 评估范围

    # 污染源调查
    pollution_sources: List[PollutionSource] = field(default_factory=list)  # 污染源清单
    sampling_points: List[SamplingPoint] = field(default_factory=list)  # 采样点
    pollution_assessments: List[PollutionAssessment] = field(default_factory=list)  # 污染评估

    # 环境质量现状
    air_quality: Optional[AirQuality] = None
    surface_water_quality: Optional[WaterQuality] = None
    groundwater_quality: Optional[WaterQuality] = None
    soil_quality: Optional[SoilQuality] = None
    noise_quality: Optional[NoiseQuality] = None

    # 报告章节
    chapters: List[ReportChapter] = field(default_factory=list)  # 自定义章节

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    assessment_team: List[str] = field(default_factory=list)  # 评估人员
    reference_standards: List[str] = field(default_factory=list)  # 引用标准
    remarks: str = ""


# =============================================================================
# 报告生成器
# =============================================================================

class PollutionAssessmentReportGenerator:
    """
    场地污染源调查与环境评估报告生成器

    用法:
        generator = PollutionAssessmentReportGenerator()

        # 创建报告数据
        report_data = generator.create_report_data(
            project_name="XX场地污染源调查",
            ...
        )

        # 生成报告
        report_path = generator.generate(
            data=report_data,
            format=AssessmentReportFormat.DOCX,
            output_dir="./reports"
        )
    """

    def __init__(self, template_dir: str = None):
        self.template_dir = template_dir or self._get_default_template_dir()
        self._templates: Dict[str, Dict] = {}
        self._load_default_templates()

    def _get_default_template_dir(self) -> str:
        """获取默认模板目录"""
        base_dir = Path(__file__).parent
        return str(base_dir / "templates" / "pollution_assessment")

    def _load_default_templates(self) -> None:
        """加载默认模板"""
        self._templates["standard"] = {
            "name": "标准模板",
            "description": "适用于一般场地污染源调查与环境评估",
            "chapters": [
                {"id": "cover", "number": "0", "title": "封面", "level": 0},
                {"id": "toc", "number": "0", "title": "目录", "level": 0},
                {"id": "declaration", "number": "0", "title": "报告说明", "level": 1},
                {"id": "overview", "number": "1", "title": "1 项目概述", "level": 1},
                {"id": "scope", "number": "1.1", "title": "1.1 调查范围与目标", "level": 2},
                {"id": "method", "number": "1.2", "title": "1.2 调查方法与依据", "level": 2},
                {"id": "history", "number": "1.3", "title": "1.3 场地历史沿革", "level": 2},
                {"id": "pollution_sources", "number": "2", "title": "2 污染源调查", "level": 1},
                {"id": "source_inventory", "number": "2.1", "title": "2.1 污染源清单", "level": 2},
                {"id": "source_analysis", "number": "2.2", "title": "2.2 污染源分析", "level": 2},
                {"id": "sampling", "number": "3", "title": "3 采样与检测", "level": 1},
                {"id": "sampling_plan", "number": "3.1", "title": "3.1 采样方案", "level": 2},
                {"id": "sampling_results", "number": "3.2", "title": "3.2 检测结果", "level": 2},
                {"id": "assessment", "number": "4", "title": "4 污染评估", "level": 1},
                {"id": "soil_assessment", "number": "4.1", "title": "4.1 土壤污染评估", "level": 2},
                {"id": "water_assessment", "number": "4.2", "title": "4.2 地下水污染评估", "level": 2},
                {"id": "env_quality", "number": "5", "title": "5 环境质量现状", "level": 1},
                {"id": "air_env", "number": "5.1", "title": "5.1 大气环境", "level": 2},
                {"id": "water_env", "number": "5.2", "title": "5.2 水环境", "level": 2},
                {"id": "soil_env", "number": "5.3", "title": "5.3 土壤环境", "level": 2},
                {"id": "noise_env", "number": "5.4", "title": "5.4 声环境", "level": 2},
                {"id": "impact_analysis", "number": "6", "title": "6 环境影响分析", "level": 1},
                {"id": "construction_impact", "number": "6.1", "title": "6.1 施工期影响", "level": 2},
                {"id": "operation_impact", "number": "6.2", "title": "6.2 运营期影响", "level": 2},
                {"id": "mitigation", "number": "7", "title": "7 环境保护措施", "level": 1},
                {"id": "conclusion", "number": "8", "title": "8 结论与建议", "level": 1},
                {"id": "attachments", "number": "9", "title": "9 附件", "level": 1},
            ]
        }

    def create_report_data(
        self,
        project_name: str,
        report_title: str = None,
        entrust_unit: str = "",
        assessment_unit: str = "",
        **kwargs
    ) -> PollutionAssessmentReportData:
        """
        创建报告数据对象

        Args:
            project_name: 项目名称
            report_title: 报告标题
            entrust_unit: 委托单位
            assessment_unit: 评估单位
            **kwargs: 其他参数

        Returns:
            PollutionAssessmentReportData: 报告数据对象
        """
        report_id = f"PAR_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 创建封面信息
        cover = ReportCover(
            report_title=report_title or f"{project_name}场地污染源调查与环境评估报告",
            project_name=project_name,
            entrust_unit=entrust_unit,
            assessment_unit=assessment_unit,
            entrust_unit_contact=kwargs.get("entrust_contact", ""),
            assessment_unit_license=kwargs.get("assessment_license", ""),
            assessment_person=kwargs.get("assessment_person", ""),
            report_author=kwargs.get("report_author", ""),
            approval_date=datetime.now().strftime("%Y-%m-%d"),
        )

        # 创建项目信息
        project_info = ProjectInfo(
            project_name=project_name,
            project_type=kwargs.get("project_type", ""),
            project_address=kwargs.get("project_address", ""),
            construction_scale=kwargs.get("construction_scale", ""),
            total_investment=kwargs.get("total_investment", ""),
            area=kwargs.get("area", ""),
            historical_use=kwargs.get("historical_use", []),
        )

        # 创建评估范围
        assessment_scope = AssessmentScope(
            assessment_area=kwargs.get("assessment_area", ""),
            horizontal_extent=kwargs.get("horizontal_extent", ""),
            vertical_extent=kwargs.get("vertical_extent", ""),
        )

        return PollutionAssessmentReportData(
            report_id=report_id,
            report_cover=cover,
            project_info=project_info,
            assessment_scope=assessment_scope,
            pollution_sources=kwargs.get("pollution_sources", []),
            sampling_points=kwargs.get("sampling_points", []),
            pollution_assessments=kwargs.get("pollution_assessments", []),
            air_quality=kwargs.get("air_quality"),
            surface_water_quality=kwargs.get("surface_water_quality"),
            groundwater_quality=kwargs.get("groundwater_quality"),
            soil_quality=kwargs.get("soil_quality"),
            noise_quality=kwargs.get("noise_quality"),
            assessment_team=kwargs.get("assessment_team", []),
            reference_standards=kwargs.get("reference_standards", []),
        )

    def add_pollution_source(
        self,
        data: PollutionAssessmentReportData,
        source_name: str,
        source_type: str,
        location: str,
        **kwargs
    ) -> PollutionSource:
        """添加污染源"""
        source = PollutionSource(
            source_id=f"PS{len(data.pollution_sources) + 1:03d}",
            source_name=source_name,
            source_type=source_type,
            location=location,
            coordinates=kwargs.get("coordinates"),
            contaminants=kwargs.get("contaminants", []),
            emission_mode=kwargs.get("emission_mode", ""),
            operation_status=kwargs.get("operation_status", "在产"),
            risk_level=kwargs.get("risk_level", "中"),
            remarks=kwargs.get("remarks", ""),
        )
        data.pollution_sources.append(source)
        return source

    def add_sampling_point(
        self,
        data: PollutionAssessmentReportData,
        point_name: str,
        location: str,
        media_type: MediaType,
        sampling_date: str,
        **kwargs
    ) -> SamplingPoint:
        """添加采样点"""
        point = SamplingPoint(
            point_id=f"SP{len(data.sampling_points) + 1:03d}",
            point_name=point_name,
            location=location,
            coordinates=kwargs.get("coordinates"),
            media_type=media_type,
            sampling_date=sampling_date,
            depth=kwargs.get("depth", ""),
        )
        data.sampling_points.append(point)
        return point

    def add_sample(
        self,
        sampling_point: SamplingPoint,
        sample_name: str,
        parameter: str,
        value: float,
        unit: str,
        standard_value: float,
        **kwargs
    ) -> Sample:
        """添加样品检测结果"""
        exceedance_ratio = 0.0
        is_exceeded = False
        if standard_value > 0:
            exceedance_ratio = (value - standard_value) / standard_value
            is_exceeded = value > standard_value

        sample = Sample(
            sample_id=f"S{len(sampling_point.samples) + 1:03d}",
            sample_name=sample_name,
            parameter=parameter,
            unit=unit,
            value=value,
            detection_limit=kwargs.get("detection_limit", 0.0),
            standard_value=standard_value,
            exceedance_ratio=exceedance_ratio,
            is_exceeded=is_exceeded,
            detection_method=kwargs.get("detection_method", ""),
            remarks=kwargs.get("remarks", ""),
        )
        sampling_point.samples.append(sample)
        return sample

    def add_pollution_assessment(
        self,
        data: PollutionAssessmentReportData,
        media_type: MediaType,
        assessment_conclusion: str,
        **kwargs
    ) -> PollutionAssessment:
        """添加污染评估结果"""
        assessment = PollutionAssessment(
            media_type=media_type,
            assessment_area=kwargs.get("assessment_area", ""),
            pollution_level=kwargs.get("pollution_level", PollutionLevel.UNKNOWN),
            total_contaminants=kwargs.get("total_contaminants", []),
            main_contaminants=kwargs.get("main_contaminants", []),
            exceedance_parameters=kwargs.get("exceedance_parameters", []),
            max_exceedance_ratio=kwargs.get("max_exceedance_ratio", 0.0),
            assessment_conclusion=assessment_conclusion,
        )
        data.pollution_assessments.append(assessment)
        return assessment

    def generate(
        self,
        data: PollutionAssessmentReportData,
        format: AssessmentReportFormat = AssessmentReportFormat.DOCX,
        output_dir: str = None,
        template: str = "standard",
        **kwargs
    ) -> str:
        """
        生成报告

        Args:
            data: 报告数据
            format: 输出格式
            output_dir: 输出目录
            template: 模板名称
            **kwargs: 其他参数

        Returns:
            str: 生成的报告文件路径
        """
        output_dir = output_dir or self._get_default_output_dir()
        os.makedirs(output_dir, exist_ok=True)

        filename = f"{data.report_cover.project_name}_{data.report_id}.{format.value}"
        output_path = os.path.join(output_dir, filename)

        if format == AssessmentReportFormat.DOCX:
            return self._generate_docx(data, output_path, template, **kwargs)
        elif format == AssessmentReportFormat.HTML:
            return self._generate_html(data, output_path, template, **kwargs)
        elif format == AssessmentReportFormat.MARKDOWN:
            return self._generate_markdown(data, output_path, template, **kwargs)
        elif format == AssessmentReportFormat.PDF:
            return self._generate_pdf(data, output_path, template, **kwargs)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _get_default_output_dir(self) -> str:
        """获取默认输出目录"""
        base_dir = Path.home() / ".hermes-desktop" / "reports" / "pollution_assessment"
        base_dir.mkdir(parents=True, exist_ok=True)
        return str(base_dir)

    def _generate_docx(
        self,
        data: PollutionAssessmentReportData,
        output_path: str,
        template: str,
        **kwargs
    ) -> str:
        """生成DOCX格式报告"""
        try:
            from client.src.business.md_to_doc.docx_generator import DOCXGenerator
            from client.src.business.md_to_doc.models import DocumentNode, DocumentElement, ElementType

            # 生成Markdown内容
            md_content = self._generate_markdown_content(data, template)

            # 转换为DOCX
            generator = DOCXGenerator()
            doc_node = generator.generate_from_markdown(md_content)
            docx_bytes = generator.generate(doc_node)

            with open(output_path, 'wb') as f:
                f.write(docx_bytes)

            logger.info(f"Generated DOCX report: {output_path}")
            return output_path

        except ImportError as e:
            logger.warning(f"DOCX generator not available: {e}, falling back to HTML")
            html_path = output_path.replace('.docx', '.html')
            self._generate_html(data, html_path, template)
            return html_path

    def _generate_html(
        self,
        data: PollutionAssessmentReportData,
        output_path: str,
        template: str,
        **kwargs
    ) -> str:
        """生成HTML格式报告"""
        html_content = self._render_html_template(data, template)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"Generated HTML report: {output_path}")
        return output_path

    def _generate_markdown(
        self,
        data: PollutionAssessmentReportData,
        output_path: str,
        template: str,
        **kwargs
    ) -> str:
        """生成Markdown格式报告"""
        md_content = self._generate_markdown_content(data, template)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        logger.info(f"Generated Markdown report: {output_path}")
        return output_path

    def _generate_pdf(
        self,
        data: PollutionAssessmentReportData,
        output_path: str,
        template: str,
        **kwargs
    ) -> str:
        """生成PDF格式报告（通过HTML中转）"""
        html_path = output_path.replace('.pdf', '.html')
        self._generate_html(data, html_path, template)
        # PDF生成需要额外的转换工具，这里返回HTML路径
        logger.warning(f"PDF generation not fully implemented, generated HTML: {html_path}")
        return html_path

    def _generate_markdown_content(
        self,
        data: PollutionAssessmentReportData,
        template: str
    ) -> str:
        """生成Markdown报告内容"""
        lines = []
        cover = data.report_cover
        project = data.project_info

        # ==================== 封面 ====================
        lines.append("# " + cover.report_title)
        lines.append("")
        if cover.report_subtitle:
            lines.append("## " + cover.report_subtitle)
            lines.append("")
        lines.append("")
        lines.append(f"**报告编号**: {cover.report_number or '_____________'}")
        lines.append(f"**项目名称**: {project.project_name}")
        lines.append(f"**委托单位**: {cover.entrust_unit}")
        lines.append(f"**评估单位**: {cover.assessment_unit}")
        lines.append(f"**批准日期**: {cover.approval_date}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ==================== 目录 ====================
        lines.append("# 目录")
        lines.append("")
        lines.append("> 本报告目录")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ==================== 项目概述 ====================
        lines.append("# 1 项目概述")
        lines.append("")
        lines.append(f"## 1.1 项目基本情况")
        lines.append("")
        lines.append(f"**项目名称**: {project.project_name}")
        lines.append(f"**项目地址**: {project.project_address}")
        lines.append(f"**项目类别**: {project.project_type}")
        lines.append(f"**建设规模**: {project.construction_scale}")
        lines.append(f"**占地面积**: {project.area}")
        lines.append(f"**总投资**: {project.total_investment}")
        lines.append(f"**建设周期**: {project.construction_period}")
        lines.append("")

        if project.historical_use:
            lines.append(f"## 1.2 场地历史沿革")
            lines.append("")
            for i, use in enumerate(project.historical_use, 1):
                lines.append(f"{i}. {use}")
            lines.append("")

        # ==================== 污染源调查 ====================
        lines.append("# 2 污染源调查")
        lines.append("")

        if data.pollution_sources:
            lines.append(f"## 2.1 污染源清单")
            lines.append("")
            lines.append("| 序号 | 污染源名称 | 类型 | 位置 | 状态 | 风险等级 |")
            lines.append("|------|-----------|------|------|------|--------|")
            for i, src in enumerate(data.pollution_sources, 1):
                lines.append(f"| {i} | {src.source_name} | {src.source_type} | {src.location} | {src.operation_status} | {src.risk_level} |")
            lines.append("")

            lines.append(f"## 2.2 污染源详细信息")
            lines.append("")
            for src in data.pollution_sources:
                lines.append(f"### {src.source_id} {src.source_name}")
                lines.append("")
                lines.append(f"- **类型**: {src.source_type}")
                lines.append(f"- **位置**: {src.location}")
                lines.append(f"- **状态**: {src.operation_status}")
                lines.append(f"- **风险等级**: {src.risk_level}")
                if src.contaminants:
                    lines.append(f"- **主要污染物**: {', '.join(src.contaminants)}")
                if src.emission_mode:
                    lines.append(f"- **排放方式**: {src.emission_mode}")
                lines.append("")

        # ==================== 采样与检测 ====================
        lines.append("# 3 采样与检测")
        lines.append("")

        if data.sampling_points:
            lines.append(f"## 3.1 采样点布设")
            lines.append("")
            lines.append("| 采样点编号 | 名称 | 位置 | 介质 | 采样日期 |")
            lines.append("|-----------|------|------|------|----------|")
            for pt in data.sampling_points:
                lines.append(f"| {pt.point_id} | {pt.point_name} | {pt.location} | {pt.media_type.value} | {pt.sampling_date} |")
            lines.append("")

            lines.append(f"## 3.2 检测结果")
            lines.append("")

            for pt in data.sampling_points:
                lines.append(f"### {pt.point_id} {pt.point_name}")
                lines.append("")
                if pt.samples:
                    lines.append("| 样品编号 | 参数 | 检测值 | 单位 | 标准值 | 超标倍数 | 是否超标 |")
                    lines.append("|---------|------|--------|------|--------|---------|--------|")
                    for sample in pt.samples:
                        exceed = "是" if sample.is_exceeded else "否"
                        exceed_ratio = f"{sample.exceedance_ratio:.2f}" if sample.exceedance_ratio > 0 else "-"
                        lines.append(f"| {sample.sample_id} | {sample.parameter} | {sample.value} | {sample.unit} | {sample.standard_value} | {exceed_ratio} | {exceed} |")
                    lines.append("")
                else:
                    lines.append("*暂无检测数据*")
                    lines.append("")

        # ==================== 污染评估 ====================
        lines.append("# 4 污染评估")
        lines.append("")

        if data.pollution_assessments:
            for assessment in data.pollution_assessments:
                level_display = {
                    PollutionLevel.CLEAN: "未污染",
                    PollutionLevel.LIGHT: "轻度污染",
                    PollutionLevel.MODERATE: "中度污染",
                    PollutionLevel.SEVERE: "重度污染",
                    PollutionLevel.UNKNOWN: "未知"
                }.get(assessment.pollution_level, "未知")

                lines.append(f"## 4.{data.pollution_assessments.index(assessment)+1} {assessment.media_type.value}污染评估")
                lines.append("")
                lines.append(f"- **评估范围**: {assessment.assessment_area}")
                lines.append(f"- **污染等级**: {level_display}")
                if assessment.main_contaminants:
                    lines.append(f"- **主要污染物**: {', '.join(assessment.main_contaminants)}")
                if assessment.exceedance_parameters:
                    lines.append(f"- **超标参数**: {', '.join(assessment.exceedance_parameters)}")
                if assessment.max_exceedance_ratio > 0:
                    lines.append(f"- **最大超标倍数**: {assessment.max_exceedance_ratio:.2f}")
                lines.append(f"- **评估结论**: {assessment.assessment_conclusion}")
                lines.append("")

        # ==================== 环境质量现状 ====================
        lines.append("# 5 环境质量现状")
        lines.append("")

        def render_env_quality(title: str, eq: EnvironmentalQuality):
            lines.append(f"## {title}")
            lines.append("")
            if eq:
                lines.append(f"- **监测日期**: {eq.monitoring_date}")
                lines.append(f"- **监测点位**: {eq.monitoring_locations}个")
                lines.append(f"- **监测参数**: {', '.join(eq.parameters) if eq.parameters else '-'}")
                lines.append(f"- **执行标准**: {eq.standard_type}")
                lines.append(f"- **质量等级/达标情况**: {eq.quality_level or '-'}")
                if eq.remarks:
                    lines.append(f"- **备注**: {eq.remarks}")
            else:
                lines.append("*暂无数据*")
            lines.append("")

        if data.air_quality:
            render_env_quality("5.1 大气环境质量", data.air_quality)
        if data.surface_water_quality:
            render_env_quality("5.2 地表水环境质量", data.surface_water_quality)
        if data.groundwater_quality:
            render_env_quality("5.3 地下水环境质量", data.groundwater_quality)
        if data.soil_quality:
            render_env_quality("5.4 土壤环境质量", data.soil_quality)
        if data.noise_quality:
            render_env_quality("5.5 声环境质量", data.noise_quality)

        # ==================== 结论与建议 ====================
        lines.append("# 6 结论与建议")
        lines.append("")

        lines.append("## 6.1 主要结论")
        lines.append("")
        lines.append("根据现场调查、采样检测和综合分析，本次场地污染源调查与环境评估的主要结论如下：")
        lines.append("")
        lines.append("1. 场地现状：...")
        lines.append("2. 污染状况：...")
        lines.append("3. 环境质量：...")
        lines.append("")

        lines.append("## 6.2 建议")
        lines.append("")
        lines.append("1. 针对检出污染物，建议采取以下修复措施：...")
        lines.append("2. 后续监测建议：...")
        lines.append("3. 开发建设建议：...")
        lines.append("")

        # ==================== 附件 ====================
        lines.append("# 附件")
        lines.append("")
        lines.append("1. 现场照片")
        lines.append("2. 检测报告副本")
        lines.append("3. 实验室资质证书")
        lines.append("4. 采样原始记录")
        lines.append("")

        return "\n".join(lines)

    def _render_html_template(
        self,
        data: PollutionAssessmentReportData,
        template: str
    ) -> str:
        """渲染HTML模板"""
        cover = data.report_cover
        project = data.project_info

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{cover.report_title}</title>
    <style>
        body {{ font-family: "Microsoft YaHei", "SimHei", Arial, sans-serif; margin: 40px; line-height: 1.8; color: #333; }}
        h1 {{ color: #1a5f7a; border-bottom: 3px solid #1a5f7a; padding-bottom: 10px; }}
        h2 {{ color: #2e86ab; border-bottom: 1px solid #2e86ab; padding-bottom: 5px; margin-top: 30px; }}
        h3 {{ color: #548b91; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background-color: #1a5f7a; color: white; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .cover {{ text-align: center; margin: 60px 0; }}
        .cover h1 {{ font-size: 28px; margin-bottom: 20px; }}
        .cover p {{ margin: 8px 0; }}
        .toc {{ background: #f5f5f5; padding: 20px; margin: 20px 0; }}
        .exceeded {{ color: #d32f2f; font-weight: bold; }}
        .footer {{ margin-top: 60px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="cover">
        <h1>{cover.report_title}</h1>
        <p><strong>报告编号</strong>: {cover.report_number or '_____________'}</p>
        <p><strong>项目名称</strong>: {project.project_name}</p>
        <p><strong>委托单位</strong>: {cover.entrust_unit}</p>
        <p><strong>评估单位</strong>: {cover.assessment_unit}</p>
        <p><strong>批准日期</strong>: {cover.approval_date}</p>
    </div>

    <div class="toc">
        <h2>目录</h2>
        <ol>
            <li>项目概述</li>
            <li>污染源调查</li>
            <li>采样与检测</li>
            <li>污染评估</li>
            <li>环境质量现状</li>
            <li>结论与建议</li>
            <li>附件</li>
        </ol>
    </div>

    <h1>1 项目概述</h1>
    <h2>1.1 项目基本情况</h2>
    <table>
        <tr><th>项目名称</th><td>{project.project_name}</td></tr>
        <tr><th>项目地址</th><td>{project.project_address}</td></tr>
        <tr><th>项目类别</th><td>{project.project_type}</td></tr>
        <tr><th>建设规模</th><td>{project.construction_scale}</td></tr>
        <tr><th>占地面积</th><td>{project.area}</td></tr>
        <tr><th>总投资</th><td>{project.total_investment}</td></tr>
    </table>

    <h1>2 污染源调查</h1>
    <h2>2.1 污染源清单</h2>
    <table>
        <tr><th>序号</th><th>名称</th><th>类型</th><th>位置</th><th>状态</th><th>风险等级</th></tr>
"""

        for i, src in enumerate(data.pollution_sources, 1):
            html += f"""        <tr>
            <td>{i}</td>
            <td>{src.source_name}</td>
            <td>{src.source_type}</td>
            <td>{src.location}</td>
            <td>{src.operation_status}</td>
            <td>{src.risk_level}</td>
        </tr>
"""

        html += """    </table>

    <h1>3 采样与检测</h1>
    <h2>3.1 采样点布设</h2>
    <table>
        <tr><th>编号</th><th>名称</th><th>位置</th><th>介质</th><th>采样日期</th></tr>
"""

        for pt in data.sampling_points:
            html += f"""        <tr>
            <td>{pt.point_id}</td>
            <td>{pt.point_name}</td>
            <td>{pt.location}</td>
            <td>{pt.media_type.value}</td>
            <td>{pt.sampling_date}</td>
        </tr>
"""

        html += """    </table>

    <h1>4 污染评估</h1>
"""

        for i, assessment in enumerate(data.pollution_assessments, 1):
            level_map = {
                PollutionLevel.CLEAN: "未污染",
                PollutionLevel.LIGHT: "轻度污染",
                PollutionLevel.MODERATE: "中度污染",
                PollutionLevel.SEVERE: "重度污染",
                PollutionLevel.UNKNOWN: "未知"
            }
            level_display = level_map.get(assessment.pollution_level, "未知")

            html += f"""    <h2>4.{i} {assessment.media_type.value}污染评估</h2>
    <ul>
        <li><strong>评估范围</strong>: {assessment.assessment_area}</li>
        <li><strong>污染等级</strong>: {level_display}</li>
        <li><strong>主要污染物</strong>: {', '.join(assessment.main_contaminants) if assessment.main_contaminants else '-'}</li>
        <li><strong>超标参数</strong>: {', '.join(assessment.exceedance_parameters) if assessment.exceedance_parameters else '-'}</li>
        <li><strong>评估结论</strong>: {assessment.assessment_conclusion}</li>
    </ul>
"""

        html += """    <h1>5 结论与建议</h1>
    <h2>5.1 主要结论</h2>
    <p>根据现场调查、采样检测和综合分析，本次场地污染源调查与环境评估的主要结论如下：</p>
    <ol>
        <li>场地现状：...</li>
        <li>污染状况：...</li>
        <li>环境质量：...</li>
    </ol>

    <h2>5.2 建议</h2>
    <ol>
        <li>针对检出污染物，建议采取以下修复措施：...</li>
        <li>后续监测建议：...</li>
        <li>开发建设建议：...</li>
    </ol>

    <h1>6 附件</h1>
    <ol>
        <li>现场照片</li>
        <li>检测报告副本</li>
        <li>实验室资质证书</li>
        <li>采样原始记录</li>
    </ol>

    <div class="footer">
        <p>本报告由""" + cover.assessment_unit + """编制</p>
        <p>生成时间: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
    </div>
</body>
</html>"""

        return html

    def generate_pollution_source_table(
        self,
        data: PollutionAssessmentReportData
    ) -> List[Dict]:
        """生成污染源汇总表"""
        table = []
        for src in data.pollution_sources:
            table.append({
                "source_id": src.source_id,
                "source_name": src.source_name,
                "source_type": src.source_type,
                "location": src.location,
                "contaminants": ", ".join(src.contaminants),
                "operation_status": src.operation_status,
                "risk_level": src.risk_level,
            })
        return table

    def generate_exceedance_summary(
        self,
        data: PollutionAssessmentReportData
    ) -> Dict[str, Any]:
        """生成超标汇总"""
        summary = {
            "total_samples": 0,
            "exceeded_samples": 0,
            "exceedance_rate": 0.0,
            "max_exceedance_ratio": 0.0,
            "max_exceeded_parameter": "",
            "max_exceeded_point": "",
            "parameters_detail": {}
        }

        for point in data.sampling_points:
            for sample in point.samples:
                summary["total_samples"] += 1
                if sample.is_exceeded:
                    summary["exceeded_samples"] += 1
                    if sample.exceedance_ratio > summary["max_exceedance_ratio"]:
                        summary["max_exceedance_ratio"] = sample.exceedance_ratio
                        summary["max_exceeded_parameter"] = sample.parameter
                        summary["max_exceeded_point"] = f"{point.point_id} {point.point_name}"

                    if sample.parameter not in summary["parameters_detail"]:
                        summary["parameters_detail"][sample.parameter] = {
                            "count": 0,
                            "max_ratio": 0.0,
                            "max_point": ""
                        }
                    summary["parameters_detail"][sample.parameter]["count"] += 1
                    if sample.exceedance_ratio > summary["parameters_detail"][sample.parameter]["max_ratio"]:
                        summary["parameters_detail"][sample.parameter]["max_ratio"] = sample.exceedance_ratio
                        summary["parameters_detail"][sample.parameter]["max_point"] = f"{point.point_id}"

        if summary["total_samples"] > 0:
            summary["exceedance_rate"] = summary["exceeded_samples"] / summary["total_samples"]

        return summary


# =============================================================================
# 便捷函数
# =============================================================================

def create_pollution_assessment_report(
    project_name: str,
    report_title: str = None,
    entrust_unit: str = "",
    assessment_unit: str = "",
    **kwargs
) -> PollutionAssessmentReportData:
    """
    创建污染评估报告数据的便捷函数

    用法:
        data = create_pollution_assessment_report(
            project_name="XX场地",
            report_title="场地污染源调查与环境评估报告",
            entrust_unit="XX公司",
            assessment_unit="XX环境科技有限公司",
        )

        # 添加污染源
        add_pollution_source(data, ...)

        # 生成报告
        generator = PollutionAssessmentReportGenerator()
        path = generator.generate(data, format=AssessmentReportFormat.DOCX)
    """
    generator = PollutionAssessmentReportGenerator()
    return generator.create_report_data(
        project_name=project_name,
        report_title=report_title,
        entrust_unit=entrust_unit,
        assessment_unit=assessment_unit,
        **kwargs
    )


def add_pollution_source(
    data: PollutionAssessmentReportData,
    source_name: str,
    source_type: str,
    location: str,
    **kwargs
) -> PollutionSource:
    """添加污染源的便捷函数"""
    generator = PollutionAssessmentReportGenerator()
    return generator.add_pollution_source(data, source_name, source_type, location, **kwargs)


def add_sampling_point(
    data: PollutionAssessmentReportData,
    point_name: str,
    location: str,
    media_type: MediaType,
    sampling_date: str,
    **kwargs
) -> SamplingPoint:
    """添加采样点的便捷函数"""
    generator = PollutionAssessmentReportGenerator()
    return generator.add_sampling_point(data, point_name, location, media_type, sampling_date, **kwargs)


# =============================================================================
# 验证入口
# =============================================================================

if __name__ == "__main__":
    # 测试报告生成
    logging.basicConfig(level=logging.INFO)

    generator = PollutionAssessmentReportGenerator()

    # 创建报告数据
    report_data = generator.create_report_data(
        project_name="某化工场地污染源调查",
        report_title="某化工场地污染源调查与环境评估报告",
        entrust_unit="某市人民政府",
        assessment_unit="某某环境科技有限公司",
        project_address="某市某区某路",
        project_type="化工场地",
        area="50000 m²",
        total_investment="5亿元",
        construction_scale="新建",
    )

    # 添加污染源
    generator.add_pollution_source(
        report_data,
        source_name="原生产车间",
        source_type="工业",
        location="场地中部",
        contaminants=["苯", "甲苯", "二甲苯", "石油烃"],
        operation_status="停产",
        risk_level="高",
    )

    generator.add_pollution_source(
        report_data,
        source_name="储罐区",
        source_type="储罐",
        location="场地北部",
        contaminants=["原油", "柴油"],
        operation_status="废弃",
        risk_level="中",
    )

    # 添加采样点
    pt1 = generator.add_sampling_point(
        report_data,
        point_name="生产车间东南角",
        location="场地中部",
        media_type=MediaType.SOIL,
        sampling_date="2024-03-15",
        depth="0-0.5m",
    )

    generator.add_sample(pt1, "土壤样品S01", "苯", 0.05, "mg/kg", 0.04, detection_method="GB/T 5750")
    generator.add_sample(pt1, "土壤样品S01", "甲苯", 1.2, "mg/kg", 1.0, detection_method="GB/T 5750")

    # 生成报告
    output_path = generator.generate(
        report_data,
        format=AssessmentReportFormat.HTML,
        output_dir="./test_output"
    )

    print(f"\n报告已生成: {output_path}")
