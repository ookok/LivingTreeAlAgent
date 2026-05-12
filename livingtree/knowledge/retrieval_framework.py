"""Retrieval Decision Framework (RDF) — query-shape-aware retrieval routing.

Replaces "one-size-fits-all" vector search with shape-aware routing.
Core insight: RAG failures are retrieval architecture failures, not model failures.

Query Shapes (not domains — shapes describe the TYPE of information needed):
  EXACT_LOOKUP       → keyword/exact match, NOT semantic similarity
  POLICY_VERSIONED   → latest version + staleness disclaimer
  ACCESS_CONTROLLED  → permission check BEFORE retrieval
  SEMANTIC_CONCEPT   → vector search IS appropriate here
  TEMPORAL_RECENT    → recency-weighted, time-filtered
  COMPARATIVE        → multi-source, parallel retrieval
  MULTI_HOP          → iterative, chain-of-thought retrieval
  NUMERIC_RANGE      → range query, not vector
  REGULATORY_COMPLIANCE → authoritative sources + version tracking
  DEBUG_DIAGNOSTIC   → error logs + configuration state
  GENERAL            → fallback hybrid search
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


class QueryShape(str, Enum):
    EXACT_LOOKUP = "exact_lookup"
    POLICY_VERSIONED = "policy_versioned"
    ACCESS_CONTROLLED = "access_controlled"
    SEMANTIC_CONCEPT = "semantic_concept"
    TEMPORAL_RECENT = "temporal_recent"
    COMPARATIVE = "comparative"
    MULTI_HOP = "multi_hop"
    NUMERIC_RANGE = "numeric_range"
    REGULATORY_COMPLIANCE = "regulatory_compliance"
    DEBUG_DIAGNOSTIC = "debug_diagnostic"
    GENERAL = "general"


# ── Shape → primary retrieval method mapping ──

SHAPE_METHOD_MAP: dict[str, str] = {
    QueryShape.EXACT_LOOKUP: "keyword",
    QueryShape.POLICY_VERSIONED: "keyword",
    QueryShape.ACCESS_CONTROLLED: "keyword",
    QueryShape.SEMANTIC_CONCEPT: "vector",
    QueryShape.TEMPORAL_RECENT: "temporal",
    QueryShape.COMPARATIVE: "multi_source",
    QueryShape.MULTI_HOP: "iterative",
    QueryShape.NUMERIC_RANGE: "range",
    QueryShape.REGULATORY_COMPLIANCE: "authoritative",
    QueryShape.DEBUG_DIAGNOSTIC: "keyword",
    QueryShape.GENERAL: "hybrid",
}

SHAPE_FALLBACK_MAP: dict[str, list[str]] = {
    QueryShape.EXACT_LOOKUP: ["vector", "hybrid"],
    QueryShape.POLICY_VERSIONED: ["vector", "temporal"],
    QueryShape.ACCESS_CONTROLLED: [],
    QueryShape.SEMANTIC_CONCEPT: ["hybrid", "keyword"],
    QueryShape.TEMPORAL_RECENT: ["vector", "keyword"],
    QueryShape.COMPARATIVE: ["vector", "keyword"],
    QueryShape.MULTI_HOP: ["vector", "keyword"],
    QueryShape.NUMERIC_RANGE: ["keyword", "vector"],
    QueryShape.REGULATORY_COMPLIANCE: ["keyword", "multi_source"],
    QueryShape.DEBUG_DIAGNOSTIC: ["temporal", "vector"],
    QueryShape.GENERAL: ["keyword", "vector"],
}

SHAPE_DEFAULT_FILTERS: dict[str, dict] = {
    QueryShape.POLICY_VERSIONED: {"min_version": "2025", "sort_by": "version"},
    QueryShape.TEMPORAL_RECENT: {"recency_days": 30},
    QueryShape.ACCESS_CONTROLLED: {"require_permission": True},
    QueryShape.REGULATORY_COMPLIANCE: {"min_sources": 2, "authoritative_only": True},
    QueryShape.NUMERIC_RANGE: {},
    QueryShape.DEBUG_DIAGNOSTIC: {"include_logs": True, "recency_days": 7},
}

SHAPE_THRESHOLDS: dict[str, float] = {
    QueryShape.EXACT_LOOKUP: 0.85,
    QueryShape.POLICY_VERSIONED: 0.70,
    QueryShape.ACCESS_CONTROLLED: 0.80,
    QueryShape.SEMANTIC_CONCEPT: 0.50,
    QueryShape.TEMPORAL_RECENT: 0.60,
    QueryShape.COMPARATIVE: 0.45,
    QueryShape.MULTI_HOP: 0.45,
    QueryShape.NUMERIC_RANGE: 0.90,
    QueryShape.REGULATORY_COMPLIANCE: 0.75,
    QueryShape.DEBUG_DIAGNOSTIC: 0.65,
    QueryShape.GENERAL: 0.55,
}

SHAPE_VALIDATION_REQUIRED: dict[str, bool] = {
    QueryShape.EXACT_LOOKUP: True,
    QueryShape.POLICY_VERSIONED: True,
    QueryShape.ACCESS_CONTROLLED: True,
    QueryShape.SEMANTIC_CONCEPT: False,
    QueryShape.TEMPORAL_RECENT: True,
    QueryShape.COMPARATIVE: True,
    QueryShape.MULTI_HOP: True,
    QueryShape.NUMERIC_RANGE: True,
    QueryShape.REGULATORY_COMPLIANCE: True,
    QueryShape.DEBUG_DIAGNOSTIC: True,
    QueryShape.GENERAL: False,
}

SHAPE_MAX_SOURCES: dict[str, int] = {
    QueryShape.EXACT_LOOKUP: 3,
    QueryShape.POLICY_VERSIONED: 5,
    QueryShape.ACCESS_CONTROLLED: 3,
    QueryShape.SEMANTIC_CONCEPT: 8,
    QueryShape.TEMPORAL_RECENT: 10,
    QueryShape.COMPARATIVE: 12,
    QueryShape.MULTI_HOP: 6,
    QueryShape.NUMERIC_RANGE: 5,
    QueryShape.REGULATORY_COMPLIANCE: 8,
    QueryShape.DEBUG_DIAGNOSTIC: 10,
    QueryShape.GENERAL: 5,
}

SYSTEM_PROMPT_HINTS: dict[str, str] = {
    QueryShape.EXACT_LOOKUP: (
        "注意: 未找到精确匹配结果，以下是最相似的内容。请明确指出这不是精确匹配。"
    ),
    QueryShape.POLICY_VERSIONED: (
        "注意: 检索到的政策可能不是最新版本，请在回答中注明版本日期。"
    ),
    QueryShape.ACCESS_CONTROLLED: (
        "注意: 部分内容可能因权限限制未完整展示，请仅基于可访问的内容回答。"
    ),
    QueryShape.TEMPORAL_RECENT: (
        "注意: 以下为近期数据，可能不包含所有历史信息。"
    ),
    QueryShape.REGULATORY_COMPLIANCE: (
        "注意: 合规性判断需要权威来源确认，以下信息仅供参考，不构成法律建议。"
    ),
}

SHAPE_WARNINGS: dict[str, list[str]] = {
    QueryShape.EXACT_LOOKUP: [],
    QueryShape.POLICY_VERSIONED: ["数据可能已过时", "请确认是否为最新版本"],
    QueryShape.ACCESS_CONTROLLED: ["需要验证权限", "敏感数据已过滤"],
    QueryShape.SEMANTIC_CONCEPT: [],
    QueryShape.TEMPORAL_RECENT: ["仅包含近期数据"],
    QueryShape.COMPARATIVE: [],
    QueryShape.MULTI_HOP: ["多步推理可能存在累积误差"],
    QueryShape.NUMERIC_RANGE: ["数值范围可能不精确"],
    QueryShape.REGULATORY_COMPLIANCE: ["需要权威来源验证", "不构成法律建议"],
    QueryShape.DEBUG_DIAGNOSTIC: ["诊断结果需人工确认"],
    QueryShape.GENERAL: [],
}


@dataclass
class RetrievalStrategy:
    """Concrete retrieval plan derived from query shape analysis."""
    shape: QueryShape
    primary_method: str
    secondary_methods: list[str] = field(default_factory=list)
    filters: dict = field(default_factory=dict)
    confidence_threshold: float = 0.55
    requires_validation: bool = False
    max_sources: int = 5
    system_prompt_override: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "shape": self.shape.value,
            "primary_method": self.primary_method,
            "secondary_methods": list(self.secondary_methods),
            "filters": dict(self.filters),
            "confidence_threshold": self.confidence_threshold,
            "requires_validation": self.requires_validation,
            "max_sources": self.max_sources,
            "system_prompt_override": self.system_prompt_override,
        }


@dataclass
class RetrievalDecision:
    """Full classification + strategy decision for a single query."""
    query: str
    shape: QueryShape
    confidence: float
    strategy: RetrievalStrategy
    reasoning: str = ""
    warnings: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "query": self.query[:200],
            "shape": self.shape.value,
            "confidence": round(self.confidence, 4),
            "strategy": self.strategy.to_dict(),
            "reasoning": self.reasoning,
            "warnings": list(self.warnings),
            "timestamp": int(self.timestamp),
        }


@dataclass
class ShapeStats:
    """Per-shape tracking statistics."""
    total: int = 0
    successes: int = 0
    failures: int = 0

    @property
    def success_rate(self) -> float:
        return self.successes / max(1, self.total)


# ── Regex-based pattern detectors ──

_EXACT_PATTERNS = [
    re.compile(r"(什么时候|何时|几号|哪天|日期|时间).*(?:合同|订单|客户|申请|记录|续签)"),
    re.compile(r"(?:合同|订单|客户|申请|记录|续签).*(?:什么时候|何时|几号|哪天|日期|时间)"),
    re.compile(r"(?:合同号|订单号|编号|ID|账号|工号)[是为:：]?\s*[A-Za-z0-9\-_]+"),
    re.compile(r"(?:编号|序号|代码|批次)[是为:：]\s*[A-Za-z0-9\-_]+"),
    re.compile(r"(?:到期|截止|生效|签署|签订)(?:日期|时间|年月日)"),
]

_ACCESS_PATTERNS = [
    re.compile(r"(?:无权限|无权访问|没有权限|不可访问|拒绝访问|访问被拒)"),
    re.compile(r"(?:谁能看|谁可以看|哪些人能|允许.*查看)"),
    re.compile(r"(?:是否有权限|可否访问|允许查看|授权查看)"),
    re.compile(r"(?:安全级别|密级|访问级别|权限等级)"),
    re.compile(r"(?:保密数据|机密文件|脱敏|敏感数据).*(?:访问|查看|查阅)"),
]

_POLICY_PATTERNS = [
    re.compile(r"(?:当前|最新|最新版|现行).*(?:政策|规定|制度|保留|策略|规章|办法|条例)"),
    re.compile(r"(?:政策|规定|制度|保留|策略|规章|办法|条例).*(?:当前|最新|最新版|现行)"),
    re.compile(r"(?:数据保留|存储期限|归档|保存).*(?:政策|规定|要求|期限)"),
    re.compile(r"(?:版本|修订|更新).*(?:政策|规定|制度|文档)"),
]

_TEMPORAL_PATTERNS = [
    re.compile(r"(?:最近|上周|本周|本月|近期|最新|刚).*(?:日志|异常|错误|事件|变更)"),
    re.compile(r"(?:过去|近)\s*(\d+)\s*(?:天|周|月|小时|年)"),
    re.compile(r"(?:今天|昨天|刚刚|刚才).*(?:发生|出现|报错|提交)"),
    re.compile(r"(?:(\d+)\s*(?:天|周|月|小时|年)\s*(?:内|以来|以内))"),
]

_COMPARATIVE_PATTERNS = [
    re.compile(r"(?:对比|比较|区别|差异)"),
    re.compile(r"\bvs\b", re.IGNORECASE),
    re.compile(r"(?:哪个更好|哪个更优|优缺点|优劣|异同)"),
    re.compile(r".+(?:和|与|同|跟).+(?:哪个|更好|更优|区别|差异|不同)"),
]

_MULTI_HOP_PATTERNS = [
    re.compile(r"(?:如何影响|导致|进而|因此|从而|最终)"),
    re.compile(r"(?:如果|假如|假设|若).*(?:那么|则|会).*(?:如何|怎样|什么)"),
    re.compile(r"(?:什么|哪些)(?:因素|条件|规则).*(?:决定|影响|导致)"),
    re.compile(r"(?:先.*再|首先.*然后|第一步.*第二步)"),
]

_NUMERIC_PATTERNS = [
    re.compile(r"(\d+)\s*[-~—到至]\s*(\d+)\s*(?:万|亿|千|百|元|美元|%)"),
    re.compile(r"(?:大于|小于|至少|不超过|以上|以下|不低于|不高于)\s*(\d+)"),
    re.compile(r"(?:预算|金额|价格|费用|成本|数量|范围).*(\d+)"),
    re.compile(r"(?:之间|范围内|区间)\s*(\d+).*(\d+)"),
]

_REGULATORY_PATTERNS = [
    re.compile(r"(?:GDPR|ISO\s*\d+|SOC\s*2|HIPAA|PCI|等保|HJ\s*\d+|GB\s*\d+|GB/T\s*\d+)"),
    re.compile(r"第\d+条.*(?:规定|要求|说明)"),
    re.compile(r"(?:遵守|合规|符合|违反|遵循|满足).*(?:法规|条例|标准|要求)"),
    re.compile(r"(?:法律|法规|条例|标准).*(?:要求|规定)"),
]

_DEBUG_PATTERNS = [
    re.compile(r"为什么.*(?:报错|出错|错误|失败|异常|故障|崩溃|不行)"),
    re.compile(r"(?:报错|什么原因|哪里出了问题|为何失败)"),
    re.compile(r"(?:异常|故障|失败|错误|崩溃|超时).*(?:原因|排查|定位|分析)"),
    re.compile(r"(?:日志|报错|错误码|错误信息).*(?:分析|查看|检查)"),
    re.compile(r"(?:怎么|如何).*(?:修复|解决|处理).*(?:错误|异常|失败)"),
]

_SEMANTIC_PATTERNS = [
    re.compile(r"(?:解释|阐述|说明|什么是|含义|定义|概念)"),
    re.compile(r"(?:原理|机制|架构|模型).*(?:是什么|如何)"),
    re.compile(r"(?:了解|理解|介绍|概述).*$"),
]


class QueryShapeClassifier:
    """Fast regex-based query shape classifier — no LLM call needed.

    Classifies queries into shapes based on keyword and structural patterns.
    Runs in priority order: first match wins.
    """

    def __init__(self):
        self._detectors: list[tuple[str, list[re.Pattern], float]] = [
            ("EXACT_LOOKUP", _EXACT_PATTERNS, 0.85),
            ("POLICY_VERSIONED", _POLICY_PATTERNS, 0.82),
            ("DEBUG_DIAGNOSTIC", _DEBUG_PATTERNS, 0.80),
            ("ACCESS_CONTROLLED", _ACCESS_PATTERNS, 0.90),
            ("REGULATORY_COMPLIANCE", _REGULATORY_PATTERNS, 0.88),
            ("NUMERIC_RANGE", _NUMERIC_PATTERNS, 0.87),
            ("COMPARATIVE", _COMPARATIVE_PATTERNS, 0.78),
            ("MULTI_HOP", _MULTI_HOP_PATTERNS, 0.75),
            ("TEMPORAL_RECENT", _TEMPORAL_PATTERNS, 0.80),
            ("SEMANTIC_CONCEPT", _SEMANTIC_PATTERNS, 0.65),
        ]

    def classify(self, query: str, user_context: Optional[dict] = None) -> RetrievalDecision:
        """Classify a query into a QueryShape and build a RetrievalDecision.

        Args:
            query: The user's query string.
            user_context: Optional dict with access_level, department, timezone.
        """
        query_stripped = query.strip()
        if not query_stripped:
            return self._fallback_decision(query_stripped)

        # Run detectors in priority order — first match wins
        for shape_name, patterns, base_confidence in self._detectors:
            for pat in patterns:
                if pat.search(query_stripped):
                    shape = QueryShape(shape_name.lower())
                    confidence = base_confidence
                    # Boost confidence for multi-pattern matches
                    match_count = sum(1 for p in patterns if p.search(query_stripped))
                    if match_count >= 2:
                        confidence = min(0.99, base_confidence + 0.08)
                    logger.debug(
                        f"QueryShapeClassifier: '{query_stripped[:60]}' → {shape.value} "
                        f"(conf={confidence:.2f}, pattern={pat.pattern[:60]})"
                    )
                    return self._build_decision(query_stripped, shape, confidence, user_context)

        # No pattern matched → GENERAL
        return self._build_decision(
            query_stripped, QueryShape.GENERAL, 0.50, user_context,
        )

    @staticmethod
    def _build_decision(
        query: str,
        shape: QueryShape,
        confidence: float,
        user_context: Optional[dict] = None,
    ) -> RetrievalDecision:
        """Build a RetrievalDecision with the full strategy derived from shape."""
        uc = user_context or {}
        access_level = uc.get("access_level", "public")

        primary = SHAPE_METHOD_MAP.get(shape.value, "hybrid")
        fallback = list(SHAPE_FALLBACK_MAP.get(shape.value, ["vector", "keyword"]))
        filters = dict(SHAPE_DEFAULT_FILTERS.get(shape.value, {}))
        if access_level and access_level != "public":
            filters["access_level"] = access_level

        # ACCESS_CONTROLLED: skip retrieval if user has no permission
        warnings = list(SHAPE_WARNINGS.get(shape.value, []))
        if shape == QueryShape.ACCESS_CONTROLLED and access_level == "public":
            warnings.append("当前用户无权访问敏感数据，检索范围已限制")
            confidence = 0.95

        system_hint = SYSTEM_PROMPT_HINTS.get(shape.value)

        strategy = RetrievalStrategy(
            shape=shape,
            primary_method=primary,
            secondary_methods=fallback,
            filters=filters,
            confidence_threshold=SHAPE_THRESHOLDS.get(shape.value, 0.55),
            requires_validation=SHAPE_VALIDATION_REQUIRED.get(shape.value, False),
            max_sources=SHAPE_MAX_SOURCES.get(shape.value, 5),
            system_prompt_override=system_hint,
        )

        reasoning = _build_reasoning(shape, query)

        return RetrievalDecision(
            query=query,
            shape=shape,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            warnings=warnings,
        )

    @staticmethod
    def _fallback_decision(query: str) -> RetrievalDecision:
        return QueryShapeClassifier._build_decision(query, QueryShape.GENERAL, 0.30)


def _build_reasoning(shape: QueryShape, query: str) -> str:
    """Generate human-readable reasoning for why a shape was chosen."""
    reason_map = {
        QueryShape.EXACT_LOOKUP: f"查询包含精确标识符/日期匹配需求，使用关键词检索而非语义搜索",
        QueryShape.POLICY_VERSIONED: f"查询涉及政策/规定类文档，需要最新版本并附带时效性声明",
        QueryShape.ACCESS_CONTROLLED: f"查询涉及权限敏感数据，需先验证访问权限再进行检索",
        QueryShape.SEMANTIC_CONCEPT: f"查询为概念解释类问题，向量语义搜索最为合适",
        QueryShape.TEMPORAL_RECENT: f"查询要求近期数据，启用时间加权过滤",
        QueryShape.COMPARATIVE: f"查询为对比类问题，启用多源并行检索",
        QueryShape.MULTI_HOP: f"查询需要链式推理，启用迭代式检索",
        QueryShape.NUMERIC_RANGE: f"查询包含数值范围，使用范围查询而非向量搜索",
        QueryShape.REGULATORY_COMPLIANCE: f"查询涉及法规合规，需要权威来源并追踪版本",
        QueryShape.DEBUG_DIAGNOSTIC: f"查询为故障诊断类，需要日志和配置状态数据",
        QueryShape.GENERAL: f"查询未匹配特定模式，使用通用混合检索",
    }
    return reason_map.get(shape, "使用通用检索策略")


class RetrievalFramework:
    """Orchestrator for query-shape-aware retrieval routing.

    Usage:
        rf = get_retrieval_framework()
        decision = rf.decide("合同续签日期是什么时候？")
        params = rf.get_retrieval_params(decision)
        # → {"method": "keyword", "filters": {...}, ...}
    """

    MAX_DECISION_LOG = 200

    def __init__(self):
        self._classifier = QueryShapeClassifier()
        self._decision_log: list[RetrievalDecision] = []
        self._stats: dict[str, ShapeStats] = defaultdict(ShapeStats)
        self._total_decisions = 0

    # ── Core API ──

    def decide(
        self, query: str, user_context: Optional[dict] = None,
    ) -> RetrievalDecision:
        """Classify query shape → generate strategy → return decision.

        Args:
            query: User query string.
            user_context: Optional dict with access_level, department, timezone.
        """
        decision = self._classifier.classify(query, user_context)
        self._log_decision(decision)
        logger.info(
            f"RDF: '{query[:60]}' → {decision.shape.value} "
            f"(conf={decision.confidence:.2f}, method={decision.strategy.primary_method})"
        )
        return decision

    def get_retrieval_params(self, decision: RetrievalDecision) -> dict:
        """Convert a RetrievalDecision into concrete retrieval system parameters.

        These parameters can be passed directly to unified_retrieve() or
        any retrieval backend.

        Args:
            decision: A RetrievalDecision from self.decide().

        Returns:
            Dict with method, fallback, filters, top_k, min_score, validate, system_hint.
        """
        strat = decision.strategy
        params: dict = {
            "method": strat.primary_method,
            "fallback": list(strat.secondary_methods),
            "filters": dict(strat.filters),
            "top_k": strat.max_sources,
            "min_score": strat.confidence_threshold,
            "validate": strat.requires_validation,
            "system_hint": strat.system_prompt_override,
        }
        return params

    # ── Analytics ──

    def get_shape_distribution(self) -> dict[str, int]:
        """Return count of decisions per query shape."""
        dist: dict[str, int] = {}
        for shape_name in QueryShape:
            key = shape_name.value
            dist[key] = self._stats[key].total
        return dist

    def record_outcome(self, decision: RetrievalDecision, was_successful: bool) -> None:
        """Feedback loop: track which strategies work for which shapes.

        Args:
            decision: The original RetrievalDecision.
            was_successful: Whether the retrieval was ultimately helpful.
        """
        shape_key = decision.shape.value
        self._stats[shape_key].total += 1
        if was_successful:
            self._stats[shape_key].successes += 1
        else:
            self._stats[shape_key].failures += 1

    def stats(self) -> dict:
        """Return aggregate statistics about the framework's performance.

        Returns:
            Dict with total_decisions, shape_distribution, success_rate_by_shape.
        """
        return {
            "total_decisions": self._total_decisions,
            "shape_distribution": self.get_shape_distribution(),
            "success_rate_by_shape": {
                k: round(v.success_rate, 3) if v.total > 0 else None
                for k, v in self._stats.items()
            },
            "overall_success_rate": round(
                self._overall_success_rate(), 3
            ) if self._total_decisions > 0 else None,
        }

    # ── Internal ──

    def _log_decision(self, decision: RetrievalDecision) -> None:
        self._decision_log.append(decision)
        self._total_decisions += 1
        shape_key = decision.shape.value
        self._stats[shape_key].total += 1
        if len(self._decision_log) > self.MAX_DECISION_LOG:
            self._decision_log = self._decision_log[-self.MAX_DECISION_LOG:]

    def _overall_success_rate(self) -> float:
        total_outcomes = sum(
            s.successes + s.failures for s in self._stats.values()
        )
        total_successes = sum(s.successes for s in self._stats.values())
        return total_successes / max(1, total_outcomes) if total_outcomes > 0 else 0.0


# ── Integration helpers ──

def apply_filters(
    docs: list[dict], filters: dict, current_time: Optional[float] = None,
) -> list[dict]:
    """Apply post-retrieval filters: recency, access_level, version, source count.

    Args:
        docs: List of document dicts, each with keys like 'ts', 'access_level', 'version'.
        filters: Filter dict from RetrievalStrategy.filters.
        current_time: Current timestamp for recency calculation.

    Returns:
        Filtered list of docs.
    """
    now = current_time or time.time()
    filtered = list(docs)

    # Recency filter
    if "recency_days" in filters:
        cutoff = now - filters["recency_days"] * 86400
        filtered = [
            d for d in filtered
            if d.get("ts", now) >= cutoff
        ]

    # Access level filter
    if "access_level" in filters:
        required = filters["access_level"]
        level_rank = {"public": 0, "employee": 1, "admin": 2, "confidential": 3}
        min_rank = level_rank.get(required, 0)
        filtered = [
            d for d in filtered
            if level_rank.get(d.get("access_level", "public"), 0) <= min_rank
        ]

    # Version filter
    if "min_version" in filters:
        min_ver = _parse_version(filters["min_version"])
        filtered = [
            d for d in filtered
            if _parse_version(str(d.get("version", "0"))) >= min_ver
        ]
        if "sort_by" in filters and filters["sort_by"] == "version":
            filtered.sort(key=lambda d: _parse_version(str(d.get("version", "0"))), reverse=True)

    # Authoritative sources only
    if filters.get("authoritative_only"):
        AUTHORITATIVE_SOURCES = {
            "legal_db", "policy_repo", "regulatory_db", "compliance_store",
            "document_kb", "knowledge_base",
        }
        filtered = [
            d for d in filtered
            if d.get("source", "") in AUTHORITATIVE_SOURCES
        ]

    # Include logs
    if filters.get("include_logs"):
        # Already includes all, just tag for downstream
        for d in filtered:
            if d.get("source") in ("error_log", "app_log", "system_log"):
                d["priority"] = "high"

    logger.debug(
        f"apply_filters: {len(docs)} docs → {len(filtered)} after filters={filters}"
    )
    return filtered


def validate_retrieval(
    docs: list[dict], decision: RetrievalDecision,
) -> dict:
    """Post-retrieval quality check based on query shape.

    Args:
        docs: Retrieved documents after filtering.
        decision: The original RetrievalDecision.

    Returns:
        Dict with 'passed', 'issues', 'warnings'.
    """
    issues: list[str] = []
    warnings: list[str] = list(decision.warnings)

    shape = decision.shape
    strat = decision.strategy

    # Minimum source count check
    if len(docs) < 1:
        issues.append("检索结果为空，无法验证")
        return {"passed": False, "issues": issues, "warnings": warnings}

    # Score threshold check
    if docs and all(d.get("score", 0) < strat.confidence_threshold for d in docs):
        issues.append(
            f"所有结果置信度低于阈值 {strat.confidence_threshold}"
        )

    # EXACT_LOOKUP: check if any document matches exactly
    if shape == QueryShape.EXACT_LOOKUP:
        query = decision.query.lower()
        has_exact = any(
            query in d.get("text", "").lower() for d in docs
        )
        if not has_exact:
            issues.append("未找到精确匹配，以下是最相似结果")
            warnings.append("非精确匹配")

    # ACCESS_CONTROLLED: verify no confidential data leaked
    if shape == QueryShape.ACCESS_CONTROLLED:
        confidential = [
            d for d in docs
            if d.get("access_level") == "confidential"
        ]
        if confidential:
            warnings.append(f"过滤了 {len(confidential)} 条敏感数据")

    # POLICY_VERSIONED: verify version info present
    if shape == QueryShape.POLICY_VERSIONED:
        has_version = any(d.get("version") for d in docs)
        if not has_version:
            issues.append("检索结果缺少版本信息")
            warnings.append("数据可能已过时")

    # REGULATORY_COMPLIANCE: require at least 2 authoritative sources
    if shape == QueryShape.REGULATORY_COMPLIANCE:
        if len(docs) < 2:
            issues.append("合规查询需要至少2个权威来源，当前不足")
            warnings.append("合规信息不完整")

    # DEBUG_DIAGNOSTIC: check for log data presence
    if shape == QueryShape.DEBUG_DIAGNOSTIC:
        has_logs = any(
            d.get("source", "") in ("error_log", "app_log", "system_log")
            for d in docs
        )
        if not has_logs:
            warnings.append("未找到相关日志数据")

    passed = len(issues) == 0

    logger.debug(
        f"validate_retrieval: shape={shape.value}, passed={passed}, "
        f"issues={len(issues)}, warnings={len(warnings)}"
    )

    return {"passed": passed, "issues": issues, "warnings": warnings}


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string like '2025' or '2.3.1' into a comparable tuple."""
    try:
        return tuple(int(x) for x in re.findall(r"\d+", version_str))
    except (ValueError, TypeError):
        return (0,)


# ── Singleton ──

_framework: Optional[RetrievalFramework] = None


def get_retrieval_framework() -> RetrievalFramework:
    """Get or create the singleton RetrievalFramework instance."""
    global _framework
    if _framework is None:
        _framework = RetrievalFramework()
        logger.info("RetrievalFramework initialized (query-shape-aware routing)")
    return _framework
