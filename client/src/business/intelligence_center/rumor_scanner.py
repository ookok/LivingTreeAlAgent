# -*- coding: utf-8 -*-
"""
Rumor Scanner 谣言检测与舆情分析
Intelligence Center - Rumor Detection & Sentiment Analysis
"""

import asyncio
import re
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RumorVerdict(Enum):
    TRUE = "true"
    MOSTLY_TRUE = "mostly_true"
    UNVERIFIED = "unverified"
    PARTLY_FALSE = "partly_false"
    FALSE = "false"
    MISLEADING = "misleading"


class AlertLevel(Enum):
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class RumorClaim:
    claim_id: str = ""
    text: str = ""
    source_url: str = ""
    source_name: str = ""
    published_date: Optional[datetime] = None


@dataclass
class RumorResult:
    claim_id: str = ""
    verdict: RumorVerdict = RumorVerdict.UNVERIFIED
    confidence: float = 0.0
    truth_score: float = 0.5
    evidence_for: List[str] = field(default_factory=list)
    evidence_against: List[str] = field(default_factory=list)
    summary: str = ""
    risk_level: AlertLevel = AlertLevel.INFO
    checked_at: datetime = field(default_factory=datetime.now)


@dataclass
class SentimentResult:
    text: str = ""
    sentiment_score: float = 0.0
    sentiment_label: str = "neutral"
    confidence: float = 0.0
    positive_aspects: List[str] = field(default_factory=list)
    negative_aspects: List[str] = field(default_factory=list)


class SentimentAnalyzer:
    POSITIVE_WORDS = {
        "好", "棒", "赞", "优秀", "出色", "完美", "推荐", "值得", "喜欢", "爱", "满意", "惊喜",
        "good", "great", "excellent", "amazing", "awesome", "best", "recommend",
    }
    NEGATIVE_WORDS = {
        "差", "烂", "坑", "垃圾", "失望", "后悔", "骗子", "假", "投诉", "曝光", "欺骗", "虚假",
        "bad", "terrible", "awful", "worst", "scam", "fake",
    }
    INTENSIFIERS = {"非常", "特别", "极其", "超", "超级", "十分", "very", "extremely"}

    @classmethod
    def analyze(cls, text: str) -> SentimentResult:
        if not text:
            return SentimentResult(text=text)

        text_lower = text.lower()
        pos_count = sum(1 for w in cls.POSITIVE_WORDS if w in text_lower)
        neg_count = sum(1 for w in cls.NEGATIVE_WORDS if w in text_lower)
        intensifier_count = sum(1 for w in cls.INTENSIFIERS if w in text_lower)

        if pos_count > 0 or neg_count > 0:
            raw_score = (pos_count - neg_count) / (pos_count + neg_count + 1)
            intensity_factor = 1.0 + (intensifier_count * 0.2)
            sentiment_score = max(-1, min(1, raw_score * intensity_factor))
        else:
            sentiment_score = 0.0

        if sentiment_score > 0.3:
            label = "positive"
        elif sentiment_score < -0.3:
            label = "negative"
        else:
            label = "neutral"

        total = pos_count + neg_count
        confidence = min(1.0, total / 3) if total > 0 else 0.5

        return SentimentResult(
            text=text, sentiment_score=sentiment_score,
            sentiment_label=label, confidence=confidence,
            positive_aspects=[w for w in cls.POSITIVE_WORDS if w in text_lower][:3],
            negative_aspects=[w for w in cls.NEGATIVE_WORDS if w in text_lower][:3],
        )


class RumorDetector:
    HIGH_RISK_KEYWORDS = {"造假", "假货", "欺骗", "诈骗", "传销", "非法", "违禁", "fake", "scam", "fraud"}
    RUMOR_PATTERNS = [
        r"别买.*都是假的", r".*惊天秘密.*", r".*曝光.*惊人",
        r"99%.*不知道", r".*千万别.*", r"转发.*救命",
    ]

    def __init__(self, search_pipeline=None):
        self.search_pipeline = search_pipeline
        self.sentiment_analyzer = SentimentAnalyzer()

    async def check(self, claim: RumorClaim) -> RumorResult:
        result = RumorResult(claim_id=claim.claim_id)

        # 检测高风险关键词
        has_high_risk = any(kw in claim.text for kw in self.HIGH_RISK_KEYWORDS)
        matches_rumor = any(re.search(p, claim.text) for p in self.RUMOR_PATTERNS)

        # 情感分析
        sentiment = self.sentiment_analyzer.analyze(claim.text)

        # 计算真实性评分
        truth_score = 0.5
        if has_high_risk or matches_rumor:
            truth_score = 0.3
            result.evidence_against.append("检测到高风险关键词或谣言模式")

        if sentiment.sentiment_label == "negative":
            truth_score *= 0.9

        result.truth_score = truth_score

        # 判定
        if truth_score >= 0.7:
            result.verdict = RumorVerdict.MOSTLY_TRUE
        elif truth_score >= 0.4:
            result.verdict = RumorVerdict.UNVERIFIED
        else:
            result.verdict = RumorVerdict.FALSE

        # 置信度
        result.confidence = 0.6 if has_high_risk else 0.4

        # 风险评估
        risk_score = 0
        if has_high_risk:
            risk_score += 2
        if result.verdict in (RumorVerdict.FALSE, RumorVerdict.PARTLY_FALSE):
            risk_score += 3
        if sentiment.sentiment_label == "negative":
            risk_score += 1

        if risk_score >= 5:
            result.risk_level = AlertLevel.CRITICAL
        elif risk_score >= 3:
            result.risk_level = AlertLevel.HIGH
        elif risk_score >= 2:
            result.risk_level = AlertLevel.MEDIUM
        elif risk_score >= 1:
            result.risk_level = AlertLevel.LOW

        # 摘要
        verdicts = {
            RumorVerdict.TRUE: "经核实，该信息属实",
            RumorVerdict.MOSTLY_TRUE: "该信息大部分属实",
            RumorVerdict.UNVERIFIED: "该信息暂时无法核实",
            RumorVerdict.PARTLY_FALSE: "该信息部分失实",
            RumorVerdict.FALSE: "经核实，该信息为谣言",
        }
        result.summary = verdicts.get(result.verdict, "")

        return result


class SentimentAggregator:
    """舆情聚合器"""

    def __init__(self):
        self.history: List[SentimentResult] = []

    def add(self, result: SentimentResult):
        self.history.append(result)

    def get_trend(self) -> Dict[str, Any]:
        if not self.history:
            return {"trend": "neutral", "change": 0.0, "average_score": 0.0}

        scores = [r.sentiment_score for r in self.history]
        avg_score = sum(scores) / len(scores)

        if len(scores) >= 3:
            recent_avg = sum(scores[-3:]) / 3
            older_avg = sum(scores[:-3]) / max(1, len(scores) - 3)
            change = recent_avg - older_avg
        else:
            change = 0.0

        if change > 0.2:
            trend = "improving"
        elif change < -0.2:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "average_score": avg_score,
            "trend": trend,
            "change": change,
            "total_mentions": len(scores),
            "positive_count": sum(1 for s in scores if s > 0.3),
            "negative_count": sum(1 for s in scores if s < -0.3),
        }


__all__ = ["RumorVerdict", "AlertLevel", "RumorClaim", "RumorResult",
           "SentimentResult", "SentimentAnalyzer", "RumorDetector", "SentimentAggregator"]