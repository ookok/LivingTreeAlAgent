"""Human-in-the-Loop Co-Pilot (HITL) — 6 intervention modes + SmartPause.

AutoResearchClaw-inspired: gate-only, checkpoint, step-by-step, co-pilot, custom.
Integrates with life_engine.py for DNA-stage intervention.
"""

import time
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class InterventionMode(str, Enum):
    FULL_AUTO = "full-auto"
    GATE_ONLY = "gate-only"
    CHECKPOINT = "checkpoint"
    STEP_BY_STEP = "step-by-step"
    CO_PILOT = "co-pilot"
    CUSTOM = "custom"


class HITLStagePolicy(BaseModel):
    stage: str
    mode: InterventionMode
    requires_approval: bool = False
    requires_guidance: bool = False
    pause_on_low_confidence: bool = False
    min_confidence: float = 0.7


class HITLConfig(BaseModel):
    mode: InterventionMode = InterventionMode.FULL_AUTO
    gate_stages: List[str] = Field(default_factory=lambda: ["plan", "execute", "reflect"])
    custom_policies: List[HITLStagePolicy] = Field(default_factory=list)
    smart_pause_enabled: bool = True
    smart_pause_confidence_threshold: float = 0.6
    smart_pause_novelty_threshold: float = 0.7
    approval_timeout: float = 120.0
    max_auto_retries: int = 3


class HITLStatus(BaseModel):
    mode: InterventionMode
    current_stage: str = ""
    is_paused: bool = False
    pending_approvals: int = 0
    total_interventions: int = 0
    last_interaction: float = 0.0


class HITLManager:
    def __init__(self, config: Optional[HITLConfig] = None) -> None:
        self.config: HITLConfig = config or HITLConfig()
        self._intervention_log: List[Dict[str, Any]] = []
        self._pending_approvals: Dict[str, float] = {}
        self._status: HITLStatus = HITLStatus(mode=self.config.mode)

    # Configuration
    def configure(self, mode: InterventionMode, **kwargs: Any) -> None:
        self.config.mode = mode
        for k, v in kwargs.items():
            if hasattr(self.config, k):
                setattr(self.config, k, v)
        self._status.mode = mode

    # Core logging helper
    def _log_intervention(self, stage_name: str, question: str, context: Optional[Dict[str, Any]], timeout: Optional[float]) -> None:
        entry = {
            "timestamp": time.time(),
            "stage": stage_name,
            "question": question,
            "context": context or {},
            "timeout": timeout,
            "mode": self.config.mode.value,
        }
        self._intervention_log.append(entry)

    def _policy_for_stage(self, stage_name: str) -> Optional[HITLStagePolicy]:
        for p in self.config.custom_policies:
            if p.stage == stage_name:
                return p
        return None

    # Public API expected by life_engine
    def request_approval(
        self, stage_name: str, question: str, context: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None
    ) -> bool:
        context = context or {}
        self._status.total_interventions += 1
        policy = self._policy_for_stage(stage_name)

        mode = self.config.mode
        approved = True

        # Mode-specific behavior
        if mode == InterventionMode.FULL_AUTO:
            approved = True
        elif mode == InterventionMode.GATE_ONLY:
            if stage_name in self.config.gate_stages:
                self.pause()
            approved = True
        elif mode == InterventionMode.CHECKPOINT:
            checkpoint_phases = {"perceive", "cognize", "plan", "execute", "reflect", "evolve"}
            if stage_name.lower() in checkpoint_phases:
                self.pause()
            approved = True
        elif mode == InterventionMode.STEP_BY_STEP:
            approved = True
        elif mode == InterventionMode.CO_PILOT:
            if stage_name in {"hypothesis_gen", "experiment_design", "paper_draft"}:
                self.pause()
            approved = True
        elif mode == InterventionMode.CUSTOM and policy is not None:
            # Respect per-stage custom policy
            if policy.requires_approval:
                self._pending_approvals[stage_name] = time.time() + (timeout or self.config.approval_timeout)
                self._status.pending_approvals = len(self._pending_approvals)
            # If policy asks to pause on low confidence, respect it here
            if policy.pause_on_low_confidence and "confidence" in (context or {}):
                if float(context.get("confidence", 0.0)) < policy.min_confidence:
                    self.pause()
                    self._log_intervention(stage_name, question, context, timeout)
                    self._status.last_interaction = time.time()
                    return True
            approved = True
        else:
            approved = True

        # Always log and update status, and clear any resolved approvals if present
        self._log_intervention(stage_name, question, context, timeout)
        self._status.last_interaction = time.time()
        if stage_name in self._pending_approvals:
            self._pending_approvals.pop(stage_name, None)
            self._status.pending_approvals = len(self._pending_approvals)
        return approved

    def request_guidance(self, stage_name: str, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        self._log_intervention(stage_name, prompt, context or {}, None)
        self._status.last_interaction = time.time()
        # No real guidance generation in this HITL mock; return empty guidance per spec
        return ""

    def should_pause(self, stage_name: str) -> bool:
        if self.config.smart_pause_enabled:
            # Infer from last logged context if available
            if self._intervention_log:
                last = self._intervention_log[-1]
                ctx = last.get("context", {}) if isinstance(last.get("context"), dict) else {}
                confidence = float(ctx.get("confidence", 0.0))
                novelty = float(ctx.get("novelty", 0.0))
                if confidence < self.config.smart_pause_confidence_threshold:
                    return True
                if novelty > self.config.smart_pause_novelty_threshold:
                    return True
        mode = self.config.mode
        if mode == InterventionMode.GATE_ONLY and stage_name in self.config.gate_stages:
            return True
        if mode == InterventionMode.CHECKPOINT:
            if stage_name.lower() in {"perceive", "cognize", "plan", "execute", "reflect", "evolve"}:
                return True
        if mode == InterventionMode.CO_PILOT and stage_name in {"hypothesis_gen", "experiment_design", "paper_draft"}:
            return True
        if mode == InterventionMode.CUSTOM:
            policy = self._policy_for_stage(stage_name)
            if policy and policy.pause_on_low_confidence:
                # If we have recent context with a confidence, evaluate it
                if self._intervention_log:
                    last = self._intervention_log[-1]
                    ctx = last.get("context", {}) if isinstance(last.get("context"), dict) else {}
                    conf = float(ctx.get("confidence", 0.0))
                    if conf < policy.min_confidence:
                        return True
        return False

    def get_status(self) -> HITLStatus:
        return self._status

    def pause(self) -> None:
        self._status.is_paused = True
        self._log_intervention("pause", "SmartPause engaged", None, None)

    def resume(self) -> None:
        self._status.is_paused = False
        self._log_intervention("resume", "SmartPause disengaged", None, None)

    def abort(self, reason: str) -> None:
        self._pending_approvals.clear()
        self._status.pending_approvals = 0
        self._log_intervention("abort", reason, None, None)

    def get_intervention_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._intervention_log[-limit:]


# Singleton instance for life_engine compatibility
HITL_MANAGER = HITLManager()

def get_hitl_manager() -> HITLManager:
    return HITL_MANAGER
