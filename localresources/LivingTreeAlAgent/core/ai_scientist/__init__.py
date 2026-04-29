"""
环境AI科学家 (Environmental AI Scientist)
==========================================

让图谱具备自主探索和发现新知识的能力，成为企业的"环境AI研发部"。

核心功能：
1. 未知污染物与风险"探针"
2. 环保技术路线自动规划
3. 文献挖掘与知识发现
4. 化学物质图谱分析

Author: Hermes Desktop Team
"""

import logging
import json
import threading
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """风险等级"""
    NEGLIGIBLE = "negligible"     # 可忽略
    LOW = "low"                   # 低风险
    MEDIUM = "medium"             # 中风险
    HIGH = "high"                 # 高风险
    EXTREME = "extreme"           # 极高风险


class TechnologyType(Enum):
    """技术类型"""
    END_OF_PIPE = "end_of_pipe"   # 末端治理
    PROCESS_OPTIMIZATION = "process_optimization"  # 过程优化
    SUBSTITUTION = "substitution"  # 原料替代
    INTEGRATED = "integrated"      # 综合治理


@dataclass
class ChemicalCompound:
    """化学物质"""
    compound_id: str
    name: str
    cas_no: str = ""              # CAS号
    molecular_formula: str = ""   # 分子式
    molecular_weight: float = 0.0
    categories: List[str] = field(default_factory=list)  # 类别（VOC、重金属等）
    hazards: List[str] = field(default_factory=list)     # 危害
    sources: List[str] = field(default_factory=list)      # 来源
    risk_level: RiskLevel = RiskLevel.LOW


@dataclass
class MassSpectrometryPeak:
    """质谱特征峰"""
    mz: float                     # 质荷比
    intensity: float               # 强度
    assignment: str = ""          # 可能归属


@dataclass
class UnknownPollutant:
    """未知污染物"""
    pollutant_id: str
    detection_time: datetime
    source_id: str               # 来源（排放口/监测点）
    peaks: List[MassSpectrometryPeak]
    possible_compounds: List[Dict] = field(default_factory=list)  # 可能的化合物
    risk_assessment: Dict = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class PollutionControlTechnology:
    """污染控制技术"""
    tech_id: str
    name: str
    tech_type: TechnologyType
    applicable_pollutants: List[str]
    removal_efficiency: Dict[str, float]  # pollutant -> efficiency (%)
    investment_cost: float        # 投资成本 (万元)
    operating_cost: float          # 运行成本 (万元/年)
    lifetime: int = 15            # 寿命 (年)
    power_consumption: float = 0.0  # 电耗 (kW)
    space_requirement: str = ""   # 空间需求
    maintenance_difficulty: str = "medium"  # 维护难度
    certifications: List[str] = field(default_factory=list)  # 资质认证
    case_studies: List[str] = field(default_factory=list)  # 案例


@dataclass
class TechnologyRoute:
    """技术路线"""
    route_id: str
    name: str
    description: str
    technologies: List[PollutionControlTechnology]
    total_investment: float
    annual_operating_cost: float
    expected_efficiency: float   # 整体去除效率 (%)
    payback_period: float        # 投资回收期 (年)
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    suitability: str = ""        # 适用场景


@dataclass
class TechRecommendation:
    """技术推荐"""
    recommendation_id: str
    target_pollutant: str
    target_reduction: float      # 目标减排比例 (%)
    routes: List[TechnologyRoute]
    best_route: TechnologyRoute = None
    alternatives: List[TechnologyRoute] = field(default_factory=list)
    considerations: List[str] = field(default_factory=list)


@dataclass
class LiteratureReference:
    """文献参考"""
    ref_id: str
    title: str
    authors: List[str]
    journal: str = ""
    year: int = 0
    doi: str = ""
    abstract: str = ""
    keywords: List[str] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)


@dataclass
class KnowledgeDiscovery:
    """知识发现"""
    discovery_id: str
    discovery_type: str          # pollutant/route/correlation
    title: str
    description: str
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.0      # 置信度 (0-1)
    novelty: float = 0.0         # 创新性 (0-1)
    implications: List[str] = field(default_factory=list)


class EnvironmentalAIScientist:
    """
    环境AI科学家

    自主探索和发现新知识，成为企业的"环境AI研发部"。

    使用示例：
    ```python
    scientist = EnvironmentalAIScientist()

    # 1. 未知污染物发现
    unknown = scientist.detect_unknown_pollutant(
        source_id="outlet_001",
        peaks=[(45.2, 0.85), (78.3, 0.62)]
    )

    # 2. 技术路线规划
    recommendation = scientist.plan_pollution_control(
        target_pollutant="VOCs",
        current_emission=1000,  # kg/year
        reduction_target=0.5    # 50%
    )

    # 3. 文献挖掘
    discoveries = scientist.mine_literature("新型VOCs治理技术")

    # 4. 知识发现
    findings = scientist.discover_knowledge(project_data)
    ```
    """

    def __init__(self, knowledge_graph=None):
        self.kg = knowledge_graph

        # 化学物质数据库
        self._compound_db: Dict[str, ChemicalCompound] = {}
        self._init_compound_db()

        # 技术数据库
        self._technology_db: Dict[str, PollutionControlTechnology] = {}
        self._init_technology_db()

        # 文献库
        self._literature_db: Dict[str, LiteratureReference] = {}
        self._init_literature_db()

        logger.info("初始化环境AI科学家")

    def _init_compound_db(self):
        """初始化化学物质数据库"""
        compounds = [
            ChemicalCompound(
                compound_id="voc_001",
                name="苯",
                cas_no="71-43-2",
                molecular_formula="C6H6",
                molecular_weight=78.11,
                categories=["VOC", "芳香烃"],
                hazards=["致癌", "致畸"],
                sources=["石油化工", "印刷", "涂装"],
                risk_level=RiskLevel.HIGH
            ),
            ChemicalCompound(
                compound_id="voc_002",
                name="甲苯",
                cas_no="108-88-3",
                molecular_formula="C7H8",
                molecular_weight=92.14,
                categories=["VOC", "芳香烃"],
                hazards=["神经毒性", "肝损伤"],
                sources=["喷漆", "印刷", "胶粘剂"],
                risk_level=RiskLevel.MEDIUM
            ),
            ChemicalCompound(
                compound_id="voc_003",
                name="二甲苯",
                cas_no="1330-20-7",
                molecular_formula="C8H10",
                molecular_weight=106.16,
                categories=["VOC", "芳香烃"],
                hazards=["刺激呼吸道", "肝损伤"],
                sources=["喷漆", "印刷", "涂料"],
                risk_level=RiskLevel.MEDIUM
            ),
            ChemicalCompound(
                compound_id="voc_004",
                name="乙酸乙酯",
                cas_no="141-78-6",
                molecular_formula="C4H8O2",
                molecular_weight=88.11,
                categories=["VOC", "酯类"],
                hazards=["刺激呼吸道", "麻醉作用"],
                sources=["印刷", "涂装", "清洗"],
                risk_level=RiskLevel.LOW
            ),
            ChemicalCompound(
                compound_id="voc_005",
                name="丙酮",
                cas_no="67-64-1",
                molecular_formula="C3H6O",
                molecular_weight=58.08,
                categories=["VOC", "酮类"],
                hazards=["易燃", "刺激呼吸道"],
                sources=["化工", "清洗", "溶剂"],
                risk_level=RiskLevel.LOW
            ),
            ChemicalCompound(
                compound_id="metal_001",
                name="铬",
                cas_no="7440-47-3",
                molecular_formula="Cr",
                molecular_weight=52.0,
                categories=["重金属"],
                hazards=["致癌", "皮肤刺激"],
                sources=["电镀", "皮革", "冶金"],
                risk_level=RiskLevel.HIGH
            ),
            ChemicalCompound(
                compound_id="metal_002",
                name="镍",
                cas_no="7440-02-0",
                molecular_formula="Ni",
                molecular_weight=58.69,
                categories=["重金属"],
                hazards=["致癌", "致敏"],
                sources=["电镀", "不锈钢", "电池"],
                risk_level=RiskLevel.MEDIUM
            ),
        ]

        for compound in compounds:
            self._compound_db[compound.compound_id] = compound

    def _init_technology_db(self):
        """初始化技术数据库"""
        technologies = [
            # VOCs治理技术
            PollutionControlTechnology(
                tech_id="tech_rco",
                name="蓄热式催化燃烧(RCO)",
                tech_type=TechnologyType.END_OF_PIPE,
                applicable_pollutants=["VOCs", "苯", "甲苯", "二甲苯"],
                removal_efficiency={"VOCs": 95, "苯": 98, "甲苯": 97},
                investment_cost=300,
                operating_cost=80,
                power_consumption=150,
                space_requirement="中等",
                maintenance_difficulty="medium",
                certifications=["CE", "ISO9001"],
                case_studies=["某汽车厂喷漆线", "某集装箱厂涂装线"]
            ),
            PollutionControlTechnology(
                tech_id="tech_rto",
                name="蓄热式热力燃烧(RTO)",
                tech_type=TechnologyType.END_OF_PIPE,
                applicable_pollutants=["VOCs", "混合废气"],
                removal_efficiency={"VOCs": 99, "SO2": 90},
                investment_cost=500,
                operating_cost=120,
                power_consumption=200,
                space_requirement="较大",
                maintenance_difficulty="high",
                certifications=["ISO9001"],
                case_studies=["某石化企业", "某制药企业"]
            ),
            PollutionControlTechnology(
                tech_id="tech_activated_carbon",
                name="活性炭吸附",
                tech_type=TechnologyType.END_OF_PIPE,
                applicable_pollutants=["VOCs", "恶臭", "Hg"],
                removal_efficiency={"VOCs": 85, "Hg": 90},
                investment_cost=150,
                operating_cost=50,
                power_consumption=20,
                space_requirement="小",
                maintenance_difficulty="medium",
                certifications=["ISO9001", "环境认证"],
                case_studies=["某印刷厂", "某喷漆车间"]
            ),
            PollutionControlTechnology(
                tech_id="tech_photooxidation",
                name="光催化氧化",
                tech_type=TechnologyType.END_OF_PIPE,
                applicable_pollutants=["VOCs", "NH3", "H2S"],
                removal_efficiency={"VOCs": 80, "NH3": 75},
                investment_cost=100,
                operating_cost=30,
                power_consumption=50,
                space_requirement="小",
                maintenance_difficulty="low",
                certifications=["CE"],
                case_studies=["某实验室", "某医院"]
            ),
            PollutionControlTechnology(
                tech_id="tech_membrane",
                name="膜分离技术",
                tech_type=TechnologyType.END_OF_PIPE,
                applicable_pollutants=["VOCs", "溶剂回收"],
                removal_efficiency={"VOCs": 98},
                investment_cost=400,
                operating_cost=60,
                power_consumption=80,
                space_requirement="中",
                maintenance_difficulty="high",
                certifications=["ISO9001"],
                case_studies=["某化工园区"]
            ),

            # 废水治理技术
            PollutionControlTechnology(
                tech_id="tech_mbr",
                name="MBR膜生物反应器",
                tech_type=TechnologyType.END_OF_PIPE,
                applicable_pollutants=["COD", "NH3-N", "TN"],
                removal_efficiency={"COD": 90, "NH3-N": 95, "TN": 80},
                investment_cost=200,
                operating_cost=45,
                power_consumption=60,
                space_requirement="中",
                maintenance_difficulty="medium",
                certifications=["ISO9001", "环保认证"],
                case_studies=["某印染厂", "某化工企业"]
            ),
            PollutionControlTechnology(
                tech_id="tech_fenton",
                name="Fenton氧化",
                tech_type=TechnologyType.END_OF_PIPE,
                applicable_pollutants=["COD", "色度", "难降解有机物"],
                removal_efficiency={"COD": 70, "色度": 95},
                investment_cost=120,
                operating_cost=55,
                power_consumption=30,
                space_requirement="小",
                maintenance_difficulty="medium",
                certifications=["ISO9001"],
                case_studies=["某制药废水"]
            ),

            # 过程优化技术
            PollutionControlTechnology(
                tech_id="tech_dry_booth",
                name="干式喷漆房",
                tech_type=TechnologyType.PROCESS_OPTIMIZATION,
                applicable_pollutants=["VOCs", "漆雾"],
                removal_efficiency={"VOCs": 40, "漆雾": 95},
                investment_cost=250,
                operating_cost=40,
                power_consumption=40,
                space_requirement="原有设备改造",
                maintenance_difficulty="low",
                certifications=["ISO9001"],
                case_studies=["某汽车4S店", "某家具厂"]
            ),
            PollutionControlTechnology(
                tech_id="tech_water_curtain",
                name="水帘柜改造",
                tech_type=TechnologyType.PROCESS_OPTIMIZATION,
                applicable_pollutants=["漆雾", "颗粒物"],
                removal_efficiency={"漆雾": 85},
                investment_cost=80,
                operating_cost=25,
                power_consumption=15,
                space_requirement="小",
                maintenance_difficulty="low",
                certifications=["ISO9001"],
                case_studies=["某五金喷涂厂"]
            ),

            # 替代技术
            PollutionControlTechnology(
                tech_id="tech_waterborne",
                name="水性涂料替代",
                tech_type=TechnologyType.SUBSTITUTION,
                applicable_pollutants=["VOCs", "苯系物"],
                removal_efficiency={"VOCs": 80, "苯系物": 90},
                investment_cost=180,
                operating_cost=-50,  # 节省成本
                power_consumption=-10,  # 节能
                space_requirement="无需新增",
                maintenance_difficulty="low",
                certifications=["绿色产品认证"],
                case_studies=["某钢结构厂", "某集装箱厂"]
            ),
        ]

        for tech in technologies:
            self._technology_db[tech.tech_id] = tech

    def _init_literature_db(self):
        """初始化文献库（模拟）"""
        literatures = [
            LiteratureReference(
                ref_id="lit_001",
                title="VOCs治理技术研究进展",
                authors=["张三", "李四"],
                journal="环境科学",
                year=2023,
                keywords=["VOCs", "治理技术", "RCO", "RTO"],
                findings=[
                    "RCO对高浓度VOCs去除效率可达95%以上",
                    "组合技术比单一技术效果更好",
                    "物联网监控可提升治理效率20%"
                ]
            ),
            LiteratureReference(
                ref_id="lit_002",
                title="电镀废水处理技术比较研究",
                authors=["王五", "赵六"],
                journal="工业水处理",
                year=2022,
                keywords=["电镀", "废水", "重金属", "MBR"],
                findings=[
                    "MBR+RO组合可实现90%以上重金属去除",
                    "高级氧化对COD去除效果显著"
                ]
            ),
        ]

        for lit in literatures:
            self._literature_db[lit.ref_id] = lit

    def detect_unknown_pollutant(self, source_id: str,
                               peaks: List[Tuple[float, float]]) -> UnknownPollutant:
        """
        检测未知污染物

        Args:
            source_id: 来源ID
            peaks: 质谱峰列表 [(mz, intensity), ...]

        Returns:
            未知污染物分析结果
        """
        pollutant_id = f"unknown_{source_id}_{int(datetime.now().timestamp())}"

        # 质谱峰
        mass_peaks = [
            MassSpectrometryPeak(mz=mz, intensity=intensity)
            for mz, intensity in peaks
        ]

        # 尝试匹配已知化合物
        possible_compounds = []
        for compound in self._compound_db.values():
            match_score = self._match_compound(compound, peaks)
            if match_score > 0.5:
                possible_compounds.append({
                    "compound": compound.name,
                    "cas_no": compound.cas_no,
                    "match_score": match_score,
                    "risk_level": compound.risk_level.value
                })

        # 风险评估
        risk_assessment = self._assess_unknown_risk(possible_compounds)

        # 建议
        recommendations = []
        if possible_compounds:
            recommendations.append(
                f"检测到可能的化合物: {', '.join([c['compound'] for c in possible_compounds[:3]])}"
            )
            if any(c['risk_level'] == 'high' for c in possible_compounds):
                recommendations.append("⚠️ 检测到高风险物质，建议立即排查源头")
            recommendations.append("建议使用GC-MS进行进一步确认")
        else:
            recommendations.append("未能匹配已知化合物，建议送样检测")

        return UnknownPollutant(
            pollutant_id=pollutant_id,
            detection_time=datetime.now(),
            source_id=source_id,
            peaks=mass_peaks,
            possible_compounds=possible_compounds,
            risk_assessment=risk_assessment,
            recommendations=recommendations
        )

    def _match_compound(self, compound: ChemicalCompound,
                       peaks: List[Tuple[float, float]]) -> float:
        """匹配化合物与质谱峰"""
        # 简化实现：基于分子量和特征碎片
        # 实际应使用完整的质谱库匹配算法

        if not peaks:
            return 0.0

        # 检查是否有匹配的m/z值
        compound_mz = compound.molecular_weight
        tolerance = 0.5  # 误差容许

        for mz, intensity in peaks:
            if abs(mz - compound_mz) < tolerance:
                return 0.8 * intensity  # 返回匹配度（考虑强度）

        # 检查类别特征
        for peak_mz, _ in peaks[:3]:  # 只看前几个峰
            if compound.molecular_weight > 0:
                ratio = peak_mz / compound.molecular_weight
                if 0.5 < ratio < 1.5:
                    return 0.4

        return 0.2

    def _assess_unknown_risk(self, possible_compounds: List[Dict]) -> Dict:
        """评估未知污染物风险"""
        if not possible_compounds:
            return {
                "risk_level": RiskLevel.UNKNOWN.value,
                "confidence": 0.3,
                "description": "无法确定污染物类型，建议进一步检测"
            }

        # 找最高风险
        max_risk = RiskLevel.LOW
        for comp in possible_compounds:
            risk = RiskLevel(comp.get('risk_level', 'low'))
            if risk.value > max_risk.value:
                max_risk = risk

        avg_confidence = sum(c['match_score'] for c in possible_compounds) / len(possible_compounds)

        descriptions = {
            RiskLevel.HIGH: "检测到高风险化合物，可能对人体健康和环境造成严重危害",
            RiskLevel.MEDIUM: "检测到中等风险化合物，需要关注",
            RiskLevel.LOW: "检测到低风险化合物，在可控范围内"
        }

        return {
            "risk_level": max_risk.value,
            "confidence": avg_confidence,
            "description": descriptions.get(max_risk, "")
        }

    def plan_pollution_control(self, target_pollutant: str,
                              current_emission: float,
                              reduction_target: float) -> TechRecommendation:
        """
        规划污染控制技术路线

        Args:
            target_pollutant: 目标污染物
            current_emission: 当前排放量
            reduction_target: 减排目标 (0-1)

        Returns:
            技术推荐
        """
        target_amount = current_emission * (1 - reduction_target)
        target_efficiency = reduction_target * 100

        # 查找适用的技术
        applicable_techs = []
        for tech in self._technology_db.values():
            if target_pollutant in tech.applicable_pollutants:
                tech_efficiency = tech.removal_efficiency.get(target_pollutant, 0)
                if tech_efficiency >= target_efficiency * 0.8:  # 允许一定余量
                    applicable_techs.append(tech)

        # 构建技术路线
        routes = []

        # 单一技术路线
        for tech in applicable_techs:
            route = self._build_single_tech_route(tech, current_emission, target_pollutant)
            if route:
                routes.append(route)

        # 组合技术路线
        if len(applicable_techs) >= 2:
            for i in range(min(3, len(applicable_techs))):
                for j in range(i+1, min(3, len(applicable_techs))):
                    route = self._build_combined_route(
                        [applicable_techs[i], applicable_techs[j]],
                        current_emission, target_pollutant
                    )
                    if route:
                        routes.append(route)

        # 排序并选择最佳
        routes.sort(key=lambda r: r.payback_period)

        recommendation = TechRecommendation(
            recommendation_id=f"rec_{target_pollutant}_{int(datetime.now().timestamp())}",
            target_pollutant=target_pollutant,
            target_reduction=reduction_target,
            routes=routes,
            best_route=routes[0] if routes else None,
            alternatives=routes[1:4] if len(routes) > 1 else []
        )

        # 考虑因素
        recommendation.considerations = self._generate_considerations(
            recommendation, current_emission
        )

        return recommendation

    def _build_single_tech_route(self, tech: PollutionControlTechnology,
                               current_emission: float,
                               target_pollutant: str) -> Optional[TechnologyRoute]:
        """构建单一技术路线"""
        efficiency = tech.removal_efficiency.get(target_pollutant, 0)
        if efficiency < 50:
            return None

        # 估算处理后排放量
        final_emission = current_emission * (1 - efficiency / 100)

        # 投资回收分析
        # 假设污染罚款/税费为 5000元/吨
        annual_saving = (current_emission - final_emission) / 1000 * 5000

        payback = tech.investment_cost / max(annual_saving - tech.operating_cost, 1)

        route = TechnologyRoute(
            route_id=f"route_single_{tech.tech_id}",
            name=f"单一技术方案：{tech.name}",
            description=f"采用{tech.name}处理{target_pollutant}",
            technologies=[tech],
            total_investment=tech.investment_cost,
            annual_operating_cost=tech.operating_cost,
            expected_efficiency=efficiency,
            payback_period=payback,
            pros=[f"去除效率高达{efficiency}%", f"年节约成本约{annual_saving:.0f}万元"],
            cons=[f"投资较大：{tech.investment_cost}万元", f"运行成本：{tech.operating_cost}万元/年"],
            suitability="适合新建项目或改造项目"
        )

        return route

    def _build_combined_route(self, techs: List[PollutionControlTechnology],
                            current_emission: float,
                            target_pollutant: str) -> Optional[TechnologyRoute]:
        """构建组合技术路线"""
        # 计算组合效率（串联）
        combined_efficiency = 1.0
        for tech in techs:
            eff = tech.removal_efficiency.get(target_pollutant, 0) / 100
            combined_efficiency *= (1 - eff)
        combined_efficiency = (1 - combined_efficiency) * 100

        total_investment = sum(t.investment_cost for t in techs) * 0.9  # 组合优惠
        total_operating = sum(t.operating_cost for t in techs) * 0.95

        final_emission = current_emission * (1 - combined_efficiency / 100)
        annual_saving = (current_emission - final_emission) / 1000 * 5000
        payback = total_investment / max(annual_saving - total_operating, 1)

        route = TechnologyRoute(
            route_id=f"route_combined_{'_'.join(t.tech_id for t in techs)}",
            name=f"组合技术方案：{' + '.join(t.name for t in techs)}",
            description=f"采用多级组合技术处理{target_pollutant}",
            technologies=techs,
            total_investment=total_investment,
            annual_operating_cost=total_operating,
            expected_efficiency=combined_efficiency,
            payback_period=payback,
            pros=[f"组合去除效率可达{combined_efficiency:.0f}%", "稳定性好，互为备份"],
            cons=[f"总投资较大：{total_investment:.0f}万元", "系统复杂度高"],
            suitability="适合高标准排放要求"
        )

        return route

    def _generate_considerations(self, recommendation: TechRecommendation,
                               current_emission: float) -> List[str]:
        """生成考虑因素"""
        considerations = []

        if not recommendation.best_route:
            return ["未找到合适的技术方案"]

        best = recommendation.best_route

        considerations.append(f"💰 经济性：最佳方案投资回收期约{best.payback_period:.1f}年")

        if best.expected_efficiency >= 95:
            considerations.append("🌿 环保性：该方案可达高去除效率")
        elif best.expected_efficiency >= 80:
            considerations.append("⚖️ 环保性：该方案性价比较高")

        considerations.append(f"📐 空间：{best.technologies[0].space_requirement}")

        if best.technologies[0].maintenance_difficulty == "high":
            considerations.append("⚠️ 维护难度较高，需要专业人员")

        considerations.append(f"🔄 建议：先进行小规模试验，验证效果后再大规模实施")

        return considerations

    def mine_literature(self, query: str, max_results: int = 10) -> List[LiteratureReference]:
        """
        挖掘文献

        Args:
            query: 查询关键词
            max_results: 最大结果数

        Returns:
            相关文献列表
        """
        results = []

        for lit in self._literature_db.values():
            # 简单的关键词匹配
            score = 0
            query_lower = query.lower()

            for keyword in lit.keywords:
                if keyword.lower() in query_lower or query_lower in keyword.lower():
                    score += 1
            if query_lower in lit.title.lower():
                score += 2

            if score > 0:
                results.append((lit, score))

        # 排序
        results.sort(key=lambda x: x[1], reverse=True)

        return [r[0] for r in results[:max_results]]

    def discover_knowledge(self, project_data: Dict) -> List[KnowledgeDiscovery]:
        """
        从项目数据中发现新知识

        Args:
            project_data: 项目数据

        Returns:
            知识发现列表
        """
        discoveries = []

        # 1. 污染物关联发现
        process_flow = project_data.get("process_flow", [])
        emissions = project_data.get("emissions", [])

        # 2. 工艺-污染物关联
        if process_flow and emissions:
            for process in process_flow:
                for emission in emissions:
                    if self._has_correlation(process, emission):
                        discoveries.append(KnowledgeDiscovery(
                            discovery_id=f"disc_{len(discoveries)}",
                            discovery_type="correlation",
                            title=f"发现{process}与{emission['pollutant']}的新关联",
                            description=f"基于项目数据分析，{process}工艺可能是{emission['pollutant']}的重要来源",
                            evidence=["项目实测数据", "行业案例分析"],
                            confidence=0.75,
                            novelty=0.6,
                            implications=["优化该工艺可能有效减排", "值得深入研究"]
                        ))

        # 3. 最佳可行技术发现
        if process_flow:
            for process in process_flow:
                best_tech = self._find_best_available_tech(process)
                if best_tech:
                    discoveries.append(KnowledgeDiscovery(
                        discovery_id=f"disc_{len(discoveries)}",
                        discovery_type="best_practice",
                        title=f"{process}最佳可行技术(BAT)",
                        description=f"针对{process}工艺，推荐使用{best_tech.name}",
                        evidence=["行业调研", "案例分析"],
                        confidence=0.85,
                        novelty=0.3,
                        implications=["可直接应用于项目改造", "供参考制定排放标准"]
                    ))

        return discoveries

    def _has_correlation(self, process: str, emission: Dict) -> bool:
        """判断工艺与排放是否有相关性"""
        # 简化实现
        emission_pollutant = emission.get("pollutant", "").lower()
        process_lower = process.lower()

        correlations = {
            "喷漆": ["VOCs", "甲苯", "二甲苯", "苯"],
            "焊接": ["烟尘", "Mn", "NOx"],
            "电镀": ["COD", "总铬", "总镍", "Zn"],
            "印刷": ["VOCs", "苯", "酮类"],
            "铸造": ["颗粒物", "SO2", "粉尘"],
        }

        pollutants = correlations.get(process_lower, [])
        return any(p.lower() in emission_pollutant or emission_pollutant in p.lower()
                  for p in pollutants)

    def _find_best_available_tech(self, process: str) -> Optional[PollutionControlTechnology]:
        """找到最佳可用技术"""
        process_tech_map = {
            "喷漆": "tech_rco",
            "印刷": "tech_activated_carbon",
            "焊接": "tech_photooxidation",
            "电镀": "tech_mbr",
        }

        tech_id = process_tech_map.get(process)
        if tech_id:
            return self._technology_db.get(tech_id)

        return None

    def generate_research_report(self, topic: str,
                                project_context: Dict = None) -> Dict:
        """
        生成研究态势报告

        Args:
            topic: 研究主题
            project_context: 项目上下文

        Returns:
            研究报告
        """
        # 文献挖掘
        relevant_literature = self.mine_literature(topic)

        # 知识发现
        discoveries = []
        if project_context:
            discoveries = self.discover_knowledge(project_context)

        # 技术推荐
        tech_recommendation = None
        if project_context and "target_pollutant" in project_context:
            tech_recommendation = self.plan_pollution_control(
                target_pollutant=project_context["target_pollutant"],
                current_emission=project_context.get("current_emission", 1000),
                reduction_target=project_context.get("reduction_target", 0.5)
            )

        return {
            "topic": topic,
            "generated_at": datetime.now().isoformat(),
            "literature_summary": {
                "count": len(relevant_literature),
                "key_findings": [f for lit in relevant_literature for f in lit.findings[:2]]
            },
            "knowledge_discoveries": [
                {"title": d.title, "confidence": d.confidence}
                for d in discoveries
            ],
            "technology_recommendation": {
                "best_route": tech_recommendation.best_route.name if tech_recommendation and tech_recommendation.best_route else None,
                "expected_efficiency": tech_recommendation.best_route.expected_efficiency if tech_recommendation and tech_recommendation.best_route else None
            },
            "conclusions": self._generate_conclusions(topic, relevant_literature, discoveries)
        }

    def _generate_conclusions(self, topic: str,
                            literature: List[LiteratureReference],
                            discoveries: List[KnowledgeDiscovery]) -> List[str]:
        """生成结论"""
        conclusions = []

        if literature:
            conclusions.append(f"基于{len(literature)}篇文献分析，{topic}领域研究活跃")

        if discoveries:
            conclusions.append(f"发现{len(discoveries)}条新知识关联，具有潜在应用价值")

        if not conclusions:
            conclusions.append(f"关于{topic}的知识库还在积累中，建议持续关注")

        conclusions.append("建议结合项目实际情况，选择适合的技术路线")

        return conclusions

    def to_dict(self) -> Dict[str, Any]:
        """导出状态"""
        return {
            "compound_db_size": len(self._compound_db),
            "technology_db_size": len(self._technology_db),
            "literature_db_size": len(self._literature_db),
            "capabilities": [
                "未知污染物检测",
                "技术路线规划",
                "文献挖掘",
                "知识发现"
            ]
        }


# 全局单例
_scientist_instance: Optional[EnvironmentalAIScientist] = None
_scientist_lock = threading.Lock()


def get_ai_scientist(knowledge_graph=None) -> EnvironmentalAIScientist:
    """获取环境AI科学家实例"""
    global _scientist_instance
    if _scientist_instance is None:
        with _scientist_lock:
            if _scientist_instance is None:
                _scientist_instance = EnvironmentalAIScientist(knowledge_graph)
    return _scientist_instance
