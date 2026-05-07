"""ReasoningChain — Decision provenance and reasoning transparency.

Human experts don't just produce answers — they can explain their reasoning:
  "I chose AERSCREEN over ADMS because the terrain is flat and the source is simple.
   I also considered CALPUFF but rejected it due to lack of meteorological data."

This module captures the WHY behind every significant agent decision:
  1. Decision node: what was decided
  2. Reasoning: why this choice
  3. Alternatives: what else was considered and why rejected
  4. Confidence: how sure the agent was
  5. Validation: was the decision correct in hindsight?
  6. Revision: did the decision change later?

Integration:
  - LifeEngine: record decisions at each stage (plan, execute, reflect)
  - MetaMemory: feed validated decisions back as strategy evidence
  - SkillProgression: track decision quality over time

Usage:
    chain = get_reasoning_chain()
    chain.decide(
        domain="model_selection",
        decision="AERSCREEN",
        reasoning="Flat terrain, simple point source — Gaussian plume adequate",
        alternatives=["ADMS (too complex for flat terrain)", "CALPUFF (insufficient met data)"],
        confidence=0.85,
    )
    # Later...
    chain.validate(decision_id="d_001", outcome="model predictions within 15% of monitoring data")
"""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

CHAIN_DIR = Path(".livingtree/meta")
CHAIN_FILE = CHAIN_DIR / "reasoning_chains.json"


# ═══════════════════════════════════════════════════════════════════
# Types
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DecisionNode:
    """一次决策的完整记录."""
    id: str = field(default_factory=lambda: f"d_{uuid.uuid4().hex[:8]}")
    domain: str = "general"            # model_selection / analytical_approach / parameter_choice / ...
    decision: str = ""                 # 做了什么决定
    reasoning: str = ""                # 为什么
    alternatives: list[str] = field(default_factory=list)  # 考虑过但拒绝的替代方案
    confidence: float = 0.5            # 当时的确信度
    context: str = ""                  # 决策背景（相关任务描述）
    session_id: str = ""
    timestamp: float = field(default_factory=time.time)
    # 事后验证
    validated: bool = False
    validation_outcome: str = ""       # "决策正确，因为..."
    validation_timestamp: float = 0.0
    # 修订
    revised: bool = False
    revised_decision: str = ""
    revised_reasoning: str = ""
    revised_timestamp: float = 0.0

    @property
    def age_hours(self) -> float:
        return (time.time() - self.timestamp) / 3600

    @property
    def is_validated(self) -> bool:
        return self.validated

    @property
    def one_line(self) -> str:
        status = "✓" if self.validated else ("↻" if self.revised else "?")
        return f"[{status}] {self.domain}: {self.decision[:60]}"


@dataclass
class ChainSummary:
    """某个领域的决策链摘要."""
    domain: str
    total_decisions: int = 0
    validated_count: int = 0
    revised_count: int = 0
    avg_confidence: float = 0.0
    validation_rate: float = 0.0
    common_alternatives: list[str] = field(default_factory=list)
    key_insights: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# ReasoningChain Engine
# ═══════════════════════════════════════════════════════════════════

class ReasoningChain:
    """决策溯源引擎——记录每个关键决策的完整推理链."""

    MAX_NODES = 500
    # 决策领域分类
    DOMAINS = [
        "model_selection",         # 模型选择
        "analytical_approach",     # 分析方法选择
        "parameter_choice",        # 参数设定
        "data_interpretation",     # 数据解读
        "conclusion",              # 结论形成
        "tool_selection",          # 工具选择
        "retrieval_strategy",      # 检索策略
        "generation_strategy",     # 生成策略
    ]

    def __init__(self):
        self._nodes: dict[str, DecisionNode] = {}
        self._domain_index: dict[str, list[str]] = defaultdict(list)
        self._session_index: dict[str, list[str]] = defaultdict(list)
        self._loaded = False
        self._load()

    # ═══ Record ═══

    def decide(
        self, domain: str, decision: str, reasoning: str = "",
        alternatives: list[str] | None = None,
        confidence: float = 0.5, context: str = "",
        session_id: str = "",
    ) -> DecisionNode:
        """记录一个决策.

        Args:
            domain: 决策领域
            decision: 做了什么决定
            reasoning: 为什么这么决定
            alternatives: 考虑过的替代方案
            confidence: 当时的确信度 (0-1)
            context: 决策背景
            session_id: 关联的会话

        Returns:
            DecisionNode
        """
        node = DecisionNode(
            domain=domain, decision=decision, reasoning=reasoning,
            alternatives=alternatives or [], confidence=confidence,
            context=context, session_id=session_id,
        )
        self._nodes[node.id] = node
        self._domain_index[domain].append(node.id)
        if session_id:
            self._session_index[session_id].append(node.id)

        # 修剪
        if len(self._nodes) > self.MAX_NODES:
            self._prune_oldest()

        logger.debug(f"ReasoningChain: [{domain}] {decision[:50]} (conf={confidence:.0%})")
        return node

    # ═══ Validate ═══

    def validate(self, decision_id: str, outcome: str, correct: bool = True) -> DecisionNode | None:
        """事后验证决策是否正确.

        Args:
            decision_id: 决策ID
            outcome: 验证结果描述
            correct: 决策是否正确
        """
        node = self._nodes.get(decision_id)
        if not node:
            return None

        node.validated = True
        node.validation_outcome = outcome
        node.validation_timestamp = time.time()

        if not correct:
            logger.info(f"ReasoningChain: decision '{decision_id}' was INCORRECT — {outcome}")
        return node

    def revise(self, decision_id: str, new_decision: str, new_reasoning: str) -> DecisionNode | None:
        """修订之前的决策."""
        node = self._nodes.get(decision_id)
        if not node:
            return None

        node.revised = True
        node.revised_decision = new_decision
        node.revised_reasoning = new_reasoning
        node.revised_timestamp = time.time()
        logger.info(f"ReasoningChain: revised '{decision_id}' → {new_decision[:50]}")
        return node

    # ═══ Query ═══

    def for_domain(self, domain: str, limit: int = 20) -> list[DecisionNode]:
        """查询某领域的所有决策."""
        ids = self._domain_index.get(domain, [])[-limit:]
        return [self._nodes[i] for i in ids if i in self._nodes]

    def for_session(self, session_id: str) -> list[DecisionNode]:
        """查询某会话的所有决策."""
        ids = self._session_index.get(session_id, [])
        return [self._nodes[i] for i in ids if i in self._nodes]

    def summary(self, domain: str) -> ChainSummary:
        """某领域的决策链摘要."""
        decisions = self.for_domain(domain, limit=100)
        common_alts: list[str] = []
        insights: list[str] = []

        if not decisions:
            return ChainSummary(domain=domain)

        validated = [d for d in decisions if d.validated]
        revised = [d for d in decisions if d.revised]

        # 常见的替代方案
        alt_counts: dict[str, int] = {}
        for d in decisions:
            for alt in d.alternatives:
                alt_counts[alt] = alt_counts.get(alt, 0) + 1
            common_alts = sorted(alt_counts, key=lambda k: alt_counts.get(k, 0), reverse=True)[:5]

            # 洞察
            insights: list[str] = []
            if validated:
                correct_rate = sum(1 for d in validated
                                 if "正确" in d.validation_outcome or "correct" in d.validation_outcome.lower())
                correct_rate = correct_rate / max(len(validated), 1)
                insights.append(f"验证正确率: {correct_rate:.0%} ({len(validated)} 条)")
            if revised:
                insights.append(f"已修订 {len(revised)} 条决策")
            if domain == "model_selection":
                model_counts: dict[str, int] = {}
                for d in decisions:
                    model_counts[d.decision] = model_counts.get(d.decision, 0) + 1
                if model_counts:
                    most = max(model_counts, key=lambda k: model_counts.get(k, 0))
                    insights.append(f"最常用模型: {most} ({model_counts[most]}次)")

        return ChainSummary(
            domain=domain,
            total_decisions=len(decisions),
            validated_count=len(validated),
            revised_count=len(revised),
            avg_confidence=round(
                sum(d.confidence for d in decisions) / len(decisions), 2),
            validation_rate=round(len(validated) / len(decisions), 2),
            common_alternatives=common_alts,
            key_insights=insights,
        )

    def inject_context(self, domain: str = "", max_chars: int = 800) -> str:
        """生成可注入 LLM prompt 的决策上下文."""
        if domain:
            decisions = self.for_domain(domain, limit=5)
        else:
            # 所有领域最近的决策
            all_ids = []
            for ids in self._domain_index.values():
                all_ids.extend(ids[-3:])
            decisions = [self._nodes[i] for i in all_ids if i in self._nodes]

        if not decisions:
            return ""

        lines = ["[既往决策记录]"]
        for d in decisions:
            validation = f" — 验证: {d.validation_outcome[:60]}" if d.validated else ""
            revision = " [已修订]" if d.revised else ""
            lines.append(
                f"  - [{d.domain}] {d.decision[:40]} "
                f"(conf={d.confidence:.0%}, 替代方案: {', '.join(d.alternatives[:2]) or '无'})"
                f"{validation}{revision}")
        result = "\n".join(lines)
        return result[:max_chars]

    # ═══ Cross-Domain Insights ═══

    def cross_domain_patterns(self) -> list[str]:
        """跨领域模式发现——哪些决策模式在不同领域重复出现."""
        patterns = []
        # 检视：同一session中，一个领域的决策是否影响了另一个领域
        for sid in self._session_index:
            decisions = self.for_session(sid)
            domains = set(d.domain for d in decisions)
            if len(domains) >= 3:
                patterns.append(
                    f"会话 {sid[:8]}: 涉及 {len(domains)} 个决策领域, "
                    f"{len(decisions)} 个决策节点")
        return patterns[-10:]

    # ═══ Persistence ═══

    def _save(self):
        try:
            CHAIN_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "nodes": {
                    nid: {
                        "id": n.id, "domain": n.domain, "decision": n.decision,
                        "reasoning": n.reasoning, "alternatives": n.alternatives,
                        "confidence": n.confidence, "context": n.context,
                        "session_id": n.session_id, "timestamp": n.timestamp,
                        "validated": n.validated, "validation_outcome": n.validation_outcome,
                        "validation_timestamp": n.validation_timestamp,
                        "revised": n.revised, "revised_decision": n.revised_decision,
                        "revised_reasoning": n.revised_reasoning,
                        "revised_timestamp": n.revised_timestamp,
                    }
                    for nid, n in self._nodes.items()
                },
            }
            CHAIN_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"ReasoningChain save: {e}")

    def _load(self):
        try:
            if not CHAIN_FILE.exists():
                return
            data = json.loads(CHAIN_FILE.read_text())
            for nid, nd in data.get("nodes", {}).items():
                node = DecisionNode(**nd)
                self._nodes[nid] = node
                self._domain_index[node.domain].append(nid)
                if node.session_id:
                    self._session_index[node.session_id].append(nid)
            self._loaded = True
            logger.info(f"ReasoningChain: loaded {len(self._nodes)} decision nodes")
        except Exception as e:
            logger.debug(f"ReasoningChain load: {e}")

    def _prune_oldest(self):
        sorted_nodes = sorted(self._nodes.values(), key=lambda n: n.timestamp)
        for node in sorted_nodes[:50]:  # Remove oldest 50
            self._nodes.pop(node.id, None)
            self._domain_index[node.domain].remove(node.id)
            if node.session_id:
                self._session_index[node.session_id].remove(node.id)

    def stats(self) -> dict[str, Any]:
        total = len(self._nodes)
        validated = sum(1 for n in self._nodes.values() if n.validated)
        revised = sum(1 for n in self._nodes.values() if n.revised)
        return {
            "total_decisions": total,
            "domains": len(self._domain_index),
            "sessions": len(self._session_index),
            "validated": validated,
            "revised": revised,
            "validation_rate": round(validated / max(total, 1), 2),
        }


# ── Singleton ──────────────────────────────────────────────────────

_reasoning_chain: ReasoningChain | None = None


def get_reasoning_chain() -> ReasoningChain:
    global _reasoning_chain
    if _reasoning_chain is None:
        _reasoning_chain = ReasoningChain()
    return _reasoning_chain
