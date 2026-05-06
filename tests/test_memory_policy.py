"""MemPO memory policy optimization tests.

Tests:
  - MemoryItem: importance, recency, retention scoring
  - CreditAssigner: task success → credit assignment
  - RetentionPolicy: selective retention / compression / forgetting
  - TokenBudget: task complexity → token allocation
  - MemPOOptimizer: full pipeline orchestration
  - Integration: credit assignment response to importance drift
"""

from __future__ import annotations

import time
import pytest

from livingtree.memory.memory_policy import (
    MemoryItem,
    CreditAssigner,
    RetentionPolicy,
    TokenBudget,
    MemPOOptimizer,
)


# ═══ MemoryItem ═══

class TestMemoryItem:
    def test_initial_state(self):
        m = MemoryItem(content="test memory")
        assert m.importance == 1.0
        assert m.access_count == 0
        assert m.recency_score > 0

    def test_mark_accessed(self):
        m = MemoryItem(content="test")
        m.mark_accessed()
        assert m.access_count == 1
        assert m.last_accessed > 0

    def test_add_credit(self):
        m = MemoryItem(content="important memory")
        m.add_credit(0.5)
        assert m.importance == 1.5
        assert len(m.credit_history) == 1

    def test_recency_decay(self):
        m = MemoryItem(content="old")
        m.last_accessed = time.time() - 86400 * 10  # 10 days ago
        score_recent = m.recency_score
        assert score_recent < 0.5  # should be low

    def test_retention_score(self):
        m = MemoryItem(content="hot", importance=5.0)
        m.access_count = 10
        m.last_accessed = time.time()
        score = m.retention_score
        assert score > 1.0  # important + hot + frequent

    def test_is_cold(self):
        m = MemoryItem(content="cold")
        m.last_accessed = time.time() - 86400 * 14  # 14 days
        assert m.is_cold

    def test_clamped_importance(self):
        m = MemoryItem(content="test")
        m.add_credit(20.0)
        assert m.importance <= 10.0  # clamped
        m.add_credit(-20.0)
        assert m.importance >= 0.01  # clamped


# ═══ CreditAssigner ═══

class TestCreditAssigner:
    def test_log_access(self):
        ca = CreditAssigner()
        ca.log_access("mem_1")
        ca.log_access("mem_2")
        assert len(ca._task_access_log["default"]) == 2

    def test_assign_credit(self):
        ca = CreditAssigner(alpha=0.2)
        store = {
            "mem_1": MemoryItem(content="大气扩散模型参数设置依据HJ2.2标准"),
            "mem_2": MemoryItem(content="噪声限值依据GB12348"),
        }
        ca.log_access("mem_1", task_id="t1")
        ca.log_access("mem_2", task_id="t1")
        total = ca.assign_credit(
            task_id="t1",
            success=0.95,
            task_output="依据HJ2.2-2018标准，大气扩散模型参数设置...",
            memory_store=store,
        )
        assert total > 0
        assert store["mem_1"].importance > 1.0  # contributed more (higher overlap)

    def test_assign_credit_no_matching(self):
        ca = CreditAssigner(alpha=0.2)
        store = {"mem_x": MemoryItem(content="unrelated content")}
        ca.log_access("mem_x")
        total = ca.assign_credit(
            task_id="t2", success=1.0,
            task_output="completely different topic",
            memory_store=store,
        )
        assert total >= 0

    def test_penalize_failure(self):
        ca = CreditAssigner()
        store = {"mem_f": MemoryItem(content="bad memory")}
        ca.log_access("mem_f")
        penalty = ca.penalize_task_failure(task_id="default", memory_store=store)
        assert store["mem_f"].importance < 1.0

    def test_get_top_contributing(self):
        ca = CreditAssigner()
        store = {
            "a": MemoryItem(content="a", importance=0.5),
            "b": MemoryItem(content="b", importance=2.0),
            "c": MemoryItem(content="c", importance=1.5),
        }
        top = ca.get_top_contributing_memories(2, store)
        assert top[0][0] == "b"


# ═══ RetentionPolicy ═══

class TestRetentionPolicy:
    def test_decide_retain(self):
        rp = RetentionPolicy(keep_threshold=0.5)
        m = MemoryItem(content="vital", importance=5.0)
        m.last_accessed = time.time()
        assert rp.decide(m) == "RETAIN"

    def test_decide_forget(self):
        rp = RetentionPolicy(keep_threshold=5.0)
        m = MemoryItem(content="noise", importance=0.01)
        m.last_accessed = time.time() - 86400 * 30
        assert rp.decide(m) == "FORGET"

    def test_decide_compress(self):
        rp = RetentionPolicy(keep_threshold=3.0, compress_threshold=0.3)
        m = MemoryItem(content="mid", importance=1.0)
        m.last_accessed = time.time() - 86400
        decision = rp.decide(m)
        assert decision in ("COMPRESS", "FORGET")

    def test_apply_policy(self):
        rp = RetentionPolicy(keep_threshold=0.5, max_memories=5)
        store = {}
        for i in range(20):
            m = MemoryItem(content=f"memory {i}")
            m.importance = float(20 - i) / 20  # decreasing importance
            m.last_accessed = time.time()
            store[f"mem_{i}"] = m

        retained, compressed, forgotten = rp.apply_policy(store)
        assert len(retained) <= 5
        assert len(retained) + len(compressed) + len(forgotten) == 20

    def test_policy_stats(self):
        rp = RetentionPolicy()
        store = {"a": MemoryItem(content="a", importance=5.0)}
        store["a"].last_accessed = time.time()
        stats = rp.get_policy_stats(store)
        assert stats["total"] == 1


# ═══ TokenBudget ═══

class TestTokenBudget:
    def test_allocate_simple(self):
        tb = TokenBudget(base_tokens=1024, complexity_bonus=2048)
        total, per = tb.allocate(task_complexity=0.3, num_memories=5)
        assert total > 1024
        assert per > 0

    def test_allocate_max_cap(self):
        tb = TokenBudget(base_tokens=2048, max_tokens=4096)
        total, per = tb.allocate(task_complexity=1.0, num_memories=100)
        assert total <= 4096

    def test_estimate_complexity_simple(self):
        tb = TokenBudget()
        score = tb.estimate_complexity("环评是什么")
        assert score < 0.5

    def test_estimate_complexity_compound(self):
        tb = TokenBudget()
        score = tb.estimate_complexity(
            "环评中大气扩散模型参数与噪声衰减模型的标准化方法对比分析以及验证"
        )
        assert score > 0.5

    def test_format_context_budget(self):
        tb = TokenBudget()
        memories = [
            MemoryItem(content=f"Memory item {i} with some detailed technical content. " * 5)
            for i in range(10)
        ]
        context, tokens = tb.format_context_budget(memories, task_complexity=0.5)
        assert len(context) > 0
        assert tokens > 0


# ═══ MemPOOptimizer ═══

class TestMemPOOptimizer:
    def test_add_and_retrieve(self):
        mempo = MemPOOptimizer(max_memories=100)
        mid = mempo.add_memory("atmospheric dispersion model parameters")
        assert mid.startswith("mem_")
        assert mempo.get_memory(mid).content == "atmospheric dispersion model parameters"

    def test_task_cycle(self):
        mempo = MemPOOptimizer(alpha=0.2, max_memories=100)
        m1 = mempo.add_memory("HJ2.2标准大气扩散模型参数设置方法")
        m2 = mempo.add_memory("GB12348噪声限值标准")

        task = "env_report_task"
        mempo.log_access(m1, task_id=task)
        mempo.log_access(m2, task_id=task)

        total_credit = mempo.on_task_complete(
            task_id=task,
            success=0.9,
            task_output="依据HJ2.2-2018标准设置大气扩散模型参数...",
        )
        assert total_credit > 0
        assert mempo.get_memory(m1).importance > 1.0  # m1 contributed

    def test_task_failure_penalty(self):
        mempo = MemPOOptimizer()
        m = mempo.add_memory("bad context")
        mempo.log_access(m)
        penalty = mempo.on_task_fail()
        assert mempo.get_memory(m).importance < 1.0

    def test_optimize_retention(self):
        mempo = MemPOOptimizer(keep_threshold=3.0, max_memories=50)
        for i in range(20):
            mempo.add_memory(f"memory {i}")

        # Boost first 5 items
        for i in range(5):
            mem_id = f"mem_{i + 1}"
            item = mempo.get_memory(mem_id)
            if item:
                item.importance = 10.0
                item.last_accessed = time.time()

        # Make last 5 items cold (very low importance)
        for i in range(15, 20):
            mem_id = f"mem_{i + 1}"
            item = mempo.get_memory(mem_id)
            if item:
                item.importance = 0.01
                item.last_accessed = 0

        result = mempo.optimize()
        assert result["forgotten"] > 0

    def test_build_context(self):
        mempo = MemPOOptimizer()
        mempo.add_memory("大气扩散模型参数" * 10)
        mempo.add_memory("噪声限值标准GB12348" * 10)
        context, tokens = mempo.build_context(query="大气扩散", max_memories=2)
        assert len(context) > 0

    def test_get_stats(self):
        mempo = MemPOOptimizer()
        mempo.add_memory("test")
        stats = mempo.get_stats()
        assert stats["total_memories"] == 1
        assert "credit" in stats

    def test_auto_optimize_on_overflow(self):
        mempo = MemPOOptimizer(keep_threshold=5.0, max_memories=10)
        for i in range(30):
            mempo.add_memory(f"memory {i}")
        # Under threshold 5.0 and force_forget_overflow, items are cleaned up
        assert len(mempo._memories) <= 20  # was optimized + force-forget

    def test_importance_drift(self):
        """Simulate long-horizon: important items retain high score, noise fades."""
        mempo = MemPOOptimizer(keep_threshold=0.3, max_memories=100)

        mempo.add_memory("vital knowledge" * 10)
        mempo.add_memory("random noise" * 10)

        vital_id = "mem_1"
        noise_id = "mem_2"

        for _ in range(10):
            mempo.log_access(vital_id)
            mempo.on_task_complete(success=0.95, task_output="vital knowledge used")

        time.sleep(0.1)
        # Noise item not accessed → importance stays low
        vital_score = mempo.get_memory(vital_id).retention_score
        noise_score = mempo.get_memory(noise_id).retention_score
        assert vital_score > noise_score
