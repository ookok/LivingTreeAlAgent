"""Precedence Model — learn transition probabilities between knowledge fragments.

OKH-RAG (arXiv:2604.12185) 核心组件：
  - Transition Matrix: P(fact_j | fact_i) — 事实间的转移概率
  - Self-supervised: 从文档/检索序列中自学先后依赖，无需时间标签
  - Inference: 给定事实集合，推断最似然排序

Integration:
  - HypergraphStore: 提供共现统计数据用于学习
  - OrderAwareReranker: 转移概率作为重排序特征
  - PlanValidator: 步骤顺序合理性评分
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Transition:
    """A learned transition between two logical fact types."""
    from_type: str
    to_type: str
    probability: float              # P(to | from) smoothed probability
    raw_count: int                  # Observed co-occurrence count
    confidence: float               # Statistical confidence in this transition
    examples: list[str] = field(default_factory=list)  # Example transition instances


@dataclass
class PrecedenceResult:
    """Result of ordering a set of facts."""
    ordered_indices: list[int]      # Indices of facts in optimal order
    ordered_types: list[str]        # Type labels in optimal order
    total_score: float              # Total sequence score (0-1)
    per_transition_scores: list[tuple[str, str, float]] = field(default_factory=list)
    alternatives: list[list[int]] = field(default_factory=list)  # Alternative orderings


class PrecedenceModel:
    """Learned transition model for knowledge fragment ordering.

    Learns P(type_j | type_i) from observed sequences without temporal labels.
    The key insight from OKH-RAG: order emerges from statistical co-occurrence
    patterns in training data, not from explicit time annotations.

    Fact types are derived from:
      - Relation labels in hyperedges (e.g., "definition" → "threshold" → "compliance")
      - Document section hierarchy (e.g., "background" → "method" → "results")
      - Tool/step types in execution plans (e.g., "retrieve" → "analyze" → "generate")
    """

    def __init__(self, smoothing: float = 0.01):
        self._smoothing = smoothing
        # type → {next_type: count}
        self._transitions: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # type → total outgoing count
        self._out_counts: dict[str, int] = defaultdict(int)
        # Raw sequences for periodic relearning
        self._sequences: list[list[str]] = []

    # ── Training ──

    def observe_sequence(self, type_sequence: list[str]) -> None:
        """Observe a sequence of fact/document/step types for learning.

        Args:
            type_sequence: Ordered list of type labels (e.g., ["background", "method", "result"])
        """
        if len(type_sequence) < 2:
            return
        self._sequences.append(type_sequence)
        for i in range(len(type_sequence) - 1):
            self._transitions[type_sequence[i]][type_sequence[i + 1]] += 1
            self._out_counts[type_sequence[i]] += 1

    def observe_pairs(self, pairs: list[tuple[str, str]]) -> None:
        """Observe individual (before, after) type pairs."""
        for before, after in pairs:
            self._transitions[before][after] += 1
            self._out_counts[before] += 1

    def learn_from_hyperedges(
        self, edges: list[Any],
        type_key: str = "relation",
    ) -> None:
        """Learn transitions from a collection of hyperedges with precedence."""
        for edge in edges:
            edge_type = getattr(edge, type_key, str(edge))
            before_ids = getattr(edge, "precedence_before", [])
            after_ids = getattr(edge, "precedence_after", [])
            for b_id in before_ids:
                self._transitions[edge_type][f"before:{b_id}"] += 1
                self._out_counts[edge_type] += 1
            for a_id in after_ids:
                self._transitions[f"after:{a_id}"][edge_type] += 1
                self._out_counts[f"after:{a_id}"] += 1

    # ── Inference ──

    def transition_prob(self, from_type: str, to_type: str) -> float:
        """Get P(to_type | from_type) with Laplace smoothing."""
        count = self._transitions.get(from_type, {}).get(to_type, 0)
        total = self._out_counts.get(from_type, 0)
        vocab_size = len(self._transitions)
        # Smoothed probability
        return (count + self._smoothing) / (total + self._smoothing * vocab_size + 1e-9)

    def get_transitions(self, from_type: str, min_prob: float = 0.01) -> list[Transition]:
        """Get all likely next types for a given type."""
        results = []
        total = self._out_counts.get(from_type, 0)
        for to_type, count in self._transitions.get(from_type, {}).items():
            prob = self.transition_prob(from_type, to_type)
            if prob < min_prob:
                continue
            confidence = 1.0 - math.exp(-count / 5.0) if count > 0 else 0.0
            results.append(Transition(
                from_type=from_type, to_type=to_type,
                probability=round(prob, 4), raw_count=count,
                confidence=round(confidence, 3),
            ))
        results.sort(key=lambda t: -t.probability)
        return results

    # ── Order Inference (OKH-RAG core) ──

    def order_facts(
        self, fact_types: list[str], beam_width: int = 3,
    ) -> PrecedenceResult:
        """Infer the most-likely ordering of a set of fact types.

        Uses greedy beam search over transition probabilities.

        Args:
            fact_types: Unordered list of type labels to order
            beam_width: Number of candidate sequences to maintain

        Returns:
            PrecedenceResult with optimal ordering and scores
        """
        n = len(fact_types)
        if n <= 1:
            return PrecedenceResult(
                ordered_indices=list(range(n)),
                ordered_types=list(fact_types),
                total_score=1.0 if n == 1 else 0.0,
            )

        # Beam search: (ordered_indices, score, last_type)
        beam: list[tuple[list[int], float, str]] = []
        # Initialize: try each fact as first
        for i in range(n):
            beam.append(([i], 0.5, fact_types[i]))

        for _ in range(n - 1):
            candidates: list[tuple[list[int], float, str]] = []
            for seq, score, last_type in beam:
                used = set(seq)
                for j in range(n):
                    if j in used:
                        continue
                    next_type = fact_types[j]
                    trans_prob = self.transition_prob(last_type, next_type)
                    new_score = score * (0.3 + 0.7 * trans_prob)
                    candidates.append((seq + [j], new_score, next_type))
            beam = sorted(candidates, key=lambda x: -x[1])[:beam_width]

        if not beam:
            # Fallback: return original order
            return PrecedenceResult(
                ordered_indices=list(range(n)),
                ordered_types=list(fact_types),
                total_score=0.3,
            )

        best_indices, best_score, _ = beam[0]
        best_types = [fact_types[i] for i in best_indices]

        # Per-transition scores for explainability
        per_trans = []
        for i in range(len(best_types) - 1):
            prob = self.transition_prob(best_types[i], best_types[i + 1])
            per_trans.append((best_types[i], best_types[i + 1], round(prob, 3)))

        # Alternatives
        alternatives = [indices for indices, _, _ in beam[:3]]

        return PrecedenceResult(
            ordered_indices=best_indices,
            ordered_types=best_types,
            total_score=round(best_score, 4),
            per_transition_scores=per_trans,
            alternatives=alternatives,
        )

    def score_ordering(self, ordered_types: list[str]) -> float:
        """Score a given ordering by its transition probabilities (0-1)."""
        if len(ordered_types) <= 1:
            return 1.0
        log_prob = 0.0
        for i in range(len(ordered_types) - 1):
            p = self.transition_prob(ordered_types[i], ordered_types[i + 1])
            log_prob += math.log(max(p, 1e-9))
        n = len(ordered_types) - 1
        avg_log = log_prob / n
        return max(0.0, min(1.0, math.exp(avg_log)))

    # ── Stats & Persistence ──

    def stats(self) -> dict[str, Any]:
        total_transitions = sum(len(v) for v in self._transitions.values())
        return {
            "type_count": len(self._transitions),
            "total_transitions": total_transitions,
            "sequence_count": len(self._sequences),
            "top_types": sorted(
                self._out_counts.keys(),
                key=lambda t: -self._out_counts[t],
            )[:10],
        }

    def to_dict(self) -> dict:
        """Serialize transition data for persistence."""
        return {
            "transitions": {
                f: dict(t) for f, t in self._transitions.items()
            },
            "out_counts": dict(self._out_counts),
        }

    @classmethod
    def from_dict(cls, data: dict, smoothing: float = 0.01) -> "PrecedenceModel":
        """Deserialize."""
        model = cls(smoothing=smoothing)
        for f, t_dict in data.get("transitions", {}).items():
            for t, cnt in t_dict.items():
                model._transitions[f][t] = cnt
        for t, cnt in data.get("out_counts", {}).items():
            model._out_counts[t] = cnt
        return model

    # ── Domain-specific initializers ──

    @classmethod
    def for_environmental_reports(cls) -> "PrecedenceModel":
        """Initialize with common EIA report type sequences."""
        model = cls(smoothing=0.01)
        # Standard EIA procedural chain
        eia_chain = [
            ["background", "site_survey", "pollution_source",
             "monitoring_data", "standard_comparison",
             "impact_prediction", "mitigation", "conclusion"],
            ["background", "regulation_review", "scope_definition",
             "data_collection", "analysis", "recommendation"],
            ["executive_summary", "introduction", "methodology",
             "findings", "discussion", "conclusion"],
        ]
        for chain in eia_chain:
            for _ in range(5):  # Boost with repetition for stronger priors
                model.observe_sequence(chain)
        return model

    @classmethod
    def for_code_generation(cls) -> "PrecedenceModel":
        """Initialize with code generation type sequences."""
        model = cls(smoothing=0.01)
        chains = [
            ["requirement", "design", "implementation", "test", "review"],
            ["analysis", "architecture", "coding", "debugging", "optimization"],
            ["spec", "scaffold", "core_logic", "edge_cases", "documentation"],
        ]
        for chain in chains:
            for _ in range(5):
                model.observe_sequence(chain)
        return model

    @classmethod
    def for_document_generation(cls) -> "PrecedenceModel":
        """Initialize with document generation type sequences."""
        model = cls(smoothing=0.01)
        chains = [
            ["outline", "introduction", "body", "conclusion", "appendix"],
            ["research", "draft", "review", "revise", "finalize"],
            ["data_gathering", "analysis", "visualization", "narrative", "formatting"],
        ]
        for chain in chains:
            for _ in range(5):
                model.observe_sequence(chain)
        return model


# ═══ Singleton ═══

_precedence_model: PrecedenceModel | None = None


def get_precedence_model() -> PrecedenceModel:
    global _precedence_model
    if _precedence_model is None:
        _precedence_model = PrecedenceModel()
    return _precedence_model


def initialize_for_domain(domain: str = "general") -> PrecedenceModel:
    """Initialize a domain-specific precedence model."""
    global _precedence_model
    if domain in ("environmental", "eia", "环评"):
        _precedence_model = PrecedenceModel.for_environmental_reports()
    elif domain in ("code", "编程", "开发"):
        _precedence_model = PrecedenceModel.for_code_generation()
    elif domain in ("document", "文档", "报告"):
        _precedence_model = PrecedenceModel.for_document_generation()
    else:
        _precedence_model = PrecedenceModel()
    return _precedence_model


__all__ = [
    "PrecedenceModel", "Transition", "PrecedenceResult",
    "get_precedence_model", "initialize_for_domain",
]
