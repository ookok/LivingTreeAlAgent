"""Memory Policy Optimization — MemPO-inspired self-memory management.

Implements the core MemPO algorithm (Li et al., 2026) for LivingTree:
  1. MemoryItem:  记忆条目 with importance + credit scoring
  2. CreditAssigner: RL-based 信用分配 — 回溯成功任务为贡献记忆加分
  3. RetentionPolicy: 选择性保留 — importance × recency > threshold
  4. TokenBudget:  动态 Token 预算分配 — 任务复杂度 → 记忆配额

Core formula (MemPO credit assignment):
  importance_new = importance_old + α × contribution_score × task_success
  contribution_score = ngram_overlap(memory_content, task_output) × access_recency

Integration with existing:
  - StructMemory.EventEntry: 记忆载体
  - MemoryBuffer: 待整合缓冲区
  - TemporalCompressor: 三级量化 (hot/warm/cold)
  - DisCoGC: 存储层 GC 的空间维度 + 记忆层 GC 的时间/重要性维度
"""

from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# ═══ Memory Item ═══

@dataclass
class MemoryItem:
    """A single memory entry with MemPO importance tracking.

    Attributes:
        content: memory text content
        importance: MemPO importance score (increased by credit assignment)
        access_count: how often retrieved
        last_accessed: timestamp of last retrieval
        created_at: creation timestamp
        credit_history: log of credit assignment events
        metadata: arbitrary extra data
    """
    content: str
    importance: float = 1.0
    access_count: int = 0
    last_accessed: float = 0.0
    created_at: float = field(default_factory=time.time)
    credit_history: list[dict] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def recency_score(self, now: float = None) -> float:
        """Exponential recency decay. Recent memories score higher."""
        now = now or time.time()
        age_hours = (now - self.last_accessed) / 3600 if self.last_accessed else (now - self.created_at) / 3600
        return math.exp(-age_hours / 24)  # Half-life: ~16 hours

    @property
    def retention_score(self, now: float = None) -> float:
        """Combined retention score = importance × recency × access_frequency."""
        now = now or time.time()
        freq_boost = min(2.0, 1.0 + math.log(max(self.access_count, 1)) * 0.3)
        return self.importance * self.recency_score * freq_boost

    @property
    def is_cold(self, now: float = None) -> bool:
        now = now or time.time()
        return (now - self.last_accessed) > 86400 * 7  # 7 days untouched

    def mark_accessed(self) -> None:
        self.access_count += 1
        self.last_accessed = time.time()

    def add_credit(self, score: float, task_id: str = "") -> None:
        self.importance += score
        self.credit_history.append({
            "score": score,
            "task_id": task_id,
            "timestamp": time.time(),
        })
        self.importance = max(0.01, min(10.0, self.importance))

    def age_seconds(self) -> float:
        return time.time() - self.created_at


# ═══ Credit Assigner ═══

@dataclass
class CreditEvent:
    """A single credit assignment event — task completion triggers credit."""
    task_id: str
    task_success: float        # 0.0 (fail) to 1.0 (complete success)
    contributed_memories: list[str]  # memory IDs that were accessed
    timestamp: float = field(default_factory=time.time)


class CreditAssigner:
    """MemPO 信用分配器 — 任务成功→回溯→为贡献记忆加分。

    Algorithm:
      1. Task completes with success score s ∈ [0,1]
      2. Backtrack: which memories were accessed during this task?
      3. For each accessed memory:
         contribution = ngram_overlap(memory_content, task_output)
         credit = α × contribution × task_success
         memory.importance += credit

    Usage:
        ca = CreditAssigner(alpha=0.15)
        ca.log_access("mem_001")  # during task execution
        ca.log_access("mem_003")
        ca.assign_credit(task_id="t42", success=0.95,
                        task_output="大气扩散模型参数设置...")
    """

    def __init__(self, alpha: float = 0.15, decay_alpha: bool = True):
        self.alpha = alpha
        self.decay_alpha = decay_alpha
        self._task_access_log: dict[str, list[str]] = defaultdict(list)  # task_id → memory_ids
        self._events: list[CreditEvent] = []
        self._lock = threading.RLock()
        self._total_credits_assigned: float = 0.0
        self._total_assignments: int = 0

    def log_access(self, memory_id: str, task_id: str = "default") -> None:
        with self._lock:
            self._task_access_log[task_id].append(memory_id)

    def assign_credit(
        self,
        task_id: str,
        success: float,
        task_output: str = "",
        memory_store: dict[str, MemoryItem] = None,
    ) -> float:
        """Assign credit to memories that contributed to a task.

        Returns total credit assigned.
        """
        with self._lock:
            accessed_ids = self._task_access_log.pop(task_id, [])
            if not accessed_ids or not memory_store:
                return 0.0

            total_assigned = 0.0
            unique_ids = list(dict.fromkeys(accessed_ids))  # dedup preserve order

            for mem_id in unique_ids:
                if mem_id not in memory_store:
                    continue

                memory = memory_store[mem_id]

                # Contribution score: how much did this memory contribute?
                contribution = self._compute_contribution(
                    memory.content, task_output,
                ) if task_output else 0.3

                credit = self.alpha * contribution * success
                memory.add_credit(credit, task_id)
                total_assigned += credit

            event = CreditEvent(
                task_id=task_id,
                task_success=success,
                contributed_memories=unique_ids,
            )
            self._events.append(event)
            self._total_credits_assigned += total_assigned
            self._total_assignments += 1

            if self.decay_alpha:
                self.alpha *= 0.999  # slow decay to stabilize learning

            logger.debug(
                "CreditAssigner: task=%s success=%.2f → assigned %.3f to %d memories "
                "(α=%.4f, total_assignments=%d)",
                task_id, success, total_assigned, len(unique_ids),
                self.alpha, self._total_assignments,
            )

            return total_assigned

    def penalize_task_failure(self, task_id: str, memory_store: dict[str, MemoryItem] = None) -> float:
        """轻量惩罚：任务失败时，对访问过的记忆略微降低 importance。

        importance *= 0.95 (not a hard penalty — just depreciation).
        """
        with self._lock:
            accessed_ids = self._task_access_log.pop(task_id, [])
            total_penalty = 0.0
            for mem_id in set(accessed_ids):
                if mem_id in memory_store:
                    old = memory_store[mem_id].importance
                    memory_store[mem_id].importance *= 0.95
                    total_penalty += old - memory_store[mem_id].importance

            return total_penalty

    def get_top_contributing_memories(self, n: int = 10, memory_store: dict = None) -> list[tuple[str, float]]:
        if not memory_store:
            return []
        scored = [(mid, m.importance) for mid, m in memory_store.items()]
        scored.sort(key=lambda x: -x[1])
        return scored[:n]

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "alpha": round(self.alpha, 6),
                "total_credits_assigned": round(self._total_credits_assigned, 4),
                "total_assignments": self._total_assignments,
                "credit_events": len(self._events),
                "recent_events": len(self._task_access_log),
            }

    @staticmethod
    def _compute_contribution(memory_content: str, task_output: str) -> float:
        """Compute how much a memory contributed to the task output.

        Uses Jaccard similarity of character trigrams.
        """
        if not memory_content or not task_output:
            return 0.3

        def _trigrams(text: str) -> set:
            return {text[i:i+3] for i in range(len(text) - 2)}

        a = _trigrams(memory_content.lower())
        b = _trigrams(task_output.lower())

        if not a or not b:
            return 0.3

        overlap = len(a & b)
        union = len(a | b)
        return overlap / max(union, 1)


# ═══ Retention Policy ═══

class RetentionPolicy:
    """MemPO 选择性保留策略 — importance × recency > threshold.

    三层决策:
      RETAIN:   retention_score >= keep_threshold → 保留
      COMPRESS: compress_threshold <= score < keep_threshold → 压缩为摘要
      FORGET:   score < compress_threshold → 遗忘（释放 token）

    Usage:
        rp = RetentionPolicy(keep_threshold=0.5, compress_threshold=0.1)
        decision = rp.decide(memory_item)
        if decision == "RETAIN":
            keep(memory_item)
        elif decision == "FORGET":
            forget(memory_item)
    """

    def __init__(
        self,
        keep_threshold: float = 0.5,
        compress_threshold: float = 0.15,
        max_memories: int = 1000,
    ):
        self.keep_threshold = keep_threshold
        self.compress_threshold = compress_threshold
        self.max_memories = max_memories

    def decide(self, memory: MemoryItem, now: float = None) -> str:
        score = memory.retention_score
        if score >= self.keep_threshold:
            return "RETAIN"
        elif score >= self.compress_threshold:
            return "COMPRESS"
        return "FORGET"

    def apply_policy(
        self,
        memory_store: dict[str, MemoryItem],
        now: float = None,
    ) -> tuple[list[str], list[str], list[str]]:
        """Apply retention policy to the entire memory store.

        Returns (retained_ids, compressed_ids, forgotten_ids).
        """
        now = now or time.time()
        retained, compressed, forgotten = [], [], []

        scored = [(mid, m.retention_score) for mid, m in memory_store.items()]
        scored.sort(key=lambda x: -x[1])

        max_keep = self.max_memories

        for i, (mem_id, score) in enumerate(scored):
            if i < max_keep and score >= self.keep_threshold:
                retained.append(mem_id)
            elif score >= self.compress_threshold:
                compressed.append(mem_id)
            else:
                forgotten.append(mem_id)

        if retained:
            logger.debug(
                "RetentionPolicy: retained=%d (max=%.2f) compressed=%d forgotten=%d",
                len(retained), scored[0][1] if scored else 0,
                len(compressed), len(forgotten),
            )

        return retained, compressed, forgotten

    def get_policy_stats(self, memory_store: dict[str, MemoryItem]) -> dict:
        if not memory_store:
            return {"retained": 0, "compressed": 0, "forgotten": 0}

        retained, compressed, forgotten = self.apply_policy(memory_store)
        return {
            "total": len(memory_store),
            "retained": len(retained),
            "compressed": len(compressed),
            "forgotten": len(forgotten),
            "retention_rate": len(retained) / len(memory_store),
            "avg_importance": sum(m.importance for m in memory_store.values()) / len(memory_store),
            "avg_access_count": sum(m.access_count for m in memory_store.values()) / len(memory_store),
        }


# ═══ Token Budget ═══

class TokenBudget:
    """动态 Token 预算分配 — 任务复杂度 → 记忆配额。

    核心公式:
      budget = base_tokens + complexity_bonus × complexity_factor
      per_memory = budget / n_retained_memories

    对接现有 ContextAssembler 的字符预算系统。
    """

    def __init__(
        self,
        base_tokens: int = 2048,
        max_tokens: int = 8192,
        complexity_bonus: int = 4096,
    ):
        self.base_tokens = base_tokens
        self.max_tokens = max_tokens
        self.complexity_bonus = complexity_bonus

    def allocate(
        self,
        task_complexity: float = 0.5,
        num_memories: int = 10,
    ) -> tuple[int, int]:
        """Allocate token budget based on task complexity.

        Args:
            task_complexity: 0.0 (simple) to 1.0 (very complex)
            num_memories: number of candidate memories

        Returns: (total_budget_tokens, per_memory_tokens)
        """
        budget = int(self.base_tokens + self.complexity_bonus * task_complexity)
        budget = min(budget, self.max_tokens)

        per_memory = budget // max(num_memories, 1) if num_memories > 0 else budget
        return budget, per_memory

    def estimate_complexity(self, query: str) -> float:
        """Heuristic: estimate task complexity from query characteristics.

        Factors:
          - Length: longer queries → more complex
          - Multi-part: "与", "以及", "和" → compound → more complex
          - Technical depth: presence of technical terms
        """
        score = 0.3  # base

        if len(query) > 50:
            score += 0.2
        if len(query) > 100:
            score += 0.1

        compound_markers = ["与", "以及", "和", "对比", "比较", "综合"]
        if any(m in query for m in compound_markers):
            score += 0.2

        tech_terms = ["参数", "模型", "标准", "规范", "公式", "分析", "评估",
                     "计算", "模拟", "优化", "验证"]
        tech_count = sum(1 for t in tech_terms if t in query)
        score += min(0.3, tech_count * 0.05)

        return min(1.0, max(0.1, score))

    def format_context_budget(
        self,
        memories: list[MemoryItem],
        task_complexity: float = 0.5,
    ) -> tuple[str, int]:
        """Format memories for context injection, respecting token budget.

        Returns (context_string, tokens_used).
        """
        budget, per_memory = self.allocate(task_complexity, len(memories))

        sorted_mems = sorted(memories, key=lambda m: -m.retention_score)
        parts = []
        tokens_used = 0
        budget_chars = budget * 3  # ~3 chars per token

        for mem in sorted_mems:
            chunk = mem.content[:per_memory * 3]  # ~3 chars per token
            if tokens_used + len(chunk) > budget_chars:
                break
            parts.append(chunk)
            tokens_used += len(chunk)

        return "\n\n---\n".join(parts), tokens_used // 3


# ═══ MemPO Optimizer (Top-level orchestrator) ═══

class MemPOOptimizer:
    """MemPO 记忆策略优化器 — 顶层编排。

    Orchestrates:
      1. Credit assignment for each completed task
      2. Periodic retention policy application
      3. Token budget allocation for context assembly

    Usage:
        mempo = MemPOOptimizer()
        mempo.add_memory("mem_1", "大气扩散模型参数...")
        mempo.log_access("mem_1")
        mempo.on_task_complete(success=0.9, task_output="根据HJ2.2设置...")
        mempo.optimize()  # Apply retention policy
    """

    def __init__(
        self,
        keep_threshold: float = 0.5,
        compress_threshold: float = 0.15,
        max_memories: int = 1000,
        alpha: float = 0.15,
    ):
        self._memories: OrderedDict[str, MemoryItem] = OrderedDict()
        self._credit_assigner = CreditAssigner(alpha=alpha)
        self._retention = RetentionPolicy(
            keep_threshold=keep_threshold,
            compress_threshold=compress_threshold,
            max_memories=max_memories,
        )
        self._token_budget = TokenBudget()
        self._lock = threading.RLock()
        self._next_id = 0
        self._optimization_count = 0

    def add_memory(self, content: str, **metadata) -> str:
        with self._lock:
            self._next_id += 1
            mem_id = f"mem_{self._next_id}"
            self._memories[mem_id] = MemoryItem(content=content, metadata=metadata)
            if len(self._memories) > self._retention.max_memories * 2:
                self.optimize()
            return mem_id

    def get_memory(self, mem_id: str) -> Optional[MemoryItem]:
        return self._memories.get(mem_id)

    def log_access(self, mem_id: str, task_id: str = "default") -> None:
        with self._lock:
            if mem_id in self._memories:
                self._memories[mem_id].mark_accessed()
            self._credit_assigner.log_access(mem_id, task_id)

    def on_task_complete(
        self,
        task_id: str = "default",
        success: float = 1.0,
        task_output: str = "",
    ) -> float:
        with self._lock:
            return self._credit_assigner.assign_credit(
                task_id, success, task_output, self._memories,
            )

    def on_task_fail(self, task_id: str = "default") -> float:
        with self._lock:
            return self._credit_assigner.penalize_task_failure(task_id, self._memories)

    def optimize(self, force_forget_overflow: bool = True) -> dict:
        with self._lock:
            retained, compressed, forgotten = self._retention.apply_policy(self._memories)

            for mem_id in forgotten:
                del self._memories[mem_id]

            # Force-forget lowest-scoring items when exceeding 2x max
            if force_forget_overflow and len(self._memories) > self._retention.max_memories * 2:
                all_scored = sorted(
                    [(mid, m.retention_score) for mid, m in self._memories.items()],
                    key=lambda x: x[1],
                )
                excess = len(self._memories) - self._retention.max_memories
                for mem_id, _ in all_scored[:excess]:
                    if mem_id in self._memories:
                        del self._memories[mem_id]
                        forgotten.append(mem_id)

            self._optimization_count += 1

            logger.info(
                "MemPO: optim=%d — retained=%d compressed=%d forgotten=%d "
                "(memory_size=%d, avg_imp=%.3f)",
                self._optimization_count,
                len(retained), len(compressed), len(forgotten),
                len(self._memories),
                sum(m.importance for m in self._memories.values()) / max(len(self._memories), 1),
            )

            return {
                "optimization": self._optimization_count,
                "retained": len(retained),
                "compressed": len(compressed),
                "forgotten": len(forgotten),
                "total_memories": len(self._memories),
                "credit_stats": self._credit_assigner.get_stats(),
                "policy_stats": self._retention.get_policy_stats(self._memories),
            }

    def build_context(
        self,
        query: str = "",
        task_complexity: float = 0.5,
        max_memories: int = 20,
    ) -> tuple[str, int]:
        with self._lock:
            top_memories = sorted(
                self._memories.values(),
                key=lambda m: -m.retention_score,
            )[:max_memories]

            task_complexity_est = self._token_budget.estimate_complexity(query) if query else task_complexity
            return self._token_budget.format_context_budget(top_memories, task_complexity_est)

    def get_top_memories(self, n: int = 10) -> list[tuple[str, MemoryItem]]:
        scored = [(mid, m) for mid, m in self._memories.items()]
        scored.sort(key=lambda x: -x[1].retention_score)
        return scored[:n]

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_memories": len(self._memories),
                "optimizations": self._optimization_count,
                "avg_importance": sum(m.importance for m in self._memories.values()) / max(len(self._memories), 1),
                "avg_access_count": sum(m.access_count for m in self._memories.values()) / max(len(self._memories), 1),
                "credit": self._credit_assigner.get_stats(),
                "policy": self._retention.get_policy_stats(self._memories),
            }
