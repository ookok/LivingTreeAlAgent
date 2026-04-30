"""
环保分析智能体 (EIA Analyst Agent)
=================================

职责：
1. 识别污染物
2. 分析环境影响
3. 匹配控制措施
4. 合规性检查

作者：Hermes Desktop AI Team
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from business.eia_process import ProcessType, Pollutant, EIAMitigation, PollutantType

logger = logging.getLogger(__name__)


@dataclass
class EIAAnalysisResult:
    """环保分析结果"""
    # 污染物清单
    air_pollutants: List[Pollutant] = field(default_factory=list)
    water_pollutants: List[Pollutant] = field(default_factory=list)
    solid_wastes: List[Pollutant] = field(default_factory=list)
    noise_sources: List[Pollutant] = field(default_factory=list)

    # 防治措施
    mitigation_measures: List[EIAMitigation] = field(default_factory=list)

    # 环境影响分析
    environmental_impact: Dict[str, Any] = field(default_factory=dict)

    # 合规性
    compliance_status: Dict[str, bool] = field(default_factory=dict)

    # 风险评估
    risk_assessment: Dict[str, Any] = field(default_factory=dict)

    # 置信度
    confidence: float = 0.0


class EIAAnalyst:
    """
    环保分析智能体
    """

    # 污染物产生系数 (kg/吨产品 或 kg/h)
    POLLUTANT_COEFFICIENTS = {
        "喷砂": {"颗粒物": {"amount": 0.8, "unit": "kg/h", "note": "钢砂/石英砂"}},
        "喷漆": {"VOCs": {"amount": 2.5, "unit": "kg/h", "note": "苯系物/酯类"},
                 "漆雾": {"amount": 0.3, "unit": "kg/h", "note": ""}},
        "打磨": {"颗粒物": {"amount": 0.4, "unit": "kg/h", "note": "金属粉尘"}},
        "焊接": {"烟尘": {"amount": 0.5, "unit": "kg/h", "note": "金属氧化物"},
                "NOx": {"amount": 0.1, "unit": "kg/h", "note": ""}},
        "固化": {"VOCs": {"amount": 0.3, "unit": "kg/h", "note": "有机废气"}},
        "磷化": {"磷化渣": {"amount": 0.2, "unit": "kg/h", "note": "危险废物"},
                "COD": {"amount": 0.5, "unit": "kg/h", "note": ""}},
        "除油": {"石油类": {"amount": 0.3, "unit": "kg/h", "note": ""},
                "COD": {"amount": 1.0, "unit": "kg/h", "note": ""}},
        "水洗": {"COD": {"amount": 0.2, "unit": "kg/h", "note": ""},
                "SS": {"amount": 0.3, "unit": "kg/h", "note": ""}},
        "酸洗": {"HCl": {"amount": 0.2, "unit": "kg/h", "note": ""},
                "COD": {"amount": 0.3, "unit": "kg/h", "note": ""}},
        "碱洗": {"pH": {"amount": 9, "unit": "", "note": "偏碱"},
                "COD": {"amount": 0.3, "unit": "kg/h", "note": ""}},
    }

    # 噪声源
    NOISE_SOURCES = {
        "喷砂": {"level": 90, "unit": "dB(A)", "type": "设备噪声"},
        "打磨": {"level": 85, "unit": "dB(A)", "type": "设备噪声"},
        "焊接": {"level": 80, "unit": "dB(A)", "type": "设备噪声"},
        "空压机": {"level": 85, "unit": "dB(A)", "type": "设备噪声"},
        "固化炉": {"level": 70, "unit": "dB(A)", "type": "辅助噪声"},
    }

    # 排放标准
    EMISSION_STANDARDS = {
        "颗粒物": {"standard": "GB 16297-1996", "limit": 20, "unit": "mg/m³"},
        "VOCs": {"standard": "GB 16297-1996", "limit": 60, "unit": "mg/m³"},
        "SO2": {"standard": "GB 16297-1996", "limit": 50, "unit": "mg/m³"},
        "NOx": {"standard": "GB 16297-1996", "limit": 120, "unit": "mg/m³"},
        "HCl": {"standard": "GB 16297-1996", "limit": 30, "unit": "mg/m³"},
        "COD": {"standard": "GB 8978-1996", "limit": 100, "unit": "mg/L"},
        "石油类": {"standard": "GB 8978-1996", "limit": 5, "unit": "mg/L"},
        "SS": {"standard": "GB 8978-1996", "limit": 70, "unit": "mg/L"},
    }

    # 防治措施库
    MITIGATION_MEASURES = {
        "废气": [
            {"type": "布袋除尘", "efficiency": 95, "cost": 15, "适用": ["喷砂", "打磨", "焊接"]},
            {"type": "水帘除漆雾", "efficiency": 80, "cost": 20, "适用": ["喷漆"]},
            {"type": "活性炭吸附", "efficiency": 85, "cost": 25, "适用": ["喷漆", "固化"]},
            {"type": "RCO催化燃烧", "efficiency": 95, "cost": 50, "适用": ["喷漆", "固化"]},
            {"type": "湿式除尘", "efficiency": 85, "cost": 12, "适用": ["喷砂"]},
        ],
        "废水": [
            {"type": "混凝沉淀", "efficiency": 70, "cost": 10, "适用": ["磷化", "除油"]},
            {"type": "生化处理", "efficiency": 80, "cost": 30, "适用": ["水洗", "除油"]},
            {"type": "气浮", "efficiency": 75, "cost": 15, "适用": ["除油"]},
            {"type": "中和调节", "efficiency": 90, "cost": 8, "适用": ["酸洗", "碱洗"]},
        ],
        "固废": [
            {"type": "分类收集", "efficiency": 100, "cost": 2, "适用": ["喷砂", "磷化", "喷漆"]},
            {"type": "资质单位处置", "efficiency": 100, "cost": 5, "适用": ["磷化渣", "漆渣"]},
        ],
        "噪声": [
            {"type": "隔声房", "efficiency": 20, "cost": 8, "适用": ["喷砂", "打磨"]},
            {"type": "减振基础", "efficiency": 15, "cost": 5, "适用": ["空压机"]},
            {"type": "消声器", "efficiency": 10, "cost": 3, "适用": ["空压机"]},
        ],
    }

    def __init__(self):
        self.pollutant_coefficients = self.POLLUTANT_COEFFICIENTS
        self.emission_standards = self.EMISSION_STANDARDS
        self.mitigation_db = self.MITIGATION_MEASURES
        logger.info("环保分析智能体初始化完成")

    def analyze(self, process_chain: List[str], equipment: List[str] = None) -> EIAAnalysisResult:
        """
        分析工艺链的环境影响

        Args:
            process_chain: 完整工艺链
            equipment: 设备列表

        Returns:
            EIAAnalysisResult: 环保分析结果
        """
        logger.info(f"开始环保分析: {len(process_chain)}道工序")

        result = EIAAnalysisResult()

        # 1. 识别废气污染物
        result.air_pollutants = self._identify_air_pollutants(process_chain)

        # 2. 识别废水污染物
        result.water_pollutants = self._identify_water_pollutants(process_chain)

        # 3. 识别固体废物
        result.solid_wastes = self._identify_solid_wastes(process_chain)

        # 4. 识别噪声源
        result.noise_sources = self._identify_noise_sources(process_chain, equipment)

        # 5. 匹配防治措施
        result.mitigation_measures = self._match_mitigation_measures(result)

        # 6. 分析环境影响
        result.environmental_impact = self._analyze_environmental_impact(result)

        # 7. 合规性检查
        result.compliance_status = self._check_compliance(result)

        # 8. 风险评估
        result.risk_assessment = self._assess_risks(result)

        # 9. 计算置信度
        result.confidence = self._calculate_confidence(result)

        logger.info(f"环保分析完成: {len(result.air_pollutants)}种废气, "
                   f"{len(result.water_pollutants)}种废水, {len(result.solid_wastes)}种固废")
        return result

    def _identify_air_pollutants(self, chain: List[str]) -> List[Pollutant]:
        """识别废气污染物"""
        pollutants = []

        for step in chain:
            if step in self.pollutant_coefficients:
                for poll_name, data in self.pollutant_coefficients[step].items():
                    # 映射到PollutantType
                    poll_type = self._map_pollutant_type(poll_name)

                    pollutant = Pollutant(
                        type=poll_type,
                        name=poll_name,
                        code=self._generate_code("G", len(pollutants) + 1),
                        amount=data["amount"],
                        unit=data["unit"],
                        destination="废气处理系统",
                        environmental_impact=self._get_impact_description(poll_name),
                    )

                    # 添加标准信息
                    if poll_name in self.emission_standards:
                        std = self.emission_standards[poll_name]
                        pollutant.standard = std["standard"]
                        pollutant.standard_limit = std["limit"]
                        pollutant.emission_concentration = data["amount"]

                    pollutants.append(pollutant)

        return pollutants

    def _identify_water_pollutants(self, chain: List[str]) -> List[Pollutant]:
        """识别废水污染物"""
        pollutants = []

        for step in chain:
            if step in self.pollutant_coefficients:
                for poll_name, data in self.pollutant_coefficients[step].items():
                    # 只处理废水相关
                    if poll_name in ["COD", "石油类", "SS", "pH"]:
                        poll_type = self._map_pollutant_type(poll_name)

                        pollutant = Pollutant(
                            type=poll_type,
                            name=poll_name,
                            code=self._generate_code("W", len(pollutants) + 1),
                            amount=data["amount"],
                            unit=data["unit"],
                            destination="废水处理系统",
                        )

                        if poll_name in self.emission_standards:
                            std = self.emission_standards[poll_name]
                            pollutant.standard = std["standard"]
                            pollutant.standard_limit = std["limit"]

                        pollutants.append(pollutant)

        return pollutants

    def _identify_solid_wastes(self, chain: List[str]) -> List[Pollutant]:
        """识别固体废物"""
        wastes = []

        waste_map = {
            "喷砂": ("废砂料", "一般固废", "一般固废"),
            "喷漆": ("漆渣", "危险废物(HW12)", "危险废物"),
            "磷化": ("磷化渣", "危险废物(HW17)", "危险废物"),
            "焊接": ("焊渣", "一般固废", "一般固废"),
            "打磨": ("金属粉尘", "一般固废", "一般固废"),
        }

        for step in chain:
            if step in waste_map:
                waste_name, hw_code, waste_type = waste_map[step]

                waste = Pollutant(
                    type=PollutantType.HAZARDOUS_WASTE if "危险" in waste_type else PollutantType.GENERAL_WASTE,
                    name=waste_name,
                    code=self._generate_code("S", len(wastes) + 1),
                    amount=0.5,  # 估算值
                    unit="kg/h",
                    destination="固废收集点",
                )

                if "危险" in waste_type:
                    waste.emission_concentration = 0
                    waste.control_measure = "资质单位处置"
                    waste.environmental_impact = "危险废物需专门处置"

                wastes.append(waste)

        return wastes

    def _identify_noise_sources(self, chain: List[str], equipment: List[str] = None) -> List[Pollutant]:
        """识别噪声源"""
        sources = []
        checked = set()

        for step in chain:
            if step in self.NOISE_SOURCES and step not in checked:
                data = self.NOISE_SOURCES[step]

                source = Pollutant(
                    type=PollutantType.NOISE,
                    name=f"{step}噪声",
                    code=self._generate_code("N", len(sources) + 1),
                    amount=data["level"],
                    unit=data["unit"],
                    environmental_impact=f"噪声级{data['level']}dB(A), 影响范围约50m"
                )

                sources.append(source)
                checked.add(step)

        # 检查设备
        if equipment:
            for eq in equipment:
                if eq in self.NOISE_SOURCES and eq not in checked:
                    data = self.NOISE_SOURCES[eq]
                    source = Pollutant(
                        type=PollutantType.NOISE,
                        name=f"{eq}噪声",
                        amount=data["level"],
                        unit=data["unit"],
                    )
                    sources.append(source)

        return sources

    def _match_mitigation_measures(self, result: EIAAnalysisResult) -> List[EIAMitigation]:
        """匹配防治措施"""
        measures = []

        # 废气防治
        if result.air_pollutants:
            for poll in result.air_pollutants:
                for category, measure_list in self.mitigation_db.items():
                    if category != "废气":
                        continue
                    for m in measure_list:
                        if poll.name in ["颗粒物", "烟尘"] and "除尘" in m["type"]:
                            measure = EIAMitigation(
                                type="废气",
                                measure=m["type"],
                                removal_efficiency=m["efficiency"],
                                investment=m["cost"],
                                applicable_processes=m["适用"],
                            )
                            if measure.measure not in [x.measure for x in measures]:
                                measures.append(measure)
                        elif poll.name == "VOCs" and any(x in m["type"] for x in ["活性炭", "RCO"]):
                            measure = EIAMitigation(
                                type="废气",
                                measure=m["type"],
                                removal_efficiency=m["efficiency"],
                                investment=m["cost"],
                                applicable_processes=m["适用"],
                            )
                            if measure.measure not in [x.measure for x in measures]:
                                measures.append(measure)

        # 废水防治
        if result.water_pollutants:
            for poll in result.water_pollutants:
                for category, measure_list in self.mitigation_db.items():
                    if category != "废水":
                        continue
                    for m in measure_list:
                        measure = EIAMitigation(
                            type="废水",
                            measure=m["type"],
                            removal_efficiency=m["efficiency"],
                            investment=m["cost"],
                            applicable_processes=m["适用"],
                        )
                        if measure.measure not in [x.measure for x in measures]:
                            measures.append(measure)

        # 固废防治
        if result.solid_wastes:
            for waste in result.solid_wastes:
                measure = EIAMitigation(
                    type="固废",
                    measure="分类收集" + ("(危废资质处置)" if "危险" in waste.name else ""),
                    removal_efficiency=100,
                    investment=2,
                    applicable_processes=[waste.name],
                )
                if measure.measure not in [x.measure for x in measures]:
                    measures.append(measure)

        # 噪声防治
        if result.noise_sources:
            for m in self.mitigation_db["噪声"]:
                measure = EIAMitigation(
                    type="噪声",
                    measure=m["type"],
                    removal_efficiency=m["efficiency"],
                    investment=m["cost"],
                    applicable_processes=m["适用"],
                )
                if measure.measure not in [x.measure for x in measures]:
                    measures.append(measure)

        return measures

    def _analyze_environmental_impact(self, result: EIAAnalysisResult) -> Dict[str, Any]:
        """分析环境影响"""
        impact = {
            "大气影响": "",
            "水体影响": "",
            "土壤影响": "",
            "声环境影响": "",
            "总体评价": "",
        }

        # 大气影响
        if result.air_pollutants:
            voc_poll = [p for p in result.air_pollutants if "VOC" in p.name or "VOCs" in p.name]
            dust_poll = [p for p in result.air_pollutants if "颗粒" in p.name or "粉尘" in p.name]

            if voc_poll:
                impact["大气影响"] = f"VOCs排放影响范围约200m，需重点管控"
            if dust_poll:
                impact["大气影响"] += f"粉尘排放影响范围约100m"

        # 水体影响
        if result.water_pollutants:
            impact["水体影响"] = "生产废水经处理后达标排放，对纳污水体影响可控"

        # 声环境影响
        if result.noise_sources:
            max_noise = max([p.amount for p in result.noise_sources if isinstance(p.amount, (int, float))])
            impact["声环境影响"] = f"主要噪声源{max_noise}dB(A), 厂界噪声可能超标，需采取隔声措施"

        # 总体评价
        impact["总体评价"] = "本项目废气为主要污染因素，需重点治理"

        return impact

    def _check_compliance(self, result: EIAAnalysisResult) -> Dict[str, bool]:
        """合规性检查"""
        status = {}

        # 废气合规性
        for poll in result.air_pollutants:
            if poll.standard_limit:
                # 简化：假设处理效率后的排放达标
                is_compliant = poll.emission_concentration <= poll.standard_limit * 1.5
                status[f"废气_{poll.name}"] = is_compliant

        # 废水合规性
        for poll in result.water_pollutants:
            if poll.standard_limit:
                is_compliant = poll.amount <= poll.standard_limit * 1.2
                status[f"废水_{poll.name}"] = is_compliant

        return status

    def _assess_risks(self, result: EIAAnalysisResult) -> Dict[str, Any]:
        """风险评估"""
        risks = {
            "重大风险源": [],
            "一般风险": [],
            "风险等级": "中等",
        }

        # 识别重大风险
        for poll in result.air_pollutants:
            if "VOC" in poll.name or "VOCs" in poll.name:
                risks["重大风险源"].append(f"{poll.name}: 易燃易爆风险")

        for waste in result.solid_wastes:
            if "危险" in waste.name:
                risks["重大风险源"].append(f"{waste.name}: 危险废物泄露风险")

        # 噪声风险
        for noise in result.noise_sources:
            if noise.amount >= 85:
                risks["一般风险"].append(f"{noise.name}: 职业病风险(噪声聋)")

        # 风险等级
        if len(risks["重大风险源"]) >= 3:
            risks["风险等级"] = "重大"
        elif len(risks["重大风险源"]) >= 1:
            risks["风险等级"] = "较大"
        else:
            risks["风险等级"] = "一般"

        return risks

    def _map_pollutant_type(self, name: str) -> PollutantType:
        """映射污染物类型"""
        mapping = {
            "颗粒物": PollutantType.PARTICULATE,
            "粉尘": PollutantType.PARTICULATE,
            "VOCs": PollutantType.VOC,
            "VOC": PollutantType.VOC,
            "SO2": PollutantType.SOX,
            "NOx": PollutantType.NOX,
            "HCl": PollutantType.HCL,
            "COD": PollutantType.COD,
            "石油类": PollutantType.OIL,
            "SS": PollutantType.SS,
            "pH": PollutantType.PH,
            "噪声": PollutantType.NOISE,
            "烟尘": PollutantType.PARTICULATE,
            "漆雾": PollutantType.PARTICULATE,
        }
        return mapping.get(name, PollutantType.PARTICULATE)

    def _generate_code(self, prefix: str, index: int) -> str:
        """生成编号"""
        return f"{prefix}{index:02d}"

    def _get_impact_description(self, pollutant_name: str) -> str:
        """获取影响描述"""
        impacts = {
            "颗粒物": "影响呼吸系统，排放点下风向100m范围内浓度最高",
            "VOCs": "参与光化学反应，危害人体肝脏、肾脏、神经系统",
            "SO2": "刺激呼吸道，引起支气管炎、肺气肿",
            "NOx": "引起呼吸系统炎症，破坏臭氧层",
            "HCl": "刺激性气体，腐蚀呼吸系统",
            "COD": "消耗水体溶解氧，影响水生生物",
            "石油类": "油膜覆盖水面，影响水体复氧能力",
        }
        return impacts.get(pollutant_name, "对环境有一定影响")

    def _calculate_confidence(self, result: EIAAnalysisResult) -> float:
        """计算置信度"""
        confidence = 0.6

        if result.air_pollutants:
            confidence += 0.1
        if result.water_pollutants:
            confidence += 0.1
        if result.solid_wastes:
            confidence += 0.1
        if result.mitigation_measures:
            confidence += 0.1

        return min(confidence, 0.95)

    def analyze_to_dict(self, process_chain: List[str], equipment: List[str] = None) -> Dict[str, Any]:
        """分析并返回字典"""
        result = self.analyze(process_chain, equipment)

        return {
            "air_pollutants": [
                {
                    "name": p.name,
                    "code": p.code,
                    "amount": p.amount,
                    "unit": p.unit,
                    "standard": p.standard,
                    "limit": p.standard_limit,
                    "control": p.control_measure,
                    "impact": p.environmental_impact,
                } for p in result.air_pollutants
            ],
            "water_pollutants": [
                {
                    "name": p.name,
                    "code": p.code,
                    "amount": p.amount,
                    "unit": p.unit,
                    "standard": p.standard,
                    "limit": p.standard_limit,
                } for p in result.water_pollutants
            ],
            "solid_wastes": [
                {
                    "name": p.name,
                    "code": p.code,
                    "amount": p.amount,
                    "unit": p.unit,
                    "type": "危险废物" if "危险" in p.name else "一般固废",
                    "control": p.control_measure,
                } for p in result.solid_wastes
            ],
            "noise_sources": [
                {
                    "name": p.name,
                    "level": p.amount,
                    "unit": p.unit,
                    "impact": p.environmental_impact,
                } for p in result.noise_sources
            ],
            "mitigation_measures": [
                {
                    "type": m.type,
                    "measure": m.measure,
                    "efficiency": m.removal_efficiency,
                    "investment": m.investment,
                } for m in result.mitigation_measures
            ],
            "environmental_impact": result.environmental_impact,
            "compliance_status": result.compliance_status,
            "risk_assessment": result.risk_assessment,
            "confidence": result.confidence,
        }
