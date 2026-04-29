"""
环评报告完整性审计器
====================

AI驱动的缺失信息检测，智能分级提示，上下文感知的补充建议。

Author: Hermes Desktop EIA System
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime


class MissingLevel(str, Enum):
    """缺失级别"""
    FATAL = "fatal"           # 🔴 致命缺失（必须补充）
    IMPORTANT = "important"   # 🟡 重要提示（强烈建议）
    SUGGESTION = "suggestion" # 🔵 优化建议（可选）
    FORMAT = "format"        # 🟢 格式提醒（自动修正）


class MissingCategory(str, Enum):
    """缺失类别"""
    BASIC_INFO = "basic_info"           # 基本信息
    SOURCE_PARAMS = "source_params"     # 污染源参数
    MODEL_INPUT = "model_input"         # 模型输入
    MONITORING_DATA = "monitoring_data" # 监测数据
    REFERENCE_STANDARD = "reference_standard"  # 引用标准
    CHAPTER_CONTENT = "chapter_content" # 章节内容
    ATTACHMENT = "attachment"          # 附件材料
    COMPLIANCE = "compliance"          # 合规性


@dataclass
class MissingItem:
    """缺失项"""
    id: str
    level: MissingLevel
    category: MissingCategory
    name: str                           # 缺失项名称
    description: str                    # 描述
    location: str = ""                  # 位置（如"第3章 3.2节"）
    possible_reasons: List[str] = field(default_factory=list)  # 可能原因
    suggestions: List['Suggestion'] = field(default_factory=list)  # 补充建议
    auto_fixable: bool = False         # 是否可自动修复
    auto_fix_method: str = ""          # 自动修复方法
    depends_on: List[str] = field(default_factory=list)  # 依赖的其他项
    priority: int = 0                  # 优先级（数字越小越高）


@dataclass
class Suggestion:
    """建议"""
    action: str                         # 动作名称
    label: str                          # 显示标签
    description: str                    # 描述
    icon: str = ""                      # 图标
    callback: Optional[str] = None      # 回调函数名


@dataclass
class AuditResult:
    """审计结果"""
    project_id: str
    audit_time: datetime
    total_items: int = 0
    fatal_count: int = 0
    important_count: int = 0
    suggestion_count: int = 0
    format_count: int = 0
    items: List[MissingItem] = field(default_factory=list)
    completeness_score: float = 0.0    # 完整度评分 0-100
    risk_level: str = "LOW"            # LOW/MEDIUM/HIGH/CRITICAL
    can_submit: bool = False           # 是否可以提交
    blocking_items: List[str] = field(default_factory=list)  # 阻塞性项


class ReportCompletenessAuditor:
    """
    报告完整性审计器

    功能：
    1. 必填字段检查
    2. 模型输入完整性检查
    3. 引用完整性检查
    4. 行业特定检查
    5. 上下文感知建议
    """

    def __init__(self):
        # 必填字段模板
        self.required_fields = {
            "basic_info": [
                ("project_name", "项目名称"),
                ("location", "项目地址"),
                ("industry_type", "行业类型"),
                ("construction_scale", "建设规模"),
                ("investor", "建设单位"),
                ("contact_person", "联系人"),
                ("contact_phone", "联系电话"),
            ],
            "engineering": [
                ("main_products", "主要产品"),
                ("production_scale", "生产规模"),
                ("process_description", "工艺描述"),
                ("equipment_list", "设备清单"),
                ("raw_materials", "原辅材料"),
            ],
            "pollution_sources": [
                ("air_sources", "废气排放源"),
                ("water_sources", "废水排放源"),
                ("noise_sources", "噪声源"),
                ("solid_waste", "固体废物"),
            ],
            "environmental": [
                ("meteo_data", "气象数据"),
                ("hydro_data", "水文地质"),
                ("ambient_air", "环境空气现状"),
                ("surface_water", "地表水现状"),
                ("groundwater", "地下水现状"),
                ("soil", "土壤现状"),
                ("acoustic", "声环境现状"),
            ]
        }

        # 行业特定必填章节
        self.industry_chapters = {
            "化工": ["risk_assessment", "leaching_assessment"],
            "石化": ["risk_assessment", "fire_assessment"],
            "制药": ["odor_assessment", "bio_assessment"],
            "电子": ["soil_assessment", "groundwater_assessment"],
            "电镀": ["heavy_metal_assessment", "soil_assessment"],
            "印染": ["water_balance", "dyeing_assessment"],
            "造纸": ["water_discharge", "sludge_assessment"],
            "焦化": ["vocs_assessment", " Coke_oven_emissions"],
            "钢铁": ["PM25_assessment", "greenhouse_gas"],
            "水泥": ["PM_assessment", "Dust_control"],
        }

        # 标准引用模板
        self.standard_references = {
            "air": [
                ("GB 16297", "大气污染物综合排放标准"),
                ("GB 3095", "环境空气质量标准"),
                ("HJ 2.2", "环境影响评价技术导则 大气环境"),
            ],
            "water": [
                ("GB 8978", "污水综合排放标准"),
                ("GB/T 14848", "地下水质量标准"),
                ("HJ 2.3", "环境影响评价技术导则 地表水环境"),
            ],
            "noise": [
                ("GB 12348", "工业企业厂界环境噪声排放标准"),
                ("GB 3096", "声环境质量标准"),
                ("HJ 2.4", "环境影响评价技术导则 声环境"),
            ],
            "solid": [
                ("GB 18599", "一般工业固体废物贮存、处置场污染控制标准"),
                ("GB 18597", "危险废物贮存污染控制标准"),
            ]
        }

        # 缺失项ID生成器
        self._item_counter = 0

    def _generate_id(self) -> str:
        """生成唯一ID"""
        self._item_counter += 1
        return f"missing_{self._item_counter:04d}"

    def audit_report(self, report_data: Dict, project_context: Dict) -> AuditResult:
        """
        审计报告完整性

        Args:
            report_data: 报告数据（章节内容、字段值等）
            project_context: 项目上下文（行业、规模、地区等）
        """
        items: List[MissingItem] = []

        # 1. 基本信息检查
        items.extend(self._check_basic_info(report_data))

        # 2. 污染源参数检查
        items.extend(self._check_pollution_sources(report_data, project_context))

        # 3. 模型输入检查
        items.extend(self._check_model_inputs(report_data))

        # 4. 监测数据检查
        items.extend(self._check_monitoring_data(report_data, project_context))

        # 5. 引用标准检查
        items.extend(self._check_standard_references(report_data))

        # 6. 章节完整性检查
        items.extend(self._check_chapter_completeness(report_data, project_context))

        # 7. 附件材料检查
        items.extend(self._check_attachments(report_data))

        # 8. 合规性预检查
        items.extend(self._check_compliance_prescan(report_data, project_context))

        # 排序并生成结果
        items.sort(key=lambda x: (self._level_priority(x.level), x.priority))

        return self._build_audit_result(report_data.get("project_id", ""), items)

    def _level_priority(self, level: MissingLevel) -> int:
        """获取级别优先级"""
        priorities = {
            MissingLevel.FATAL: 0,
            MissingLevel.IMPORTANT: 1,
            MissingLevel.SUGGESTION: 2,
            MissingLevel.FORMAT: 3
        }
        return priorities.get(level, 99)

    def _build_audit_result(self, project_id: str, items: List[MissingItem]) -> AuditResult:
        """构建审计结果"""
        fatal_items = [i for i in items if i.level == MissingLevel.FATAL]
        important_items = [i for i in items if i.level == MissingLevel.IMPORTANT]
        suggestion_items = [i for i in items if i.level == MissingLevel.SUGGESTION]
        format_items = [i for i in items if i.level == MissingLevel.FORMAT]

        # 计算完整度评分
        total_checks = sum(len(v) for v in self.required_fields.values())
        missing_count = len(items)
        completeness_score = max(0, 100 - (missing_count / max(total_checks, 1) * 100))

        # 判断风险等级
        if fatal_items:
            risk_level = "CRITICAL"
            can_submit = False
        elif important_items:
            risk_level = "HIGH"
            can_submit = False
        elif suggestion_items:
            risk_level = "MEDIUM"
            can_submit = True
        else:
            risk_level = "LOW"
            can_submit = True

        return AuditResult(
            project_id=project_id,
            audit_time=datetime.now(),
            total_items=len(items),
            fatal_count=len(fatal_items),
            important_count=len(important_items),
            suggestion_count=len(suggestion_items),
            format_count=len(format_items),
            items=items,
            completeness_score=completeness_score,
            risk_level=risk_level,
            can_submit=can_submit,
            blocking_items=[i.id for i in fatal_items + important_items]
        )

    def _check_basic_info(self, report_data: Dict) -> List[MissingItem]:
        """检查基本信息"""
        items = []
        basic_info = report_data.get("basic_info", {})

        for field_key, field_name in self.required_fields["basic_info"]:
            if not basic_info.get(field_key):
                items.append(MissingItem(
                    id=self._generate_id(),
                    level=MissingLevel.FATAL,
                    category=MissingCategory.BASIC_INFO,
                    name=field_name,
                    description=f"必填字段「{field_name}」未提供",
                    location="报告封面/基本信息表",
                    possible_reasons=[
                        "项目基本信息未填写",
                        "从文档中未提取到该信息",
                        "需要补充项目立项文件"
                    ],
                    suggestions=[
                        Suggestion(
                            action="fill_field",
                            label="直接填写",
                            description=f"在下方表单中填写「{field_name}」",
                            icon="📝"
                        ),
                        Suggestion(
                            action="upload_document",
                            label="上传文档自动提取",
                            description="上传项目批复、可研报告等，系统自动提取",
                            icon="📄"
                        ),
                        Suggestion(
                            action="use_template",
                            label="使用模板填充",
                            description="如果类似项目有过往资料，可一键继承",
                            icon="📋"
                        )
                    ],
                    priority=1
                ))

        return items

    def _check_pollution_sources(self, report_data: Dict, project_context: Dict) -> List[MissingItem]:
        """检查污染源参数"""
        items = []
        sources = report_data.get("pollution_sources", {})

        industry = project_context.get("industry_type", "")

        for source_type in ["air", "water", "noise", "solid"]:
            source_data = sources.get(source_type, {})
            if not source_data or not source_data.get("sources"):
                type_names = {
                    "air": "废气排放源",
                    "water": "废水排放源",
                    "noise": "噪声源",
                    "solid": "固体废物"
                }
                items.append(MissingItem(
                    id=self._generate_id(),
                    level=MissingLevel.IMPORTANT,
                    category=MissingCategory.SOURCE_PARAMS,
                    name=f"{type_names.get(source_type, source_type)}数据",
                    description=f"未提供{source_type}污染源参数",
                    location="工程分析章节/污染源列表",
                    possible_reasons=[
                        "工程分析中未识别到污染源",
                        "污染源参数未量化",
                        "需要设备清单和工艺参数"
                    ],
                    suggestions=[
                        Suggestion(
                            action="draw_source",
                            label="在绘图表中绘制",
                            description="在污染源分布图上绘制并标注参数",
                            icon="🎨"
                        ),
                        Suggestion(
                            action="import_params",
                            label="导入参数表",
                            description="上传设备参数表或工艺文件",
                            icon="📊"
                        ),
                        Suggestion(
                            action="use_industry_default",
                            label="使用行业默认值",
                            description=f"基于{industry}行业的典型源强填充",
                            icon="⚡"
                        )
                    ],
                    priority=2
                ))

        return items

    def _check_model_inputs(self, report_data: Dict) -> List[MissingItem]:
        """检查模型输入"""
        items = []

        # 大气模型检查
        if report_data.get("has_air_model"):
            meteo_data = report_data.get("meteo_data")
            if not meteo_data:
                items.append(MissingItem(
                    id=self._generate_id(),
                    level=MissingLevel.FATAL,
                    category=MissingCategory.MODEL_INPUT,
                    name="大气预测气象数据",
                    description="大气预测模型需要气象数据，但未提供",
                    location="环境影响预测章节/大气环境",
                    possible_reasons=[
                        "气象观测数据未获取",
                        "气象数据格式不符合要求",
                        "可以使用典型气象年数据替代"
                    ],
                    suggestions=[
                        Suggestion(
                            action="provide_meteo",
                            label="提供气象数据",
                            description="上传气象观测站数据（至少一年）",
                            icon="🌤️"
                        ),
                        Suggestion(
                            action="use_typical_year",
                            label="使用典型气象年",
                            description="使用项目所在地的典型气象年数据",
                            icon="📅"
                        ),
                        Suggestion(
                            action="generate_synthetic",
                            label="生成合成气象数据",
                            description="基于地理信息生成代表性气象参数",
                            icon="🔧"
                        )
                    ],
                    priority=1
                ))

            # 地形数据检查
            if not report_data.get("terrain_data"):
                items.append(MissingItem(
                    id=self._generate_id(),
                    level=MissingLevel.IMPORTANT,
                    category=MissingCategory.MODEL_INPUT,
                    name="地形数据",
                    description="大气预测模型需要地形数据",
                    location="大气环境影响预测",
                    possible_reasons=[
                        "未获取项目所在地地形图",
                        "地形数据精度不足"
                    ],
                    suggestions=[
                        Suggestion(
                            action="provide_terrain",
                            label="提供地形图",
                            description="上传项目区域的地形图文件",
                            icon="🗺️"
                        ),
                        Suggestion(
                            action="use_srtm",
                            label="使用SRTM高程数据",
                            description="自动从公开地理数据获取",
                            icon="🌍"
                        )
                    ],
                    priority=3
                ))

        # 噪声模型检查
        if report_data.get("has_noise_model"):
            if not report_data.get("noise_sources_detail"):
                items.append(MissingItem(
                    id=self._generate_id(),
                    level=MissingLevel.IMPORTANT,
                    category=MissingCategory.MODEL_INPUT,
                    name="噪声源详细信息",
                    description="噪声预测需要各噪声源的详细参数",
                    location="声环境影响预测",
                    suggestions=[
                        Suggestion(
                            action="draw_noise_sources",
                            label="在总图上标注噪声源",
                            description="绘制厂区总图，标注设备位置和源强",
                            icon="🔊"
                        )
                    ],
                    priority=3
                ))

        return items

    def _check_monitoring_data(self, report_data: Dict, project_context: Dict) -> List[MissingItem]:
        """检查监测数据"""
        items = []
        industry = project_context.get("industry_type", "")
        location = project_context.get("location", "")

        # 环境空气监测
        if not report_data.get("ambient_air_data"):
            items.append(MissingItem(
                id=self._generate_id(),
                level=MissingLevel.IMPORTANT,
                category=MissingCategory.MONITORING_DATA,
                name="环境空气现状监测数据",
                description="缺少环境空气现状监测数据",
                location="环境现状章节/环境空气",
                possible_reasons=[
                    "监测工作尚未完成",
                    "可以使用已有监测数据或引用资料",
                    "部分地区可使用自动监测站数据"
                ],
                suggestions=[
                    Suggestion(
                        action="provide_monitoring",
                        label="提供监测报告",
                        description="上传最近一年的环境空气监测数据",
                        icon="📊"
                    ),
                    Suggestion(
                        action="use_station_data",
                        label="引用监测站数据",
                        description="引用附近监测站的公开数据",
                        icon="🏢"
                    ),
                    Suggestion(
                        action="skip_if_applicable",
                        label="说明豁免原因",
                        description="如果满足豁免条件，生成豁免说明",
                        icon="📝"
                    )
                ],
                priority=2
            ))

        # 行业特定监测
        specific_monitors = {
            "化工": ["risk_monitor", "toxic_gases"],
            "石化": ["flammable_gases", "vocs"],
            "电镀": ["heavy_metals"],
            "印染": ["colority", "COD"],
            "焦化": ["benzene_series", "vocs"],
        }

        if industry in specific_monitors:
            for monitor_type in specific_monitors[industry]:
                if not report_data.get(monitor_type):
                    items.append(MissingItem(
                        id=self._generate_id(),
                        level=MissingLevel.IMPORTANT,
                        category=MissingCategory.MONITORING_DATA,
                        name=f"{industry}特征污染物监测",
                        description=f"{industry}项目通常需要{monitor_type}相关监测",
                        location="环境现状章节",
                        suggestions=[
                            Suggestion(
                                action="add_monitoring",
                                label="添加监测项目",
                                description=f"补充{monitor_type}的监测方案",
                                icon="➕"
                            )
                        ],
                        priority=4
                    ))

        return items

    def _check_standard_references(self, report_data: Dict) -> List[MissingItem]:
        """检查标准引用"""
        items = []

        referenced_standards = report_data.get("referenced_standards", [])
        referenced_keys = [s.get("code") for s in referenced_standards]

        # 检查大气标准引用
        has_air_standard = any("GB 16297" in k or "GB 3095" in k
                               for k in referenced_keys if k)
        if report_data.get("has_air_emission") and not has_air_standard:
            items.append(MissingItem(
                id=self._generate_id(),
                level=MissingLevel.IMPORTANT,
                category=MissingCategory.REFERENCE_STANDARD,
                name="大气排放标准引用",
                description="报告引用了大气排放源但未标注执行标准",
                location="工程分析章节/污染物排放",
                possible_reasons=[
                    "标准选择不正确",
                    "地方标准未单独引用"
                ],
                suggestions=[
                    Suggestion(
                        action="select_standard",
                        label="选择执行标准",
                        description="从标准库中选择适用的大气排放标准",
                        icon="📖"
                    ),
                    Suggestion(
                        action="check_local_standard",
                        label="核查地方标准",
                        description="部分地区有更严格的地方排放标准",
                        icon="🏛️"
                    )
                ],
                auto_fixable=False,
                priority=3
            ))

        # 检查标准条款完整性
        for standard in referenced_standards:
            if standard.get("code") and not standard.get("specific_clauses"):
                items.append(MissingItem(
                    id=self._generate_id(),
                    level=MissingLevel.SUGGESTION,
                    category=MissingCategory.REFERENCE_STANDARD,
                    name=f"标准{standard.get('code')}条款",
                    description="引用了标准但未提供具体条款内容",
                    location=f"依据章节/{standard.get('code')}",
                    suggestions=[
                        Suggestion(
                            action="fill_clauses",
                            label="补充具体条款",
                            description="填写引用的具体标准条款号和内容",
                            icon="📝"
                        )
                    ],
                    auto_fixable=False,
                    priority=5
                ))

        return items

    def _check_chapter_completeness(self, report_data: Dict, project_context: Dict) -> List[MissingItem]:
        """检查章节完整性"""
        items = []
        industry = project_context.get("industry_type", "")
        chapters = report_data.get("chapters", {})

        # 检查必需章节
        required_chapters = ["1_total", "2_engineering", "3_environmental_status",
                            "4_impact_prediction", "5_protection_measures", "6_conclusion"]

        for chapter_key in required_chapters:
            if chapter_key not in chapters or not chapters[chapter_key].get("content"):
                chapter_names = {
                    "1_total": "第一章 总论",
                    "2_engineering": "第二章 工程分析",
                    "3_environmental_status": "第三章 环境现状",
                    "4_impact_prediction": "第四章 环境影响预测",
                    "5_protection_measures": "第五章 环境保护措施",
                    "6_conclusion": "第六章 结论与建议"
                }
                items.append(MissingItem(
                    id=self._generate_id(),
                    level=MissingLevel.FATAL,
                    category=MissingCategory.CHAPTER_CONTENT,
                    name=f"{chapter_names.get(chapter_key, chapter_key)}缺失",
                    description="报告缺少该章节内容",
                    location=chapter_names.get(chapter_key, chapter_key),
                    suggestions=[
                        Suggestion(
                            action="generate_chapter",
                            label="AI生成章节",
                            description="基于已有数据AI生成章节内容",
                            icon="🤖"
                        )
                    ],
                    priority=1
                ))

        # 行业特定章节检查
        if industry in self.industry_chapters:
            for specific_chapter in self.industry_chapters[industry]:
                if specific_chapter not in chapters:
                    items.append(MissingItem(
                        id=self._generate_id(),
                        level=MissingLevel.IMPORTANT,
                        category=MissingCategory.CHAPTER_CONTENT,
                        name=f"{industry}特定章节：{specific_chapter}",
                        description=f"{industry}项目通常需要{specific_chapter}章节",
                        location="相关章节",
                        suggestions=[
                            Suggestion(
                                action="add_chapter",
                                label="添加章节",
                                description=f"从章节模板库中添加{specific_chapter}",
                                icon="➕"
                            )
                        ],
                        priority=3
                    ))

        return items

    def _check_attachments(self, report_data: Dict) -> List[MissingItem]:
        """检查附件材料"""
        items = []

        attachments = report_data.get("attachments", [])

        # 必需附件检查
        required_attachments = [
            ("location_map", "项目地理位置图"),
            ("plane_layout", "厂区平面布置图"),
            ("sensitive_distribution", "敏感目标分布图"),
        ]

        for attach_key, attach_name in required_attachments:
            if attach_key not in attachments:
                items.append(MissingItem(
                    id=self._generate_id(),
                    level=MissingLevel.FATAL,
                    category=MissingCategory.ATTACHMENT,
                    name=attach_name,
                    description=f"缺少必需附件：{attach_name}",
                    location="报告附件",
                    suggestions=[
                        Suggestion(
                            action="upload_attachment",
                            label="上传附件",
                            description=f"上传{attach_name}",
                            icon="📎"
                        ),
                        Suggestion(
                            action="generate_from_drawing",
                            label="从绘图表导出",
                            description="在绘图表中绘制后自动导出",
                            icon="🎨"
                        )
                    ],
                    priority=1
                ))

        # 计算附件检查
        if report_data.get("has_air_model") and "air_calculation" not in attachments:
            items.append(MissingItem(
                id=self._generate_id(),
                level=MissingLevel.IMPORTANT,
                category=MissingCategory.ATTACHMENT,
                name="大气环境影响计算附件",
                description="大气预测模型计算书",
                location="报告附件",
                suggestions=[
                    Suggestion(
                        action="generate_attachment",
                        label="生成计算附件",
                        description="基于模型计算结果生成计算书",
                        icon="📄"
                    )
                ],
                priority=2
            ))

        return items

    def _check_compliance_prescan(self, report_data: Dict, project_context: Dict) -> List[MissingItem]:
        """合规性预扫描"""
        items = []
        industry = project_context.get("industry_type", "")

        # 检查是否在环境敏感区
        if project_context.get("is_sensitive_area"):
            if not report_data.get("sensitive_assessment"):
                items.append(MissingItem(
                    id=self._generate_id(),
                    level=MissingLevel.FATAL,
                    category=MissingCategory.COMPLIANCE,
                    name="环境敏感区专篇",
                    description="项目位于环境敏感区域，需要专篇说明",
                    location="报告正文/环境敏感区分析",
                    suggestions=[
                        Suggestion(
                            action="add_sensitive_section",
                            label="添加敏感区专篇",
                            description="AI辅助生成敏感区影响分析专篇",
                            icon="🛡️"
                        )
                    ],
                    priority=1
                ))

        # 总量控制检查
        if report_data.get("has_pollution_emission"):
            if not report_data.get("total_amount_control"):
                items.append(MissingItem(
                    id=self._generate_id(),
                    level=MissingLevel.IMPORTANT,
                    category=MissingCategory.COMPLIANCE,
                    name="污染物总量控制",
                    description="需要明确主要污染物排放总量",
                    location="结论与建议章节",
                    suggestions=[
                        Suggestion(
                            action="calculate_total",
                            label="计算总量",
                            description="基于源强和排放参数计算污染物总量",
                            icon="🧮"
                        )
                    ],
                    priority=2
                ))

        return items

    def generate_audit_report(self, result: AuditResult) -> str:
        """生成审计报告（文本格式）"""
        lines = []
        lines.append("=" * 60)
        lines.append("📋 环评报告完整性审计报告")
        lines.append("=" * 60)
        lines.append(f"审计时间: {result.audit_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"项目ID: {result.project_id}")
        lines.append("")
        lines.append(f"📊 完整度评分: {result.completeness_score:.1f}%")
        lines.append(f"⚠️ 风险等级: {result.risk_level}")
        lines.append(f"✅ 是否可提交: {'是' if result.can_submit else '否'}")
        lines.append("")

        lines.append("-" * 60)
        lines.append(f"🔴 致命缺失: {result.fatal_count} 项")
        lines.append(f"🟡 重要提示: {result.important_count} 项")
        lines.append(f"🔵 优化建议: {result.suggestion_count} 项")
        lines.append(f"🟢 格式提醒: {result.format_count} 项")
        lines.append("-" * 60)

        # 按级别分组显示
        for level in [MissingLevel.FATAL, MissingLevel.IMPORTANT,
                     MissingLevel.SUGGESTION, MissingLevel.FORMAT]:
            level_items = [i for i in result.items if i.level == level]
            if not level_items:
                continue

            level_names = {
                MissingLevel.FATAL: "🔴 致命缺失",
                MissingLevel.IMPORTANT: "🟡 重要提示",
                MissingLevel.SUGGESTION: "🔵 优化建议",
                MissingLevel.FORMAT: "🟢 格式提醒"
            }

            lines.append("")
            lines.append(f"{level_names.get(level, level.value)} ({len(level_items)}项)")
            lines.append("-" * 40)

            for item in level_items:
                lines.append(f"  • {item.name}")
                lines.append(f"    位置: {item.location}")
                lines.append(f"    说明: {item.description}")
                if item.suggestions:
                    lines.append(f"    建议:")
                    for sug in item.suggestions[:2]:  # 最多显示2个建议
                        lines.append(f"      ▸ {sug.icon} {sug.label}: {sug.description}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)


# 全局审计器实例
_auditor: Optional[ReportCompletenessAuditor] = None


def get_auditor() -> ReportCompletenessAuditor:
    """获取审计器实例"""
    global _auditor
    if _auditor is None:
        _auditor = ReportCompletenessAuditor()
    return _auditor


def audit_report_completeness(report_data: Dict, project_context: Dict) -> AuditResult:
    """便捷函数：审计报告完整性"""
    auditor = get_auditor()
    return auditor.audit_report(report_data, project_context)
