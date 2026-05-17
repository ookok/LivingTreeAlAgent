"""Opportunity Scorer + Bidding Assistant + Adaptive Pricing.

Three engines in one:
  1. OpportunityScorer:  每个商机量化评分 0-100
  2. BiddingAssistant:   自动投标方案 + 对手分析 + 定价建议
  3. AdaptivePricing:    市场供需驱动的价格推荐

Core economic logic:
  - 匹配度 × 紧迫度 × 利润率 × (1 - 竞争度) → composite score
  - 历史中标价 + 竞争格局 + 市场需求趋势 → recommended price
"""
# DEPRECATED — candidate for removal. No active references found.


from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger

from .user_profile import UserProfile, Competitor, get_profile_engine


# ═══ Opportunity Scoring ═══

@dataclass
class ScoredOpportunity:
    """A quantified market opportunity."""
    project_name: str
    stage: str
    date: str
    composite_score: float = 0.0     # 0-100

    match_score: float = 0.0          # 领域/地域匹配度
    urgency_score: float = 0.0        # 时间紧迫度
    profit_score: float = 0.0         # 预估利润率
    competition_score: float = 0.0    # 竞争度 (越高越不利)

    estimated_value: float = 0.0       # 预估项目金额(万元)
    estimated_profit: float = 0.0      # 预估利润(万元)
    recommended_price: str = ""        # 建议投标价
    competitor_count: int = 0
    top_competitor: str = ""

    recommendation: str = ""            # "立即跟进" / "关注" / "观望"
    source_url: str = ""


class OpportunityScorer:
    """Quantified opportunity scoring engine.

    Formula:
      composite = match(30%) + urgency(25%) + profit(25%) + (1-competition)(20%)

    Usage:
        scorer = OpportunityScorer()
        scored = scorer.score(profile, announcements)
        for s in sorted(scored, key=lambda x: -x.composite_score):
            print(f"{s.project_name}: {s.composite_score:.0f}/100 — {s.recommendation}")
    """

    def score(
        self,
        profile: UserProfile,
        announcements: list[dict],
    ) -> list[ScoredOpportunity]:
        """Score all announcements for this user profile."""
        scored = []
        for item in announcements:
            opp = self._score_one(profile, item)
            if opp.composite_score > 20:
                scored.append(opp)
        scored.sort(key=lambda x: -x.composite_score)
        return scored

    def _score_one(self, profile: UserProfile, item: dict) -> ScoredOpportunity:
        title = item.get("title", "")
        stage = item.get("stage", "")
        date = item.get("date", "")

        opp = ScoredOpportunity(
            project_name=title[:100], stage=stage, date=date,
            source_url=item.get("source_url", ""),
        )

        # Match score: domain overlap + geographic proximity
        opp.match_score = self._calc_match(profile, title)

        # Urgency score: time pressure
        opp.urgency_score = self._calc_urgency(stage, date)

        # Profit score: based on historical pricing + project type
        opp.profit_score = self._calc_profit(title, profile)

        # Competition score: how many known competitors are active
        opp.competition_score = self._calc_competition(title)
        opp.competitor_count = int(opp.competition_score * 10)

        # Composite (weighted)
        opp.composite_score = (
            opp.match_score * 30 +
            opp.urgency_score * 25 +
            opp.profit_score * 25 +
            (1 - opp.competition_score) * 20
        )

        # Value estimation
        opp.estimated_value = self._estimate_value(title, profile)
        opp.estimated_profit = opp.estimated_value * 0.4  # assume 40% margin
        opp.recommended_price = self._recommend_price(title, profile, opp)

        # Recommendation
        if opp.composite_score >= 70:
            opp.recommendation = "⚡ 立即跟进"
        elif opp.composite_score >= 50:
            opp.recommendation = "📌 重点关注"
        elif opp.composite_score >= 30:
            opp.recommendation = "🔭 保持观望"
        else:
            opp.recommendation = "— 暂不建议"

        return opp

    def score_batch(self, profile: UserProfile, announcements: list[dict]) -> list[ScoredOpportunity]:
        return self.score(profile, announcements)

    # ═══ Scoring Sub-functions ═══

    @staticmethod
    def _calc_match(profile: UserProfile, title: str) -> float:
        score = 0.0
        for domain in profile.service_domains:
            if domain in title:
                score += 0.3
        for keyword in ["项目", "工程", "扩建", "新建"]:
            if keyword in title:
                score += 0.1
        return min(1.0, score)

    @staticmethod
    def _calc_urgency(stage: str, date: str) -> float:
        urgency_map = {
            "招标公告": 1.0,
            "审批批复": 0.7,
            "受理公示": 0.5,
            "验收公示": 0.4,
            "拟批准公示": 0.6,
        }
        base = urgency_map.get(stage, 0.3)

        # Check if date is recent
        if date:
            try:
                from datetime import datetime
                d = datetime.strptime(date[:10], "%Y-%m-%d")
                days_ago = (datetime.now() - d).days
                if days_ago < 7:
                    base += 0.2
                elif days_ago < 30:
                    base += 0.1
            except Exception:
                pass

        return min(1.0, base)

    @staticmethod
    def _calc_profit(title: str, profile: UserProfile) -> float:
        base = 0.5
        if "扩建" in title or "新建" in title:
            base += 0.2
        if "大型" in title or "重点" in title:
            base += 0.15
        if profile.projects_won > 5:
            base += 0.1  # experienced → likely more efficient
        return min(1.0, base)

    @staticmethod
    def _calc_competition(title: str) -> float:
        """Higher = more competition (worse)."""
        keywords = ["环评", "环境", "监测", "检测", "治理", "环保"]
        count = sum(1 for kw in keywords if kw in title)
        return min(1.0, count * 0.25)

    @staticmethod
    def _estimate_value(title: str, profile: UserProfile) -> float:
        """Estimate project value from title keywords."""
        if "亿" in title:
            return 500.0
        if "大型" in title or "重点" in title:
            return 100.0
        if "扩建" in title:
            return 50.0
        if "新建" in title:
            return 80.0
        return 20.0  # default small project

    @staticmethod
    def _recommend_price(title: str, profile: UserProfile, opp: ScoredOpportunity) -> str:
        """Adaptive pricing recommendation."""
        estimated = opp.estimated_value
        if opp.competition_score > 0.5:
            # High competition → price aggressively
            return f"{estimated * 0.85:.0f}-{estimated * 0.95:.0f}万 (激烈竞争, 建议低价竞标)"
        elif opp.match_score > 0.8:
            # Strong match → premium pricing
            return f"{estimated * 1.05:.0f}-{estimated * 1.15:.0f}万 (匹配度高, 可适当提价)"
        return f"{estimated * 0.9:.0f}-{estimated:.0f}万 (标准定价)"


# ═══ Market Trend Analysis ═══

class MarketTrendAnalyzer:
    """Analyze market supply/demand trends from announcement data."""

    def analyze(self, announcements: list[dict]) -> dict:
        """Analyze market trends from recent announcements."""
        by_type = {}
        by_month = {}
        now = __import__('time').time()

        for item in announcements:
            stage = item.get("stage", "其他")
            by_type[stage] = by_type.get(stage, 0) + 1

            date = item.get("date", "")
            if len(date) >= 7:
                month_key = date[:7]
                by_month[month_key] = by_month.get(month_key, 0) + 1

        # Trend: is volume increasing?
        months = sorted(by_month.keys())
        trend = "stable"
        if len(months) >= 2:
            recent = by_month[months[-1]]
            previous = by_month[months[-2]]
            if recent > previous * 1.3:
                trend = "rising"      # 市场需求上升 → 建议提价
            elif recent < previous * 0.7:
                trend = "falling"     # 市场需求下降 → 建议降价

        return {
            "trend": trend,
            "total_announcements": len(announcements),
            "by_stage": by_type,
            "by_month": by_month,
            "recommendation": {
                "rising": "📈 市场需求上升，建议提升报价10-15%",
                "falling": "📉 市场需求下降，建议保守报价，关注回款周期",
                "stable": "➡ 市场平稳，维持标准定价策略",
            }.get(trend, ""),
        }


# ═══ Bidding Assistant ═══

class BiddingAssistant:
    """Auto-generate bid documents + competitor analysis."""

    def generate_bid_strategy(
        self,
        profile: UserProfile,
        opportunity: ScoredOpportunity,
        competitors: list[Competitor] = None,
    ) -> str:
        """Generate a complete bidding strategy."""
        comps = competitors or []
        active_comps = [c for c in comps if c.threat_level in ("high", "medium")]

        lines = [
            f"# 投标策略 — {opportunity.project_name[:60]}",
            f"综合评分: {opportunity.composite_score:.0f}/100",
            f"建议报价: {opportunity.recommended_price}",
            f"预估利润: {opportunity.estimated_profit:.0f}万",
            "",
        ]

        if active_comps:
            lines.append("## 已知竞争对手")
            for c in active_comps[:5]:
                lines.append(f"- {c.name}: 中标率{c.win_rate:.0%}, 均价{c.avg_price:.0f}万 ({c.threat_level})")

        lines.extend([
            "",
            "## 投标要点",
            f"1. 技术方案: 突出{', '.join(profile.service_domains[:3])}领域的项目经验",
            f"2. 报价策略: {opportunity.recommended_price}",
            "3. 工期承诺: 建议给予合理工期，不过度承诺",
            "4. 资质展示: 列举同类项目业绩",
            "",
            "## 倒计时",
        ])

        if opportunity.date:
            try:
                from datetime import datetime, timedelta
                d = datetime.strptime(opportunity.date[:10], "%Y-%m-%d")
                deadline = d + timedelta(days=opportunity.stage == "招标公告" and 20 or 90)
                days_left = (deadline - datetime.now()).days
                lines.append(f"截止日期: {deadline.strftime('%Y-%m-%d')} (剩余{days_left}天)")
            except Exception:
                pass

        return "\n".join(lines)

    def generate_technical_proposal_outline(
        self,
        profile: UserProfile,
        project_title: str,
    ) -> str:
        """Generate a technical proposal outline."""
        return f"""# 技术方案大纲 — {project_title[:60]}

## 1. 项目理解
- 项目概况分析
- 重点难点识别

## 2. 技术路线
- 工作流程: 资料收集 → 现场踏勘 → { ' → '.join(profile.service_domains[:3]) } 分析 → 报告编制
- 采用标准: 根据项目类型选择适用GB/HJ标准

## 3. 人员配置
- 项目负责人: 1名 (10年+经验)
- 专业技术人员: {min(profile.projects_won + 1, 5)}名

## 4. 工期安排
- 总工期: 30-60天
- 关键节点: 方案编制5天 → 现场工作10天 → 报告编写15天

## 5. 质量保证
- 三级审核制度
- 专家评审环节
- 同类项目业绩: {profile.projects_won}个已交付项目"""


# ═══ Singleton ═══

_scorer: Optional[OpportunityScorer] = None
_bid_assistant: Optional[BiddingAssistant] = None
_trend_analyzer: Optional[MarketTrendAnalyzer] = None


def get_scorer() -> OpportunityScorer:
    global _scorer
    if _scorer is None:
        _scorer = OpportunityScorer()
    return _scorer

def get_bid_assistant() -> BiddingAssistant:
    global _bid_assistant
    if _bid_assistant is None:
        _bid_assistant = BiddingAssistant()
    return _bid_assistant

def get_trend_analyzer() -> MarketTrendAnalyzer:
    global _trend_analyzer
    if _trend_analyzer is None:
        _trend_analyzer = MarketTrendAnalyzer()
    return _trend_analyzer
