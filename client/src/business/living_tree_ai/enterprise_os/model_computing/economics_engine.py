"""
工程经济引擎 (Economics Engine)

实现投资估算、运营成本计算、成本效益分析。

支持：
1. 投资估算（工程量×单价法、类比法）
2. 运营成本计算
3. 成本效益分析（NPV、IRR、回收期）
4. 敏感性分析

使用方法：
```python
engine = get_economics_engine()

# 投资估算
estimate = await engine.estimate_investment(
    project_id="PROJ001",
    project_type="新建",
    scale="large",
    components=[
        {"name": "土建工程", "quantity": 1000, "unit": "m2", "unit_price": 800},
        {"name": "设备购置", "quantity": 10, "unit": "套", "unit_price": 500000},
    ]
)

# 成本效益分析
result = await engine.cost_benefit_analysis(
    project_id="PROJ001",
    investment=10000000,
    annual_benefits=3000000,
    annual_costs=1500000,
    project_life=15,
    discount_rate=0.08
)
```
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
import math


class CostType(Enum):
    """成本类型"""
    INITIAL_INVESTMENT = "initial_investment"
    CAPITAL_EXPENDITURE = "capital_expenditure"
    OPERATING_COST = "operating_cost"
    MAINTENANCE_COST = "maintenance_cost"
    ENVIRONMENTAL_COST = "environmental_cost"
    SOCIAL_COST = "social_cost"


@dataclass
class CostItem:
    """成本项目"""
    name: str
    cost_type: CostType
    amount: float
    unit: str = "万元"
    currency: str = "CNY"

    category: str = ""
    specification: str = ""
    quantity: float = 1.0
    unit_price: float = 0.0

    is_estimated: bool = True
    estimation_method: str = ""
    estimation_accuracy: float = 0.85

    year: Optional[int] = None
    tax_category: str = ""


@dataclass
class InvestmentEstimate:
    """投资估算结果"""
    project_id: str
    project_type: str
    scale: str

    total_investment: float = 0.0
    total_investment_unit: str = "万元"

    components: List[CostItem] = field(default_factory=list)
    by_category: Dict[str, float] = field(default_factory=dict)
    by_phase: Dict[str, float] = field(default_factory=dict)

    estimation_method: str = ""
    estimation_basis: str = ""
    contingency_rate: float = 0.0
    contingency_amount: float = 0.0

    confidence: float = 0.85
    accuracy: float = 0.80

    estimated_at: datetime = field(default_factory=datetime.now)
    estimator: str = "system"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_type": self.project_type,
            "total_investment": self.total_investment,
            "components_count": len(self.components),
            "by_category": self.by_category,
            "confidence": self.confidence,
            "estimated_at": self.estimated_at.isoformat(),
        }


@dataclass
class OperatingCost:
    """运营成本"""
    project_id: str

    annual_cost: float = 0.0
    unit: str = "万元/年"

    components: List[CostItem] = field(default_factory=list)
    by_category: Dict[str, float] = field(default_factory=dict)
    by_cost_type: Dict[str, float] = field(default_factory=dict)

    unit_cost: Optional[float] = None
    unit_cost_unit: str = ""

    growth_rate: float = 0.0

    base_year: int = 0
    estimated_years: List[int] = field(default_factory=list)

    confidence: float = 0.85

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "annual_cost": self.annual_cost,
            "unit_cost": self.unit_cost,
            "by_category": self.by_category,
            "growth_rate": self.growth_rate,
        }


@dataclass
class CostBenefitResult:
    """成本效益分析结果"""
    project_id: str

    npv: float = 0.0
    irr: float = 0.0
    payback_period: float = 0.0
    benefit_cost_ratio: float = 0.0

    sensitivity_analysis: Dict[str, Any] = field(default_factory=dict)

    is_economically_viable: bool = True
    main_risk_factors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    investment: float = 0.0
    project_life: int = 0
    discount_rate: float = 0.0
    annual_benefits: float = 0.0
    annual_costs: float = 0.0

    cash_flows: List[Dict[str, Any]] = field(default_factory=list)

    confidence: float = 0.85
    evaluated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "npv": round(self.npv, 2),
            "irr": f"{round(self.irr * 100, 2)}%",
            "payback_period": round(self.payback_period, 2),
            "benefit_cost_ratio": round(self.benefit_cost_ratio, 2),
            "is_economically_viable": self.is_economically_viable,
            "confidence": self.confidence,
        }


class EconomicsEngine:
    """
    工程经济引擎

    支持：
    1. 投资估算 - 工程量×单价法、类比法
    2. 运营成本 - 分项计算、类比估算
    3. 成本效益 - NPV、IRR、回收期
    4. 敏感性分析
    """

    INVESTMENT_INDICES = {
        "化工": {
            "新建": {
                "unit": "万元/吨产品",
                "range": [0.5, 2.0],
                "typical": 1.0,
            },
            "扩建": {
                "unit": "万元/吨产品",
                "range": [0.3, 1.2],
                "typical": 0.6,
            }
        },
        "印染": {
            "新建": {
                "unit": "万元/m布",
                "range": [0.01, 0.05],
                "typical": 0.02,
            }
        }
    }

    OPERATING_COST_INDICES = {
        "人工费": {"ratio": 0.15, "description": "占销售收入比例"},
        "原材料费": {"ratio": 0.50, "description": "占销售收入比例"},
        "能源费": {"ratio": 0.10, "description": "占销售收入比例"},
        "折旧费": {"ratio": 0.08, "description": "占投资比例"},
        "维修费": {"ratio": 0.03, "description": "占投资比例"},
        "管理费": {"ratio": 0.05, "description": "占销售收入比例"},
    }

    def __init__(self):
        self._calculation_history: List[Dict[str, Any]] = []

    async def estimate_investment(
        self,
        project_id: str,
        project_type: str = "新建",
        scale: str = "medium",
        components: Optional[List[Dict[str, Any]]] = None,
        total_product_capacity: Optional[float] = None,
        industry: str = "化工",
        contingency_rate: float = 0.10,
        **kwargs
    ) -> InvestmentEstimate:
        """投资估算"""
        result = InvestmentEstimate(
            project_id=project_id,
            project_type=project_type,
            scale=scale,
            contingency_rate=contingency_rate,
            estimation_method="工程量×单价法" if components else "类比估算法",
        )

        total = 0.0
        by_category = {}

        if components:
            result.estimation_method = "工程量×单价法"

            for comp in components:
                item = CostItem(
                    name=comp.get("name", ""),
                    cost_type=CostType.INITIAL_INVESTMENT,
                    amount=comp.get("quantity", 0) * comp.get("unit_price", 0),
                    unit="万元",
                    category=comp.get("category", "其他"),
                    quantity=comp.get("quantity", 1),
                    unit_price=comp.get("unit_price", 0),
                    estimation_method="工程量×单价法",
                )
                result.components.append(item)
                total += item.amount
                by_category[item.category] = by_category.get(item.category, 0) + item.amount

        elif total_product_capacity:
            result.estimation_method = "类比估算法"

            index = self.INVESTMENT_INDICES.get(industry, {}).get(project_type, {})
            typical = index.get("typical", 1.0)
            total = total_product_capacity * typical

            categories = ["设备购置", "安装工程", "建筑工程", "其他费用"]
            ratios = [0.40, 0.20, 0.25, 0.15]

            for cat, ratio in zip(categories, ratios):
                amount = total * ratio
                by_category[cat] = amount
                result.components.append(CostItem(
                    name=cat,
                    cost_type=CostType.INITIAL_INVESTMENT,
                    amount=amount,
                    category=cat,
                    is_estimated=True,
                    estimation_method="类比估算法",
                ))

        result.contingency_amount = total * contingency_rate
        result.total_investment = total + result.contingency_amount
        result.by_category = {k: round(v, 2) for k, v in by_category.items()}
        result.components.append(CostItem(
            name="预备费",
            cost_type=CostType.INITIAL_INVESTMENT,
            amount=result.contingency_amount,
            category="预备费",
            estimation_method=f"按总投资{contingency_rate*100}%计",
        ))

        self._calculation_history.append({
            "project_id": project_id,
            "type": "investment_estimate",
            "total": result.total_investment,
            "method": result.estimation_method,
            "timestamp": datetime.now().isoformat(),
        })

        return result

    async def calculate_operating_cost(
        self,
        project_id: str,
        annual_revenue: Optional[float] = None,
        investment: Optional[float] = None,
        components: Optional[List[Dict[str, Any]]] = None,
        project_life: int = 15,
        growth_rate: float = 0.02,
        **kwargs
    ) -> OperatingCost:
        """运营成本计算"""
        result = OperatingCost(
            project_id=project_id,
            growth_rate=growth_rate,
            base_year=datetime.now().year,
        )

        if components:
            total = 0.0
            by_category = {}
            by_type = {}

            for comp in components:
                item = CostItem(
                    name=comp.get("name", ""),
                    cost_type=CostType(comp.get("cost_type", "operating_cost")),
                    amount=comp.get("amount", 0),
                    unit="万元/年",
                    category=comp.get("category", "其他"),
                )
                result.components.append(item)
                total += item.amount
                by_category[item.category] = by_category.get(item.category, 0) + item.amount
                by_type[item.cost_type.value] = by_type.get(item.cost_type.value, 0) + item.amount

            result.annual_cost = total
            result.by_category = {k: round(v, 2) for k, v in by_category.items()}
            result.by_type = {k: round(v, 2) for k, v in by_type.items()}

        elif annual_revenue:
            total = 0.0
            by_category = {}

            for cat, index in self.OPERATING_COST_INDICES.items():
                ratio = index.get("ratio", 0)
                amount = annual_revenue * ratio
                total += amount
                by_category[cat] = amount
                result.components.append(CostItem(
                    name=cat,
                    cost_type=CostType.OPERATING_COST,
                    amount=amount,
                    category=cat,
                    is_estimated=True,
                ))

            if investment:
                depreciation = investment / project_life
                total += depreciation
                by_category["折旧费"] = depreciation
                result.components.append(CostItem(
                    name="折旧费",
                    cost_type=CostType.OPERATING_COST,
                    amount=depreciation,
                    category="折旧",
                ))

            result.annual_cost = total
            result.by_category = {k: round(v, 2) for k, v in by_category.items()}

        return result

    async def cost_benefit_analysis(
        self,
        project_id: str,
        investment: float,
        annual_benefits: float,
        annual_costs: float,
        project_life: int = 15,
        discount_rate: float = 0.08,
        salvage_value: float = 0.0,
        **kwargs
    ) -> CostBenefitResult:
        """成本效益分析"""
        result = CostBenefitResult(
            project_id=project_id,
            investment=investment,
            project_life=project_life,
            discount_rate=discount_rate,
            annual_benefits=annual_benefits,
            annual_costs=annual_costs,
        )

        net_annual_benefit = annual_benefits - annual_costs
        cash_flows = []

        cash_flows.append({"year": 0, "cash_flow": -investment, "type": "investment"})

        cumulative = -investment
        for year in range(1, project_life + 1):
            cf = net_annual_benefit
            if year == project_life:
                cf += salvage_value

            cumulative += cf
            cash_flows.append({
                "year": year,
                "cash_flow": round(cf, 2),
                "net_cash_flow": round(cumulative, 2),
                "type": "operation" if year < project_life else "final",
            })

        result.cash_flows = cash_flows

        npv = -investment
        for year in range(1, project_life + 1):
            cf = net_annual_benefit
            if year == project_life:
                cf += salvage_value
            npv += cf / ((1 + discount_rate) ** year)

        result.npv = round(npv, 2)
        result.irr = round(self._calculate_irr(cash_flows, discount_rate), 4)
        result.payback_period = round(self._calculate_payback_period(investment, net_annual_benefit, cash_flows), 2)

        pv_benefits = sum(annual_benefits / ((1 + discount_rate) ** year) for year in range(1, project_life + 1))
        pv_costs = investment + sum(annual_costs / ((1 + discount_rate) ** year) for year in range(1, project_life + 1))
        result.benefit_cost_ratio = round(pv_benefits / pv_costs, 2) if pv_costs > 0 else 0

        result.is_economically_viable = (
            result.npv > 0 and
            result.irr > discount_rate and
            result.payback_period < project_life * 0.7
        )

        result.sensitivity_analysis = await self._sensitivity_analysis(
            investment, annual_benefits, annual_costs, project_life, discount_rate
        )

        if result.npv < 0:
            result.main_risk_factors.append("净现值为负")
        if result.irr < discount_rate:
            result.main_risk_factors.append("内部收益率低于折现率")
        if result.payback_period > project_life * 0.6:
            result.main_risk_factors.append("投资回收期过长")

        result.recommendations = self._generate_recommendations(result)

        self._calculation_history.append({
            "project_id": project_id,
            "type": "cost_benefit",
            "npv": result.npv,
            "irr": result.irr,
            "is_viable": result.is_economically_viable,
            "timestamp": datetime.now().isoformat(),
        })

        return result

    def _calculate_irr(self, cash_flows: List[Dict[str, Any]], initial_rate: float) -> float:
        """计算内部收益率（牛顿迭代法）"""
        rate = initial_rate
        max_iterations = 100
        tolerance = 0.0001

        for _ in range(max_iterations):
            npv = 0
            d_npv = 0

            for cf in cash_flows:
                year = cf["year"]
                cash = cf["cash_flow"]
                factor = (1 + rate) ** year
                npv += cash / factor
                d_npv -= year * cash / ((1 + rate) ** (year + 1))

            if abs(d_npv) < tolerance:
                break

            rate = rate - npv / d_npv

            if rate < -0.99:
                rate = -0.99
            elif rate > 10:
                rate = 10

        return rate

    def _calculate_payback_period(
        self,
        investment: float,
        annual_net_benefit: float,
        cash_flows: List[Dict[str, Any]]
    ) -> float:
        """计算投资回收期"""
        if annual_net_benefit <= 0:
            return float('inf')

        static_payback = investment / annual_net_benefit

        cumulative = -investment
        for cf in cash_flows[1:]:
            cumulative += cf["cash_flow"]
            if cumulative >= 0:
                years_before = cf["year"] - 1
                remaining = -sum(cash_flows[i]["cash_flow"] for i in range(1, cf["year"]))
                fraction = remaining / cf["cash_flow"]
                return years_before + fraction

        return static_payback

    async def _sensitivity_analysis(
        self,
        investment: float,
        annual_benefits: float,
        annual_costs: float,
        project_life: int,
        discount_rate: float
    ) -> Dict[str, Dict[str, float]]:
        """敏感性分析"""
        base_npv = -investment
        for year in range(1, project_life + 1):
            base_npv += (annual_benefits - annual_costs) / ((1 + discount_rate) ** year)

        sensitivity = {}

        for change in [-0.2, 0.2]:
            new_investment = investment * (1 + change)
            new_npv = -new_investment
            for year in range(1, project_life + 1):
                new_npv += (annual_benefits - annual_costs) / ((1 + discount_rate) ** year)

            sensitivity[f"investment_{'+' if change > 0 else ''}{int(change*100)}%"] = {
                "new_npv": round(new_npv, 2),
                "npv_change": round(new_npv - base_npv, 2),
                "npv_change_pct": round((new_npv - base_npv) / base_npv, 4) if base_npv != 0 else 0,
            }

        for change in [-0.2, 0.2]:
            new_benefits = annual_benefits * (1 + change)
            new_npv = -investment
            for year in range(1, project_life + 1):
                new_npv += (new_benefits - annual_costs) / ((1 + discount_rate) ** year)

            sensitivity[f"benefits_{'+' if change > 0 else ''}{int(change*100)}%"] = {
                "new_npv": round(new_npv, 2),
                "npv_change": round(new_npv - base_npv, 2),
                "npv_change_pct": round((new_npv - base_npv) / base_npv, 4) if base_npv != 0 else 0,
            }

        return sensitivity

    def _generate_recommendations(self, result: CostBenefitResult) -> List[str]:
        """生成建议"""
        recommendations = []

        if result.is_economically_viable:
            recommendations.append("项目经济可行，建议投资")
        else:
            recommendations.append("项目经济不可行，建议重新评估")

        if result.irr > result.discount_rate * 1.5:
            recommendations.append("内部收益率显著高于折现率，项目抗风险能力较强")

        if result.payback_period < result.project_life * 0.4:
            recommendations.append("投资回收期较短，资金周转良好")

        if sensitivity := result.sensitivity_analysis:
            max_impact_factor = max(sensitivity.items(), key=lambda x: abs(x[1]["npv_change_pct"]))
            recommendations.append(f"对{max_impact_factor[0].split('_')[0]}最敏感，需重点关注")

        return recommendations


_economics_engine: Optional[EconomicsEngine] = None


def get_economics_engine() -> EconomicsEngine:
    """获取工程经济引擎单例"""
    global _economics_engine
    if _economics_engine is None:
        _economics_engine = EconomicsEngine()
    return _economics_engine