"""LivingTree Market Engine — 市场智能 + 经济规律驱动的数字生命体进化.

Six engines:
  UserProfileEngine:   deep user profiling + competitor intelligence
  OpportunityScorer:   quantified opportunity scoring 0-100
  BiddingAssistant:    auto-bid strategy + competitor analysis
  MarketTrendAnalyzer: supply/demand trend analysis
  RevenueAttribution:  system calculates its own ROI
  SelfInvestmentEngine: auto-decide evolution based on ROI
"""

from .user_profile import UserProfileEngine, UserProfile, Competitor, get_profile_engine
from .opportunity_scorer import (
    OpportunityScorer, ScoredOpportunity,
    BiddingAssistant, MarketTrendAnalyzer,
    get_scorer, get_bid_assistant, get_trend_analyzer,
)
from .revenue_engine import (
    RevenueAttribution, RevenueItem, MonthlyReport,
    SelfInvestmentEngine, InvestmentOption,
    get_investment_engine,
)

__all__ = [
    "UserProfileEngine", "UserProfile", "Competitor", "get_profile_engine",
    "OpportunityScorer", "ScoredOpportunity",
    "BiddingAssistant", "MarketTrendAnalyzer",
    "get_scorer", "get_bid_assistant", "get_trend_analyzer",
    "RevenueAttribution", "RevenueItem", "MonthlyReport",
    "SelfInvestmentEngine", "InvestmentOption",
    "get_investment_engine",
]
