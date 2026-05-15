"""Historical Logic — 历史逻辑五规律：归因迭代 + 层累演进 + 民心向背."""
from .attribution_loop import AttributionLoop, Attribution
from .reasoning_hub import (
    LayeringTracker, Layer, EmergentCapability,
    ConsensusMeasure, ABComparison, TrialResult, DecisionOutcome,
    get_layering_tracker, get_consensus_measure,
)

__all__ = [
    "AttributionLoop", "Attribution",
    "LayeringTracker", "Layer", "EmergentCapability",
    "ConsensusMeasure", "ABComparison", "TrialResult", "DecisionOutcome",
    "get_layering_tracker", "get_consensus_measure",
]
