"""LayerGovernance — consistency contracts, fallback chains, boundary calibration, version coordination.

Addresses the 4 gaps in layered inference architecture:

1. Layer Consistency: All layers share unified classification labels and output format contracts.
2. Fallback Chain: Explicit escalation rules (local→fast→reasoning) with configurable thresholds.
3. Boundary Calibration: Complexity thresholds that adapt from success/failure rates.
4. Version Coordination: Prompt version tracking with automatic rollback on degradation.
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

from loguru import logger


class LayerLevel(StrEnum):
    LOCAL = "local"
    FAST = "fast"
    REASONING = "reasoning"


class Decision(StrEnum):
    ACCEPT = "accept"        # current layer handles it, no escalation
    ESCALATE = "escalate"    # pass to next layer up
    FALLBACK = "fallback"    # current layer failed, use higher layer
    RETRY = "retry"          # try same layer again (transient error)


@dataclass
class LayerContract:
    """Consistency contract: all layers must align on these."""
    classification_labels: list[str] = field(default_factory=lambda: [
        "chat", "code", "reasoning", "search", "creative",
    ])
    output_format: str = "text"  # all layers return plain text
    confidence_threshold: float = 0.6  # min confidence to accept


@dataclass
class CalibrationState:
    """Adaptive threshold calibration from success/failure rates."""
    fast_simple_threshold: float = 0.5   # below this → fast model
    fast_success_rate: float = 0.95
    reasoning_escalation_rate: float = 0.15  # % of fast queries escalated
    target_escalation: float = 0.2          # ideal escalation rate
    last_calibrated: float = field(default_factory=time.time)


@dataclass
class PromptVersion:
    """Tracked prompt version with rollback capability."""
    version_id: str
    content_hash: str
    created_at: float
    quality_score: float = 0.5
    request_count: int = 0
    active: bool = True


class LayerGovernance:
    """Orchestrates consistency, fallback, calibration, and versioning."""

    _instance: Optional["LayerGovernance"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._contract = LayerContract()
        self._calibration = CalibrationState()
        self._prompt_versions: dict[str, list[PromptVersion]] = {}  # domain → versions
        self._escalation_log: list[dict] = []  # last 100 escalation events

    @classmethod
    def instance(cls) -> "LayerGovernance":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = LayerGovernance()
        return cls._instance

    # ═══ 1. Layer Consistency Contract ═════════════════════════════

    def validate_query(self, query: str, layer: LayerLevel) -> dict:
        """Validate that a query is appropriate for a layer.

        Returns {decision, confidence, reason}.
        """
        try:
            from .adaptive_classifier import get_adaptive_classifier
            ac = get_adaptive_classifier()
            task_type, confidence = ac.classify(query, ac.TASK_TYPES, "tasks")
        except Exception:
            task_type, confidence = "general", 0.5

        # Check classification consistency
        if task_type not in self._contract.classification_labels:
            task_type = "chat"

        # Layer-specific gating
        if layer == LayerLevel.LOCAL:
            if confidence < self._contract.confidence_threshold:
                return {"decision": Decision.ESCALATE, "confidence": confidence,
                       "reason": f"Low confidence ({confidence:.2f} < {self._contract.confidence_threshold})"}
            if len(query) > 200:
                return {"decision": Decision.ESCALATE, "confidence": confidence,
                       "reason": "Query too long for local model"}
            return {"decision": Decision.ACCEPT, "confidence": confidence, "reason": "ok"}

        elif layer == LayerLevel.FAST:
            if task_type in ("code", "reasoning"):
                if self._is_complex(query):
                    return {"decision": Decision.ESCALATE, "confidence": confidence,
                           "reason": f"Complex {task_type} → reasoning layer"}
            return {"decision": Decision.ACCEPT, "confidence": confidence, "reason": "ok"}

        else:  # REASONING
            return {"decision": Decision.ACCEPT, "confidence": confidence, "reason": "ok"}

    # ═══ 2. Fallback Chain ═════════════════════════════════════════

    async def execute_with_fallback(self, query: str,
                                     tree_llm=None) -> dict:
        """Execute query with full fallback chain: local → fast → reasoning."""
        t0 = time.time()
        chain = []
        result_text = ""

        try:
            from .sticky_election import get_layer_config
            cfg = get_layer_config()
        except Exception:
            cfg = None

        # Tier 1: Local / fast (same path if no local model)
        validation = self.validate_query(query, LayerLevel.FAST)
        chain.append({"layer": "fast", "decision": validation["decision"]})

        if validation["decision"] == Decision.ACCEPT and tree_llm and cfg:
            prov, model = cfg.get_provider(1)
            p = tree_llm._providers.get(prov)
            if p:
                try:
                    r = await p.chat(messages=[{"role": "user", "content": query}],
                                    model=model or None, temperature=0.7,
                                    max_tokens=1024, timeout=30)
                    fast_text = r.text if r and hasattr(r, 'text') else ""
                    if fast_text and len(fast_text) > 30:
                        result_text = fast_text
                except Exception as e:
                    chain[-1]["error"] = str(e)[:80]

        # Tier 2: Reasoning (if fast didn't produce or escalated)
        if not result_text and tree_llm and cfg:
            prov, model = cfg.get_provider(2)
            p = tree_llm._providers.get(prov)
            if p:
                try:
                    r = await p.chat(messages=[{"role": "user", "content": query}],
                                    model=model or None, temperature=0.3,
                                    max_tokens=2048, timeout=60)
                    reas_text = r.text if r and hasattr(r, 'text') else ""
                    if reas_text:
                        result_text = reas_text
                        chain.append({"layer": "reasoning", "decision": "accept"})
                except Exception as e:
                    chain.append({"layer": "reasoning", "decision": "error",
                                  "error": str(e)[:80]})

        # Log escalation
        self._escalation_log.append({
            "query": query[:100], "chain": chain, "time": time.time(),
            "final_layer": chain[-1]["layer"] if chain else "none",
        })
        if len(self._escalation_log) > 100:
            self._escalation_log.pop(0)

        elapsed = (time.time() - t0) * 1000
        return {"text": result_text, "chain": chain, "elapsed_ms": round(elapsed, 0)}

    # ═══ 3. Boundary Calibration ═══════════════════════════════════

    def calibrate(self):
        """Adapt complexity thresholds from escalation history.

        If too many queries are escalated (rate > target), raise thresholds.
        If too few are escalated (rate < target/2), lower thresholds.
        """
        if len(self._escalation_log) < 10:
            return

        recent = self._escalation_log[-50:]
        escalated = sum(1 for e in recent
                       if any(c.get("decision") in ("escalate",) for c in e.get("chain", [])))
        total = len(recent)
        rate = escalated / max(total, 1)

        cal = self._calibration
        error = rate - cal.target_escalation
        # PID-like correction
        cal.fast_simple_threshold = max(0.2, min(0.8,
            cal.fast_simple_threshold - error * 0.05))

        cal.last_calibrated = time.time()
        logger.debug(f"Calibration: escalation_rate={rate:.2f} (target={cal.target_escalation}), "
                    f"new_fast_threshold={cal.fast_simple_threshold:.2f}")

    def record_success(self, layer: LayerLevel):
        """Record successful request for calibration."""
        if layer == LayerLevel.FAST:
            self._calibration.fast_success_rate = (
                self._calibration.fast_success_rate * 0.9 + 0.1
            )

    def record_failure(self, layer: LayerLevel):
        """Record failed request for calibration."""
        if layer == LayerLevel.FAST:
            self._calibration.fast_success_rate = (
                self._calibration.fast_success_rate * 0.95
            )

    # ═══ 4. Version Coordination ═══════════════════════════════════

    def register_prompt(self, domain: str, content: str) -> str:
        """Register a new prompt version. Returns version_id."""
        version_id = f"v{len(self._prompt_versions.get(domain, [])) + 1}_{int(time.time())}"
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        pv = PromptVersion(version_id=version_id, content_hash=content_hash,
                          created_at=time.time())

        # Deactivate previous versions
        if domain in self._prompt_versions:
            for old in self._prompt_versions[domain]:
                old.active = False

        self._prompt_versions.setdefault(domain, []).append(pv)
        versions = self._prompt_versions[domain]
        if len(versions) > 10:
            versions.pop(0)

        logger.info(f"Prompt version registered: {domain}/{version_id} (hash={content_hash})")
        return version_id

    def get_active_prompt(self, domain: str) -> str | None:
        """Get the currently active prompt version for a domain."""
        versions = self._prompt_versions.get(domain, [])
        for pv in reversed(versions):
            if pv.active:
                return pv.version_id
        return None

    def rollback_prompt(self, domain: str) -> bool:
        """Rollback to the previous prompt version (deactivates current)."""
        versions = self._prompt_versions.get(domain, [])
        active = [pv for pv in versions if pv.active]
        if not active:
            return False

        current = active[0]
        current.active = False
        current.quality_score = 0.0  # mark as degraded

        # Activate previous
        inactive = [pv for pv in versions if not pv.active and pv != current]
        if inactive:
            inactive[-1].active = True
            logger.warning(f"Prompt rollback: {domain}/{current.version_id}→{inactive[-1].version_id}")
            return True

        logger.warning(f"Prompt rollback: {domain}/{current.version_id} (no previous version)")
        return False

    def record_prompt_quality(self, domain: str, version_id: str, score: float):
        """Record prompt quality score. Triggers rollback if score < 0.3."""
        versions = self._prompt_versions.get(domain, [])
        for pv in versions:
            if pv.version_id == version_id:
                pv.request_count += 1
                pv.quality_score = pv.quality_score * 0.8 + score * 0.2
                if pv.quality_score < 0.3 and pv.request_count > 10:
                    logger.warning(f"Prompt quality degraded: {domain}/{version_id} score={pv.quality_score:.2f}")
                    self.rollback_prompt(domain)
                break

    # ═══ Stats ═════════════════════════════════════════════════════

    def stats(self) -> dict:
        cal = self._calibration
        return {
            "contract": {
                "labels": self._contract.classification_labels,
                "confidence_threshold": self._contract.confidence_threshold,
            },
            "calibration": {
                "fast_threshold": round(cal.fast_simple_threshold, 3),
                "fast_success_rate": round(cal.fast_success_rate, 3),
                "escalation_rate": round(sum(1 for e in self._escalation_log[-50:]
                    if any(c.get("layer") in ("reasoning",) for c in e.get("chain", [])))
                    / max(len(self._escalation_log[-50:]), 1), 3),
                "target_escalation": cal.target_escalation,
            },
            "escalations": {
                "total": len(self._escalation_log),
                "recent_50": [
                    {"query": e["query"][:60],
                     "final_layer": e.get("final_layer", "?")}
                    for e in self._escalation_log[-10:]
                ],
            },
            "versions": {
                domain: {
                    "active": next((pv.version_id for pv in reversed(vs) if pv.active), "none"),
                    "count": len(vs),
                }
                for domain, vs in self._prompt_versions.items()
            },
        }

    @staticmethod
    def _is_complex(query: str) -> bool:
        if len(query) > 300: return True
        indicators = ["compare", "analyze", "evaluate", "implement",
                     "对比", "分析", "评估", "实现", "架构", "设计"]
        return any(k in query.lower() for k in indicators)


def get_layer_governance() -> LayerGovernance:
    return LayerGovernance.instance()
