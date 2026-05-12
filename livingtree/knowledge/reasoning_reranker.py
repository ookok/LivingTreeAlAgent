"""Reasoning-Aware Memory Reranker — "think before you rank".

MemReranker (Li et al., arXiv:2605.06132, 2026) concept implementation.
Addresses three core retrieval problems without running a 0.6B model:

1. Miscalibrated relevance scores → Platt scaling (online logistic calibration)
2. Degradation on complex queries → reasoning step extracts temporal/causal constraints
3. No dialogue context → inject conversation history for coreference resolution

Architecture:
  Query → ReasoningStep (LLM or heuristic) → per-doc multi-signal scoring
  → Platt calibration → sorted CalibratedScore list

Integration:
  from .reasoning_reranker import get_reasoning_reranker
  rr = get_reasoning_reranker(consciousness=cons)
  scored = await rr.rerank_with_reasoning(candidates, query, dialogue_context)
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ═══ Dataclasses ═══════════════════════════════════════════════════════════════

@dataclass
class ReasoningStep:
    """LLM-generated (or heuristic) reasoning about what information is needed."""
    query: str
    reasoning: str = ""
    temporal_constraints: list[str] = field(default_factory=list)
    causal_constraints: list[str] = field(default_factory=list)
    key_entities: list[str] = field(default_factory=list)
    expected_doc_type: str = "general"

    def is_empty(self) -> bool:
        return not self.temporal_constraints and not self.causal_constraints and not self.reasoning

    def summary(self) -> str:
        parts: list[str] = []
        if self.temporal_constraints:
            parts.append(f"temporal={self.temporal_constraints}")
        if self.causal_constraints:
            parts.append(f"causal={self.causal_constraints}")
        if self.key_entities:
            parts.append(f"entities={self.key_entities}")
        return f"ReasoningStep(doc_type={self.expected_doc_type}, {', '.join(parts)})" if parts else f"ReasoningStep(doc_type={self.expected_doc_type})"


@dataclass
class CalibratedScore:
    """Per-document reasoning-aware calibrated score."""
    doc_id: str
    raw_score: float = 0.0
    reasoning_boost: float = 0.0
    temporal_match: float = 0.0
    causal_match: float = 0.0
    context_match: float = 0.0
    calibrated_score: float = 0.0
    confidence: float = 0.0


# ═══ Regex patterns for heuristic reasoning ════════════════════════════════════

_TEMPORAL_RE = re.compile(
    r"(上次|后来|之前|之后|最近|当时|今天|昨天|明天|刚才|刚刚|以前|以后|过去"
    r"|未来|现在|当前|上次|下次|上周|本周|下周|去年|今年|明年"
    r"|before|after|recently|previously|later|earlier|last\s+\w+)",
    re.IGNORECASE,
)

_CAUSAL_RE = re.compile(
    r"(因为|所以|导致|原因|放弃|改为|改成|由于|因此|从而|引起|造成|影响"
    r"|because|cause|due to|therefore|thus|hence|result in|lead to"
    r"|consequently|accordingly|as a result)",
    re.IGNORECASE,
)

_ENTITY_RE = re.compile(
    r"[\u4e00-\u9fff]{2,}(?:系统|平台|服务|模块|方案|项目|产品|功能|接口|数据库"
    r"|模型|算法|框架|工具|组件|引擎|协议|标准|规范|流程|策略|模式)\b|"
    r'"[^"]+"|\'[^\']+\'|《[^》]+》|[A-Z][a-z]+(?:\s[A-Z][a-z]+)+',
)

_ENTITY_SIMPLE_RE = re.compile(
    r"[A-Za-z]+(?:[_\-.][A-Za-z0-9]+)+|"        # snake_case, kebab-case, dot.notation
    r"[A-Z][a-z]+(?:[A-Z][a-z]+)+",              # CamelCase
)

_INDICATOR_WORDS_RE = re.compile(r"什么|哪|怎么|如何|为何|why|what|how|which|when|who|where", re.IGNORECASE)

_DEFINITION_TERMS = {
    "定义", "是指", "是指", "概念", "什么是", "什么是", "含义", "意思",
    "definition", "concept", "meaning", "what is",
}
_THRESHOLD_TERMS = {
    "限值", "阈值", "标准值", "要求", "规范", "规定",
    "threshold", "limit", "standard", "requirement", "specification",
}
_PROCEDURE_TERMS = {
    "步骤", "流程", "方法", "怎么做", "如何", "操作",
    "procedure", "method", "how to", "steps", "protocol",
}
_CONCLUSION_TERMS = {
    "总结", "结论", "结果", "建议", "评估",
    "conclusion", "summary", "result", "recommendation", "evaluation",
}

# Keywords used for reasoning keyword matching
_REASONING_KEYWORDS = {
    "temporal", "causal", "constraint", "definition", "threshold", "procedure",
    "conclusion", "requirement", "mitigation", "analysis", "observation",
    "standard", "regulation", "measurement", "finding",
}


# ═══ ReasoningReranker ════════════════════════════════════════════════════════

class ReasoningReranker:
    """Reasoning-aware memory reranker implementing MemReranker concept.

    Core idea: "think before you rank" — extract temporal/causal/entity
    constraints from the query before scoring, then Platt-calibrate scores
    using historical relevance feedback.

    Features:
      - ReasoningStep generation (LLM or heuristic)
      - Multi-signal per-document scoring (temporal, causal, context, reasoning)
      - Platt scaling calibration from online feedback
      - Dialogue context injection for coreference resolution
    """

    _PLATT_LEARNING_RATE: float = 0.01
    _PLATT_ITERATIONS: int = 100
    _CALIBRATION_BATCH: int = 20
    _DEFAULT_PLATT_A: float = 1.0
    _DEFAULT_PLATT_B: float = 0.0

    def __init__(self, consciousness: Any = None):
        self._consciousness = consciousness
        self._calibration_history: list[tuple[float, float]] = []  # (score, was_relevant)
        self._platt_a: float = self._DEFAULT_PLATT_A
        self._platt_b: float = self._DEFAULT_PLATT_B

        # Stats
        self._total_reranks: int = 0
        self._total_calibrated_sum: float = 0.0
        self._total_temporal_boost: float = 0.0
        self._total_causal_boost: float = 0.0
        self._total_reasoning_steps: int = 0

    # ── Reasoning Step Generation ─────────────────────────────────────────

    async def generate_reasoning(
        self, query: str, dialogue_context: str | None = None,
    ) -> ReasoningStep:
        """Generate a reasoning step from query and optional dialogue context.

        Uses LLM consciousness if available; falls back to regex heuristics.
        """
        if self._consciousness is not None:
            try:
                return await self._llm_reasoning(query, dialogue_context)
            except Exception as exc:
                logger.debug(f"LLM reasoning fallback: {exc}")
        return self._heuristic_reasoning(query, dialogue_context)

    async def _llm_reasoning(
        self, query: str, dialogue_context: str | None,
    ) -> ReasoningStep:
        """Use consciousness LLM to extract reasoning constraints."""
        ctx = dialogue_context or "(none)"
        prompt = (
            "You are a retrieval planning assistant. Given a user query and dialogue context, "
            "analyze what specific information is needed to answer it.\n\n"
            f"Query: {query}\n"
            f"Dialogue context: {ctx}\n\n"
            "Output a JSON object with these fields:\n"
            '  "reasoning": a short sentence describing what information would answer this query\n'
            '  "temporal_constraints": list of time-related constraints (e.g. "after last week", "before the change")\n'
            '  "causal_constraints": list of cause-effect relationships relevant to the query\n'
            '  "key_entities": list of named entities or key terms that need disambiguation\n'
            '  "expected_doc_type": one of definition/threshold/procedure/conclusion/general\n\n'
            "Output ONLY the JSON object, no other text."
        )

        raw = await self._consciousness.query(prompt, max_tokens=500, temperature=0.1)
        parsed = self._parse_json_response(raw)
        if not parsed:
            return self._heuristic_reasoning(query, dialogue_context)

        step = ReasoningStep(
            query=query,
            reasoning=parsed.get("reasoning", ""),
            temporal_constraints=parsed.get("temporal_constraints", []),
            causal_constraints=parsed.get("causal_constraints", []),
            key_entities=parsed.get("key_entities", []),
            expected_doc_type=parsed.get("expected_doc_type", "general"),
        )
        self._total_reasoning_steps += 1
        logger.debug(step.summary())
        return step

    def _heuristic_reasoning(
        self, query: str, dialogue_context: str | None = None,
    ) -> ReasoningStep:
        """Regex-based heuristic reasoning extraction (no LLM required)."""
        query_lower = query.lower()

        temporal = _TEMPORAL_RE.findall(query)
        temporal_constraints: list[str] = []
        seen_t: set[str] = set()
        for t in temporal:
            if t not in seen_t:
                temporal_constraints.append(t)
                seen_t.add(t)

        causal = _CAUSAL_RE.findall(query)
        causal_constraints: list[str] = []
        seen_c: set[str] = set()
        for c in causal:
            if c not in seen_c:
                causal_constraints.append(c)
                seen_c.add(c)

        entities: list[str] = []
        for match in _ENTITY_RE.finditer(query):
            e = match.group().strip()
            if e and e not in entities and len(e) >= 2:
                entities.append(e)
        for match in _ENTITY_SIMPLE_RE.finditer(query):
            e = match.group().strip()
            if e and e not in entities and len(e) >= 2:
                entities.append(e)

        doc_type = self._infer_expected_doc_type(query_lower)

        reasoning_parts: list[str] = []
        if temporal_constraints:
            reasoning_parts.append(f"temporal constraints: {', '.join(temporal_constraints)}")
        if causal_constraints:
            reasoning_parts.append(f"causal constraints: {', '.join(causal_constraints)}")
        if entities:
            reasoning_parts.append(f"key entities: {', '.join(entities)}")
        if not reasoning_parts:
            reasoning_parts.append(f"direct query: {query}")

        reasoning = "; ".join(reasoning_parts)

        if dialogue_context:
            ctx_entities = self._extract_entities_from_text(dialogue_context)
            extra = [e for e in ctx_entities if e not in entities]
            entities.extend(extra[:5])

        self._total_reasoning_steps += 1
        step = ReasoningStep(
            query=query,
            reasoning=reasoning,
            temporal_constraints=temporal_constraints,
            causal_constraints=causal_constraints,
            key_entities=entities,
            expected_doc_type=doc_type,
        )
        logger.debug(step.summary())
        return step

    def _infer_expected_doc_type(self, query_lower: str) -> str:
        """Infer what type of document would best answer this query."""
        if any(t in query_lower for t in _DEFINITION_TERMS):
            return "definition"
        if any(t in query_lower for t in _THRESHOLD_TERMS):
            return "threshold"
        if any(t in query_lower for t in _PROCEDURE_TERMS):
            return "procedure"
        if any(t in query_lower for t in _CONCLUSION_TERMS):
            return "conclusion"
        return "general"

    def _extract_entities_from_text(self, text: str) -> list[str]:
        entities: list[str] = []
        for match in _ENTITY_RE.finditer(text):
            e = match.group().strip()
            if e and e not in entities and len(e) >= 2:
                entities.append(e)
        for match in _ENTITY_SIMPLE_RE.finditer(text):
            e = match.group().strip()
            if e and e not in entities and len(e) >= 2:
                entities.append(e)
        return entities

    # ── Reranking ──────────────────────────────────────────────────────────

    def rerank(
        self,
        candidates: list[dict],
        reasoning_step: ReasoningStep,
        dialogue_context: str | None = None,
        top_k: int = 5,
    ) -> list[CalibratedScore]:
        """Rerank candidates using the reasoning step and dialogue context.

        Multi-signal scoring:
          - temporal_match: constraint keyword overlap with doc text
          - causal_match: causal keyword overlap with doc text
          - reasoning_boost: Jaccard similarity between reasoning keywords and doc
          - context_match: entity overlap between dialogue context and doc

        Weights: raw=0.30, reasoning_boost=0.25, temporal=0.20, causal=0.15, context=0.10
        """
        if not candidates:
            return []

        t0 = time.time()
        all_calibrated: list[CalibratedScore] = []

        ctx_entities: set[str] = set()
        if dialogue_context:
            for e in self._extract_entities_from_text(dialogue_context):
                ctx_entities.add(e.lower())

        reasoning_text = reasoning_step.reasoning.lower()
        reasoning_keywords: set[str] = set()
        if reasoning_text:
            for kw in _REASONING_KEYWORDS:
                if kw in reasoning_text:
                    reasoning_keywords.add(kw)
        if not reasoning_keywords:
            reasoning_keywords = set(reasoning_text.split())

        for i, cand in enumerate(candidates):
            doc_id = cand.get("id", cand.get("doc_id", f"doc_{i}"))
            text = cand.get("text", cand.get("content", str(cand)))
            text_lower = text.lower() if isinstance(text, str) else ""
            original_score = float(cand.get("score", cand.get("final_score", 0.5)))

            temporal_match = self._compute_keyword_match(
                text_lower, reasoning_step.temporal_constraints,
            )
            causal_match = self._compute_keyword_match(
                text_lower, reasoning_step.causal_constraints,
            )
            reasoning_boost = self._compute_jaccard(reasoning_keywords, text_lower)
            context_match = self._compute_jaccard(ctx_entities, text_lower) if ctx_entities else 0.0

            raw = (
                original_score * 0.30
                + reasoning_boost * 0.25
                + temporal_match * 0.20
                + causal_match * 0.15
                + context_match * 0.10
            )

            calibrated = self._platt(raw)
            confidence = self._compute_confidence(
                temporal_match, causal_match, context_match, reasoning_boost,
            )

            all_calibrated.append(CalibratedScore(
                doc_id=doc_id,
                raw_score=round(original_score, 4),
                reasoning_boost=round(reasoning_boost, 4),
                temporal_match=round(temporal_match, 4),
                causal_match=round(causal_match, 4),
                context_match=round(context_match, 4),
                calibrated_score=round(calibrated, 4),
                confidence=round(confidence, 4),
            ))

        all_calibrated.sort(key=lambda x: x.calibrated_score, reverse=True)
        top = all_calibrated[:top_k]

        self._total_reranks += 1
        if all_calibrated:
            self._total_calibrated_sum += all_calibrated[0].calibrated_score
            self._total_temporal_boost += all_calibrated[0].temporal_match
            self._total_causal_boost += all_calibrated[0].causal_match

        elapsed = (time.time() - t0) * 1000
        logger.debug(
            f"ReasoningReranker: {len(candidates)} → {len(top)} docs "
            f"(top_score={top[0].calibrated_score if top else 0:.3f}, "
            f"{elapsed:.0f}ms)",
        )
        return top

    async def rerank_with_reasoning(
        self,
        candidates: list[dict],
        query: str,
        dialogue_context: str | None = None,
        top_k: int = 5,
    ) -> list[CalibratedScore]:
        """Main entry point: generate reasoning, then rerank.

        Convenience method that chains generate_reasoning() → rerank().
        """
        step = await self.generate_reasoning(query, dialogue_context)
        return self.rerank(candidates, step, dialogue_context, top_k)

    # ── Multi-signal scoring helpers ──────────────────────────────────────

    @staticmethod
    def _compute_keyword_match(text_lower: str, constraints: list[str]) -> float:
        """Fraction of constraint strings found in the document text."""
        if not constraints:
            return 0.0
        hits = sum(1 for c in constraints if c.lower() in text_lower)
        return hits / len(constraints)

    @staticmethod
    def _compute_jaccard(keywords: set[str], text_lower: str) -> float:
        """Jaccard similarity between keyword set and document word set."""
        if not keywords:
            return 0.0
        doc_words = set(text_lower.split())
        if not doc_words:
            return 0.0
        intersection = keywords & doc_words
        union = keywords | doc_words
        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def _compute_confidence(
        temporal: float, causal: float, context: float, reasoning: float,
    ) -> float:
        """Confidence estimate based on signal strength distribution."""
        signals = [temporal, causal, context, reasoning]
        non_zero = [s for s in signals if s > 0]
        if not non_zero:
            return 0.3
        avg = sum(non_zero) / len(non_zero)
        coverage = len(non_zero) / len(signals)
        return min(1.0, avg * 0.6 + coverage * 0.4)

    # ── Platt Scaling Calibration ─────────────────────────────────────────

    def _platt(self, raw_score: float) -> float:
        """Apply Platt scaling: calibrated = 1 / (1 + exp(-(a*x + b)))."""
        try:
            return 1.0 / (1.0 + math.exp(-(self._platt_a * raw_score + self._platt_b)))
        except OverflowError:
            return 1.0 if raw_score > 0 else 0.0

    def calibrate(self, score: float, was_relevant: bool) -> None:
        """Record a calibration sample and periodically refit Platt parameters.

        Args:
            score: The raw (pre-scaling) relevance score that was used.
            was_relevant: True if the user/process confirmed this result was relevant.
        """
        label = 1.0 if was_relevant else 0.0
        self._calibration_history.append((score, label))
        logger.debug(
            f"Calibration sample {len(self._calibration_history)}: "
            f"score={score:.3f} relevant={was_relevant}",
        )

        if len(self._calibration_history) % self._CALIBRATION_BATCH == 0:
            self._refit_platt()

    def _refit_platt(self) -> None:
        """Refit Platt parameters via simple gradient descent on cross-entropy.

        Minimizes: -[y*log(p) + (1-y)*log(1-p)] where p = sigmoid(a*x + b).
        """
        if len(self._calibration_history) < 2:
            return

        a = self._DEFAULT_PLATT_A
        b = self._DEFAULT_PLATT_B
        lr = self._PLATT_LEARNING_RATE
        n = len(self._calibration_history)

        for _ in range(self._PLATT_ITERATIONS):
            grad_a = 0.0
            grad_b = 0.0
            for score, label in self._calibration_history:
                z = a * score + b
                try:
                    p = 1.0 / (1.0 + math.exp(-z))
                except OverflowError:
                    p = 1.0 if z > 0 else 0.0
                p = max(1e-15, min(1.0 - 1e-15, p))
                error = p - label
                grad_a += error * score
                grad_b += error
            a -= lr * grad_a / n
            b -= lr * grad_b / n

        self._platt_a = a
        self._platt_b = b
        logger.info(
            f"Platt refitted: a={a:.4f}, b={b:.4f} "
            f"(n={n}, n_pos={sum(1 for _, l in self._calibration_history if l > 0.5)})",
        )

    def get_calibration_stats(self) -> dict[str, Any]:
        """Return calibration statistics."""
        n = len(self._calibration_history)
        error = 0.0
        if n > 0:
            errors = []
            for score, label in self._calibration_history:
                cal = self._platt(score)
                errors.append(abs(cal - label))
            error = sum(errors) / n
        n_pos = sum(1 for _, l in self._calibration_history if l > 0.5) if n else 0
        return {
            "n_samples": n,
            "n_positive": n_pos,
            "platt_a": round(self._platt_a, 4),
            "platt_b": round(self._platt_b, 4),
            "calibration_error": round(error, 4),
        }

    # ── Dialogue Context Injection ────────────────────────────────────────

    def inject_dialogue_context(
        self, query: str, dialogue_history: list[str] | None,
    ) -> str:
        """Resolve coreferences in query using conversation history.

        Example:
            query = "上次说的那个方案后来为什么放弃了"
            history = ["我们讨论了高并发消息队列方案", "评估了Kafka和RabbitMQ"]
            → resolves "那个方案" to "高并发消息队列方案"

        Simple implementation: scan history for entities, substitute pronoun references.
        """
        if not dialogue_history:
            return query

        # Collect all candidate entities from history
        hist_entities: list[str] = []
        for msg in dialogue_history[-5:]:
            hist_entities.extend(self._extract_entities_from_text(msg))
        if not hist_entities:
            return query

        resolved = query

        # Resolve generic pronoun references
        pronoun_map = [
            (r"(那个|这个)(方案|项目|功能|模块|系统|服务|平台|产品|接口|组件|配置)",
             lambda m, idx: hist_entities[0] if hist_entities else m.group(0)),
            (r"(上次|之前)(说的|提到的|讨论的)(那个|这个)?(方案|项目|功能|模块|系统|服务|平台|产品|接口|组件|配置)",
             lambda m, idx: hist_entities[0] if hist_entities else m.group(0)),
            (r"它(们)?",
             lambda m, idx: hist_entities[0] if hist_entities else m.group(0)),
        ]

        for pattern, replacer in pronoun_map:
            match = re.search(pattern, resolved)
            if match:
                candidate = replacer(match, hist_entities.index(hist_entities[0]) if hist_entities else 0)
                resolved = resolved[:match.start()] + candidate + resolved[match.end():]
                break

        logger.debug(f"Coreference: '{query}' → '{resolved}'")
        return resolved

    # ── Query Wrapping for Retrieval ─────────────────────────────────────

    async def wrap_retrieval(
        self, query: str, dialogue_context: list[str] | None = None,
    ) -> tuple[str, ReasoningStep]:
        """Prepare query for retrieval by resolving coreferences and generating reasoning.

        Returns (enriched_query, reasoning_step) for downstream retrieval.
        """
        dialogue_str = " | ".join(dialogue_context) if dialogue_context else None
        resolved = self.inject_dialogue_context(query, dialogue_context)
        step = await self.generate_reasoning(resolved, dialogue_str)

        # Expand query with reasoning hints
        hints: list[str] = []
        if step.temporal_constraints:
            hints.append("temporal:" + ",".join(step.temporal_constraints[:3]))
        if step.causal_constraints:
            hints.append("causal:" + ",".join(step.causal_constraints[:3]))
        if step.key_entities:
            hints.append("entities:" + ",".join(step.key_entities[:5]))

        enriched = resolved
        if hints:
            enriched = f"{resolved} [{' | '.join(hints)}]"

        logger.debug(f"Wrap retrieval: '{query}' → '{enriched}'")
        return enriched, step

    # ── Stats ─────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return runtime statistics."""
        avg_cal = 0.0
        if self._total_reranks > 0:
            avg_cal = self._total_calibrated_sum / self._total_reranks
        avg_temporal = 0.0
        if self._total_reranks > 0:
            avg_temporal = self._total_temporal_boost / self._total_reranks
        avg_causal = 0.0
        if self._total_reranks > 0:
            avg_causal = self._total_causal_boost / self._total_reranks

        return {
            "total_reranks": self._total_reranks,
            "avg_calibrated_score": round(avg_cal, 4),
            "calibration_samples": len(self._calibration_history),
            "avg_temporal_boost": round(avg_temporal, 4),
            "avg_causal_boost": round(avg_causal, 4),
            "total_reasoning_steps": self._total_reasoning_steps,
        }

    @property
    def platt_a(self) -> float:
        return self._platt_a

    @property
    def platt_b(self) -> float:
        return self._platt_b


# ═══ Helpers ═══════════════════════════════════════════════════════════════════

def _parse_json_response(raw: str) -> dict | None:
    """Extract and parse a JSON object from LLM output."""
    try:
        s = raw.index("{")
        e = raw.rindex("}") + 1
        return json.loads(raw[s:e])
    except (ValueError, json.JSONDecodeError):
        return None


# ═══ Singleton ═════════════════════════════════════════════════════════════════

_instance: ReasoningReranker | None = None


def get_reasoning_reranker(consciousness: Any = None) -> ReasoningReranker:
    """Get or create the singleton ReasoningReranker instance.

    Args:
        consciousness: Optional LLM consciousness for reasoning step generation.
                       If provided and instance exists with no consciousness,
                       updates the instance.
    """
    global _instance
    if _instance is None:
        _instance = ReasoningReranker(consciousness=consciousness)
    elif consciousness is not None and _instance._consciousness is None:
        _instance._consciousness = consciousness
    return _instance


def reset_reasoning_reranker() -> None:
    """Reset the singleton instance."""
    global _instance
    _instance = None


__all__ = [
    "ReasoningReranker",
    "ReasoningStep",
    "CalibratedScore",
    "get_reasoning_reranker",
    "reset_reasoning_reranker",
]
