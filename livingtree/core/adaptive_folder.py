"""Adaptive Context Folding — neurologically-inspired context compression.

Based on Nature Neuroscience: constituent-constrained prediction.
The brain compresses at phrase boundaries and uses dual-context (compressed
distant + detailed local) for efficient prediction.

Applied to LLM agents:
1. Fold context at natural boundaries (turn, step, section) — not continuously
2. Dual-context injection: compressed history + detailed current window
3. Budget allocation: more tokens for high-relevance, less for background
4. Smaller effective context → faster, cheaper, with minimal quality loss

Integrates with existing: context_fold.py, token_compressor.py, BudgetAllocation.
"""

from __future__ import annotations

import time as _time
from typing import Optional

from loguru import logger

from ..execution.context_fold import fold_text_heuristic, BudgetAllocation, score_segment_relevance


class AdaptiveFolder:
    """Context compression triggered at natural boundaries, like the brain."""

    # Boundaries where compression is safe and beneficial
    BOUNDARY_MARKERS = [
        "\n\n", "---", "===", "## ", "# ",  # Document structure
    ]

    def __init__(self, max_context_chars: int = 4000, fold_target_chars: int = 500):
        self._max_context = max_context_chars
        self._fold_target = fold_target_chars
        self._compressed_segments: list[str] = []
        self._stats = {"folded": 0, "saved_chars": 0, "total_folds": 0}

    def should_fold(self, text: str, is_boundary: bool = False) -> bool:
        """Fold when: at natural boundary AND context exceeds budget."""
        return is_boundary and len(text) > self._max_context

    def fold_at_boundary(self, full_context: str, current_query: str = "",
                          consciousness=None) -> str:
        """Compress context at a logical boundary. Returns optimized context."""
        if len(full_context) <= self._max_context:
            return full_context

        if consciousness:
            return self._llm_fold(full_context, consciousness)

        return self._heuristic_fold(full_context, current_query)

    def _llm_fold(self, context: str, consciousness) -> str:
        """LLM-powered folding: compress while preserving key entities/decisions."""
        try:
            prompt = (
                f"压缩以下上下文, 保留关键实体、决策和结论。目标{self._fold_target}字以内:\n\n"
                f"{context[:8000]}"
            )
            result = consciousness.chain_of_thought(prompt, steps=1)
            folded = result if isinstance(result, str) else str(result)
            if len(folded) < len(context):
                saved = len(context) - len(folded)
                self._stats["folded"] += 1
                self._stats["saved_chars"] += saved
                self._stats["total_folds"] += 1
                logger.debug(f"Context folded: {len(context)} → {len(folded)} chars (saved {saved})")
                return folded[:self._fold_target]
        except Exception as e:
            logger.debug(f"LLM fold failed, using heuristic: {e}")
        return self._heuristic_fold(context, "")

    def _heuristic_fold(self, context: str, query: str) -> str:
        """Heuristic folding: keep first/last + key lines."""
        lines = context.split("\n")
        if len(lines) <= 10:
            return context

        # Keep: first 3 lines, last 2 lines, lines with key indicators
        key_indicators = ["结论", "决策", "错误", "关键", "重要", "步骤",
                          "Error", "Decision", "Step", "Key", "Important",
                          "```", "###", "##"]
        keep_indices = {0, 1, 2, len(lines) - 2, len(lines) - 1}
        for i, line in enumerate(lines):
            if any(ind in line for ind in key_indicators):
                keep_indices.add(i)

        result = []
        for i in sorted(keep_indices):
            if i < len(lines):
                result.append(lines[i][:200])

        folded = "\n".join(result)
        if len(folded) < len(context):
            saved = len(context) - len(folded)
            self._stats["folded"] += 1
            self._stats["saved_chars"] += saved
            self._stats["total_folds"] += 1

        return folded[:self._max_context]

    def dual_context(self, full_history: str, current_step: str) -> str:
        """Dual-context: compressed distant + detailed local (like the brain).

        full_history: everything up to this point
        current_step: the current reasoning/execution window
        Returns: optimized context for LLM injection
        """
        if len(full_history) <= self._max_context:
            return full_history

        folded = self.fold_at_boundary(full_history)
        if len(folded) + len(current_step) <= self._max_context:
            return f"[上文摘要]\n{folded}\n\n[当前]\n{current_step}"

        step_folded = current_step[:self._max_context - len(folded) - 50]
        return f"[上文摘要]\n{folded}\n\n[当前]\n{step_folded}"

    def budget_allocate(self, segments: list[tuple[str, float]]) -> str:
        """Allocate context budget by relevance score (like attention routing).

        segments: list of (text, relevance_score)
        Returns: assembled context within budget
        """
        budget = BudgetAllocation(total_budget=self._max_context)
        allocations = []
        for text, score in segments:
            alloc = budget.allocate(text, score)
            allocations.append((score, alloc.text[:alloc.allocated_chars]))

        allocations.sort(key=lambda x: -x[0])
        return "\n\n---\n\n".join(t for _, t in allocations)

    def stats(self) -> dict:
        total_saved = self._stats["saved_chars"]
        return {
            **self._stats,
            "estimated_tokens_saved": total_saved // 4,
            "estimated_cost_saved_yuan": round(total_saved / 1_000_000 * 2, 6),
        }


_folder_instance: Optional[AdaptiveFolder] = None


def get_folder() -> AdaptiveFolder:
    global _folder_instance
    if _folder_instance is None:
        _folder_instance = AdaptiveFolder()
    return _folder_instance
