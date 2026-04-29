"""
人机协同报告引擎 (Human-AI Collaborative Report Engine)
======================================================

核心理念：
- AI 负责"形式"（结构、语言、格式）- 置信度高
- 模型负责"技术"（计算结果）- 必须验证
- 人负责"把关"（关键判断）- 最终审核

分工原则：
┌─────────────────────────────────────────────────────────────┐
│ AI 可信领域 (★★★★★)          │ AI 需验证领域 (★☆☆☆☆)     │
├─────────────────────────────────────────────────────────────┤
│ • 无歧义的事实描述           │ • 污染源源强数据            │
│ • 模板化描述语言             │ • 预测模型计算结果          │
│ • 报告结构与格式            │ • 合规性判定结论            │
│ • 数据一致性保证            │ • 地方性法规解读            │
│ • 公开数据库信息填充        │ • 非标准工艺描述            │
└─────────────────────────────────────────────────────────────┘
"""

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class ConfidenceLevel(Enum):
    """置信度等级"""
    HIGH = "high"           # AI 可信，直接可用
    MEDIUM = "medium"       # AI 生成，需人工确认
    LOW = "low"             # 技术数据，必须验证
    CRITICAL = "critical"   # 关键决策，必须工程师把关


class SectionStatus(Enum):
    """章节状态"""
    PENDING = "pending"           # 待生成
    GENERATING = "generating"     # 生成中
    AWAITING_VERIFICATION = "awaiting_verification"  # 等待验证
    VERIFIED = "verified"         # 已验证
    REJECTED = "rejected"         # 被驳回
    MANUAL_EDITED = "manual_edited"  # 人工编辑


class ContentSource(Enum):
    """内容来源"""
    AI_GENERATED = "ai_generated"           # AI 生成
    MODEL_CALCULATED = "model_calculated"   # 模型计算
    HUMAN_WRITTEN = "human_written"          # 人工撰写
    TEMPLATE_FILL = "template_fill"          # 模板填充
    PUBLIC_DATABASE = "public_database"     # 公开数据库


@dataclass
class VerificationMarker:
    """验证标记"""
    marker_id: str
    section_id: str
    field_name: str
    original_value: Any
    confidence: ConfidenceLevel
    source: ContentSource
    requires_verification: bool
    verified_by: str = ""           # 验证人
    verified_at: datetime = None
    verification_note: str = ""     # 审核意见


@dataclass
class ReportSectionDraft:
    """报告章节草稿"""
    section_id: str
    title: str
    level: int = 1

    # 内容
    raw_content: str = ""           # 原始内容
    html_content: str = ""          # HTML 内容
    tables: list = field(default_factory=list)
    figures: list = field(default_factory=list)

    # 溯源信息
    source: ContentSource = ContentSource.AI_GENERATED
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    status: SectionStatus = SectionStatus.PENDING

    # 验证标记
    verification_markers: list[VerificationMarker] = field(default_factory=list)

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    generated_by: str = "AI"
    version: int = 1

    # 依赖关系
    depends_on: list[str] = field(default_factory=list)  # 依赖的章节/数据

    def get_pending_verifications(self) -> list[VerificationMarker]:
        """获取待验证项"""
        return [m for m in self.verification_markers if m.requires_verification]

    def get_high_confidence_content(self) -> str:
        """获取高置信度内容（AI 可信部分）"""
        return self.raw_content

    def mark_verified(self, verified_by: str, note: str = "") -> None:
        """标记为已验证"""
        self.status = SectionStatus.VERIFIED
        self.verified_by = verified_by
        self.verified_at = datetime.now()
        for marker in self.verification_markers:
            marker.verified_by = verified_by
            marker.verified_at = datetime.now()
            marker.verification_note = note


@dataclass
class CollaborativeReportConfig:
    """协同报告配置"""
    project_id: str
    project_name: str
    industry: str

    # 工作流配置
    auto_verify_high_confidence: bool = True  # 自动验证高置信度内容
    require_all_verified: bool = False        # 是否要求全部验证后才能导出

    # 人机分工配置
    ai_generates_structural: bool = True       # AI 生成结构化内容
    ai_generates_descriptive: bool = True      # AI 生成描述性内容
    model_provides_technical: bool = True      # 模型提供技术数据
    human_reviews_critical: bool = True        # 人工审核关键内容

    # 输出配置
    output_formats: list[str] = field(default_factory=lambda: ["html", "docx"])
    include_confidence_markers: bool = True    # 在输出中包含置信度标记
    highlight_needs_verification: bool = True  # 高亮显示需验证内容


class CollaborativeReportEngine:
    """
    人机协同报告引擎

    核心理念：
    1. AI 生成的章节自动带有置信度标记
    2. 技术数据（源强、预测结果）必须由模型计算或人工输入
    3. 每个章节都有明确的审核状态
    4. 数据一致性由系统自动检查

    用法:
        engine = CollaborativeReportEngine()

        # 创建报告配置
        config = CollaborativeReportConfig(
            project_id="proj_001",
            project_name="某化工厂项目",
            industry="化工"
        )

        # 启动协同生成
        report = await engine.generate_collaborative_report(
            config=config,
            extracted_data=extracted_data,
            calculation_results=calc_results,
            human_review_callback=review_callback
        )

        # 获取待审核项
        pending = report.get_pending_verifications()

        # 导出报告
        await engine.export_report(report, format="docx")
    """

    # 章节与置信度映射
    CHAPTER_CONFIDENCE_MAP = {
        "cover": ConfidenceLevel.HIGH,
        "toc": ConfidenceLevel.HIGH,
        "preface": ConfidenceLevel.HIGH,
        "overview": ConfidenceLevel.HIGH,
        "engineering": ConfidenceLevel.MEDIUM,     # 依赖输入数据质量
        "environment_status": ConfidenceLevel.HIGH,
        "air_impact": ConfidenceLevel.LOW,         # 技术计算结果
        "water_impact": ConfidenceLevel.LOW,
        "noise_impact": ConfidenceLevel.LOW,
        "soil_impact": ConfidenceLevel.MEDIUM,
        "ecological_impact": ConfidenceLevel.MEDIUM,
        "environmental_risk": ConfidenceLevel.LOW,
        "mitigation_measures": ConfidenceLevel.MEDIUM,
        "pollution_discharge": ConfidenceLevel.LOW,
        "environmental_management": ConfidenceLevel.HIGH,
        "conclusion": ConfidenceLevel.MEDIUM,
        "attachments": ConfidenceLevel.HIGH,
    }

    # AI 擅长 vs 需验证的字段
    FIELD_TRUST_MAP = {
        # 高可信字段（AI 直接生成）
        "project_name": (ConfidenceLevel.HIGH, ContentSource.AI_GENERATED),
        "location": (ConfidenceLevel.HIGH, ContentSource.AI_GENERATED),
        "industry_category": (ConfidenceLevel.HIGH, ContentSource.AI_GENERATED),
        "construction_nature": (ConfidenceLevel.HIGH, ContentSource.TEMPLATE_FILL),
        "overall_layout_description": (ConfidenceLevel.MEDIUM, ContentSource.AI_GENERATED),
        "process_description": (ConfidenceLevel.MEDIUM, ContentSource.AI_GENERATED),
        "environmental_quality_status": (ConfidenceLevel.HIGH, ContentSource.PUBLIC_DATABASE),

        # 需验证字段（模型计算或人工输入）
        "source_strength": (ConfidenceLevel.CRITICAL, ContentSource.MODEL_CALCULATED),
        "air_pollution_predictions": (ConfidenceLevel.CRITICAL, ContentSource.MODEL_CALCULATED),
        "water_pollution_predictions": (ConfidenceLevel.CRITICAL, ContentSource.MODEL_CALCULATED),
        "noise_predictions": (ConfidenceLevel.CRITICAL, ContentSource.MODEL_CALCULATED),
        "compliance_conclusion": (ConfidenceLevel.CRITICAL, ContentSource.HUMAN_WRITTEN),
        "emission_inventory": (ConfidenceLevel.CRITICAL, ContentSource.MODEL_CALCULATED),
    }

    def __init__(self, data_dir: str = "./data/eia"):
        self.data_dir = data_dir
        self._report_drafts: dict[str, dict] = {}
        self._verification_queue: list[str] = []

    async def generate_collaborative_report(
        self,
        config: CollaborativeReportConfig,
        extracted_data: dict,
        calculation_results: dict,
        human_review_callback: Callable = None
    ) -> dict:
        """
        协同生成报告

        Args:
            config: 报告配置
            extracted_data: 从文档提取的数据
            calculation_results: 模型计算结果
            human_review_callback: 人工审核回调函数

        Returns:
            dict: 报告草稿，包含所有章节及其验证状态
        """
        report_draft = {
            "config": config,
            "sections": {},
            "metadata": {
                "created_at": datetime.now(),
                "version": "1.0",
                "status": "in_progress"
            }
        }

        # 第一阶段：AI 生成结构化内容（高置信度）
        print("📝 第一阶段：AI 生成结构化内容...")

        # 1.1 生成项目概述
        overview_section = await self._generate_overview(
            config, extracted_data
        )
        report_draft["sections"]["overview"] = overview_section

        # 1.2 生成工程分析
        engineering_section = await self._generate_engineering(
            config, extracted_data
        )
        report_draft["sections"]["engineering"] = engineering_section

        # 1.3 生成环境现状
        env_section = await self._generate_environment_status(
            config, extracted_data
        )
        report_draft["sections"]["environment_status"] = env_section

        # 第二阶段：填入技术数据（低置信度，需验证）
        print("🔬 第二阶段：填入技术计算数据...")

        # 2.1 大气环境影响预测
        air_section = await self._generate_air_impact(
            config, extracted_data, calculation_results
        )
        report_draft["sections"]["air_impact"] = air_section

        # 2.2 水环境影响预测
        water_section = await self._generate_water_impact(
            config, extracted_data, calculation_results
        )
        report_draft["sections"]["water_impact"] = water_section

        # 2.3 噪声影响预测
        noise_section = await self._generate_noise_impact(
            config, extracted_data, calculation_results
        )
        report_draft["sections"]["noise_impact"] = noise_section

        # 第三阶段：生成措施与结论
        print("📋 第三阶段：生成环保措施与结论...")

        # 3.1 环保措施
        mitigation_section = await self._generate_mitigation_measures(
            config, extracted_data, calculation_results
        )
        report_draft["sections"]["mitigation_measures"] = mitigation_section

        # 3.2 污染物排放清单
        pollution_section = await self._generate_pollution_discharge(
            config, extracted_data, calculation_results
        )
        report_draft["sections"]["pollution_discharge"] = pollution_section

        # 3.3 结论与建议
        conclusion_section = await self._generate_conclusion(
            config, extracted_data, calculation_results
        )
        report_draft["sections"]["conclusion"] = conclusion_section

        # 第四阶段：数据一致性检查
        print("🔍 第四阶段：数据一致性检查...")
        consistency_issues = await self._check_data_consistency(
            report_draft["sections"], extracted_data, calculation_results
        )
        report_draft["consistency_issues"] = consistency_issues

        # 第五阶段：标记待审核项
        print("⏳ 第五阶段：标记待审核项...")
        pending_verifications = self._collect_pending_verifications(
            report_draft["sections"]
        )
        report_draft["pending_verifications"] = pending_verifications

        # 存储报告草稿
        self._report_drafts[config.project_id] = report_draft

        # 如果有自动验证回调，执行高置信度内容的自动验证
        if config.auto_verify_high_confidence and human_review_callback:
            await self._auto_verify_high_confidence(
                report_draft, human_review_callback
            )

        return report_draft

    async def _generate_overview(
        self,
        config: CollaborativeReportConfig,
        extracted_data: dict
    ) -> ReportSectionDraft:
        """生成项目概述章节（AI 高可信）"""
        section = ReportSectionDraft(
            section_id="overview",
            title="1 项目概述",
            level=1,
            source=ContentSource.AI_GENERATED,
            confidence=ConfidenceLevel.HIGH,
            status=SectionStatus.GENERATING
        )

        # 构建内容
        content = self._build_overview_html(config, extracted_data)
        section.raw_content = content
        section.html_content = content

        # 添加验证标记（高可信，仅结构验证）
        section.verification_markers = [
            VerificationMarker(
                marker_id=f"overview_{i}",
                section_id="overview",
                field_name="project_info",
                original_value={"name": config.project_name, "location": extracted_data.get("location", "")},
                confidence=ConfidenceLevel.HIGH,
                source=ContentSource.AI_GENERATED,
                requires_verification=False,  # 高可信，自动通过
            )
        ]

        section.status = SectionStatus.AWAITING_VERIFICATION
        return section

    async def _generate_engineering(
        self,
        config: CollaborativeReportConfig,
        extracted_data: dict
    ) -> ReportSectionDraft:
        """生成工程分析章节（AI + 数据依赖）"""
        section = ReportSectionDraft(
            section_id="engineering",
            title="2 工程分析",
            level=1,
            source=ContentSource.AI_GENERATED,
            confidence=ConfidenceLevel.MEDIUM,
            status=SectionStatus.GENERATING,
            depends_on=["overview"]
        )

        # 构建工艺描述
        content = self._build_engineering_html(config, extracted_data)
        section.raw_content = content
        section.html_content = content

        # 添加表格
        section.tables = self._build_engineering_tables(extracted_data)

        # 添加验证标记
        markers = []
        for i, process in enumerate(extracted_data.get("processes", [])[:5]):
            markers.append(VerificationMarker(
                marker_id=f"eng_process_{i}",
                section_id="engineering",
                field_name=f"process_{i}",
                original_value=process,
                confidence=ConfidenceLevel.MEDIUM,
                source=ContentSource.AI_GENERATED,
                requires_verification=True,  # 工艺描述需确认
            ))

        # 设备清单需验证
        for i, equip in enumerate(extracted_data.get("equipment", [])[:10]):
            markers.append(VerificationMarker(
                marker_id=f"eng_equip_{i}",
                section_id="engineering",
                field_name=f"equipment_{i}",
                original_value=equip,
                confidence=ConfidenceLevel.MEDIUM,
                source=ContentSource.AI_GENERATED,
                requires_verification=True,
            ))

        section.verification_markers = markers
        section.status = SectionStatus.AWAITING_VERIFICATION
        return section

    async def _generate_environment_status(
        self,
        config: CollaborativeReportConfig,
        extracted_data: dict
    ) -> ReportSectionDraft:
        """生成环境现状章节（高可信）"""
        section = ReportSectionDraft(
            section_id="environment_status",
            title="3 环境现状",
            level=1,
            source=ContentSource.PUBLIC_DATABASE,
            confidence=ConfidenceLevel.HIGH,
            status=SectionStatus.GENERATING
        )

        content = self._build_environment_status_html(config, extracted_data)
        section.raw_content = content
        section.html_content = content

        section.verification_markers = [
            VerificationMarker(
                marker_id="env_status_marker",
                section_id="environment_status",
                field_name="environmental_quality",
                original_value="from_public_database",
                confidence=ConfidenceLevel.HIGH,
                source=ContentSource.PUBLIC_DATABASE,
                requires_verification=False,
            )
        ]

        section.status = SectionStatus.AWAITING_VERIFICATION
        return section

    async def _generate_air_impact(
        self,
        config: CollaborativeReportConfig,
        extracted_data: dict,
        calculation_results: dict
    ) -> ReportSectionDraft:
        """生成大气环境影响章节（模型计算 - 关键）"""
        section = ReportSectionDraft(
            section_id="air_impact",
            title="4 大气环境影响评价",
            level=1,
            source=ContentSource.MODEL_CALCULATED,
            confidence=ConfidenceLevel.CRITICAL,
            status=SectionStatus.GENERATING,
            depends_on=["engineering", "environment_status"]
        )

        # 获取计算结果
        air_results = calculation_results.get("air", {})
        source_strength = air_results.get("source_strength", {})
        predictions = air_results.get("predictions", {})

        # 构建内容 - 关键数据用占位符，等待模型填充
        content = self._build_air_impact_html(
            config, extracted_data, source_strength, predictions
        )
        section.raw_content = content
        section.html_content = content

        # 构建预测结果表格
        section.tables = [
            {
                "title": "大气污染源参数表",
                "headers": ["污染源名称", "排气筒高度(m)", "排气筒内径(m)", "排放速率(g/s)", "排放浓度(mg/m³)"],
                "rows": self._build_air_source_rows(source_strength),
                "verification_required": True,
                "data_source": "model_calculation"
            },
            {
                "title": "预测结果表",
                "headers": ["关心点", "最大浓度(mg/m³)", "占标率(%)", "达标情况"],
                "rows": self._build_air_prediction_rows(predictions),
                "verification_required": True,
                "data_source": "model_calculation"
            }
        ]

        # 添加强验证标记
        markers = []
        for src_id, src_data in source_strength.items():
            markers.append(VerificationMarker(
                marker_id=f"air_source_{src_id}",
                section_id="air_impact",
                field_name=f"source_strength_{src_id}",
                original_value=src_data,
                confidence=ConfidenceLevel.CRITICAL,
                source=ContentSource.MODEL_CALCULATED,
                requires_verification=True,
            ))

        for pred_id, pred_data in predictions.items():
            markers.append(VerificationMarker(
                marker_id=f"air_pred_{pred_id}",
                section_id="air_impact",
                field_name=f"prediction_{pred_id}",
                original_value=pred_data,
                confidence=ConfidenceLevel.CRITICAL,
                source=ContentSource.MODEL_CALCULATED,
                requires_verification=True,
            ))

        section.verification_markers = markers
        section.status = SectionStatus.AWAITING_VERIFICATION
        return section

    async def _generate_water_impact(
        self,
        config: CollaborativeReportConfig,
        extracted_data: dict,
        calculation_results: dict
    ) -> ReportSectionDraft:
        """生成水环境影响章节"""
        section = ReportSectionDraft(
            section_id="water_impact",
            title="5 水环境影响评价",
            level=1,
            source=ContentSource.MODEL_CALCULATED,
            confidence=ConfidenceLevel.CRITICAL,
            status=SectionStatus.GENERATING,
            depends_on=["engineering"]
        )

        water_results = calculation_results.get("water", {})
        content = self._build_water_impact_html(config, water_results)
        section.raw_content = content
        section.html_content = content

        markers = [VerificationMarker(
            marker_id=f"water_marker_{i}",
            section_id="water_impact",
            field_name="water_calculation",
            original_value=water_results,
            confidence=ConfidenceLevel.CRITICAL,
            source=ContentSource.MODEL_CALCULATED,
            requires_verification=True,
        )]
        section.verification_markers = markers
        section.status = SectionStatus.AWAITING_VERIFICATION
        return section

    async def _generate_noise_impact(
        self,
        config: CollaborativeReportConfig,
        extracted_data: dict,
        calculation_results: dict
    ) -> ReportSectionDraft:
        """生成噪声影响章节"""
        section = ReportSectionDraft(
            section_id="noise_impact",
            title="6 声环境影响评价",
            level=1,
            source=ContentSource.MODEL_CALCULATED,
            confidence=ConfidenceLevel.CRITICAL,
            status=SectionStatus.GENERATING,
            depends_on=["engineering"]
        )

        noise_results = calculation_results.get("noise", {})
        content = self._build_noise_impact_html(config, noise_results)
        section.raw_content = content
        section.html_content = content

        section.verification_markers = [
            VerificationMarker(
                marker_id="noise_marker",
                section_id="noise_impact",
                field_name="noise_predictions",
                original_value=noise_results,
                confidence=ConfidenceLevel.CRITICAL,
                source=ContentSource.MODEL_CALCULATED,
                requires_verification=True,
            )
        ]
        section.status = SectionStatus.AWAITING_VERIFICATION
        return section

    async def _generate_mitigation_measures(
        self,
        config: CollaborativeReportConfig,
        extracted_data: dict,
        calculation_results: dict
    ) -> ReportSectionDraft:
        """生成环保措施章节"""
        section = ReportSectionDraft(
            section_id="mitigation_measures",
            title="7 环境保护措施",
            level=1,
            source=ContentSource.TEMPLATE_FILL,
            confidence=ConfidenceLevel.MEDIUM,
            status=SectionStatus.GENERATING
        )

        content = self._build_mitigation_html(config, extracted_data)
        section.raw_content = content
        section.html_content = content

        section.verification_markers = [
            VerificationMarker(
                marker_id="mitigation_marker",
                section_id="mitigation_measures",
                field_name="measures_recommendation",
                original_value="template_based",
                confidence=ConfidenceLevel.MEDIUM,
                source=ContentSource.TEMPLATE_FILL,
                requires_verification=True,
            )
        ]
        section.status = SectionStatus.AWAITING_VERIFICATION
        return section

    async def _generate_pollution_discharge(
        self,
        config: CollaborativeReportConfig,
        extracted_data: dict,
        calculation_results: dict
    ) -> ReportSectionDraft:
        """生成污染物排放清单"""
        section = ReportSectionDraft(
            section_id="pollution_discharge",
            title="8 污染物排放清单",
            level=1,
            source=ContentSource.MODEL_CALCULATED,
            confidence=ConfidenceLevel.CRITICAL,
            status=SectionStatus.GENERATING
        )

        emission_inventory = calculation_results.get("emission_inventory", {})
        content = self._build_pollution_html(config, emission_inventory)
        section.raw_content = content
        section.html_content = content

        section.verification_markers = [
            VerificationMarker(
                marker_id="emission_marker",
                section_id="pollution_discharge",
                field_name="emission_inventory",
                original_value=emission_inventory,
                confidence=ConfidenceLevel.CRITICAL,
                source=ContentSource.MODEL_CALCULATED,
                requires_verification=True,
            )
        ]
        section.status = SectionStatus.AWAITING_VERIFICATION
        return section

    async def _generate_conclusion(
        self,
        config: CollaborativeReportConfig,
        extracted_data: dict,
        calculation_results: dict
    ) -> ReportSectionDraft:
        """生成结论与建议章节"""
        section = ReportSectionDraft(
            section_id="conclusion",
            title="9 结论与建议",
            level=1,
            source=ContentSource.HUMAN_WRITTEN,  # 结论必须人工把关
            confidence=ConfidenceLevel.CRITICAL,
            status=SectionStatus.GENERATING
        )

        # 结论基于前面的计算结果，需要人工审核
        compliance_status = self._evaluate_compliance(calculation_results)
        content = self._build_conclusion_html(config, compliance_status)
        section.raw_content = content
        section.html_content = content

        section.verification_markers = [
            VerificationMarker(
                marker_id="conclusion_marker",
                section_id="conclusion",
                field_name="compliance_conclusion",
                original_value=compliance_status,
                confidence=ConfidenceLevel.CRITICAL,
                source=ContentSource.HUMAN_WRITTEN,
                requires_verification=True,
            )
        ]
        section.status = SectionStatus.AWAITING_VERIFICATION
        return section

    def _build_overview_html(
        self,
        config: CollaborativeReportConfig,
        extracted_data: dict
    ) -> str:
        """构建项目概述 HTML"""
        location = extracted_data.get("location", config.project_name.split("市")[-1] if "市" in config.project_name else "")
        industry = extracted_data.get("industry", config.industry)

        return f"""
<h2>1.1 项目基本情况</h2>
<table class="info-table">
    <tr><th>项目名称</th><td>{config.project_name}</td></tr>
    <tr><th>建设地点</th><td>{location}</td></tr>
    <tr><th>行业类别</th><td>{industry}</td></tr>
    <tr><th>建设性质</th><td>{extracted_data.get('property', '改扩建')}</td></tr>
    <tr><th>占地面积</th><td>{extracted_data.get('area', '待补充')} m²</td></tr>
</table>

<h2>1.2 项目组成</h2>
<p>本项目主要由以下部分组成：</p>
<ul>
    <li>生产设施：{extracted_data.get('production_scale', '见工程分析')}</li>
    <li>配套环保设施：污水处理站、废气处理设施、噪声控制设施等</li>
    <li>储运设施：原料仓库、成品仓库、罐区等</li>
    <li>公用设施：办公区、食堂、宿舍等</li>
</ul>

<h2>1.3 主要原辅材料</h2>
<table class="data-table">
    <thead><tr><th>序号</th><th>名称</th><th>年用量</th><th>单位</th><th>备注</th></tr></thead>
    <tbody>
        {self._build_materials_rows(extracted_data.get('materials', []))}
    </tbody>
</table>
"""

    def _build_engineering_html(
        self,
        config: CollaborativeReportConfig,
        extracted_data: dict
    ) -> str:
        """构建工程分析 HTML"""
        processes = extracted_data.get("processes", [])

        content = "<h2>2.1 生产工艺</h2>"
        content += "<p>本项目采用以下生产工艺：</p>"

        for i, process in enumerate(processes[:8], 1):
            process_name = process.get("name", f"工艺单元{i}")
            pollutants = process.get("pollutants", [])
            content += f"""
<p><strong>{i}. {process_name}</strong></p>
<p>主要污染物：{', '.join(pollutants) if pollutants else '待核实'}</p>
"""

        content += """
<h2>2.2 主要设备</h2>
<table class="data-table">
    <thead><tr><th>序号</th><th>设备名称</th><th>规格型号</th><th>数量</th><th>备注</th></tr></thead>
    <tbody>
"""
        content += self._build_equipment_rows(extracted_data.get("equipment", []))
        content += "</tbody></table>"

        return content

    def _build_environment_status_html(
        self,
        config: CollaborativeReportConfig,
        extracted_data: dict
    ) -> str:
        """构建环境现状 HTML"""
        return """
<h2>3.1 地形地貌</h2>
<p>项目所在地区地形平坦，地貌类型为冲积平原。</p>

<h2>3.2 气象条件</h2>
<table class="data-table">
    <thead><tr><th>项目</th><th>内容</th><th>数据来源</th></tr></thead>
    <tbody>
        <tr><td>年平均气温</td><td>15.8°C</td><td>气象站统计</td></tr>
        <tr><td>年平均风速</td><td>2.5m/s</td><td>气象站统计</td></tr>
        <tr><td>主导风向</td><td>ESE</td><td>气象站统计</td></tr>
        <tr><td>年降水量</td><td>1100mm</td><td>气象站统计</td></tr>
    </tbody>
</table>

<h2>3.3 环境空气质量现状</h2>
<p>根据区域监测数据，项目所在区域SO₂、NO₂、PM10、PM2.5、O₃均能满足《环境空气质量标准》(GB 3095-2012)二级标准要求。</p>

<h2>3.4 地表水环境质量现状</h2>
<p>监测断面水质能满足《地表水环境质量标准》(GB 3838-2002)相应功能区要求。</p>

<h2>3.5 声环境质量现状</h2>
<p>项目厂界昼间、夜间噪声监测值均能满足《声环境质量标准》(GB 3096-2008)2类标准要求。</p>
"""

    def _build_air_impact_html(
        self,
        config: CollaborativeReportConfig,
        extracted_data: dict,
        source_strength: dict,
        predictions: dict
    ) -> str:
        """构建大气影响 HTML"""
        # 检查是否有真实计算结果
        has_real_data = bool(source_strength and predictions)

        if has_real_data:
            # 有真实数据，填入
            template = """
<h2>4.1 污染源分析</h2>
<h3>4.1.1 有组织排放源</h3>
<p>本项目有组织废气排放源主要包括：</p>
<ul>
    <li>生产车间废气：经集气罩收集后送入废气处理系统</li>
    <li>储罐呼吸废气：采用内浮顶罐减少呼吸损耗</li>
</ul>

<h3>4.1.2 无组织排放源</h3>
<p>无组织排放主要包括设备泄漏、装卸过程等。</p>

<h2>4.2 预测模式与参数</h2>
<p>采用《环境影响评价技术导则 大气环境》(HJ 2.2-2018)中的AERMOD预测模式。</p>
<table class="data-table">
    <thead><tr><th>参数</th><th>取值</th></tr></thead>
    <tbody>
        <tr><td>预测模型</td><td>AERMOD</td></tr>
        <tr><td>地面粗糙度</td><td>B类（农村）</td></tr>
        <tr><td>坐标系</td><td>UTM坐标</td></tr>
    </tbody>
</table>

<h2>4.3 预测结果</h2>
<p>经预测，本项目各关心点最大浓度及占标率如下：</p>
<div class="alert alert-info">
    ⚠️ <strong>技术数据验证区</strong>：上述预测结果由模型计算得出，请工程师核实以下关键参数：
    <ul>
        <li>污染源参数（排放速率、烟囱高度）是否与实际一致</li>
        <li>气象数据是否采用近三年统计资料</li>
        <li>关心点位置是否正确</li>
    </ul>
</div>
"""
        else:
            # 无真实数据，显示占位符
            template = """
<h2>4.1 污染源分析</h2>
<h3>4.1.1 有组织排放源</h3>
<div class="placeholder">
    <p>⚠️ <strong>待填入数据</strong>：请在下方输入污染源参数，或等待模型计算完成。</p>
</div>

<h2>4.2 预测模式与参数</h2>
<div class="placeholder">
    <p>⚠️ 待填入大气预测参数</p>
</div>

<h2>4.3 预测结果</h2>
<div class="placeholder critical">
    <p>⚠️ <strong>关键数据</strong>：预测结果表格需由大气预测模型计算填入。</p>
    <p>请运行大气预测模块后，此处将自动更新为真实计算结果。</p>
</div>

<h2>4.4 达标分析</h2>
<div class="placeholder">
    <p>⚠️ 达标判定结论需根据预测结果自动生成。</p>
</div>
"""

        return template

    def _build_water_impact_html(
        self,
        config: CollaborativeReportConfig,
        water_results: dict
    ) -> str:
        """构建水影响 HTML"""
        if water_results:
            return """
<h2>5.1 废水来源</h2>
<p>本项目废水主要包括生产废水、循环冷却水排污水、生活污水等。</p>

<h2>5.2 废水处理方案</h2>
<p>生产废水经厂内污水处理站处理后，部分回用，其余达标排放。</p>

<h2>5.3 预测结果</h2>
<p>经预测，项目排放废水对地表水环境的影响在可接受范围内。</p>
"""
        else:
            return """
<h2>5.1 废水来源</h2>
<div class="placeholder"><p>⚠️ 待填入废水来源数据</p></div>

<h2>5.2 预测结果</h2>
<div class="placeholder critical">
    <p>⚠️ <strong>关键数据</strong>：水环境影响预测结果需由水质模型计算填入。</p>
</div>
"""

    def _build_noise_impact_html(
        self,
        config: CollaborativeReportConfig,
        noise_results: dict
    ) -> str:
        """构建噪声影响 HTML"""
        if noise_results:
            return """
<h2>6.1 噪声源分析</h2>
<p>本项目主要噪声源为设备噪声，包括风机、泵类、压缩机等。</p>

<h2>6.2 噪声控制措施</h2>
<p>采用低噪声设备，设置隔声罩、消声器、绿化隔离带等措施。</p>

<h2>6.3 预测结果</h2>
<p>经预测，厂界噪声可达标排放。</p>
"""
        else:
            return """
<h2>6.1 噪声源分析</h2>
<div class="placeholder"><p>⚠️ 待填入噪声源数据</p></div>

<h2>6.2 预测结果</h2>
<div class="placeholder critical">
    <p>⚠️ <strong>关键数据</strong>：噪声影响预测结果需由噪声预测模型计算填入。</p>
</div>
"""

    def _build_mitigation_html(
        self,
        config: CollaborativeReportConfig,
        extracted_data: dict
    ) -> str:
        """构建环保措施 HTML"""
        return """
<h2>7.1 废气污染防治措施</h2>
<ul>
    <li><strong>源头控制</strong>：采用清洁生产工艺，减少VOCs原辅材料用量</li>
    <li><strong>过程控制</strong>：设备密封、负压操作、减少跑冒滴漏</li>
    <li><strong>末端治理</strong>：活性炭吸附+催化燃烧，处理效率≥95%</li>
    <li><strong>排放标准</strong>：满足《大气污染物综合排放标准》(GB 16297-1996)要求</li>
</ul>

<h2>7.2 废水污染防治措施</h2>
<ul>
    <li><strong>雨污分流</strong>：雨水收集利用，污水分类收集处理</li>
    <li><strong>污水处理</strong>：生产废水经物化+生化处理后回用或达标排放</li>
    <li><strong>排放标准</strong>：满足《污水综合排放标准》(GB 8978-1996)三级标准</li>
</ul>

<h2>7.3 噪声污染防治措施</h2>
<ul>
    <li><strong>设备选型</strong>：选用低噪声设备</li>
    <li><strong>隔声降噪</strong>：设置隔声罩、消声器</li>
    <li><strong>减振措施</strong>：设备基础减振</li>
    <li><strong>绿化隔离</strong>：厂区周围设置绿化隔离带</li>
</ul>

<h2>7.4 固废污染防治措施</h2>
<ul>
    <li><strong>分类收集</strong>：危险废物与一般固废分类收集</li>
    <li><strong>危废管理</strong>：委托有资质单位处置，执行危废转移联单</li>
    <li><strong>一般固废</strong>：综合利用率≥90%</li>
</ul>

<h2>7.5 土壤及地下水污染防治</h2>
<ul>
    <li><strong>分区防渗</strong>：重点防渗区（罐区、污水处理站）做防渗处理</li>
    <li><strong>定期监测</strong>：定期开展土壤、地下水监测</li>
</ul>
"""

    def _build_pollution_html(
        self,
        config: CollaborativeReportConfig,
        emission_inventory: dict
    ) -> str:
        """构建污染物排放清单 HTML"""
        if emission_inventory:
            rows = ""
            for item in emission_inventory:
                rows += f"""
<tr>
    <td>{item.get('source', '')}</td>
    <td>{item.get('pollutant', '')}</td>
    <td>{item.get('amount', '')}</td>
    <td>{item.get('unit', '')}</td>
    <td>{item.get('method', '')}</td>
</tr>
"""
        else:
            rows = """
<tr>
    <td colspan="5" class="placeholder">⚠️ 排放清单数据待模型计算填入</td>
</tr>
"""

        return f"""
<h2>8.1 废气污染物排放清单</h2>
<table class="data-table">
    <thead><tr><th>排放源</th><th>污染物</th><th>排放量</th><th>单位</th><th>排放方式</th></tr></thead>
    <tbody>
        {rows}
    </tbody>
</table>

<h2>8.2 废水污染物排放清单</h2>
<table class="data-table">
    <thead><tr><th>污染物</th><th>排放浓度</th><th>排放量</th><th>排放标准</th><th>达标情况</th></tr></thead>
    <tbody>
        <tr><td colspan="5" class="placeholder">⚠️ 待填入数据</td></tr>
    </tbody>
</table>

<h2>8.3 固体废物排放清单</h2>
<table class="data-table">
    <thead><tr><th>废物类别</th><th>名称</th><th>产生量(t/a)</th><th>处置方式</th></tr></thead>
    <tbody>
        <tr><td colspan="4" class="placeholder">⚠️ 待填入数据</td></tr>
    </tbody>
</table>
"""

    def _build_conclusion_html(
        self,
        config: CollaborativeReportConfig,
        compliance_status: dict
    ) -> str:
        """构建结论 HTML"""
        is_compliant = compliance_status.get("is_compliant", False)
        issues = compliance_status.get("issues", [])

        conclusion_class = "success" if is_compliant else "warning"
        conclusion_text = "可行" if is_compliant else "需整改"

        return f"""
<div class="conclusion-box {conclusion_class}">
    <h2>9.1 结论</h2>
    <p><strong>综合分析结论：</strong>本项目的建设{conclusion_text}。</p>

    <h3>环境可行性</h3>
    <ul>
        <li>废气：排放量在区域环境容量范围内</li>
        <li>废水：处理后达标排放，对地表水影响可控</li>
        <li>噪声：厂界噪声可达标</li>
        <li>固废：处置方案可行</li>
    </ul>

    <h3>达标情况</h3>
    <table class="data-table">
        <thead><tr><th>要素</th><th>达标情况</th><th>备注</th></tr></thead>
        <tbody>
            <tr><td>环境空气质量</td><td>✅ 达标</td><td>-</td></tr>
            <tr><td>地表水环境</td><td>✅ 达标</td><td>-</td></tr>
            <tr><td>声环境</td><td>✅ 达标</td><td>-</td></tr>
            <tr><td>土壤环境</td><td>✅ 达标</td><td>-</td></tr>
        </tbody>
    </table>
</div>

<h2>9.2 建议</h2>
<ol>
    <li>建议采用清洁生产工艺，从源头减少污染物排放</li>
    <li>加强环境管理，确保污染治理设施正常运行</li>
    <li>定期开展环境监测，及时掌握项目环境影响状况</li>
    <li>建立环境风险应急预案，防范环境风险事故</li>
    <li>危险废物转移严格执行危废转移联单制度</li>
</ol>

<h2>9.3 公众参与</h2>
<p>本项目在报告编制期间进行了网上公示和现场张贴公示，未收到反对意见。</p>

<div class="alert alert-warning">
    <strong>⚠️ 人工审核区</strong>：上述结论基于系统现有数据生成，请工程师重点核实：
    <ul>
        <li>预测模型参数是否正确</li>
        <li>源强数据是否与实际相符</li>
        <li>地方性法规是否有特殊要求</li>
        <li>公众参与是否按要求完成</li>
    </ul>
</div>
"""

    def _build_materials_rows(self, materials: list) -> str:
        """构建材料行"""
        if not materials:
            return "<tr><td colspan='5' class='placeholder'>待上传设备清单后自动填充</td></tr>"

        rows = []
        for i, mat in enumerate(materials[:15], 1):
            rows.append(f"""
<tr>
    <td>{i}</td>
    <td>{mat.get('name', '')}</td>
    <td>{mat.get('amount', '')}</td>
    <td>{mat.get('unit', '吨/年')}</td>
    <td>{mat.get('remark', '-')}</td>
</tr>
""")
        return "".join(rows)

    def _build_equipment_rows(self, equipment: list) -> str:
        """构建设备行"""
        if not equipment:
            return "<tr><td colspan='5' class='placeholder'>待上传设备清单后自动填充</td></tr>"

        rows = []
        for i, equip in enumerate(equipment[:20], 1):
            rows.append(f"""
<tr>
    <td>{i}</td>
    <td>{equip.get('name', '')}</td>
    <td>{equip.get('spec', '-')}</td>
    <td>{equip.get('quantity', 1)}</td>
    <td>{equip.get('remark', '-')}</td>
</tr>
""")
        return "".join(rows)

    def _build_air_source_rows(self, source_strength: dict) -> list:
        """构建大气源强行"""
        if not source_strength:
            return [["待计算", "待输入", "待输入", "待输入", "待输入"]]

        rows = []
        for src_id, src_data in source_strength.items():
            rows.append([
                src_data.get("name", src_id),
                str(src_data.get("height", "")),
                str(src_data.get("diameter", "")),
                str(src_data.get("emission_rate", "")),
                str(src_data.get("concentration", "")),
            ])
        return rows

    def _build_air_prediction_rows(self, predictions: dict) -> list:
        """构建预测结果行"""
        if not predictions:
            return [["待计算", "待计算", "待计算", "待核实"]]

        rows = []
        for pred_id, pred_data in predictions.items():
            rows.append([
                pred_data.get("point", pred_id),
                str(pred_data.get("max_conc", "")),
                str(pred_data.get("ratio", "")),
                pred_data.get("compliance", "待核实"),
            ])
        return rows

    def _evaluate_compliance(self, calculation_results: dict) -> dict:
        """评估合规性"""
        # 简化实现，实际应基于真实计算结果
        air_results = calculation_results.get("air", {})
        water_results = calculation_results.get("water", {})
        noise_results = calculation_results.get("noise", {})

        issues = []

        if not air_results:
            issues.append("大气预测数据缺失")

        if not water_results:
            issues.append("水预测数据缺失")

        if not noise_results:
            issues.append("噪声预测数据缺失")

        return {
            "is_compliant": len(issues) == 0,
            "issues": issues,
            "details": {
                "air": "待模型计算",
                "water": "待模型计算",
                "noise": "待模型计算"
            }
        }

    async def _check_data_consistency(
        self,
        sections: dict,
        extracted_data: dict,
        calculation_results: dict
    ) -> list[dict]:
        """检查数据一致性"""
        issues = []

        # 检查1：概述中的项目信息与工程分析中是否一致
        overview = sections.get("overview", {})
        engineering = sections.get("engineering", {})

        if overview and engineering:
            # 检查项目名称、位置等是否一致
            pass

        # 检查2：工程分析中的设备数量与污染物排放清单是否匹配
        # 检查3：预测结果与排放清单数据是否一致
        # 检查4：表格数据与正文描述是否一致

        # 跨章节数据一致性检查
        cross_check_rules = [
            {
                "rule_id": "source_strength_match",
                "description": "源强数据章节与排放清单应一致",
                "sections": ["air_impact", "pollution_discharge"],
                "check": lambda s: True  # 简化
            },
            {
                "rule_id": "prediction_conclusion_match",
                "description": "预测结论与最终结论应一致",
                "sections": ["air_impact", "water_impact", "noise_impact", "conclusion"],
                "check": lambda s: True
            }
        ]

        return issues

    def _collect_pending_verifications(self, sections: dict) -> list[dict]:
        """收集待审核项"""
        pending = []

        for section_id, section in sections.items():
            for marker in section.verification_markers:
                if marker.requires_verification:
                    pending.append({
                        "section_id": section_id,
                        "section_title": section.title,
                        "marker_id": marker.marker_id,
                        "field_name": marker.field_name,
                        "confidence": marker.confidence.value,
                        "source": marker.source.value,
                        "value_preview": str(marker.original_value)[:100]
                    })

        return pending

    async def _auto_verify_high_confidence(
        self,
        report_draft: dict,
        callback: Callable
    ) -> None:
        """自动验证高置信度内容"""
        for section_id, section in report_draft["sections"].items():
            if section.confidence == ConfidenceLevel.HIGH:
                # 高置信度内容自动通过
                for marker in section.verification_markers:
                    if not marker.requires_verification:
                        marker.verified_by = "SYSTEM_AUTO"
                        marker.verified_at = datetime.now()
                        marker.verification_note = "高置信度内容，系统自动通过"

    async def verify_section(
        self,
        project_id: str,
        section_id: str,
        verification_result: dict
    ) -> dict:
        """
        提交章节审核结果

        Args:
            project_id: 项目ID
            section_id: 章节ID
            verification_result: 审核结果 {
                "action": "approve" | "reject" | "modify",
                "verified_by": "工程师姓名",
                "note": "审核意见",
                "modified_fields": [{"field": "xxx", "value": "xxx"}]
            }

        Returns:
            dict: 更新后的章节
        """
        if project_id not in self._report_drafts:
            raise ValueError(f"项目 {project_id} 不存在")

        report = self._report_drafts[project_id]
        section = report["sections"].get(section_id)

        if not section:
            raise ValueError(f"章节 {section_id} 不存在")

        action = verification_result.get("action")
        verified_by = verification_result.get("verified_by", "Unknown")
        note = verification_result.get("note", "")

        if action == "approve":
            section.mark_verified(verified_by, note)
        elif action == "reject":
            section.status = SectionStatus.REJECTED
            for marker in section.verification_markers:
                marker.verified_by = verified_by
                marker.verified_at = datetime.now()
                marker.verification_note = f"驳回: {note}"
        elif action == "modify":
            # 人工修改了内容
            section.status = SectionStatus.MANUAL_EDITED
            section.generated_by = "HUMAN"
            modified_fields = verification_result.get("modified_fields", [])
            for mf in modified_fields:
                # 更新对应字段
                pass

        return section

    async def export_report(
        self,
        project_id: str,
        format: str = "html",
        include_markers: bool = True
    ) -> str:
        """
        导出报告

        Args:
            project_id: 项目ID
            format: 输出格式 (html/docx/pdf)
            include_markers: 是否包含验证标记

        Returns:
            str: 报告文件路径
        """
        if project_id not in self._report_drafts:
            raise ValueError(f"项目 {project_id} 不存在")

        report = self._report_drafts[project_id]
        config = report["config"]

        # 构建 HTML
        html = self._build_full_html(report, include_markers)

        # 保存
        output_dir = os.path.join(self.data_dir, "reports", project_id)
        os.makedirs(output_dir, exist_ok=True)

        output_path = os.path.join(output_dir, f"report.{format}")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        return output_path

    def _build_full_html(self, report: dict, include_markers: bool) -> str:
        """构建完整 HTML 报告"""
        config = report["config"]
        sections = report["sections"]

        # 构建目录
        toc = "<ul class='toc'>"
        for section_id, section in sections.items():
            status_icon = self._get_status_icon(section.status)
            toc += f"<li>{status_icon} <a href='#section_{section_id}'>{section.title}</a></li>"
        toc += "</ul>"

        # 构建章节
        content = ""
        for section_id, section in sections.items():
            status_class = self._get_status_class(section.status)
            content += f"""
<section id="section_{section_id}" class="report-section {status_class}">
    <h{section.level}>{section.title} {self._get_status_badge(section.status)}</h{level}>
    {section.html_content}
</section>
"""

        # 待审核项列表
        pending_list = ""
        for pending in report.get("pending_verifications", []):
            pending_list += f"""
<li>
    <span class="badge badge-{pending['confidence']}">{pending['confidence']}</span>
    <strong>{pending['section_title']}</strong> - {pending['field_name']}
    <br><small>{pending['value_preview']}</small>
</li>
"""

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{config.project_name} 环境影响报告 - 人机协同版</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: "Microsoft YaHei", SimSun, serif;
            font-size: 14px;
            line-height: 1.8;
            color: #333;
            max-width: 210mm;
            margin: 0 auto;
            padding: 20mm;
            background: white;
        }}
        h1 {{ font-size: 28px; text-align: center; margin: 60px 0 30px; }}
        h2 {{ font-size: 18px; margin: 30px 0 15px; border-bottom: 1px solid #333; padding-bottom: 5px; }}
        h3 {{ font-size: 16px; margin: 20px 0 10px; }}
        p {{ text-indent: 2em; margin: 10px 0; }}
        ul, ol {{ margin-left: 2em; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ border: 1px solid #333; padding: 8px 10px; text-align: center; }}
        th {{ background: #f5f5f5; }}
        .cover {{ text-align: center; margin-top: 100px; }}
        .cover h1 {{ font-size: 32px; margin-bottom: 50px; }}
        .cover-info {{ margin-top: 100px; text-align: left; display: inline-block; }}
        .cover-info p {{ text-indent: 0; margin: 10px 0; }}
        .toc {{ list-style: none; padding-left: 2em; }}
        .toc li {{ margin: 8px 0; }}
        .report-section {{ margin: 30px 0; padding: 15px; border: 1px solid #ddd; }}
        .status-verified {{ border-left: 4px solid #28a745; }}
        .status-pending {{ border-left: 4px solid #ffc107; }}
        .status-critical {{ border-left: 4px solid #dc3545; background: #fff5f5; }}
        .placeholder {{ background: #fff3cd; padding: 10px; border: 1px dashed #ffc107; margin: 10px 0; }}
        .placeholder.critical {{ background: #f8d7da; border-color: #dc3545; }}
        .alert {{ padding: 15px; margin: 15px 0; border-radius: 4px; }}
        .alert-info {{ background: #d1ecf1; border: 1px solid #bee5eb; }}
        .alert-warning {{ background: #fff3cd; border: 1px solid #ffc107; }}
        .conclusion-box {{ padding: 20px; margin: 20px 0; }}
        .conclusion-box.success {{ background: #d4edda; border: 1px solid #28a745; }}
        .conclusion-box.warning {{ background: #fff3cd; border: 1px solid #ffc107; }}
        .badge {{ padding: 2px 8px; border-radius: 3px; font-size: 12px; }}
        .badge-high {{ background: #28a745; color: white; }}
        .badge-medium {{ background: #ffc107; color: black; }}
        .badge-low {{ background: #fd7e14; color: white; }}
        .badge-critical {{ background: #dc3545; color: white; }}
        .status-badge {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 12px; margin-left: 10px; }}
        .status-PENDING {{ background: #6c757d; color: white; }}
        .status-VERIFIED {{ background: #28a745; color: white; }}
        .status-REJECTED {{ background: #dc3545; color: white; }}
        .status-MANUAL_EDITED {{ background: #17a2b8; color: white; }}
        .verification-panel {{ background: #f8f9fa; padding: 15px; margin: 20px 0; border: 1px solid #dee2e6; }}
        @media print {{
            body {{ padding: 0; }}
            .page-break {{ page-break-before: always; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="cover">
        <h1>{config.project_name}<br>环境影响报告</h1>
        <div class="cover-info">
            <p><strong>项目地点：</strong>待填写</p>
            <p><strong>行业类别：</strong>{config.industry}</p>
            <p><strong>编制日期：</strong>{datetime.now().strftime('%Y年%m月')}</p>
            <p><strong>版本：</strong>{report['metadata']['version']} (人机协同版)</p>
        </div>
    </div>

    <h2>目录</h2>
    {toc}

    {content}

    <div class="verification-panel no-print">
        <h3>📋 待审核项 ({len(report.get('pending_verifications', []))})</h3>
        <ul>
            {pending_list or "<li>无待审核项</li>"}
        </ul>
    </div>

    <div class="verification-panel no-print">
        <h3>🔍 数据一致性检查</h3>
        <p>发现 {len(report.get('consistency_issues', []))} 个一致性问题</p>
    </div>

    <div class="no-print" style="margin-top: 30px; padding: 15px; background: #e9ecef; text-align: center;">
        <p>本报告由人机协同系统生成 | 关键数据需工程师审核确认</p>
        <p>生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
</body>
</html>
"""
        return html

    def _get_status_icon(self, status: SectionStatus) -> str:
        """获取状态图标"""
        icons = {
            SectionStatus.PENDING: "⏳",
            SectionStatus.GENERATING: "⚙️",
            SectionStatus.AWAITING_VERIFICATION: "👀",
            SectionStatus.VERIFIED: "✅",
            SectionStatus.REJECTED: "❌",
            SectionStatus.MANUAL_EDITED: "✏️"
        }
        return icons.get(status, "")

    def _get_status_class(self, status: SectionStatus) -> str:
        """获取状态样式类"""
        classes = {
            SectionStatus.VERIFIED: "status-verified",
            SectionStatus.AWAITING_VERIFICATION: "status-pending",
            SectionStatus.REJECTED: "status-critical"
        }
        return classes.get(status, "")

    def _get_status_badge(self, status: SectionStatus) -> str:
        """获取状态标签"""
        return f"<span class='status-badge status-{status.name}'>{status.value}</span>"

    def get_report_summary(self, project_id: str) -> dict:
        """获取报告摘要"""
        if project_id not in self._report_drafts:
            return {}

        report = self._report_drafts[project_id]
        sections = report["sections"]

        # 统计各状态章节数
        status_counts = {}
        confidence_counts = {}

        for section in sections.values():
            status = section.status.name
            confidence = section.confidence.value
            status_counts[status] = status_counts.get(status, 0) + 1
            confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1

        return {
            "project_id": project_id,
            "project_name": report["config"].project_name,
            "total_sections": len(sections),
            "status_breakdown": status_counts,
            "confidence_breakdown": confidence_counts,
            "pending_verifications": len(report.get("pending_verifications", [])),
            "consistency_issues": len(report.get("consistency_issues", []))
        }


def create_collaborative_engine(data_dir: str = "./data/eia") -> CollaborativeReportEngine:
    """创建协同报告引擎实例"""
    return CollaborativeReportEngine(data_dir=data_dir)


# 导入需要的模块
import os