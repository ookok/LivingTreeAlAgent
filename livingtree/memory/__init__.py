"""LivingTree Memory Layer — MemPO self-memory policy optimization.

MemPO (Li et al., 2026): Agent autonomously summarizes and manages memory
during long-horizon interaction. Credit assignment based on memory
effectiveness selectively retains crucial information, significantly
reducing token consumption while preserving task performance.

Core modules:
  - MemoryItem: memory entry with importance + credit tracking
  - CreditAssigner: RL-based credit assignment (task success → backtrack → reward)
  - RetentionPolicy: selective retention (importance × recency > threshold)
  - TokenBudget: dynamic token allocation (task complexity → memory quota)
  - MemPOOptimizer: top-level orchestrator
"""
from .memory_policy import (
    MemoryItem,
    CreditAssigner,
    CreditEvent,
    RetentionPolicy,
    TokenBudget,
    MemPOOptimizer,
)

__all__ = [
    "MemoryItem",
    "CreditAssigner",
    "CreditEvent",
    "RetentionPolicy",
    "TokenBudget",
    "MemPOOptimizer",
]
