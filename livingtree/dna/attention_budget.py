from __future__ import annotations
import time, math
from dataclasses import dataclass, field
from collections import deque
from loguru import logger

@dataclass
class HookProfile:
    """Profile for a single post-processing hook."""
    name: str                          # e.g. "mempo", "rlvr_monitor", "gep_compile"
    cost_tokens: int = 500             # approximate token cost per run
    min_complexity: float = 0.0        # minimum query complexity to activate
    frequency: int = 1                 # run every N cycles (1=every cycle)
    category: str = "core"             # core/quality/evolution/meta
    enabled: bool = True

class AttentionBudgetOptimizer:
    """Dynamically selects which post-processing hooks to run.
    
    Core principle: simple queries don't need 20+ post-hooks.
    Each hook has a cost and a minimum complexity threshold.
    
    COMPLEXITY → HOOK SELECTION:
      complexity < 0.2 (very simple: "hello", "yes"):
        → only CORE hooks (struct_mem, conversation_dna)
      complexity < 0.4 (simple: "what is X?"):
        → CORE + context wiki compilation
      complexity < 0.6 (moderate: "compare A and B"):
        → CORE + wiki + retrieval framework + mempo
      complexity < 0.8 (complex: "design a system for X"):
        → ALL quality hooks + evolution hooks
      complexity >= 0.8 (very complex: multi-step reasoning):
        → ALL hooks enabled (full pipeline)
    """
    
    # Hook definitions with cost and minimum complexity
    HOOKS = {
        "struct_mem":       HookProfile("struct_mem", 200, 0.0, 1, "core"),
        "conversation_dna": HookProfile("conversation_dna", 150, 0.0, 1, "core"),
        "context_wiki":     HookProfile("context_wiki", 300, 0.15, 1, "core"),
        "retrieval_framework": HookProfile("retrieval_framework", 200, 0.3, 1, "quality"),
        "mempo_credit":     HookProfile("mempo_credit", 400, 0.3, 1, "evolution"),
        "surprise_gate":    HookProfile("surprise_gate", 250, 0.4, 1, "evolution"),
        "rlvr_monitor":     HookProfile("rlvr_monitor", 200, 0.5, 1, "quality"),
        "external_verifier": HookProfile("external_verifier", 500, 0.5, 1, "quality"),
        "gep_compile":      HookProfile("gep_compile", 350, 0.4, 2, "evolution"),
        "safety_coordinator": HookProfile("safety_coordinator", 250, 0.3, 1, "quality"),
        "shesha_delegation": HookProfile("shesha_delegation", 400, 0.5, 2, "meta"),
        "emotion_decision": HookProfile("emotion_decision", 200, 0.3, 1, "meta"),
        "meta_optimizer":   HookProfile("meta_optimizer", 300, 0.6, 5, "meta"),
        "autonomous_goals": HookProfile("autonomous_goals", 500, 0.6, 20, "meta"),
        "dream_school":     HookProfile("dream_school", 600, 0.7, 50, "meta"),
        "identity_narrative": HookProfile("identity_narrative", 400, 0.5, 10, "meta"),
    }
    
    def __init__(self):
        self._cycle_count = 0
        self._hook_runs: dict[str, int] = {}
        self._tokens_saved: int = 0
        self._total_tokens_spent: int = 0
    
    def get_active_hooks(self, complexity: float, cycle_count: int) -> list[str]:
        """Return list of hook names that should run for this complexity level."""
        self._cycle_count = cycle_count
        active = []
        
        for name, profile in self.HOOKS.items():
            if not profile.enabled:
                continue
            # Complexity gate
            if complexity < profile.min_complexity:
                continue
            # Frequency gate
            if cycle_count % profile.frequency != 0:
                continue
            active.append(name)
            self._hook_runs[name] = self._hook_runs.get(name, 0) + 1
            self._total_tokens_spent += profile.cost_tokens
        
        # Calculate tokens saved (hooks NOT run)
        all_hooks_cost = sum(p.cost_tokens for p in self.HOOKS.values())
        self._tokens_saved = all_hooks_cost - sum(
            self.HOOKS[n].cost_tokens for n in active
        )
        
        logger.debug(
            f"AttentionBudget: complexity={complexity:.2f} → "
            f"{len(active)}/{len(self.HOOKS)} hooks active, "
            f"tokens_saved={self._tokens_saved}"
        )
        return active
    
    def stats(self) -> dict:
        return {
            "cycle_count": self._cycle_count,
            "tokens_saved": self._tokens_saved,
            "total_spent": self._total_tokens_spent,
            "savings_ratio": self._tokens_saved / max(self._total_tokens_spent + self._tokens_saved, 1),
            "hook_runs": dict(self._hook_runs),
        }

# Singleton
_budget: AttentionBudgetOptimizer | None = None

def get_attention_budget() -> AttentionBudgetOptimizer:
    global _budget
    if _budget is None:
        _budget = AttentionBudgetOptimizer()
    return _budget
