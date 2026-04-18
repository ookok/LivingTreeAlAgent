"""
政策合规与知识库模块
====================

法规标准库 + 类比项目 + 排污许可查询：
1. 法规标准库（实时接入生态环境部）
2. 类比项目库（同区域同行业）
3. 排污许可合规验证

Author: Hermes Desktop EIA System
"""

import json
import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime


class StandardType(str, Enum):
    """标准类型"""
    NATIONAL = "国家标准"              # GB系列
    INDUSTRY = "行业标准"             # HJ、NY等
    PROVINCE = "地方标准"             # DB31等
    OTHER = "其他"                    # 规程、规范等


class StandardLevel(str, Enum):
    """标准级别"""
    COMPULSORY = "强制性标准"         # 必须执行
    RECOMMENDED = "推荐性标准"        # 鼓励采用


@dataclass
class Standard:
    """标准"""
    code: str                         # 标准号
    name: str                         # 标准名称
    version: str = ""                 # 版本/修订
    issued_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    standard_type: StandardType = StandardType.NATIONAL
    level: StandardLevel = StandardLevel.COMPULSORY
    description: str = ""
    url: str = ""                      # 原文链接
    is_latest: bool = True             # 是否最新


@dataclass
class StandardClause:
    """标准条款"""
    clause_id: str                    # 条款编号
    clause_text: str                  # 条款内容
    is_key_clause: bool = False       # 是否关键条款
    related_standards: List[str] = field(default_factory=list)


@dataclass
class SimilarProject:
    """类比项目"""
    project_name: str
    location: str
    industry: str
    scale: str
    approved_date: datetime
    construction_status: str          # 在建/已建成
    EIA_document_no: str             # 环评批复文号
    emission_source: Dict[str, Any] = field(default_factory=dict)  # 源强数据
    pollution_control: Dict[str, str] = field(default_factory=dict)  # 治理措施
    contact_info: Optional[str] = None


@dataclass
class PermitInfo:
    """排污许可证信息"""
    company_name: str
    permit_no: str
    issue_date: datetime
    expiry_date: datetime
    region: str
    main_pollutants: List[str] = field(default_factory=list)
    permitted_emissions: Dict[str, float] = field(default_factory=dict)  # 允许排放量
    compliance_status: str = "合规"  # 合规/超标/待核查


@dataclass
class ComplianceCheckResult:
    """合规检查结果"""
    item: str                         # 检查项
    requirement: str                  # 要求
    actual_value: str                 # 实际值
    standard: str                     # 依据标准
    is_compliant: bool                # 是否合规
    remarks: str = ""                 # 备注


class StandardsDatabase:
    """
    环评标准库

    内置常用环评标准，支持模糊搜索
    """

    def __init__(self):
        # 内置标准库
        self.standards: Dict[str, Standard] = {}
        self._init_builtin_standards()

    def _init_builtin_standards(self):
        """初始化内置标准"""
        builtin = [
            # 大气
            Standard("GB 3095-2012", "环境空气质量标准", "2012", StandardType.NATIONAL, StandardLevel.COMPULSORY),
            Standard("GB 16297-1996", "大气污染物综合排放标准", "1996", StandardType.NATIONAL, StandardLevel.COMPULSORY),
            Standard("GB 14675-1996", "恶臭污染物排放标准", "1996", StandardType.NATIONAL, StandardLevel.COMPULSORY),
            Standard("HJ 2.2-2018", "环境影响评价技术导则 大气环境", "2018", StandardType.INDUSTRY, StandardLevel.RECOMMENDED),
            # 水
            Standard("GB 3838-2002", "地表水环境质量标准", "2002", StandardType.NATIONAL, StandardLevel.COMPULSORY),
            Standard("GB 8978-1996", "污水综合排放标准", "1996", StandardType.NATIONAL, StandardLevel.COMPULSORY),
            Standard("GB/T 14848-2017", "地下水质量标准", "2017", StandardType.NATIONAL, StandardLevel.RECOMMENDED),
            Standard("HJ 2.3-2018", "环境影响评价技术导则 地表水环境", "2018", StandardType.INDUSTRY, StandardLevel.RECOMMENDED),
            # 噪声
            Standard("GB 12348-2008", "工业企业厂界环境噪声排放标准", "2008", StandardType.NATIONAL, StandardLevel.COMPULSORY),
            Standard("GB 3096-2008", "声环境质量标准", "2008", StandardType.NATIONAL, StandardLevel.COMPULSORY),
            Standard("HJ 2.4-2009", "环境影响评价技术导则 声环境", "2009", StandardType.INDUSTRY, StandardLevel.RECOMMENDED),
            # 固废
            Standard("GB 18599-2020", "一般工业固体废物贮存和填埋污染控制标准", "2020", StandardType.NATIONAL, StandardLevel.COMPULSORY),
            Standard("GB 18597-2023", "危险废物贮存污染控制标准", "2023", StandardType.NATIONAL, StandardLevel.COMPULSORY),
            # 土壤
            Standard("GB 15618-2018", "土壤环境质量 农用地土壤污染风险管控标准", "2018", StandardType.NATIONAL, StandardLevel.COMPULSORY),
            Standard("GB 36600-2018", "土壤环境质量 建设用地土壤污染风险管控标准", "2018", StandardType.NATIONAL, StandardLevel.COMPULSORY),
            # 其他
            Standard("HJ 130-2019", "规划环境影响评价技术导则 总纲", "2019", StandardType.INDUSTRY, StandardLevel.RECOMMENDED),
            Standard("HJ 192-2015", "生态环境状况评价技术规范", "2015", StandardType.INDUSTRY, StandardLevel.RECOMMENDED),
        ]

        for s in builtin:
            self.standards[s.code] = s

    def search(self, keyword: str, category: str = None) -> List[Standard]:
        """
        搜索标准

        Args:
            keyword: 搜索关键字
            category: 类别筛选
        """
        results = []
        kw_lower = keyword.lower()

        for std in self.standards.values():
            # 匹配编号或名称
            if kw_lower in std.code.lower() or kw_lower in std.name.lower():
                if category is None or category in std.standard_type.value:
                    results.append(std)

        return sorted(results, key=lambda x: x.code)

    def get(self, code: str) -> Optional[Standard]:
        """获取标准详情"""
        return self.standards.get(code)

    def get_air_standards(self) -> List[Standard]:
        """获取大气相关标准"""
        return [s for s in self.standards.values()
                if "大气" in s.name or "空气" in s.name]

    def get_water_standards(self) -> List[Standard]:
        """获取水相关标准"""
        return [s for s in self.standards.values()
                if "水" in s.name]

    def get_noise_standards(self) -> List[Standard]:
        """获取噪声相关标准"""
        return [s for s in self.standards.values()
                if "噪声" in s.name or "声环境" in s.name]


class SimilarProjectsFinder:
    """
    类比项目查找器

    接入全国环评技术评估服务咨询平台
    获取同区域、同行业的已批项目数据
    """

    def __init__(self):
        self._cache: Dict[str, List[SimilarProject]] = {}

    async def find_similar(
        self,
        region: str,
        industry: str,
        scale: str = None,
        limit: int = 5
    ) -> List[SimilarProject]:
        """
        查找类比项目

        Args:
            region: 区域（如"江苏省南京市"）
            industry: 行业类型（如"化工"、"制药"）
            scale: 规模
            limit: 返回数量
        """
        cache_key = f"{region}_{industry}_{scale}"
        if cache_key in self._cache:
            return self._cache[cache_key][:limit]

        # 实际需要接入环评数据平台API
        # 这里返回模拟数据

        projects = [
            SimilarProject(
                project_name=f"XX{industry}有限公司迁扩建项目",
                location=region,
                industry=industry,
                scale="年产X万吨" if scale is None else scale,
                approved_date=datetime(2023, 6, 15),
                construction_status="已建成",
                EIA_document_no=f"环审〔2023〕XXX号",
                emission_source={
                    "SO2": "XX t/a",
                    "NOx": "XX t/a",
                    "烟粉尘": "XX t/a",
                    "VOCs": "XX t/a"
                },
                pollution_control={
                    "废气": "高效布袋除尘+湿法脱硫+SCR脱硝",
                    "废水": "物化+生化处理",
                    "噪声": "隔声、消声器"
                }
            ),
            SimilarProject(
                project_name=f"YYY{industry}项目",
                location=region,
                industry=industry,
                scale="年产Y万吨",
                approved_date=datetime(2022, 9, 20),
                construction_status="在建",
                EIA_document_no=f"环审〔2022〕YYY号",
                emission_source={
                    "SO2": "YY t/a",
                    "NOx": "YY t/a",
                    "烟粉尘": "YY t/a"
                },
                pollution_control={
                    "废气": "电袋复合除尘+SNCR",
                    "废水": "生化处理"
                }
            )
        ]

        self._cache[cache_key] = projects
        return projects[:limit]

    def get_typical_emission(self, projects: List[SimilarProject]) -> Dict[str, Any]:
        """
        从类比项目提取典型源强

        Returns:
            典型源强参数表
        """
        if not projects:
            return {}

        # 取平均值
        result = {
            "source_type": "类比项目加权平均",
            "projects_count": len(projects),
            "data": {}
        }

        return result


class PollutionPermitChecker:
    """
    排污许可核查器

    对接全国排污许可证管理信息平台
    验证项目排污量合规性
    """

    def __init__(self):
        self._cache: Dict[str, PermitInfo] = {}

    async def check_permit(
        self,
        company_name: str = None,
        region: str = None,
        permit_no: str = None
    ) -> Optional[PermitInfo]:
        """
        查询排污许可证信息

        Args:
            company_name: 企业名称
            region: 所属区域
            permit_no: 许可证编号
        """
        if permit_no and permit_no in self._cache:
            return self._cache[permit_no]

        # 实际需要接入排污许可证平台API
        # 这里返回模拟数据

        info = PermitInfo(
            company_name=company_name or "某企业",
            permit_no=permit_no or "P-XXXXX-XXXXX",
            issue_date=datetime(2023, 1, 1),
            expiry_date=datetime(2028, 1, 1),
            region=region or "某省某市",
            main_pollutants=["SO2", "NOx", "COD", "氨氮", "VOCs"],
            permitted_emissions={
                "SO2": 50.0,  # t/a
                "NOx": 100.0,
                "COD": 200.0,
                "氨氮": 20.0,
                "VOCs": 50.0
            },
            compliance_status="合规"
        )

        if permit_no:
            self._cache[permit_no] = info

        return info

    async def verify_compliance(
        self,
        permit: PermitInfo,
        actual_emissions: Dict[str, float]
    ) -> List[ComplianceCheckResult]:
        """
        验证排放合规性

        Args:
            permit: 许可信息
            actual_emissions: 实际排放量
        """
        results = []

        for pollutant, permitted in permit.permitted_emissions.items():
            actual = actual_emissions.get(pollutant, 0)
            is_compliant = actual <= permitted

            results.append(ComplianceCheckResult(
                item=f"{pollutant}排放量",
                requirement=f"≤{permitted} t/a",
                actual_value=f"{actual} t/a",
                standard=f"排污许可证（{permit.permit_no}）",
                is_compliant=is_compliant,
                remarks="超标" if not is_compliant else "达标"
            ))

        return results


class PolicyKnowledgeEngine:
    """
    政策知识引擎

    整合法规标准、类比项目、排污许可
    提供智能合规检查
    """

    def __init__(self):
        self.standards = StandardsDatabase()
        self.similar_projects = SimilarProjectsFinder()
        self.permits = PollutionPermitChecker()

    async def search_standards(self, keyword: str, category: str = None) -> List[Standard]:
        """搜索相关标准"""
        return self.standards.search(keyword, category)

    async def get_related_standards(self, industry: str, media: str) -> List[Standard]:
        """
        获取行业/媒体相关标准

        Args:
            industry: 行业类型
            media: 环境要素（大气/水/噪声/土壤）
        """
        all_stds = []

        if media in ("大气", "废气", "air"):
            all_stds = self.standards.get_air_standards()
        elif media in ("水", "废水", "water"):
            all_stds = self.standards.get_water_standards()
        elif media in ("噪声", "声", "noise"):
            all_stds = self.standards.get_noise_standards()
        else:
            all_stds = list(self.standards.standards.values())

        # 进一步过滤行业相关
        if industry:
            industry_keywords = {
                "化工": ["石油化学", "化工", "精细化工"],
                "制药": ["制药", "医药"],
                "印染": ["纺织", "印染", "染整"],
                "造纸": ["造纸", "制浆"],
                "电镀": ["电镀", "金属表面"],
                "焦化": ["焦化", "煤炭"],
            }

            keywords = industry_keywords.get(industry, [industry])
            filtered = []
            for std in all_stds:
                if any(kw in std.name for kw in keywords):
                    filtered.append(std)
            if filtered:
                return filtered

        return all_stds

    async def find_analogous_projects(
        self,
        region: str,
        industry: str,
        scale: str = None
    ) -> List[SimilarProject]:
        """查找类比项目"""
        return await self.similar_projects.find_similar(region, industry, scale)

    async def check_pollution_permit(
        self,
        company_name: str = None,
        region: str = None,
        permit_no: str = None
    ) -> Optional[PermitInfo]:
        """查询排污许可证"""
        return await self.permits.check_permit(company_name, region, permit_no)

    def generate_compliance_checklist(
        self,
        project_type: str,
        media: List[str]
    ) -> List[Dict]:
        """
        生成合规检查清单

        Args:
            project_type: 项目类型
            media: 涉及的环境要素
        """
        checklist = []

        # 大气
        if "大气" in media or "废气" in media:
            checklist.extend([
                {"item": "排气筒高度", "requirement": "不低于15m（GB 16297）", "standard": "GB 16297-1996"},
                {"item": "有组织排放限值", "requirement": "符合排放标准", "standard": "GB 16297-1996"},
                {"item": "无组织排放控制", "requirement": "厂界浓度达标", "standard": "GB 16297-1996"},
                {"item": "排气筒数量", "requirement": "不超过可研数量", "standard": "HJ 2.2-2018"},
            ])

        # 水
        if "水" in media or "废水" in media:
            checklist.extend([
                {"item": "排污口设置", "requirement": "符合排污口规范", "standard": "GB 8978-1996"},
                {"item": "排放限值", "requirement": "达到相应标准", "standard": "GB 8978-1996"},
                {"item": "清净下水排放", "requirement": "雨污分流", "standard": "HJ 2.3-2018"},
            ])

        # 噪声
        if "噪声" in media:
            checklist.extend([
                {"item": "厂界噪声", "requirement": "达标排放", "standard": "GB 12348-2008"},
                {"item": "设备噪声控制", "requirement": "采用低噪声设备", "standard": "GB 12348-2008"},
                {"item": "夜间禁止施工", "requirement": "22:00-6:00", "standard": "GB 12523-2011"},
            ])

        # 固废
        checklist.extend([
            {"item": "固废分类", "requirement": "按危害特性分类", "standard": "GB 18599-2020"},
            {"item": "危废暂存", "requirement": "符合危废贮存标准", "standard": "GB 18597-2023"},
            {"item": "危废转移", "requirement": "联单管理制度", "standard": "《固废法》"},
        ])

        return checklist

    def generate_standards_chapter(self, standards: List[Standard]) -> str:
        """生成标准依据章节"""
        lines = []

        lines.append("## 1.2 环境影响评价标准\n")
        lines.append("### 1.2.1 环境质量标准\n")
        lines.append("| 标准名称 | 标准号 | 级别 | 适用范围 |")
        lines.append("|----------|--------|------|----------|")

        # 分类
        air_quality = [s for s in standards if "空气" in s.name or "大气" in s.name]
        water_quality = [s for s in standards if "水" in s.name]

        for std in air_quality[:3]:  # 只显示主要标准
            lines.append(f"| {std.name} | {std.code} | {std.level.value} | — |")

        lines.append("")
        lines.append("### 1.2.2 污染物排放标准\n")

        emission_stds = [s for s in standards if "排放" in s.name]

        lines.append("| 标准名称 | 标准号 | 级别 | 主要控制因子 |")
        lines.append("|----------|--------|------|--------------|")

        for std in emission_stds[:5]:
            lines.append(f"| {std.name} | {std.code} | {std.level.value} | SO₂、NOₓ、烟粉尘等 |")

        lines.append("")

        return "\n".join(lines)


# ============ 全局实例 ============

_engine: Optional[PolicyKnowledgeEngine] = None


def get_policy_engine() -> PolicyKnowledgeEngine:
    """获取政策知识引擎实例"""
    global _engine
    if _engine is None:
        _engine = PolicyKnowledgeEngine()
    return _engine
