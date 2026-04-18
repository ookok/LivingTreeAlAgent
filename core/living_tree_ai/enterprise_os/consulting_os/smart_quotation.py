"""
项目智能报价系统

基于项目特征的自动化报价引擎。
"""

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime


# ==================== 枚举定义 ====================

class PricingModel(Enum):
    """定价模型"""
    FIXED = "fixed"                     # 固定价格
    TIME_AND_MATERIALS = "time_and_materials"  # 成本加酬金
    VALUE_BASED = "value_based"         # 价值定价
    COMPETITIVE = "competitive"        # 竞争性定价


class ComplexityLevel(Enum):
    """复杂度等级"""
    SIMPLE = "simple"                   # 简单
    STANDARD = "standard"               # 标准
    COMPLEX = "complex"                 # 复杂
    HIGHLY_COMPLEX = "highly_complex"  # 高度复杂


# ==================== 数据模型 ====================

@dataclass
class QuotationFactors:
    """报价因子"""
    # 项目特征
    project_type: str = ""
    industry: str = ""
    region: str = ""
    scale: str = "medium"              # small/medium/large
    investment_amount: float = 0.0

    # 复杂度
    technical_complexity: ComplexityLevel = ComplexityLevel.STANDARD
    regulatory_complexity: ComplexityLevel = ComplexityLevel.STANDARD
    client_complexity: ComplexityLevel = ComplexityLevel.STANDARD  # 客户沟通难度

    # 工作量
    estimated_man_days: float = 0.0
    requires_monitoring: bool = False  # 是否需要现场监测
    requires_expert_review: bool = False
    requires_on_site: bool = False      # 是否需要现场踏勘

    # 商务因素
    client_relationship: str = "new"    # new/existing/vip
    competition_level: str = "medium"   # low/medium/high
    urgency: str = "normal"            # normal/urgent

    # 成本因子
    labor_cost_per_day: float = 1500.0  # 人天成本
    travel_cost_estimate: float = 0.0
    third_party_cost: float = 0.0      # 第三方费用（监测等）

    # 利润率
    target_profit_margin: float = 0.35  # 目标利润率 35%


@dataclass
class PriceComponent:
    """价格组成"""
    component_name: str
    category: str                        # labor/travel/third_party/profit/risk
    calculation_method: str             # formula/manual/percentage
    amount: float = 0.0
    description: str = ""
    details: Dict = field(default_factory=dict)


@dataclass
class HistoricalReference:
    """历史参考"""
    project_id: str
    project_name: str
    project_type: str
    industry: str
    region: str
    scale: str
    contract_amount: float = 0.0
    actual_cost: float = 0.0
    actual_man_days: float = 0.0
    profitability: float = 0.0
    client_satisfaction: float = 0.0    # 1-5
    year: int = 0


# ==================== 项目分析器 ====================

class ProjectAnalyzer:
    """
    项目分析器

    分析项目特征，计算报价因子。
    """

    # 行业复杂度系数
    INDUSTRY_COMPLEXITY = {
        "石化": {"technical": 1.3, "regulatory": 1.4, "client": 1.2},
        "化工": {"technical": 1.2, "regulatory": 1.3, "client": 1.1},
        "制药": {"technical": 1.3, "regulatory": 1.3, "client": 1.0},
        "电子": {"technical": 1.0, "regulatory": 1.0, "client": 1.0},
        "制造": {"technical": 1.0, "regulatory": 1.1, "client": 1.0},
        "房地产": {"technical": 1.1, "regulatory": 1.2, "client": 1.1},
        "市政": {"technical": 1.0, "regulatory": 1.1, "client": 0.9},
        "农业": {"technical": 0.9, "regulatory": 1.0, "client": 0.9},
    }

    # 地区难度系数
    REGION_DIFFICULTY = {
        "北京": 1.3,
        "上海": 1.2,
        "广东": 1.1,
        "江苏": 1.0,
        "浙江": 1.0,
        "山东": 0.95,
        "其他": 0.9,
    }

    # 项目类型基础人天
    BASE_MAN_DAYS = {
        "eia_report": {
            "simple": 15,
            "standard": 30,
            "complex": 60,
            "highly_complex": 120,
        },
        "safety_assessment": {
            "simple": 10,
            "standard": 20,
            "complex": 40,
            "highly_complex": 80,
        },
        "feasibility_study": {
            "simple": 8,
            "standard": 15,
            "complex": 30,
            "highly_complex": 60,
        },
        "pollution_permit": {
            "simple": 5,
            "standard": 10,
            "complex": 20,
            "highly_complex": 40,
        },
        "emergency_plan": {
            "simple": 3,
            "standard": 7,
            "complex": 15,
            "highly_complex": 30,
        },
    }

    @classmethod
    def analyze_project(
        cls,
        project_type: str,
        industry: str = None,
        region: str = "江苏",
        scale: str = "medium",
        investment_amount: float = 0.0,
        special_requirements: List[str] = None
    ) -> QuotationFactors:
        """
        分析项目特征

        Args:
            project_type: 项目类型
            industry: 行业
            region: 地区
            scale: 规模
            investment_amount: 投资额
            special_requirements: 特殊要求

        Returns:
            QuotationFactors
        """
        # 确定复杂度
        technical_complexity = ComplexityLevel.STANDARD
        if scale == "large" or investment_amount > 100000000:
            technical_complexity = ComplexityLevel.COMPLEX
        elif scale == "small" and investment_amount < 10000000:
            technical_complexity = ComplexityLevel.SIMPLE

        # 行业特殊复杂度
        industry_factors = cls.INDUSTRY_COMPLEXITY.get(industry, {})
        if industry in ["石化", "化工", "制药"]:
            technical_complexity = ComplexityLevel.COMPLEX

        # 计算基础人天
        base_days = cls.BASE_MAN_DAYS.get(
            project_type,
            {"standard": 20}
        ).get(scale, 20)

        # 根据复杂度调整
        if technical_complexity == ComplexityLevel.SIMPLE:
            base_days *= 0.7
        elif technical_complexity == ComplexityLevel.COMPLEX:
            base_days *= 1.5
        elif technical_complexity == ComplexityLevel.HIGHLY_COMPLEX:
            base_days *= 2.5

        # 评估附加需求
        requires_monitoring = False
        requires_expert_review = False
        requires_on_site = False

        if special_requirements:
            for req in special_requirements:
                if "监测" in req:
                    requires_monitoring = True
                    base_days += 5  # 监测增加5人天
                if "专家" in req:
                    requires_expert_review = True
                    base_days += 3
                if "现场" in req:
                    requires_on_site = True
                    base_days += 3

        # 估算差旅成本
        travel_cost = 0
        if requires_on_site:
            travel_cost = 3000 * max(1, int(base_days / 5))

        # 第三方成本
        third_party = 0
        if requires_monitoring:
            third_party = 10000

        return QuotationFactors(
            project_type=project_type,
            industry=industry or "",
            region=region,
            scale=scale,
            investment_amount=investment_amount,
            technical_complexity=technical_complexity,
            regulatory_complexity=ComplexityLevel.STANDARD,
            estimated_man_days=base_days,
            requires_monitoring=requires_monitoring,
            requires_expert_review=requires_expert_review,
            requires_on_site=requires_on_site,
            labor_cost_per_day=1500,
            travel_cost_estimate=travel_cost,
            third_party_cost=third_party
        )


# ==================== 智能报价引擎 ====================

class SmartQuotationEngine:
    """
    智能报价引擎

    核心功能：
    1. 基于项目特征的自动报价
    2. 历史项目参考
    3. 多模型定价
    4. 报价单生成
    """

    def __init__(self):
        self._historical_projects: List[HistoricalReference] = []
        self._analyzer = ProjectAnalyzer()

        # 加载历史数据（模拟）
        self._load_historical_data()

    def _load_historical_data(self):
        """加载历史数据"""
        # 模拟历史项目
        self._historical_projects = [
            HistoricalReference(
                project_id="P001",
                project_name="XX化工环评项目",
                project_type="eia_report",
                industry="化工",
                region="江苏",
                scale="large",
                contract_amount=150000,
                actual_cost=95000,
                actual_man_days=45,
                profitability=0.37,
                client_satisfaction=4.5,
                year=2024
            ),
            HistoricalReference(
                project_id="P002",
                project_name="XX电子安全评价",
                project_type="safety_assessment",
                industry="电子",
                region="广东",
                scale="medium",
                contract_amount=50000,
                actual_cost=32000,
                actual_man_days=22,
                profitability=0.36,
                client_satisfaction=4.0,
                year=2024
            ),
        ]

    async def generate_quotation(
        self,
        factors: QuotationFactors,
        pricing_model: PricingModel = PricingModel.FIXED
    ) -> Dict:
        """
        生成报价

        Args:
            factors: 报价因子
            pricing_model: 定价模型

        Returns:
            报价结果
        """
        components = []

        # 1. 人力成本
        labor_cost = factors.estimated_man_days * factors.labor_cost_per_day
        components.append(PriceComponent(
            component_name="人力成本",
            category="labor",
            calculation_method="man_days * daily_rate",
            amount=labor_cost,
            description=f"{factors.estimated_man_days:.1f}人天 × {factors.labor_cost_per_day}元/天",
            details={
                "man_days": factors.estimated_man_days,
                "daily_rate": factors.labor_cost_per_day
            }
        ))

        # 2. 差旅成本
        if factors.travel_cost_estimate > 0:
            components.append(PriceComponent(
                component_name="差旅成本",
                category="travel",
                calculation_method="estimate",
                amount=factors.travel_cost_estimate,
                description="现场踏勘差旅费用"
            ))

        # 3. 第三方费用
        if factors.third_party_cost > 0:
            components.append(PriceComponent(
                component_name="第三方费用",
                category="third_party",
                calculation_method="monitoring_cost",
                amount=factors.third_party_cost,
                description="环境监测等第三方服务费用"
            ))

        # 4. 专家评审费
        if factors.requires_expert_review:
            components.append(PriceComponent(
                component_name="专家评审费",
                category="labor",
                calculation_method="fixed",
                amount=5000,
                description="专家评审费用"
            ))

        # 5. 成本合计
        total_cost = sum(c.amount for c in components)

        # 6. 利润率
        profit_margin = factors.target_profit_margin

        # 根据客户关系和竞争程度调整
        if factors.client_relationship == "existing":
            profit_margin -= 0.05  # 老客户优惠
        elif factors.client_relationship == "vip":
            profit_margin -= 0.08

        if factors.competition_level == "high":
            profit_margin -= 0.05

        if factors.urgency == "urgent":
            profit_margin += 0.1  # 加急加价

        profit_margin = max(0.15, min(0.5, profit_margin))  # 15%-50%范围

        profit = total_cost * profit_margin / (1 - profit_margin)

        components.append(PriceComponent(
            component_name="管理费与利润",
            category="profit",
            calculation_method=f"cost * {profit_margin:.0%}",
            amount=profit,
            description=f"管理费用及利润（利润率{profit_margin:.0%}）"
        ))

        # 7. 合计
        total_amount = total_cost + profit

        # 8. 查找历史参考
        similar = await self._find_similar_projects(factors)

        # 9. 生成报价单
        quotation = {
            "pricing_model": pricing_model.value,
            "factors": {
                "project_type": factors.project_type,
                "industry": factors.industry,
                "region": factors.region,
                "scale": factors.scale,
                "estimated_man_days": factors.estimated_man_days,
                "complexity": factors.technical_complexity.value
            },
            "components": [
                {
                    "name": c.component_name,
                    "category": c.category,
                    "amount": c.amount,
                    "description": c.description
                }
                for c in components
            ],
            "summary": {
                "total_cost": total_cost,
                "total_amount": total_amount,
                "profit_margin": profit_margin,
                "breakdown": {
                    "人力成本": labor_cost,
                    "差旅成本": factors.travel_cost_estimate,
                    "第三方费用": factors.third_party_cost,
                    "利润": profit
                }
            },
            "price_range": {
                "conservative": total_amount * 0.85,
                "standard": total_amount,
                "optimistic": total_amount * 1.15
            },
            "historical_reference": similar,
            "validity_days": 30,
            "payment_terms": "合同签订后付50%，报告提交后付50%"
        }

        return quotation

    async def _find_similar_projects(
        self,
        factors: QuotationFactors
    ) -> List[Dict]:
        """查找相似项目"""
        similar = []

        for proj in self._historical_projects:
            score = 0
            if proj.project_type == factors.project_type:
                score += 3
            if proj.industry == factors.industry:
                score += 2
            if proj.region == factors.region:
                score += 1
            if proj.scale == factors.scale:
                score += 1

            if score >= 3:
                similar.append({
                    "project_name": proj.project_name,
                    "contract_amount": proj.contract_amount,
                    "actual_cost": proj.actual_cost,
                    "profitability": proj.profitability,
                    "similarity_score": score / 7,
                    "year": proj.year
                })

        # 按相似度排序
        similar.sort(key=lambda x: x["similarity_score"], reverse=True)

        return similar[:3]

    async def calculate_competitiveness(
        self,
        quotation_amount: float,
        project_type: str,
        region: str
    ) -> Dict:
        """评估报价竞争力"""
        # 查找同类型同地区项目
        similar = [
            p for p in self._historical_projects
            if p.project_type == project_type and p.region == region
        ]

        if not similar:
            return {
                "competitiveness": "unknown",
                "reason": "缺乏同类型同地区参考数据"
            }

        avg_price = sum(p.contract_amount for p in similar) / len(similar)

        ratio = quotation_amount / avg_price

        if ratio < 0.8:
            return {
                "competitiveness": "very_high",
                "ratio": ratio,
                "recommendation": "价格偏低，可适当上调"
            }
        elif ratio < 1.0:
            return {
                "competitiveness": "high",
                "ratio": ratio,
                "recommendation": "价格有竞争力"
            }
        elif ratio < 1.2:
            return {
                "competitiveness": "medium",
                "ratio": ratio,
                "recommendation": "价格适中，需突出差异化价值"
            }
        else:
            return {
                "competitiveness": "low",
                "ratio": ratio,
                "recommendation": "价格偏高，建议优化成本或增加价值"
            }

    async def generate_alternatives(
        self,
        factors: QuotationFactors
    ) -> List[Dict]:
        """生成多种报价方案"""
        alternatives = []

        # 方案1：标准报价
        standard = await self.generate_quotation(factors, PricingModel.FIXED)
        standard["option_name"] = "标准方案"
        standard["description"] = "一次性固定报价"
        alternatives.append(standard)

        # 方案2：成本加酬金
        if factors.estimated_man_days > 20:
            t_and_m = await self.generate_quotation(factors, PricingModel.TIME_AND_MATERIALS)
            t_and_m["option_name"] = "成本加酬金方案"
            t_and_m["description"] = "按实际人天结算，报价为最高限价"
            alternatives.append(t_and_m)

        # 方案3：分阶段报价
        phased = await self._generate_phased_quotation(factors)
        phased["option_name"] = "分阶段方案"
        phased["description"] = "按工作阶段分期付款"
        alternatives.append(phased)

        return alternatives

    async def _generate_phased_quotation(
        self,
        factors: QuotationFactors
    ) -> Dict:
        """生成分阶段报价"""
        # 按阶段分配比例
        phases = [
            {"name": "启动阶段", "percent": 0.2, "days": factors.estimated_man_days * 0.15},
            {"name": "调研编制", "percent": 0.5, "days": factors.estimated_man_days * 0.55},
            {"name": "审核提交", "percent": 0.3, "days": factors.estimated_man_days * 0.30},
        ]

        total_cost = factors.estimated_man_days * factors.labor_cost_per_day
        total_cost += factors.travel_cost_estimate + factors.third_party_cost

        for phase in phases:
            phase_amount = total_cost * phase["percent"] * (1 + factors.target_profit_margin)
            phase["amount"] = phase_amount

        return {
            "phases": phases,
            "total_amount": sum(p["amount"] for p in phases)
        }


# ==================== 单例模式 ====================

_quotation_engine: Optional[SmartQuotationEngine] = None


def get_quotation_engine() -> SmartQuotationEngine:
    """获取报价引擎单例"""
    global _quotation_engine
    if _quotation_engine is None:
        _quotation_engine = SmartQuotationEngine()
    return _quotation_engine
