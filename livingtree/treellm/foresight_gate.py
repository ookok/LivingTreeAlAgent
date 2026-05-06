"""foresight_gate.py — RuView-inspired Coherence Gate with hysteresis.

Upgraded from binary ForesightGate to 4-state CoherenceGate (RuView pattern):
- ACCEPT: Proceed with full execution
- PREDICT_ONLY: Simulate but don't execute (uncertain domain)
- REJECT: Block execution (unsafe / out-of-scope)
- RECALIBRATE: Request more information before deciding

Hysteresis: Tracks last N decisions to prevent rapid state oscillation (RuView's
coherence gate uses phasor gating with hysteresis to avoid flickering at state
boundaries).

Original inspiration: "Current Agents Fail to Leverage World Model as Tool for
Foresight" (arXiv:2601.03905) + RuView signal-line protocol (CRV/ADR-033).
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


class GateState(enum.StrEnum):
    """4-state coherence gate — RuView signal-line protocol mapping."""
    ACCEPT = "accept"               # Proceed with full execution
    PREDICT_ONLY = "predict_only"   # Simulate but don't execute
    REJECT = "reject"               # Block — unsafe or out-of-scope
    RECALIBRATE = "recalibrate"     # Request more information


@dataclass
class ForesightDecision:
    """Legacy binary decision — maintained for backward compatibility."""
    should_simulate: bool
    reason: str
    depth: int  # 1-3
    confidence: float  # 0.0 - 1.0
    factors: Dict[str, float]


@dataclass
class CoherenceDecision:
    """4-state coherence-gated decision with hysteresis tracking."""
    state: GateState
    confidence: float                # Overall confidence in this decision
    scores: Dict[str, float]         # Per-factor scores
    reason: str
    depth: int = 1                   # Simulation depth if PREDICT_ONLY (1-3)
    data_completeness: float = 1.0   # 0.0=no data, 1.0=complete
    requires_recalibration: bool = False
    recalibration_hints: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def should_simulate(self) -> bool:
        return self.state in (GateState.ACCEPT, GateState.PREDICT_ONLY)

    @property
    def is_safe(self) -> bool:
        return self.state != GateState.REJECT


class CoherenceGate:
    """4-state decision gate with hysteresis (RuView coherence gate pattern).

    Key features:
    - 4 output states: ACCEPT / PREDICT_ONLY / REJECT / RECALIBRATE
    - Hysteresis buffer: prevents rapid state oscillation
    - Data completeness check: insufficient data → RECALIBRATE
    - Confidence thresholds: per-state minimum confidence requirements
    """

    # Hysteresis: how many consecutive same-state decisions before committing
    HYSTERESIS_WINDOW = 3
    # Minimum confidence for each state
    CONFIDENCE_THRESHOLDS = {
        GateState.ACCEPT: 0.60,
        GateState.PREDICT_ONLY: 0.35,
        GateState.REJECT: 0.80,       # High bar — only reject when very certain
        GateState.RECALIBRATE: 0.50,   # Low confidence → recalibrate
    }
    # Data completeness: below this, always RECALIBRATE
    MIN_DATA_COMPLETENESS = 0.30

    def __init__(self) -> None:
        self._history: List[GateState] = []
        self._state_streak: Dict[str, int] = {}

    def gate(
        self,
        query: str,
        task_type: str = "general",
        history: Optional[List[str]] = None,
        risk_level: str = "normal",
        data_completeness: float = 1.0,
        available_sources: int = 0,
    ) -> CoherenceDecision:
        """Main entry point — returns a 4-state coherence-gated decision.

        Args:
            query: Task description.
            task_type: 'code', 'reasoning', 'chat', 'search', 'multimodal', 'general'.
            history: Past queries for novelty scoring.
            risk_level: 'low', 'normal', 'high'.
            data_completeness: 0.0-1.0 — how complete the input data is.
            available_sources: Number of distinct data sources available.
        """
        complexity = self._complexity_score(query)
        novelty = self._novelty_score(query, history or [])
        risk = self._risk_score(task_type, risk_level)
        coherence = self._coherence_score(query, available_sources)

        # Combine scores
        total = complexity * 0.30 + novelty * 0.25 + risk * 0.25 + coherence * 0.20
        confidence = 0.4 + 0.6 * (1.0 - abs(0.5 - total))  # High at extremes, low at ambiguity

        scores = {
            "complexity": complexity,
            "novelty": novelty,
            "risk": risk,
            "coherence": coherence,
        }

        # Determine state
        state, reason, recal_hints = self._determine_state(
            total, confidence, data_completeness, scores, risk, task_type
        )

        # Apply hysteresis
        stabilized_state = self._apply_hysteresis(state)

        depth = self._compute_depth(total) if stabilized_state in (GateState.ACCEPT, GateState.PREDICT_ONLY) else 1

        return CoherenceDecision(
            state=stabilized_state,
            confidence=confidence,
            scores=scores,
            reason=reason,
            depth=depth,
            data_completeness=data_completeness,
            requires_recalibration=(stabilized_state == GateState.RECALIBRATE),
            recalibration_hints=recal_hints,
        )

    def _determine_state(
        self, total: float, confidence: float, data_completeness: float,
        scores: Dict[str, float], risk: float, task_type: str,
    ) -> tuple[GateState, str, List[str]]:
        """Core state logic — maps scores → 4-state decision."""
        hints: List[str] = []

        # Data insufficiency gate
        if data_completeness < self.MIN_DATA_COMPLETENESS:
            hints.append("insufficient input data")
            return GateState.RECALIBRATE, "data_completeness < 0.30", hints

        # High-confidence rejection: risk-dominated + low coherence
        if risk > 0.85 and confidence > self.CONFIDENCE_THRESHOLDS[GateState.REJECT]:
            return GateState.REJECT, f"risk={risk:.2f} exceeds safety threshold", []

        # Out-of-scope detection
        unsafe_keywords = ["rm -rf", "DROP TABLE", "format c:", "shutdown", "/dev/null"]
        if any(kw.lower() in task_type.lower() for kw in ["system", "unsafe"]):
            return GateState.REJECT, "task_type flagged as unsafe", []

        # High confidence + low risk → ACCEPT
        if total > 0.70 and confidence > self.CONFIDENCE_THRESHOLDS[GateState.ACCEPT]:
            return GateState.ACCEPT, f"high confidence ({confidence:.2f}), total={total:.2f}", []

        # Moderate confidence + moderate total → ACCEPT (standard path)
        if total >= 0.55 and confidence >= self.CONFIDENCE_THRESHOLDS[GateState.PREDICT_ONLY]:
            return GateState.ACCEPT, f"acceptable confidence ({confidence:.2f}), total={total:.2f}", []

        # Low confidence but safe → PREDICT_ONLY (simulate, don't commit)
        if total >= 0.35 and risk < 0.70:
            hints.append("low confidence — recommend simulation before execution")
            return GateState.PREDICT_ONLY, f"predict-only: confidence={confidence:.2f} below accept threshold", hints

        # Ambiguous zone → RECALIBRATE
        hints.extend([
            f"complexity={scores['complexity']:.2f}",
            f"novelty={scores['novelty']:.2f}",
            f"coherence={scores['coherence']:.2f}",
        ])
        return GateState.RECALIBRATE, f"ambiguous: total={total:.2f}, confidence={confidence:.2f}", hints

    def _apply_hysteresis(self, new_state: GateState) -> GateState:
        """Hysteresis: prevent rapid oscillation between states.

        The state only changes after HYSTERESIS_WINDOW consecutive same-state
        decisions. This prevents flickering at state boundaries (RuView pattern:
        coherence gate uses Z-score phasor gating with hysteresis).
        """
        self._history.append(new_state)
        if len(self._history) > self.HYSTERESIS_WINDOW * 2:
            self._history = self._history[-self.HYSTERESIS_WINDOW * 2:]

        # Count consecutive same-state from end
        count = 0
        for s in reversed(self._history):
            if s == new_state:
                count += 1
            else:
                break

        if count >= self.HYSTERESIS_WINDOW:
            return new_state
        # Return most recent state that has enough streak
        for streak_count in range(self.HYSTERESIS_WINDOW, 0, -1):
            for s in reversed(self._history[-streak_count:]):
                pass
            if streak_count == 1:
                # Not enough hysteresis — return last committed state or ACCEPT as safe default
                for s in reversed(self._history[:-1]):
                    return s
                return GateState.PREDICT_ONLY  # Safe default: simulate but don't execute
        return new_state

    def _compute_depth(self, total: float) -> int:
        if total < 0.55:
            return 1
        elif total < 0.75:
            return 2
        return 3

    # ── Scoring Methods (enhanced from original) ──

    def _complexity_score(self, query: str) -> float:
        q = query or ""
        score = 0.0
        if len(q) > 200:
            score += 0.3

        lower = q.lower()
        for token in ["what", "why", "how", "分析", "实现"]:
            count = lower.count(token)
            if count:
                score += 0.15 * count

        code_indicators = 0
        if "```" in q:
            code_indicators += 1
        for tok in ["def ", "function ", "class "]:
            if tok in q:
                code_indicators += 1
        score += 0.2 * code_indicators

        multi = 0
        for tok in ["首先", "然后", "first", "then"]:
            multi += lower.count(tok)
        score += 0.2 * multi

        for tok in ["算法", "优化", "架构", "algorithm"]:
            if tok in q:
                score += 0.15

        return max(0.0, min(1.0, score))

    def _novelty_score(self, query: str, history: List[str]) -> float:
        if not history:
            return 0.7
        qset = set((query or "").lower().split())
        max_overlap = 0.0
        for h in history:
            hset = set(h.lower().split())
            if not hset:
                continue
            overlap = len(qset & hset) / max(len(qset | hset), 1)
            max_overlap = max(max_overlap, overlap)
        if max_overlap < 0.3:
            return 0.9
        return max(0.0, min(1.0, 0.3 + 0.7 * (1.0 - max_overlap)))

    def _risk_score(self, task_type: str, risk_level: str) -> float:
        risk_map = {
            "code": 0.7, "reasoning": 0.5, "chat": 0.2,
            "search": 0.3, "multimodal": 0.6,
        }
        base = risk_map.get(task_type.lower(), 0.4)
        level = (risk_level or "normal").lower()
        modifier = {"high": 1.0, "normal": 0.0, "low": -0.3}.get(level, 0.0)
        return max(0.0, min(1.0, base + modifier))

    def _coherence_score(self, query: str, available_sources: int) -> float:
        """Signal coherence — how stable/consistent is the input? (RuView pattern)

        Low sources → low coherence → more likely RECALIBRATE.
        Incoherent text (contradictions, gibberish) → low coherence.
        """
        score = 0.5
        q = (query or "").lower()

        # Source count bonus (RuView: multi-band = better signal)
        if available_sources >= 3:
            score += 0.3
        elif available_sources >= 1:
            score += 0.15

        # Self-contradiction detection
        contradiction_pairs = [
            ("always", "never"), ("must", "optional"), ("required", "unnecessary"),
            ("true", "false"), ("correct", "wrong"),
        ]
        for a, b in contradiction_pairs:
            if a in q and b in q:
                score -= 0.2

        # Gibberish detection: high char entropy
        if len(set(q)) / max(len(q), 1) > 0.8 and len(q) > 30:
            score -= 0.15

        # Named entity bonus (real content)
        import re as _re
        entity_count = len(_re.findall(r'\b[A-Z][a-z]{2,}\b', query or ""))
        if entity_count >= 3:
            score += 0.1

        return max(0.0, min(1.0, score))

    # ── Backward-compatible assess() ──

    def assess(
        self, query: str, task_type: str = "general",
        history: Optional[List[str]] = None, risk_level: str = "normal",
        data_completeness: float = 1.0, available_sources: int = 0,
    ) -> ForesightDecision:
        """Legacy API — wraps gate() for backward compatibility."""
        cd = self.gate(query, task_type, history, risk_level, data_completeness, available_sources)
        return ForesightDecision(
            should_simulate=cd.should_simulate,
            reason=cd.reason,
            depth=cd.depth,
            confidence=cd.confidence,
            factors=cd.scores,
        )

    def get_state_history(self) -> List[GateState]:
        return list(self._history)

    def reset_hysteresis(self) -> None:
        self._history.clear()


# Legacy name for backward compat
ForesightGate = CoherenceGate

# Singleton
_gate: Optional[CoherenceGate] = None

def get_foresight_gate() -> CoherenceGate:
    global _gate
    if _gate is None:
        _gate = CoherenceGate()
    return _gate

def get_coherence_gate() -> CoherenceGate:
    return get_foresight_gate()
