"""ContextMoE — Human-like Mixture-of-Experts memory with spreading activation.

Models human memory architecture:
  🔥 Hot Expert   → Working memory (7±2 chunks, current conversation)
  🌤️  Warm Expert  → Short-term memory (same-day, recent tasks)
  ❄️ Cold Expert   → Long-term memory (domain-bucketed, fading)
  🧊 Deep Expert   → Permanent knowledge (preferences, patterns, skills)
  ⚡ Flash Expert  → Reflex cache (high-frequency patterns, zero-latency)

Key innovations:
  1. MoE Router: dynamically weights experts per query type
  2. Spreading Activation: recalling one memory boosts related memories
  3. Consolidation Pipeline: Warm→Cold→Deep with usage-based promotion
  4. Forgetting Curve: Ebbinghaus-inspired decay with access refresh
  5. Reference Pointers: OpenWiki-style linked memory with file/concept/relationship refs
  6. KV Allocation (Opus 4.7-inspired): per-block token budget allocation + mid-section boost

Integration:
  moe = get_context_moe()
  result = await moe.query(message, task_type)  # → {hot, warm, cold, deep, flash, activation}
  await moe.consolidate()                         # periodic memory consolidation

Replaces: continuous_consciousness.py (now deprecated)
Bridges: StructMemory, FluidCollective, SemanticDedupCache, CrossSessionBridge
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

from loguru import logger

STATE_FILE = Path(".livingtree/context_moe_state.json")


# ═══ Expert Types ═════════════════════════════════════════════════


class ExpertLayer(StrEnum):
    FLASH = "flash"   # Reflex cache, ~0ms
    HOT = "hot"       # Working memory, ~1ms
    WARM = "warm"     # Short-term memory, ~5ms
    COLD = "cold"     # Long-term memory, ~20ms
    DEEP = "deep"     # Permanent knowledge, ~10ms


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class ReferencePointer:
    """OpenWiki-style linked reference to another memory or resource."""
    ref_type: str     # "memory" | "file" | "concept" | "decision" | "url"
    target_id: str    # block_id, file_path, concept_name
    label: str = ""   # human-readable label
    relevance: float = 0.5  # 0.0-1.0


@dataclass
class MemoryBlock:
    """A compressed memory unit stored in the MoE system.

    v2.5 Opus 4.7 KV-Allocation: kv_allocation_weight controls how many
    context tokens this block receives when injected. Higher weight = more
    tokens preserved (less compression). position_index tracks where in the
    conversation this block originated, enabling mid-section decay compensation.
    """
    id: str
    content: str            # Compressed summary
    original_length: int    # Chars before compression
    layer: ExpertLayer      # Current storage layer
    timestamp: float
    last_accessed: float
    access_count: int = 0
    relevance_score: float = 0.5   # Current MoE relevance
    topics: list[str] = field(default_factory=list)
    task_type: str = "general"
    pointers: list[ReferencePointer] = field(default_factory=list)
    related_blocks: list[str] = field(default_factory=list)  # Activation graph edges
    consolidation_count: int = 0  # How many times consolidated deeper
    prominence: float = 0.5       # Overall importance score
    decay_factor: float = 1.0     # Ebbinghaus decay: starts at 1.0, decays over time
    kv_allocation_weight: float = 0.5   # Token budget allocation (0=suppress, 1=preserve fully)
    position_index: int = -1            # Turn index in conversation (-1=unknown)
    task_criticality: float = 0.5       # How critical this block is to current task (0-1)


@dataclass
class ExpertResult:
    """Query result from a single expert layer."""
    layer: ExpertLayer
    blocks: list[MemoryBlock]
    weight: float  # Router-assigned weight
    latency_ms: float


@dataclass
class MoEQueryResult:
    """Complete MoE query result with all expert contributions."""
    results: list[ExpertResult]
    activation_spread: list[str]  # Block IDs activated via spreading
    total_weight: float
    hot: list[MemoryBlock]
    warm: list[MemoryBlock]
    cold: list[MemoryBlock]
    deep: list[MemoryBlock]
    flash: list[MemoryBlock]


# ═══ Task Boundary Detector ═══════════════════════════════════════


class TaskBoundaryDetector:
    """Detects natural task boundaries from conversation signals."""

    CLOSING_PHRASES = [
        "好的谢谢", "谢谢", "感谢", "拜拜", "再见", "下次见",
        "没问题了", "可以了", "就这样", "清楚了", "明白了",
        "thanks", "thank you", "bye", "goodbye", "see you",
        "that's all", "got it", "understood",
        "完美", "搞定", "done", "先这样", "到此为止", "收工",
    ]
    SILENCE_THRESHOLD_SECONDS = 300
    TOPIC_SHIFT_JACCARD = 0.15

    def detect(self, message: str, time_since_last: float,
               recent_topics: set[str]) -> tuple[bool, str, float]:
        msg_lower = message.lower().strip()
        for phrase in self.CLOSING_PHRASES:
            if phrase in msg_lower:
                return True, f"closing:{phrase}", 0.9
        if time_since_last > self.SILENCE_THRESHOLD_SECONDS:
            conf = 0.8 if time_since_last > self.SILENCE_THRESHOLD_SECONDS * 2 else 0.5
            return True, f"silence:{int(time_since_last)}s", conf
        if recent_topics and message:
            current = set(msg_lower.split())
            if current and recent_topics:
                overlap = len(current & recent_topics) / max(len(current | recent_topics), 1)
                if overlap < self.TOPIC_SHIFT_JACCARD:
                    return True, f"topic_shift:{overlap:.2f}", 0.4
        return False, "", 0.0


# ═══ MoE Router ════════════════════════════════════════════════════


class MoERouter:
    """Dynamic expert weight assignment based on query characteristics."""

    # Base weights [flash, hot, warm, cold, deep]
    DEFAULT_WEIGHTS = [0.05, 0.30, 0.35, 0.25, 0.05]

    def route(self, query: str, time_since_last: float,
              active_topics: set[str]) -> list[float]:
        """Return expert weights [flash, hot, warm, cold, deep] based on query."""
        w = list(self.DEFAULT_WEIGHTS)
        q = query.lower()
        qlen = len(query)

        # Flash reflex patterns → boost flash
        reflex_patterns = ["继续", "之前那个", "刚才", "上一个", "continue", "previous",
                           "再试", "retry", "接着", "然后呢", "还有吗"]
        if any(p in q for p in reflex_patterns):
            w[0] = 0.35  # Flash ↑
            w[1] = 0.40  # Hot ↑
            w[2] = 0.15  # Warm ↓
            w[3] = 0.08  # Cold ↓
            w[4] = 0.02  # Deep → minimal

        # New topic / exploration → boost cold + warm
        elif qlen > 30 and time_since_last > 120:
            w[0] = 0.02
            w[1] = 0.18
            w[2] = 0.30  # Warm ↑
            w[3] = 0.35  # Cold ↑
            w[4] = 0.15  # Deep ↑

        # Very short → hot dominant
        elif qlen < 10:
            w[0] = 0.10
            w[1] = 0.55  # Hot dominant
            w[2] = 0.25
            w[3] = 0.08
            w[4] = 0.02

        # Knowledge question → cold + deep
        elif any(k in q for k in ["解释", "什么是", "如何", "怎么", "原理", "why", "how", "explain"]):
            w[0] = 0.02
            w[1] = 0.15
            w[2] = 0.25
            w[3] = 0.38  # Cold ↑
            w[4] = 0.20  # Deep ↑

        # Normalize
        total = sum(w)
        return [round(x / total, 4) for x in w]


# ═══ Spreading Activation ═════════════════════════════════════════


class SpreadingActivation:
    """When a memory is retrieved, boost related memories.

    Models neural associative networks: activating node A spreads
    activation to connected nodes B, C, D with diminishing strength.
    """

    ACTIVATION_DECAY = 0.6    # Each hop loses 40% strength
    MAX_HOPS = 2              # Maximum activation spread hops

    def spread(self, seed_blocks: list[MemoryBlock],
               all_blocks: dict[str, MemoryBlock],
               boost: float = 0.3) -> list[str]:
        """Spread activation from seed blocks to related blocks.

        Returns list of block IDs that received activation boost.
        """
        activated: set[str] = set()
        queue: list[tuple[str, float]] = []

        # Seed: all seed blocks get activation
        for b in seed_blocks:
            queue.append((b.id, boost))

        for _ in range(self.MAX_HOPS):
            next_queue: list[tuple[str, float]] = []
            for block_id, strength in queue:
                if block_id in activated:
                    continue
                activated.add(block_id)
                block = all_blocks.get(block_id)
                if not block:
                    continue

                # Spread to related blocks with decay
                for related_id in block.related_blocks:
                    if related_id not in activated:
                        decayed = strength * self.ACTIVATION_DECAY
                        if decayed > 0.05:  # Minimum threshold
                            next_queue.append((related_id, decayed))
                            rb = all_blocks.get(related_id)
                            if rb:
                                rb.relevance_score = min(1.0, rb.relevance_score + decayed)

                # Spread via shared topics
                if block.topics:
                    for bid, b in all_blocks.items():
                        if bid not in activated and bid != block_id:
                            shared = set(block.topics) & set(b.topics)
                            if shared:
                                topic_boost = strength * 0.3 * len(shared) / max(len(block.topics), 1)
                                if topic_boost > 0.03:
                                    next_queue.append((bid, topic_boost))
                                    b.relevance_score = min(1.0, b.relevance_score + topic_boost)
            queue = next_queue

        return list(activated)


# ═══ ContextMoE — Main Engine ═════════════════════════════════════


class ContextMoE:
    """Human-like Mixture-of-Experts context memory."""

    _instance: Optional["ContextMoE"] = None
    _instance_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "ContextMoE":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = ContextMoE()
        return cls._instance

    def __init__(self, session_id: str = "perpetual"):
        self.session_id = session_id
        self._lock = asyncio.Lock()   # Protects _hot/_warm/_cold mutations
        self._router = MoERouter()
        self._detector = TaskBoundaryDetector()
        self._activation = SpreadingActivation()

        # 🔥 Hot: Working memory (current conversation, 7±2 turns)
        self._hot: list[MemoryBlock] = []
        self._hot_max = 14  # ~7 user+assistant pairs

        # 🌤️ Warm: Short-term memory (same-day archived tasks)
        self._warm: dict[str, MemoryBlock] = {}
        self._warm_max = 50

        # ❄️ Cold: Long-term memory (domain-bucketed, fading)
        self._cold: dict[str, MemoryBlock] = {}
        self._cold_max = 200

        # 🧊 Deep: Permanent knowledge (preferences, patterns, skills)
        self._deep: dict[str, dict] = {}   # {key: {value, ts, source}}

        # ⚡ Flash: Reflex cache (high-frequency shortcuts)
        self._flash: dict[str, str] = {}    # {pattern_hash: block_id}

        # Global state
        self._recent_topics: set[str] = set()
        self._last_message_time: float = 0.0
        self._task_count: int = 0
        self._total_messages: int = 0
        self._last_consolidation: float = 0.0

        # Activation graph
        self._activation_graph: dict[str, list[str]] = defaultdict(list)

        # Stats
        self._query_count = 0
        self._activation_spreads = 0
        self._consolidations = 0

        self._load()

    # ── Main Query Pipeline ───────────────────────────────────────

    async def query(self, message: str, task_type: str = "general",
                    hot_context: list[dict] = None) -> MoEQueryResult:
        """Route query through MoE experts. Per-session isolated via get_context_moe(sid)."""
        now = time.time()
        self._query_count += 1
        time_since_last = now - self._last_message_time if self._last_message_time else 0
        self._last_message_time = now
        self._total_messages += 1

        # 1. Detect task boundary
        is_boundary, reason, confidence = self._detector.detect(
            message, time_since_last, self._recent_topics,
        )
        if is_boundary and confidence > 0.5:
            await self._archive_to_warm(reason)
            logger.info(f"ContextMoE: boundary detected — {reason}")

        # 2. Update hot context
        if hot_context:
            await self._update_hot(hot_context, task_type)

        # 3. Update topics
        self._recent_topics |= set(message.lower().split()[:20])

        # 4. MoE routing → get expert weights
        weights = self._router.route(message, time_since_last, self._recent_topics)

        # 5. Query each expert
        t0 = time.time()
        flash_result = self._query_flash(message)
        flash_lat = (time.time() - t0) * 1000

        t0 = time.time()
        async with self._lock:
            hot_result = self._query_hot()
        hot_lat = (time.time() - t0) * 1000

        t0 = time.time()
        warm_result = self._query_warm(message, task_type)
        warm_lat = (time.time() - t0) * 1000

        t0 = time.time()
        cold_result = self._query_cold(message, task_type)
        cold_lat = (time.time() - t0) * 1000

        t0 = time.time()
        deep_result = self._query_deep(message, task_type)
        deep_lat = (time.time() - t0) * 1000

        # 6. Spreading activation: boost related memories
        seed_blocks = hot_result + warm_result + cold_result
        all_blocks = {**self._warm, **self._cold}
        activated_ids = self._activation.spread(seed_blocks, all_blocks)
        self._activation_spreads += len(activated_ids)

        # 7. Build result
        result = MoEQueryResult(
        results=[
        ExpertResult(ExpertLayer.FLASH, flash_result, weights[0], flash_lat),
        ExpertResult(ExpertLayer.HOT, hot_result, weights[1], hot_lat),
        ExpertResult(ExpertLayer.WARM, warm_result, weights[2], warm_lat),
        ExpertResult(ExpertLayer.COLD, cold_result, weights[3], cold_lat),
        ExpertResult(ExpertLayer.DEEP, deep_result, weights[4], deep_lat),
        ],
        activation_spread=activated_ids,
        total_weight=sum(weights),
        hot=hot_result,
        warm=warm_result,
        cold=cold_result,
        deep=deep_result,
        flash=flash_result,
        )

        # 8. Build enriched context string
        return result

    def build_enriched_message(self, query: str, result: MoEQueryResult,
                                total_budget: int = 3000, current_turn: int = 0) -> str:
        """Build human-readable enriched context from MoE result.

        v2.5 Opus 4.7 KV-Allocation: uses allocate_context_budget() to
        dynamically distribute token budget across memory blocks instead
        of uniform truncation.
        """
        if not result.hot and not result.warm and not result.cold and not result.deep:
            return query

        query_terms = set(query.lower().split())

        # Score task-criticality for all blocks
        all_candidates: list[MemoryBlock] = []
        for b in result.hot:
            self.score_task_criticality(b, query_terms)
            b.position_index = current_turn
            all_candidates.append(b)
        for b in result.warm + result.cold + result.deep:
            self.score_task_criticality(b, query_terms)
            all_candidates.append(b)

        memory_context = self.allocate_context_budget(
            all_candidates, total_budget=total_budget, current_turn=current_turn,
        )

        if not memory_context:
            return query

        return f"[相关记忆]\n{memory_context}\n\n---\n当前问题: {query}"

    # ── Expert Queries ────────────────────────────────────────────

    def _query_flash(self, query: str) -> list[MemoryBlock]:
        """⚡ Flash: pattern-hash lookup, zero-latency."""
        h = hashlib.md5(query.lower().strip()[:60].encode()).hexdigest()[:8]
        block_id = self._flash.get(h)
        if block_id:
            block = self._warm.get(block_id) or self._cold.get(block_id)
            if block:
                block.last_accessed = time.time()
                block.access_count += 1
                return [block]
        return []

    def _query_hot(self) -> list[MemoryBlock]:
        """🔥 Hot: return current working memory."""
        return self._hot[-7:]  # 7±2 rule

    def _query_warm(self, query: str, task_type: str) -> list[MemoryBlock]:
        """🌤️ Warm: short-term semantic search with TriAttention-inspired center similarity."""
        query_words = set(query.lower().split())
        # Build query topic center from query words
        query_topics = {w for w in query_words if len(w) > 2}

        scored = []
        for b in self._warm.values():
            block_words = set(b.content.lower().split())
            overlap = len(query_words & block_words) / max(len(query_words | block_words), 1)

            # TriAttention: topic center similarity — topics are semantic centers
            topic_overlap = 0.0
            if b.topics and query_topics:
                shared = len(set(str(t) for t in b.topics) & query_topics)
                topic_overlap = shared / max(len(b.topics), 1)

            task_match = 1.0 if b.task_type == task_type else 0.3
            hours_ago = (time.time() - b.last_accessed) / 3600
            recency = math.exp(-hours_ago / 12)

            # Enhanced scoring: topic center gets extra weight (TriAttention insight)
            score = overlap * 0.30 + topic_overlap * 0.25 + task_match * 0.25 + recency * 0.20
            if score > 0.08:
                scored.append((b, score))

        scored.sort(key=lambda x: -x[1])
        for b, _ in scored[:3]:
            b.last_accessed = time.time()
            b.access_count += 1
        return [b for b, _ in scored[:3]]

    def _query_cold(self, query: str, task_type: str) -> list[MemoryBlock]:
        """❄️ Cold: domain-bucketed long-term memory with center similarity + forgetting curve."""
        query_words = set(query.lower().split())
        query_topics = {w for w in query_words if len(w) > 2}

        scored = []
        for b in self._cold.values():
            days_since_access = (time.time() - b.last_accessed) / 86400
            b.decay_factor = math.exp(-days_since_access / 30)

            block_words = set(b.content.lower().split())
            overlap = len(query_words & block_words) / max(len(query_words | block_words), 1)

            # TriAttention: topic center similarity
            topic_overlap = 0.0
            if b.topics and query_topics:
                shared = len(set(str(t) for t in b.topics) & query_topics)
                topic_overlap = shared / max(len(b.topics), 1)

            task_match = 1.0 if b.task_type == task_type else 0.3

            # Center-aware scoring: topic overlap weighted highly for cold memory
            score = (overlap * 0.25 + topic_overlap * 0.25 +
                    task_match * 0.20 + b.decay_factor * 0.15 + b.prominence * 0.15)
            if score > 0.08:
                scored.append((b, score))

        scored.sort(key=lambda x: -x[1])
        for b, _ in scored[:3]:
            b.last_accessed = time.time()
            b.access_count += 1
            b.decay_factor = 1.0  # Access resets decay
        return [b for b, _ in scored[:3]]

    def _query_deep(self, query: str, task_type: str) -> list[MemoryBlock]:
        """🧊 Deep: permanent structured knowledge."""
        results = []
        ql = query.lower()
        for key, entry in self._deep.items():
            if isinstance(entry, dict) and key.lower() in ql:
                results.append(MemoryBlock(
                    id=f"deep:{key}",
                    content=f"{key}: {entry.get('value', '')}",
                    original_length=len(str(entry)),
                    layer=ExpertLayer.DEEP,
                    timestamp=entry.get("ts", 0),
                    last_accessed=time.time(),
                    task_type="persistent",
                    prominence=1.0,
                ))
        return results

    # ── Memory Operations ─────────────────────────────────────────

    async def _update_hot(self, messages: list[dict], task_type: str) -> None:
        """Update working memory from recent messages."""
        for m in messages[-4:]:
            content = str(m.get("content", ""))[:500]
            if not content:
                continue
            block = MemoryBlock(
                id=f"hot_{self._total_messages}_{int(time.time())}",
                content=content,
                original_length=len(content),
                layer=ExpertLayer.HOT,
                timestamp=time.time(),
                last_accessed=time.time(),
                task_type=task_type,
            )
            # DataValueDensity: only store high-density memories
            try:
                from .data_value_density import get_data_value_density
                dvd = get_data_value_density()
                density = dvd.assess(content).total_score
                if density < 0.2:
                    continue  # Skip low-value noise
                block.prominence = density  # Store density as prominence
            except Exception:
                pass
            self._hot.append(block)

        # Maintain 7±2 capacity — evict lowest-density first
        if len(self._hot) > self._hot_max:
            self._hot.sort(key=lambda b: getattr(b, 'prominence', 0.5))
            overflow = self._hot[:-self._hot_max]
            for b in overflow:
                b.layer = ExpertLayer.WARM
                b.id = f"warm_overflow_{int(time.time())}_{hash(b.content) & 0xFFFF}"
                self._warm[b.id] = b
            self._hot = self._hot[-self._hot_max:]

    async def _archive_to_warm(self, reason: str) -> None:
        """Archive completed hot context to warm short-term memory."""
        if not self._hot:
            return

        self._task_count += 1
        task_id = f"task_{self._task_count}_{int(time.time())}"

        # Compress hot blocks into a single warm block
        summary = " | ".join(b.content[:150] for b in self._hot[-10:])
        if len(summary) > 2000:
            summary = summary[:2000] + "..."

        # Extract pointers
        pointers = []
        for b in self._hot[-5:]:
            if any(k in b.content.lower() for k in ["file", "文件", "path", "路径"]):
                pointers.append(ReferencePointer(
                    ref_type="memory", target_id=b.id, label="关键对话",
                ))

        block = MemoryBlock(
            id=task_id,
            content=summary,
            original_length=sum(b.original_length for b in self._hot),
            layer=ExpertLayer.WARM,
            timestamp=time.time(),
            last_accessed=time.time(),
            topics=list(self._recent_topics)[:15],
            task_type=self._hot[-1].task_type if self._hot else "general",
            pointers=pointers,
        )
        self._warm[task_id] = block

        # Update flash cache with closing phrase→task_id
        self._flash[hashlib.md5(reason.encode()).hexdigest()[:8]] = task_id

        # Link related blocks via activation graph
        for existing_id in list(self._warm.keys())[-5:]:
            if existing_id != task_id:
                self._activation_graph[task_id].append(existing_id)
                self._activation_graph[existing_id].append(task_id)
                eb = self._warm.get(existing_id)
                if eb:
                    eb.related_blocks.append(task_id)

        # Clear hot
        self._hot = []
        self._recent_topics.clear()

        logger.info(
            f"ContextMoE: archived task #{self._task_count} → warm "
            f"({block.original_length}→{len(summary)} chars)"
        )

    async def consolidate(self) -> int:
        """Periodic consolidation: Warm→Cold, Cold→Deep, prune forgotten."""
        self._consolidations += 1
        self._last_consolidation = time.time()
        moved = 0

        # Warm → Cold: blocks older than 24h AND accessed <3 times
        for bid in list(self._warm.keys()):
            b = self._warm[bid]
            age_hours = (time.time() - b.timestamp) / 3600
            if age_hours > 24 and b.access_count < 3:
                b.layer = ExpertLayer.COLD
                b.consolidation_count += 1
                b.decay_factor = 0.8
                # Summarize further
                if len(b.content) > 600:
                    b.content = b.content[:600] + "..."
                    b.pointers.append(ReferencePointer(
                        ref_type="memory", target_id=bid,
                        label="原始记录", relevance=0.5,
                    ))
                self._cold[bid] = b
                del self._warm[bid]
                moved += 1

        # Cold → Deep: blocks with >5 accesses AND prominence > 0.7
        for bid in list(self._cold.keys()):
            b = self._cold[bid]
            if b.access_count >= 5 and b.prominence > 0.7:
                # Extract as permanent knowledge
                key = f"pattern:{b.task_type}:{b.topics[0] if b.topics else 'general'}"
                self._deep[key] = {
                    "value": b.content[:300],
                    "ts": time.time(),
                    "source": bid,
                }
                moved += 1

        # Prune forgotten: cold blocks with decay < 0.05 AND access_count < 2
        pruned = 0
        for bid in list(self._cold.keys()):
            b = self._cold[bid]
            if b.decay_factor < 0.05 and b.access_count < 2:
                del self._cold[bid]
                pruned += 1

        # Capacity control
        if len(self._warm) > self._warm_max:
            excess = sorted(self._warm.keys(),
                          key=lambda k: self._warm[k].last_accessed)[:len(self._warm) - self._warm_max]
            for k in excess:
                b = self._warm.pop(k)
                b.layer = ExpertLayer.COLD
                self._cold[k] = b
                moved += 1

        if len(self._cold) > self._cold_max:
            excess = sorted(self._cold.keys(),
                          key=lambda k: (self._cold[k].decay_factor, -self._cold[k].access_count))[:len(self._cold) - self._cold_max]
            for k in excess:
                del self._cold[k]
                pruned += 1

        if moved or pruned:
            self._save()
            logger.info(
                f"ContextMoE consolidate: {moved} moved, {pruned} pruned "
                f"(warm={len(self._warm)}, cold={len(self._cold)}, deep={len(self._deep)})"
            )

        return moved + pruned

    def inject_deep(self, key: str, value: str, source: str = "auto") -> None:
        """Inject permanent knowledge into the Deep layer."""
        self._deep[key] = {"value": value, "ts": time.time(), "source": source}

    def get_deep(self, key: str) -> Optional[str]:
        entry = self._deep.get(key)
        return entry["value"] if entry else None

    # ── Opus 4.7 KV Allocation ──────────────────────────────────────

    def allocate_context_budget(
        self, blocks: list[MemoryBlock], total_budget: int = 3000,
        current_turn: int = 0,
    ) -> str:
        """Dynamically allocate token budget across blocks per Opus 4.7 KV weighting.

        Each block gets tokens proportional to:
        kv_allocation_score = relevance × 0.35 + layer_weight × 0.25
                            + task_criticality × 0.25 + mid_section_boost × 0.15

        Mid-section boost: blocks from conversation turns 5-15 that have high
        task-criticality get a 1.5x multiplier to combat the natural decay of
        middle-conversation information (Claude Opus 4.7's key innovation).

        v2.6 ALiBi Slopes: pos_decay now uses per-expert geometric slopes.
        FLASH (1/2) rapidly discounts position for transient blocks → favors recency.
        DEEP (1/256) barely decays position → permanent knowledge is always relevant.
        This mirrors ALiBi's per-head slope distribution across memory layers.
        """
        if not blocks:
            return ""

        layer_weight_map = {
            ExpertLayer.FLASH: 0.5, ExpertLayer.HOT: 0.9,
            ExpertLayer.WARM: 0.6, ExpertLayer.COLD: 0.4, ExpertLayer.DEEP: 0.7,
        }
        alibi_slopes = {
            ExpertLayer.FLASH: 0.5, ExpertLayer.HOT: 0.25,
            ExpertLayer.WARM: 0.125, ExpertLayer.COLD: 0.0625, ExpertLayer.DEEP: 0.015625,
        }

        scored_blocks: list[tuple[MemoryBlock, float]] = []
        for b in blocks:
            lw = layer_weight_map.get(b.layer, 0.3)

            mid_boost = 1.0
            if b.position_index >= 0:
                recency_gap = current_turn - b.position_index if current_turn > 0 else 0
                slope = alibi_slopes.get(b.layer, 0.1)
                pos_decay = max(0.3, 1.0 - recency_gap * slope)
                if 5 <= b.position_index <= 15 and b.task_criticality > 0.6:
                    mid_boost = 1.5
            else:
                pos_decay = 0.6

            allocation_score = (
                b.relevance_score * 0.35
                + lw * 0.25
                + b.task_criticality * 0.25
                + mid_boost * 0.15
            ) * pos_decay
            b.kv_allocation_weight = round(allocation_score, 4)
            scored_blocks.append((b, allocation_score))

        total_score = sum(s for _, s in scored_blocks) or 1.0

        parts: list[str] = []
        for b, score in scored_blocks:
            budget = max(50, int(total_budget * score / total_score))
            now = time.time()
            age_text = ""
            if b.timestamp > 0:
                age_days = int((now - b.timestamp) / 86400)
                if age_days > 0:
                    age_text = f"[{age_days}d前] "
            content = b.content[:budget]
            parts.append(f"{age_text}{content}")

        return "\n".join(parts)

    def score_task_criticality(self, block: MemoryBlock,
                                query_terms: set[str]) -> float:
        """Score how critical a memory block is to the current task.

        High task_criticality when:
        - Block contains decision markers (决定, decided, selected)
        - Block shares many terms with the query
        - Block was accessed multiple times (indicates persistent relevance)
        - Block has high prominence score
        """
        score = 0.3
        content_lower = block.content.lower()
        decision_markers = [
            "决定", "选择", "最终", "采用", "确认",
            "decided", "chose", "final", "confirmed", "selected",
            "结论", "conclusion", "方案", "设计", "architecture",
        ]
        for m in decision_markers:
            if m in content_lower:
                score += 0.1
                break

        if block.topics and query_terms:
            shared = len(set(block.topics) & query_terms)
            score += min(0.3, shared * 0.08)

        score += min(0.2, block.access_count * 0.05)
        score += block.prominence * 0.2

        block.task_criticality = round(min(1.0, score), 4)
        return block.task_criticality

    # ── Persistence ────────────────────────────────────────────────

    def _save(self):
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "task_count": self._task_count,
                "total_messages": self._total_messages,
                "last_consolidation": self._last_consolidation,
                "hot": [{
                    "content": b.content, "original_length": b.original_length,
                    "timestamp": b.timestamp, "task_type": b.task_type,
                    "prominence": b.prominence,
                } for b in self._hot],
                "recent_topics": list(self._recent_topics),
                "warm": {
                    bid: {
                        "content": b.content, "original_length": b.original_length,
                        "timestamp": b.timestamp, "last_accessed": b.last_accessed,
                        "access_count": b.access_count, "topics": b.topics,
                        "task_type": b.task_type, "prominence": b.prominence,
                        "decay_factor": b.decay_factor, "consolidation_count": b.consolidation_count,
                    }
                    for bid, b in self._warm.items()
                },
                "cold": {
                    bid: {
                        "content": b.content, "original_length": b.original_length,
                        "timestamp": b.timestamp, "last_accessed": b.last_accessed,
                        "access_count": b.access_count, "topics": b.topics,
                        "task_type": b.task_type, "prominence": b.prominence,
                        "decay_factor": b.decay_factor, "consolidation_count": b.consolidation_count,
                    }
                    for bid, b in self._cold.items()
                },
                "deep": self._deep,
                "flash": self._flash,
                "activation_graph": dict(self._activation_graph),
            }
            STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"ContextMoE save: {e}")

    def _load(self):
        try:
            if STATE_FILE.exists():
                data = json.loads(STATE_FILE.read_text())
                self._task_count = data.get("task_count", 0)
                self._total_messages = data.get("total_messages", 0)
                self._last_consolidation = data.get("last_consolidation", 0)
                self._deep = data.get("deep", {})
                self._flash = data.get("flash", {})
                self._recent_topics = set(data.get("recent_topics", []))
                for bd in data.get("hot", []):
                    self._hot.append(MemoryBlock(
                        id=f"hot_restored_{bd.get('timestamp',0)}",
                        layer=ExpertLayer.HOT,
                        content=bd.get("content",""),
                        original_length=bd.get("original_length",0),
                        timestamp=bd.get("timestamp",0),
                        task_type=bd.get("task_type","general"),
                        prominence=bd.get("prominence",0.5),
                        last_accessed=time.time(),
                    ))
                self._activation_graph = defaultdict(list, data.get("activation_graph", {}))
                for bid, bd in data.get("warm", {}).items():
                    self._warm[bid] = MemoryBlock(
                        id=bid, layer=ExpertLayer.WARM, **{
                            k: v for k, v in bd.items()
                            if k in ("content","original_length","timestamp","last_accessed",
                                     "access_count","topics","task_type","prominence",
                                     "decay_factor","consolidation_count")
                        })
                for bid, bd in data.get("cold", {}).items():
                    self._cold[bid] = MemoryBlock(
                        id=bid, layer=ExpertLayer.COLD, **{
                            k: v for k, v in bd.items()
                            if k in ("content","original_length","timestamp","last_accessed",
                                     "access_count","topics","task_type","prominence",
                                     "decay_factor","consolidation_count")
                        })
                logger.info(
                    f"ContextMoE: loaded warm={len(self._warm)} cold={len(self._cold)} "
                    f"deep={len(self._deep)} flash={len(self._flash)}"
                )
        except Exception as e:
            logger.debug(f"ContextMoE load: {e}")

    def state_report(self) -> dict:
        return {
            "total_messages": self._total_messages,
            "task_count": self._task_count,
            "hot_blocks": len(self._hot),
            "warm_blocks": len(self._warm),
            "cold_blocks": len(self._cold),
            "deep_entries": len(self._deep),
            "flash_entries": len(self._flash),
            "activation_edges": sum(len(v) for v in self._activation_graph.values()),
            "consolidations": self._consolidations,
            "activation_spreads": self._activation_spreads,
            "queries": self._query_count,
        }


# ═══ Session-Multiplexed Instance Pool ════════════════════════════

_moe_sessions: dict[str, ContextMoE] = {}
_moe_lock = asyncio.Lock()


async def get_context_moe(session_id: str = "perpetual") -> ContextMoE:
    """Get or create a ContextMoE instance for a specific session.

    Each terminal/session gets its own ContextMoE with isolated working memory
    (_hot, _recent_topics) but shared long-term memory (_warm, _cold, _deep).

    For true multi-terminal safety, derive session_id from request headers
    (X-Session-Id, Authorization token hash, or client IP + User-Agent hash).
    """
    if session_id in _moe_sessions:
        return _moe_sessions[session_id]
    async with _moe_lock:
        if session_id in _moe_sessions:
            return _moe_sessions[session_id]
        moe = ContextMoE(session_id)
        _moe_sessions[session_id] = moe
        # Purge old sessions
        if len(_moe_sessions) > 100:
            oldest = sorted(_moe_sessions.keys(),
                           key=lambda k: _moe_sessions[k]._last_message_time)[:10]
            for k in oldest:
                del _moe_sessions[k]
        return moe


__all__ = [
    "ContextMoE", "MoERouter", "SpreadingActivation",
    "TaskBoundaryDetector", "ExpertLayer",
    "MemoryBlock", "MoEQueryResult", "ExpertResult",
    "ReferencePointer", "get_context_moe",
]
