"""life_context.py — Data structures for the LifeEngine pipeline.

Extracted from life_engine.py as part of God Object decomposition.
Contains all dataclasses, enums, and Pydantic models used by the engine.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


class StageGate(enum.StrEnum):
    """CRV 6-stage signal-line protocol gate states (RuView pattern).
    
    gestalt → sensory → topology → coherence → search → model
    """
    ACCEPT = "accept"           # Stage output is confident — proceed
    RECALIBRATE = "recalibrate"  # Stage output insufficient — re-process
    SKIP = "skip"               # Stage not needed for this context
    REJECT = "reject"           # Stage detected unsafe/invalid condition


@dataclass
class StageGateResult:
    """CRV gate result with recalibration hints (RuView coherence gate pattern)."""
    gate: StageGate
    confidence: float           # 0.0-1.0
    reason: str
    recalibration_hints: list[str] = field(default_factory=list)
    max_recalibrations: int = 1  # How many times this stage can recalibrate
    depth_boost: int = 0         # Extra depth for recalibration attempt


class LifeStage(BaseModel):
    stage: str
    started_at: str
    completed_at: str | None = None
    status: str = "pending"
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0


class LifeContext(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_input: str | None = None
    collected_materials: list[dict[str, Any]] = Field(default_factory=list)
    intent: str | None = None
    retrieved_knowledge: list[dict[str, Any]] = Field(default_factory=list)
    plan: list[dict[str, Any]] = Field(default_factory=list)
    execution_results: list[dict[str, Any]] = Field(default_factory=list)
    reflections: list[str] = Field(default_factory=list)
    quality_reports: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Simulation / foresight stage results (optional)
    simulation_ran: bool = False
    simulation_findings: dict[str, Any] = Field(default_factory=dict)
    simulation_decision: dict[str, Any] = Field(default_factory=dict)


@dataclass
class Branch:
    id: str
    name: str
    hypothesis: str
    parent_session: str = ""
    created_at: str = ""
    status: str = "active"  # active, completed, merged, abandoned
    context_snapshot: dict = field(default_factory=dict)
    plan: list = field(default_factory=list)
    execution_results: list = field(default_factory=list)
    reflections: list = field(default_factory=list)
    success_rate: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class ComparisonReport:
    branches_compared: list[str] = field(default_factory=list)
    winner: str = ""
    winner_score: float = 0.0
    scores: dict = field(default_factory=dict)
    improvements: list[str] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class BranchDecision:
    should_branch: bool = False
    reason: str = ""
    num_branches: int = 1
    hypotheses: list[str] = field(default_factory=list)
    confidence: float = 0.0
