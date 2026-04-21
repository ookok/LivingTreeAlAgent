"""
Kronos 金融垂直大模型模块
基于 shiyu-coder/Kronos 思想：金融领域专用分析

功能：
- 财报分析
- 风控评估
- 投资建议
- 合规检查
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FinancialMetrics:
    """财务指标"""
    revenue: float = 0.0          # 营收
    net_profit: float = 0.0       # 净利润
    gross_margin: float = 0.0     # 毛利率
    debt_ratio: float = 0.0       # 负债率
    current_ratio: float = 0.0    # 流动比率
    quick_ratio: float = 0.0      # 速动比率
    roe: float = 0.0              # 净资产收益率
    debt_to_equity: float = 0.0   # 产权比率


@dataclass
class RiskAssessment:
    """风险评估结果"""
    level: RiskLevel
    score: float  # 0-100
    factors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class CashFlowAnalysis:
    """现金流分析"""
    operating_cf: float = 0.0    # 经营活动现金流
    investing_cf: float = 0.0     # 投资活动现金流
    financing_cf: float = 0.0     # 融资活动现金流
    net_cf: float = 0.0          # 净现金流
    health_score: float = 0.0    # 健康度评分 (0-100)


class KronosAnalyzer:
    """
    Kronos 金融分析器
    专注财报分析、风控评估、投资建议
    """

    def __init__(self):
        self.model_name = "kronos-financial"
        # 风险阈值
        self.thresholds = {
            "debt_ratio_warning": 0.6,
            "debt_ratio_danger": 0.8,
            "current_ratio_healthy": 2.0,
            "current_ratio_warning": 1.0,
            "roe_healthy": 0.15,
        }

    async def analyze_financial_health(
        self,
        metrics: FinancialMetrics
    ) -> RiskAssessment:
        """
        分析财务健康度

        Args:
            metrics: 财务指标

        Returns:
            风险评估结果
        """
        factors = []
        recommendations = []
        risk_score = 50.0  # 初始分数，越低越好

        # 负债率检查
        if metrics.debt_ratio > self.thresholds["debt_ratio_danger"]:
            factors.append(f"负债率过高: {metrics.debt_ratio:.1%}")
            recommendations.append("建议降低负债，增加自有资金")
            risk_score += 25
        elif metrics.debt_ratio > self.thresholds["debt_ratio_warning"]:
            factors.append(f"负债率偏高: {metrics.debt_ratio:.1%}")
            recommendations.append("关注负债结构，适时调整")
            risk_score += 15

        # 流动比率检查
        if metrics.current_ratio < self.thresholds["current_ratio_warning"]:
            factors.append(f"流动比率偏低: {metrics.current_ratio:.2f}")
            recommendations.append("短期偿债能力不足，注意流动性风险")
            risk_score += 20
        elif metrics.current_ratio < self.thresholds["current_ratio_healthy"]:
            factors.append(f"流动比率偏低: {metrics.current_ratio:.2f}")
            recommendations.append("流动资产略紧，建议优化库存")
            risk_score += 10

        # 毛利率检查
        if metrics.gross_margin < 0.1:
            factors.append(f"毛利率较低: {metrics.gross_margin:.1%}")
            recommendations.append("考虑提升产品定价或降低成本")
            risk_score += 10
        elif metrics.gross_margin > 0.4:
            factors.append(f"毛利率优秀: {metrics.gross_margin:.1%}")

        # ROE 检查
        if metrics.roe > self.thresholds["roe_healthy"]:
            factors.append(f"净资产收益率良好: {metrics.roe:.1%}")
        elif metrics.roe < 0:
            factors.append(f"净资产收益为负: {metrics.roe:.1%}")
            recommendations.append("经营亏损，需改善盈利")
            risk_score += 15

        # 确定风险等级
        if risk_score < 30:
            level = RiskLevel.LOW
        elif risk_score < 50:
            level = RiskLevel.MEDIUM
        elif risk_score < 70:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.CRITICAL

        return RiskAssessment(
            level=level,
            score=100 - risk_score,  # 转为健康分数
            factors=factors,
            recommendations=recommendations
        )

    async def analyze_cash_flow(
        self,
        operating: float,
        investing: float,
        financing: float
    ) -> CashFlowAnalysis:
        """
        分析现金流状况
        """
        net_cf = operating + investing + financing

        # 健康度评分
        health_score = 50.0

        if operating > 0:
            health_score += 20
        else:
            health_score -= 30

        if abs(investing) < abs(operating) * 0.5:
            health_score += 10

        if financing < 0 and operating > 0:
            health_score += 10  # 正常还债

        return CashFlowAnalysis(
            operating_cf=operating,
            investing_cf=investing,
            financing_cf=financing,
            net_cf=net_cf,
            health_score=min(100, max(0, health_score))
        )

    async def credit_assessment(
        self,
        metrics: FinancialMetrics,
        cash_flow: CashFlowAnalysis
    ) -> Dict[str, Any]:
        """
        信用评估（电商场景：卖家/买家贷款/提额）

        Returns:
            信用评估结果，包含额度建议
        """
        health = await self.analyze_financial_health(metrics)
        cash_health = await self.analyze_cash_flow(
            cash_flow.operating_cf,
            cash_flow.investing_cf,
            cash_flow.financing_cf
        )

        # 综合评分
        composite_score = (health.score * 0.6 + cash_health.health_score * 0.4)

        # 额度建议（基于分数）
        base_limit = 10000
        if composite_score > 80:
            limit = base_limit * 3
            tier = "优质客户"
        elif composite_score > 60:
            limit = base_limit * 2
            tier = "良好客户"
        elif composite_score > 40:
            limit = base_limit
            tier = "一般客户"
        else:
            limit = base_limit * 0.5
            tier = "风险客户"

        return {
            "composite_score": composite_score,
            "tier": tier,
            "suggested_limit": limit,
            "health_score": health.score,
            "cash_flow_score": cash_health.health_score,
            "risk_level": health.level.value,
            "recommendations": health.recommendations,
            "approval_recommended": composite_score > 50
        }

    async def generate_report(
        self,
        company_name: str,
        metrics: FinancialMetrics,
        cash_flow: CashFlowAnalysis
    ) -> str:
        """
        生成财务分析报告
        """
        health = await self.analyze_financial_health(metrics)

        factors_md = "".join(f"- {f}\n" for f in health.factors)
        recs_md = "".join(f"- {r}\n" for r in health.recommendations)

        report = f"""
# {company_name} 财务分析报告

## 基本指标
| 指标 | 数值 |
|------|------|
| 营收 | ¥{metrics.revenue:,.2f} |
| 净利润 | ¥{metrics.net_profit:,.2f} |
| 毛利率 | {metrics.gross_margin:.1%} |
| 负债率 | {metrics.debt_ratio:.1%} |
| 流动比率 | {metrics.current_ratio:.2f} |
| 净资产收益率 | {metrics.roe:.1%} |

## 健康度评估
- **综合评分**: {health.score}/100
- **风险等级**: {health.level.value.upper()}
- **主要因素**:
{factors_md}

## 建议
{recs_md}

## 现金流
- 经营现金流: ¥{cash_flow.operating_cf:,.2f}
- 投资现金流: ¥{cash_flow.investing_cf:,.2f}
- 融资现金流: ¥{cash_flow.financing_cf:,.2f}
- 健康度: {cash_flow.health_score}/100
"""
        return report


class KronosRouter:
    """
    Kronos 路由器
    将金融请求路由到 Kronos 专用模型
    """

    def __init__(self):
        self.capabilities = [
            "financial_analysis",
            "risk_assessment",
            "credit_evaluation",
            "cash_flow_analysis",
            "investment_advice"
        ]

    async def route(self, query: str) -> Dict[str, Any]:
        """
        分析查询类型并返回处理建议
        """
        query_lower = query.lower()

        if any(k in query_lower for k in ["风险", "风控", "评估", "信用"]):
            return {"type": "risk_assessment", "requires_metrics": True}
        elif any(k in query_lower for k in ["现金流", "现金", "资金流"]):
            return {"type": "cash_flow", "requires_metrics": True}
        elif any(k in query_lower for k in ["贷款", "借款", "额度", "授信", "信贷"]):
            return {"type": "credit", "requires_metrics": True}
        elif any(k in query_lower for k in ["财报", "财务", "利润", "营收"]):
            return {"type": "financial_report", "requires_metrics": True}
        else:
            return {"type": "general", "requires_metrics": False}


# 单例
_kronos_analyzer: Optional[KronosAnalyzer] = None


def get_kronos_analyzer() -> KronosAnalyzer:
    """获取 Kronos 分析器单例"""
    global _kronos_analyzer
    if _kronos_analyzer is None:
        _kronos_analyzer = KronosAnalyzer()
    return _kronos_analyzer
