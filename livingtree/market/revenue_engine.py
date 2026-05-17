"""Revenue Engine — system self-calculates ROI + auto-investment decisions.

Two engines:
  1. RevenueAttribution:  system calculates exactly how much value it created
  2. SelfInvestment:       system decides its own evolution based on ROI

Economic logic:
  - Every action has a market value (商机发现 = N万, 期限提醒避免罚款 = N万)
  - System running cost is tracked (API calls, storage, compute)
  - ROI = (value_created - cost) / cost
  - High-ROI upgrades are auto-recommended (or auto-executed)
  - This is the "external force" driving system evolution
"""
# DEPRECATED — candidate for removal. No active references found.


from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# ═══ Revenue Attribution ═══

@dataclass
class RevenueItem:
    """One revenue event attributed to system action."""
    date: str
    category: str         # "opportunity", "reminder", "template", "compliance", "search"
    description: str
    estimated_value: float  # 万元
    confidence: float = 0.5
    source: str = ""


@dataclass
class MonthlyReport:
    """Monthly revenue attribution report."""
    month: str
    total_value: float = 0.0     # 万元
    total_cost: float = 0.0      # 万元
    roi: float = 0.0
    by_category: dict[str, float] = field(default_factory=dict)
    top_items: list[RevenueItem] = field(default_factory=list)
    system_actions: int = 0
    trend: str = "stable"


class RevenueAttribution:
    """System self-calculates ROI.

    Usage:
        ra = RevenueAttribution()
        ra.record("商机发现", "亚威变压器招标 → 中标35万", value=35.0)
        report = ra.monthly_report()
        # → 本月创造价值: 56.5万 | 成本: 0.5万 | ROI: 113x
    """

    VALUE_RULES = {
        "opportunity_discovered": 10.0,   # 发现1个商机 = 10万价值
        "opportunity_won": 35.0,          # 中标1个 = 35万
        "reminder_saved_penalty": 20.0,   # 避免1次罚款 = 20万
        "template_saved_time": 1.5,       # 模板节省3天人工 = 1.5万
        "compliance_check": 5.0,          # 合规检查 = 5万
        "search_time_saved": 0.5,         # 搜索省时 = 0.5万
    }

    COST_RULES = {
        "api_call_1k": 0.001,    # 1000次API调用 = ¥10
        "storage_gb_month": 0.5, # 1GB存储/月 = ¥5
        "compute_hour": 2.0,     # 1小时计算 = ¥20
    }

    def __init__(self, data_dir: str = ""):
        self._data_dir = data_dir or os.path.expanduser("~/.livingtree/revenue")
        os.makedirs(self._data_dir, exist_ok=True)
        self._items: list[RevenueItem] = []
        self._api_calls: int = 0
        self._storage_gb: float = 0.1
        self._compute_hours: float = 0.0

    def record(
        self, category: str, description: str,
        value: float = 0.0, confidence: float = 0.5,
    ) -> None:
        """Record a revenue-generating event."""
        if value == 0.0:
            value = self.VALUE_RULES.get(category, 1.0) * confidence

        item = RevenueItem(
            date=time.strftime("%Y-%m-%d"),
            category=category,
            description=description[:200],
            estimated_value=value,
            confidence=confidence,
        )
        self._items.append(item)

    def record_cost(self, api_calls: int = 0, storage_gb: float = 0.0,
                    compute_hours: float = 0.0) -> None:
        self._api_calls += api_calls
        self._storage_gb += storage_gb
        self._compute_hours += compute_hours

    def monthly_report(self, month: str = "") -> MonthlyReport:
        """Generate monthly revenue attribution report."""
        month = month or time.strftime("%Y-%m")
        month_items = [i for i in self._items if i.date.startswith(month)]

        total_value = sum(i.estimated_value for i in month_items)
        by_cat = {}
        for i in month_items:
            by_cat[i.category] = by_cat.get(i.category, 0.0) + i.estimated_value

        total_cost = (
            self._api_calls * self.COST_RULES["api_call_1k"] / 1000 +
            self._storage_gb * self.COST_RULES["storage_gb_month"] +
            self._compute_hours * self.COST_RULES["compute_hour"]
        )

        total_cost = max(0.01, total_cost)  # avoid division by zero
        roi = total_value / total_cost

        report = MonthlyReport(
            month=month,
            total_value=total_value,
            total_cost=total_cost,
            roi=roi,
            by_category=by_cat,
            top_items=sorted(month_items, key=lambda x: -x.estimated_value)[:10],
            system_actions=len(month_items),
        )

        logger.info(
            "Revenue: %s — value=%.1f万 cost=%.3f万 ROI=%.0fx (%d actions)",
            month, total_value, total_cost, roi, len(month_items),
        )
        return report

    def format_monthly_report(self, report: MonthlyReport) -> str:
        """Format the monthly report for display."""
        lines = [
            f"# 💰 月度价值报告 — {report.month}",
            f"系统创造价值: {report.total_value:.1f}万",
            f"系统运行成本: {report.total_cost:.3f}万",
            f"ROI: {report.roi:.0f}x",
            "",
        ]

        if report.by_category:
            lines.append("## 价值来源")
            for cat, val in sorted(report.by_category.items(), key=lambda x: -x[1]):
                lines.append(f"- {cat}: {val:.1f}万")

        if report.top_items:
            lines.append("\n## 主要贡献")
            for item in report.top_items[:5]:
                lines.append(f"- [{item.category}] {item.description}: {item.estimated_value:.1f}万")

        lines.append(f"\n系统动作数: {report.system_actions}")
        return "\n".join(lines)

    def get_stats(self) -> dict:
        report = self.monthly_report()
        return {
            "month": report.month,
            "total_value": report.total_value,
            "total_cost": report.total_cost,
            "roi": report.roi,
            "actions": report.system_actions,
        }


# ═══ Self-Investment Engine ═══

@dataclass
class InvestmentOption:
    """A self-upgrade option with ROI analysis."""
    name: str
    description: str
    upgrade_module: str         # which module to upgrade
    dev_cost_hours: int = 0     # developer time needed
    monthly_api_cost_increase: float = 0.0  # ¥
    expected_monthly_value: float = 0.0  # 万元
    expected_annual_value: float = 0.0    # 万元
    roi: float = 0.0
    priority: str = "low"

    def __post_init__(self):
        if self.expected_annual_value == 0.0:
            self.expected_annual_value = self.expected_monthly_value * 12
        annual_cost = self.dev_cost_hours * 200 + self.monthly_api_cost_increase * 12
        self.roi = self.expected_annual_value * 10000 / max(annual_cost, 1)
        self.priority = "high" if self.roi > 50 else "medium" if self.roi > 10 else "low"


class SelfInvestmentEngine:
    """System auto-decides its own evolution based on ROI.

    Pre-built investment options with estimated ROI.
    System learns which upgrades pay for themselves fastest.

    Usage:
        ie = SelfInvestmentEngine()
        options = ie.evaluate_options()
        ie.recommend()  # → highest ROI option
        ie.execute("hunt_expansion")  # auto-execute upgrade
    """

    def __init__(self):
        self._options: dict[str, InvestmentOption] = {}
        self._executed: list[str] = []
        self._revenue = RevenueAttribution()
        self._seed_options()

    def _seed_options(self) -> None:
        self._options = {
            "hunt_expansion": InvestmentOption(
                name="hunt_expansion",
                description="全网搜索狩猎 — 从固定站点扩展到全网络搜索商机",
                upgrade_module="knowledge_forager.hunt",
                dev_cost_hours=4,
                monthly_api_cost_increase=50.0,
                expected_monthly_value=2.5,
            ),
            "competitor_intel": InvestmentOption(
                name="competitor_intel",
                description="竞争对手情报 — 自动分析竞对中标模式",
                upgrade_module="market.user_profile",
                dev_cost_hours=3,
                monthly_api_cost_increase=30.0,
                expected_monthly_value=1.5,
            ),
            "bid_automation": InvestmentOption(
                name="bid_automation",
                description="投标自动化 — 自动生成技术方案 + 定价建议",
                upgrade_module="market.opportunity_scorer",
                dev_cost_hours=8,
                monthly_api_cost_increase=100.0,
                expected_monthly_value=5.0,
            ),
            "auto_patrol_frequency": InvestmentOption(
                name="auto_patrol_frequency",
                description="巡逻频率提升 — 从24小时缩短到6小时",
                upgrade_module="knowledge_forager.patrol",
                dev_cost_hours=2,
                monthly_api_cost_increase=80.0,
                expected_monthly_value=1.0,
            ),
            "llm_gateway_cascade": InvestmentOption(
                name="llm_gateway_cascade",
                description="LLM级联路由 — 小模型先试, 节省50% API费",
                upgrade_module="treellm.gateway",
                dev_cost_hours=6,
                monthly_api_cost_increase=-200.0,  # SAVES money!
                expected_monthly_value=1.0,
            ),
        }

    def evaluate_options(self) -> list[InvestmentOption]:
        """Evaluate all investment options, sorted by ROI."""
        options = sorted(self._options.values(), key=lambda x: -x.roi)
        for opt in options:
            logger.debug(
                "Investment: %s — ROI=%.0fx (cost=%.0f¥/mo, value=%.1f万/mo)",
                opt.name, opt.roi, opt.monthly_api_cost_increase, opt.expected_monthly_value,
            )
        return options

    def recommend(self, top_n: int = 3) -> str:
        """Recommend the best investment options."""
        options = self.evaluate_options()
        lines = ["## 🚀 系统进化建议 (按ROI排序)", ""]
        for opt in options[:top_n]:
            icon = {"high": "⚡", "medium": "📌", "low": "🔭"}[opt.priority]
            lines.append(
                f"{icon} **{opt.description}**\n"
                f"   ROI: {opt.roi:.0f}x | 年价值: {opt.expected_annual_value:.0f}万\n"
                f"   成本: {opt.dev_cost_hours}h开发 + {opt.monthly_api_cost_increase:.0f}¥/月API\n"
                f"   升级模块: {opt.upgrade_module}"
            )
        return "\n".join(lines)

    def execute(self, option_name: str) -> dict:
        """Execute a self-upgrade."""
        opt = self._options.get(option_name)
        if not opt:
            return {"error": f"Unknown option: {option_name}"}

        self._executed.append(option_name)
        logger.info("SelfInvestment: executed '%s' (ROI=%.0fx)", option_name, opt.roi)

        # Track the cost in revenue attribution
        self._revenue.record_cost(api_calls=0)
        if opt.monthly_api_cost_increase < 0:
            self._revenue.record(
                "cost_saving",
                f"升级{opt.name}: 月省¥{abs(opt.monthly_api_cost_increase):.0f}",
                value=abs(opt.monthly_api_cost_increase) * 12 / 10000,
            )

        return {
            "executed": option_name,
            "module": opt.upgrade_module,
            "expected_annual_value": opt.expected_annual_value,
            "roi": opt.roi,
            "cost_savings_monthly": abs(opt.monthly_api_cost_increase) if opt.monthly_api_cost_increase < 0 else 0,
        }

    def get_evolution_summary(self) -> str:
        """Get the system's self-evolution summary."""
        ra = self._revenue
        report = ra.monthly_report()

        lines = [
            "# 🌳 数字生命体 — 进化报告",
            f"本月创造价值: {report.total_value:.1f}万",
            f"累计动作: {report.system_actions}次",
            f"ROI: {report.roi:.0f}x",
            "",
        ]

        if self._executed:
            lines.append("## 已执行升级")
            for e in self._executed:
                opt = self._options.get(e)
                if opt:
                    lines.append(f"- {opt.description} (ROI: {opt.roi:.0f}x)")

        lines.append("")
        lines.append(self.recommend(2))
        return "\n".join(lines)

    def get_revenue_engine(self) -> RevenueAttribution:
        return self._revenue


# ═══ Singleton ═══

_investment: Optional[SelfInvestmentEngine] = None


def get_investment_engine() -> SelfInvestmentEngine:
    global _investment
    if _investment is None:
        _investment = SelfInvestmentEngine()
    return _investment
