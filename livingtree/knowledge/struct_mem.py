"""StructMem — Structured Hierarchical Memory for Long-Horizon LLM Agents.

Implements the StructMem framework (ACL 2026, ZJU + Ant Group):
- Event-Level Binding: dual-perspective extraction (FACT + RELATION)
- Cross-Event Consolidation: batch semantic synthesis on time triggers
- Temporal Anchoring: all entries timestamped for temporal reasoning
- Natural language storage: no rigid triplets, avoids entity resolution overhead

Configured for LivingTree: uses LivingTree's DualModelConsciousness for LLM
calls and VectorStore for semantic retrieval. Flash model handles extraction
(cheap), pro model handles consolidation (quality).

Usage:
    mem = StructMemory(hub.world)
    
    # Auto-called after every LifeEngine cycle:
    await mem.bind_events(session_id, messages, timestamp)
    
    # Auto-triggered when buffer > time_threshold:
    await mem.consolidate_if_needed()
    
    # Query for context injection:
    entries, synthesis = await mem.retrieve_for_query(query, top_k=60, n_synthesis=5)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger


@dataclass
class EventEntry:
    """A single memory entry with dual-perspective content."""
    id: str
    session_id: str
    timestamp: str
    role: str
    content: str
    fact_perspective: str = ""
    rel_perspective: str = ""
    embedding: list[float] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def text_for_retrieval(self) -> str:
        parts = [self.fact_perspective]
        if self.rel_perspective:
            parts.append(self.rel_perspective)
        return " ".join(parts) or self.content[:200]


@dataclass
class SynthesisBlock:
    """A consolidated cross-event synthesis block."""
    id: str
    timestamp: str
    content: str
    source_entries: list[str] = field(default_factory=list)
    session_ids: list[str] = field(default_factory=list)

    def text_for_retrieval(self) -> str:
        return self.content


@dataclass
class MemoryBuffer:
    """Buffered unconsolidated entries since last consolidation."""
    entries: list[EventEntry] = field(default_factory=list)
    first_timestamp: str = ""
    last_timestamp: str = ""

    def add(self, entry: EventEntry) -> None:
        self.entries.append(entry)
        if not self.first_timestamp:
            self.first_timestamp = entry.timestamp
        self.last_timestamp = entry.timestamp

    def elapsed_seconds(self) -> float:
        if not self.first_timestamp:
            return 0.0
        try:
            first = datetime.fromisoformat(self.first_timestamp)
            return (datetime.now(timezone.utc) - first).total_seconds()
        except Exception:
            return 0.0

    def clear(self) -> None:
        self.entries.clear()
        self.first_timestamp = ""
        self.last_timestamp = ""


# Dual-perspective extraction prompts (from StructMem paper, adapted for LivingTree)
FACT_EXTRACT_PROMPT = """Extract factual events from the following conversation utterance.
Focus on objective, verifiable facts: who did what, when, where, what was said.

Rules:
- Output one fact per line, prefixed with "- "
- Keep each fact under 80 words
- Use the speaker's actual name (not "User" or "AI")
- Only include facts explicitly stated in the utterance
- Do not infer or speculate

Utterance: {utterance}

Factual entries:"""


REL_EXTRACT_PROMPT = """Extract relational dynamics from the following conversation utterance.
Focus on: interpersonal dynamics, causal influences, emotional tone shifts,
preference changes, temporal dependencies, and decision-making context.

Rules:
- Output one relation per line, prefixed with "- "
- Keep each relation under 60 words
- Describe how this utterance relates to the broader conversation
- Note any changes in: relationship, goal, preference, emotional state
- Only include relations grounded in the utterance

Utterance: {utterance}

Relational entries:"""


CONSOLIDATION_PROMPT = """Synthesize cross-event connections from the following temporally related events.

Below are two groups:
[BUFFER EVENTS] — recent unconsolidated events
[HISTORICAL EVENTS] — semantically similar past events retrieved from memory

Identify connections across time that reveal:
1. Causal chains (X caused Y)
2. Preference evolution (user started wanting X, now wants Y)
3. Repeated patterns (similar situations that recur)
4. Unresolved threads (questions or tasks left incomplete)
5. Temporal progressions (how something changed over time)

Rules:
- Be specific: cite which events you're connecting
- Only assert connections supported by both event groups
- Format: "- [connection type]: specific description"
- Limit to 5-8 synthesized connections
- If no meaningful connections exist, say "NO_CONNECTIONS"

{context}

Cross-event synthesis:"""


class StructMemory:
    """Hierarchical memory with dual-perspective binding and batch consolidation."""

    CONSOLIDATION_THRESHOLD_SECONDS = 300  # 5 minutes
    SEMANTIC_SEEDS = 15
    DEFAULT_RETRIEVAL_TOP_K = 60
    DEFAULT_SYNTHESIS_BLOCKS = 5

    def __init__(self, world: Any = None):
        self._world = world
        self._entries: dict[str, EventEntry] = {}
        self._synthesis: list[SynthesisBlock] = []
        self._buffer = MemoryBuffer()
        self._last_consolidation: float = 0.0
        self._stats = {
            "entries_total": 0,
            "synthesis_total": 0,
            "consolidation_count": 0,
            "bind_count": 0,
        }

    async def bind_events(
        self,
        session_id: str,
        messages: list[dict],
        timestamp: str | None = None,
    ) -> list[EventEntry]:
        """Extract dual-perspective entries from a set of conversation messages.

        Called after each LifeEngine cycle. Extracts FACT and RELATION
        perspectives for user and assistant messages.

        Args:
            session_id: Current session identifier
            messages: List of {"role": "user"|"assistant", "content": "..."}
            timestamp: ISO timestamp (defaults to now)

        Returns:
            List of newly created EventEntry objects
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        new_entries = []

        for msg in messages:
            if msg.get("role") not in ("user", "assistant"):
                continue
            content = msg.get("content", "").strip()
            if not content or len(content) < 10:
                continue

            entry_id = self._make_id(session_id, ts, msg["role"])
            if entry_id in self._entries:
                continue

            fact = await self._extract_fact(content)
            rel = await self._extract_rel(content)

            embedding = await self._compute_embedding(fact + " " + rel)

            entry = EventEntry(
                id=entry_id,
                session_id=session_id,
                timestamp=ts,
                role=msg["role"],
                content=content,
                fact_perspective=fact,
                rel_perspective=rel,
                embedding=embedding,
                sources=[session_id],
            )

            self._entries[entry_id] = entry
            self._buffer.add(entry)
            new_entries.append(entry)
            self._stats["entries_total"] += 1

        self._stats["bind_count"] += 1
        logger.debug(f"StructMem bound {len(new_entries)} entries (total={self._stats['entries_total']})")
        return new_entries

    async def consolidate_if_needed(self) -> list[SynthesisBlock]:
        """Trigger batch consolidation if buffer exceeds time threshold.

        Returns newly created synthesis blocks, or empty list if not yet due.
        """
        if self._buffer.elapsed_seconds() < self.CONSOLIDATION_THRESHOLD_SECONDS:
            return []

        if len(self._buffer.entries) < 3:
            return []

        return await self._consolidate()

    async def _consolidate(self) -> list[SynthesisBlock]:
        """Execute a full consolidation cycle."""
        new_blocks = []

        buf = self._buffer
        if not buf.entries:
            return []

        cons_id = self._make_id("consolidation", datetime.now(timezone.utc).isoformat(), "synth")

        # Build query from all buffer entries
        query_text = " ".join(
            e.fact_perspective + " " + e.rel_perspective
            for e in buf.entries[-10:]
        )
        query_embedding = await self._compute_embedding(query_text)

        # Retrieve semantically similar historical entries
        seeds = await self._semantic_retrieve(query_embedding, top_k=self.SEMANTIC_SEEDS)

        # Reconstruct complete events from seed timestamps
        reconstructed = self._reconstruct_events(seeds, buf.entries)

        if not reconstructed:
            self._buffer.clear()
            return []

        # Synthesize cross-event connections via LLM
        synthesis_text = await self._synthesize(buf.entries, reconstructed)

        if synthesis_text and "NO_CONNECTIONS" not in synthesis_text:
            block = SynthesisBlock(
                id=cons_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                content=synthesis_text,
                source_entries=[s.id for s in seeds] + [e.id for e in buf.entries[:5]],
                session_ids=list(set(e.session_id for e in buf.entries)),
            )
            self._synthesis.append(block)
            new_blocks.append(block)
            self._stats["synthesis_total"] += 1

        self._stats["consolidation_count"] += 1
        self._buffer.clear()
        self._last_consolidation = time.time()

        logger.debug(
            f"StructMem consolidated: {len(buf.entries)}→{len(new_blocks)} "
            f"synthesis (total={self._stats['synthesis_total']})"
        )
        return new_blocks

    async def retrieve_for_query(
        self,
        query: str,
        top_k: int = 60,
        n_synthesis: int = 5,
    ) -> tuple[list[EventEntry], list[SynthesisBlock]]:
        """Retrieve entries and synthesis blocks for context injection.

        Args:
            query: The user query
            top_k: Number of entries to retrieve
            n_synthesis: Number of synthesis blocks to retrieve

        Returns:
            (entries, synthesis) — both sorted by relevance
        """
        query_embedding = await self._compute_embedding(query)

        scored_entries = []
        for entry in self._entries.values():
            score = self._cosine_similarity(query_embedding, entry.embedding)
            scored_entries.append((score, entry))
        scored_entries.sort(key=lambda x: x[0], reverse=True)
        entries = [e for _, e in scored_entries[:top_k]]

        scored_synth = []
        for block in self._synthesis:
            block_emb = await self._compute_embedding(block.content)
            score = self._cosine_similarity(query_embedding, block_emb)
            scored_synth.append((score, block))
        scored_synth.sort(key=lambda x: x[0], reverse=True)
        synthesis = [b for _, b in scored_synth[:n_synthesis]]

        return entries, synthesis

    def get_context_block(self, query: str = "", entries: list[EventEntry] | None = None,
                          synthesis: list[SynthesisBlock] | None = None) -> str:
        """Format retrieved memory for injection into the model's system prompt.

        Args:
            query: The original query (for context)
            entries: Pre-retrieved entries (auto-retrieves if None)
            synthesis: Pre-retrieved synthesis blocks (auto-retrieves if None)

        Returns:
            Formatted context block string for LLM prompt injection
        """
        parts = []

        if synthesis:
            parts.append("[RELEVANT MEMORY SYNTHESIS]")
            for i, block in enumerate(synthesis[:5]):
                parts.append(f"S{i+1}: {block.content}")

        if entries:
            parts.append("[RELATED PAST EVENTS]")
            for i, entry in enumerate(entries[:20]):
                ts_short = entry.timestamp[:19] if entry.timestamp else "?"
                role = "U" if entry.role == "user" else "A"
                text = entry.fact_perspective or entry.content[:100]
                parts.append(f"[{ts_short}] {role}: {text}")

        return "\n".join(parts) if parts else ""

    def get_stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "buffer_size": len(self._buffer.entries),
            "buffer_age_s": int(self._buffer.elapsed_seconds()),
            "total_entries_stored": len(self._entries),
            "total_synthesis_stored": len(self._synthesis),
        }

    # ── Private helpers ──

    async def _extract_fact(self, utterance: str) -> str:
        try:
            engine = getattr(self._world, 'extraction_engine', None) if self._world else None
            if engine and engine._lx_available:
                results = engine.extract(
                    text=utterance[:3000],
                    classes=["fact"],
                    prompt_description=FACT_EXTRACT_PROMPT.format(utterance="{text}"),
                    model_id="",
                )
                if results:
                    return "\n".join(
                        f"- {r.extraction_text}  [{r.char_start}:{r.char_end}]"
                        for r in results[:10]
                    )
        except Exception as e:
            logger.debug(f"StructMem grounded fact: {e}")

        # Fallback: raw LLM extraction
        try:
            consciousness = self._world.consciousness if self._world else None
            if consciousness:
                result = await consciousness.chain_of_thought(
                    FACT_EXTRACT_PROMPT.format(utterance=utterance[:2000]),
                    steps=1, temperature=0.3, max_tokens=512,
                )
                return result.strip()
        except Exception as e:
            logger.debug(f"StructMem fact extract: {e}")
        return utterance[:200]

    async def _extract_rel(self, utterance: str) -> str:
        try:
            engine = getattr(self._world, 'extraction_engine', None) if self._world else None
            if engine and engine._lx_available:
                results = engine.extract(
                    text=utterance[:3000],
                    classes=["relation"],
                    prompt_description=REL_EXTRACT_PROMPT.format(utterance="{text}"),
                    model_id="",
                )
                if results:
                    return "\n".join(
                        f"- {r.extraction_text}  [{r.char_start}:{r.char_end}]"
                        for r in results[:10]
                    )
        except Exception as e:
            logger.debug(f"StructMem grounded rel: {e}")

        try:
            consciousness = self._world.consciousness if self._world else None
            if consciousness:
                result = await consciousness.chain_of_thought(
                    REL_EXTRACT_PROMPT.format(utterance=utterance[:2000]),
                    steps=1, temperature=0.3, max_tokens=512,
                )
                return result.strip()
        except Exception as e:
            logger.debug(f"StructMem rel extract: {e}")
        return ""

    async def _compute_embedding(self, text: str) -> list[float]:
        if not text:
            return []
        try:
            vs = self._world.vector_store if self._world else None
            if vs and hasattr(vs, 'encode'):
                emb = await vs.encode(text)
                return emb.tolist() if hasattr(emb, 'tolist') else list(emb)
        except Exception as e:
            logger.debug(f"StructMem embed: {e}")
        return []

    async def _semantic_retrieve(
        self,
        query_embedding: list[float],
        top_k: int = 15,
    ) -> list[EventEntry]:
        if not query_embedding:
            return list(self._entries.values())[-top_k:]

        scored = []
        for entry in self._entries.values():
            if entry.id in {e.id for e in self._buffer.entries}:
                continue
            score = self._cosine_similarity(query_embedding, entry.embedding)
            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:top_k]]

    def _reconstruct_events(
        self,
        seeds: list[EventEntry],
        buffer_entries: list[EventEntry],
    ) -> list[EventEntry]:
        seen_ids = {e.id for e in buffer_entries}
        result = list(buffer_entries)

        for seed in seeds:
            if seed.id in seen_ids:
                continue
            for entry in self._entries.values():
                if entry.timestamp == seed.timestamp and entry.id not in seen_ids:
                    result.append(entry)
                    seen_ids.add(entry.id)

        return result

    async def _synthesize(
        self,
        buffer_entries: list[EventEntry],
        reconstructed: list[EventEntry],
    ) -> str:
        buf_text = "\n".join(
            f"[{e.timestamp[:19]}] {e.role}: {e.fact_perspective or e.content[:100]}"
            for e in buffer_entries[-10:]
        )
        hist_text = "\n".join(
            f"[{e.timestamp[:19]}] {e.role}: {e.fact_perspective or e.content[:100]}"
            for e in reconstructed[:15]
            if e not in buffer_entries
        )

        context = (
            f"[BUFFER EVENTS]\n{buf_text}\n\n"
            f"[HISTORICAL EVENTS]\n{hist_text}"
        )

        try:
            consciousness = self._world.consciousness if self._world else None
            if consciousness:
                result = await consciousness.chain_of_thought(
                    CONSOLIDATION_PROMPT.format(context=context),
                    steps=2,
                    temperature=0.5,
                    max_tokens=1024,
                )
                return result.strip()
        except Exception as e:
            logger.debug(f"StructMem synthesis: {e}")

        return ""

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _make_id(session: str, ts: str, role: str) -> str:
        import hashlib
        raw = f"{session}:{ts}:{role}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]
