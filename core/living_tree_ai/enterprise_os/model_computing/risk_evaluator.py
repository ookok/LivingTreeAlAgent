"""
风险评价引擎 (Risk Evaluator)

实现环境风险评价和安全生产风险评价。

支持：
1. LS危险度评价（事故可能性×后果严重度）
2. 环境风险扩散模型
3. 重大危险源辨识
4. 风险等级划分

使用方法：
```python
evaluator = get_risk_evaluator()

# 危险度评价
result = await evaluator.ls_evaluation(
    project_id="PROJ001",
    scenario={
        "name": "储罐泄漏",
        "frequency": 1e-4,  # 每年发生次数
        "consequence": {
            "type": "中毒",
            "severity": "严重",
            "affected_area": 100,  # m2
            "casualties": 3,  # 死亡人数
        }
    }
)

# 重大危险源辨识
result = await evaluator.identify_major_hazard_sources(
    project_id="PROJ001",
    inventory=[{"name": "液氨", "amount": 50, "threshold": 10}]
)
```
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
import math


class RiskType(Enum):
    """风险类型"""
    ENVIRONMENTAL = "environmental"           # 环境风险
    SAFETY = "safety"                         # 安全风险
    OCCUPATIONAL = "occupational"             # 职业健康风险
    SOCIAL = "social"                         # 社会风险


class RiskLevel(Enum):
    """风险等级"""
    EXTREME = "extreme"                       # 重大风险（红）
    HIGH = "high"                             # 较大风险（橙）
    MEDIUM = "medium"                         # 一般风险（黄）
    LOW = "low"                              # 低风险（蓝）
    NEGLIGIBLE = "negligible"                # 可忽略风险（绿）

    @property
    def color(self) -> str:
        colors = {
            "extreme": "#FF0000",
            "high": "#FFA500",
            "medium": "#FFFF00",
            "low": "#0000FF",
            "negligible": "#00FF00",
        }
        return colors.get(self.value, "#808080")

    @property
    def description(self) -> str:
        descs = {
            "extreme": "极其严重，必须立即采取措施",
            "high": "后果严重，必须采取控制措施",
            "medium": "可能造成伤害，可接受但需关注",
            "low": "基本无风险",
            "negligible": "可以忽略",
        }
        return descs.get(self.value, "")


@dataclass
class RiskScenario:
    """风险情景"""
    scenario_id: str
    project_id: str
    name: str
    description: str

    risk_type: RiskType = RiskType.ENVIRONMENTAL

    frequency: float = 1e-3
    frequency_source: str = "analysis"

    consequence_type: str = ""
    severity: str = "moderate"

    affected_area: float = 0.0
    casualties: int = 0
    economic_loss: float = 0.0
    environmental_damage: str = ""

    existing_controls: List[str] = field(default_factory=list)
    proposed_controls: List[str] = field(default_factory=list)

    risk_value: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW

    created_at: datetime = field(default_factory=datetime.now)
    analyst: str = "system"


@dataclass
class RiskConsequence:
    """风险后果"""
    type: str
    severity: float = 5.0
    probability: float = 0.5

    fatalities: int = 0
    injuries: int = 0
    evacuees: int = 0
    economic_loss: float = 0.0

    affected_ecosystem: str = ""
    contamination_area: float = 0.0
    contamination_duration: str = ""

    public_impact: str = ""
    media_impact: bool = False


@dataclass
class RiskEvaluationResult:
    """风险评价结果"""
    project_id: str
    evaluation_type: str

    overall_risk_level: RiskLevel
    overall_risk_value: float

    risk_matrix: Dict[str, Any] = field(default_factory=dict)
    scenarios: List[RiskScenario] = field(default_factory=list)
    major_hazard_sources: List[Dict[str, Any]] = field(default_factory=list)
    risk_control_measures: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    confidence: float = 0.8
    quality_score: float = 0.85

    evaluated_at: datetime = field(default_factory=datetime.now)
    evaluator: str = "system"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "evaluation_type": self.evaluation_type,
            "overall_risk_level": self.overall_risk_level.value,
            "overall_risk_value": self.overall_risk_value,
            "scenarios_count": len(self.scenarios),
            "major_hazard_sources_count": len(self.major_hazard_sources),
            "confidence": self.confidence,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


class RiskEvaluator:
    """
    风险评价引擎

    支持多种风险评价方法：
    1. LS法（危险度评价）
    2. QRA（定量风险评价）
    3. 重大危险源辨识
    """

    LS_PARAMS = {
        "frequency_score": {
            "1e-4": 1,
            "1e-3": 2,
            "1e-2": 3,
            "1e-1": 4,
            "1e0": 5,
        },
        "severity_score": {
            "negligible": 1,
            "moderate": 2,
            "critical": 3,
            "catastrophic": 4,
        }
    }

    RISK_MATRIX = [
        [1, 2, 3, 4, 5],
        [2, 3, 4, 5, 6],
        [3, 4, 5, 6, 7],
        [4, 5, 6, 7, 8],
    ]

    MAJOR_HAZARD_THRESHOLDS = {
        "液氨": 10,
        "液氯": 5,
        "甲醇": 500,
        "乙醇": 500,
        "苯": 50,
        "甲苯": 500,
        "二甲苯": 500,
        "环氧乙烷": 10,
        "丙烯腈": 50,
        "氰化物": 1,
        "砷化物": 1,
        "汞": 0.1,
    }

    def __init__(self):
        self._evaluation_history: List[RiskEvaluationResult] = []

    async def ls_evaluation(
        self,
        project_id: str,
        scenario: Dict[str, Any],
        **kwargs
    ) -> RiskScenario:
        """LS危险度评价"""
        result = RiskScenario(
            scenario_id=f"SCN:{datetime.now().strftime('%Y%m%d%H%M%S')}",
            project_id=project_id,
            name=scenario.get("name", ""),
            description=scenario.get("description", ""),
            risk_type=RiskType(scenario.get("risk_type", "environmental")),
            frequency=scenario.get("frequency", 1e-3),
            frequency_source=scenario.get("frequency_source", "analysis"),
            consequence_type=scenario.get("consequence_type", ""),
            severity=scenario.get("severity", "moderate"),
        )

        frequency = result.frequency
        if frequency >= 1:
            l_score = 5
        elif frequency >= 1e-1:
            l_score = 4
        elif frequency >= 1e-2:
            l_score = 3
        elif frequency >= 1e-3:
            l_score = 2
        else:
            l_score = 1

        severity_map = {"negligible": 1, "moderate": 2, "critical": 3, "catastrophic": 4}
        s_score = severity_map.get(result.severity, 2)

        if l_score <= 5 and s_score <= 4:
            risk_value = self.RISK_MATRIX[s_score - 1][l_score - 1]
        else:
            risk_value = l_score * s_score

        result.risk_value = risk_value
        result.risk_level = self._get_risk_level(risk_value)

        return result

    async def qra_evaluation(
        self,
        project_id: str,
        scenarios: List[Dict[str, Any]],
        **kwargs
    ) -> RiskEvaluationResult:
        """定量风险评价（QRA）"""
        evaluated_scenarios = []
        for scenario in scenarios:
            evaluated = await self.ls_evaluation(project_id, scenario)
            evaluated_scenarios.append(evaluated)

        max_risk = max(s.risk_value for s in evaluated_scenarios) if evaluated_scenarios else 0
        total_social_risk = sum(s.risk_value * s.frequency for s in evaluated_scenarios)

        overall_level = self._get_risk_level(max_risk)

        result = RiskEvaluationResult(
            project_id=project_id,
            evaluation_type="QRA",
            overall_risk_level=overall_level,
            overall_risk_value=max_risk,
            scenarios=evaluated_scenarios,
        )

        self._evaluation_history.append(result)
        return result

    async def identify_major_hazard_sources(
        self,
        project_id: str,
        inventory: List[Dict[str, Any]],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """重大危险源辨识"""
        hazard_sources = []

        for item in inventory:
            name = item.get("name", "")
            amount = item.get("amount", 0)
            unit = item.get("unit", "t")

            threshold = self._get_threshold(name)

            if threshold and amount >= threshold:
                ratio = amount / threshold
                hazard_sources.append({
                    "name": name,
                    "amount": amount,
                    "unit": unit,
                    "threshold": threshold,
                    "ratio": round(ratio, 2),
                    "is_major": True,
                    "hazard_level": self._get_major_hazard_level(ratio),
                    "suggestion": f"构成{self._get_major_hazard_level(ratio)}级重大危险源",
                })
            else:
                hazard_sources.append({
                    "name": name,
                    "amount": amount,
                    "unit": unit,
                    "threshold": threshold,
                    "ratio": round(amount / threshold, 2) if threshold else 0,
                    "is_major": False,
                    "hazard_level": "无",
                    "suggestion": "未构成重大危险源",
                })

        return hazard_sources

    async def environmental_risk_assessment(
        self,
        project_id: str,
        risk_sources: List[Dict[str, Any]],
        sensitive_areas: List[Dict[str, Any]] = None,
        **kwargs
    ) -> RiskEvaluationResult:
        """环境风险评价"""
        scenarios = []
        sensitive_areas = sensitive_areas or []

        for source in risk_sources:
            scenario_dict = {
                "name": source.get("name", "环境风险源"),
                "description": source.get("description", ""),
                "risk_type": "environmental",
                "frequency": source.get("frequency", 1e-4),
                "consequence_type": source.get("consequence_type", "泄漏"),
                "severity": source.get("severity", "moderate"),
            }

            scenario = await self.ls_evaluation(project_id, scenario_dict)

            distance = source.get("distance_to_sensitive", 1000)
            if distance < 500:
                scenario.risk_value *= 1.5
            elif distance > 2000:
                scenario.risk_value *= 0.8

            scenarios.append(scenario)

        max_risk = max(s.risk_value for s in scenarios) if scenarios else 0

        result = RiskEvaluationResult(
            project_id=project_id,
            evaluation_type="environmental_risk",
            overall_risk_level=self._get_risk_level(max_risk),
            overall_risk_value=max_risk,
            scenarios=scenarios,
        )

        self._evaluation_history.append(result)
        return result

    def _get_risk_level(self, risk_value: float) -> RiskLevel:
        """根据风险值确定风险等级"""
        if risk_value >= 7:
            return RiskLevel.EXTREME
        elif risk_value >= 5:
            return RiskLevel.HIGH
        elif risk_value >= 3:
            return RiskLevel.MEDIUM
        elif risk_value >= 2:
            return RiskLevel.LOW
        else:
            return RiskLevel.NEGLIGIBLE

    def _get_threshold(self, substance_name: str) -> Optional[float]:
        """获取危险物质临界量"""
        if substance_name in self.MAJOR_HAZARD_THRESHOLDS:
            return self.MAJOR_HAZARD_THRESHOLDS[substance_name]

        name_lower = substance_name.lower()
        for key, value in self.MAJOR_HAZARD_THRESHOLDS.items():
            if key.lower() in name_lower or name_lower in key.lower():
                return value

        return None

    def _get_major_hazard_level(self, ratio: float) -> str:
        """确定重大危险源等级"""
        if ratio >= 100:
            return "一级"
        elif ratio >= 50:
            return "二级"
        elif ratio >= 10:
            return "三级"
        else:
            return "四级"


_risk_evaluator: Optional[RiskEvaluator] = None


def get_risk_evaluator() -> RiskEvaluator:
    """获取风险评价引擎单例"""
    global _risk_evaluator
    if _risk_evaluator is None:
        _risk_evaluator = RiskEvaluator()
    return _risk_evaluator