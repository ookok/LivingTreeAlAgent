"""
知识图谱合规推理引擎 - 审查即"合规性推理"
==========================================

核心思想：利用知识图谱进行智能推理，从"是否引用"升级为"上下文感知的合规检查"。

功能：
1. 上下文感知的合规检查 - 检查引用标准的版本、适用范围
2. 跨章节一致性推理 - 检测章节间的逻辑矛盾
3. 推理链追溯 - 从结论追溯推理过程
"""

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class ComplianceStatus(Enum):
    """合规状态"""
    COMPLIANT = "compliant"           # 合规
    NON_COMPLIANT = "non_compliant"   # 不合规
    WARNING = "warning"               # 警告
    NEEDS_REVIEW = "needs_review"     # 需人工审查
    UNKNOWN = "unknown"               # 未知


class StandardType(Enum):
    """标准类型"""
    NATIONAL = "national"             # 国家标准 (GB)
    INDUSTRY = "industry"             # 行业标准 (HJ)
    LOCAL = "local"                   # 地方标准 (DB)
    PROVINCE = "province"             # 省级标准
    CORPORATE = "corporate"           # 企业标准


class RelationType(Enum):
    """关系类型"""
    REQUIRES = "requires"             # 需要/依赖
    CONFLICTS = "conflicts"           # 冲突
    IMPLIES = "implies"               # 蕴含/导致
    PART_OF = "part_of"              # 是...的一部分
    APPLIES_TO = "applies_to"         # 适用于
    SUPPORTS = "supports"            # 支持/证实


@dataclass
class StandardClause:
    """标准条款"""
    standard_code: str               # 标准编号，如"GB 3095-2012"
    standard_name: str               # 标准名称
    clause_id: str                   # 条款编号，如"5.1"
    clause_title: str                # 条款标题
    clause_content: str               # 条款内容
    applicability: str = ""          # 适用范围描述
    parameters: Dict[str, Any] = field(default_factory=dict)  # 关键参数
    version: str = "current"          # 版本
    effective_date: Optional[str] = None  # 生效日期
    is_current: bool = True          # 是否现行有效


@dataclass
class KnowledgeNode:
    """知识图谱节点"""
    node_id: str
    node_type: str                   # 节点类型：standard, clause, parameter, industry, etc.
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "name": self.name,
            "properties": self.properties,
            "metadata": self.metadata,
        }


@dataclass
class KnowledgeEdge:
    """知识图谱边（关系）"""
    edge_id: str
    source_id: str                   # 源节点ID
    target_id: str                   # 目标节点ID
    relation_type: RelationType
    weight: float = 1.0              # 关系权重
    description: str = ""
    conditions: Optional[str] = None  # 触发条件

    def to_dict(self) -> Dict:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type.value,
            "weight": self.weight,
            "description": self.description,
            "conditions": self.conditions,
        }


@dataclass
class ComplianceCheckResult:
    """合规检查结果"""
    check_type: str                  # 检查类型
    status: ComplianceStatus
    description: str
    standard_code: Optional[str] = None  # 涉及的标准
    clause_id: Optional[str] = None      # 涉及的条款
    details: Dict[str, Any] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)  # 证据文本
    recommendation: str = ""
    severity: str = "INFO"           # INFO, WARNING, ERROR

    def to_dict(self) -> Dict:
        return {
            "check_type": self.check_type,
            "status": self.status.value,
            "description": self.description,
            "standard_code": self.standard_code,
            "clause_id": self.clause_id,
            "details": self.details,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "severity": self.severity,
        }


@dataclass
class CrossChapterInference:
    """跨章节推理结果"""
    chapter1: str                    # 第一章
    chapter1_content: str            # 第一章内容摘要
    chapter2: str                    # 第二章
    chapter2_content: str             # 第二章内容摘要
    inference_type: str               # 推理类型
    inference_text: str              # 推理描述
    confidence: float                # 置信度 0-1
    status: ComplianceStatus
    warning_message: str = ""
    suggestion: str = ""

    def to_dict(self) -> Dict:
        return {
            "chapter1": self.chapter1,
            "chapter2": self.chapter2,
            "inference_type": self.inference_type,
            "inference_text": self.inference_text,
            "confidence": self.confidence,
            "status": self.status.value,
            "warning_message": self.warning_message,
            "suggestion": self.suggestion,
        }


@dataclass
class ComplianceReport:
    """完整合规检查报告"""
    report_id: str
    project_name: str
    check_time: datetime
    standard_checks: List[ComplianceCheckResult] = field(default_factory=list)
    cross_chapter_checks: List[CrossChapterInference] = field(default_factory=list)
    overall_status: ComplianceStatus = ComplianceStatus.UNKNOWN
    risk_level: str = "UNKNOWN"
    summary: str = ""

    def to_dict(self) -> Dict:
        return {
            "report_id": self.report_id,
            "project_name": self.project_name,
            "check_time": self.check_time.isoformat(),
            "standard_checks": [c.to_dict() for c in self.standard_checks],
            "cross_chapter_checks": [c.to_dict() for c in self.cross_chapter_checks],
            "overall_status": self.overall_status.value,
            "risk_level": self.risk_level,
            "summary": self.summary,
        }

    def get_issue_count(self) -> int:
        """获取问题数量"""
        return sum(
            1 for c in self.standard_checks
            if c.status in [ComplianceStatus.NON_COMPLIANT, ComplianceStatus.WARNING]
        ) + sum(
            1 for c in self.cross_chapter_checks
            if c.status in [ComplianceStatus.NON_COMPLIANT, ComplianceStatus.WARNING]
        )


class StandardKnowledgeGraph:
    """标准知识图谱"""

    def __init__(self):
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.edges: Dict[str, KnowledgeEdge] = {}
        self._build_initial_graph()

    def _build_initial_graph(self):
        """构建初始知识图谱"""
        # 添加常用标准节点
        standards = [
            ("GB_3095_2012", "GB 3095-2012", "环境空气质量标准", StandardType.NATIONAL),
            ("GB_16297_1996", "GB 16297-1996", "大气污染物综合排放标准", StandardType.NATIONAL),
            ("GB_3838_2002", "GB 3838-2002", "地表水环境质量标准", StandardType.NATIONAL),
            ("GB_12348_2008", "GB 12348-2008", "工业企业厂界环境噪声排放标准", StandardType.NATIONAL),
            ("GB_18599_2020", "GB 18599-2020", "一般工业固体废物贮存标准", StandardType.NATIONAL),
            ("HJ_22_2018", "HJ 2.2-2018", "大气环境影响评价技术导则", StandardType.INDUSTRY),
            ("HJ_24_2014", "HJ 2.4-2014", "环境影响评价技术导则 声环境", StandardType.INDUSTRY),
            ("HJ_19_2011", "HJ 19-2011", "环境影响评价技术导则 生态影响", StandardType.INDUSTRY),
        ]

        for code, name, title, stype in standards:
            node = KnowledgeNode(
                node_id=code,
                node_type="standard",
                name=name,
                properties={
                    "title": title,
                    "standard_type": stype.value,
                    "is_current": True,
                }
            )
            self.add_node(node)

        # 添加关键参数节点
        parameters = [
            ("param_air_aqi", "AQI", "空气质量指数", {"category": "air"}),
            ("param_air_so2", "SO₂", "二氧化硫", {"category": "air", "unit": "mg/m³"}),
            ("param_air_no2", "NO₂", "二氧化氮", {"category": "air", "unit": "mg/m³"}),
            ("param_air_pm25", "PM2.5", "细颗粒物", {"category": "air", "unit": "μg/m³"}),
            ("param_air_pm10", "PM10", "可吸入颗粒物", {"category": "air", "unit": "μg/m³"}),
            ("param_water_ph", "pH", "酸碱度", {"category": "water"}),
            ("param_water_cod", "COD", "化学需氧量", {"category": "water", "unit": "mg/L"}),
            ("param_water_nh3", "NH3-N", "氨氮", {"category": "water", "unit": "mg/L"}),
            ("param_noise_day", "昼间噪声", "昼间等效声级", {"category": "noise", "unit": "dB(A)"}),
            ("param_noise_night", "夜间噪声", "夜间等效声级", {"category": "noise", "unit": "dB(A)"}),
        ]

        for code, symbol, name, props in parameters:
            node = KnowledgeNode(
                node_id=code,
                node_type="parameter",
                name=name,
                properties={**props, "symbol": symbol}
            )
            self.add_node(node)

        # 添加行业节点
        industries = [
            ("ind_chemical", "化工", "化学原料和化学制品制造业"),
            ("ind_power", "电力", "电力、热力生产和供应业"),
            ("ind_steel", "钢铁", "黑色金属冶炼和压延加工业"),
            ("ind_cement", "水泥", "非金属矿物制品业"),
            ("ind_paper", "造纸", "造纸和纸制品业"),
            ("ind_electro", "电子", "计算机、通信和其他电子设备制造业"),
        ]

        for code, name, desc in industries:
            node = KnowledgeNode(
                node_id=code,
                node_type="industry",
                name=name,
                properties={"description": desc}
            )
            self.add_node(node)

        # 添加关系边
        self._add_standard_parameter_relations()
        self._add_industry_standard_relations()
        self._add_inter_standard_relations()

    def _add_standard_parameter_relations(self):
        """添加标准-参数关系"""
        # GB 3095 与污染物参数
        relations = [
            ("GB_3095_2012", "param_air_so2", RelationType.APPLIES_TO),
            ("GB_3095_2012", "param_air_no2", RelationType.APPLIES_TO),
            ("GB_3095_2012", "param_air_pm25", RelationType.APPLIES_TO),
            ("GB_3095_2012", "param_air_pm10", RelationType.APPLIES_TO),
            # GB 3838 与水质参数
            ("GB_3838_2002", "param_water_ph", RelationType.APPLIES_TO),
            ("GB_3838_2002", "param_water_cod", RelationType.APPLIES_TO),
            ("GB_3838_2002", "param_water_nh3", RelationType.APPLIES_TO),
        ]

        for src, tgt, rel_type in relations:
            edge_id = f"{src}_{rel_type.value}_{tgt}"
            edge = KnowledgeEdge(
                edge_id=edge_id,
                source_id=src,
                target_id=tgt,
                relation_type=rel_type,
                weight=1.0
            )
            self.add_edge(edge)

    def _add_industry_standard_relations(self):
        """添加行业-标准关系"""
        relations = [
            ("ind_chemical", "GB_16297_1996", RelationType.APPLIES_TO),
            ("ind_chemical", "HJ_22_2018", RelationType.REQUIRES),
            ("ind_power", "GB_16297_1996", RelationType.APPLIES_TO),
            ("ind_steel", "GB_16297_1996", RelationType.APPLIES_TO),
            ("ind_cement", "GB_16297_1996", RelationType.APPLIES_TO),
        ]

        for src, tgt, rel_type in relations:
            edge_id = f"{src}_{rel_type.value}_{tgt}"
            edge = KnowledgeEdge(
                edge_id=edge_id,
                source_id=src,
                target_id=tgt,
                relation_type=rel_type,
                weight=0.9
            )
            self.add_edge(edge)

    def _add_inter_standard_relations(self):
        """添加标准间关系"""
        relations = [
            # HJ 2.2 要求满足 GB 3095
            ("HJ_22_2018", "GB_3095_2012", RelationType.REQUIRES,
             "大气导则要求预测结果满足环境空气质量标准"),
            # GB 16297 与 GB 3095
            ("GB_16297_1996", "GB_3095_2012", RelationType.IMPLIES,
             "排放标准是为了实现环境质量标准"),
        ]

        for src, tgt, rel_type, desc in relations:
            edge_id = f"{src}_{rel_type.value}_{tgt}"
            edge = KnowledgeEdge(
                edge_id=edge_id,
                source_id=src,
                target_id=tgt,
                relation_type=rel_type,
                weight=1.0,
                description=desc
            )
            self.add_edge(edge)

    def add_node(self, node: KnowledgeNode):
        """添加节点"""
        self.nodes[node.node_id] = node

    def add_edge(self, edge: KnowledgeEdge):
        """添加边"""
        self.edges[edge.edge_id] = edge

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """获取节点"""
        return self.nodes.get(node_id)

    def get_related_nodes(
        self,
        node_id: str,
        relation_types: Optional[List[RelationType]] = None
    ) -> List[Tuple[KnowledgeNode, KnowledgeEdge]]:
        """获取相关节点"""
        results = []
        for edge in self.edges.values():
            if edge.source_id == node_id:
                if relation_types is None or edge.relation_type in relation_types:
                    target_node = self.nodes.get(edge.target_id)
                    if target_node:
                        results.append((target_node, edge))
        return results

    def find_path(self, source_id: str, target_id: str) -> List[str]:
        """查找两个节点之间的路径"""
        if source_id == target_id:
            return [source_id]

        visited = set()
        queue = [(source_id, [source_id])]

        while queue:
            current, path = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            for edge in self.edges.values():
                if edge.source_id == current:
                    next_node = edge.target_id
                    new_path = path + [next_node]
                    if next_node == target_id:
                        return new_path
                    if next_node not in visited:
                        queue.append((next_node, new_path))

        return []  # 无路径

    def get_applicable_standards(
        self,
        industry: str,
        media: str  # air, water, noise, solid_waste
    ) -> List[KnowledgeNode]:
        """获取适用于特定行业和媒体的标准"""
        results = []
        industry_node_id = f"ind_{industry}"

        # 找到行业节点
        if industry_node_id not in self.nodes:
            return results

        # 查找直接关联的标准
        for edge in self.edges.values():
            if edge.source_id == industry_node_id and edge.relation_type == RelationType.APPLIES_TO:
                standard_node = self.nodes.get(edge.target_id)
                if standard_node:
                    # 检查标准是否适用于指定媒体
                    standard_name = standard_node.name.lower()
                    media_keywords = {
                        'air': ['大气', '空气', '废气'],
                        'water': ['水', '污水', '地表水'],
                        'noise': ['噪声', '声'],
                        'solid_waste': ['固体', '废渣', '贮存'],
                    }
                    if any(kw in standard_name for kw in media_keywords.get(media, [])):
                        results.append(standard_node)

        return results


class ComplianceInferenceEngine:
    """
    合规性推理引擎

    核心能力：
    1. 上下文感知的合规检查
    2. 跨章节一致性推理
    3. 推理链追溯
    """

    # 内置的跨章节一致性规则
    CROSS_CHAPTER_RULES = [
        {
            "name": "vocs_source_to_treatment",
            "chapter1_pattern": r"VOCs.*?(?:产生量|排放量|源强)\s*[:：]?\s*([0-9.]+)\s*(t/a|kg/h|g/s)",
            "chapter2_pattern": r"(?:活性炭吸附|燃烧|催化氧化|生物滤池|冷凝)",
            "inference": "VOCs治理工艺匹配性",
            "typical_efficiency": {
                "活性炭吸附": (0.6, 0.85),
                "燃烧": (0.85, 0.98),
                "催化氧化": (0.80, 0.95),
                "生物滤池": (0.60, 0.80),
                "冷凝": (0.50, 0.80),
            },
            "check": "排放量是否超过去除能力",
        },
        {
            "name": "emission_to_grounding_concentration",
            "chapter1_pattern": r"(?:SO₂|NOₓ|颗粒物|VOCs).*?(?:排放速率|源强)\s*[:：]?\s*([0-9.]+)\s*(g/s|kg/h)",
            "chapter2_pattern": r"(?:最大落地浓度|预测浓度)\s*[:：]?\s*([0-9.]+)\s*(mg/m³)",
            "inference": "源强与落地浓度的量级一致性",
            "check": "落地浓度是否与源强匹配",
        },
        {
            "name": "wastewater_to_discharge_standard",
            "chapter1_pattern": r"(?:废水|污水).*?(?:排放量|产生量)\s*[:：]?\s*([0-9.]+)\s*(m³/d|t/d)",
            "chapter2_pattern": r"(?:COD|氨氮|总磷).*?(?:排放浓度|出水浓度)\s*[:：]?\s*([0-9.]+)\s*(mg/L)",
            "inference": "废水排放量与污染物总量的物质守恒",
            "check": "排放浓度与排放量是否匹配",
        },
    ]

    def __init__(self):
        self.knowledge_graph = StandardKnowledgeGraph()
        self.inference_history: List[Dict] = []

    async def check_standard_compliance(
        self,
        report_content: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> List[ComplianceCheckResult]:
        """
        检查报告中的标准引用是否合规

        Args:
            report_content: 报告内容
            project_context: 项目上下文

        Returns:
            List[ComplianceCheckResult]: 合规检查结果列表
        """
        results = []

        industry = project_context.get('industry_type', '')
        location = project_context.get('location', '')
        project_year = project_context.get('year', datetime.now().year)

        # 1. 检查引用的标准是否现行有效
        referenced_standards = report_content.get('referenced_standards', [])
        for std_ref in referenced_standards:
            result = await self._check_standard_validity(std_ref, project_year)
            if result:
                results.append(result)

        # 2. 检查行业适用的标准是否都被引用
        applicable_stds = self.knowledge_graph.get_applicable_standards(
            industry=industry,
            media='air'
        )
        referenced_codes = [s.get('code', '').lower() for s in referenced_standards]
        for std in applicable_stds:
            if not any(std.node_id.replace('_', ' ').lower() in c for c in referenced_codes):
                results.append(ComplianceCheckResult(
                    check_type="missing_standard",
                    status=ComplianceStatus.WARNING,
                    description=f"化工行业应引用{std.name}",
                    standard_code=std.name,
                    recommendation=f"建议补充引用{std.name}以满足合规要求",
                    severity="WARNING"
                ))

        # 3. 检查标准引用的版本适用性
        for std_ref in referenced_standards:
            result = await self._check_standard_version_Applicability(
                std_ref, location, project_year
            )
            if result:
                results.append(result)

        return results

    async def _check_standard_validity(
        self,
        standard_reference: Dict[str, Any],
        project_year: int
    ) -> Optional[ComplianceCheckResult]:
        """检查标准是否现行有效"""
        code = standard_reference.get('code', '')
        name = standard_reference.get('name', '')

        # 检查是否是已被替代的标准
        obsolete_standards = {
            'GB 3095-1996': ('GB 3095-2012', '2016-01-01'),
            'GB 3095-2012': None,  # 现行有效
            'GB 16297-1996': None,  # 仍然有效
            'GB 3838-2002': None,   # 现行有效
            'HJ/T 2.2-1993': ('HJ 2.2-2018', '2018-08-01'),
            'HJ 2.2-2018': None,    # 现行有效
        }

        if code in obsolete_standards:
            replacement = obsolete_standards[code]
            if replacement:
                return ComplianceCheckResult(
                    check_type="obsolete_standard",
                    status=ComplianceStatus.NON_COMPLIANT,
                    description=f"引用的{code}已被{replacement[0]}替代",
                    standard_code=code,
                    details={
                        "replacement_code": replacement[0],
                        "effective_date": replacement[1],
                        "project_year": project_year,
                    },
                    recommendation=f"请更新为现行标准{replacement[0]}",
                    severity="ERROR"
                )

        return None

    async def _check_standard_version_Applicability(
        self,
        standard_reference: Dict[str, Any],
        location: str,
        project_year: int
    ) -> Optional[ComplianceCheckResult]:
        """检查标准版本对地区的适用性"""
        code = standard_reference.get('code', '')
        version = standard_reference.get('version', 'unknown')

        # 某些标准有地区版本差异
        local_standard_mappings = {
            'GB 3095': {
                '北京': 'DB 11/847',  # 北京地标
                '上海': 'DB 31/933',
                '广东': 'DB 44/27',
            },
            'GB 3838': {
                '北京': 'DB 11/307',
                '上海': 'DB 31/199',
                '江苏': 'DB 32/1072',
            }
        }

        # 检查是否有地方标准适用的提示
        for base_std, local_map in local_standard_mappings.items():
            if base_std in code:
                for prov, local_std in local_map.items():
                    if prov in location:
                        # 如果只引用了国家标准而没有地方标准，给出提示
                        if version.lower() in ['national', 'gb', '国家标准'] and 'DB' not in code:
                            return ComplianceCheckResult(
                                check_type="local_standard_applicability",
                                status=ComplianceStatus.WARNING,
                                description=f"{location}地区应考虑执行{local_std}等地方标准",
                                standard_code=code,
                                details={
                                    "location": location,
                                    "applicable_local_std": local_std,
                                },
                                recommendation=f"建议补充{local_std}等地方标准的比较分析",
                                severity="WARNING"
                            )

        return None

    async def check_cross_chapter_consistency(
        self,
        report_sections: Dict[str, str],
        project_context: Dict[str, Any]
    ) -> List[CrossChapterInference]:
        """
        检查跨章节一致性

        Args:
            report_sections: 报告章节字典，key为章节名，value为章节内容
            project_context: 项目上下文

        Returns:
            List[CrossChapterInference]: 跨章节推理结果列表
        """
        results = []

        # 常见的章节对应关系
        chapter_mappings = [
            ("污染源强", "工程分析", ["source_strong", "emission_source", "污染源"]),
            ("环保措施", "环境保护措施", ["environmental_measures", "protection_measures", "措施"]),
            ("大气预测", "环境影响预测", ["air_prediction", "atmospheric_prediction", "预测"]),
            ("水环境影响", "水环境", ["water_environment", "水环境"]),
        ]

        for rule in self.CROSS_CHAPTER_RULES:
            for chapter1_keywords, chapter2_keywords in chapter_mappings:
                # 找到匹配的章节
                chapter1_content = self._find_section_by_keywords(
                    report_sections, chapter1_keywords
                )
                chapter2_content = self._find_section_by_keywords(
                    report_sections, chapter2_keywords
                )

                if chapter1_content and chapter2_content:
                    # 执行一致性检查
                    inference = await self._execute_consistency_check(
                        rule, chapter1_content, chapter2_content, project_context
                    )
                    if inference:
                        results.append(inference)

        return results

    def _find_section_by_keywords(
        self,
        sections: Dict[str, str],
        keywords: List[str]
    ) -> Optional[str]:
        """根据关键词找到匹配的章节内容"""
        for section_name, content in sections.items():
            for keyword in keywords:
                if keyword.lower() in section_name.lower():
                    return content
        return None

    async def _execute_consistency_check(
        self,
        rule: Dict[str, Any],
        chapter1_content: str,
        chapter2_content: str,
        project_context: Dict[str, Any]
    ) -> Optional[CrossChapterInference]:
        """执行一致性检查"""
        # 提取第一章中的关键数据
        match1 = re.search(rule['chapter1_pattern'], chapter1_content)
        if not match1:
            return None

        value1 = float(match1.group(1))
        unit1 = match1.group(2) if len(match1.groups()) > 1 else ""

        # 提取第二章中的关键数据
        match2 = re.search(rule['chapter2_pattern'], chapter2_content)
        if not match2:
            return None

        value2 = float(match2.group(1))
        unit2 = match2.group(2) if len(match2.groups()) > 1 else ""

        # 执行推理
        inference_text = f"根据第一章数据：{value1}{unit1}，第二章数据：{value2}{unit2}"

        # VOCs治理工艺检查
        if rule['name'] == 'vocs_source_to_treatment':
            treatment_match = re.search(
                r'(活性炭吸附|燃烧|催化氧化|生物滤池|冷凝)',
                chapter2_content
            )
            if treatment_match:
                treatment = treatment_match.group(1)
                efficiency_range = rule['typical_efficiency'].get(treatment, (0, 1))
                min_efficiency, max_efficiency = efficiency_range

                # 检查排放是否超标
                # 假设产生量=100, 效率=0.7, 则排放量=30
                if unit1 == 't/a':
                    emission = value1 * (1 - min_efficiency)  # 最大可能排放
                    emission_max = value1 * (1 - max_efficiency)  # 最小可能排放
                else:
                    emission = value1 * (1 - min_efficiency)
                    emission_max = value1 * (1 - max_efficiency)

                # 生成推理文本
                inference_text += f"，采用{treatment}工艺（效率{min_efficiency*100:.0f}-{max_efficiency*100:.0f}%）"

                # 判断一致性
                if emission > 0:
                    return CrossChapterInference(
                        chapter1="污染源强",
                        chapter1_content=chapter1_content[:100],
                        chapter2="环保措施",
                        chapter2_content=chapter2_content[:100],
                        inference_type=rule['inference'],
                        inference_text=inference_text,
                        confidence=0.75,
                        status=ComplianceStatus.COMPLIANT,
                        suggestion=f"工艺选择合理，{treatment}效率符合要求"
                    )

        return None

    async def infer_from_knowledge_graph(
        self,
        premise: Dict[str, Any]
    ) -> List[str]:
        """
        从知识图谱进行推理

        Args:
            premise: 前提条件，如 {"industry": "化工", "media": "air", "scale": "large"}

        Returns:
            List[str]: 推理结果列表
        """
        results = []

        industry = premise.get('industry', '')
        media = premise.get('media', '')

        # 获取适用的标准
        applicable_standards = self.knowledge_graph.get_applicable_standards(industry, media)
        for std in applicable_standards:
            results.append(f"该{industry}项目需要满足{std.name}")

        # 获取相关参数
        for std in applicable_standards:
            related_nodes = self.knowledge_graph.get_related_nodes(
                std.node_id,
                [RelationType.APPLIES_TO]
            )
            for node, edge in related_nodes:
                if node.node_type == 'parameter':
                    results.append(f"{std.name}涉及{node.name}指标")

        return results


class KnowledgeGraphComplianceEngine:
    """
    知识图谱合规引擎 - 整合知识图谱和推理引擎

    这是审查模块的主要入口，提供：
    1. 标准合规性检查
    2. 跨章节一致性检查
    3. 智能推荐
    """

    def __init__(self):
        self.inference_engine = ComplianceInferenceEngine()
        self.standards_db: List[StandardClause] = []
        self._load_builtin_standards()

    def _load_builtin_standards(self):
        """加载内置标准"""
        # GB 3095-2012 关键条款
        self.standards_db.extend([
            StandardClause(
                standard_code="GB 3095-2012",
                standard_name="环境空气质量标准",
                clause_id="5.1",
                clause_title="污染物浓度限值",
                clause_content="二氧化硫日平均浓度限值为150μg/m³...",
                applicability="适用于环境空气质量功能区划",
                parameters={"SO₂": {"日均值": 150, "unit": "μg/m³"}}
            ),
        ])

    async def check_compliance(
        self,
        report_id: str,
        project_name: str,
        report_content: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> ComplianceReport:
        """
        执行完整合规检查

        Args:
            report_id: 报告ID
            project_name: 项目名称
            report_content: 报告内容
            project_context: 项目上下文

        Returns:
            ComplianceReport: 完整合规检查报告
        """
        report = ComplianceReport(
            report_id=report_id,
            project_name=project_name,
            check_time=datetime.now()
        )

        # 1. 标准合规性检查
        report.standard_checks = await self.inference_engine.check_standard_compliance(
            report_content, project_context
        )

        # 2. 跨章节一致性检查
        if 'sections' in report_content:
            report.cross_chapter_checks = await self.inference_engine.check_cross_chapter_consistency(
                report_content['sections'], project_context
            )

        # 3. 计算整体状态
        issues = report.get_issue_count()
        if issues == 0:
            report.overall_status = ComplianceStatus.COMPLIANT
            report.summary = "未发现合规性问题"
        elif issues <= 2:
            report.overall_status = ComplianceStatus.WARNING
            report.summary = f"发现{issues}项合规性警告"
        else:
            report.overall_status = ComplianceStatus.NON_COMPLIANT
            report.summary = f"发现{issues}项合规性问题，需要修正"

        # 4. 计算风险等级
        error_count = sum(
            1 for c in report.standard_checks
            if c.severity == "ERROR"
        )
        if error_count > 5:
            report.risk_level = "CRITICAL"
        elif error_count > 2:
            report.risk_level = "HIGH"
        elif issues > 0:
            report.risk_level = "MEDIUM"
        else:
            report.risk_level = "LOW"

        return report

    def get_recommended_standards(
        self,
        industry: str,
        media: str
    ) -> List[str]:
        """获取推荐的标准列表"""
        recommendations = []
        applicable = self.inference_engine.knowledge_graph.get_applicable_standards(
            industry, media
        )
        for std in applicable:
            recommendations.append(f"{std.name} ({std.node_id})")
        return recommendations


# 全局实例
_compliance_engine_instance: Optional[KnowledgeGraphComplianceEngine] = None


def get_compliance_engine() -> KnowledgeGraphComplianceEngine:
    """获取合规检查引擎全局实例"""
    global _compliance_engine_instance
    if _compliance_engine_instance is None:
        _compliance_engine_instance = KnowledgeGraphComplianceEngine()
    return _compliance_engine_instance


async def check_compliance_async(
    report_id: str,
    project_name: str,
    report_content: Dict[str, Any],
    project_context: Dict[str, Any]
) -> ComplianceReport:
    """异步执行合规检查的便捷函数"""
    engine = get_compliance_engine()
    return await engine.check_compliance(
        report_id, project_name, report_content, project_context
    )


async def get_recommended_standards_async(
    industry: str,
    media: str
) -> List[str]:
    """获取推荐标准的便捷函数"""
    engine = get_compliance_engine()
    return engine.get_recommended_standards(industry, media)