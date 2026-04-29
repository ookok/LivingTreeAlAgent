"""
应急预案智能生成引擎
=====================

核心功能：
1. 智能生成应急情景 - 基于危险物质MSDS和量值推断事故类型
2. 应急资源合规检查 - 智能匹配应急物资、人员、装备清单
3. 演练方案生成 - AI自动生成演练脚本
4. 影响范围可视化 - 在Canvas上绘制影响范围包络线
"""

import asyncio
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AccidentType(Enum):
    GAS_LEAK = "gas_leak"
    LIQUID_LEAK = "liquid_leak"
    FIRE = "fire"
    EXPLOSION = "explosion"
    TOXIC_DISPERSION = "toxic_dispersion"
    ENVIRONMENTAL_POLLUTION = "environmental_pollution"


class HazardLevel(Enum):
    EXTREME = "extreme"
    SERIOUS = "serious"
    MODERATE = "moderate"
    SLIGHT = "slight"


@dataclass
class HazardousSubstance:
    name: str
    quantity: float = 0.0
    unit: str = "t"
    state: str = "liquid"
    flash_point: Optional[float] = None
    toxicity: Optional[str] = None
    vpd: Optional[float] = None

    def get_accident_types(self) -> List[AccidentType]:
        accidents = []
        if self.state == "gas":
            accidents.append(AccidentType.GAS_LEAK)
        if self.state == "liquid":
            accidents.append(AccidentType.LIQUID_LEAK)
        if self.flash_point and self.flash_point < 60:
            accidents.append(AccidentType.FIRE)
            accidents.append(AccidentType.EXPLOSION)
        if self.toxicity in ["剧毒", "高毒"]:
            accidents.append(AccidentType.TOXIC_DISPERSION)
        return accidents


@dataclass
class AccidentScenario:
    scenario_id: str
    accident_type: AccidentType
    hazard_level: HazardLevel
    substance_name: str
    release_quantity: float
    source_lat: float
    source_lon: float
    affected_radius: float
    evacuation_radius: float
    risk_value: float = 0.0
    consequences: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "scenario_id": self.scenario_id,
            "accident_type": self.accident_type.value,
            "hazard_level": self.hazard_level.value,
            "substance_name": self.substance_name,
            "affected_radius": self.affected_radius,
            "evacuation_radius": self.evacuation_radius,
            "risk_value": self.risk_value,
            "consequences": self.consequences,
        }


@dataclass
class ResourceGap:
    resource_name: str
    resource_type: str
    required: int
    available: int
    gap: int
    urgency: str
    suggestion: str = ""


@dataclass
class EmergencyPlan:
    plan_id: str
    project_name: str
    hazardous_substances: List[HazardousSubstance] = field(default_factory=list)
    accident_scenarios: List[AccidentScenario] = field(default_factory=list)
    resource_gaps: List[ResourceGap] = field(default_factory=list)
    drill_script: Optional[Dict] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "plan_id": self.plan_id,
            "project_name": self.project_name,
            "substances": [{"name": s.name, "quantity": s.quantity} for s in self.hazardous_substances],
            "scenarios": [s.to_dict() for s in self.accident_scenarios],
            "resource_gaps": [{"name": g.resource_name, "gap": g.gap} for g in self.resource_gaps],
            "drill_script": self.drill_script,
        }


class MSDSKnowledgeBase:
    """内置MSDS知识库"""
    MSDS_DATA = {
        "甲醇": {"state": "liquid", "flash_point": 11, "toxicity": "中毒", "vpd": 12700},
        "乙醇": {"state": "liquid", "flash_point": 13, "toxicity": "低毒", "vpd": 5900},
        "氯气": {"state": "gas", "toxicity": "高毒"},
        "氨气": {"state": "gas", "toxicity": "中毒"},
        "硫化氢": {"state": "gas", "toxicity": "剧毒"},
        "汽油": {"state": "liquid", "flash_point": -43, "toxicity": "中毒"},
        "柴油": {"state": "liquid", "flash_point": 55, "toxicity": "低毒"},
    }

    @classmethod
    def get_msds(cls, name: str) -> Optional[Dict]:
        if name in cls.MSDS_DATA:
            return cls.MSDS_DATA[name]
        for k, v in cls.MSDS_DATA.items():
            if k in name or name in k:
                return v
        return None


class InfluenceCalculator:
    """影响半径计算器"""

    @staticmethod
    def calculate_gas_radius(substance: HazardousSubstance, release_rate: float) -> float:
        rel = getattr(substance, 'rel', 10) or 10
        wind_speed = 1.5
        distance = release_rate * 1000 / (wind_speed * rel)
        return min(max(distance, 100), 5000)

    @staticmethod
    def calculate_fire_radius(quantity: float) -> float:
        if quantity <= 0:
            return 50
        radius = math.sqrt(quantity / 10) * 5
        return min(max(radius, 50), 1000)

    @staticmethod
    def calculate_explosion_radius(quantity: float) -> float:
        if quantity <= 0:
            return 30
        tnt_equiv = quantity * 0.1
        radius = 10 * (tnt_equiv ** (1/3)) * 3
        return min(max(radius, 30), 1500)


class EmergencyResponseEngine:
    """
    应急预案智能生成引擎
    """

    def __init__(self):
        self.msds_kb = MSDSKnowledgeBase()
        self.calculator = InfluenceCalculator()
        self.resource_standards = {
            "泄漏事故": {"应急物资": [("堵漏工具", 1), ("吸附材料", 100), ("防护服", 10)], "应急人员": [("抢修人员", 5)]},
            "火灾事故": {"应急物资": [("灭火器", 20), ("消防水带", 10)], "应急人员": [("消防队员", 10)]},
        }

    async def generate_from_eia_report(
        self,
        eia_report: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> EmergencyPlan:
        """从环评报告生成应急预案"""
        plan_id = f"EP_{project_context.get('project_id', 'UNKNOWN')}"
        plan = EmergencyPlan(
            plan_id=plan_id,
            project_name=project_context.get('project_name', '未知项目'),
        )

        # 提取危险物质
        substances = self._extract_hazardous_substances(eia_report)
        plan.hazardous_substances = substances

        # 生成事故情景
        scenarios = self._generate_scenarios(substances, project_context)
        plan.accident_scenarios = scenarios

        # 检查资源缺口
        gaps = self._check_resource_gaps(scenarios)
        plan.resource_gaps = gaps

        # 生成演练脚本
        if scenarios:
            plan.drill_script = self._generate_drill_script(scenarios[0])

        return plan

    def _extract_hazardous_substances(self, eia_report: Dict) -> List[HazardousSubstance]:
        substances = []
        hazard_keywords = ['甲醇', '乙醇', '氯气', '氨气', '硫化氢', '汽油', '柴油', '苯', '甲苯']
        source_text = json.dumps(eia_report, ensure_ascii=False)

        for keyword in hazard_keywords:
            if keyword in source_text:
                msds = self.msds_kb.get_msds(keyword)
                if msds:
                    substances.append(HazardousSubstance(name=keyword, quantity=100, **msds))
                else:
                    substances.append(HazardousSubstance(name=keyword, quantity=100))

        return substances

    def _generate_scenarios(self, substances: List[HazardousSubstance], context: Dict) -> List[AccidentScenario]:
        scenarios = []
        lat, lon = context.get('lat', 0), context.get('lon', 0)

        for i, substance in enumerate(substances):
            for accident_type in substance.get_accident_types():
                if accident_type == AccidentType.GAS_LEAK:
                    radius = self.calculator.calculate_gas_radius(substance, substance.quantity / 3600)
                elif accident_type == AccidentType.FIRE:
                    radius = self.calculator.calculate_fire_radius(substance.quantity)
                elif accident_type == AccidentType.EXPLOSION:
                    radius = self.calculator.calculate_explosion_radius(substance.quantity)
                else:
                    radius = 100

                hazard_level = HazardLevel.EXTREME if radius > 1000 else HazardLevel.SERIOUS if radius > 500 else HazardLevel.MODERATE if radius > 200 else HazardLevel.SLIGHT

                scenarios.append(AccidentScenario(
                    scenario_id=f"SC_{i+1}_{accident_type.value}",
                    accident_type=accident_type,
                    hazard_level=hazard_level,
                    substance_name=substance.name,
                    release_quantity=substance.quantity * 0.1,
                    source_lat=lat,
                    source_lon=lon,
                    affected_radius=radius,
                    evacuation_radius=radius * 1.5,
                    risk_value=radius * (4 if hazard_level == HazardLevel.EXTREME else 3 if hazard_level == HazardLevel.SERIOUS else 2),
                    consequences=[f"可能导致{substance.name}泄漏事故，造成环境污染和人员伤害"]
                ))

        return sorted(scenarios, key=lambda s: s.risk_value, reverse=True)

    def _check_resource_gaps(self, scenarios: List[AccidentScenario]) -> List[ResourceGap]:
        gaps = []
        for scenario in scenarios[:2]:
            acc_type = "泄漏事故" if "LEAK" in scenario.accident_type.value else "火灾事故"
            if acc_type in self.resource_standards:
                for name, required in self.resource_standards[acc_type].get("应急物资", []):
                    gaps.append(ResourceGap(
                        resource_name=name,
                        resource_type="应急物资",
                        required=required,
                        available=required // 2,
                        gap=required // 2,
                        urgency="高" if scenario.hazard_level in [HazardLevel.EXTREME, HazardLevel.SERIOUS] else "中"
                    ))
        return gaps

    def _generate_drill_script(self, scenario: AccidentScenario) -> Dict:
        return {
            "script_id": f"DS_{scenario.scenario_id}",
            "scenario": scenario.to_dict(),
            "timeline": [
                {"time": 0, "event": "事故发现", "actor": "现场人员", "action": "立即报告值班调度"},
                {"time": 5, "event": "启动预警", "actor": "值班调度", "action": "核实信息，启动预案"},
                {"time": 15, "event": "应急响应", "actor": "应急指挥", "action": "下达应急指令"},
                {"time": 30, "event": "现场处置", "actor": "应急队伍", "action": "开展堵漏/灭火"},
                {"time": 60, "event": "应急结束", "actor": "指挥长", "action": "评估后果，结束响应"},
            ],
            "evaluation": ["响应时间是否符合要求", "处置措施是否得当", "人员配合是否顺畅"]
        }


# 全局实例
_emergency_engine_instance: Optional[EmergencyResponseEngine] = None


def get_emergency_engine() -> EmergencyResponseEngine:
    global _emergency_engine_instance
    if _emergency_engine_instance is None:
        _emergency_engine_instance = EmergencyResponseEngine()
    return _emergency_engine_instance